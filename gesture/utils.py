""" Utilidades gerais para o projeto. """

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
