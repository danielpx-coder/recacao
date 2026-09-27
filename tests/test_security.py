"""Testes de segurança, proteção de credenciais, isolamento de domínio e redação de logs."""

import logging
import sqlite3
from pathlib import Path
from danaurium.security.keyring_manager import CredentialManager, extract_domain
from danaurium.security.redaction import redact_secrets, SecretRedactionFilter
from danaurium.persistence.backup import create_backup


def test_extract_domain():
    assert extract_domain("https://api.openai.com/v1/chat/completions") == "api.openai.com"
    assert extract_domain("https://openrouter.ai:443/api/v1") == "openrouter.ai"
    assert extract_domain("http://localhost:11434/v1") == "localhost"


def test_credential_storage_and_domain_protection():
    mgr = CredentialManager()
    mgr._keyring_available = False  # Forçar teste de memória segura

    conn_id = "test_conn_openai"
    original_url = "https://api.openai.com/v1"
    secret_key = "sk-test-super-secret-key-1234567890"

    # 1. Salvar chave
    ok = mgr.set_api_key(conn_id, original_url, secret_key)
    assert ok is True

    # 2. Recuperar com o mesmo domínio -> DEVE FUNCIONAR
    retrieved = mgr.get_api_key(conn_id, original_url)
    assert retrieved == secret_key

    # 3. Tentar recuperar com domínio alterado -> DEVE SER BLOQUEADO
    altered_url = "https://malicious-server.com/v1"
    blocked_key = mgr.get_api_key(conn_id, altered_url)
    assert blocked_key is None, "A chave jamais deve ser enviada a um domínio alterado sem reconfirmação explícita!"

    # 4. Excluir chave
    mgr.delete_api_key(conn_id)
    assert mgr.get_api_key(conn_id, original_url) is None


def test_secret_redaction_in_strings():
    text_with_keys = (
        "Iniciando chamada com Authorization: Bearer sk-proj-1234567890abcdef1234567890 "
        "e x-api-key: sk-ant-api03-abcdef1234567890 "
        "e chave openrouter sk-or-v1-abcdef12345678901234567890."
    )

    sanitized = redact_secrets(text_with_keys)
    assert "sk-proj-1234567890abcdef1234567890" not in sanitized
    assert "sk-ant-api03-abcdef1234567890" not in sanitized
    assert "sk-or-v1-abcdef12345678901234567890" not in sanitized
    assert "[REDACTED]" in sanitized


def test_logging_filter_scrubs_secrets(tmp_path):
    log_file = tmp_path / "test_secure.log"
    logger = logging.getLogger("test_redact_logger")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.addFilter(SecretRedactionFilter())
    formatter = logging.Formatter("%(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.info("Tentativa com token sk-123456789012345678901234567890")
    fh.flush()

    with open(log_file, "r", encoding="utf-8") as f:
        log_content = f.read()

    assert "sk-123456789012345678901234567890" not in log_content
    assert "[REDACTED]" in log_content


def test_absence_of_keys_in_sqlite_and_backups(isolated_app_environment):
    repo = isolated_app_environment["repo"]
    db = isolated_app_environment["db"]

    # Salvar conexão no banco
    conn_id = repo.save_connection({
        "id": "conn_verify_no_keys",
        "name": "Conexão de Teste Sem Segredo",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
    })

    # Verificar todas as colunas de todas as tabelas
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        schemas = cur.fetchall()
        for s in schemas:
            schema_text = s[0].lower()
            assert "api_key" not in schema_text, "A palavra-chave 'api_key' não deve constar em nenhuma tabela SQLite!"

    # Criar backup consistente e verificar integridade
    backup_file = create_backup(manager=db)
    assert backup_file.exists()

    with sqlite3.connect(str(backup_file)) as bkp_conn:
        cur = bkp_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        assert "connections" in tables

        # Verificar dados da tabela connections no backup
        cur.execute("SELECT * FROM connections;")
        cols = [d[0] for d in cur.description]
        assert "api_key" not in cols
