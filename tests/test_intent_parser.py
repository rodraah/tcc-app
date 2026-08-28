"""Testes unitários do parser de intenção (sem microfone)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.intent_parser import IntentParser


def test_open_app():
    parser = IntentParser()
    intent = parser.parse("assistente, abrir bloco de notas")
    assert intent is not None
    assert intent.name == "open_app"
    assert intent.params["app"] == "notepad"


def test_open_calculator():
    parser = IntentParser()
    intent = parser.parse("assistente abrir calculadora")
    assert intent is not None
    assert intent.name == "open_app"
    assert intent.params["app"] == "calc"


def test_open_browser():
    parser = IntentParser()
    intent = parser.parse("assistente, abrir navegador")
    assert intent is not None
    assert intent.name == "browser_open"
    assert "bing.com" in intent.params["url"]


def test_browser_back():
    parser = IntentParser()
    for phrase in ("voltar", "volte", "retornar"):
        intent = parser.parse(phrase)
        assert intent is not None, phrase
        assert intent.name == "browser_back"


def test_browser_scroll_down():
    parser = IntentParser()
    for phrase in (
        "role para baixo",
        "role para baixo a pagina",
        "rolar para baixo",
    ):
        intent = parser.parse(phrase)
        assert intent is not None, phrase
        assert intent.name == "browser_scroll"
        assert intent.params["direction"] == "down"


def test_browser_scroll_up():
    parser = IntentParser()
    for phrase in ("role para cima", "role para cima a pagina"):
        intent = parser.parse(phrase)
        assert intent is not None, phrase
        assert intent.name == "browser_scroll"
        assert intent.params["direction"] == "up"


def test_open_youtube():
    parser = IntentParser()
    intent = parser.parse("assistente, abrir youtube")
    assert intent is not None
    assert intent.name == "open_url"
    assert "youtube" in intent.params["url"]


def test_browser_search():
    parser = IntentParser()
    intent = parser.parse("pesquisa python tutorial")
    assert intent is not None
    assert intent.name == "browser_search"
    assert intent.params["query"] == "python tutorial"


def test_browser_search_buscar():
    parser = IntentParser()
    intent = parser.parse("buscar receita de bolo")
    assert intent is not None
    assert intent.name == "browser_search"
    assert "receita de bolo" in intent.params["query"]


def test_browser_search_pesquise():
    parser = IntentParser()
    intent = parser.parse("pesquise tutorial pyt")
    assert intent is not None
    assert intent.name == "browser_search"
    assert intent.params["query"] == "tutorial pyt"


def test_browser_click_first_link():
    parser = IntentParser()
    intent = parser.parse("clique no primeiro link")
    assert intent is not None
    assert intent.name == "browser_click_link"
    assert intent.params["index"] == 0


def test_browser_click_second_link():
    parser = IntentParser()
    intent = parser.parse("clique no segundo link")
    assert intent is not None
    assert intent.name == "browser_click_link"
    assert intent.params["index"] == 1


def test_browser_click_second_without_link():
    parser = IntentParser()
    intent = parser.parse("clicar no segundo")
    assert intent is not None
    assert intent.name == "browser_click_link"
    assert intent.params["index"] == 1


def test_browser_click_first_video():
    parser = IntentParser()
    intent = parser.parse("clique no primeiro video")
    assert intent is not None
    assert intent.name == "browser_click_link"
    assert intent.params["index"] == 0


def test_browser_click_text():
    parser = IntentParser()
    intent = parser.parse("clicar em tutorial python")
    assert intent is not None
    assert intent.name == "browser_click_text"
    assert "tutorial python" in intent.params["text"]


def test_browser_click_text_without_preposition():
    """STT: 'clicar liberado na franca' sem 'em'."""
    parser = IntentParser()
    intent = parser.parse("clicar liberado na franca")
    assert intent is not None
    assert intent.name == "browser_click_text"
    assert intent.params["text"] == "liberado na franca"


def test_browser_forward_refresh_tabs_zoom():
    parser = IntentParser()
    assert parser.parse("avancar").name == "browser_forward"
    assert parser.parse("atualizar pagina").name == "browser_refresh"
    assert parser.parse("atualizar a pagina").name == "browser_refresh"
    assert parser.parse("nova aba").name == "browser_new_tab"
    assert parser.parse("fechar aba").name == "browser_close_tab"
    assert parser.parse("aumentar zoom").params["direction"] == "in"
    assert parser.parse("diminuir zoom").params["direction"] == "out"


def test_hotkeys_and_keys():
    parser = IntentParser()
    intent = parser.parse("copiar")
    assert intent.name == "hotkey"
    assert intent.params["keys"] == ["ctrl", "c"]
    assert parser.parse("enter").name == "press_key"
    assert parser.parse("enter").params["key"] == "enter"
    assert parser.parse("colar").params["keys"] == ["ctrl", "v"]


def test_window_and_switch():
    parser = IntentParser()
    assert parser.parse("minimizar").params["action"] == "minimize"
    assert parser.parse("proxima janela").params["direction"] == "next"
    intent = parser.parse("focar bloco de notas")
    assert intent.name == "focus_app"
    assert intent.params["app"] == "notepad"


def test_maximizar_com_app():
    parser = IntentParser()
    intent = parser.parse("maximizar bloco de notas")
    assert intent is not None
    assert intent.name == "window_action"
    assert intent.params["action"] == "maximize"
    assert intent.params["app"] == "notepad"


def test_help_repeat_cancel():
    parser = IntentParser()
    assert parser.parse("ajuda").name == "help"
    assert parser.parse("repetir").name == "repeat_last"
    assert parser.parse("cancelar").name == "cancel"


def test_volume_desktop_lock_a11y_run():
    parser = IntentParser()
    assert parser.parse("aumentar volume").params["action"] == "up"
    assert parser.parse("abaixar volume").params["action"] == "down"
    assert parser.parse("baixar volume").params["action"] == "down"
    assert parser.parse("mudo").params["action"] == "mute"
    assert parser.parse("mostrar area de trabalho").name == "show_desktop"
    lock = parser.parse("bloquear computador")
    assert lock.name == "lock_pc"
    assert lock.params["confirmed"] is False
    confirm = parser.parse_lock_confirm("confirmar")
    assert confirm.name == "lock_pc"
    assert confirm.params["confirmed"] is True
    assert parser.parse("abrir lupa").name == "open_a11y"
    assert parser.parse("abrir lupa").params["app"] == "magnify"
    run = parser.parse("executar notepad")
    assert run.name == "run_dialog"
    assert run.params["command"] == "notepad"


def test_open_explorer():
    parser = IntentParser()
    intent = parser.parse("abrir explorador")
    assert intent is not None
    assert intent.name == "open_app"
    assert intent.params["app"] == "explorer"


def test_open_url():
    parser = IntentParser()
    intent = parser.parse("assistente, abrir site google")
    assert intent is not None
    assert intent.name == "open_url"
    assert "google" in intent.params["url"]


def test_without_wake_word():
    parser = IntentParser()
    intent = parser.parse("abrir bloco de notas")
    assert intent is not None
    assert intent.name == "open_app"


def test_partial_app_name():
    parser = IntentParser()
    intent = parser.parse("assistente abrir bloco")
    assert intent is not None
    assert intent.name == "open_app"
    assert intent.params["app"] == "notepad"


def test_type_text():
    parser = IntentParser()
    intent = parser.parse("assistente, digitar ola mundo")
    assert intent is not None
    assert intent.name == "type_text"
    assert "ola mundo" in intent.params["text"]


def test_type_text_digite_without_wake_word():
    parser = IntentParser()
    intent = parser.parse("digite ola mundo")
    assert intent is not None
    assert intent.name == "type_text"
    assert "ola mundo" in intent.params["text"]


def test_vosk_misrecognition_abril():
    parser = IntentParser()
    intent = parser.parse("assistente abril bloco de notas")
    assert intent is not None
    assert intent.name == "open_app"
    assert intent.params["app"] == "notepad"


def test_close_notepad():
    parser = IntentParser()
    intent = parser.parse("fechar bloco de notas")
    assert intent is not None
    assert intent.name == "close_app"
    assert intent.params["app"] == "notepad"


def test_dialog_save():
    parser = IntentParser()
    intent = parser.parse("salvar", dialog_mode=True)
    assert intent is not None
    assert intent.name == "dialog_choice"
    assert intent.params["choice"] == "save"


def test_dialog_discard():
    parser = IntentParser()
    intent = parser.parse("nao salvar", dialog_mode=True)
    assert intent is not None
    assert intent.params["choice"] == "discard"


def test_dialog_cancel():
    parser = IntentParser()
    intent = parser.parse("cancelar", dialog_mode=True)
    assert intent is not None
    assert intent.params["choice"] == "cancel"


def test_scroll_not_cancelled_by_para():
    """'para' em 'role para baixo' não deve virar cancel."""
    parser = IntentParser()
    intent = parser.parse("role para baixo")
    assert intent.name == "browser_scroll"


def test_open_folder():
    parser = IntentParser()
    for phrase in ("abrir pasta downloads", "abrir downloads", "abrir documentos"):
        intent = parser.parse(phrase)
        assert intent is not None, phrase
        assert intent.name == "open_folder"
        assert intent.params["path"].startswith("shell:")


def test_windows_search():
    parser = IntentParser()
    intent = parser.parse("pesquisar no windows notepad")
    assert intent is not None
    assert intent.name == "windows_search"
    assert intent.params["query"] == "notepad"


def test_browser_switch_tab():
    parser = IntentParser()
    assert parser.parse("proxima aba").params["direction"] == "next"
    assert parser.parse("aba anterior").params["direction"] == "prev"
    assert parser.parse("aba 2").params["index"] == 1
    assert parser.parse("focar aba youtube").params["title"] == "youtube"


def test_browser_goto():
    parser = IntentParser()
    intent = parser.parse("ir para github.com")
    assert intent.name == "browser_goto"
    assert "github.com" in intent.params["url"]


def test_browser_find_in_page():
    parser = IntentParser()
    intent = parser.parse("encontrar na pagina python")
    assert intent.name == "browser_find"
    assert intent.params["text"] == "python"
    # não deve roubar busca web
    web = parser.parse("buscar receita de bolo")
    assert web.name == "browser_search"


def test_browser_click_role():
    parser = IntentParser()
    btn = parser.parse("clicar no botao enviar")
    assert btn.name == "browser_click_role"
    assert btn.params == {"role": "button", "name": "enviar"}
    field = parser.parse("clicar no campo busca")
    assert field.name == "browser_click_role"
    assert field.params["role"] == "textbox"


def test_browser_youtube():
    parser = IntentParser()
    assert parser.parse("pausar video").params["action"] == "play_pause"
    assert parser.parse("avancar video").params["action"] == "forward"
    assert parser.parse("voltar video").params["action"] == "rewind"
    # "voltar" sozinho continua sendo browser_back
    assert parser.parse("voltar").name == "browser_back"
    # fora do YouTube, "pausar" sozinho não casa
    assert parser.parse("pausar") is None


def test_youtube_short_actions_only_on_youtube():
    parser = IntentParser()
    assert parser.parse("pausar", youtube_mode=True).params["action"] == "play_pause"
    assert parser.parse("despausar", youtube_mode=True).params["action"] == "play_pause"
    assert parser.parse("avancar", youtube_mode=True).params["action"] == "forward"
    assert parser.parse("retroceder", youtube_mode=True).params["action"] == "rewind"
    assert parser.parse("aumentar som", youtube_mode=True).params["action"] == "volume_up"
    assert parser.parse("diminuir som", youtube_mode=True).params["action"] == "volume_down"
    assert parser.parse("mudo", youtube_mode=True).params["action"] == "mute"
    # fora do YouTube, mudo/avancar continuam sistema/navegador
    assert parser.parse("mudo").name == "volume"
    assert parser.parse("avancar").name == "browser_forward"


if __name__ == "__main__":
    test_open_app()
    test_open_calculator()
    test_open_browser()
    test_browser_back()
    test_browser_scroll_down()
    test_browser_scroll_up()
    test_open_youtube()
    test_browser_search()
    test_browser_search_buscar()
    test_browser_search_pesquise()
    test_browser_click_first_link()
    test_browser_click_second_link()
    test_browser_click_second_without_link()
    test_browser_click_first_video()
    test_browser_click_text()
    test_browser_click_text_without_preposition()
    test_browser_forward_refresh_tabs_zoom()
    test_hotkeys_and_keys()
    test_window_and_switch()
    test_maximizar_com_app()
    test_help_repeat_cancel()
    test_volume_desktop_lock_a11y_run()
    test_open_explorer()
    test_open_url()
    test_without_wake_word()
    test_partial_app_name()
    test_type_text()
    test_type_text_digite_without_wake_word()
    test_vosk_misrecognition_abril()
    test_close_notepad()
    test_dialog_save()
    test_dialog_discard()
    test_dialog_cancel()
    test_scroll_not_cancelled_by_para()
    test_open_folder()
    test_windows_search()
    test_browser_switch_tab()
    test_browser_goto()
    test_browser_find_in_page()
    test_browser_click_role()
    test_browser_youtube()
    test_youtube_short_actions_only_on_youtube()
    print("Todos os testes passaram.")
