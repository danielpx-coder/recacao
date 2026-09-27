"""Backup e restauração consistente do banco de dados SQLite sem segredos."""

import os
import sqlite3
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from danaurium.config import paths
from danaurium.persistence.database import DatabaseManager, db_manager

logger = logging.getLogger("danaurium.persistence.backup")


def create_backup(target_file: Optional[Path] = None, manager: Optional[DatabaseManager] = None) -> Path:
    """Cria uma cópia consistente online do banco de dados SQLite usando a API nativa de backup.
    
    O arquivo gerado é totalmente livre de chaves de API ou segredos.
    """
    db = manager or db_manager
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = target_file or (paths.backups_dir / f"danaurium_backup_{timestamp}.db")
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # Conectar ao banco de origem e criar o backup seguro
    with db.get_connection() as src_conn:
        dest_conn = sqlite3.connect(str(backup_path))
        try:
            src_conn.backup(dest_conn)
            logger.info("Backup online concluído com sucesso em %s", backup_path)
        finally:
            dest_conn.close()

    # Validação pós-criação: verificar integridade do backup
    with sqlite3.connect(str(backup_path)) as chk_conn:
        cur = chk_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0] != "ok":
            raise RuntimeError(f"Falha na verificação de integridade do backup gerado: {res}")

    return backup_path


def restore_backup(source_file: Path, manager: Optional[DatabaseManager] = None) -> bool:
    """Restaura o banco de dados a partir de um arquivo de backup consistente.
    
    Verifica integridade antes de sobrescrever o banco principal.
    """
    if not source_file.exists():
        raise FileNotFoundError(f"Arquivo de backup não encontrado: {source_file}")

    db = manager or db_manager

    # 1. Validar se o arquivo de origem é um banco SQLite válido e íntegro
    try:
        with sqlite3.connect(str(source_file)) as test_conn:
            cur = test_conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            if not row or row[0] != "ok":
                raise ValueError("O arquivo de backup selecionado está corrompido.")
            
            # Verificar se contém as tabelas essenciais
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('connections', 'projects');")
            tables = [r[0] for r in cur.fetchall()]
            if len(tables) < 2:
                raise ValueError("O arquivo de backup não contém as tabelas necessárias do Danaurium Redação Studio.")
    except Exception as e:
        logger.error("Falha ao validar arquivo de backup para restauração: %s", e)
        raise

    # 2. Fazer cópia de segurança do banco atual antes de sobrescrever
    current_db = db.db_path
    if current_db.exists():
        safety_path = current_db.with_suffix(f".pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.bak")
        shutil.copy2(current_db, safety_path)
        logger.info("Cópia de segurança pré-restauração criada em %s", safety_path)

    # 3. Executar restauração online para o banco atual
    dest_conn = db.get_connection()
    try:
        src_conn = sqlite3.connect(str(source_file))
        try:
            src_conn.backup(dest_conn)
            logger.info("Restauração do backup de %s para %s concluída com sucesso.", source_file, current_db)
        finally:
            src_conn.close()
    finally:
        dest_conn.close()

    return True
