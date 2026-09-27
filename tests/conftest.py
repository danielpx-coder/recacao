"""Configurações globais e fixtures para a suíte de testes com pytest."""

import os
import sys
import shutil
import tempfile
from pathlib import Path
import pytest

# Forçar Qt para modo offscreen nos testes para não exigir servidor X11 / Wayland
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def isolated_app_environment(monkeypatch, tmp_path):
    """Isola completamente o diretório de dados em uma pasta temporária para cada teste."""
    temp_dir = tmp_path / "danaurium_test_data"
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DANAURIUM_DATA_DIR", str(temp_dir))

    # Reconfigurar caminhos globais
    from danaurium.config import AppPaths
    test_paths = AppPaths(base_dir=temp_dir)
    monkeypatch.setattr("danaurium.config.paths", test_paths)

    # Reconfigurar banco de dados isolado
    from danaurium.persistence.database import DatabaseManager
    test_db = DatabaseManager(db_path=test_paths.db_path)
    monkeypatch.setattr("danaurium.persistence.database.db_manager", test_db)

    # Reconfigurar repositório
    from danaurium.persistence.repository import Repository
    test_repo = Repository(manager=test_db)
    monkeypatch.setattr("danaurium.persistence.repository.repo", test_repo)

    # Limpar memória do gerenciador de credenciais
    from danaurium.security.keyring_manager import credentials
    credentials.clear_session_memory()

    yield {
        "paths": test_paths,
        "db": test_db,
        "repo": test_repo,
        "temp_dir": temp_dir,
    }
