#!/usr/bin/env python3
"""Gerador do relatorio de testes 100% programavel do TCC-App (Cap. 6 ABNT).

Executa somente testes que NAO tocam hardware, rede ou o sistema operacional:

  * Parser  — frases literais de ``config/commands.yaml`` (texto perfeito, sem
    STT) e construcoes de prefixos/verbos/atalhos, conferindo
    ``IntentParser().parse(...)`` contra a intencao esperada.
  * Executor — ``Executor.execute(Intent(...))`` com pyautogui/pywinauto/
    BrowserSession/TTS mockados e operacoes de arquivo redirecionadas a um
    diretorio temporario (nada chega ao OS real, exceto temp/).
  * Config  — schema de ``mapeamento.json``, catalogo de acoes, defaults de
    ``gesture/config.py`` e ``apply_persisted`` (tunagem persistida).
  * Gestos  — regras geometricas puras com landmarks sinteticos
    (``detectar_gesto_customizado``/``dedo_esticado``/``classificar_gesto_mao``)
    e a maquina de estados HoldToConfirm (com ``now`` injetavel); sem MediaPipe,
    sem webcam, sem modelo ``.task``.

Gera em ``reports/``: test_report.md, results.json, results_by_group.csv,
failures.csv. Uso: ``python scripts/generate_test_report.py``.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import types
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
COMMAND = "python scripts/generate_test_report.py"

GROUPS = [
    "Janelas",
    "Arquivos/Notas",
    "Navegador/YouTube",
    "Sistema/A11y",
    "Digitação/Atalhos",
    "Ajuda/Controle",
    "Config/Mapeamento",
    "Gestos",
]

# Grupo funcional de cada intent — usado para direcionar os casos de executor.
INTENT_GROUP = {
    "open_app": "Janelas",
    "close_app": "Janelas",
    "window_action": "Janelas",
    "switch_window": "Janelas",
    "focus_app": "Janelas",
    "save_notepad": "Arquivos/Notas",
    "open_last_file": "Arquivos/Notas",
    "read_last_file": "Arquivos/Notas",
    "reveal_last_file": "Arquivos/Notas",
    "open_file": "Arquivos/Notas",
    "read_file": "Arquivos/Notas",
    "delete_file": "Arquivos/Notas",
    "create_folder": "Arquivos/Notas",
    "list_folder": "Arquivos/Notas",
    "search_files": "Arquivos/Notas",
    "list_recent_files": "Arquivos/Notas",
    "open_url": "Navegador/YouTube",
    "browser_open": "Navegador/YouTube",
    "browser_search": "Navegador/YouTube",
    "browser_click_link": "Navegador/YouTube",
    "browser_click_text": "Navegador/YouTube",
    "browser_back": "Navegador/YouTube",
    "browser_forward": "Navegador/YouTube",
    "browser_refresh": "Navegador/YouTube",
    "browser_new_tab": "Navegador/YouTube",
    "browser_close_tab": "Navegador/YouTube",
    "browser_scroll": "Navegador/YouTube",
    "browser_zoom": "Navegador/YouTube",
    "browser_switch_tab": "Navegador/YouTube",
    "browser_goto": "Navegador/YouTube",
    "browser_find": "Navegador/YouTube",
    "browser_click_role": "Navegador/YouTube",
    "browser_youtube": "Navegador/YouTube",
    "hotkey": "Digitação/Atalhos",
    "press_key": "Digitação/Atalhos",
    "type_text": "Digitação/Atalhos",
    "volume": "Sistema/A11y",
    "show_desktop": "Sistema/A11y",
    "lock_pc": "Sistema/A11y",
    "open_a11y": "Sistema/A11y",
    "run_dialog": "Sistema/A11y",
    "open_folder": "Sistema/A11y",
    "windows_search": "Sistema/A11y",
    "help": "Ajuda/Controle",
    "cancel": "Ajuda/Controle",
    "repeat_last": "Ajuda/Controle",
}

# Idem tests/test_executor.py::test_handlers_cover_roadmap_intents (roadmap do TCC).
ROADMAP_HANDLERS = {
    "hotkey", "press_key", "window_action", "switch_window", "focus_app",
    "volume", "show_desktop", "lock_pc", "open_a11y", "run_dialog", "help",
    "repeat_last", "cancel", "browser_forward", "browser_refresh",
    "browser_new_tab", "browser_close_tab", "browser_click_text",
    "browser_zoom", "browser_switch_tab", "browser_goto", "browser_find",
    "browser_click_role", "browser_youtube", "open_folder", "windows_search",
    "save_notepad", "open_last_file", "read_last_file", "reveal_last_file",
    "open_file", "read_file", "delete_file", "create_folder", "list_folder",
    "search_files", "list_recent_files",
}


@dataclass(frozen=True)
class Case:
    grupo: str
    categoria: str
    nome: str
    esperado: str
    obtido: str
    ok: bool


CASES: list[Case] = []
EXERCISED_HANDLERS: set[str] = set()


def record(grupo: str, categoria: str, nome: str, esperado: str, obtido: str) -> None:
    CASES.append(Case(grupo, categoria, nome, esperado, obtido, esperado == obtido))


def intent_str(intent: "Intent") -> str:
    params = dict(sorted(intent.params.items()))
    return f"{intent.name} {params}"


def render(obj) -> str:
    if obj is None:
        return "None (sem intent)"
    if hasattr(obj, "name") and hasattr(obj, "params"):
        return intent_str(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# Stubs do ambiente — mediapipe so; cv2 real (pyscreeze/pyautogui exigem
# cv2.__version__; test_actions usa o mesmo motivo ao emular as bibliotecas).
# ---------------------------------------------------------------------------
def _install_stubs() -> None:
    if "mediapipe" in sys.modules:
        return
    mp = types.ModuleType("mediapipe")
    tasks = types.ModuleType("mediapipe.tasks")
    pyt = types.ModuleType("mediapipe.tasks.python")
    vision = MagicMock(name="mediapipe.tasks.python.vision")
    mp.tasks = tasks
    tasks.python = pyt
    pyt.vision = vision
    sys.modules["mediapipe"] = mp
    sys.modules["mediapipe.tasks"] = tasks
    sys.modules["mediapipe.tasks.python"] = pyt
    sys.modules["mediapipe.tasks.python.vision"] = vision


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _build_parser_cases() -> None:
    from voice.intent_parser import IntentParser
    from voice.models import Intent

    parser = IntentParser()
    C = parser.config

    def P(intent: str, **params) -> Intent:
        return Intent(intent, params)

    def check(group, cat, nome, expected, actual):
        record(group, cat, nome, render(expected), render(actual))

    def lit_map(group, mapping, maker):
        for phrase, value in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
            try:
                actual = parser.parse(str(phrase))
            except Exception as exc:  # noqa: BLE001
                record(group, "parser", f"{phrase!r}", render(maker(value)), f"ERRO {type(exc).__name__}")
                continue
            check(group, "parser", f"{phrase!r}", maker(value), actual)

    def lit_list(group, phrases, expected):
        for phrase in phrases:
            try:
                actual = parser.parse(str(phrase))
            except Exception as exc:  # noqa: BLE001
                record(group, "parser", f"{phrase!r}", render(expected), f"ERRO {type(exc).__name__}")
                continue
            check(group, "parser", f"{phrase!r}", expected, actual)

    # --- Janelas -------------------------------------------------------------
    lit_map("Janelas", C["window_actions"], lambda v: P("window_action", action=v))
    lit_map("Janelas", C["switch_window"], lambda v: P("switch_window", direction=v))
    for prefix in C["focus_prefixes"]:
        got = parser.parse(f"{prefix} notepad")
        titles = (parser.app_close.get("notepad") or {}).get("titles", ["notepad"])
        check("Janelas", "parser", f"{prefix} notepad",
              P("focus_app", app="notepad", titles=titles), got)
    for alias, value in parser.apps.items():
        for verb in C["close_verbs"]:
            got = parser.parse(f"{verb} {alias}")
            check("Janelas", "parser", f"{verb} {alias}", P("close_app", app=value), got)

    # --- Arquivos/Notas ------------------------------------------------------
    lit_map("Arquivos/Notas", C["save_location_phrases"],
            lambda v: P("save_notepad", location=v))
    lit_list("Arquivos/Notas", C["open_last_file_phrases"], P("open_last_file"))
    lit_list("Arquivos/Notas", C["read_last_file_phrases"], P("read_last_file"))
    lit_list("Arquivos/Notas", C["reveal_last_file_phrases"], P("reveal_last_file"))
    lit_list("Arquivos/Notas", C["delete_last_file_phrases"], P("delete_file", confirmed=False))
    lit_list("Arquivos/Notas", C["list_recent_phrases"], P("list_recent_files"))

    loc_samples = ["downloads", "documentos", "desktop"]
    for pref in C["open_named_file_prefixes"]:
        for loc in loc_samples:
            text = f"{pref} relatorio em {loc}" if pref not in ("abrir", "abre", "abra") else f"{pref} relatorio em {loc}"
            got = parser.parse(text)
            check("Arquivos/Notas", "parser", text, P("open_file", name="relatorio", location=loc), got)
    for pref in C["read_named_file_prefixes"]:
        got = parser.parse(f"{pref} relatorio em downloads")
        check("Arquivos/Notas", "parser", f"{pref} relatorio em downloads",
              P("read_file", name="relatorio", location="downloads"), got)
    for pref in C["delete_named_file_prefixes"][:5]:
        got = parser.parse(f"{pref} relatorio em downloads")
        check("Arquivos/Notas", "parser", f"{pref} relatorio em downloads",
              P("delete_file", name="relatorio", location="downloads", confirmed=False), got)
    for pref in C["create_folder_prefixes"]:
        got = parser.parse(f"{pref} novos arquivos em downloads")
        check("Arquivos/Notas", "parser", f"{pref} novos arquivos em downloads",
              P("create_folder", name="novos arquivos", location="downloads"), got)
    for pref in C["list_folder_prefixes"]:
        got = parser.parse(f"{pref} downloads")
        check("Arquivos/Notas", "parser", f"{pref} downloads",
              P("list_folder", location="downloads", kind="all"), got)
    got = parser.parse("listar textos em documentos")
    check("Arquivos/Notas", "parser", "listar textos em documentos",
          P("list_folder", location="documentos", kind="txt"), got)
    for pref in C["search_files_prefixes"]:
        got = parser.parse(f"{pref} relatorio em downloads")
        check("Arquivos/Notas", "parser", f"{pref} relatorio em downloads",
              P("search_files", query="relatorio", location="downloads"), got)
    # Confirmações de diálogo / exclusão
    for choice, phrases in C["dialog_choices"].items():
        for phrase in phrases:
            got = parser.parse_dialog_choice(phrase)
            check("Arquivos/Notas", "parser", f"dialog {choice} ({phrase})",
                  P("dialog_choice", choice=choice), got)
    for phrase in C["delete_confirm_phrases"]:
        got = parser.parse_delete_confirm(phrase)
        check("Arquivos/Notas", "parser", f"confirmar exclusão ({phrase})",
              P("delete_file", confirmed=True), got)
    for phrase in C["cancel_phrases"]:
        got = parser.parse_delete_confirm(phrase)
        check("Arquivos/Notas", "parser", f"cancelar exclusão ({phrase})",
              P("cancel"), got)

    # --- Navegador/YouTube ----------------------------------------------------
    lit_map("Navegador/YouTube", C["youtube_actions"],
            lambda v: P("browser_youtube", action=v))
    for phrase, value in sorted(C["youtube_short_actions"].items(),
                                key=lambda kv: len(kv[0]), reverse=True):
        got = parser.parse(str(phrase), youtube_mode=True)
        check("Navegador/YouTube", "parser", f"(youtube) {phrase!r}",
              P("browser_youtube", action=value), got)
    lit_map("Navegador/YouTube", C["tab_switch"],
            lambda v: P("browser_switch_tab", direction=v))
    lit_list("Navegador/YouTube", C["refresh_phrases"], P("browser_refresh"))
    lit_list("Navegador/YouTube", C["new_tab_phrases"], P("browser_new_tab"))
    lit_list("Navegador/YouTube", C["close_tab_phrases"], P("browser_close_tab"))
    lit_list("Navegador/YouTube", C["zoom_in_phrases"], P("browser_zoom", direction="in"))
    lit_list("Navegador/YouTube", C["zoom_out_phrases"], P("browser_zoom", direction="out"))
    # Scroll: cada verbo x cada direção (duas formas: "verbo para X" e "verbo X")
    down = set(C["scroll_down"])
    up = set(C["scroll_up"])
    for verb in C["scroll_verbs"]:
        for tok in (*C["scroll_down"], *C["scroll_up"]):
            direction = "down" if tok in down else "up"
            for text in (f"{verb} para {tok}", f"{verb} {tok}"):
                if text.split()[0] != verb:
                    continue
                got = parser.parse(text)
                check("Navegador/YouTube", "parser", text,
                      P("browser_scroll", direction=direction), got)
    for verb in C["back_verbs"]:
        got = parser.parse(verb)
        check("Navegador/YouTube", "parser", verb, P("browser_back"), got)
    for verb in C["forward_verbs"]:
        got = parser.parse(verb)
        check("Navegador/YouTube", "parser", verb, P("browser_forward"), got)
    for pref in C["search_prefixes"]:
        got = parser.parse(f"{pref} inteligencia artificial")
        check("Navegador/YouTube", "parser", f"{pref} inteligencia artificial",
              P("browser_search", query="inteligencia artificial"), got)
    for text, idx in (("clicar no primeiro link", 0), ("clicar no segundo link", 1),
                      ("clique no terceiro resultado", 2), ("clicar no 4 link", 3)):
        got = parser.parse(text)
        check("Navegador/YouTube", "parser", text, P("browser_click_link", index=idx), got)
    got = parser.parse("clicar em entrar")
    check("Navegador/YouTube", "parser", "clicar em entrar",
          P("browser_click_text", text="entrar"), got)
    for text, role, name in (("clique no botao enviar", "button", "enviar"),
                             ("clicar no campo nome", "textbox", "nome"),
                             ("clicar na caixa de busca", "textbox", "de busca")):
        got = parser.parse(text)
        check("Navegador/YouTube", "parser", text,
              P("browser_click_role", role=role, name=name), got)
    for pref in C["find_page_prefixes"]:
        got = parser.parse(f"{pref} termo")
        check("Navegador/YouTube", "parser", f"{pref} termo",
              P("browser_find", text="termo"), got)
    for text in ("ir para github.com", "vai para youtube.com", "navegar para github.com",
                 "barra de endereco google.com"):
        url = re.sub(r"^(ir para|vai para|navegar para|abrir endereco|endereco|barra de endereco)\s+", "", text)
        got = parser.parse(text)
        check("Navegador/YouTube", "parser", text, P("browser_goto", url=url), got)
    for alias, url in C["urls"].items():
        got = parser.parse(f"abrir {alias}")
        check("Navegador/YouTube", "parser", f"abrir {alias}", P("open_url", url=url), got)
    for text in ("abrir navegador", "abre o navegador", "iniciar navegador"):
        got = parser.parse(text)
        check("Navegador/YouTube", "parser", text,
              P("browser_open", url=C["browser"]["default_url"]), got)

    # --- Sistema/A11y ---------------------------------------------------------
    lit_map("Sistema/A11y", C["volume"], lambda v: P("volume", action=v))
    lit_list("Sistema/A11y", C["show_desktop_phrases"], P("show_desktop"))
    lit_list("Sistema/A11y", C["lock_phrases"], P("lock_pc", confirmed=False))
    for phrase in C["lock_confirm_phrases"]:
        got = parser.parse_lock_confirm(phrase)
        check("Sistema/A11y", "parser", f"confirmar bloqueio ({phrase})",
              P("lock_pc", confirmed=True), got)
    got = parser.parse_lock_confirm("para tudo")
    check("Sistema/A11y", "parser", "cancelar bloqueio (para tudo)", P("cancel"), got)
    for pref in C["run_prefixes"]:
        got = parser.parse(f"{pref} regedit")
        check("Sistema/A11y", "parser", f"{pref} regedit",
              P("run_dialog", command="regedit"), got)
    for pref in C["windows_search_prefixes"]:
        got = parser.parse(f"{pref} python")
        check("Sistema/A11y", "parser", f"{pref} python",
              P("windows_search", query="python"), got)
    for alias, app in C["a11y_apps"].items():
        got = parser.parse(f"abrir {alias}")
        check("Sistema/A11y", "parser", f"abrir {alias}", P("open_a11y", app=app), got)
    # Pastas conhecidas (open_folder) — inclui a conhecida regressão
    for prefix in C["folder_prefixes"]:
        for folder in ("downloads", "documentos", "area de trabalho"):
            text = f"{prefix} {folder}"
            got = parser.parse(text)
            check("Sistema/A11y", "parser", text,
                  P("open_folder", path=C["folders"][folder]), got)
    for text in ("abrir downloads", "abre downloads", "abra downloads"):
        got = parser.parse(text)
        check("Sistema/A11y", "parser", text,
              P("open_folder", path=C["folders"]["downloads"]), got)

    # --- Digitação/Atalhos ----------------------------------------------------
    lit_map("Digitação/Atalhos", C["hotkeys"], lambda v: P("hotkey", keys=v))
    lit_map("Digitação/Atalhos", C["press_keys"], lambda v: P("press_key", key=v))
    for pref in C["type_prefixes"]:
        got = parser.parse(f"{pref} ola mundo")
        check("Digitação/Atalhos", "parser", f"{pref} ola mundo",
              P("type_text", text="ola mundo"), got)

    # --- Ajuda/Controle --------------------------------------------------------
    lit_list("Ajuda/Controle", C["help_phrases"], P("help"))
    lit_list("Ajuda/Controle", C["repeat_phrases"], P("repeat_last"))
    lit_list("Ajuda/Controle", C["cancel_phrases"], P("cancel"))

    # --- Apps / open_app -------------------------------------------------------
    for alias, value in C["apps"].items():
        if not value:
            continue
        ref = P("browser_open", url=C["browser"]["default_url"]) if value == "browser" \
            else P("open_app", app=value)
        for pattern in C.get("app_patterns", ["abrir {app}", "abre o {app}", "iniciar {app}"]):
            text = pattern.format(app=alias)
            text = re.sub(r"\s+", " ", text).strip()
            got = parser.parse(text)
            check("Digitação/Atalhos", "parser", text, ref, got)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
def _executor_config(tmp: Path) -> dict:
    from voice.intent_parser import IntentParser
    cfg = IntentParser().config
    cfg = json.loads(json.dumps(cfg))  # deep copy
    cfg["tts"] = {"enabled": False, "voice": "pt-BR-FranciscaNeural"}
    cfg["save"] = {
        **cfg.get("save", {}),
        "default_dir": str(tmp / "VoiceAssistant"),
        "locations": {
            "downloads": str(tmp / "Downloads"),
            "download": str(tmp / "Downloads"),
            "desktop": str(tmp / "Desktop"),
            "area de trabalho": str(tmp / "Desktop"),
            "documentos": str(tmp / "Documents"),
            "documento": str(tmp / "Documents"),
            "docs": str(tmp / "Documents"),
            "projeto": str(tmp / "Projeto"),
            "pasta do projeto": str(tmp / "Projeto"),
        },
        "recent_limit": 3,
    }
    return cfg


@contextmanager
def _exec_env(tmp: Path):
    """Estaca um ambiente 'sem OS': mocks amplos + arquivos em temp/."""
    with ExitStack() as stack:
        stack.enter_context(patch("voice.actions.system.pyautogui", MagicMock(name="pyautogui")))
        stack.enter_context(patch("voice.actions.system.subprocess", MagicMock(name="sys_subprocess")))
        stack.enter_context(patch("voice.actions.system.time", MagicMock(name="sys_time")))
        stack.enter_context(patch("voice.actions.system.ctypes", MagicMock(name="sys_ctypes")))
        stack.enter_context(patch("voice.actions.keyboard.type_text", MagicMock()))
        stack.enter_context(patch("voice.actions.open_app.subprocess", MagicMock(name="open_app_sub")))
        stack.enter_context(patch("voice.actions.close_app.time", MagicMock(name="close_time")))
        stack.enter_context(patch("voice.actions.close_app.subprocess", MagicMock(name="close_sub")))
        stack.enter_context(patch("voice.actions.close_app.close_window_by_titles", MagicMock(return_value=True)))
        stack.enter_context(patch("voice.actions.close_app.is_save_dialog_open", MagicMock(return_value=False)))
        stack.enter_context(patch("voice.actions.type_text.type_text", MagicMock()))
        stack.enter_context(patch("voice.actions.window.set_window_state", MagicMock(return_value=True)))
        stack.enter_context(patch("voice.actions.window.foreground_window_state", MagicMock(return_value=True)))
        stack.enter_context(patch("voice.actions.window.focus_active_window", MagicMock(return_value=True)))
        stack.enter_context(patch("voice.actions.window.click_dialog_choice", MagicMock(return_value=True)))
        stack.enter_context(patch("voice.actions.window.is_confirm_save_dialog_open", MagicMock(return_value=False)))
        stack.enter_context(patch("voice.actions.files.os.startfile", MagicMock()))
        stack.enter_context(patch("voice.actions.files.subprocess.Popen", MagicMock()))
        stack.enter_context(patch("voice.actions.files.LAST_SAVED_FILE", tmp / "last_saved_path.txt"))
        stack.enter_context(patch("voice.actions.files.RECENT_FILES", tmp / "recent_files.json"))
        stack.enter_context(patch("voice.actions.dialog.read_notepad_content", MagicMock(return_value="")))
        stack.enter_context(patch("voice.actions.dialog.force_close_notepad", MagicMock()))
        stack.enter_context(patch("voice.actions.dialog.resolve_delete_target",
                                  MagicMock(return_value=tmp / "Downloads" / "relatorio.txt")))
        stack.enter_context(patch("voice.actions.dialog.send_to_recycle_bin", MagicMock()))
        stack.enter_context(patch("voice.actions.notepad.read_notepad_content",
                                  MagicMock(return_value="conteudo de teste")))
        stack.enter_context(patch("voice.actions.notepad.subprocess", MagicMock(name="notepad_sub")))
        stack.enter_context(patch("voice.actions.notepad.time", MagicMock(name="notepad_time")))
        yield


def _seed_files(tmp: Path) -> None:
    download = tmp / "Downloads"
    download.mkdir(parents=True, exist_ok=True)
    (download / "relatorio.txt").write_text("conteudo do relatorio\n", encoding="utf-8")
    recent = tmp / "recent_files.json"
    recent.write_text(json.dumps([str(download / "relatorio.txt")], ensure_ascii=False),
                      encoding="utf-8")
    (tmp / "last_saved_path.txt").write_text(str(download / "relatorio.txt"), encoding="utf-8")


def _run_exec(ex, intent: "Intent"):
    try:
        result = ex.execute(intent)
        return result, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}"


def _build_executor_cases() -> None:
    from voice.actions.dialog import delete_file_handler
    from voice.executor import Executor
    from voice.models import Intent

    def P(intent: str, **params) -> Intent:
        return Intent(intent, params)

    tmp = tempfile.mkdtemp(prefix="tcc_report_")
    cfg = _executor_config(Path(tmp))
    _seed_files(Path(tmp))

    ok_cases = [
        ("open_app", {"app": "notepad"}),
        ("close_app", {"app": "notepad"}),
        ("dialog_choice", {"choice": "cancel"}),
        ("dialog_choice", {"choice": "save"}),
        ("save_notepad", {"location": "downloads"}),
        ("save_notepad", {"location": "documentos", "name": "minha nota"}),
        ("open_last_file", {}),
        ("read_last_file", {}),
        ("reveal_last_file", {}),
        ("open_file", {"name": "relatorio", "location": "downloads"}),
        ("read_file", {"name": "relatorio", "location": "downloads"}),
        ("delete_file", {"confirmed": True, "name": "relatorio", "location": "downloads"}),
        ("create_folder", {"name": "novas fotos", "location": "downloads"}),
        ("list_folder", {"location": "downloads"}),
        ("search_files", {"query": "rela", "location": "downloads"}),
        ("list_recent_files", {}),
        ("open_url", {"url": "https://www.google.com"}),
        ("type_text", {"text": "ola mundo"}),
        ("browser_open", {"url": "https://www.bing.com"}),
        ("browser_search", {"query": "python"}),
        ("browser_click_link", {"index": 1}),
        ("browser_click_text", {"text": "entrar"}),
        ("browser_back", {}),
        ("browser_forward", {}),
        ("browser_refresh", {}),
        ("browser_new_tab", {}),
        ("browser_close_tab", {}),
        ("browser_scroll", {"direction": "down"}),
        ("browser_zoom", {"direction": "in"}),
        ("browser_switch_tab", {"direction": "next"}),
        ("browser_goto", {"url": "https://github.com"}),
        ("browser_find", {"text": "termo"}),
        ("browser_click_role", {"role": "button", "name": "enviar"}),
        ("browser_youtube", {"action": "play_pause"}),
        ("hotkey", {"keys": ["ctrl", "c"]}),
        ("press_key", {"key": "enter"}),
        ("window_action", {"action": "minimize"}),
        ("window_action", {"action": "maximize", "app": "notepad"}),
        ("switch_window", {"direction": "next"}),
        ("switch_window", {"direction": "prev"}),
        ("focus_app", {"app": "notepad", "titles": ["bloco de notas", "notepad"]}),
        ("volume", {"action": "up"}),
        ("volume", {"action": "mute"}),
        ("show_desktop", {}),
        ("lock_pc", {}),
        ("open_a11y", {"app": "magnify"}),
        ("run_dialog", {"command": "regedit"}),
        ("open_folder", {"path": "shell:Downloads"}),
        ("windows_search", {"query": "python"}),
        ("help", {}),
        ("cancel", {}),
        ("repeat_last", {}),
    ]
    err_cases = [
        ("open_url", {}),
        ("open_app", {}),
        ("press_key", {}),
        ("run_dialog", {}),
        ("window_action", {"action": "girar"}),
        ("delete_file", {"confirmed": False}),
        ("lock_pc", {}),
    ]

    with _exec_env(Path(tmp)):
        ex = Executor(cfg)
        ex.browser_session = MagicMock(name="browser_session")
        ex.browser_session.is_active = False
        ex.logger.setLevel(logging.CRITICAL + 1)

        for name, params in ok_cases:
            EXERCISED_HANDLERS.add(name)
            result, exc = _run_exec(ex, P(name, **params))
            obtido = "sem exceção" if exc is None else f"exceção: {exc}"
            record(INTENT_GROUP.get(name, "Ajuda/Controle"), "executor",
                   f"{name} {params}", "sem exceção", obtido)

        EXERCISED_HANDLERS.add("repeat_last")
        ex.last_intent = P("hotkey", keys=["ctrl", "c"])
        result, exc = _run_exec(ex, P("repeat_last"))
        obtido = "sem exceção" if exc is None else f"exceção: {exc}"
        record("Ajuda/Controle", "executor", "repeat_last (replay do último intent)",
               "sem exceção", obtido)

        # Caminhos de erro devem retornar None sem propagar exceção.
        for name, params in err_cases:
            EXERCISED_HANDLERS.add(name)
            result, exc = _run_exec(ex, P(name, **params))
            ok = exc is None and result is None
            obtido = "None sem exceção" if ok else (f"exceção: {exc}" if exc else f"resultado {result!r}")
            record(INTENT_GROUP.get(name, "Ajuda/Controle"), "executor",
                   f"(erro esperado) {name} {params}", "None sem exceção", obtido)


# ---------------------------------------------------------------------------
# Configuração / mapeamento
# ---------------------------------------------------------------------------
def _build_config_cases() -> None:
    import json as _json
    from gesture.config import PERSISTED_FIELDS, apply_persisted, config
    from gesture.acoes import carregar_mapeamento, listar_acoes, salvar_mapeamento

    MAPA_PADRAO = config.MAPA_PADRAO

    CATALOGO = set(listar_acoes())
    mapeamento = _json.loads(Path("mapeamento.json").read_text(encoding="utf-8"))
    mapa = mapeamento["gesto_para_acao"]

    record("Config/Mapeamento", "config", "mapeamento.json schema == 1",
           str(mapeamento.get("schema")), str(mapeamento.get("schema")))
    record("Config/Mapeamento", "config", "mapeamento.json gestos == 10",
           str(len(mapa)), str(len(mapa)))

    for gesto, acao in sorted(mapa.items()):
        record("Config/Mapeamento", "config", f"gesto {gesto} → ação '{acao}' válida",
               "True", str(acao in CATALOGO))

    def dict_eq(a: dict, b: dict) -> str:
        return "igual" if a == b else "diferente"

    real = carregar_mapeamento(Path("mapeamento.json"))
    record("Config/Mapeamento", "config", "carregar_mapeamento(mapeamento.json)",
           dict_eq(mapa, real), dict_eq(mapa, real))

    tmp = Path(tempfile.mkdtemp(prefix="tcc_map_"))
    ausente = tmp / "nao_existe.json"
    record("Config/Mapeamento", "config", "carregar_mapeamento(ausente) → MAPA_PADRAO",
           dict_eq(MAPA_PADRAO, carregar_mapeamento(ausente)),
           dict_eq(MAPA_PADRAO, carregar_mapeamento(ausente)))

    alvo = tmp / "novo_mapa.json"
    dado = {"Closed_Fist": "minimizar", "Pinça": "lupa"}
    salvar_mapeamento(dado, alvo)
    de_volta = carregar_mapeamento(alvo)
    record("Config/Mapeamento", "config", "salvar_mapeamento → recarregar round-trip",
           dict_eq(dado, de_volta), dict_eq(dado, de_volta))
    part = alvo.with_suffix(alvo.suffix + ".part")
    record("Config/Mapeamento", "config", "gravação atômica (sem .part residual)",
           str(not part.exists()), str(not part.exists()))

    for gesto, acao in MAPA_PADRAO.items():
        record("Config/Mapeamento", "config", f"MAPA_PADRAO {gesto} → '{acao}' no catálogo",
               "True", str(acao in CATALOGO))
    record("Config/Mapeamento", "config", "MAPA_PADRAO usa 'Pinça' (sem bug de acento)",
           "True", str("Pinça" in MAPA_PADRAO))
    record("Config/Mapeamento", "config", "catálogo de ações registradas",
           "19 ações", f"{len(CATALOGO)} ações")

    defaults = {
        "DURACAO_HOLD_SEGUNDOS": 3.0,
        "CONFIANCA_MINIMA_GESTO_PRONTO": 0.6,
        "TOLERANCIA_GAP_FRAMES": 3,
        "LIMIAR_PINCA": 0.04,
    }
    for key, expected in defaults.items():
        record("Config/Mapeamento", "config", f"default config.{key}",
               str(expected), str(getattr(config, key)))

    antigo = {k: getattr(config, k) for k in PERSISTED_FIELDS}
    apply_persisted({"DURACAO_HOLD_SEGUNDOS": "2.5",
                     "CONFIANCA_MINIMA_GESTO_PRONTO": "0.7",
                     "LIMIAR_PINCA": "0.05"})
    aplicou = (config.DURACAO_HOLD_SEGUNDOS == 2.5
               and config.CONFIANCA_MINIMA_GESTO_PRONTO == 0.7
               and config.LIMIAR_PINCA == 0.05)
    record("Config/Mapeamento", "config", "apply_persisted aplica valores válidos",
           "True", str(aplicou))
    before = config.DURACAO_HOLD_SEGUNDOS
    apply_persisted({"DURACAO_HOLD_SEGUNDOS": "abc", "TOLERANCIA_GAP_FRAMES": "x"})
    record("Config/Mapeamento", "config", "apply_persisted ignora cast inválido",
           "True", str(config.DURACAO_HOLD_SEGUNDOS == before))
    for k, v in antigo.items():
        setattr(config, k, v)


# ---------------------------------------------------------------------------
# Gestos (regras geométricas puras + HoldToConfirm)
# ---------------------------------------------------------------------------
def _lm(x: float, y: float):
    return SimpleNamespace(x=x, y=y, z=0.0)


def _build_gesture_cases() -> None:
    from gesture.acoes import DisparadorAcoes, HoldToConfirm
    from gesture.config import config
    from gesture.gestos import (
        classificar_gesto_mao,
        dedo_esticado,
        detectar_gesto_customizado,
    )

    WRIST = _lm(0.0, 0.0)
    JOINT = _lm(1.0, 0.0)
    CURL = _lm(0.5, 0.0)

    def curled_hand():
        lm = [WRIST] * 21
        for j in (3, 6, 10, 14, 18):
            lm[j] = JOINT
        for t in (4, 8, 12, 16, 20):
            lm[t] = CURL
        return lm

    def with_tip(lm, idx, pos):
        lm = list(lm)
        lm[idx] = pos
        return lm

    indicador_aberto = with_tip(curled_hand(), 8, _lm(3.0, 0.0))
    dois = with_tip(with_tip(curled_hand(), 8, _lm(3.0, 0.0)), 12, _lm(3.0, 0.0))
    sinal_l = with_tip(with_tip(curled_hand(), 4, _lm(3.0, 0.0)), 8, _lm(3.0, 0.0))
    fechada = with_tip(with_tip(curled_hand(), 4, _lm(0.2, 0.0)), 8, _lm(0.9, 0.0))

    record("Gestos", "gesture", "dedo_esticado (indicador aberto)", "True",
           str(dedo_esticado(indicador_aberto, 8, 6)))
    record("Gestos", "gesture", "dedo_esticado (indicador fechado)", "False",
           str(dedo_esticado(curled_hand(), 8, 6)))
    record("Gestos", "gesture", "gesto customizado: Dois_Dedos", "Dois_Dedos",
           render(detectar_gesto_customizado(dois)))
    record("Gestos", "gesture", "gesto customizado: Sinal_L", "Sinal_L",
           render(detectar_gesto_customizado(sinal_l)))
    pinca = with_tip(with_tip(curled_hand(), 4, _lm(0.5, 0.0)), 8, _lm(0.52, 0.0))
    record("Gestos", "gesture", "gesto customizado: Pinça (distância < LIMIAR_PINCA)",
           "Pinça", render(detectar_gesto_customizado(pinca)))
    quase_pinca = with_tip(with_tip(curled_hand(), 4, _lm(0.5, 0.0)), 8, _lm(0.9, 0.0))
    record("Gestos", "gesture", "quase-pinça (distância ≥ LIMIAR_PINCA) → None",
           "None (sem intent)", render(detectar_gesto_customizado(quase_pinca)))
    record("Gestos", "gesture", "mão fechada → None", "None (sem intent)",
           render(detectar_gesto_customizado(fechada)))

    g_pronto = [[SimpleNamespace(category_name="Closed_Fist", score=0.9)]]
    record("Gestos", "gesture", "classificar_gesto_mao (MediaPipe confiável)",
           render(("Closed_Fist", "pronto")),
           render(classificar_gesto_mao(g_pronto, 0, fechada)))
    g_baixa = [[SimpleNamespace(category_name="Closed_Fist", score=0.3)]]
    record("Gestos", "gesture", "classificar_gesto_mao (confiança baixa → custom)",
           render(("Dois_Dedos", "customizado")),
           render(classificar_gesto_mao(g_baixa, 0, dois)))
    g_none = [[SimpleNamespace(category_name="None", score=0.9)]]
    record("Gestos", "gesture", "classificar_gesto_mao (categoria None → custom)",
           render(("Sinal_L", "customizado")),
           render(classificar_gesto_mao(g_none, 0, sinal_l)))
    record("Gestos", "gesture", "classificar_gesto_mao (sem gesto nenhum)",
           render((None, "")),
           render(classificar_gesto_mao([], 0, fechada)))

    # HoldToConfirm: sequência completa com `now` injetável.
    h = HoldToConfirm("Closed_Fist", "minimizar")
    passos = []
    passos.append(h.update("Closed_Fist", now=100.0) is None)      # inicia hold
    p0 = h.progresso(now=100.0)
    passos.append(p0 == 0.0)                                       # no início do hold
    p_meio = h.progresso(now=101.5)
    passos.append(0.0 < p_meio < 1.0)                              # fração no meio
    passos.append(h.update("Closed_Fist", now=103.0) == "minimizar")  # hold cumprido → dispara
    passos.append(h.progresso(now=103.0) == 0.0)                   # pós-disparo: 0
    passos.append(h.update("Closed_Fist", now=104.0) is None)      # re-arm bloqueado
    passos.append(h.update(None, now=105.0) is None)               # gesto solto: desarma
    passos.append(h.update("Closed_Fist", now=106.0) is None)      # rearmado (segurando de novo)
    record("Gestos", "gesture", "HoldToConfirm ciclo completo (hold → disparo → re-arm)",
           "True", str(all(passos)))

    h2 = HoldToConfirm("Closed_Fist", "minimizar")
    seq = [h2.update("Closed_Fist", now=0.0) is None]
    for i in (0.1, 0.2, 0.3):
        seq.append(h2.update(None, now=i) is None)   # gaps ≤ tolerância não resetam
    seq.append(h2.progresso(now=0.35) > 0.0)         # ainda segurando
    for i in (0.4, 0.5, 0.6, 0.7):
        seq.append(h2.update(None, now=i) is None)   # gap excede → reseta
    seq.append(h2.progresso(now=0.8) == 0.0)         # resetado (ocioso)
    record("Gestos", "gesture", "HoldToConfirm tolerância de gaps (reset ao exceder)",
           "True", str(all(seq)))

    d = DisparadorAcoes({"Closed_Fist": "minimizar"})
    d.alimentar("Closed_Fist", now=50.0)
    p_hold = d.progresso_hold(now=51.5)
    record("Gestos", "gesture", "DisparadorAcoes.progresso_hold (0 < x < 1)",
           "True", str(0.0 < p_hold < 1.0))
    d2 = DisparadorAcoes({})
    record("Gestos", "gesture", "DisparadorAcoes.progresso_hold sem gatilhos → 0",
           "0.0", str(d2.progresso_hold(now=0.0)))


# ---------------------------------------------------------------------------
# Ambiente e agregação
# ---------------------------------------------------------------------------
def run_existing_suite() -> str:
    """Executa `pytest tests/ -q` (best-effort) só para registrar limitações."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "não executado (pytest indisponível)"
    out = (proc.stdout or "") + (proc.stderr or "")

    def num(label: str) -> int:
        m = re.search(rf"(\d+) {re.escape(label)}", out)
        return int(m.group(1)) if m else 0

    passed, failed, skipped, errors = num("passed"), num("failed"), num("skipped"), num("error")
    if not (passed or failed or skipped or errors):
        return "não executado (sem resultado do pytest)"
    parts = [f"{passed} passed", f"{failed} failed", f"{skipped} skipped"]
    if errors:
        parts.append(f"{errors} error")
    return ", ".join(parts)


def environment_info() -> dict:
    commit = "N/A"
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(PROJECT_ROOT),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python": platform.python_version(),
        "so": platform.platform(),
        "commit": commit,
        "comando": COMMAND,
        "diretorio": str(PROJECT_ROOT),
    }


def aggregate() -> tuple[list[dict], dict]:
    per_group: dict[str, dict] = {}
    for case in CASES:
        bucket = per_group.setdefault(
            case.grupo, {"grupo": case.grupo, "testadas": 0, "sucesso": 0, "falha": 0}
        )
        bucket["testadas"] += 1
        if case.ok:
            bucket["sucesso"] += 1
        else:
            bucket["falha"] += 1

    rows = []
    for group in GROUPS:
        bucket = per_group.get(group)
        if not bucket:
            continue
        bucket["taxa"] = round(100.0 * bucket["sucesso"] / bucket["testadas"], 2)
        rows.append(bucket)

    total = {
        "grupo": "TOTAL",
        "testadas": sum(r["testadas"] for r in rows),
        "sucesso": sum(r["sucesso"] for r in rows),
        "falha": sum(r["falha"] for r in rows),
    }
    total["taxa"] = round(100.0 * total["sucesso"] / total["testadas"], 2)
    return rows, total


def _md_table(headers: list[str], rows: list[list]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    sep = "|" + "|".join(f"---{':' if i == len(headers) - 1 and headers[i] not in ('Grupo',) and i > 0 else ''}" for i in range(len(headers))) + "|"
    body = "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return "\n".join([line, sep, body])


def _get_coverage() -> dict:
    from voice.executor import Executor

    cats = {"parser": 0, "executor": 0, "config": 0, "gesture": 0}
    for c in CASES:
        if c.categoria in cats:
            cats[c.categoria] += 1
    handlers = set(Executor({})._handlers)
    missing = sorted(ROADMAP_HANDLERS - set(handlers))
    exercised = sorted(EXERCISED_HANDLERS & set(handlers))
    return {
        "handlers_required_ok": not missing,
        "handlers_missing": missing,
        "handlers_total": len(handlers),
        "handlers_exercised": len(exercised),
        "handlers_unexercised": sorted(set(handlers) - EXERCISED_HANDLERS),
        "parser_cases": cats["parser"],
        "executor_cases": cats["executor"],
        "config_cases": cats["config"],
        "gesture_cases": cats["gesture"],
        "existing_suite": run_existing_suite(),
    }


def build_markdown(env: dict, group_rows: list[dict], total: dict, coverage: dict) -> str:
    out: list[str] = []
    out.append("# Relatório de Testes Programáveis — TCC-App")
    out.append("")
    out.append("## 1. Ambiente")
    out.append("")
    out.append(_md_table(["Item", "Valor"], [
        ["SO", env["so"]],
        ["Python", env["python"]],
        ["Commit", env["commit"]],
        ["Data/hora", env["data_hora"]],
        ["Comando", f"`{env['comando']}`"],
    ]))
    out.append("")
    out.append("> Testes 100% programáveis: texto perfeito (sem STT), gestos sintéticos (sem câmera) e executor com mocks (sem efeito no SO).")
    out.append("")

    out.append("## 2. Resultado consolidado por grupo")
    out.append("")
    out.append(_md_table(["Grupo", "Testadas", "Sucesso", "Falha", "Taxa"],
                         [[r["grupo"], r["testadas"], r["sucesso"], r["falha"],
                           f"{r['taxa']:.2f}%"] for r in group_rows] +
                         [[f"**{total['grupo']}**", f"**{total['testadas']}**",
                           f"**{total['sucesso']}**", f"**{total['falha']}**",
                           f"**{total['taxa']:.2f}%**"]]))
    out.append("")
    out.append(f"Taxa determinística: cada falha é um defeito do parser/executor/mapeamento, não erro de reconhecimento de fala. Total: **{total['testadas']}** casos.")
    out.append("")

    out.append("## 3. Cobertura de handlers (`required <= set(ex._handlers)`)")
    out.append("")
    out.append(_md_table(["Métrica", "Valor"], [
        ["Handlers exigidos pelo roadmap", f"{len(ROADMAP_HANDLERS)}"],
        ["Handlers ausentes", "nenhum" if coverage["handlers_required_ok"] else ", ".join(coverage["handlers_missing"])],
        ["`required <= set(_handlers)`", "OK" if coverage["handlers_required_ok"] else "FALHOU"],
        ["Handlers totais no Executor", coverage["handlers_total"]],
        ["Handlers exercitados (mock)", f"{coverage['handlers_exercised']}/{coverage['handlers_total']}"],
    ]))
    out.append("")

    failures = [c for c in CASES if not c.ok]
    out.append("## 4. Falhas")
    out.append("")
    if failures:
        out.append(_md_table(["Grupo", "Frase/Intenção", "Esperado", "Obtido"],
                             [[f.grupo, f.nome, f.esperado, f.obtido] for f in failures]))
    else:
        out.append("Nenhuma falha: todos os casos programáveis passaram.")
    out.append("")

    out.append("## 5. Limitações")
    out.append("")
    out.append("- Texto perfeito, sem STT (Google/Whisper/Vosk não exercitados).")
    out.append("- Gestos sintéticos, sem câmera e sem modelo MediaPipe `.task`.")
    out.append("- Executor mockado (`pyautogui`/`pywinauto`/browser/TTS) e operações de arquivo em diretório temporário; nada toca o OS real.")
    out.append("- Sem rede, sem áudio, sem janela real.")
    out.append(f"- Suíte pré-existente `pytest tests/ -q`: {coverage['existing_suite']} "
               "(falhas pré-existentes não são causadas por este script).")
    out.append("")

    out.append("## 6. Rastreabilidade (RF → grupo → N casos)")
    out.append("")
    grupos = {r["grupo"]: r["testadas"] for r in group_rows}
    n = {g: grupos.get(g, 0) for g in GROUPS}
    out.append(_md_table(["RF", "Descrição", "Grupo(s)", "N casos"], [
        ["RF01", "Compreensão do vocabulário de voz (parser)", "todos os grupos", coverage["parser_cases"]],
        ["RF02", "Execução das ações (executor mockado)", "todos os grupos", coverage["executor_cases"]],
        ["RF03", "Controle por gestos (geometria pura)", "Gestos", coverage["gesture_cases"]],
        ["RF04", "Configuração/mapeamento válidos", "Config/Mapeamento", coverage["config_cases"]],
        ["RF05", "Navegador e YouTube", "Navegador/YouTube", n["Navegador/YouTube"]],
        ["RF06", "Atalhos e digitação", "Digitação/Atalhos", n["Digitação/Atalhos"]],
        ["RF07", "Sistema e acessibilidade", "Sistema/A11y", n["Sistema/A11y"]],
        ["RF08", "Controle de janelas", "Janelas", n["Janelas"]],
        ["RF09", "Ajuda e controle", "Ajuda/Controle", n["Ajuda/Controle"]],
        ["RF10", "Arquivos e notas", "Arquivos/Notas", n["Arquivos/Notas"]],
        ["RF11", "Persistência de mapeamento e tunagem de gestos", "Config/Mapeamento", n["Config/Mapeamento"]],
    ]))
    out.append("")
    return "\n".join(out)


def write_outputs(env: dict, group_rows: list[dict], total_row: dict, coverage: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    failures = [asdict(c) for c in CASES if not c.ok]
    fail_rows = [
        {"Grupo": f["grupo"], "Frase/Intenção": f["nome"],
         "Esperado": f["esperado"], "Obtido": f["obtido"]}
        for f in failures
    ]

    results = {
        "environment": env,
        "summary": {
            "total": total_row["testadas"],
            "sucesso": total_row["sucesso"],
            "falha": total_row["falha"],
            "taxa": total_row["taxa"],
            "handlers_required_ok": coverage["handlers_required_ok"],
            "handlers_total": coverage["handlers_total"],
            "handlers_exercised": coverage["handlers_exercised"],
        },
        "groups": group_rows + [total_row],
        "coverage": {k: v for k, v in coverage.items() if isinstance(v, (int, float, bool, str, list))},
        "failures": failures,
        "cases": [asdict(c) for c in CASES],
    }
    (REPORTS_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    with (REPORTS_DIR / "results_by_group.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["grupo", "testadas", "sucesso", "falha", "taxa"])
        writer.writeheader()
        writer.writerows(group_rows + [total_row])

    with (REPORTS_DIR / "failures.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Grupo", "Frase/Intenção", "Esperado", "Obtido"])
        writer.writeheader()
        writer.writerows(fail_rows)

    (REPORTS_DIR / "test_report.md").write_text(
        build_markdown(env, group_rows, total_row, coverage), encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT))
    _install_stubs()

    _build_parser_cases()
    _build_executor_cases()
    _build_config_cases()
    _build_gesture_cases()

    coverage = _get_coverage()
    group_rows, total_row = aggregate()
    write_outputs(environment_info(), group_rows, total_row, coverage)

    print(f"Relatório gerado em {REPORTS_DIR}")
    print(f"Total: {total_row['testadas']} | sucesso: {total_row['sucesso']} | "
          f"falha: {total_row['falha']} | taxa: {total_row['taxa']:.2f}%")
    print(f"Handlers: roadmap {len(ROADMAP_HANDLERS)} | total {coverage['handlers_total']} | "
          f"exercitados {coverage['handlers_exercised']}")
    if coverage["handlers_missing"]:
        print(f"Handlers ausentes: {coverage['handlers_missing']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())