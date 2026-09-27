"""Testes de persistência SQLite, versionamento editorial, auto-salvamento e crash recovery."""

from pathlib import Path
from danaurium.persistence.backup import create_backup, restore_backup


def test_schema_initialization(isolated_app_environment):
    db = isolated_app_environment["db"]
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT version FROM schema_version;")
        v = cur.fetchone()[0]
        assert v == 1


def test_connections_crud(isolated_app_environment):
    repo = isolated_app_environment["repo"]

    conn_id = repo.save_connection({
        "id": "c_teste",
        "name": "Conexão Teste",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "timeout_seconds": 45,
    })
    assert conn_id == "c_teste"

    conn = repo.get_connection("c_teste")
    assert conn is not None
    assert conn["name"] == "Conexão Teste"
    assert conn["timeout_seconds"] == 45

    repo.delete_connection("c_teste")
    assert repo.get_connection("c_teste") is None


def test_model_sync_preserves_user_preferences(isolated_app_environment):
    repo = isolated_app_environment["repo"]

    # 1. Salvar modelo inicial
    conn_id = "conn_sync_test"
    repo.save_connection({
        "id": conn_id,
        "name": "Conn Sync",
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
    })

    model_key = f"{conn_id}::gpt-4o"
    repo.save_model({
        "id": model_key,
        "connection_id": conn_id,
        "model_id": "gpt-4o",
        "display_name": "GPT-4o Inicial",
        "pricing_prompt": "2.50",
        "pricing_completion": "10.00",
        "is_favorite": True,
        "personal_category": "Premium",
        "notes": "Minhas anotações importantes que devem sobreviver ao sync.",
    })

    # 2. Executar sincronização vinda do provedor com novos preços/nomes
    fetched_from_api = [{
        "model_id": "gpt-4o",
        "display_name": "GPT-4o Omni Atualizado",
        "organization": "openai",
        "pricing_prompt": "2.00",
        "pricing_completion": "8.00",
    }]
    repo.sync_catalog_models(conn_id, fetched_from_api)

    # 3. Verificar que as preferências do usuário foram mantidas intactas
    updated = repo.get_model(model_key)
    assert updated["display_name"] == "GPT-4o Omni Atualizado"  # Atualizou dados do provedor
    assert updated["pricing_prompt"] == "2.00"
    assert updated["is_favorite"] == 1  # PRESERVADO!
    assert updated["personal_category"] == "Premium"  # PRESERVADO!
    assert updated["notes"] == "Minhas anotações importantes que devem sobreviver ao sync."  # PRESERVADO!


def test_editorial_versioning_and_rollback(isolated_app_environment):
    repo = isolated_app_environment["repo"]

    # Criar projeto
    proj_id = repo.save_project({
        "title": "Reportagem sobre Educação",
        "raw_text": "Texto inicial da matéria.",
    })

    # Salvar versão 1 do produto 'reportagem'
    v1_id = repo.save_version({
        "project_id": proj_id,
        "product_id": "reportagem",
        "content": "Primeira versão da reportagem redigida pela IA.",
    })

    # Salvar versão 2 do mesmo produto
    v2_id = repo.save_version({
        "project_id": proj_id,
        "product_id": "reportagem",
        "content": "Segunda versão revisada e encurtada pelo editor.",
    })

    versions = repo.get_versions(proj_id, "reportagem")
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1
    assert "Segunda versão" in versions[0]["content"]

    latest = repo.get_latest_version(proj_id, "reportagem")
    assert latest["id"] == v2_id


def test_crash_recovery_state(isolated_app_environment):
    repo = isolated_app_environment["repo"]

    draft_content = '{"title": "Matéria Resgatada", "raw_text": "Texto salvo antes da queda."}'
    repo.set_app_state("active_draft", draft_content)

    recovered = repo.get_app_state("active_draft")
    assert recovered == draft_content


def test_backup_and_restore(isolated_app_environment, tmp_path):
    repo = isolated_app_environment["repo"]
    db = isolated_app_environment["db"]

    proj_id = repo.save_project({
        "title": "Projeto Pré-Backup",
        "raw_text": "Dados críticos para testar restauração.",
    })

    backup_file = tmp_path / "backup_test.db"
    create_backup(backup_file, manager=db)

    # Excluir o projeto da base principal
    repo.delete_project(proj_id)
    assert repo.get_project(proj_id) is None

    # Restaurar backup
    restore_backup(backup_file, manager=db)

    # Verificar que o projeto foi recuperado
    recovered_proj = repo.get_project(proj_id)
    assert recovered_proj is not None
    assert recovered_proj["title"] == "Projeto Pré-Backup"
