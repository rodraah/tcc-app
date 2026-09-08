"""
Modulo de acoes: mapeia gestos da mao para comandos do Windows.

Responsabilidades:
  - Registrar acoes executaveis (decorator @registrar_acao).
  - Persistir o mapeamento gesto -> acao em JSON (mapeamento.json).
  - Garantir disparo seguro (edge-triggered + hold-to-confirm) das acoes.

Este modulo e puramente logico: NAO importa mediapipe nem opencv.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Guarda de importacao do pywin32 (espelha o padrao de carga do modelo em gestos.py)
# ---------------------------------------------------------------------------
try:
    import win32con
    import win32gui
except ImportError:
    print(
        "O modulo 'pywin32' nao esta instalado. "
        "Instale com: pip install pywin32"
    )
    sys.exit(1)

from gesture.config import config
import gesture.utils as utils

# ---------------------------------------------------------------------------
# Constantes VK de letras (A-Z) — o modulo win32con nao as define como
# constantes nomeadas; usamos os valores hex padrao do Windows SDK.
# ---------------------------------------------------------------------------
VK_A = 0x41
VK_C = 0x43
VK_D = 0x44
VK_E = 0x45
VK_I = 0x49
VK_L = 0x4C
VK_S = 0x53
VK_V = 0x56
VK_X = 0x58
VK_Y = 0x59
VK_Z = 0x5A

# ---------------------------------------------------------------------------
# 1. Registro de acoes (padrao decorator)
# ---------------------------------------------------------------------------
REGISTRO_ACOES: dict[str, Callable[[], None]] = {}


def registrar_acao(nome: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    """Decorator: registra a funcao no REGISTRO_ACOES sob `nome`."""
    def decorador(funcao: Callable[[], None]) -> Callable[[], None]:
        REGISTRO_ACOES[nome] = funcao
        return funcao
    return decorador


def listar_acoes() -> list[str]:
    """Nomes de acoes disponiveis, ordenados (para dropdown da futura GUI)."""
    return sorted(REGISTRO_ACOES)


def acao_existe(nome: str) -> bool:
    """Verifica se `nome` corresponde a uma acao registrada."""
    return nome in REGISTRO_ACOES


def executar_acao(nome: str) -> bool:
    """Executa `nome` se existir; captura excecoes (aviso PT-BR) e retorna
    False em falha. Nunca derruba o loop principal."""
    funcao = REGISTRO_ACOES.get(nome)
    if funcao is None:
        print(f"Aviso: acao desconhecida '{nome}' — nada foi executado.")
        return False
    try:
        funcao()
        return True
    except Exception as e:
        print(f"Erro ao executar a acao '{nome}': {e}")
        return False


@registrar_acao("minimizar")
def minimizar_janela_ativa() -> None:
    """Minimiza a janela ativa"""
    janela_ativa = utils.get_janela_ativa()
    utils.minimizar_janela(janela_ativa)

@registrar_acao("lupa")
def abrir_lupa() -> None:
    """Abre a Lupa do Windows via 'magnify.exe'."""

    # Se a Lupa estiver aberta, envia Win+Esc para fecha-la. Caso contrario, abre a Lupa.
    if utils.is_process_running("magnify.exe"):
        utils.combo_tecla([win32con.VK_LWIN, win32con.VK_ESCAPE])
    else:
        os.startfile("magnify.exe")

# ---------------------------------------------------------------------------
# 1.1 Controle de janelas
# ---------------------------------------------------------------------------
@registrar_acao("maximizar")
def maximizar_janela_ativa() -> None:
    """Alterna entre maximizar e restaurar a janela ativa."""
    janela_ativa = utils.get_janela_ativa()
    utils.maximizar_janela(janela_ativa)


@registrar_acao("fechar_janela")
def fechar_janela_ativa() -> None:
    """Fecha a janela ativa via WM_CLOSE."""
    janela_ativa = utils.get_janela_ativa()
    utils.fechar_janela(janela_ativa)


@registrar_acao("alternar_janela")
def alternar_janela() -> None:
    """Simula Alt+Tab para alternar entre janelas."""
    utils.combo_tecla([win32con.VK_MENU, win32con.VK_TAB])


@registrar_acao("mostrar_area_trabalho")
def mostrar_area_trabalho() -> None:
    """Simula Win+D para mostrar a area de trabalho."""
    utils.combo_tecla([win32con.VK_LWIN, VK_D])


@registrar_acao("tela_cheia")
def tela_cheia() -> None:
    """Simula F11 para entrar/sair do modo tela cheia."""
    utils.combo_tecla([win32con.VK_F11])

# ---------------------------------------------------------------------------
# 1.2 Atalhos do sistema
# ---------------------------------------------------------------------------
@registrar_acao("captura_tela")
def captura_tela() -> None:
    """Simula Win+Shift+S para abrir a ferramenta de captura."""
    utils.combo_tecla([win32con.VK_LWIN, win32con.VK_SHIFT, VK_S])


@registrar_acao("bloquear_tela")
def bloquear_tela() -> None:
    """Simula Win+L para bloquear a tela."""
    utils.combo_tecla([win32con.VK_LWIN, VK_L])


@registrar_acao("abrir_explorador")
def abrir_explorador() -> None:
    """Simula Win+E para abrir o Explorador de Arquivos."""
    utils.combo_tecla([win32con.VK_LWIN, VK_E])


@registrar_acao("abrir_configuracoes")
def abrir_configuracoes() -> None:
    """Simula Win+I para abrir Configuracoes do Windows."""
    utils.combo_tecla([win32con.VK_LWIN, VK_I])


@registrar_acao("abrir_calculadora")
def abrir_calculadora() -> None:
    """Abre a Calculadora do Windows via calc.exe."""
    os.startfile("calc.exe")


@registrar_acao("abrir_gerenciador_tarefas")
def abrir_gerenciador_tarefas() -> None:
    """Simula Ctrl+Shift+Esc para abrir o Gerenciador de Tarefas."""
    utils.combo_tecla([win32con.VK_CONTROL, win32con.VK_SHIFT, win32con.VK_ESCAPE])

# ---------------------------------------------------------------------------
# 1.3 Edicao de texto
# ---------------------------------------------------------------------------
@registrar_acao("copiar")
def copiar() -> None:
    """Simula Ctrl+C para copiar."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_C])


@registrar_acao("colar")
def colar() -> None:
    """Simula Ctrl+V para colar."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_V])


@registrar_acao("recortar")
def recortar() -> None:
    """Simula Ctrl+X para recortar."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_X])


@registrar_acao("desfazer")
def desfazer() -> None:
    """Simula Ctrl+Z para desfazer."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_Z])


@registrar_acao("refazer")
def refazer() -> None:
    """Simula Ctrl+Y para refazer."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_Y])


@registrar_acao("selecionar_tudo")
def selecionar_tudo() -> None:
    """Simula Ctrl+A para selecionar tudo."""
    utils.combo_tecla([win32con.VK_CONTROL, VK_A])

# ---------------------------------------------------------------------------
# 2. Mapeamento gesto -> acao (persistido em JSON)
# ---------------------------------------------------------------------------
def carregar_mapeamento(caminho: Path | None = None) -> dict[str, str]:
    """Le o JSON de mapeamento e devolve {gesto: acao}.

    Valida: acao desconhecida (nao esta no REGISTRO_ACOES) -> aviso PT-BR e
    ignora a entrada. JSON ausente/corrompido -> aviso PT-BR e retorna copia
    de MAPA_PADRAO. Nunca levanta excecao."""
    caminho = caminho or config.CAMINHO_MAPEAMENTO
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        print(
            f"Aviso: mapeamento ausente ou corrompido em '{caminho}'. "
            "Usando o mapeamento padrao."
        )
        return dict(config.MAPA_PADRAO)

    gesto_para_acao = dados.get("gesto_para_acao", {})
    mapa: dict[str, str] = {}
    for gesto, acao in gesto_para_acao.items():
        if acao in REGISTRO_ACOES:
            mapa[gesto] = acao
        else:
            print(
                f"Aviso: acao desconhecida '{acao}' para o gesto '{gesto}' "
                "no mapeamento — entrada ignorada."
            )
    return mapa


def salvar_mapeamento(mapa: dict[str, str], caminho: Path | None = None) -> None:
    """Grava o mapeamento em JSON com schema {'schema': 1, 'gesto_para_acao': {...}}.

    Gravacao atomica: escreve em um arquivo temporario (.part) e depois
    substitui o destino com os.replace."""
    caminho = caminho or config.CAMINHO_MAPEAMENTO
    dados = {"schema": 1, "gesto_para_acao": dict(mapa)}
    caminho_part = caminho.with_suffix(caminho.suffix + ".part")
    with open(caminho_part, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    os.replace(caminho_part, caminho)


# ---------------------------------------------------------------------------
# 3. Estado de disparo: edge-triggered + hold-to-confirm
# ---------------------------------------------------------------------------
class HoldToConfirm:
    """Maquina de estados para um unico par (gesto, acao).

    Edge-triggered + hold-to-confirm: o gesto precisa ser mantido continuamente
    por `duracao_hold` segundos para disparar, tolerando pequenas falhas de
    deteccao (ate `tolerancia_gap_frames` frames) sem resetar o timer.
    update() e chamado 1x por frame e nunca dorme (hold baseado em timestamps).
    """

    def __init__(self, nome_gesto: str, nome_acao: str,
                 duracao_hold: float = config.DURACAO_HOLD_SEGUNDOS,
                 tolerancia_gap_frames: int = config.TOLERANCIA_GAP_FRAMES) -> None:
        self.nome_gesto = nome_gesto
        self.nome_acao = nome_acao
        self.duracao_hold = duracao_hold
        self.tolerancia_gap_frames = tolerancia_gap_frames

        # Estados internos: OCIOSO (armado) <-> SEGURANDO, e OCIOSO com
        # re-arm bloqueado apos um disparo (aguardando soltura do gesto).
        self._segurando = False
        self._aguardando_soltura = False
        self._inicio_hold = 0.0
        self._gap_atual = 0

    def update(self, gesto: str | None, now: float | None = None) -> str | None:
        """Alimenta com o gesto do frame (esperado ou None).

        Retorna `nome_acao` no disparo (1x por episodio), senao None.
        `now` e injetavel para testes; por padrao usa time.monotonic()."""
        if now is None:
            now = time.monotonic()

        if self._segurando:
            if gesto == self.nome_gesto:
                # Gesto mantido: zera o gap e checa se o hold foi cumprido.
                self._gap_atual = 0
                if now - self._inicio_hold >= self.duracao_hold:
                    self._segurando = False
                    self._aguardando_soltura = True  # OCIOSO com re-arm bloqueado
                    return self.nome_acao
                return None

            # Gesto ausente ou alterado: conta como gap (flicker nao reseta).
            self._gap_atual += 1
            if self._gap_atual > self.tolerancia_gap_frames:
                # Perda sustentada: reseta e rearma.
                self._segurando = False
                self._aguardando_soltura = False
                self._gap_atual = 0
            return None

        # Estado OCIOSO.
        if self._aguardando_soltura:
            # Pos-disparo: nao rearma enquanto o gesto continuar sendo feito.
            if gesto == self.nome_gesto:
                return None
            self._aguardando_soltura = False  # desarma: novo hold permitido
            return None

        # OCIOSO armado: gesto esperado inicia o hold.
        if gesto == self.nome_gesto:
            self._segurando = True
            self._inicio_hold = now
            self._gap_atual = 0
        return None


class DisparadorAcoes:
    """Dono do estado de disparo. Instanciado 1x em gestos.py; alimentado 1x por frame."""

    def __init__(self, mapa: dict[str, str] | None = None,
                 duracao_hold: float = config.DURACAO_HOLD_SEGUNDOS,
                 tolerancia_gap_frames: int = config.TOLERANCIA_GAP_FRAMES) -> None:
        self._duracao_hold = duracao_hold
        self._tolerancia_gap_frames = tolerancia_gap_frames
        self._mapa: dict[str, str] = {}
        self._gatilhos: list[HoldToConfirm] = []
        # Constroi um HoldToConfirm por entrada do mapa (ignora acoes fora do registry).
        self.mapa = dict(config.MAPA_PADRAO) if mapa is None else mapa

    @property
    def mapa(self) -> dict[str, str]:
        return dict(self._mapa)

    @mapa.setter
    def mapa(self, novo: dict[str, str]) -> None:
        """Reconstroi os gatilhos — seam de hot-reload para a futura GUI."""
        novo_mapa: dict[str, str] = {}
        novos_gatilhos: list[HoldToConfirm] = []
        for gesto, acao in novo.items():
            if acao not in REGISTRO_ACOES:
                print(
                    f"Aviso: acao desconhecida '{acao}' para o gesto '{gesto}' "
                    "no mapa — entrada ignorada."
                )
                continue
            novo_mapa[gesto] = acao
            novos_gatilhos.append(
                HoldToConfirm(
                    gesto,
                    acao,
                    duracao_hold=self._duracao_hold,
                    tolerancia_gap_frames=self._tolerancia_gap_frames,
                )
            )
        self._mapa = novo_mapa
        self._gatilhos = novos_gatilhos

    def alimentar(self, gesto: str | None, now: float | None = None) -> str | None:
        """1x por frame. Para cada gatilho: se gesto e o dele, alimenta com
        gesto; senao None (gap). No disparo: chama executar_acao() e retorna
        o nome da acao executada; senao None."""
        for gatilho in self._gatilhos:
            entrada = gesto if gesto == gatilho.nome_gesto else None
            acao = gatilho.update(entrada, now)
            if acao is not None:
                executar_acao(acao)
                return acao
        return None
