"""Regras editoriais centrais, prompts do sistema e orquestração de instruções jornalísticas."""

from typing import Any, Dict, List, Optional
from danaurium.editorial.products import EDITORIAL_PRODUCTS, EditorialProductDefinition
from danaurium.editorial.fidelity import build_safe_prompt_context


def get_base_system_prompt() -> str:
    """Prompt de sistema mestre que define a postura profissional de jornalista sênior."""
    return (
        "Você é um jornalista e editor de comunicação institucional altamente experiente no Brasil. "
        "Você domina o padrão culto da língua portuguesa brasileira (acordo ortográfico vigente), "
        "com texto claro, sóbrio, objetivo e sem rodeios. "
        "Diretrizes fundamentais:\n"
        "1. Ordem direta prioritária (Sujeito - Verbo - Complemento).\n"
        "2. Evite adjetivação vazia (ex: 'importante marco', 'fundamental divisor de águas', 'revolucionário'). "
        "Deixe os fatos demonstrarem a relevância.\n"
        "3. Não use chavões ou linguagem empolada. Prefira verbos ativos e frases de até 25 palavras.\n"
        "4. Fidelidade total ao texto de entrada: nunca invente nomes, locais, números, cargos ou falas.\n"
        "5. Citações entre aspas devem ser estritamente literais da fonte. Se for paráfrase, escreva sem aspas.\n"
        "6. Em caso de dados ausentes, aponte a lacuna claramente em vez de tentar adivinhar.\n"
        "7. Respeite com exatidão o formato e o limite de caracteres solicitado."
    )


def build_generation_prompts(
    product_id: str,
    project_data: Dict[str, Any],
    custom_instruction: Optional[str] = None,
) -> Dict[str, str]:
    """Monta o par de prompts (sistema e usuário) com todas as variáveis contextuais do projeto."""
    product_def = EDITORIAL_PRODUCTS.get(product_id)
    if not product_def:
        raise ValueError(f"Produto editorial '{product_id}' desconhecido.")

    system_prompt = get_base_system_prompt()

    # Extrair parâmetros do projeto
    raw_source = project_data.get("raw_text", "")
    pinned_facts = project_data.get("extracted_facts", [])
    tone = project_data.get("tone", "Equilibrado e Jornalístico")
    audience = project_data.get("audience", "Público Geral")
    purpose = project_data.get("purpose", "Informar com clareza")
    grammatical_person = project_data.get("grammatical_person", "3ª pessoa")
    institutional_signature = project_data.get("institutional_signature", "").strip()
    mandatory_words = project_data.get("mandatory_words", "").strip()
    forbidden_expressions = project_data.get("forbidden_expressions", "").strip()
    char_limit = project_data.get("char_limit_preset", product_def.default_char_limit)

    # Montar corpo da instrução
    user_prompt_parts = []
    user_prompt_parts.append(f"TAREFA EDITORIAL: Gerar o produto '{product_def.name}'.")
    user_prompt_parts.append(f"DIRETRIZES DO PRODUTO:\n{product_def.guidelines_prompt}")
    user_prompt_parts.append("\nPARÂMETROS EDITORIAIS ESPECÍFICOS:")
    user_prompt_parts.append(f"- Tom da narrativa: {tone}")
    user_prompt_parts.append(f"- Público-alvo: {audience}")
    user_prompt_parts.append(f"- Finalidade: {purpose}")
    user_prompt_parts.append(f"- Pessoa verbal: {grammatical_person}")
    user_prompt_parts.append(f"- Limite de caracteres desejado: aproximadamente {char_limit} caracteres (não corte frases no meio; encerre com sentido completo).")

    if institutional_signature:
        user_prompt_parts.append(f"- Assinatura institucional obrigatória ao final: {institutional_signature}")
    if mandatory_words:
        user_prompt_parts.append(f"- Palavras ou termos obrigatórios que DEVEM constar no texto: {mandatory_words}")
    if forbidden_expressions:
        user_prompt_parts.append(f"- Expressões ou termos PROIBIDOS que NÃO podem aparecer: {forbidden_expressions}")

    if custom_instruction:
        user_prompt_parts.append(f"\nINSTRUÇÃO ADICIONAL DO EDITOR:\n{custom_instruction.strip()}")

    # Adicionar o contêiner protegido com o texto-base e fatos fixados
    safe_context = build_safe_prompt_context(raw_source, pinned_facts)
    user_prompt_parts.append(f"\n{safe_context}")

    user_prompt_parts.append("\nResponda diretamente com o produto final pronto para publicação:")

    return {
        "system_prompt": system_prompt,
        "user_prompt": "\n".join(user_prompt_parts),
    }
