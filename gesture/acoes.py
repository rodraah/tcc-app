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
