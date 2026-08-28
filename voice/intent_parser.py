import re
from pathlib import Path

import yaml
from rapidfuzz import fuzz
from unidecode import unidecode

from voice.models import Intent
from voice.paths import DEFAULT_CONFIG


class IntentParser:
    def __init__(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path) if config_path else DEFAULT_CONFIG
        with path.open(encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.wake_word = self.config.get("wake_word", "assistente")
        self.wake_word_required = self.config.get("wake_word_required", False)
        self.fuzzy_threshold = self.config.get("fuzzy_threshold", 70)
        self.verb_fuzzy_threshold = self.config.get("verb_fuzzy_threshold", 70)
        stt_cfg = self.config.get("stt", {})
        self.soft_correct_threshold = int(
            stt_cfg.get(
                "soft_correct_threshold",
                self.config.get("soft_correct_threshold", 80),
            )
        )
        self.verbs = self.config.get("verbs", [])
        self.verb_aliases: dict[str, str] = self.config.get("verb_aliases", {})
        self.type_prefixes = self.config.get(
            "type_prefixes", ["digitar", "digite", "escrever", "escreva"]
        )
        self.close_verbs = self.config.get("close_verbs", ["fechar", "fecha", "encerrar"])
        self.close_verb_aliases: dict[str, str] = self.config.get(
            "close_verb_aliases", {}
        )
        self.apps: dict[str, str] = self.config.get("apps", {})
        self.urls: dict[str, str] = self.config.get("urls", {})
        self.dialog_choices: dict[str, list[str]] = self.config.get(
            "dialog_choices",
            {
                "save": ["salvar", "save", "sim"],
                "discard": ["nao salvar", "não salvar", "nao", "descartar"],
                "cancel": ["cancelar", "cancel"],
            },
        )
        self.search_prefixes = self.config.get(
            "search_prefixes",
            ["pesquisar", "pesquisa", "buscar", "busca", "procurar"],
        )
        self.click_verbs = self.config.get(
            "click_verbs", ["clique", "clica", "clicar"]
        )
        self.back_verbs = self.config.get(
            "back_verbs", ["voltar", "volte", "retornar", "retorne"]
        )
        self.forward_verbs = self.config.get(
            "forward_verbs", ["avancar", "avance", "frente"]
        )
        self.refresh_phrases = self.config.get("refresh_phrases", [])
        self.new_tab_phrases = self.config.get("new_tab_phrases", [])
        self.close_tab_phrases = self.config.get("close_tab_phrases", [])
        self.zoom_in_phrases = self.config.get("zoom_in_phrases", [])
        self.zoom_out_phrases = self.config.get("zoom_out_phrases", [])
        self.scroll_verbs = self.config.get(
            "scroll_verbs", ["role", "rola", "rolar", "scroll"]
        )
        self.scroll_down = self.config.get(
            "scroll_down", ["baixo", "desce", "descer"]
        )
        self.scroll_up = self.config.get(
            "scroll_up", ["cima", "sobe", "subir"]
        )
        self.hotkeys: dict[str, list] = self.config.get("hotkeys", {})
        self.press_keys: dict[str, str] = self.config.get("press_keys", {})
        self.window_actions: dict[str, str] = self.config.get("window_actions", {})
        self.switch_window: dict[str, str] = self.config.get("switch_window", {})
        self.focus_prefixes = self.config.get(
            "focus_prefixes", ["focar", "foca", "foque", "foco em", "focar em"]
        )
        self.help_phrases = self.config.get("help_phrases", [])
        self.repeat_phrases = self.config.get("repeat_phrases", [])
        self.cancel_phrases = self.config.get("cancel_phrases", [])
        self.volume_map: dict[str, str] = self.config.get("volume", {})
        self.a11y_apps: dict[str, str] = self.config.get("a11y_apps", {})
        self.show_desktop_phrases = self.config.get("show_desktop_phrases", [])
        self.lock_phrases = self.config.get("lock_phrases", [])
        self.lock_confirm_phrases = self.config.get("lock_confirm_phrases", [])
        self.run_prefixes = self.config.get(
            "run_prefixes", ["executar", "rode", "rodar"]
        )
        self.folders: dict[str, str] = self.config.get("folders", {})
        self.folder_prefixes = self.config.get(
            "folder_prefixes", ["abrir pasta", "abre pasta"]
        )
        self.windows_search_prefixes = self.config.get(
            "windows_search_prefixes",
            ["pesquisar no windows", "buscar no windows"],
        )
        self.goto_prefixes = self.config.get(
            "goto_prefixes",
            ["ir para", "vai para", "abrir endereco", "barra de endereco"],
        )
        self.find_page_prefixes = self.config.get(
            "find_page_prefixes",
            ["encontrar na pagina", "buscar na pagina", "achar na pagina"],
        )
        self.tab_switch: dict[str, str] = self.config.get("tab_switch", {})
        self.youtube_actions: dict[str, str] = self.config.get(
            "youtube_actions", {}
        )
        self.youtube_short_actions: dict[str, str] = self.config.get(
            "youtube_short_actions", {}
        )
        self.link_ordinals = {
            "primeiro": 0,
            "primeira": 0,
            "1": 0,
            "um": 0,
            "segundo": 1,
            "segunda": 1,
            "2": 1,
            "dois": 1,
            "terceiro": 2,
            "terceira": 2,
            "3": 2,
            "tres": 2,
        }
        browser_config = self.config.get("browser", {})
        self.browser_default_url = browser_config.get(
            "default_url", "https://www.bing.com"
        )
        self.app_close = self.config.get("app_close", {})
        self._known_phrases = self._build_known_phrases()

    def normalize(self, text: str) -> str:
        text = unidecode(text.lower().strip())
        # Mantém '.' e '-' (URLs: github.com); remove o resto da pontuação.
        text = re.sub(r"[^\w\s.\-]", " ", text)
        text = re.sub(r"\s+ponto\s+", ".", text)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_command(self, normalized: str) -> str | None:
        if not normalized:
            return None

        if self.wake_word in normalized:
            idx = normalized.find(self.wake_word)
            return normalized[idx + len(self.wake_word) :].strip()

        words = normalized.split()
        if words and fuzz.ratio(words[0], self.wake_word) >= self.verb_fuzzy_threshold:
            remainder = " ".join(words[1:]).strip()
            return remainder or None

        if not self.wake_word_required:
            return normalized

        return None

    def _apply_verb_aliases(self, text: str) -> str:
        words = text.split()
        normalized_words = []
        for i, word in enumerate(words):
            if word in self.verb_aliases:
                normalized_words.append(self.verb_aliases[word])
                continue
            # Fuzzy só na 1ª palavra (verbo); evita "aba"→"abrir".
            if i > 0 or len(word) < 4:
                normalized_words.append(word)
                continue
            best_verb = None
            best_score = 0
            for alias, canonical in self.verb_aliases.items():
                score = fuzz.ratio(word, alias)
                if score > best_score:
                    best_score = score
                    best_verb = canonical
            if best_verb and best_score >= self.verb_fuzzy_threshold:
                normalized_words.append(best_verb)
            else:
                normalized_words.append(word)
        return " ".join(normalized_words)

    def _has_verb(self, text: str, verbs: list[str] | None = None) -> bool:
        verb_list = verbs or self.verbs
        if any(verb in text for verb in verb_list):
            return True

        aliases = self.verb_aliases if verbs is None else self.close_verb_aliases
        words = text.split()
        for word in words:
            for verb in verb_list:
                canonical = verb.split()[0]
                if fuzz.ratio(word, canonical) >= self.verb_fuzzy_threshold:
                    return True
            if word in aliases:
                return True
        return False

    def _has_close_verb(self, text: str) -> bool:
        normalized = text
        for alias, canonical in self.close_verb_aliases.items():
            normalized = normalized.replace(alias, canonical)
        return self._has_verb(normalized, self.close_verbs)

    def _score_app_alias(self, alias: str, text: str) -> float:
        return max(
            fuzz.partial_ratio(alias, text),
            fuzz.token_set_ratio(alias, text),
        )

    def _match_app(self, text: str, require_close: bool = False) -> str | None:
        if require_close:
            if not self._has_close_verb(text):
                return None
        elif not self._has_verb(text):
            return None

        best_alias = None
        best_score = 0

        for alias in self.apps:
            if alias == "browser" and require_close:
                continue
            score = self._score_app_alias(alias, text)
            alias_words = alias.split()
            if alias_words and alias_words[0] in text.split():
                score = max(score, 85.0)

            if score > best_score:
                best_score = score
                best_alias = alias

        if best_alias and best_score >= self.fuzzy_threshold:
            return self.apps[best_alias]
        return None

    def _match_close_app(self, text: str) -> str | None:
        return self._match_app(text, require_close=True)

    def _match_url(self, text: str) -> str | None:
        if not self._has_verb(text):
            return None

        for alias, url in self.urls.items():
            if alias in text or fuzz.partial_ratio(alias, text) >= self.fuzzy_threshold:
                return url

        site_match = re.search(r"(?:site|para)\s+([\w\s]+)", text)
        if site_match:
            domain = site_match.group(1).strip().replace(" ", ".")
            if "." not in domain:
                domain = f"{domain}.com"
            return f"https://www.{domain}"

        return None

    def _match_type(self, text: str) -> str | None:
        for prefix in sorted(self.type_prefixes, key=len, reverse=True):
            if prefix in text:
                idx = text.find(prefix) + len(prefix)
                content = text[idx:].strip()
                if content:
                    return content
        return None

    def _match_browser_search(self, text: str) -> str | None:
        # Prefixo como palavra inteira; "pesquisar" sozinho não vira query "r"
        # (substring "pesquisa" + sobra). Sem query → None, sem cair em prefixo menor.
        for prefix in sorted(self.search_prefixes, key=len, reverse=True):
            m = re.search(rf"(?:^|\s){re.escape(prefix)}(?:\s+|$)", text)
            if not m:
                continue
            query = text[m.end() :].strip()
            return query or None
        return None

    def _match_browser_back(self, text: str) -> bool:
        words = text.split()
        for verb in self.back_verbs:
            if verb == text or verb in words:
                return True
        if len(words) == 1:
            word = words[0]
            for verb in self.back_verbs:
                if fuzz.ratio(word, verb) >= self.verb_fuzzy_threshold:
                    return True
        return False

    def _match_browser_forward(self, text: str) -> bool:
        words = text.split()
        for verb in self.forward_verbs:
            if verb == text or verb in words:
                return True
        if len(words) == 1:
            for verb in self.forward_verbs:
                if fuzz.ratio(words[0], verb) >= self.verb_fuzzy_threshold:
                    return True
        return False

    def _has_scroll_verb(self, text: str) -> bool:
        words = text.split()
        for verb in self.scroll_verbs:
            if verb in words:
                return True
            for word in words:
                if fuzz.ratio(word, verb) >= self.verb_fuzzy_threshold:
                    return True
        return False

    def _match_browser_scroll(self, text: str) -> str | None:
        if not self._has_scroll_verb(text):
            return None
        words = text.split()
        for token in self.scroll_down:
            if token in words:
                return "down"
        for token in self.scroll_up:
            if token in words:
                return "up"
        return None

    def _match_browser_click(self, text: str) -> int | None:
        if not any(verb in text for verb in self.click_verbs):
            words = text.split()
            has_click_verb = False
            for word in words:
                for verb in self.click_verbs:
                    if fuzz.ratio(word, verb) >= self.verb_fuzzy_threshold:
                        has_click_verb = True
                        break
                if has_click_verb:
                    break
            if not has_click_verb:
                return None

        ordinals = (
            r"primeiro|primeira|segundo|segunda|terceiro|terceira|"
            r"um|dois|tres|\d+"
        )
        match = re.search(
            rf"(?:no|na|em)\s+({ordinals})(?:\s+(?:link|video|resultado))?(?:\s|$)",
            text,
        )
        if not match:
            match = re.search(rf"({ordinals})\s+(?:link|video)", text)
        if not match:
            return None

        ordinal = match.group(1)
        if ordinal in self.link_ordinals:
            return self.link_ordinals[ordinal]

        try:
            return max(int(ordinal) - 1, 0)
        except ValueError:
            return None

    def _match_browser_click_text(self, text: str) -> str | None:
        if not any(verb in text for verb in self.click_verbs):
            return None
        # "clicar em X" ou "clicar X" (STT costuma omitir a preposição)
        match = re.search(
            r"(?:clique|clica|clicar)\s+(?:(?:no|na|em)\s+)?(.+)$",
            text,
        )
        if not match:
            return None
        target = match.group(1).strip()
        target = re.sub(r"\s+link$", "", target).strip()
        first = target.split()[0] if target else ""
        # Ordinal / role ficam para outros matchers.
        if first in self.link_ordinals or first.isdigit():
            return None
        if first in ("botao", "campo", "caixa", "input"):
            return None
        return target or None

    # Artigos/preposições: "bloquear o computador" ≈ "bloquear computador".
    _FILLERS = frozenset(
        {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "no", "na", "nos", "nas"}
    )

    @classmethod
    def _without_fillers(cls, text: str) -> str:
        return " ".join(w for w in text.split() if w not in cls._FILLERS)

    def _build_known_phrases(self) -> list[str]:
        """Frases canônicas para soft-correct de erros de STT."""
        raw: set[str] = set()
        for mapping in (
            self.hotkeys,
            self.press_keys,
            self.window_actions,
            self.switch_window,
            self.volume_map,
            self.tab_switch,
            self.youtube_actions,
            self.youtube_short_actions,
        ):
            raw.update(str(k) for k in mapping)
        for lst in (
            self.help_phrases,
            self.repeat_phrases,
            self.cancel_phrases,
            self.show_desktop_phrases,
            self.lock_phrases,
            self.refresh_phrases,
            self.new_tab_phrases,
            self.close_tab_phrases,
            self.zoom_in_phrases,
            self.zoom_out_phrases,
        ):
            raw.update(str(p) for p in lst)
        for verb in self.scroll_verbs:
            for direction in (*self.scroll_down, *self.scroll_up):
                raw.add(f"{verb} para {direction}")
                raw.add(f"{verb} {direction}")
        normalized = {self.normalize(p) for p in raw if p and str(p).strip()}
        return sorted((p for p in normalized if p), key=len, reverse=True)

    @staticmethod
    def _similar_token_len(a: str, b: str, max_delta: int = 1) -> bool:
        return abs(len(a.split()) - len(b.split())) <= max_delta

    def _soft_correct(self, command: str) -> str:
        """Corrige utterance perto de frase conhecida (ex.: holly→role para baixo)."""
        if not command or not self._known_phrases:
            return command
        if command in self._known_phrases:
            return command

        best_phrase = None
        best_score = 0.0
        for phrase in self._known_phrases:
            # Mesmo nº de tokens — evita "voltar"→"voltar aba".
            if not self._similar_token_len(command, phrase, max_delta=0):
                continue
            # ratio (não token_set): "abrir X" não cola em qualquer "abrir Y".
            score = float(fuzz.ratio(command, phrase))
            if score > best_score:
                best_score = score
                best_phrase = phrase
        if best_phrase and best_score >= self.soft_correct_threshold:
            return best_phrase

        # Verbo de scroll misturado pelo STT: "holly para baixo"
        m = re.match(
            r"^(\S+)\s+((?:para\s+)?(?:baixo|cima|desce|descer|sobe|subir))\b(.*)$",
            command,
        )
        if m:
            verb, direction, tail = m.group(1), m.group(2), m.group(3)
            best_verb = None
            best_v = 0.0
            for candidate in self.scroll_verbs:
                score = float(fuzz.ratio(verb, candidate))
                if score > best_v:
                    best_v = score
                    best_verb = candidate
            if best_verb and best_v >= self.verb_fuzzy_threshold:
                return f"{best_verb} {direction}{tail}".strip()

        return command

    def _phrase_matches(self, phrase: str, normalized: str) -> bool:
        if phrase == normalized:
            return True
        if " " in phrase:
            if phrase in normalized:
                return True
            collapsed_phrase = self._without_fillers(phrase)
            collapsed_text = self._without_fillers(normalized)
            if collapsed_phrase and (
                collapsed_phrase == collapsed_text
                or collapsed_phrase in collapsed_text
            ):
                return True
            # Fuzzy com ratio + mesmo nº de tokens (token_set fazia "abrir aba"≈"abrir paint").
            # ≥85: evita "marcar tudo"≈"para tudo" (cancel).
            phrase_thresh = max(self.fuzzy_threshold, 85)
            if self._similar_token_len(phrase, normalized, max_delta=0) and (
                fuzz.ratio(phrase, normalized) >= phrase_thresh
            ):
                return True
            if (
                collapsed_phrase
                and collapsed_text
                and self._similar_token_len(
                    collapsed_phrase, collapsed_text, max_delta=0
                )
                and fuzz.ratio(collapsed_phrase, collapsed_text) >= phrase_thresh
            ):
                return True
            return False
        words = normalized.split()
        # Frase de uma palavra: só match exato na utterance inteira (evita voltar≈colar).
        if len(words) == 1:
            return fuzz.ratio(words[0], phrase) >= 90
        return False

    def _match_phrase_map(self, text: str, mapping: dict) -> object | None:
        for phrase, value in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
            if self._phrase_matches(phrase, text):
                return value
        return None

    def _match_phrase_list(self, text: str, phrases: list[str]) -> bool:
        for phrase in sorted(phrases, key=len, reverse=True):
            if self._phrase_matches(phrase, text):
                return True
        return False

    def _match_window_action(self, text: str) -> Intent | None:
        for phrase, action in sorted(
            self.window_actions.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if text == phrase:
                return Intent("window_action", {"action": action})
            if text.startswith(phrase + " "):
                remainder = text[len(phrase) :].strip()
                params: dict = {"action": action}
                if remainder:
                    app = self._match_app_name_only(remainder)
                    if app:
                        params["app"] = app
                        params["titles"] = (
                            self.app_close.get(app) or {}
                        ).get("titles", [app])
                return Intent("window_action", params)
            # fuzzy só se a utterance for uma palavra (ex.: "minimiza")
            if " " not in text and " " not in phrase:
                if fuzz.ratio(text, phrase) >= 90:
                    return Intent("window_action", {"action": action})
        return None

    def _match_focus_app(self, text: str) -> str | None:
        for prefix in sorted(self.focus_prefixes, key=len, reverse=True):
            if prefix in text:
                remainder = text[text.find(prefix) + len(prefix) :].strip()
                if not remainder:
                    return None
                return self._match_app_name_only(remainder)
        return None

    def _match_app_name_only(self, text: str) -> str | None:
        best_alias = None
        best_score = 0
        for alias in self.apps:
            score = self._score_app_alias(alias, text)
            if score > best_score:
                best_score = score
                best_alias = alias
        if best_alias and best_score >= self.fuzzy_threshold:
            return self.apps[best_alias]
        return None

    def _match_a11y(self, text: str) -> str | None:
        if not self._has_verb(text) and "abrir" not in text:
            # allow "abrir lupa"
            if not any(name in text for name in self.a11y_apps):
                return None
        for alias, app in self.a11y_apps.items():
            if alias in text:
                return app
        return None

    def _match_run(self, text: str) -> str | None:
        for prefix in sorted(self.run_prefixes, key=len, reverse=True):
            if text.startswith(prefix + " ") or text.startswith(prefix):
                cmd = text[len(prefix) :].strip()
                if cmd:
                    return cmd
        return None

    def _match_prefix_remainder(
        self, text: str, prefixes: list[str]
    ) -> str | None:
        for prefix in sorted(prefixes, key=len, reverse=True):
            m = re.search(rf"(?:^|\s){re.escape(prefix)}(?:\s+|$)", text)
            if not m:
                continue
            remainder = text[m.end() :].strip()
            return remainder or None
        return None

    def _match_open_folder(self, text: str) -> str | None:
        if not self.folders:
            return None
        remainder = self._match_prefix_remainder(text, self.folder_prefixes)
        candidate = remainder
        if candidate is None:
            # "abrir downloads" / "abrir documentos" sem "pasta"
            for verb in ("abrir", "abre", "abra"):
                if text.startswith(verb + " "):
                    candidate = text[len(verb) :].strip()
                    break
        if not candidate:
            return None
        for alias, path in sorted(
            self.folders.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if candidate == alias or candidate.startswith(alias):
                return path
            if fuzz.ratio(candidate, alias) >= self.fuzzy_threshold:
                return path
        return None

    def _match_windows_search(self, text: str) -> str | None:
        return self._match_prefix_remainder(text, self.windows_search_prefixes)

    def _match_goto(self, text: str) -> str | None:
        return self._match_prefix_remainder(text, self.goto_prefixes)

    def _match_find_in_page(self, text: str) -> str | None:
        return self._match_prefix_remainder(text, self.find_page_prefixes)

    def _match_tab_by_index_or_title(self, text: str) -> Intent | None:
        # "aba 2" / "ir para aba 2" / "focar aba youtube"
        m = re.search(r"(?:^|\s)aba\s+(\d+)\b", text)
        if m:
            return Intent(
                "browser_switch_tab", {"index": max(int(m.group(1)) - 1, 0)}
            )
        m = re.search(
            r"(?:focar|foca|foque|ir para|vai para)\s+aba\s+(.+)$", text
        )
        if m:
            title = m.group(1).strip()
            if title and not title.isdigit():
                return Intent("browser_switch_tab", {"title": title})
        return None

    def _match_click_role(self, text: str) -> Intent | None:
        if not any(verb in text for verb in self.click_verbs):
            return None
        # texto já normalizado (unidecode): botão → botao
        m = re.search(
            r"(?:clique|clica|clicar)\s+(?:no|na|em)\s+"
            r"(botao|campo|caixa|input)\s+(.+)$",
            text,
        )
        if not m:
            return None
        kind = m.group(1)
        name = m.group(2).strip()
        if not name:
            return None
        role = "textbox" if kind in ("campo", "caixa", "input") else "button"
        return Intent("browser_click_role", {"role": role, "name": name})

    def parse_dialog_choice(self, text: str) -> Intent | None:
        normalized = self.normalize(text)
        if not normalized:
            return None

        priority = ["discard", "cancel", "save"]

        for choice in priority:
            phrases = self.dialog_choices.get(choice, [])
            for phrase in sorted(phrases, key=len, reverse=True):
                if self._phrase_matches(phrase, normalized):
                    return Intent("dialog_choice", {"choice": choice})

        return None

    def parse_lock_confirm(self, text: str) -> Intent | None:
        normalized = self.normalize(text)
        if not normalized:
            return None
        if self._match_phrase_list(normalized, self.lock_confirm_phrases):
            return Intent("lock_pc", {"confirmed": True})
        if self._match_phrase_list(normalized, self.cancel_phrases):
            return Intent("cancel")
        return None

    def help_summary(self) -> str:
        parts = [
            "Abrir e fechar apps",
            "digitar texto",
            "copiar colar desfazer",
            "minimizar maximizar",
            "pesquisar e clicar em links",
            "volume e area de trabalho",
            "ajuda e repetir",
        ]
        return "Comandos: " + "; ".join(parts)

    def parse(
        self,
        text: str,
        dialog_mode: bool = False,
        youtube_mode: bool = False,
    ) -> Intent | None:
        if dialog_mode:
            dialog = self.parse_dialog_choice(text)
            if dialog:
                return dialog

        normalized = self.normalize(text)
        command = self._extract_command(normalized)
        if not command:
            return None

        command = self._apply_verb_aliases(command)
        command = self._soft_correct(command)

        if self._match_phrase_list(command, self.cancel_phrases):
            return Intent("cancel")

        if self._match_phrase_list(command, self.help_phrases):
            return Intent("help")

        if self._match_phrase_list(command, self.repeat_phrases):
            return Intent("repeat_last")

        if self._match_phrase_list(command, self.lock_phrases):
            return Intent("lock_pc", {"confirmed": False})

        if self._match_phrase_list(command, self.show_desktop_phrases):
            return Intent("show_desktop")

        # No YouTube: pausar/avancar/mudo/som controlam o player, não o Windows.
        if youtube_mode:
            yt_short = self._match_phrase_map(command, self.youtube_short_actions)
            if yt_short is not None:
                return Intent("browser_youtube", {"action": yt_short})

        vol = self._match_phrase_map(command, self.volume_map)
        if vol is not None:
            return Intent("volume", {"action": vol})

        a11y = self._match_a11y(command)
        if a11y:
            return Intent("open_a11y", {"app": a11y})

        run_cmd = self._match_run(command)
        if run_cmd:
            return Intent("run_dialog", {"command": run_cmd})

        win_search = self._match_windows_search(command)
        if win_search:
            return Intent("windows_search", {"query": win_search})

        folder = self._match_open_folder(command)
        if folder:
            return Intent("open_folder", {"path": folder})

        yt = self._match_phrase_map(command, self.youtube_actions)
        if yt is not None:
            return Intent("browser_youtube", {"action": yt})

        keys = self._match_phrase_map(command, self.hotkeys)
        if keys is not None:
            return Intent("hotkey", {"keys": keys})

        key = self._match_phrase_map(command, self.press_keys)
        if key is not None:
            return Intent("press_key", {"key": key})

        win = self._match_window_action(command)
        if win:
            return win

        tab_dir = self._match_phrase_map(command, self.tab_switch)
        if tab_dir is not None:
            return Intent("browser_switch_tab", {"direction": tab_dir})

        tab_target = self._match_tab_by_index_or_title(command)
        if tab_target:
            return tab_target

        switch = self._match_phrase_map(command, self.switch_window)
        if switch is not None:
            return Intent("switch_window", {"direction": switch})

        focus_app = self._match_focus_app(command)
        if focus_app:
            titles = (self.app_close.get(focus_app) or {}).get("titles", [focus_app])
            return Intent("focus_app", {"app": focus_app, "titles": titles})

        if self._match_phrase_list(command, self.zoom_in_phrases):
            return Intent("browser_zoom", {"direction": "in"})
        if self._match_phrase_list(command, self.zoom_out_phrases):
            return Intent("browser_zoom", {"direction": "out"})

        if self._match_phrase_list(command, self.refresh_phrases):
            return Intent("browser_refresh")
        if self._match_phrase_list(command, self.new_tab_phrases):
            return Intent("browser_new_tab")
        if self._match_phrase_list(command, self.close_tab_phrases):
            return Intent("browser_close_tab")

        scroll_dir = self._match_browser_scroll(command)
        if scroll_dir:
            return Intent("browser_scroll", {"direction": scroll_dir})

        if self._match_browser_forward(command):
            return Intent("browser_forward")

        if self._match_browser_back(command):
            return Intent("browser_back")

        link_index = self._match_browser_click(command)
        if link_index is not None:
            return Intent("browser_click_link", {"index": link_index})

        click_role = self._match_click_role(command)
        if click_role:
            return click_role

        click_text = self._match_browser_click_text(command)
        if click_text:
            return Intent("browser_click_text", {"text": click_text})

        find_text = self._match_find_in_page(command)
        if find_text:
            return Intent("browser_find", {"text": find_text})

        goto = self._match_goto(command)
        if goto:
            return Intent("browser_goto", {"url": goto})

        search_query = self._match_browser_search(command)
        if search_query:
            return Intent("browser_search", {"query": search_query})

        typed = self._match_type(command)
        if typed:
            return Intent("type_text", {"text": typed})

        url = self._match_url(command)
        if url:
            return Intent("open_url", {"url": url})

        closed = self._match_close_app(command)
        if closed:
            return Intent("close_app", {"app": closed})

        app = self._match_app(command)
        if app:
            if app == "browser":
                return Intent(
                    "browser_open", {"url": self.browser_default_url}
                )
            return Intent("open_app", {"app": app})

        return None
