"""Biblioteca de instruções e prompts editoriais reutilizáveis, versionados e editáveis."""

from typing import Dict, List, Any
from danaurium.persistence.repository import Repository, repo

DEFAULT_LIBRARY_PROMPTS = [
    {
        "id": "prompt_encurtar",
        "title": "Encurtar sem Perder Informação",
        "category": "Edição",
        "content": "Reescreva o trecho selecionado de forma mais concisa, eliminando palavras vazias e mantendo todos os dados, números e nomes essenciais.",
        "version": 1,
        "is_default": 1,
    },
    {
        "id": "prompt_simplificar",
        "title": "Simplificar Linguagem",
        "category": "Edição",
        "content": "Substitua jargões técnicos e burocráticos por termos do cotidiano acessíveis ao leitor comum, sem diminuir a precisão da informação.",
        "version": 1,
        "is_default": 1,
    },
    {
        "id": "prompt_mais_direto",
        "title": "Tornar Mais Direto (Ordem Direta)",
        "category": "Estilo",
        "content": "Reorganize as frases estritamente na ordem direta (Sujeito + Verbo + Complemento), usando verbos ativos no indicativo e reduzindo orações subordinadas.",
        "version": 1,
        "is_default": 1,
    },
    {
        "id": "prompt_gancho_redes",
        "title": "Fortalecer Gancho de Abertura",
        "category": "Redes Sociais",
        "content": "Crie uma primeira frase impactante que resuma a grande novidade ou benefício prático, capturando a atenção imediata do leitor.",
        "version": 1,
        "is_default": 1,
    },
    {
        "id": "prompt_checagem_fidelidade",
        "title": "Revisão Crítica de Fidelidade",
        "category": "Checagem",
        "content": "Compare o texto produzido com o texto-base e aponte qualquer divergência em datas, números, cargos ou afirmações que não estejam comprovadas na fonte.",
        "version": 1,
        "is_default": 1,
    },
]


def seed_prompt_library_if_empty(repository: Repository = repo):
    """Garante a existência de templates padrão de prompt na primeira execução."""
    with repository.db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM prompt_library").fetchone()["c"]
        if count == 0:
            for p in DEFAULT_LIBRARY_PROMPTS:
                conn.execute("""
                    INSERT INTO prompt_library (id, title, category, content, version, is_default, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (p["id"], p["title"], p["category"], p["content"], p["version"], p["is_default"]))
            conn.commit()


def get_all_prompts(repository: Repository = repo) -> List[Dict[str, Any]]:
    seed_prompt_library_if_empty(repository)
    with repository.db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM prompt_library ORDER BY category, title").fetchall()
        return [dict(r) for r in rows]
