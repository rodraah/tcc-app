"""Unit tests for gesture/acoes.py — action registry, window control,
system shortcuts, text editing, and mapping loading."""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Hermetic stubs for the ML stack.
# Importing `gesture` triggers gesture/__init__.py -> gestos.py, which imports
# mediapipe + cv2 at module level. When the full suite runs, test_app_shell
# installs a fake PIL that breaks mediapipe's matplotlib import, so we stub
# mediapipe/cv2 here to keep this test environment-independent.
# ---------------------------------------------------------------------------
_mp = types.ModuleType("mediapipe")
_mp_tasks = types.ModuleType("mediapipe.tasks")
_mp_tasks_python = types.ModuleType("mediapipe.tasks.python")
_mp_vision = MagicMock(name="mediapipe.tasks.python.vision")
_mp_tasks_python.vision = _mp_vision
_mp_tasks.python = _mp_tasks_python
_mp.tasks = _mp_tasks
sys.modules["mediapipe"] = _mp
sys.modules["mediapipe.tasks"] = _mp_tasks
sys.modules["mediapipe.tasks.python"] = _mp_tasks_python
sys.modules["mediapipe.tasks.python.vision"] = _mp_vision

_cv2 = types.ModuleType("cv2")
sys.modules["cv2"] = _cv2

from gesture import config
from gesture.acoes import (
    REGISTRO_ACOES,
    VK_A,
    VK_C,
    VK_D,
    VK_E,
    VK_I,
    VK_L,
    VK_S,
    VK_V,
    VK_X,
    VK_Y,
    VK_Z,
    carregar_mapeamento,
    executar_acao,
)
import gesture.utils as utils
import win32con


EXPECTED_ACTIONS = {
    "minimizar",
    "lupa",
    "maximizar",
    "fechar_janela",
    "alternar_janela",
    "mostrar_area_trabalho",
    "tela_cheia",
    "captura_tela",
    "bloquear_tela",
    "abrir_explorador",
    "abrir_configuracoes",
    "abrir_calculadora",
    "abrir_gerenciador_tarefas",
    "copiar",
    "colar",
    "recortar",
    "desfazer",
    "refazer",
    "selecionar_tudo",
}


class TestRegistroAcoes(unittest.TestCase):
    """Registration completeness: the registry contains exactly the 19 actions."""

    def test_registro_completo(self):
        self.assertEqual(set(REGISTRO_ACOES), EXPECTED_ACTIONS)


class TestMaximizar(unittest.TestCase):
    """maximizar toggles between maximize and restore."""

    @patch("gesture.utils.win32gui")
    def test_normal_window_maximizes(self, mock_win32gui):
        mock_win32gui.GetForegroundWindow.return_value = 100
        mock_win32gui.IsWindow.return_value = True
        mock_win32gui.IsZoomed.return_value = False

        executar_acao("maximizar")

        mock_win32gui.ShowWindow.assert_called_once_with(100, win32con.SW_MAXIMIZE)

    @patch("gesture.utils.win32gui")
    def test_maximized_window_restores(self, mock_win32gui):
        mock_win32gui.GetForegroundWindow.return_value = 100
        mock_win32gui.IsWindow.return_value = True
        mock_win32gui.IsZoomed.return_value = True

        executar_acao("maximizar")

        mock_win32gui.ShowWindow.assert_called_once_with(100, win32con.SW_RESTORE)

    @patch("gesture.utils.win32gui")
    def test_no_foreground_window_noop(self, mock_win32gui):
        mock_win32gui.GetForegroundWindow.return_value = 0

        executar_acao("maximizar")

        mock_win32gui.ShowWindow.assert_not_called()


class TestFecharJanela(unittest.TestCase):
    """fechar_janela sends WM_CLOSE to the active window."""

    @patch("gesture.utils.win32gui")
    def test_sends_wm_close(self, mock_win32gui):
        mock_win32gui.GetForegroundWindow.return_value = 100
        mock_win32gui.IsWindow.return_value = True

        executar_acao("fechar_janela")

        mock_win32gui.PostMessage.assert_called_once_with(100, win32con.WM_CLOSE, 0, 0)

    @patch("gesture.utils.win32gui")
    def test_no_window_noop(self, mock_win32gui):
        mock_win32gui.GetForegroundWindow.return_value = 0

        executar_acao("fechar_janela")

        mock_win32gui.PostMessage.assert_not_called()


class TestComboAcoes(unittest.TestCase):
    """Each combo action calls combo_tecla with the exact VK list."""

    @patch("gesture.utils.combo_tecla")
    def test_alternar_janela(self, mock_combo):
        executar_acao("alternar_janela")
        mock_combo.assert_called_once_with([win32con.VK_MENU, win32con.VK_TAB])

    @patch("gesture.utils.combo_tecla")
    def test_mostrar_area_trabalho(self, mock_combo):
        executar_acao("mostrar_area_trabalho")
        mock_combo.assert_called_once_with([win32con.VK_LWIN, VK_D])

    @patch("gesture.utils.combo_tecla")
    def test_tela_cheia(self, mock_combo):
        executar_acao("tela_cheia")
        mock_combo.assert_called_once_with([win32con.VK_F11])

    @patch("gesture.utils.combo_tecla")
    def test_captura_tela(self, mock_combo):
        executar_acao("captura_tela")
        mock_combo.assert_called_once_with(
            [win32con.VK_LWIN, win32con.VK_SHIFT, VK_S]
        )

    @patch("gesture.utils.combo_tecla")
    def test_bloquear_tela(self, mock_combo):
        executar_acao("bloquear_tela")
        mock_combo.assert_called_once_with([win32con.VK_LWIN, VK_L])

    @patch("gesture.utils.combo_tecla")
    def test_abrir_explorador(self, mock_combo):
        executar_acao("abrir_explorador")
        mock_combo.assert_called_once_with([win32con.VK_LWIN, VK_E])

    @patch("gesture.utils.combo_tecla")
    def test_abrir_configuracoes(self, mock_combo):
        executar_acao("abrir_configuracoes")
        mock_combo.assert_called_once_with([win32con.VK_LWIN, VK_I])

    @patch("gesture.utils.combo_tecla")
    def test_abrir_gerenciador_tarefas(self, mock_combo):
        executar_acao("abrir_gerenciador_tarefas")
        mock_combo.assert_called_once_with(
            [win32con.VK_CONTROL, win32con.VK_SHIFT, win32con.VK_ESCAPE]
        )

    @patch("gesture.utils.combo_tecla")
    def test_copiar(self, mock_combo):
        executar_acao("copiar")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_C])

    @patch("gesture.utils.combo_tecla")
    def test_colar(self, mock_combo):
        executar_acao("colar")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_V])

    @patch("gesture.utils.combo_tecla")
    def test_recortar(self, mock_combo):
        executar_acao("recortar")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_X])

    @patch("gesture.utils.combo_tecla")
    def test_desfazer(self, mock_combo):
        executar_acao("desfazer")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_Z])

    @patch("gesture.utils.combo_tecla")
    def test_refazer(self, mock_combo):
        executar_acao("refazer")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_Y])

    @patch("gesture.utils.combo_tecla")
    def test_selecionar_tudo(self, mock_combo):
        executar_acao("selecionar_tudo")
        mock_combo.assert_called_once_with([win32con.VK_CONTROL, VK_A])


class TestAbrirCalculadora(unittest.TestCase):
    """abrir_calculadora launches calc.exe via os.startfile."""

    @patch("gesture.acoes.os.startfile")
    def test_abre_calc_exe(self, mock_startfile):
        executar_acao("abrir_calculadora")
        mock_startfile.assert_called_once_with("calc.exe")


class TestMapaPadraoValido(unittest.TestCase):
    """Every action referenced in MAPA_PADRAO must be registered."""

    def test_todas_acoes_registradas(self):
        for gesto, acao in config.MAPA_PADRAO.items():
            self.assertIn(
                acao,
                REGISTRO_ACOES,
                f"Acao '{acao}' (gesto '{gesto}') nao esta registrada",
            )


class TestCarregarMapeamento(unittest.TestCase):
    """carregar_mapeamento behavior for missing and invalid files."""

    def test_arquivo_ausente_retorna_padrao(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_inexistente = Path(tmpdir) / "nao_existe.json"
            resultado = carregar_mapeamento(caminho_inexistente)
            self.assertEqual(resultado, dict(config.MAPA_PADRAO))

    def test_acao_desconhecida_retorna_vazio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho = Path(tmpdir) / "mapeamento.json"
            caminho.write_text(
                json.dumps({"schema": 1, "gesto_para_acao": {"Foo": "bar"}}),
                encoding="utf-8",
            )
            resultado = carregar_mapeamento(caminho)
            self.assertEqual(resultado, {})


if __name__ == "__main__":
    unittest.main()
