# Danaurium Redação Studio — Manual do Usuário

**Versão:** 1.0.0  
**Público-Alvo:** Jornalistas, assessores de comunicação, redatores e comunicadores institucionais.  
**Sistemas Operacionais Homologados:** Windows 10 e Windows 11 (64 bits).

---

## 1. Visão Geral do Aplicativo

O **Danaurium Redação Studio** é um estúdio desktop completo desenvolvido para transformar uma pauta, release ou documento em múltiplos produtos jornalísticos com rigor factual, controle de gastos e sem dependência de hardware pesado (não requer GPU local nem instalação de modelos em disco).

### Principais Destaques:
- **14 Produtos Editoriais Integrados:** Reportagem, Release, Resumo, Títulos, Subtítulos, Spots de rádio, Roteiro com 2 locutores, WhatsApp, Redes Sociais (Instagram/Facebook/LinkedIn), Post ultracurto, Card gráfico, Vídeo curto e HTML limpo para WordPress.
- **Proteção de Fidelidade Editorial:** O texto original é tratado exclusivamente como dados e nunca como instrução. Há detecção automática de números novos, checagem de aspas literais e painel de fatos fixados.
- **Segurança de Credenciais:** As chaves de API nunca são gravadas no SQLite, logs ou arquivos de configuração; são salvas no Windows Credential Manager.
- **Modo Somente Gratuitos:** Bloqueia rigorosamente modelos pagos ou com preço desconhecido, impedindo cobranças indesejadas.
- **Orçamento Preciso:** Cálculo de custo em dólares e reais (BRL), com tetos diário, mensal e por projeto.

---

## 2. Primeiro Uso: Configurando as Conexões de IA

Ao abrir o aplicativo pela primeira vez, navegue até a aba **"🔌 Central de Conexões"**:

1. Selecione a conexão desejada:
   - **OpenAI Oficial** (`https://api.openai.com/v1`)
   - **Anthropic Claude** (`https://api.anthropic.com/v1`)
   - **OpenRouter** (`https://openrouter.ai/api/v1`)
   - **Personalizado** (qualquer servidor local ou API compatível com OpenAI Chat Completions)
2. Clique em **"Editar Conexão"**.
3. Insira sua chave de API no campo de senha seguro.
4. Clique em **"Testar Conexão"**: o aplicativo validará a autenticação, medirá a latência e informará quantos modelos estão acessíveis.
5. Clique em **"Atualizar Catálogo"** para baixar a lista de modelos com capacidades e preços atualizados.

---

## 3. Fluxo de Trabalho Passo a Passo

### Passo 1: Inserir a Matéria-Base
Na aba **"✍ Bancada de Redação"**:
- Digite um título para a matéria.
- Cole o texto da pauta ou clique em **"Importar Arquivo..."** (suporta `.txt`, `.docx` e `.pdf` com camada de texto).

### Passo 2: Extrair e Fixar Fatos (Ground Truth)
- Clique em **"Extrair Fatos da Fonte"**.
- O sistema identificará automaticamente declarações entre aspas, datas, números, porcentagens e valores monetários com a referência do parágrafo de origem.
- Você pode editar e desmarcar fatos antes de gerar. Fatos marcados como **"Fixar"** são enviados à IA como verdade absoluta inegociável.

### Passo 3: Escolher Produtos e Configurar Estilo
- Selecione os produtos desejados (ex: *Reportagem*, *Release*, *Chamada de WhatsApp*, *HTML para WordPress*).
- Selecione o perfil editorial (ex: *Econômico*, *Somente Gratuitos*, *Equilibrado*).
- Ajuste tom, público-alvo, pessoa verbal e termos obrigatórios.
- Observe o selo **"Previsão de Custo"** que indica quantas chamadas serão feitas e o custo estimado em dólares antes de iniciar.

### Passo 4: Gerar os Conteúdos
- Clique no botão **"Gerar Produtos Selecionados"**.
- O processamento ocorre em segundo plano sem travar a interface.
- O texto aparece em tempo real via streaming nas abas de resultados.
- Caso precise interromper, clique no botão vermelho **"Cancelar"**.

### Passo 5: Revisar, Comparar e Exportar
- Cada aba exibe contadores de caracteres, palavras e avisos de limites.
- **Alertas de Fidelidade:** O sistema destacará se números novos ou paráfrases entre aspas foram inseridos indevidamente.
- **Rádio:** O sistema calcula a duração estimada da locução em minutos e segundos com base em 135 palavras por minuto e pausas técnicas.
- **Reescrever Trecho:** Selecione um trecho e clique em **"Reescrever Seleção..."** para encurtar ou simplificar sem perder dados.
- **Histórico de Versões:** Alterne entre versões anteriores e use o botão **"Comparar Versões"** para visualização lado a lado das diferenças.
- **Exportação:** Exporte produtos individuais em TXT, DOCX, Markdown ou HTML limpo para WordPress, ou clique em **"Exportar Pacote ZIP..."** para salvar todos os produtos de uma vez.

---

## 4. Laboratório de Comparação de Modelos

Na aba **"🔬 Laboratório de Comparação"**:
- Permite enviar a mesma matéria para 2 ou 3 modelos diferentes (ex: GPT-4o vs Claude 3.5 Sonnet vs Llama 3.3).
- Exibe lado a lado o texto, tempo de resposta em milissegundos, tokens consumidos, custo financeiro e alertas factuais.
- Permite atribuir nota editorial de 1 a 5 estrelas para cada modelo.

---

## 5. Consumo e Orçamento

Na aba **"💰 Consumo e Orçamento"**:
- Visualize os gastos por dia, semana, mês ou histórico completo.
- Distinção transparente entre estimativa prévia, consumo informado pela API e custo calculado pelo aplicativo.
- Conversão automática para Reais (BRL) com cotação e data informadas.
- Configure tetos máximos diários e mensais em dólares. Se o teto for atingido, novas chamadas são bloqueadas para proteger seu orçamento.

---

## 6. Atalhos de Teclado Úteis

- **Ctrl+N:** Novo projeto editorial
- **Ctrl+S:** Salvar rascunho manualmente
- **Ctrl+E:** Exportar pacote ZIP
- **Ctrl+Q:** Sair do aplicativo

---

## 7. Onde ficam meus dados?

Todos os seus projetos, versões, configurações e relatórios de consumo são salvos localmente no seu computador em:
```
%LOCALAPPDATA%\DanauriumRedacaoStudio\
```
Subpastas:
- `database/`: Banco de dados SQLite (`danaurium.db`)
- `logs/`: Arquivos de registro (com higienização de chaves)
- `backups/`: Cópias de segurança do banco
- `exports/`: Pastas de exportação
- `sample_data/`: Matérias de exemplo para testes
