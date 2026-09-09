from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from rapidfuzz import fuzz
from unidecode import unidecode

from voice.logger import setup_logging
from voice.paths import PROJECT_ROOT

_YOUTUBE_KEYS = {
    "play_pause": "k",
    "forward": "l",
    "rewind": "j",
    "mute": "m",
    "fullscreen": "f",
    "volume_up": "ArrowUp",
    "volume_down": "ArrowDown",
}

# STT/unidecode → "franca"; HTML do YouTube pode ter "França".
_FLEX_CHARS = {
    "a": "[aáàãâä]",
    "e": "[eéèêë]",
    "i": "[iíìîï]",
    "o": "[oóòõôö]",
    "u": "[uúùûü]",
    "c": "[cç]",
    "n": "[nñ]",
}


def _flex_text_regex(needle: str) -> re.Pattern[str]:
    parts: list[str] = []
    for ch in needle.lower():
        parts.append(_FLEX_CHARS.get(ch, re.escape(ch)))
    return re.compile("".join(parts), re.I)

# Paths típicos no Windows (Playwright channel=chrome|msedge).
_CHANNEL_EXE = {
    "chrome": (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
    ),
    "msedge": (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
    ),
}


def _channel_installed(name: str) -> bool:
    return any(p.is_file() for p in _CHANNEL_EXE.get(name, ()))


class BrowserSession:
    """Sessão Playwright reutilizável para navegação por voz."""

    def __init__(self, config: dict | None = None) -> None:
        self.logger = setup_logging()
        browser_config = (config or {}).get("browser", {})
        self.default_url = browser_config.get(
            "default_url", "https://www.bing.com"
        )
        self.search_url = browser_config.get(
            "search_url", "https://www.bing.com/search?q={query}"
        )
        self.fallback_search_url = browser_config.get(
            "fallback_search_url", "https://duckduckgo.com/?q={query}"
        )
        self.youtube_search_url = browser_config.get(
            "youtube_search_url",
            "https://www.youtube.com/results?search_query={query}",
        )
        # auto | chrome | msedge | chromium
        self.channel = (browser_config.get("channel") or "auto").lower()
        self.cdp_url = (browser_config.get("cdp_url") or "").strip()
        user_data = (browser_config.get("user_data_dir") or "").strip()
        if user_data:
            path = Path(user_data).expanduser()
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            self.user_data_dir = str(path.resolve())
        else:
            self.user_data_dir = ""
        self.headless = browser_config.get("headless", False)
        self.scroll_amount = int(browser_config.get("scroll_amount", 600))
        self.scroll_steps = max(1, int(browser_config.get("scroll_steps", 12)))
        self.scroll_step_ms = max(0, int(browser_config.get("scroll_step_ms", 40)))
        self.click_fuzzy_threshold = int(
            browser_config.get("click_fuzzy_threshold", 75)
        )
        selectors = browser_config.get("link_selectors", {})
        self.primary_selector = selectors.get(
            "duckduckgo", "li.b_algo h2 a"
        )
        self.generic_selector = selectors.get(
            "generic", "main a[href], article a[href]"
        )
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._persistent = False
        self._attached = False
        self._active_channel = "chromium"

    @property
    def is_active(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    def _ensure_started(self) -> None:
        if self.is_active:
            return
        self.start()

    def start(self, url: str | None = None) -> None:
        if self.is_active:
            if url:
                self.navigate(url)
            return

        from app_paths import configure_playwright_browsers
        from playwright.sync_api import sync_playwright

        # Frozen builds ship Chromium under ms-playwright/ next to the exe.
        configure_playwright_browsers()
        self._playwright = sync_playwright().start()

        if self.cdp_url:
            self._attach_cdp(url)
            return

        if self.user_data_dir:
            self._start_persistent(url)
            return

        self._start_launch(url)

    def _channel_candidates(self) -> list[str | None]:
        """Lista de channels a tentar; None = Chromium do Playwright."""
        preferred = self.channel
        installed = [n for n in ("msedge", "chrome") if _channel_installed(n)]

        if preferred == "chromium":
            return [None]
        if preferred in ("chrome", "msedge"):
            ordered: list[str | None] = []
            if preferred in installed:
                ordered.append(preferred)
            else:
                self.logger.warning(
                    f"{preferred} não encontrado; tentando outro browser."
                )
            for name in installed:
                if name not in ordered:
                    ordered.append(name)
            ordered.append(None)
            return ordered

        # auto: Edge > Chrome > Chromium (neste PC Chrome costuma faltar)
        ordered = list(installed)
        ordered.append(None)
        return ordered

    def _channel_kwargs(self, channel: str | None) -> dict:
        kwargs: dict = {"headless": self.headless}
        if channel:
            kwargs["channel"] = channel
        return kwargs

    def _attach_cdp(self, url: str | None) -> None:
        assert self._playwright is not None
        self._browser = self._playwright.chromium.connect_over_cdp(self.cdp_url)
        self._attached = True
        contexts = self._browser.contexts
        self._context = contexts[0] if contexts else self._browser.new_context()
        pages = [p for p in self._context.pages if not p.is_closed()]
        self._page = pages[0] if pages else self._context.new_page()
        if url:
            self._safe_goto(self._page, url)
        self.logger.info(f"Browser anexado via CDP ({self.cdp_url}).")

    def _profile_dir(self, channel: str | None) -> Path:
        base = Path(self.user_data_dir)
        sub = channel or "chromium"
        path = base / sub
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _start_persistent(self, url: str | None) -> None:
        assert self._playwright is not None
        last_exc: Exception | None = None
        for channel in self._channel_candidates():
            label = channel or "chromium"
            try:
                self._context = self._playwright.chromium.launch_persistent_context(
                    str(self._profile_dir(channel)),
                    **self._channel_kwargs(channel),
                )
                self._active_channel = label
                break
            except Exception as exc:
                last_exc = exc
                self.logger.warning(f"Falha channel={label} persistente: {exc}")
        else:
            raise RuntimeError(
                f"Não foi possível abrir o navegador: {last_exc}"
            )

        self._persistent = True
        self._browser = getattr(self._context, "browser", None)
        pages = [p for p in self._context.pages if not p.is_closed()]
        self._page = pages[0] if pages else self._context.new_page()
        target = url or self.default_url
        self._safe_goto(self._page, target)
        self.logger.info(
            f"Browser persistente ({self._active_channel}): {target}"
        )

    def _start_launch(self, url: str | None) -> None:
        assert self._playwright is not None
        last_exc: Exception | None = None
        for channel in self._channel_candidates():
            label = channel or "chromium"
            try:
                self._browser = self._playwright.chromium.launch(
                    **self._channel_kwargs(channel)
                )
                self._active_channel = label
                break
            except Exception as exc:
                last_exc = exc
                self.logger.warning(f"Falha channel={label}: {exc}")
        else:
            raise RuntimeError(
                f"Não foi possível abrir o navegador: {last_exc}"
            )

        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        target = url or self.default_url
        self._safe_goto(self._page, target)
        self.logger.info(f"Browser aberto ({self._active_channel}): {target}")

    def _safe_goto(self, page, url: str) -> None:
        try:
            page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            # Ctrl+C / close no meio do load → TargetClosedError ruidoso
            name = type(exc).__name__
            if "TargetClosed" in name or "Interrupted" in name:
                raise KeyboardInterrupt from exc
            raise
        self._dismiss_cookie_banner()

    def _dismiss_cookie_banner(self) -> None:
        """Fecha modal de cookies Microsoft/Bing (pode atrasar / iframe / IDs)."""
        if not self._page:
            return
        if self._try_dismiss_cookie_once():
            return

        # Só espera no ecossistema Microsoft — banner atrasa após domcontentloaded.
        try:
            host = (self._page.url or "").lower()
        except Exception:
            host = ""
        if not any(h in host for h in ("bing.com", "microsoft.com", "msn.com")):
            return

        for _ in range(14):  # ~3.5s
            try:
                self._page.wait_for_timeout(250)
            except Exception:
                return
            if self._try_dismiss_cookie_once():
                return

    def _try_dismiss_cookie_once(self) -> bool:
        assert self._page is not None
        roots = [self._page]
        try:
            # frames[0] é o main; demais cobrem consent em iframe.
            roots.extend(self._page.frames[1:])
        except Exception:
            pass

        # Bing clássico (#bnp_*) + consentimento novo (Aceitar/Rejeitar).
        selectors = (
            "#bnp_btn_reject",
            "button#bnp_btn_reject",
            "#bnp_btn_accept",
            "button:has-text('Rejeitar')",
            "button:has-text('Reject')",
            "button:has-text('Aceitar')",
            "button:has-text('Accept')",
            "[aria-label='Rejeitar']",
            "[aria-label='Reject']",
            "input[type='button'][value='Rejeitar']",
            "input[type='submit'][value='Rejeitar']",
        )
        labels = ("Rejeitar", "Reject", "Aceitar", "Accept")

        for root in roots:
            for sel in selectors:
                if self._click_if_visible(root, sel):
                    self.logger.info(f"Banner de cookies: {sel}")
                    try:
                        self._page.wait_for_timeout(400)
                    except Exception:
                        pass
                    return True
            for label in labels:
                try:
                    btn = root.get_by_role(
                        "button",
                        name=re.compile(rf"^{re.escape(label)}$", re.I),
                    )
                    if btn.count() > 0 and btn.first.is_visible() is True:
                        btn.first.click(timeout=1500)
                        self.logger.info(f"Banner de cookies: {label}")
                        try:
                            self._page.wait_for_timeout(400)
                        except Exception:
                            pass
                        return True
                except Exception:
                    continue
        return False

    @staticmethod
    def _click_if_visible(root, selector: str) -> bool:
        try:
            loc = root.locator(selector)
            if loc.count() == 0:
                return False
            target = loc.first
            # `is True` evita MagicMock truthy nos testes.
            if target.is_visible() is not True:
                return False
            target.click(timeout=1500)
            return True
        except Exception:
            return False

    def navigate(self, url: str) -> None:
        self._ensure_started()
        assert self._page is not None
        self._safe_goto(self._page, url)
        self.logger.info(f"Navegou para: {url}")

    @staticmethod
    def normalize_url(raw: str) -> str:
        text = raw.strip().lower()
        text = re.sub(r"\s+ponto\s+", ".", text)
        text = text.replace(" ", "")
        if not text:
            raise ValueError("URL vazia.")
        if re.match(r"^https?://", text, re.I):
            return text
        if "." not in text:
            text = f"{text}.com"
        return f"https://{text}"

    def search(self, query: str) -> None:
        if not query.strip():
            raise ValueError("Query de pesquisa vazia.")
        self._ensure_started()
        assert self._page is not None
        encoded = quote_plus(query.strip())

        # Na aba do YouTube, pesquisa no próprio YouTube (não no Bing).
        if self._is_youtube():
            url = self.youtube_search_url.format(query=encoded)
            self._safe_goto(self._page, url)
            self.logger.info(f"Pesquisa YouTube: {query}")
            return

        url = self.search_url.format(query=encoded)
        self._safe_goto(self._page, url)
        if self._is_blocked() and self.fallback_search_url:
            fallback = self.fallback_search_url.format(query=encoded)
            self.logger.warning(
                "Busca bloqueada (CAPTCHA/desafio); fallback DuckDuckGo."
            )
            self._safe_goto(self._page, fallback)
            self.logger.info(f"Pesquisa (fallback): {query}")
            return
        self.logger.info(f"Pesquisa: {query}")

    def _is_youtube(self) -> bool:
        try:
            host = (self._page.url or "").lower()
        except Exception:
            return False
        return "youtube.com" in host or "youtu.be" in host

    @property
    def on_youtube(self) -> bool:
        return self.is_active and self._is_youtube()

    def _is_blocked(self) -> bool:
        """CAPTCHA real do Bing — não varrer HTML (scripts trazem 'challenge'/'captcha')."""
        assert self._page is not None
        try:
            if self._page.locator(self.primary_selector).count() > 0:
                return False
        except Exception:
            pass
        # Frases da UI do desafio (pt/en); palavras soltas geram falso positivo.
        phrases = (
            "uma última etapa",
            "uma ultima etapa",
            "resolva o desafio",
            "resolve o desafio",
            "are you a robot",
            "unusual traffic",
        )
        for phrase in phrases:
            try:
                loc = self._page.get_by_text(
                    re.compile(re.escape(phrase), re.I)
                )
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def go_back(self) -> None:
        self._ensure_started()
        assert self._page is not None
        assert self._context is not None

        response = self._page.go_back(wait_until="domcontentloaded")
        if response is not None:
            self.logger.info("Voltou para a página anterior.")
            return

        pages = [p for p in self._context.pages if not p.is_closed()]
        if len(pages) > 1:
            current = self._page
            current.close()
            remaining = [p for p in self._context.pages if not p.is_closed()]
            self._page = remaining[-1]
            self._page.bring_to_front()
            self.logger.info("Fechou aba e voltou para a anterior.")
            return

        raise RuntimeError("Não há página anterior no histórico.")

    def go_forward(self) -> None:
        self._ensure_started()
        assert self._page is not None
        response = self._page.go_forward(wait_until="domcontentloaded")
        if response is None:
            raise RuntimeError("Não há página seguinte no histórico.")
        self.logger.info("Avançou para a página seguinte.")

    def refresh(self) -> None:
        self._ensure_started()
        assert self._page is not None
        self._page.reload(wait_until="domcontentloaded")
        self.logger.info("Página atualizada.")

    def new_tab(self, url: str | None = None) -> None:
        self._ensure_started()
        assert self._context is not None
        self._page = self._context.new_page()
        target = url or self.default_url
        self._page.goto(target, wait_until="domcontentloaded")
        self.logger.info(f"Nova aba: {target}")

    def close_tab(self) -> None:
        self._ensure_started()
        assert self._page is not None
        assert self._context is not None
        pages = [p for p in self._context.pages if not p.is_closed()]
        if len(pages) <= 1:
            raise RuntimeError("Só há uma aba; use fechar navegador.")
        self._page.close()
        remaining = [p for p in self._context.pages if not p.is_closed()]
        self._page = remaining[-1]
        self._page.bring_to_front()
        self.logger.info("Aba fechada.")

    def switch_tab(
        self,
        direction: str | None = None,
        index: int | None = None,
        title: str | None = None,
    ) -> None:
        self._ensure_started()
        assert self._page is not None
        assert self._context is not None
        pages = [p for p in self._context.pages if not p.is_closed()]
        if not pages:
            raise RuntimeError("Nenhuma aba aberta.")

        target = None
        if title:
            needle = title.strip().lower()
            for page in pages:
                hay = f"{page.title()} {page.url}".lower()
                if needle in hay:
                    target = page
                    break
            if target is None:
                raise RuntimeError(f"Aba '{title}' não encontrada.")
        elif index is not None:
            if index < 0 or index >= len(pages):
                raise RuntimeError(
                    f"Aba {index + 1} inválida ({len(pages)} abertas)."
                )
            target = pages[index]
        elif direction in ("next", "prev"):
            try:
                cur = pages.index(self._page)
            except ValueError:
                cur = 0
            delta = 1 if direction == "next" else -1
            target = pages[(cur + delta) % len(pages)]
        else:
            raise ValueError("Informe direction, index ou title.")

        self._page = target
        self._page.bring_to_front()
        self.logger.info(f"Aba ativa: {self._page.title()}")

    def find_in_page(self, text: str) -> None:
        self._ensure_started()
        assert self._page is not None
        needle = text.strip()
        if not needle:
            raise ValueError("Texto de busca na página vazio.")
        self._page.keyboard.press("Control+f")
        self._page.keyboard.type(needle, delay=20)
        self.logger.info(f"Busca na página: {needle}")

    def click_role(self, role: str, name: str | None = None) -> None:
        self._ensure_started()
        assert self._page is not None
        role = role.strip().lower()
        if role not in ("button", "textbox", "searchbox", "checkbox", "link"):
            raise ValueError(f"Role inválida: {role}")
        if name:
            locator = self._page.get_by_role(
                role, name=re.compile(re.escape(name.strip()), re.I)
            )
        else:
            locator = self._page.get_by_role(role)
        if locator.count() == 0:
            raise RuntimeError(
                f"Nenhum {role}"
                + (f" '{name}'" if name else "")
                + " encontrado."
            )
        locator.first.click()
        self.logger.info(f"Clicou {role}: {name or '(primeiro)'}")

    def youtube(self, action: str) -> None:
        self._ensure_started()
        assert self._page is not None
        key = _YOUTUBE_KEYS.get(action)
        if not key:
            raise ValueError(f"Ação YouTube inválida: {action}")
        try:
            self._page.bring_to_front()
        except Exception:
            pass
        # Foca o player sem clicar no centro (clique no vídeo alterna play).
        try:
            self._page.evaluate(
                """() => {
                  const p = document.querySelector('#movie_player, video');
                  if (p) p.focus({ preventScroll: true });
                }"""
            )
        except Exception:
            pass
        presses = 4 if action in ("volume_up", "volume_down") else 1
        for _ in range(presses):
            self._page.keyboard.press(key)
        self.logger.info(f"YouTube: {action} ({key} x{presses})")

    def zoom(self, direction: str) -> None:
        self._ensure_started()
        assert self._page is not None
        if direction not in ("in", "out"):
            raise ValueError(f"Direção de zoom inválida: {direction}")
        self._page.keyboard.down("Control")
        try:
            self._page.keyboard.press("=" if direction == "in" else "-")
        finally:
            self._page.keyboard.up("Control")
        self.logger.info(f"Zoom {'+' if direction == 'in' else '-'}.")

    def click_text(self, text: str) -> None:
        self._ensure_started()
        assert self._page is not None
        needle = text.strip()
        if not needle:
            raise ValueError("Texto de clique vazio.")
        pattern = _flex_text_regex(needle)

        # YouTube: título do vídeo costuma estar em a#video-title (não só role=link).
        yt = self._page.locator(
            "a#video-title, a.ytd-video-renderer[href*='/watch'], "
            "a.yt-simple-endpoint[href*='/watch']"
        ).filter(has_text=pattern)
        if yt.count() > 0:
            link = yt.first
            href = link.get_attribute("href") or ""
            if href and self._is_valid_href(href):
                if href.startswith("/"):
                    href = "https://www.youtube.com" + href
                self._safe_goto(self._page, href)
            else:
                link.click()
            self.logger.info(f"Clicou em texto (youtube): {needle}")
            return

        locator = self._page.get_by_role("link", name=pattern)
        if locator.count() == 0:
            locator = self._page.get_by_text(pattern)
        if locator.count() > 0:
            target = locator.first
            href = None
            try:
                href = target.get_attribute("href")
            except Exception:
                pass
            if href and self._is_valid_href(href):
                if href.startswith("/"):
                    href = urljoin(self._page.url, href)
                self._safe_goto(self._page, href)
            else:
                target.click()
            self.logger.info(f"Clicou em texto: {needle}")
            return

        if self._semantic_click(needle):
            return
        raise RuntimeError(f"Nenhum elemento com texto '{needle}'.")

    def _semantic_click(self, needle: str) -> bool:
        """Fallback: score em links/botões visíveis (ideia browser-use, sem LLM)."""
        assert self._page is not None
        try:
            candidates = self._page.evaluate(
                """() => {
                  const sel = 'a[href], button, [role="link"], [role="button"], a#video-title';
                  const out = [];
                  for (const el of document.querySelectorAll(sel)) {
                    const r = el.getBoundingClientRect();
                    if (r.width < 2 || r.height < 2) continue;
                    const style = getComputedStyle(el);
                    if (style.visibility === 'hidden' || style.display === 'none') continue;
                    const text = (
                      el.getAttribute('aria-label')
                      || el.innerText
                      || el.title
                      || el.textContent
                      || ''
                    ).trim().replace(/\\s+/g, ' ');
                    if (!text) continue;
                    out.push({
                      text: text.slice(0, 240),
                      href: el.href || el.getAttribute('href') || '',
                    });
                    if (out.length >= 100) break;
                  }
                  return out;
                }"""
            )
        except Exception as exc:
            self.logger.warning(f"Clique semântico: enumerate falhou: {exc}")
            return False

        if not candidates:
            return False

        needle_n = unidecode(needle.lower())
        best_i = -1
        best_score = 0.0
        for i, item in enumerate(candidates):
            hay = unidecode(str(item.get("text") or "").lower())
            if not hay:
                continue
            score = float(fuzz.token_set_ratio(needle_n, hay))
            if score > best_score:
                best_score = score
                best_i = i

        if best_i < 0 or best_score < self.click_fuzzy_threshold:
            return False

        chosen = candidates[best_i]
        href = str(chosen.get("href") or "")
        label = str(chosen.get("text") or "")[:60]
        if href and self._is_valid_href(href):
            if href.startswith("/"):
                href = urljoin(self._page.url, href)
            self._safe_goto(self._page, href)
        else:
            try:
                self._page.evaluate(
                    """(idx) => {
                      const sel = 'a[href], button, [role="link"], [role="button"], a#video-title';
                      const nodes = [];
                      for (const el of document.querySelectorAll(sel)) {
                        const r = el.getBoundingClientRect();
                        if (r.width < 2 || r.height < 2) continue;
                        const style = getComputedStyle(el);
                        if (style.visibility === 'hidden' || style.display === 'none') continue;
                        const text = (
                          el.getAttribute('aria-label')
                          || el.innerText
                          || el.title
                          || el.textContent
                          || ''
                        ).trim();
                        if (!text) continue;
                        nodes.push(el);
                        if (nodes.length >= 100) break;
                      }
                      const el = nodes[idx];
                      if (el) el.click();
                    }""",
                    best_i,
                )
            except Exception as exc:
                self.logger.warning(f"Clique semântico: click falhou: {exc}")
                return False

        self.logger.info(
            f"Clicou semântico: {label!r} (score={best_score:.0f})"
        )
        return True

    def scroll(self, direction: str, amount: int | None = None) -> None:
        self._ensure_started()
        assert self._page is not None
        total = amount if amount is not None else self.scroll_amount
        if direction == "up":
            total = -abs(total)
        elif direction == "down":
            total = abs(total)
        else:
            raise ValueError(f"Direção de rolagem inválida: {direction}")

        steps = self.scroll_steps
        step = total // steps
        for i in range(steps):
            chunk = step if i < steps - 1 else total - step * (steps - 1)
            if chunk:
                self._page.mouse.wheel(0, chunk)
            if self.scroll_step_ms:
                self._page.wait_for_timeout(self.scroll_step_ms)

        self.logger.info(
            f"Rolou para {'cima' if total < 0 else 'baixo'} ({abs(total)}px)."
        )

    def click_link(self, index: int = 0) -> None:
        self._ensure_started()
        assert self._page is not None
        if index < 0:
            raise ValueError("Índice de link inválido.")

        links = self._collect_links()
        if not links:
            raise RuntimeError("Nenhum link clicável encontrado na página.")

        if index >= len(links):
            raise RuntimeError(
                f"Link {index + 1} não encontrado ({len(links)} disponíveis)."
            )

        # Mesma aba: Bing/Google usam target=_blank; go_back quebraria.
        url = links[index].evaluate("el => el.href")
        if not url:
            raise RuntimeError("Link sem URL válida.")
        self._safe_goto(self._page, url)
        kind = "vídeo" if self._is_youtube() else "link"
        self.logger.info(f"Clicou no {kind} #{index + 1}")

    def _collect_links(self):
        assert self._page is not None
        if self._is_youtube():
            return self._collect_youtube_videos()

        selectors = [self.primary_selector, self.generic_selector, "a[href]"]
        seen_hrefs: set[str] = set()
        collected = []

        for selector in selectors:
            locator = self._page.locator(selector)
            count = locator.count()
            for i in range(count):
                link = locator.nth(i)
                if not link.is_visible():
                    continue
                href = link.get_attribute("href") or ""
                if not self._is_valid_href(href):
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                collected.append(link)
            if collected:
                return collected
        return collected

    def _collect_youtube_videos(self):
        """Só resultados de vídeo (/watch) — evita logo, canais, Shorts, etc."""
        assert self._page is not None
        selectors = (
            "a#video-title[href*='/watch']",
            "a#video-title-link[href*='/watch']",
            "ytd-video-renderer a[href*='/watch?v=']",
            "ytd-rich-item-renderer a#video-title-link[href*='/watch']",
        )
        seen_ids: set[str] = set()
        collected = []
        for selector in selectors:
            locator = self._page.locator(selector)
            count = locator.count()
            for i in range(count):
                link = locator.nth(i)
                try:
                    if not link.is_visible():
                        continue
                except Exception:
                    continue
                href = link.get_attribute("href") or ""
                vid = self._youtube_video_id(href)
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                collected.append(link)
            if collected:
                return collected
        return collected

    @staticmethod
    def _youtube_video_id(href: str) -> str | None:
        if not href:
            return None
        low = href.lower()
        if "/shorts/" in low or "/playlist" in low:
            return None
        m = re.search(r"[?&]v=([\w-]{6,})", href)
        return m.group(1) if m else None

    @staticmethod
    def _is_valid_href(href: str) -> bool:
        if not href:
            return False
        lowered = href.lower().strip()
        if lowered.startswith("javascript:"):
            return False
        if lowered in ("#", ""):
            return False
        return True

    def close(self) -> None:
        # Anexado via CDP: não fecha o browser do usuário; só solta a conexão.
        # KeyboardInterrupt não é Exception — precisa capturar no shutdown (Ctrl+C).
        def _quiet(fn) -> None:
            try:
                fn()
            except BaseException:
                pass

        if self._attached:
            self._page = None
            self._context = None
            browser, pw = self._browser, self._playwright
            self._browser = None
            self._playwright = None
            self._attached = False
            if browser:
                _quiet(browser.close)
            if pw:
                _quiet(pw.stop)
            self.logger.info("Desconectado do browser (CDP).")
            return

        if self._persistent:
            ctx, pw = self._context, self._playwright
            self._page = None
            self._context = None
            self._browser = None
            self._persistent = False
            self._playwright = None
            if ctx:
                _quiet(ctx.close)
            if pw:
                _quiet(pw.stop)
            self.logger.info("Browser persistente fechado.")
            return

        page, ctx, browser, pw = (
            self._page,
            self._context,
            self._browser,
            self._playwright,
        )
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        for resource in (page, ctx, browser):
            if resource:
                _quiet(resource.close)
        if pw:
            _quiet(pw.stop)
        self.logger.info("Browser fechado.")
