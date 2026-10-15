""" Utilidades gerais para o projeto. """

import ctypes
import time

import win32api
import win32gui
import win32con
import subprocess

def is_process_running(process_name: str) -> bool:
    """Verifica se um processo esta rodando. Retorna True se estiver, False caso contrario."""
    try:
        # Roda 'tasklist' e pesquisa pelo nome do processo.
        # /NH remove cabecalhos, /FI filtra pelo nome
        result = subprocess.run(
            ["tasklist", "/NH", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            check=False
        )
        # If the process name appears in the output, it is running
        if process_name.lower() in result.stdout.lower():
            return True

        return False
    except Exception:
        print(f"Erro ao verificar se o processo {process_name} esta rodando.")
        return False

def apertar_tecla(tecla:int):
    """Simula o pressionamento de uma tecla."""
    win32api.keybd_event(tecla, 0, 0, 0)  # Pressiona a tecla

def soltar_tecla(tecla:int):
    """Simula soltar uma tecla."""
    win32api.keybd_event(tecla, 0, win32con.KEYEVENTF_KEYUP, 0)

def combo_tecla(teclas: list[int]):
    """Simula um combo de teclas (ex: Win+Esc)."""
    for tecla in teclas:
        apertar_tecla(tecla)
    for tecla in reversed(teclas):
        soltar_tecla(tecla)

def get_janela_ativa() -> int:
    """Retorna o handle (HWND) da janela ativa, ou 0 se nao houver."""
    return win32gui.GetForegroundWindow()

def minimizar_janela(janela:int) -> bool:
    """Minimiza uma janela (ShowWindow(SW_MINIMIZE)).

    Guarda: se o hwnd for 0 ou invalido, nao faz nada (no-op silencioso)."""
    if janela and win32gui.IsWindow(janela):
        win32gui.ShowWindow(janela, win32con.SW_MINIMIZE)
        return True
    return False

def _esta_maximizada(janela: int) -> bool:
    """Retorna True se a janela estiver maximizada. Nunca levanta excecao."""
    try:
        if not janela or not win32gui.IsWindow(janela):
            return False
    except Exception:
        return False
    # 1) Caminho preferencial: win32gui.IsZoomed (pode nao existir em algumas builds).
    try:
        if hasattr(win32gui, "IsZoomed"):
            return bool(win32gui.IsZoomed(janela))
    except Exception:
        pass
    # 2) Fallback via ctypes user32.IsZoomed.
    try:
        return ctypes.windll.user32.IsZoomed(janela) != 0
    except Exception:
        pass
    # 3) Fallback via GetWindowPlacement (showCmd == SW_MAXIMIZE == 3).
    try:
        colocacao = win32gui.GetWindowPlacement(janela)
        return colocacao[1] == 3
    except Exception:
        return False


def maximizar_janela(janela: int) -> bool:
    """Alterna entre maximizar e restaurar a janela (toggle).

    Usa _esta_maximizada(hwnd) para decidir: se maximizada → SW_RESTORE,
    caso contrario → SW_MAXIMIZE.
    Guarda: hwnd 0 ou invalido → no-op (retorna False)."""
    if not janela or not win32gui.IsWindow(janela):
        return False
    if _esta_maximizada(janela):
        win32gui.ShowWindow(janela, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(janela, win32con.SW_MAXIMIZE)
    return True


def alternar_janela_nativa() -> bool:
    """Alterna para a proxima janela (Alt+Tab + Enter). Retorna True em sucesso."""
    try:
        apertar_tecla(win32con.VK_MENU)
        try:
            apertar_tecla(win32con.VK_TAB)
            soltar_tecla(win32con.VK_TAB)
            time.sleep(0.15)
            apertar_tecla(win32con.VK_RETURN)
            soltar_tecla(win32con.VK_RETURN)
        finally:
            soltar_tecla(win32con.VK_MENU)
        return True
    except Exception:
        return False


def bloquear_tela_nativa() -> bool:
    """Bloqueia a estacao de trabalho via LockWorkStation. Retorna True em sucesso."""
    resultado = ctypes.windll.user32.LockWorkStation()
    if not resultado:
        raise OSError("Falha ao bloquear a tela (LockWorkStation retornou 0).")
    return True


def fechar_janela(janela: int) -> bool:
    """Envia WM_CLOSE para a janela (fecha elegantemente, respeitando unsaved changes)."""
    if janela and win32gui.IsWindow(janela):
        win32gui.PostMessage(janela, win32con.WM_CLOSE, 0, 0)
        return True
    return False
