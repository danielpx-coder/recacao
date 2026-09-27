# Danaurium Redação Studio

> Aplicativo desktop em Python e PySide6 para jornalistas, assessores de imprensa e comunicadores institucionais.  
> Desenvolvido para Windows 10 e 11 com interface 100% em Português do Brasil.

---

## 🏛 Arquitetura do Software

O sistema adota arquitetura em camadas estritamente desacopladas:

```
danaurium/
├── app.py                 # Ponto de entrada da aplicação desktop e ciclo de vida
├── config.py              # Definição de caminhos (%LOCALAPPDATA%), pastas e logging
├── security/              # Cofre seguro (Windows Credential Manager) e sanitização de logs
├── persistence/           # Banco SQLite em modo WAL, repositório tipado e backup online
├── providers/             # Adaptadores independentes para OpenAI, Anthropic, OpenRouter e Custom
├── catalog/               # Curadoria de modelos, precificação decimal precisa e modo gratuito
├── budget/                # Gestão de tetos diário/mensal e reserva de custo para concorrência
├── editorial/             # 14 produtos, regras jornalísticas, checagem de fidelidade e rádio
├── io/                    # Importadores (TXT/DOCX/PDF) e exportadores (TXT/DOCX/MD/HTML/ZIP)
└── gui/                   # Telas em PySide6, temas modernos, diálogos e threads em segundo plano
```

### Principais Decisões Arquiteturais:
1. **Zero Bloqueio de Interface:** Todas as operações de rede, importação pesada e geração utilizam `QThread` (`GenerationWorker`, `ConnectionTestWorker`, `CatalogSyncWorker`, `CompareLabWorker`) com cancelamento seguro e desacoplamento via sinais Qt.
2. **Segurança de Credenciais:** As chaves de API nunca são gravadas no SQLite, arquivos JSON, logs ou backups. No Windows, o aplicativo utiliza o **Windows Credential Manager** (via biblioteca `keyring`). Quando o cofre do sistema estiver inacessível, recua para armazenamento seguro volátil em memória durante a sessão.
3. **Proteção Contra Injeção e Alucinações:** A matéria-fonte é envelopada em tags delimitadoras e tratada estritamente como dados, instruindo o modelo a ignorar eventuais comandos contidos no texto. O sistema conta com extrator de fatos preliminares e verificação determinística de novos números, termos obrigatórios e aspas literais.
4. **Precisão Financeira:** Todos os cálculos de micro-custos por token utilizam a biblioteca `Decimal` de alta precisão do Python, evitando erros de arredondamento de ponto flutuante.

---

## 📦 Dependências e Requisitos

- **Python:** 3.10 ou 3.11 (64-bit recomendado)
- **Bibliotecas Principais:**
  - `PySide6` (Interface desktop moderna Qt6)
  - `httpx` (Cliente HTTP/SSE assíncrono e síncrono para streaming)
  - `pydantic` (Validação de estruturas e modelos de dados)
  - `keyring` (Integração com o Windows Credential Manager)
  - `python-docx` (Manipulação de arquivos do Microsoft Word)
  - `pypdf` (Extração de camada de texto de documentos PDF)
  - `pytest` (Testes automatizados unitários e de integração)
  - `pyinstaller` (Empacotamento executável para Windows)

### Instalação em Ambiente de Desenvolvimento:
```bash
pip install -r requirements.txt
```

---

## 🚀 Execução em Modo de Desenvolvimento

```bash
# Executar a aplicação desktop
python -m danaurium.app

# Executar diagnóstico do ambiente
python diagnostics.py

# Executar a suíte de testes automatizados
pytest -v
```

---

## 🛠 Compilação do Executável para Windows

Em um computador com Windows 10 ou 11 instalado:

```bash
# 1. Compilar executável portátil com PyInstaller
python build_windows.py

# O binário compilado será gerado em:
# dist\DanauriumRedacaoStudio\DanauriumRedacaoStudio.exe

# 2. (Opcional) Gerar instalador com Inno Setup
iscc installer.iss
```

---

## 📑 Produtos Editoriais Atendidos (14 Produtos)

1. **Reportagem Jornalística** (Lead, pirâmide invertida, aspas atribuídas)
2. **Release Institucional** (Gancho de imprensa, serviço e contato)
3. **Resumo Editorial / Executivo** (Síntese rápida em tópicos)
4. **5 Sugestões de Título** (Informativo, impacto social, analítico, pergunta, criativo)
5. **Subtítulo / Linha Fina** (Linha fina complementar à manchete)
6. **Spot de Rádio** (15s, 30s, 45s, 60s ou 90s, ritmo de 135 ppm, rubricas sonoras)
7. **Roteiro com Dois Locutores** (Diálogo intercalado para bancada de rádio)
8. **Chamada de WhatsApp** (Mensagem objetiva com destaques)
9. **Legenda para Instagram e Facebook** (Gancho, desenvolvimento, CTA e hashtags)
10. **Texto para LinkedIn** (Visão profissional, resultados e aprendizados)
11. **Publicação Curta** (Limite estrito de 280 caracteres)
12. **Texto para Card Gráfico** (Frase de impacto, 3 dados essenciais e rodapé)
13. **Roteiro de Vídeo Curto** (Estrutura vertical para Reels/TikTok/Shorts)
14. **HTML para WordPress** (Fragmento semântico limpo, sanitizado e sem scripts)
