from voice.browser_session import BrowserSession
from voice.models import Intent


def browser_open_handler(intent: Intent, session: BrowserSession) -> None:
    url = intent.params.get("url") or session.default_url
    session.start(url)


def browser_search_handler(intent: Intent, session: BrowserSession) -> None:
    query = intent.params.get("query")
    if not query:
        raise ValueError("Parâmetro 'query' ausente.")
    session.search(query)


def browser_click_link_handler(intent: Intent, session: BrowserSession) -> None:
    index = intent.params.get("index", 0)
    session.click_link(int(index))


def browser_click_text_handler(intent: Intent, session: BrowserSession) -> None:
    text = intent.params.get("text")
    if not text:
        raise ValueError("Parâmetro 'text' ausente.")
    session.click_text(str(text))


def browser_back_handler(intent: Intent, session: BrowserSession) -> None:
    session.go_back()


def browser_forward_handler(intent: Intent, session: BrowserSession) -> None:
    session.go_forward()


def browser_refresh_handler(intent: Intent, session: BrowserSession) -> None:
    session.refresh()


def browser_new_tab_handler(intent: Intent, session: BrowserSession) -> None:
    session.new_tab()


def browser_close_tab_handler(intent: Intent, session: BrowserSession) -> None:
    session.close_tab()


def browser_scroll_handler(intent: Intent, session: BrowserSession) -> None:
    direction = intent.params.get("direction")
    if direction not in ("up", "down"):
        raise ValueError("Parâmetro 'direction' deve ser 'up' ou 'down'.")
    session.scroll(direction)


def browser_zoom_handler(intent: Intent, session: BrowserSession) -> None:
    direction = intent.params.get("direction")
    if direction not in ("in", "out"):
        raise ValueError("Parâmetro 'direction' deve ser 'in' ou 'out'.")
    session.zoom(direction)


def browser_switch_tab_handler(intent: Intent, session: BrowserSession) -> None:
    session.switch_tab(
        direction=intent.params.get("direction"),
        index=intent.params.get("index"),
        title=intent.params.get("title"),
    )


def browser_goto_handler(intent: Intent, session: BrowserSession) -> None:
    url = intent.params.get("url")
    if not url:
        raise ValueError("Parâmetro 'url' ausente.")
    session.navigate(BrowserSession.normalize_url(str(url)))


def browser_find_handler(intent: Intent, session: BrowserSession) -> None:
    text = intent.params.get("text")
    if not text:
        raise ValueError("Parâmetro 'text' ausente.")
    session.find_in_page(str(text))


def browser_click_role_handler(intent: Intent, session: BrowserSession) -> None:
    role = intent.params.get("role")
    if not role:
        raise ValueError("Parâmetro 'role' ausente.")
    session.click_role(str(role), intent.params.get("name"))


def browser_youtube_handler(intent: Intent, session: BrowserSession) -> None:
    action = intent.params.get("action")
    if not action:
        raise ValueError("Parâmetro 'action' ausente.")
    session.youtube(str(action))
