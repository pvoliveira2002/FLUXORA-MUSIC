# Fluxora 3.0 — versão PySide6 para VS Code

Uma **nova interface executável** para o Fluxora, com organização inspirada no conceito visual aprovado: tema preto/verde-limão, barra lateral, Downloads, Prévia, Playlist e Biblioteca.

## Antes de começar

O Fluxora 2.1 usa **Tkinter**; esta versão 3.0 usa **PySide6**. **Não substitua `modern_ui.py` e `app.py` na pasta original.** Trabalhe numa **pasta separada**, para manter a versão anterior funcionando até validar a migração.

## Como executar no Windows

1. Extraia todo o ZIP numa pasta, por exemplo `Documentos\Fluxora 3.0`.
2. Abra essa pasta no **VS Code**: `Arquivo > Abrir Pasta`.
3. Instale **Python 3.14** e **Node.js** (o Node.js melhora a compatibilidade do yt-dlp com fontes que usam desafios JS).
4. Execute `instalar.bat` **uma vez** — instala PySide6, yt-dlp e imageio-ffmpeg numa `.venv` própria.
5. Execute `iniciar_fluxora.bat` ou selecione `.venv\Scripts\python.exe` como interpretador no VS Code e pressione **F5**. O inicializador normal abre o aplicativo sem manter uma janela de CMD.

Se precisar enxergar mensagens de diagnóstico, use `iniciar_fluxora_debug.bat`.

Você também pode executar pelo terminal integrado do VS Code:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Organização do projeto

- `main.py`: inicialização da interface Qt.
- `fluxora/ui.py`: telas, componentes visuais, navegação, diálogos, cards, biblioteca.
- `fluxora/theme.py`: cores e tema Qt (QSS).
- `fluxora/icons.py`: ícones SVG desenhados no projeto.
- `fluxora/engine.py`: análise/download/playlist/FFmpeg integrados ao Qt, com tarefas em segundo plano.
- `fluxora/storage.py`: configurações e histórico local JSON.
- `assets/`: logo e ícone originais do usuário.
- `REFERENCIA_VISUAL.png`: mockup de referência aprovado — **não** é captura de tela do programa em execução.

## O que está integrado

- Downloads de vídeo (MP4) e áudio (MP3) com yt-dlp e FFmpeg.
- Qualidade de vídeo/áudio, pasta de destino, cookies do navegador ou arquivo cookies.txt.
- Detecção e análise de URL de vídeo/playlist com yt-dlp.
- Seleção de itens de playlists com miniaturas carregadas apenas quando ficam visíveis, limitada ao número configurado para analisar por página (padrão 100; máximo 500).
- Progresso, velocidade, estimativa, cancelamento, miniaturas de mídia quando disponíveis.
- Fila com até três músicas simultâneas; playlists criam uma tarefa individual por faixa.
- Histórico da sessão com filtros para fila, downloads ativos, concluídos, cancelados e falhas, além de remoção manual dos cartões.
- Biblioteca persistente e responsiva de arquivos finalizados, com pesquisa, filtros e abertura do arquivo ou da pasta.
- Ícone da bandeja pelo Qt (quando disponível).
- Migração automática, no primeiro uso, do navegador e cookies.txt salvos pelo Fluxora 2.x.

## Limites desta primeira migração

- São executados no máximo três downloads simultâneos; os demais aguardam na fila.
- **Pausar/retomar** downloads ainda não foi integrado; o botão está indisponível.
- Conversor autônomo, gravador de tela/áudio e captura de dispositivo **não estão implementados**.
- A biblioteca não importa o histórico visual temporário do Tkinter, pois ele não continha caminhos persistentes confiáveis.
- Uma pasta pode conter vídeos antigos que não apareçam automaticamente na biblioteca; a biblioteca grava os arquivos identificados ao concluir um download feito nesta versão.
- Alguns sites exigem autenticação e podem deixar de funcionar devido a alterações externas. Não há garantia de que todo link seja compatível.
- O layout segue o conceito aprovado mas não corresponde **pixel a pixel** à imagem ilustrativa; depende de fonte, resolução e escala do Windows.

## Testes e segurança

Os testes automatizados cobrem armazenamento, migração de preferências, opções MP4/MP3, detecção de playlists e navegação/componentes das quatro telas. Downloads reais dependem da fonte, da rede e da validade da sessão do usuário e devem ser confirmados com mídia autorizada.

Use URLs de mídia que você tenha permissão para baixar. Não coloque arquivos cookies.txt no GitHub — são dados privados de sessão.

## Testes locais no VS Code

Depois de instalar as dependências, rode `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` para testar o projeto sem baixar mídia. Depois faça downloads autorizados MP4 e MP3.
