"""Filtro de redação de dados sensíveis e credenciais em logs e saídas."""

import re
import logging
from typing import Any

# Padrões comuns de chaves de API e segredos
_SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9_\-]{20,})"),                         # OpenAI standard keys
    re.compile(r"(sk-ant-[a-zA-Z0-9_\-]{20,})"),                     # Anthropic keys
    re.compile(r"(sk-or-v1-[a-zA-Z0-9_\-]{20,})"),                  # OpenRouter keys
    re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),# Bearer tokens
    re.compile(r"(x-api-key\s*[:=]\s*)([a-zA-Z0-9_\-]{15,})", re.IGNORECASE),
    re.compile(r"(api[-_]?key\s*[:=]\s*['\"]?)([a-zA-Z0-9_\-]{15,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*['\"]?)([^'\"]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*['\"]?)([^'\"]+)(['\"]?)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Substitui credenciais e chaves por marcadores protegidos."""
    if not text:
        return text

    sanitized = str(text)
    for pattern in _SECRET_PATTERNS:
        # Se capturar grupos, preserva prefixo e mascara segredo
        def _replace_match(m: re.Match) -> str:
            groups = m.groups()
            if len(groups) == 1:
                val = groups[0]
                if len(val) > 8:
                    return f"{val[:4]}...[REDACTED]...{val[-4:]}"
                return "[REDACTED]"
            elif len(groups) >= 2:
                prefix = groups[0]
                val = groups[1]
                suffix = groups[2] if len(groups) > 2 else ""
                masked = f"{val[:3]}***[REDACTED]***{val[-3:]}" if len(val) > 8 else "***[REDACTED]***"
                return f"{prefix}{masked}{suffix}"
            return "[REDACTED]"

        sanitized = pattern.sub(_replace_match, sanitized)

    return sanitized


class SecretRedactionFilter(logging.Filter):
    """Filtro de logging que remove segredos de todas as mensagens registradas."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_secrets(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_secrets(str(a)) if isinstance(a, str) else a for a in record.args)
        return True
