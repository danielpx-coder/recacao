"""Definição detalhada dos 14 produtos editoriais, limites, formatos e regras de estilo."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EditorialProductDefinition:
    """Metadados e diretrizes editoriais para cada produto suportado."""
    id: str
    name: str
    category: str  # 'Jornalismo', 'Institucional', 'Rádio & Áudio', 'Redes Sociais', 'Web & Multimídia'
    description: str
    default_char_limit: int
    char_limit_presets: List[int] = field(default_factory=lambda: [1400, 1800, 2000, 2500])
    guidelines_prompt: str = ""
    output_format: str = "text"  # 'text', 'html', 'radio_script', 'video_script'


EDITORIAL_PRODUCTS: Dict[str, EditorialProductDefinition] = {
    "reportagem": EditorialProductDefinition(
        id="reportagem",
        name="Reportagem Jornalística",
        category="Jornalismo",
        description="Texto jornalístico completo com lead, pirâmide invertida, contextualização e aspas atribuídas.",
        default_char_limit=2000,
        guidelines_prompt=(
            "Estruture como reportagem jornalística clássica no padrão brasileiro. "
            "1. Lead claro no primeiro parágrafo (o que, quem, quando, onde, como e por quê). "
            "2. Ordem decrescente de relevância (pirâmide invertida). "
            "3. Parágrafos médios de 2 a 4 linhas, ordem direta (sujeito-verbo-objeto). "
            "4. Citações literais estritamente entre aspas duplas e atribuídas com nome e cargo. "
            "5. Paráfrases sem aspas. "
            "6. Tom neutro, rigor factual, sem adjetivação desnecessária ou juízo de valor."
        ),
        output_format="text",
    ),
    "release": EditorialProductDefinition(
        id="release",
        name="Release Institucional",
        category="Institucional",
        description="Comunicado de imprensa com gancho noticioso, citação oficial e dados para contato.",
        default_char_limit=1800,
        guidelines_prompt=(
            "Estruture como release de assessoria de comunicação para envio a veículos de imprensa. "
            "1. Título direto e informativo no topo. "
            "2. Localidade e data na abertura (ex: BRASÍLIA —). "
            "3. Gancho institucional no primeiro parágrafo com impacto para a sociedade. "
            "4. Declaração oficial de porta-voz institucional (entre aspas). "
            "5. Seção final de 'Serviço' ou 'Mais Informações' com contatos da assessoria."
        ),
        output_format="text",
    ),
    "resumo": EditorialProductDefinition(
        id="resumo",
        name="Resumo Editorial / Executivo",
        category="Jornalismo",
        description="Síntese rápida dos pontos principais para leitura dinâmica e briefings.",
        default_char_limit=800,
        char_limit_presets=[400, 600, 800, 1200],
        guidelines_prompt=(
            "Elabore uma síntese executiva direta e analítica. "
            "1. Parágrafo introdutório de 2 linhas resumindo o fato central. "
            "2. Lista de 3 a 5 pontos-chave em tópicos destacados. "
            "3. Conclusão ou desdobramento futuro em 1 frase."
        ),
        output_format="text",
    ),
    "cinco_titulos": EditorialProductDefinition(
        id="cinco_titulos",
        name="5 Sugestões de Título",
        category="Jornalismo",
        description="Cinco abordagens distintas de manchete para o mesmo fato.",
        default_char_limit=500,
        char_limit_presets=[300, 500, 800],
        guidelines_prompt=(
            "Apresente exatamente 5 opções de títulos jornalísticos numerados, explorando ângulos diferentes: "
            "1. Informativo Direto (foco no fato principal com verbo de ação). "
            "2. Impacto Social (foco no benefício ou consequência para as pessoas). "
            "3. Analítico / Institucional (foco no contexto e abrangência). "
            "4. Pergunta Instigante (despertando interesse sem sensacionalismo). "
            "5. Criativo / Engajador (adequado para redes ou destaques de capa)."
        ),
        output_format="text",
    ),
    "subtitulo": EditorialProductDefinition(
        id="subtitulo",
        name="Subtítulo / Linha Fina",
        category="Jornalismo",
        description="Linha fina complementar à manchete, detalhando o fato sem repetir palavras do título.",
        default_char_limit=250,
        char_limit_presets=[150, 250, 400],
        guidelines_prompt=(
            "Escreva 3 alternativas de linha fina (subtítulo) de 1 a 2 frases cada. "
            "Devem enriquecer o fato com dados essenciais ou números expressivos, sem redundâncias."
        ),
        output_format="text",
    ),
    "spot_radio": EditorialProductDefinition(
        id="spot_radio",
        name="Spot de Rádio (Áudio)",
        category="Rádio & Áudio",
        description="Texto para locução radiofônica com rubricas de tempo, pausas, efeitos sonoros e ritmo.",
        default_char_limit=800,
        char_limit_presets=[200, 400, 600, 800],
        guidelines_prompt=(
            "Escreva um spot radiofônico dinâmico e sonoro. "
            "1. Inclua indicações técnicas em colchetes maiúsculos, como [TRILHA SOBE E VAI PARA BG], [PAUSA 1s], [LOCUTOR EM TOM VIBRANTE]. "
            "2. Use linguagem falada, números por extenso para facilitar leitura, frases curtas e ritmo fluido. "
            "3. Encerramento com assinatura institucional sonora clara. "
            "4. Inclua aviso de duração estimada ao final."
        ),
        output_format="radio_script",
    ),
    "roteiro_dois_locutores": EditorialProductDefinition(
        id="roteiro_dois_locutores",
        name="Roteiro com Dois Locutores",
        category="Rádio & Áudio",
        description="Roteiro de diálogo radiofônico dinâmico entre LOCUTOR 1 e LOCUTOR 2.",
        default_char_limit=1400,
        char_limit_presets=[800, 1200, 1600, 2000],
        guidelines_prompt=(
            "Crie um diálogo radiofônico intercalado entre dois apresentadores (LOCUTOR 1 e LOCUTOR 2). "
            "1. O diálogo deve ser natural, conversacional e informativo. "
            "2. Um locutor complementa os dados do outro sem repetição. "
            "3. Inclua rubricas técnicas [TRILHA DE ABERTURA], [VINHETA], [PAUSA 1s]. "
            "4. Números e siglas explicados por extenso na fala."
        ),
        output_format="radio_script",
    ),
    "whatsapp": EditorialProductDefinition(
        id="whatsapp",
        name="Chamada de WhatsApp",
        category="Redes Sociais",
        description="Mensagem objetiva para listas de transmissão, comunidades e canais do WhatsApp.",
        default_char_limit=700,
        char_limit_presets=[400, 700, 1000],
        guidelines_prompt=(
            "Formate para aplicativo de mensagens instantâneas (WhatsApp / Telegram). "
            "1. Título em *negrito* chamativo no início com 1 emoji pertinente. "
            "2. Parágrafos breves de no máximo 2 linhas. "
            "3. Destaque dos pontos essenciais com marcadores em bullet points (* ou -). "
            "4. Chamada para ação final (CTA) clara convidando a ler a matéria ou compartilhar."
        ),
        output_format="text",
    ),
    "instagram_facebook": EditorialProductDefinition(
        id="instagram_facebook",
        name="Legenda para Instagram e Facebook",
        category="Redes Sociais",
        description="Texto para feed com gancho forte na primeira linha, quebras de linha e hashtags.",
        default_char_limit=1200,
        char_limit_presets=[800, 1200, 1600, 2200],
        guidelines_prompt=(
            "Escreva a legenda no formato ideal para Instagram e Facebook. "
            "1. Primeira frase imperativa ou provocativa antes do 'ver mais'. "
            "2. Texto estruturado com espaçamento duplo entre parágrafos curtos. "
            "3. Tom engajador e conversacional, mantendo o rigor factual. "
            "4. Pergunta no final estimulando comentários da comunidade. "
            "5. Bloco final de 4 a 6 hashtags estratégicas e específicas."
        ),
        output_format="text",
    ),
    "linkedin": EditorialProductDefinition(
        id="linkedin",
        name="Texto para LinkedIn",
        category="Redes Sociais",
        description="Publicação profissional focada em impacto, gestão, políticas públicas e aprendizados.",
        default_char_limit=1500,
        char_limit_presets=[1000, 1500, 2000, 2500],
        guidelines_prompt=(
            "Crie um artigo/post para o LinkedIn profissional. "
            "1. Gancho inicial sem jargões vazios, destacando o impacto prático. "
            "2. Desenvolvimento com foco em liderança, resultados institucionais ou inovação. "
            "3. Parágrafos espaçados de 1 a 2 frases para facilitar leitura em telas móveis. "
            "4. Pergunta final convidando conexões a opinarem."
        ),
        output_format="text",
    ),
    "publicacao_curta": EditorialProductDefinition(
        id="publicacao_curta",
        name="Publicação Curta (Bluesky / X / Threads)",
        category="Redes Sociais",
        description="Post ultracurto com limite estrito de caracteres (máx. 280 caracteres).",
        default_char_limit=280,
        char_limit_presets=[240, 280, 500],
        guidelines_prompt=(
            "Escreva uma postagem ultra-concisa de no máximo 280 caracteres no total. "
            "Deve resumir o acontecimento principal com precisão absoluta e convidar ao clique. "
            "Nunca ultrapasse o limite de caracteres sob nenhuma circunstância."
        ),
        output_format="text",
    ),
    "texto_card": EditorialProductDefinition(
        id="texto_card",
        name="Texto para Card Gráfico",
        category="Web & Multimídia",
        description="Conteúdo sintetizado para peça visual: título de destaque, 3 bullets e rodapé.",
        default_char_limit=450,
        char_limit_presets=[300, 450, 600],
        guidelines_prompt=(
            "Estruture o texto dividido para design gráfico: "
            "[CHAMADA DE DESTAQUE]: Frase de impacto curta (máx. 7 palavras). "
            "[DADOS ESSENCIAIS]: 3 tópicos com no máximo 12 palavras cada. "
            "[FONTE / RODAPÉ]: Assinatura institucional concisa."
        ),
        output_format="text",
    ),
    "roteiro_video_curto": EditorialProductDefinition(
        id="roteiro_video_curto",
        name="Roteiro de Vídeo Curto (Reels / Shorts)",
        category="Web & Multimídia",
        description="Roteiro de 30 a 60 segundos com colunas de Imagem/Cena, Fala do Apresentador e Letreiros.",
        default_char_limit=1000,
        char_limit_presets=[600, 1000, 1400],
        guidelines_prompt=(
            "Crie um roteiro de vídeo curto vertical (30 a 60 segundos). "
            "Estruture cena a cena no formato: "
            "Cena 1 (0-3s): [VÍDEO / VISUAL]: ... | [FALA / ÁUDIO]: ... | [TEXTO NA TELA]: ... "
            "Cena 2 (3-15s): [VÍDEO / VISUAL]: ... | [FALA / ÁUDIO]: ... | [TEXTO NA TELA]: ... "
            "Cena 3 (15-30s): [VÍDEO / VISUAL]: ... | [FALA / ÁUDIO]: ... | [TEXTO NA TELA]: ... "
            "Cena 4 (Encerramento): CTA e logo institucional."
        ),
        output_format="video_script",
    ),
    "html_wordpress": EditorialProductDefinition(
        id="html_wordpress",
        name="HTML para WordPress",
        category="Web & Multimídia",
        description="Fragmento de código HTML semântico, limpo e sanitizado, pronto para colar no Gutenberg ou Clássico.",
        default_char_limit=2200,
        char_limit_presets=[1400, 1800, 2200, 3000],
        guidelines_prompt=(
            "Produza apenas o fragmento HTML interno semântico (SEM <html>, <head> ou <body>). "
            "Use apenas tags padrão do WordPress: <h2>, <p>, <blockquote>, <ul>, <li>, <strong>, <em>. "
            "Não adicione atributos style inline, scripts ou fontes externas. "
            "Formate aspas em blocos <blockquote> com classe 'wp-block-quote'."
        ),
        output_format="html",
    ),
}
