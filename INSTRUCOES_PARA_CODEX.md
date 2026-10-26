# Briefing para continuar o Fluxora no VS Code / Codex

Use este arquivo ao pedir alterações à IA de programação.

## Objetivo
Refinar o Fluxora 3.0 em PySide6 para seguir com fidelidade a imagem
`REFERENCIA_VISUAL.png` (quatro telas: Downloads, Prévia, Playlist e Biblioteca),
sem perder o funcionamento real do yt-dlp/FFmpeg existente em `fluxora/engine.py`.

## Arquitetura
- `fluxora/ui.py`: interface e eventos Qt
- `fluxora/theme.py`: cores, fontes, QSS
- `fluxora/icons.py`: ícones SVG
- `fluxora/engine.py`: extração, downloads, progressos e playlists
- `fluxora/storage.py`: preferências e histórico
- `main.py`: inicialização do app

## Restrições importantes
- NÃO substituir o novo visual por Tkinter nem migrar para Electron sem pedir.
- NÃO refazer o motor de downloads que já funciona para mudar apenas a aparência.
- NÃO fazer operações de rede dentro da thread principal do Qt.
- Atualizações de interface devem chegar por signals de workers (QThread).
- Proteger a UI em caso de URL inválida, playlist vazia, timeout e falha no FFmpeg.
- Botões ainda não funcionais devem ser indicados como em desenvolvimento.
- Nunca simular downloads reais nem informar que uma função funciona se não foi testada.
- Não alterar a identidade: tema escuro + verde neon, logo original.

## Próximas melhorias desejadas
1. Polimento visual milimétrico, comparando com `REFERENCIA_VISUAL.png`.
2. Testes reais de MP4 e MP3 no Windows, com mensagens de erros claras.
3. Testes de playlist com seleção parcial, navegação e limites.
4. Melhorar ícones, espaçamentos, feedback ao passar mouse e adaptação ao DPI.
5. Futuramente: conversor e gravadores — implementar de verdade antes de habilitar.

## Primeiro pedido recomendado ao Codex
"Leia o projeto Fluxora 3.0 e a imagem REFERENCIA_VISUAL.png. Execute testes e
compare o visual das quatro telas com o conceito, corrija eventuais erros
sem mexer desnecessariamente em engine.py, e entregue um relatório curto
com itens testados, pontos que faltam e alterações realizadas."
