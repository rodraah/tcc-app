# App de acessibilidade que controla o Windows por voz e gestos de mão

Trabalho de Conclusão de Curso de Ciência da Computação que desenvolve um aplicativo de acessibilidade para Windows, permitindo controlar o computador por comandos de voz e gestos de mão capturados pela webcam. Combina reconhecimento de gestos (MediaPipe com regras geométricas) com um assistente de voz que interpreta intenções e executa ações, em uma interface gráfica simples com configurações, log de ações e atalho na bandeja do sistema.

## Funcionalidades

- Reconhecimento de gestos por câmera (MediaPipe com fallback para regras geométricas sobre os landmarks da mão) que executam ações no Windows, como controle de janelas, atalhos do sistema e edição de texto.
- Assistente de voz: reconhece a fala, interpreta intenções e executa ações, como abrir aplicativos, digitar texto, controlar janelas e navegar no navegador.
- Interface gráfica com prévia da câmera, status de gesto e voz, transcrição da fala, mapeamento gesto para ação configurável e log de ações.
- Assistente de configuração na primeira execução (câmera, microfone, pausa de voz e atalho).
- Ícone na bandeja do sistema e atalho global (F9) para mostrar ou ocultar a janela.

## Pré-requisitos

- Windows 10/11
- Webcam e microfone

## Uso (plug and play)

1. Baixe o zip da pasta `dist/TCC-App` (gerada pelo build, ou release do projeto).
2. Extraia em qualquer pasta.
3. Abra `TCC-App.exe`.

Na primeira execução, o assistente escolhe câmera, microfone e atalho. O pacote já inclui MediaPipe, Vosk e Chromium (Playwright) para comandos de voz no navegador. Whisper (se usado) baixa o modelo na primeira vez (precisa de internet).

## Build do executável (desenvolvedor)

Requer **Python 3.10–3.12** (3.14 quebra o PyAudio no Windows).

```powershell
.\scripts\build_exe.ps1
```

Gera `dist\TCC-App\` (exe + modelos + config). Zippe essa pasta para distribuir.

## Desenvolvimento (código-fonte)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/download_models.py
python scripts/download_vosk_model.py
python main.py
```

## Estrutura do projeto

- `gesture/` — módulo de reconhecimento de gestos e execução de ações no Windows.
- `voice/` — módulo de assistente de voz (reconhecimento de fala, intenções e ações).
- `gui/` — interface gráfica (CustomTkinter), bandeja do sistema e atalho global.
- `models/` — modelos do MediaPipe baixados pelo script de instalação.
- `config/` — configurações persistidas do aplicativo.
- `scripts/` — utilitários, como o download dos modelos.
- `tests/` — suíte de testes automatizados.

## Nota acadêmica

Este projeto foi desenvolvido para fins acadêmicos, como Trabalho de Conclusão de Curso de Ciência da Computação.