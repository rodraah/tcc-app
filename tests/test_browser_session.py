"""Testes de BrowserSession sem browser real."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.browser_session import BrowserSession, _flex_text_regex


def _session_with_page() -> tuple[BrowserSession, MagicMock]:
    session = BrowserSession(
        {
            "browser": {
                "scroll_steps": 1,
                "scroll_step_ms": 0,
                "scroll_amount": 600,
                "default_url": "https://example.com",
                "search_url": "https://example.com/search?q={query}",
            }
        }
    )
    page = MagicMock()
    page.is_closed.return_value = False
    page.url = "https://example.com/"
    page.frames = []
    empty = MagicMock()
    empty.count.return_value = 0
    empty.first.is_visible.return_value = False
    empty.filter.return_value = empty
    page.get_by_role.return_value = empty
    page.locator.return_value = empty
    page.get_by_text.return_value = empty
    session._page = page
    session._context = MagicMock()
    session._browser = MagicMock()
    session._playwright = MagicMock()
    return session, page


def test_scroll_one_step():
    session, page = _session_with_page()
    session.scroll("down")
    page.mouse.wheel.assert_called_once_with(0, 600)
    page.wait_for_timeout.assert_not_called()


def test_scroll_up_negative():
    session, page = _session_with_page()
    session.scroll("up")
    page.mouse.wheel.assert_called_once_with(0, -600)


def test_go_forward():
    session, page = _session_with_page()
    page.go_forward.return_value = MagicMock()
    session.go_forward()
    page.go_forward.assert_called_once_with(wait_until="domcontentloaded")


def test_go_forward_empty_raises():
    session, page = _session_with_page()
    page.go_forward.return_value = None
    try:
        session.go_forward()
        assert False
    except RuntimeError:
        pass


def test_refresh():
    session, page = _session_with_page()
    session.refresh()
    page.reload.assert_called_once_with(wait_until="domcontentloaded")


def test_zoom_in_out():
    session, page = _session_with_page()
    session.zoom("in")
    page.keyboard.down.assert_called_with("Control")
    page.keyboard.press.assert_called_with("=")
    page.keyboard.up.assert_called_with("Control")
    session.zoom("out")
    page.keyboard.press.assert_called_with("-")


def test_new_tab():
    session, page = _session_with_page()
    new_page = MagicMock()
    session._context.new_page.return_value = new_page
    session.new_tab("https://example.com/x")
    new_page.goto.assert_called_once_with(
        "https://example.com/x", wait_until="domcontentloaded"
    )
    assert session._page is new_page


def test_search_fallback_on_captcha():
    session, page = _session_with_page()
    session.search_url = "https://www.bing.com/search?q={query}"
    session.fallback_search_url = "https://duckduckgo.com/?q={query}"
    results = MagicMock()
    results.count.return_value = 0
    page.locator.return_value = results
    challenge = MagicMock()
    challenge.count.return_value = 1
    challenge.first.is_visible.return_value = True
    page.get_by_text.return_value = challenge
    session.search("tutorial python")
    assert page.goto.call_count == 2
    assert "bing.com/search" in page.goto.call_args_list[0].args[0]
    assert "duckduckgo.com" in page.goto.call_args_list[1].args[0]


def test_search_no_fallback_when_ok():
    session, page = _session_with_page()
    session.search_url = "https://www.bing.com/search?q={query}"
    session.fallback_search_url = "https://duckduckgo.com/?q={query}"
    results = MagicMock()
    results.count.return_value = 3
    page.locator.return_value = results
    session.search("tutorial")
    page.goto.assert_called_once()
    assert "bing.com/search" in page.goto.call_args.args[0]


def test_search_no_fallback_on_script_noise():
    """HTML do Bing traz 'challenge'/'captcha' em scripts — não é CAPTCHA."""
    session, page = _session_with_page()
    session.search_url = "https://www.bing.com/search?q={query}"
    session.fallback_search_url = "https://duckduckgo.com/?q={query}"
    results = MagicMock()
    results.count.return_value = 0
    page.locator.return_value = results
    empty = MagicMock()
    empty.count.return_value = 0
    page.get_by_text.return_value = empty
    session.search("relaciona")
    page.goto.assert_called_once()


def test_search_on_youtube_uses_youtube():
    session, page = _session_with_page()
    page.url = "https://www.youtube.com/"
    session.search("tutorial pyt")
    page.goto.assert_called_once()
    url = page.goto.call_args.args[0]
    assert "youtube.com/results" in url
    assert "tutorial" in url
    assert "bing.com" not in url


def test_close_tab_keeps_previous():
    session, page = _session_with_page()
    other = MagicMock()
    other.is_closed.return_value = False

    def close_side_effect():
        page.is_closed.return_value = True

    page.close.side_effect = close_side_effect
    page.is_closed.return_value = False
    session._context.pages = [other, page]
    session.close_tab()
    page.close.assert_called_once()
    assert session._page is other
    other.bring_to_front.assert_called_once()


def test_close_last_tab_raises():
    session, page = _session_with_page()
    session._context.pages = [page]
    try:
        session.close_tab()
        assert False
    except RuntimeError:
        pass


def test_click_text_by_link_href():
    session, page = _session_with_page()
    link = MagicMock()
    link.get_attribute.return_value = "https://example.com/doc"
    locator = MagicMock()
    locator.count.return_value = 1
    locator.first = link
    page.get_by_role.return_value = locator
    session.click_text("doc")
    page.goto.assert_called_once_with(
        "https://example.com/doc", wait_until="domcontentloaded"
    )


def test_click_text_youtube_title():
    session, page = _session_with_page()
    page.url = "https://www.youtube.com/results?search_query=x"
    yt = MagicMock()
    yt.count.return_value = 1
    link = MagicMock()
    link.get_attribute.return_value = "/watch?v=abc"
    yt.first = link
    yt.filter.return_value = yt
    page.locator.return_value = yt
    session.click_text("liberado na franca")
    assert "youtube.com/watch?v=abc" in page.goto.call_args.args[0]


def test_click_first_youtube_video():
    session, page = _session_with_page()
    page.url = "https://www.youtube.com/results?search_query=tutorial"
    v1 = MagicMock()
    v1.is_visible.return_value = True
    v1.get_attribute.return_value = "/watch?v=VIDEO1"
    v1.evaluate.return_value = "https://www.youtube.com/watch?v=VIDEO1"
    v2 = MagicMock()
    v2.is_visible.return_value = True
    v2.get_attribute.return_value = "/watch?v=VIDEO2"
    locator = MagicMock()
    locator.count.return_value = 2
    locator.nth.side_effect = lambda i: (v1, v2)[i]
    page.locator.return_value = locator
    session.click_link(0)
    assert "VIDEO1" in page.goto.call_args.args[0]


def test_youtube_video_id_skips_shorts():
    assert BrowserSession._youtube_video_id("/watch?v=abc123xyz") == "abc123xyz"
    assert BrowserSession._youtube_video_id("/shorts/abc123xyz") is None


def test_flex_text_regex_accents():
    pat = _flex_text_regex("liberado na franca")
    assert pat.search("Liberado na França — clip")
    assert pat.search("liberado na franca")


def test_semantic_click_fallback():
    session, page = _session_with_page()
    # seletores atuais falham
    empty = page.locator.return_value
    page.get_by_role.return_value = empty
    page.get_by_text.return_value = empty
    page.evaluate.side_effect = [
        [
            {"text": "Outro link", "href": "https://example.com/a"},
            {
                "text": "Tutorial Python completo 2024",
                "href": "https://example.com/tutorial-python",
            },
        ],
    ]
    session.click_text("tutorial python")
    assert "tutorial-python" in page.goto.call_args.args[0]


def test_semantic_click_below_threshold_raises():
    session, page = _session_with_page()
    empty = page.locator.return_value
    page.get_by_role.return_value = empty
    page.get_by_text.return_value = empty
    page.evaluate.return_value = [
        {"text": "Completely unrelated", "href": "https://example.com/x"},
    ]
    try:
        session.click_text("tutorial python")
        assert False, "deveria falhar"
    except RuntimeError:
        pass


def test_is_valid_href():
    assert BrowserSession._is_valid_href("https://x.com")
    assert not BrowserSession._is_valid_href("javascript:void(0)")
    assert not BrowserSession._is_valid_href("#")


def test_normalize_url():
    assert BrowserSession.normalize_url("github.com") == "https://github.com"
    assert BrowserSession.normalize_url("youtube") == "https://youtube.com"
    assert BrowserSession.normalize_url("https://x.com/y") == "https://x.com/y"


def test_switch_tab_next_prev():
    session, page = _session_with_page()
    other = MagicMock()
    other.is_closed.return_value = False
    other.title.return_value = "Other"
    page.title.return_value = "Current"
    session._context.pages = [page, other]
    session.switch_tab(direction="next")
    assert session._page is other
    other.bring_to_front.assert_called_once()
    session.switch_tab(direction="prev")
    assert session._page is page


def test_switch_tab_by_title():
    session, page = _session_with_page()
    yt = MagicMock()
    yt.is_closed.return_value = False
    yt.title.return_value = "YouTube"
    yt.url = "https://www.youtube.com/watch?v=1"
    page.title.return_value = "Bing"
    page.url = "https://bing.com"
    session._context.pages = [page, yt]
    session.switch_tab(title="youtube")
    assert session._page is yt


def test_find_in_page():
    session, page = _session_with_page()
    session.find_in_page("python")
    page.keyboard.press.assert_called_with("Control+f")
    page.keyboard.type.assert_called_with("python", delay=20)


def test_click_role_button():
    session, page = _session_with_page()
    locator = MagicMock()
    locator.count.return_value = 1
    page.get_by_role.return_value = locator
    session.click_role("button", "enviar")
    page.get_by_role.assert_called_once()
    locator.first.click.assert_called_once()


def test_youtube_keys():
    session, page = _session_with_page()
    session.youtube("play_pause")
    page.keyboard.press.assert_called_with("k")
    session.youtube("forward")
    page.keyboard.press.assert_called_with("l")


def test_youtube_volume_presses_multiple():
    session, page = _session_with_page()
    session.youtube("volume_up")
    assert page.keyboard.press.call_count == 4
    page.keyboard.press.assert_called_with("ArrowUp")


def test_attach_cdp_does_not_close_user_browser():
    session = BrowserSession(
        {"browser": {"cdp_url": "http://127.0.0.1:9222", "user_data_dir": ""}}
    )
    browser = MagicMock()
    context = MagicMock()
    page = MagicMock()
    page.is_closed.return_value = False
    context.pages = [page]
    browser.contexts = [context]
    pw = MagicMock()
    pw.chromium.connect_over_cdp.return_value = browser
    with patch("playwright.sync_api.sync_playwright") as sp:
        sp.return_value.start.return_value = pw
        session.start()
    assert session._attached is True
    assert session._page is page
    session.close()
    # close() no CDP desconecta; browser.close no Playwright CDP = disconnect
    browser.close.assert_called_once()


def test_channel_candidates_prefers_installed():
    session = BrowserSession({"browser": {"channel": "auto", "user_data_dir": ""}})
    with patch(
        "voice.browser_session._channel_installed",
        side_effect=lambda n: n == "msedge",
    ):
        assert session._channel_candidates() == ["msedge", None]


def test_channel_candidates_chrome_missing_falls_to_edge():
    session = BrowserSession(
        {"browser": {"channel": "chrome", "user_data_dir": ""}}
    )
    with patch(
        "voice.browser_session._channel_installed",
        side_effect=lambda n: n == "msedge",
    ):
        assert session._channel_candidates() == ["msedge", None]


def test_start_persistent_tries_edge_when_chrome_missing():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        session = BrowserSession(
            {
                "browser": {
                    "channel": "auto",
                    "user_data_dir": tmp,
                    "default_url": "https://example.com",
                }
            }
        )
        pw = MagicMock()
        ctx = MagicMock()
        page = MagicMock()
        page.is_closed.return_value = False
        ctx.pages = [page]
        pw.chromium.launch_persistent_context.return_value = ctx

        with patch("playwright.sync_api.sync_playwright") as sp:
            sp.return_value.start.return_value = pw
            with patch(
                "voice.browser_session._channel_installed",
                side_effect=lambda n: n == "msedge",
            ):
                session.start()

        kwargs = pw.chromium.launch_persistent_context.call_args.kwargs
        assert kwargs.get("channel") == "msedge"
        assert session._active_channel == "msedge"
        page.goto.assert_called_once()
        session.close()


def test_dismiss_cookie_banner_rejects():
    session, page = _session_with_page()
    page.url = "https://www.bing.com/"
    btn = MagicMock()
    btn.count.return_value = 1
    btn.first.is_visible.return_value = True
    # 1ª tentativa: selectors vazios; role encontra Rejeitar
    empty = MagicMock()
    empty.count.return_value = 0
    page.locator.return_value = empty
    page.get_by_role.return_value = btn
    page.frames = []
    session._dismiss_cookie_banner()
    btn.first.click.assert_called_once()


def test_dismiss_cookie_banner_bing_id():
    session, page = _session_with_page()
    page.url = "https://www.bing.com/"
    page.frames = []
    reject = MagicMock()
    reject.count.return_value = 1
    reject.first.is_visible.return_value = True
    page.locator.side_effect = lambda sel: (
        reject if "bnp_btn_reject" in sel else MagicMock(count=MagicMock(return_value=0))
    )
    assert session._try_dismiss_cookie_once() is True
    reject.first.click.assert_called_once()


def test_safe_goto_dismisses_cookies():
    session, page = _session_with_page()
    with patch.object(session, "_dismiss_cookie_banner") as dismiss:
        session._safe_goto(page, "https://example.com")
    page.goto.assert_called_once_with(
        "https://example.com", wait_until="domcontentloaded"
    )
    dismiss.assert_called_once()


# --- Regression: relative user_data_dir resolves under PROJECT_ROOT ----------

def test_relative_user_data_resolves_under_project_root():
    """Relative user_data_dir is resolved against PROJECT_ROOT."""
    from voice.paths import PROJECT_ROOT
    session = BrowserSession(
        {"browser": {"user_data_dir": ".test-profile"}}
    )
    assert session.user_data_dir.startswith(str(PROJECT_ROOT))
    assert ".test-profile" in session.user_data_dir


def test_absolute_user_data_passthrough():
    """Absolute user_data_dir is kept unchanged."""
    session = BrowserSession(
        {"browser": {"user_data_dir": "C:\\tmp\\my-profile"}}
    )
    assert session.user_data_dir == "C:\\tmp\\my-profile"


def test_empty_user_data_stays_empty():
    """Empty user_data_dir remains empty string."""
    session = BrowserSession(
        {"browser": {"user_data_dir": ""}}
    )
    assert session.user_data_dir == ""


if __name__ == "__main__":
    test_scroll_one_step()
    test_scroll_up_negative()
    test_go_forward()
    test_go_forward_empty_raises()
    test_refresh()
    test_zoom_in_out()
    test_new_tab()
    test_search_fallback_on_captcha()
    test_search_no_fallback_when_ok()
    test_search_no_fallback_on_script_noise()
    test_search_on_youtube_uses_youtube()
    test_close_tab_keeps_previous()
    test_close_last_tab_raises()
    test_click_text_by_link_href()
    test_click_text_youtube_title()
    test_click_first_youtube_video()
    test_youtube_video_id_skips_shorts()
    test_flex_text_regex_accents()
    test_semantic_click_fallback()
    test_semantic_click_below_threshold_raises()
    test_is_valid_href()
    test_normalize_url()
    test_switch_tab_next_prev()
    test_switch_tab_by_title()
    test_find_in_page()
    test_click_role_button()
    test_youtube_keys()
    test_youtube_volume_presses_multiple()
    test_attach_cdp_does_not_close_user_browser()
    test_channel_candidates_prefers_installed()
    test_channel_candidates_chrome_missing_falls_to_edge()
    test_start_persistent_tries_edge_when_chrome_missing()
    test_dismiss_cookie_banner_rejects()
    test_dismiss_cookie_banner_bing_id()
    test_safe_goto_dismisses_cookies()
    test_relative_user_data_resolves_under_project_root()
    test_absolute_user_data_passthrough()
    test_empty_user_data_stays_empty()
    print("Todos os testes passaram.")
