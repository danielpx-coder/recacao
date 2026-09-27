"""Gerenciamento de banco de dados SQLite com WAL mode, migrações e chaves estrangeiras."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from danaurium.config import paths

logger = logging.getLogger("danaurium.persistence.database")

SCHEMA_VERSION = 1

INIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    catalog_path TEXT NOT NULL,
    generation_path TEXT NOT NULL,
    timeout_seconds INTEGER NOT NULL DEFAULT 60,
    max_retries INTEGER NOT NULL DEFAULT 3,
    default_model_id TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    organization TEXT,
    protocol TEXT NOT NULL,
    endpoint TEXT,
    modalities TEXT NOT NULL DEFAULT '["text"]',
    context_window INTEGER,
    max_output_tokens INTEGER,
    supports_streaming INTEGER NOT NULL DEFAULT 1,
    supports_structured_output INTEGER NOT NULL DEFAULT 1,
    supported_parameters TEXT NOT NULL DEFAULT '["temperature", "top_p"]',
    pricing_prompt TEXT,
    pricing_completion TEXT,
    pricing_unit TEXT NOT NULL DEFAULT 'per_1m_tokens',
    pricing_cache_read TEXT,
    pricing_cache_write TEXT,
    pricing_reasoning TEXT,
    pricing_source TEXT,
    pricing_updated_at TEXT,
    is_free INTEGER NOT NULL DEFAULT 0,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    personal_category TEXT NOT NULL DEFAULT 'Intermediário',
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    last_tested_at TEXT,
    last_test_status TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_verified_access INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_system_preset INTEGER NOT NULL DEFAULT 0,
    task_extraction_model TEXT,
    task_drafting_model TEXT,
    task_radio_model TEXT,
    task_social_model TEXT,
    task_review_model TEXT,
    fallback_enabled INTEGER NOT NULL DEFAULT 0,
    fallback_models TEXT NOT NULL DEFAULT '[]',
    max_cost_limit TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    source_metadata TEXT NOT NULL DEFAULT '{}',
    extracted_facts TEXT NOT NULL DEFAULT '[]',
    selected_products TEXT NOT NULL DEFAULT '[]',
    tone TEXT NOT NULL DEFAULT 'Equilibrado e Jornalístico',
    audience TEXT NOT NULL DEFAULT 'Público Geral',
    purpose TEXT NOT NULL DEFAULT 'Informar com clareza',
    grammatical_person TEXT NOT NULL DEFAULT '3ª pessoa',
    institutional_signature TEXT NOT NULL DEFAULT '',
    mandatory_words TEXT NOT NULL DEFAULT '',
    forbidden_expressions TEXT NOT NULL DEFAULT '',
    char_limit_preset INTEGER NOT NULL DEFAULT 1800,
    profile_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS editorial_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    model_used TEXT,
    connection_used TEXT,
    prompt_instruction TEXT,
    fidelity_warnings TEXT NOT NULL DEFAULT '[]',
    word_count INTEGER NOT NULL DEFAULT 0,
    char_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    tokens_reasoning INTEGER NOT NULL DEFAULT 0,
    tokens_cache INTEGER NOT NULL DEFAULT 0,
    cost_calculated TEXT NOT NULL DEFAULT '0.000000',
    user_rating INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    connection_id TEXT,
    model_id TEXT,
    task_type TEXT,
    product_id TEXT,
    pre_flight_estimate TEXT NOT NULL DEFAULT '0.000000',
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    tokens_cache_read INTEGER NOT NULL DEFAULT 0,
    tokens_cache_write INTEGER NOT NULL DEFAULT 0,
    tokens_reasoning INTEGER NOT NULL DEFAULT 0,
    cost_calculated TEXT NOT NULL DEFAULT '0.000000',
    cost_provider_reported TEXT,
    currency TEXT NOT NULL DEFAULT 'USD',
    brl_exchange_rate TEXT NOT NULL DEFAULT '5.50',
    brl_exchange_date TEXT,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'success',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_library (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    daily_limit_usd TEXT,
    monthly_limit_usd TEXT,
    project_limit_usd TEXT,
    strict_free_mode INTEGER NOT NULL DEFAULT 0,
    strict_budget_mode INTEGER NOT NULL DEFAULT 0,
    max_output_tokens INTEGER NOT NULL DEFAULT 4096,
    usd_to_brl_rate TEXT NOT NULL DEFAULT '5.50',
    usd_to_brl_date TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_models_connection ON models(connection_id);
CREATE INDEX IF NOT EXISTS idx_models_free ON models(is_free);
CREATE INDEX IF NOT EXISTS idx_editorial_versions_project ON editorial_versions(project_id, product_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_project ON usage_logs(project_id);
"""


class DatabaseManager:
    """Gerenciador central de conexões SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or paths.db_path
        self._ensure_parent_directory()
        self.init_database()

    def _ensure_parent_directory(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Abre uma conexão SQLite configurada com WAL e chaves estrangeiras."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_database(self):
        """Inicializa as tabelas e índices se ainda não existirem."""
        with self.get_connection() as conn:
            conn.executescript(INIT_SQL)
            # Verificar versão do schema
            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
            row = cur.fetchone()
            if not row:
                from datetime import datetime
                now_str = datetime.utcnow().isoformat()
                cur.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, now_str),
                )
            # Garantir configurações padrão de orçamento
            cur.execute("SELECT id FROM budget_settings WHERE id = 1")
            if not cur.fetchone():
                from datetime import datetime
                now_str = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO budget_settings (
                        id, daily_limit_usd, monthly_limit_usd, project_limit_usd,
                        strict_free_mode, strict_budget_mode, max_output_tokens,
                        usd_to_brl_rate, usd_to_brl_date, updated_at
                    ) VALUES (1, '10.00', '100.00', '5.00', 0, 0, 4096, '5.50', '2026-09-27', ?)
                """, (now_str,))
            conn.commit()
            logger.info("Banco de dados SQLite inicializado com sucesso em %s", self.db_path)


# Instância global do gerenciador de banco
db_manager = DatabaseManager()
