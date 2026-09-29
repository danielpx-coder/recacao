# RD5 PageStudio 2.0

> Editor de páginas HTML com a cara do antigo **Microsoft FrontPage** (Office 2000/XP),
> em Python + Tkinter, com interface 100% em Português do Brasil.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 📄 📂 💾 │ ✂ ⧉ 📋 │ ↶ ↷ │ 🔗 🖼 ▦ ━ │ 🔍 │ 🌐            <- barra Padrão │
│ [Estilo ▼] N I S A │ Esq Cen Dir │ •≡ │ T- T+ │ ✓     <- barra Formatação │
├───────────────┬──────────────────────────────────────────────────────────┤
│ Lista de      │  pagina.htm *    C:\site                                 │
│ Pastas        ├──────────────────────────────────────────────────────────┤
│ 📁 site       │                                                          │
│  📄 index.htm │        Modo Design (WYSIWYG simplificado)                │
│  📄 sobre.htm │                                                          │
│  📁 imagens   │                                                          │
├───────────────┴──────────────────────────────────────────────────────────┤
│ ✎ Design   ‹/› Código   🔍 Visualizar                              ↻     │
├──────────────────────────────────────────────────────────────────────────┤
│ Pronto                     312 palavra(s)  Lin 4, Col 12  UTF-8  Design  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Como abrir (Windows)

Dê **dois cliques** em:

```
iniciar_pagestudio.bat
```

O script faz tudo sozinho, na ordem:

| Passo | O que ele faz |
|-------|---------------|
| 1 | Localiza um Python 3.10+ (usa `py`, `python3` ou `python`) |
| 2 | Cria o ambiente virtual em `.venv\` (só na primeira vez) |
| 3 | **Ativa** o ambiente virtual e instala o `requirements.txt` (só quando falta algo) |
| 4 | Abre o RD5 PageStudio |

Opções de linha de comando:

```bat
iniciar_pagestudio.bat                abre o editor
iniciar_pagestudio.bat pagina.htm     abre o editor já com uma página
iniciar_pagestudio.bat --dev          abre e mantém o console aberto (para ver erros)
iniciar_pagestudio.bat --shell        só cria/ativa o venv e para (prompt pronto)
iniciar_pagestudio.bat --reinstall    força a reinstalação das dependências
iniciar_pagestudio.bat --sem-venv     usa o Python do sistema, sem venv
```

> **Sem internet?** Não tem problema. O `tkinterweb` é opcional: sem ele o
> editor funciona normalmente e a visualização abre no navegador (tecla **F12**).
> O script avisa e continua.

### Linux / macOS

```bash
./iniciar_pagestudio.sh          # mesmo comportamento do .bat
```
(Em Linux o Tkinter vem do sistema: `sudo apt install python3-tk`.)

### Sem script, na mão

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python rd5_pagestudio.py [arquivo.htm]
```

---

## ✨ O que mudou da versão 1.0 para a 2.0

### 1. Tabelas, formulários e scripts não são mais destruídos
Era o defeito mais grave do 1.0: abrir uma página com `<table>`, `<form>`,
`<script>`, `<style>`, `<svg>`, `<iframe>` etc. e digitar uma vírgula no modo
Design apagava tudo isso ao salvar.

Agora esses elementos viram **blocos protegidos**: no modo Design aparecem como
uma linha cinza (`@@RD5PB0@@`, exibida como *conteúdo protegido*) e, ao gravar,
o HTML original é devolvido **byte por byte**. Apagar a linha cinza no Design
remove o bloco — é a única forma de ele sumir.

### 2. Localizar e substituir de verdade
`Ctrl+F` / `Ctrl+H` / `F3` / `Shift+F3`, com contador de ocorrências,
diferenciação de maiúsculas, **palavra inteira** e **expressão regular**,
substituição uma a uma ou todas de uma vez, no modo Design *e* no modo Código.

### 3. Desfazer/refazer confiável no modo Design
O `Ctrl+Z` do Tk só desfazia digitação — formatar em negrito e desfazer não
fazia nada. O histórico agora guarda fotos do documento (texto **e** tags),
limitadas a 60 estados.

### 4. Codificação de arquivo preservada
Lê respeitando BOM e o `charset` declarado (`utf-8`, `cp1252`, `latin-1`…) e
grava **na mesma codificação**. Se o texto não couber nela, promove para UTF-8
e corrige o `<meta charset>` — nunca perde caractere. A codificação aparece na
barra de status.

### 5. Arquivo, sessão e segurança
- **Documentos recentes** no menu Arquivo;
- **Recuperação automática**: enquanto houver alteração não gravada, uma cópia
  fica em `%LOCALAPPDATA%\RD5PageStudio\autosave` e é oferecida na próxima
  abertura (útil depois de travamento);
- **Aviso de edição externa**: se outro programa gravar o arquivo, o editor
  pergunta se você quer recarregar;
- Geometria da janela, pasta do site e preferências são lembrados.

### 6. Lista de Pastas melhorada
Filtro por nome (busca recursiva), botão de atualizar (F5) e menu de contexto:
abrir, abrir no sistema, nova página, nova pasta, renomear, excluir.

### 7. Mais recursos de edição
Inserir **tabela**, comentário HTML, data de hoje, caracteres especiais
(espaço fixo, travessão, aspas curvas, €, ©, °…), link de e-mail;
**Propriedades da página** completas (título, descrição, palavras-chave, idioma
e cores de fundo/texto/link); **Verificar HTML** (DOCTYPE, charset, título,
tags abertas/fechadas, atributos sem aspas); **contar palavras**; tamanho do
texto do modo Design ajustável (T-/T+); Tab/Shift+Tab recuam no modo Código.

---

## 📁 Organização do código

```
pagestudio/
├── rd5_pagestudio.py        ponto de entrada (python rd5_pagestudio.py)
├── requirements.txt         dependências (todas opcionais)
├── iniciar_pagestudio.bat   cria/ativa o venv e abre o app (Windows)
├── iniciar_pagestudio.sh    idem para Linux/macOS
├── ps_core/                 núcleo SEM interface gráfica (100% testável)
│   ├── consts.py            identidade, cores, fontes, gabarito, estilos
│   ├── design.py            HTML ⇄ Design, blocos protegidos, formatação inline
│   ├── htmlutil.py          leitura/gravacao, charset, metadados, validação
│   ├── history.py           desfazer/refazer por fotos do documento
│   ├── search.py            motor de localizar/substituir
│   └── config.py            preferências, recentes e autosave
├── ps_gui/                  camada fina de Tkinter
│   ├── app.py               janela, menus, barras, modos, arquivos
│   ├── panels.py            Lista de Pastas e painel Localizar/Substituir
│   ├── dialogs.py           Propriedades, Tabela, Hyperlink, Relatórios
│   └── widgets.py           dicas (tooltips)
└── tests/                   112 testes (pytest) + documento de teste PlainDoc
```

A separação existe por um motivo prático: tudo o que o editor **faz** (analisar
HTML, converter Design ⇄ HTML, preservar blocos, buscar, substituir, codificar
arquivos, manter histórico) está em `ps_core` e roda em testes automatizados sem
precisar de janela nem de display.

---

## 🧪 Testes

Da raiz do repositório:

```bash
python -m pytest pagestudio/tests -v
```

- `tests/plaindoc.py` é uma reimplementação fiel da API de `tkinter.Text`
  (índices `linha.coluna`, `dump`, faixas de tags, `search`), o que permite
  testar a conversão e o histórico de verdade, sem Tkinter;
- `tests/test_gui.py` abre o aplicativo de verdade e é **ignorado**
  automaticamente quando o ambiente não tem Tkinter/display (é o caso de
  servidores de integração contínua).

Cobertura atual: extração e fidelidade de blocos protegidos, ciclo
HTML → Design → HTML idempotente, `<pre>`, listas, alinhamento, cores,
codificações (UTF-8/BOM/cp1252/latin-1), metadados, tabelas, validação de HTML,
busca (regex/palavra inteira/volta ao início), substituição em massa, histórico
com limites, preferências e autosave.

---

## 📄 Formatos e limitações conhecidas

- O modo Design é **baseado em linhas**: cada parágrafo, título, item de lista,
  linha horizontal ou bloco protegido ocupa uma linha. O que não cabe nesse
  modelo (tabela, formulário, script…) é protegido, não editado.
- A formatação gerada segue o estilo Office 2000: `<b>`, `<i>`, `<u>`,
  `<font color/size>`, `style="text-align: …"` e `&nbsp;` para preservar
  espaços — exatamente para que o resultado continue abrindo igual em
  navegadores antigos e novos.
- A aba **Visualizar** embutida depende do `tkinterweb` (opcional). Sem ele,
  use **F12** para abrir no navegador.

## ⌨️ Atalhos

| Tecla | Ação | Tecla | Ação |
|-------|------|-------|------|
| `Ctrl+N` | Nova página | `Ctrl+1/2/3` | Design / Código / Visualizar |
| `Ctrl+O` | Abrir | `Ctrl+F` | Localizar |
| `Ctrl+S` | Salvar | `Ctrl+H` | Substituir |
| `Ctrl+Z` / `Ctrl+Y` | Desfazer / Refazer | `F3` / `Shift+F3` | Próxima / anterior |
| `Ctrl+B` `Ctrl+I` `Ctrl+U` | Negrito, itálico, sublinhado | `F12` | Navegador |
| `Ctrl+K` | Hyperlink | `F5` | Atualizar |
| `Ctrl+A` | Selecionar tudo | `Esc` | Fechar a busca |
