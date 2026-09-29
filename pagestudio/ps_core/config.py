# -*- coding: utf-8 -*-
"""
Configurações persistentes, arquivos recentes e recuperação automática.

Tudo fica em JSON no diretório de dados do usuário
(``%LOCALAPPDATA%\\RD5PageStudio`` no Windows, ``~/.local/share/RD5PageStudio``
em Linux/macOS). A variável de ambiente ``RD5_PAGESTUDIO_DIR`` sobrescreve o
local — é assim que os testes isolam o ambiente.

Além das preferências, o módulo cuida dos **autosaves**: enquanto houver
alterações não gravadas, o editor mantém uma cópia do documento na pasta
``autosave``. Se o programa for fechado de forma anormal, essa cópia é oferecida
na próxima abertura.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ENV_DIR = "RD5_PAGESTUDIO_DIR"
APP_DIRNAME = "RD5PageStudio"
CONFIG_FILENAME = "config.json"
AUTOSAVE_DIRNAME = "autosave"
AUTOSAVE_SUFFIX = ".rd5autosave.htm"
MAX_RECENT = 10


def base_dir() -> Path:
    """Diretório de dados do aplicativo (criado se necessário)."""
    env = os.environ.get(ENV_DIR)
    if env:
        root = Path(env)
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        root = Path(local) / APP_DIRNAME if local else Path.home() / "AppData" / "Local" / APP_DIRNAME
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DIRNAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        root = Path(xdg) / APP_DIRNAME if xdg else Path.home() / ".local" / "share" / APP_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def config_path() -> Path:
    return base_dir() / CONFIG_FILENAME


def autosave_dir() -> Path:
    d = base_dir() / AUTOSAVE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def autosave_path(source: Optional[str], title: str = "sem_titulo") -> Path:
    """Caminho do autosave de um documento (estável para o mesmo arquivo)."""
    key = os.path.abspath(source) if source else f"novo::{title}"
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:10]
    name = os.path.splitext(os.path.basename(source or title))[0][:40] or "pagina"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    return autosave_dir() / f"{safe}-{digest}{AUTOSAVE_SUFFIX}"


def find_autosaves() -> List[Tuple[Path, float]]:
    """Lista os autosaves existentes, do mais recente para o mais antigo."""
    found: List[Tuple[Path, float]] = []
    for p in autosave_dir().glob(f"*{AUTOSAVE_SUFFIX}"):
        try:
            found.append((p, p.stat().st_mtime))
        except OSError:  # pragma: no cover - arquivo removido no meio
            continue
    found.sort(key=lambda item: item[1], reverse=True)
    return found


def clear_autosaves() -> int:
    """Remove autosaves com mais de 30 dias; devolve quantos apagou."""
    limit = time.time() - 30 * 24 * 3600
    removed = 0
    for path, mtime in find_autosaves():
        if mtime < limit:
            try:
                path.unlink()
                removed += 1
            except OSError:  # pragma: no cover
                pass
    return removed


@dataclass
class Settings:
    """Preferências do editor."""

    recent: List[str] = field(default_factory=list)
    geometry: str = "1180x760"
    root_dir: str = ""
    mode: str = "design"
    autosave: bool = True
    autosave_minutes: int = 2
    watch_file: bool = True
    show_preview: bool = True
    font_size: int = 12
    wrap_code: bool = False

    # -- persistência -------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        p = Path(path) if path else config_path()
        data: Dict = {}
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in known}
        try:
            s = cls(**clean)
        except TypeError:  # pragma: no cover - defensivo
            s = cls()
        s.recent = [str(x) for x in s.recent if str(x)][:MAX_RECENT]
        return s

    def save(self, path: Optional[Path] = None) -> bool:
        p = Path(path) if path else config_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2),
                         encoding="utf-8")
            return True
        except OSError:
            return False

    # -- recentes -----------------------------------------------------------
    def add_recent(self, path: str) -> List[str]:
        """Coloca ``path`` no topo da lista de recentes (sem duplicatas)."""
        p = os.path.abspath(path)
        self.recent = [p] + [r for r in self.recent if os.path.abspath(r) != p]
        self.recent = self.recent[:MAX_RECENT]
        return self.recent

    def drop_recent(self, path: str) -> List[str]:
        p = os.path.abspath(path)
        self.recent = [r for r in self.recent if os.path.abspath(r) != p]
        return self.recent

    def prune_recent(self) -> List[str]:
        """Descarta entradas de arquivos que não existem mais."""
        self.recent = [r for r in self.recent if os.path.exists(r)]
        return self.recent
