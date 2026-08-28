"""Testes extras do parser: regressões e cobertura do roadmap."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.intent_parser import IntentParser


def test_voltar_not_colar():
    parser = IntentParser()
    intent = parser.parse("voltar")
    assert intent is not None
    assert intent.name == "browser_back"


def test_colar_still_works():
    parser = IntentParser()
    intent = parser.parse("colar")
    assert intent.name == "hotkey"
    assert intent.params["keys"] == ["ctrl", "v"]


def test_nova_aba_not_abrir():
    parser = IntentParser()
    intent = parser.parse("nova aba")
    assert intent.name == "browser_new_tab"


def test_pesquisar_alone_not_query_r():
    """Regressão: 'pesquisar' continha 'pesquisa' e virava query 'r' → CAPTCHA Bing."""
    parser = IntentParser()
    assert parser.parse("pesquisar") is None
    assert parser.parse("pesquisa") is None
    intent = parser.parse("pesquisar tutorial python")
    assert intent is not None
    assert intent.name == "browser_search"
    assert intent.params["query"] == "tutorial python"


def test_salvar_dialog_vs_hotkey():
    parser = IntentParser()
    assert parser.parse("salvar", dialog_mode=True).name == "dialog_choice"
    assert parser.parse("salvar").name == "hotkey"


def test_lock_confirm_flow():
    parser = IntentParser()
    assert parser.parse("bloquear pc").params["confirmed"] is False
    assert parser.parse("bloquear o computador").name == "lock_pc"
    assert parser.parse("bloquear windows").name == "lock_pc"
    assert parser.parse_lock_confirm("confirmar").params["confirmed"] is True
    assert parser.parse_lock_confirm("cancelar").name == "cancel"


def test_cooldown_exempt_in_config():
    cfg = IntentParser().config
    exempt = set(cfg.get("cooldown_exempt", []))
    assert "hotkey" in exempt
    assert "press_key" in exempt
    assert cfg["cooldown_seconds"] <= 1.0


def test_performance_audio_defaults():
    audio = IntentParser().config["audio"]
    assert audio["pause_threshold"] <= 1.0
    assert audio["pause_threshold"] >= 0.6
    browser = IntentParser().config["browser"]
    assert browser["scroll_steps"] == 1


def test_apps_extras():
    parser = IntentParser()
    assert parser.parse("abrir paint").params["app"] == "mspaint"
    assert parser.parse("abrir prompt").params["app"] == "cmd"
    assert parser.parse("abrir explorador").params["app"] == "explorer"


def test_press_arrow_keys():
    parser = IntentParser()
    assert parser.parse("seta baixo").params["key"] == "down"
    assert parser.parse("seta cima").params["key"] == "up"


def test_apagar():
    parser = IntentParser()
    intent = parser.parse("apagar")
    assert intent is not None
    assert intent.name == "press_key"
    assert intent.params["key"] == "delete"


def test_selecione_tudo():
    parser = IntentParser()
    for phrase in (
        "selecionar tudo",
        "selecione tudo",
        "seleciona tudo",
        "selecionar o texto",
        "control a",
        "marcar tudo",
    ):
        intent = parser.parse(phrase)
        assert intent is not None, phrase
        assert intent.name == "hotkey", phrase
        assert intent.params["keys"] == ["ctrl", "a"], phrase


def test_selecionar_alone_still_ignored():
    parser = IntentParser()
    assert parser.parse("selecionar") is None
    assert parser.parse("selecione") is None

def test_click_first_without_link():
    parser = IntentParser()
    intent = parser.parse("clique no primeiro")
    assert intent.name == "browser_click_link"
    assert intent.params["index"] == 0


def test_help_phrases():
    parser = IntentParser()
    for phrase in ("ajuda", "o que posso falar", "comandos"):
        assert parser.parse(phrase).name == "help", phrase


def test_soft_correct_holly_scroll():
    """STT costuma ouvir 'Holly' no lugar de 'role'."""
    parser = IntentParser()
    intent = parser.parse("Holly para baixo")
    assert intent is not None
    assert intent.name == "browser_scroll"
    assert intent.params["direction"] == "down"


def test_soft_correct_nova_aba_near_miss():
    parser = IntentParser()
    # score alto com "nova aba"
    intent = parser.parse("nova aba")
    assert intent.name == "browser_new_tab"


def test_fuzzy_multiword_phrase_map():
    parser = IntentParser()
    # leve distorção ainda casa com hotkey multi-palavra
    intent = parser.parse("selecionar tudu")
    assert intent is not None
    assert intent.name == "hotkey"
    assert intent.params["keys"] == ["ctrl", "a"]


if __name__ == "__main__":
    test_voltar_not_colar()
    test_colar_still_works()
    test_nova_aba_not_abrir()
    test_salvar_dialog_vs_hotkey()
    test_lock_confirm_flow()
    test_cooldown_exempt_in_config()
    test_performance_audio_defaults()
    test_apps_extras()
    test_press_arrow_keys()
    test_apagar()
    test_selecione_tudo()
    test_selecionar_alone_still_ignored()
    test_click_first_without_link()
    test_help_phrases()
    test_soft_correct_holly_scroll()
    test_soft_correct_nova_aba_near_miss()
    test_fuzzy_multiword_phrase_map()
    print("Todos os testes passaram.")
