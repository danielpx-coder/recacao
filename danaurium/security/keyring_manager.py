"""Gerenciamento de credenciais e chaves de API com segurança.

Utiliza Windows Credential Manager (via keyring) como padrão seguro.
Caso o keyring do sistema não esteja disponível ou falhe, utiliza armazenamento
estritamente em memória durante a sessão. Jamais persiste chaves em texto puro,
bancos SQLite, arquivos de configuração ou backups.
"""

import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import keyring
from keyring.errors import KeyringError

logger = logging.getLogger("danaurium.security")

KEYRING_SERVICE_NAME = "DanauriumRedacaoStudio"


def extract_domain(url: str) -> str:
    """Extrai o host/domínio normalizado de uma URL."""
    try:
        parsed = urlparse(url)
        return (parsed.netloc or parsed.path).lower().split(":")[0]
    except Exception:
        return "unknown_host"


class CredentialManager:
    """Gerencia chaves de API com isolamento por conexão e validação de domínio."""

    def __init__(self):
        self._memory_cache: Dict[str, str] = {}
        self._domain_bindings: Dict[str, str] = {}
        self._keyring_available = self._probe_keyring()

    def _probe_keyring(self) -> bool:
        """Verifica se há um provedor funcional do keyring disponível no sistema."""
        try:
            current_backend = keyring.get_keyring()
            backend_name = current_backend.__class__.__name__
            # Backends nulos conhecidos do keyring quando nenhum cofre existe
            if "fail" in backend_name.lower() or "null" in backend_name.lower():
                logger.info("Keyring do sistema não disponível (%s). Usando modo seguro em memória.", backend_name)
                return False

            # Teste de leitura seguro
            test_val = keyring.get_password(KEYRING_SERVICE_NAME, "__probe_test__")
            logger.info("Keyring seguro ativo: %s", backend_name)
            return True
        except Exception as e:
            logger.warning("Falha ao sondar keyring do sistema: %s. Usando modo seguro em memória.", e)
            return False

    def is_secure_storage_active(self) -> bool:
        """Indica se as credenciais estão sendo salvas no cofre seguro do sistema operacional."""
        return self._keyring_available

    def get_storage_mode_name(self) -> str:
        """Retorna uma descrição amigável do mecanismo de armazenamento ativo."""
        if self._keyring_available:
            backend = keyring.get_keyring()
            return f"Cofre do Sistema ({backend.__class__.__name__})"
        return "Sessão Segura em Memória (Não persistido em disco)"

    def _make_key(self, connection_id: str) -> str:
        return f"conn_{connection_id}"

    def set_api_key(self, connection_id: str, base_url: str, api_key: str) -> bool:
        """Salva a chave vinculando-a obrigatoriamente ao domínio da conexão.
        
        Se a URL mudar de domínio posteriormente, o acesso à chave exigirá confirmação.
        """
        if not connection_id or not api_key:
            return False

        domain = extract_domain(base_url)
        conn_key = self._make_key(connection_id)
        
        # Registrar vínculo de domínio
        self._domain_bindings[connection_id] = domain

        # Armazenar no cofre do sistema, se disponível
        saved_to_keyring = False
        if self._keyring_available:
            try:
                # Armazena com o prefixo do domínio para impedir envio a domínio incorreto
                keyring.set_password(KEYRING_SERVICE_NAME, conn_key, f"{domain}::{api_key}")
                saved_to_keyring = True
                logger.info("Chave de API salva com sucesso no cofre seguro para conexão %s (domínio %s)", connection_id, domain)
            except KeyringError as ke:
                logger.warning("Erro ao salvar no keyring do sistema: %s. Salvando em memória.", ke)
            except Exception as e:
                logger.warning("Exceção inesperada ao salvar no keyring: %s. Salvando em memória.", e)

        # Sempre mantém na memória da sessão para acesso rápido e fallback
        self._memory_cache[connection_id] = api_key
        return True

    def get_api_key(self, connection_id: str, current_base_url: str) -> Optional[str]:
        """Recupera a chave de API, validando se o domínio atual corresponde ao domínio vinculado.
        
        Isso impede que uma chave configurada para um provedor seja enviada por engano
        para outro host se a URL for alterada.
        """
        if not connection_id:
            return None

        current_domain = extract_domain(current_base_url)
        conn_key = self._make_key(connection_id)

        # 1. Tentar ler do keyring do sistema
        if self._keyring_available:
            try:
                raw_secret = keyring.get_password(KEYRING_SERVICE_NAME, conn_key)
                if raw_secret:
                    if "::" in raw_secret:
                        bound_domain, key = raw_secret.split("::", 1)
                        if bound_domain != current_domain:
                            logger.error(
                                "Alerta de segurança: domínio alterado de '%s' para '%s' na conexão '%s'. "
                                "Envio da chave bloqueado até reconfirmação explícita.",
                                bound_domain, current_domain, connection_id
                            )
                            return None
                        # Atualiza memória e retorna
                        self._memory_cache[connection_id] = key
                        self._domain_bindings[connection_id] = bound_domain
                        return key
                    else:
                        # Legado sem domínio anotado
                        return raw_secret
            except Exception as e:
                logger.warning("Falha ao ler do keyring (%s). Consultando memória.", e)

        # 2. Consultar memória da sessão
        if connection_id in self._memory_cache:
            bound_domain = self._domain_bindings.get(connection_id)
            if bound_domain and bound_domain != current_domain:
                logger.error(
                    "Alerta de segurança em memória: domínio da conexão '%s' mudou de '%s' para '%s'.",
                    connection_id, bound_domain, current_domain
                )
                return None
            return self._memory_cache[connection_id]

        return None

    def delete_api_key(self, connection_id: str) -> bool:
        """Remove a chave do cofre e da memória."""
        conn_key = self._make_key(connection_id)
        self._memory_cache.pop(connection_id, None)
        self._domain_bindings.pop(connection_id, None)

        if self._keyring_available:
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, conn_key)
                return True
            except Exception as e:
                logger.debug("Chave não encontrada no keyring ou já removida: %s", e)
                return True
        return True

    def clear_session_memory(self):
        """Limpa as chaves mantidas na memória desta sessão."""
        self._memory_cache.clear()
        self._domain_bindings.clear()


# Instância única do gerenciador de credenciais
credentials = CredentialManager()
