"""Configurações centrais, caminhos de sistema e logging do Danaurium Redação Studio."""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
from danaurium.security.redaction import SecretRedactionFilter

APP_NAME = "Danaurium Redação Studio"
APP_IDENTIFIER = "DanauriumRedacaoStudio"
APP_VERSION = "1.0.0"


def get_base_data_dir() -> Path:
    """Retorna o diretório base de dados da aplicação.
    
    No Windows: %LOCALAPPDATA%\\DanauriumRedacaoStudio
    No Linux/macOS: ~/.local/share/DanauriumRedacaoStudio
    Pode ser sobrescrito pela variável de ambiente DANAURIUM_DATA_DIR.
    """
    env_dir = os.environ.get("DANAURIUM_DATA_DIR")
    if env_dir:
        base_dir = Path(env_dir)
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data) / APP_IDENTIFIER
        else:
            base_dir = Path.home() / "AppData" / "Local" / APP_IDENTIFIER
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base_dir = Path(xdg_data) / APP_IDENTIFIER
        else:
            base_dir = Path.home() / ".local" / "share" / APP_IDENTIFIER

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


class AppPaths:
    """Gerenciador centralizado de caminhos da aplicação."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_base_data_dir()
        self.database_dir = self.base_dir / "database"
        self.config_dir = self.base_dir / "config"
        self.cache_dir = self.base_dir / "cache"
        self.logs_dir = self.base_dir / "logs"
        self.backups_dir = self.base_dir / "backups"
        self.exports_dir = self.base_dir / "exports"

        # Criar todas as pastas necessárias
        for directory in [
            self.database_dir,
            self.config_dir,
            self.cache_dir,
            self.logs_dir,
            self.backups_dir,
            self.exports_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.database_dir / "danaurium.db"

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def log_path(self) -> Path:
        return self.logs_dir / "danaurium.log"


# Instância global de caminhos
paths = AppPaths()


def setup_logging(log_path: Optional[Path] = None, debug: bool = False) -> logging.Logger:
    """Configura o sistema de log da aplicação com higienização estrita de segredos."""
    target_path = log_path or paths.log_path
    logger = logging.getLogger("danaurium")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Evitar duplicar handlers se já configurado
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redaction_filter = SecretRedactionFilter()

    # File Handler
    try:
        file_handler = logging.FileHandler(str(target_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redaction_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Aviso: Não foi possível criar arquivo de log em {target_path}: {e}")

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    logger.addHandler(console_handler)

    return logger
