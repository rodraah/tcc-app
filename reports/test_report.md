# Relatório de Testes Programáveis — TCC-App

## 1. Ambiente

| Item | Valor |
|---|---:|
| SO | Windows-11-10.0.26300-SP0 |
| Python | 3.13.15 |
| Commit | 0e52c14 |
| Data/hora | 2026-10-10 21:34:37 |
| Comando | `python scripts/generate_test_report.py` |

> Testes 100% programáveis: texto perfeito (sem STT), gestos sintéticos (sem câmera) e executor com mocks (sem efeito no SO).

## 2. Resultado consolidado por grupo

| Grupo | Testadas | Sucesso | Falha | Taxa |
|---|---|---|---|---:|
| Janelas | 67 | 67 | 0 | 100.00% |
| Arquivos/Notas | 124 | 115 | 9 | 92.74% |
| Navegador/YouTube | 158 | 155 | 3 | 98.10% |
| Sistema/A11y | 53 | 50 | 3 | 94.34% |
| Digitação/Atalhos | 90 | 90 | 0 | 100.00% |
| Ajuda/Controle | 18 | 16 | 2 | 88.89% |
| Config/Mapeamento | 34 | 34 | 0 | 100.00% |
| Gestos | 15 | 15 | 0 | 100.00% |
| **TOTAL** | **559** | **542** | **17** | **96.96%** |

Taxa determinística: cada falha é um defeito do parser/executor/mapeamento, não erro de reconhecimento de fala. Total: **559** casos.

## 3. Cobertura de handlers (`required <= set(ex._handlers)`)

| Métrica | Valor |
|---|---:|
| Handlers exigidos pelo roadmap | 37 |
| Handlers ausentes | nenhum |
| `required <= set(_handlers)` | OK |
| Handlers totais no Executor | 47 |
| Handlers exercitados (mock) | 47/47 |

## 4. Falhas

| Grupo | Frase/Intenção | Esperado | Obtido |
|---|---|---|---:|
| Arquivos/Notas | 'ler o ultimo arquivo' | read_last_file {} | open_last_file {} |
| Arquivos/Notas | 'revelar ultimo arquivo' | reveal_last_file {} | read_last_file {} |
| Arquivos/Notas | 'excluir ultimo arquivo' | delete_file {'confirmed': False} | read_last_file {} |
| Arquivos/Notas | 'excluir o ultimo arquivo' | delete_file {'confirmed': False} | read_last_file {} |
| Arquivos/Notas | 'deletar ultimo arquivo' | delete_file {'confirmed': False} | read_last_file {} |
| Arquivos/Notas | criar pasta novos arquivos em downloads | create_folder {'location': 'downloads', 'name': 'novos arquivos'} | repeat_last {} |
| Arquivos/Notas | criar uma pasta novos arquivos em downloads | create_folder {'location': 'downloads', 'name': 'novos arquivos'} | repeat_last {} |
| Arquivos/Notas | cria pasta novos arquivos em downloads | create_folder {'location': 'downloads', 'name': 'novos arquivos'} | repeat_last {} |
| Arquivos/Notas | cria uma pasta novos arquivos em downloads | create_folder {'location': 'downloads', 'name': 'novos arquivos'} | repeat_last {} |
| Navegador/YouTube | 'pular 10 segundos' | browser_youtube {'action': 'forward'} | browser_youtube {'action': 'rewind'} |
| Navegador/YouTube | 'pular video' | browser_youtube {'action': 'forward'} | browser_youtube {'action': 'play_pause'} |
| Navegador/YouTube | 'play video' | browser_youtube {'action': 'play_pause'} | browser_youtube {'action': 'forward'} |
| Sistema/A11y | abrir pasta area de trabalho | open_folder {'path': 'shell:Desktop'} | show_desktop {} |
| Sistema/A11y | abre pasta area de trabalho | open_folder {'path': 'shell:Desktop'} | show_desktop {} |
| Sistema/A11y | abrir a pasta area de trabalho | open_folder {'path': 'shell:Desktop'} | show_desktop {} |
| Ajuda/Controle | 'pare' | cancel {} | None (sem intent) |
| Ajuda/Controle | 'para tudo' | cancel {} | None (sem intent) |

## 5. Limitações

- Texto perfeito, sem STT (Google/Whisper/Vosk não exercitados).
- Gestos sintéticos, sem câmera e sem modelo MediaPipe `.task`.
- Executor mockado (`pyautogui`/`pywinauto`/browser/TTS) e operações de arquivo em diretório temporário; nada toca o OS real.
- Sem rede, sem áudio, sem janela real.
- Suíte pré-existente `pytest tests/ -q`: 269 passed, 3 failed, 2 skipped (falhas pré-existentes não são causadas por este script).

## 6. Rastreabilidade (RF → grupo → N casos)

| RF | Descrição | Grupo(s) | N casos |
|---|---|---|---:|
| RF01 | Compreensão do vocabulário de voz (parser) | todos os grupos | 450 |
| RF02 | Execução das ações (executor mockado) | todos os grupos | 60 |
| RF03 | Controle por gestos (geometria pura) | Gestos | 15 |
| RF04 | Configuração/mapeamento válidos | Config/Mapeamento | 34 |
| RF05 | Navegador e YouTube | Navegador/YouTube | 158 |
| RF06 | Atalhos e digitação | Digitação/Atalhos | 90 |
| RF07 | Sistema e acessibilidade | Sistema/A11y | 53 |
| RF08 | Controle de janelas | Janelas | 67 |
| RF09 | Ajuda e controle | Ajuda/Controle | 18 |
| RF10 | Arquivos e notas | Arquivos/Notas | 124 |
| RF11 | Persistência de mapeamento e tunagem de gestos | Config/Mapeamento | 34 |
