"""Repositório de dados tipado para todas as entidades do Danaurium Redação Studio."""

import json
import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from danaurium.persistence.database import DatabaseManager, db_manager

logger = logging.getLogger("danaurium.persistence.repository")


def _now() -> str:
    return datetime.utcnow().isoformat()


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{int(datetime.utcnow().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"


class Repository:
    """Acesso a dados com transações seguras e conversões de tipo."""

    def __init__(self, manager: Optional[DatabaseManager] = None):
        self.db = manager or db_manager

    # ---------------------------------------------------------
    # CONEXÕES
    # ---------------------------------------------------------
    def get_all_connections(self, only_active: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM connections"
        if only_active:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY name ASC"
        with self.db.get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    def get_connection(self, conn_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM connections WHERE id = ?", (conn_id,)).fetchone()
            return dict(row) if row else None

    def save_connection(self, data: Dict[str, Any]) -> str:
        """Cria ou atualiza uma conexão. Jamais salva a chave de API aqui."""
        now_str = _now()
        conn_id = data.get("id") or _gen_id("conn")
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO connections (
                    id, name, provider_type, base_url, catalog_path, generation_path,
                    timeout_seconds, max_retries, default_model_id, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    provider_type = excluded.provider_type,
                    base_url = excluded.base_url,
                    catalog_path = excluded.catalog_path,
                    generation_path = excluded.generation_path,
                    timeout_seconds = excluded.timeout_seconds,
                    max_retries = excluded.max_retries,
                    default_model_id = excluded.default_model_id,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
            """, (
                conn_id,
                data["name"],
                data["provider_type"],
                data["base_url"],
                data.get("catalog_path", "/models"),
                data.get("generation_path", "/chat/completions"),
                data.get("timeout_seconds", 60),
                data.get("max_retries", 3),
                data.get("default_model_id"),
                1 if data.get("is_active", True) else 0,
                data.get("created_at", now_str),
                now_str,
            ))
            conn.commit()
        return conn_id

    def delete_connection(self, conn_id: str) -> bool:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM connections WHERE id = ?", (conn_id,))
            conn.commit()
            return True

    # ---------------------------------------------------------
    # MODELOS E CATÁLOGO
    # ---------------------------------------------------------
    def get_models(
        self,
        connection_id: Optional[str] = None,
        only_active: bool = True,
        is_free: Optional[bool] = None,
        only_favorites: bool = False,
        personal_category: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []

        if connection_id:
            clauses.append("connection_id = ?")
            params.append(connection_id)
        if only_active:
            clauses.append("is_active = 1")
        if is_free is not None:
            clauses.append("is_free = ?")
            params.append(1 if is_free else 0)
        if only_favorites:
            clauses.append("is_favorite = 1")
        if personal_category and personal_category != "Todos":
            clauses.append("personal_category = ?")
            params.append(personal_category)
        if search_query:
            clauses.append("(display_name LIKE ? OR model_id LIKE ? OR organization LIKE ?)")
            q = f"%{search_query}%"
            params.extend([q, q, q])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM models {where_sql} ORDER BY display_name ASC"

        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["modalities"] = json.loads(d.get("modalities") or '["text"]')
                d["supported_parameters"] = json.loads(d.get("supported_parameters") or "[]")
                d["tags"] = json.loads(d.get("tags") or "[]")
                res.append(d)
            return res

    def get_model(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM models WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["modalities"] = json.loads(d.get("modalities") or '["text"]')
            d["supported_parameters"] = json.loads(d.get("supported_parameters") or "[]")
            d["tags"] = json.loads(d.get("tags") or "[]")
            return d

    def save_model(self, data: Dict[str, Any]) -> str:
        record_id = data.get("id") or f"{data['connection_id']}::{data['model_id']}"
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO models (
                    id, connection_id, model_id, display_name, organization, protocol, endpoint,
                    modalities, context_window, max_output_tokens, supports_streaming,
                    supports_structured_output, supported_parameters, pricing_prompt,
                    pricing_completion, pricing_unit, pricing_cache_read, pricing_cache_write,
                    pricing_reasoning, pricing_source, pricing_updated_at, is_free, is_favorite,
                    personal_category, tags, notes, last_tested_at, last_test_status, is_active,
                    is_verified_access
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    organization = excluded.organization,
                    protocol = excluded.protocol,
                    endpoint = excluded.endpoint,
                    modalities = excluded.modalities,
                    context_window = excluded.context_window,
                    max_output_tokens = excluded.max_output_tokens,
                    supports_streaming = excluded.supports_streaming,
                    supports_structured_output = excluded.supports_structured_output,
                    supported_parameters = excluded.supported_parameters,
                    pricing_prompt = excluded.pricing_prompt,
                    pricing_completion = excluded.pricing_completion,
                    pricing_unit = excluded.pricing_unit,
                    pricing_cache_read = excluded.pricing_cache_read,
                    pricing_cache_write = excluded.pricing_cache_write,
                    pricing_reasoning = excluded.pricing_reasoning,
                    pricing_source = excluded.pricing_source,
                    pricing_updated_at = excluded.pricing_updated_at,
                    is_free = excluded.is_free,
                    is_active = excluded.is_active
            """, (
                record_id,
                data["connection_id"],
                data["model_id"],
                data["display_name"],
                data.get("organization"),
                data.get("protocol", "chat_completions"),
                data.get("endpoint"),
                json.dumps(data.get("modalities", ["text"])),
                data.get("context_window"),
                data.get("max_output_tokens"),
                1 if data.get("supports_streaming", True) else 0,
                1 if data.get("supports_structured_output", True) else 0,
                json.dumps(data.get("supported_parameters", ["temperature", "top_p"])),
                data.get("pricing_prompt"),
                data.get("pricing_completion"),
                data.get("pricing_unit", "per_1m_tokens"),
                data.get("pricing_cache_read"),
                data.get("pricing_cache_write"),
                data.get("pricing_reasoning"),
                data.get("pricing_source"),
                data.get("pricing_updated_at"),
                1 if data.get("is_free", False) else 0,
                1 if data.get("is_favorite", False) else 0,
                data.get("personal_category", "Intermediário"),
                json.dumps(data.get("tags", [])),
                data.get("notes", ""),
                data.get("last_tested_at"),
                data.get("last_test_status"),
                1 if data.get("is_active", True) else 0,
                1 if data.get("is_verified_access", False) else 0,
            ))
            conn.commit()
        return record_id

    def update_model_preferences(
        self,
        record_id: str,
        is_favorite: Optional[bool] = None,
        personal_category: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        is_verified_access: Optional[bool] = None,
        last_tested_at: Optional[str] = None,
        last_test_status: Optional[str] = None,
    ):
        """Atualiza preferências do usuário para um modelo, preservadas após sincronização."""
        updates = []
        params = []
        if is_favorite is not None:
            updates.append("is_favorite = ?")
            params.append(1 if is_favorite else 0)
        if personal_category is not None:
            updates.append("personal_category = ?")
            params.append(personal_category)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if is_verified_access is not None:
            updates.append("is_verified_access = ?")
            params.append(1 if is_verified_access else 0)
        if last_tested_at is not None:
            updates.append("last_tested_at = ?")
            params.append(last_tested_at)
        if last_test_status is not None:
            updates.append("last_test_status = ?")
            params.append(last_test_status)

        if not updates:
            return

        params.append(record_id)
        sql = f"UPDATE models SET {', '.join(updates)} WHERE id = ?"
        with self.db.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def sync_catalog_models(self, connection_id: str, fetched_models: List[Dict[str, Any]]):
        """Sincroniza modelos do provedor preservando preferências (favoritos, tags, notas, categoria)."""
        with self.db.get_connection() as conn:
            # Buscar preferências existentes
            existing_rows = conn.execute(
                "SELECT id, is_favorite, personal_category, tags, notes, is_verified_access, last_tested_at, last_test_status FROM models WHERE connection_id = ?",
                (connection_id,),
            ).fetchall()
            existing_prefs = {r["id"]: dict(r) for r in existing_rows}

            for m in fetched_models:
                rec_id = f"{connection_id}::{m['model_id']}"
                pref = existing_prefs.get(rec_id, {})
                m_copy = dict(m)
                m_copy["id"] = rec_id
                m_copy["connection_id"] = connection_id
                # Preservar preferências
                if "is_favorite" in pref:
                    m_copy["is_favorite"] = bool(pref["is_favorite"])
                if pref.get("personal_category"):
                    m_copy["personal_category"] = pref["personal_category"]
                if pref.get("notes"):
                    m_copy["notes"] = pref["notes"]
                if pref.get("tags"):
                    m_copy["tags"] = json.loads(pref["tags"])
                if "is_verified_access" in pref:
                    m_copy["is_verified_access"] = bool(pref["is_verified_access"])
                if pref.get("last_tested_at"):
                    m_copy["last_tested_at"] = pref["last_tested_at"]
                    m_copy["last_test_status"] = pref.get("last_test_status")

                self.save_model(m_copy)

    # ---------------------------------------------------------
    # PROJETOS EDITORIAIS
    # ---------------------------------------------------------
    def get_projects(self, search_query: Optional[str] = None, only_favorites: bool = False) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if only_favorites:
            clauses.append("is_favorite = 1")
        if search_query:
            clauses.append("(title LIKE ? OR raw_text LIKE ?)")
            q = f"%{search_query}%"
            params.extend([q, q])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM projects {where_sql} ORDER BY updated_at DESC"
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["source_metadata"] = json.loads(d.get("source_metadata") or "{}")
                d["extracted_facts"] = json.loads(d.get("extracted_facts") or "[]")
                d["selected_products"] = json.loads(d.get("selected_products") or "[]")
                res.append(d)
            return res

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["source_metadata"] = json.loads(d.get("source_metadata") or "{}")
            d["extracted_facts"] = json.loads(d.get("extracted_facts") or "[]")
            d["selected_products"] = json.loads(d.get("selected_products") or "[]")
            return d

    def save_project(self, data: Dict[str, Any]) -> str:
        now_str = _now()
        proj_id = data.get("id") or _gen_id("proj")
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO projects (
                    id, title, raw_text, source_metadata, extracted_facts, selected_products,
                    tone, audience, purpose, grammatical_person, institutional_signature,
                    mandatory_words, forbidden_expressions, char_limit_preset, profile_id,
                    status, is_favorite, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    raw_text = excluded.raw_text,
                    source_metadata = excluded.source_metadata,
                    extracted_facts = excluded.extracted_facts,
                    selected_products = excluded.selected_products,
                    tone = excluded.tone,
                    audience = excluded.audience,
                    purpose = excluded.purpose,
                    grammatical_person = excluded.grammatical_person,
                    institutional_signature = excluded.institutional_signature,
                    mandatory_words = excluded.mandatory_words,
                    forbidden_expressions = excluded.forbidden_expressions,
                    char_limit_preset = excluded.char_limit_preset,
                    profile_id = excluded.profile_id,
                    status = excluded.status,
                    is_favorite = excluded.is_favorite,
                    updated_at = excluded.updated_at
            """, (
                proj_id,
                data.get("title", "Novo Projeto Editorial"),
                data.get("raw_text", ""),
                json.dumps(data.get("source_metadata", {})),
                json.dumps(data.get("extracted_facts", [])),
                json.dumps(data.get("selected_products", [])),
                data.get("tone", "Equilibrado e Jornalístico"),
                data.get("audience", "Público Geral"),
                data.get("purpose", "Informar com clareza"),
                data.get("grammatical_person", "3ª pessoa"),
                data.get("institutional_signature", ""),
                data.get("mandatory_words", ""),
                data.get("forbidden_expressions", ""),
                data.get("char_limit_preset", 1800),
                data.get("profile_id"),
                data.get("status", "draft"),
                1 if data.get("is_favorite", False) else 0,
                data.get("created_at", now_str),
                now_str,
            ))
            conn.commit()
        return proj_id

    def delete_project(self, project_id: str) -> bool:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return True

    # ---------------------------------------------------------
    # VERSÕES EDITORIAIS
    # ---------------------------------------------------------
    def get_versions(self, project_id: str, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM editorial_versions WHERE project_id = ?"
        params = [project_id]
        if product_id:
            sql += " AND product_id = ?"
            params.append(product_id)
        sql += " ORDER BY version_number DESC"

        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["fidelity_warnings"] = json.loads(d.get("fidelity_warnings") or "[]")
                res.append(d)
            return res

    def get_latest_version(self, project_id: str, product_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM editorial_versions
                WHERE project_id = ? AND product_id = ?
                ORDER BY version_number DESC LIMIT 1
            """, (project_id, product_id)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["fidelity_warnings"] = json.loads(d.get("fidelity_warnings") or "[]")
            return d

    def save_version(self, data: Dict[str, Any]) -> str:
        """Salva nova versão de um produto editorial."""
        now_str = _now()
        ver_id = data.get("id") or _gen_id("ver")
        project_id = data["project_id"]
        product_id = data["product_id"]

        with self.db.get_connection() as conn:
            # Calcular próximo número de versão se não especificado
            cur_ver = data.get("version_number")
            if not cur_ver:
                row = conn.execute(
                    "SELECT MAX(version_number) as max_v FROM editorial_versions WHERE project_id = ? AND product_id = ?",
                    (project_id, product_id),
                ).fetchone()
                cur_ver = (row["max_v"] or 0) + 1

            conn.execute("""
                INSERT INTO editorial_versions (
                    id, project_id, product_id, version_number, title, content,
                    model_used, connection_used, prompt_instruction, fidelity_warnings,
                    word_count, char_count, latency_ms, tokens_input, tokens_output,
                    tokens_reasoning, tokens_cache, cost_calculated, user_rating, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ver_id,
                project_id,
                product_id,
                cur_ver,
                data.get("title", ""),
                data["content"],
                data.get("model_used"),
                data.get("connection_used"),
                data.get("prompt_instruction"),
                json.dumps(data.get("fidelity_warnings", [])),
                data.get("word_count", len(data["content"].split())),
                data.get("char_count", len(data["content"])),
                data.get("latency_ms", 0),
                data.get("tokens_input", 0),
                data.get("tokens_output", 0),
                data.get("tokens_reasoning", 0),
                data.get("tokens_cache", 0),
                str(data.get("cost_calculated", "0.000000")),
                data.get("user_rating", 0),
                now_str,
            ))
            conn.commit()
        return ver_id

    # ---------------------------------------------------------
    # CONSUMO E ORÇAMENTO (LOGS)
    # ---------------------------------------------------------
    def log_usage(self, data: Dict[str, Any]) -> str:
        now_str = _now()
        log_id = data.get("id") or _gen_id("usage")
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO usage_logs (
                    id, project_id, connection_id, model_id, task_type, product_id,
                    pre_flight_estimate, tokens_input, tokens_output, tokens_cache_read,
                    tokens_cache_write, tokens_reasoning, cost_calculated,
                    cost_provider_reported, currency, brl_exchange_rate, brl_exchange_date,
                    latency_ms, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                data.get("project_id"),
                data.get("connection_id"),
                data.get("model_id"),
                data.get("task_type"),
                data.get("product_id"),
                str(data.get("pre_flight_estimate", "0.000000")),
                data.get("tokens_input", 0),
                data.get("tokens_output", 0),
                data.get("tokens_cache_read", 0),
                data.get("tokens_cache_write", 0),
                data.get("tokens_reasoning", 0),
                str(data.get("cost_calculated", "0.000000")),
                str(data["cost_provider_reported"]) if data.get("cost_provider_reported") else None,
                data.get("currency", "USD"),
                str(data.get("brl_exchange_rate", "5.50")),
                data.get("brl_exchange_date", "2026-09-27"),
                data.get("latency_ms", 0),
                data.get("status", "success"),
                now_str,
            ))
            conn.commit()
        return log_id

    def get_usage_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        project_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        model_id: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if start_date:
            clauses.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("created_at <= ?")
            params.append(end_date)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if connection_id:
            clauses.append("connection_id = ?")
            params.append(connection_id)
        if model_id:
            clauses.append("model_id = ?")
            params.append(model_id)
        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM usage_logs {where_sql} ORDER BY created_at DESC"
        with self.db.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ---------------------------------------------------------
    # CONFIGURAÇÕES DE ORÇAMENTO
    # ---------------------------------------------------------
    def get_budget_settings(self) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM budget_settings WHERE id = 1").fetchone()
            if row:
                return dict(row)
            return {
                "id": 1,
                "daily_limit_usd": "10.00",
                "monthly_limit_usd": "100.00",
                "project_limit_usd": "5.00",
                "strict_free_mode": 0,
                "strict_budget_mode": 0,
                "max_output_tokens": 4096,
                "usd_to_brl_rate": "5.50",
                "usd_to_brl_date": "2026-09-27",
            }

    def update_budget_settings(self, data: Dict[str, Any]):
        now_str = _now()
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE budget_settings SET
                    daily_limit_usd = ?,
                    monthly_limit_usd = ?,
                    project_limit_usd = ?,
                    strict_free_mode = ?,
                    strict_budget_mode = ?,
                    max_output_tokens = ?,
                    usd_to_brl_rate = ?,
                    usd_to_brl_date = ?,
                    updated_at = ?
                WHERE id = 1
            """, (
                str(data.get("daily_limit_usd", "10.00")),
                str(data.get("monthly_limit_usd", "100.00")),
                str(data.get("project_limit_usd", "5.00")),
                1 if data.get("strict_free_mode") else 0,
                1 if data.get("strict_budget_mode") else 0,
                data.get("max_output_tokens", 4096),
                str(data.get("usd_to_brl_rate", "5.50")),
                data.get("usd_to_brl_date", "2026-09-27"),
                now_str,
            ))
            conn.commit()

    # ---------------------------------------------------------
    # RECUPERAÇÃO DE ESTADO (CRASH RECOVERY)
    # ---------------------------------------------------------
    def set_app_state(self, key: str, value: str):
        now_str = _now()
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO app_state (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, value, now_str))
            conn.commit()

    def get_app_state(self, key: str) -> Optional[str]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None


# Instância global do repositório
repo = Repository()
