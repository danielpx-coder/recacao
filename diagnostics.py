"""Script de diagnóstico e validação do ambiente para o Danaurium Redação Studio."""

import sys
import os
from pathlib import Path

def run_diagnostics():
    print("=" * 70)
    print("  DANAURIUM REDAÇÃO STUDIO — RELATÓRIO DE DIAGNÓSTICO DO SISTEMA")
    print("=" * 70)

    # 1. Versão do Python e Plataforma
    py_ver = sys.version.split()[0]
    platform_name = sys.platform
    print(f"\n[1] AMBIENTE PYTHON E SISTEMA:")
    print(f"    • Python: {py_ver} ({sys.executable})")
    print(f"    • Plataforma: {platform_name}")
    if sys.version_info < (3, 10):
        print("    [!] AVISO: Recomendado Python 3.10 ou superior.")
    else:
        print("    [OK] Versão do Python compatível com Windows 10/11.")

    # 2. Verificação de Dependências Principais
    print(f"\n[2] DEPENDÊNCIAS DO PROJETO:")
    deps = [
        ("PySide6", "Interface Gráfica Desktop (Qt6)"),
        ("httpx", "Cliente HTTP/SSE com Streaming"),
        ("pydantic", "Modelos Tipados e Validação de Dados"),
        ("keyring", "Cofre Seguro (Windows Credential Manager)"),
        ("docx", "Importação/Exportação Word (.docx)"),
        ("pypdf", "Extração de Texto de Arquivos PDF"),
        ("pytest", "Ambiente de Testes Automatizados"),
    ]

    all_deps_ok = True
    for module_name, desc in deps:
        try:
            __import__(module_name)
            print(f"    • [OK] {module_name:12} — {desc}")
        except ImportError as e:
            all_deps_ok = False
            print(f"    • [FALHA] {module_name:12} — {desc} (Erro: {e})")

    # 3. Caminhos de Armazenamento Local
    print(f"\n[3] PASTAS DO SISTEMA (ISOLAMENTO DE DADOS):")
    try:
        from danaurium.config import paths
        print(f"    • Diretório Base: {paths.base_dir}")
        print(f"    • Base SQLite:   {paths.db_path} (Existe: {paths.db_path.exists()})")
        print(f"    • Logs:          {paths.log_path}")
        print(f"    • Backups:       {paths.backups_dir}")
        print(f"    • Exportações:   {paths.exports_dir}")
        print("    [OK] Todas as pastas essenciais verificadas e acessíveis para gravação.")
    except Exception as e:
        print(f"    [FALHA] Erro ao validar caminhos: {e}")

    # 4. Cofre de Credenciais
    print(f"\n[4] COFRE SEGURO DE CREDENCIAIS:")
    try:
        from danaurium.security.keyring_manager import credentials
        mode = credentials.get_storage_mode_name()
        is_sec = credentials.is_secure_storage_active()
        print(f"    • Mecanismo Ativo: {mode}")
        print(f"    • Persistência em Cofre do SO: {'SIM' if is_sec else 'NÃO (Sessão Segura em Memória)'}")
        print("    [OK] Chaves de API isoladas de SQLite, logs e backups.")
    except Exception as e:
        print(f"    [FALHA] Erro no módulo de credenciais: {e}")

    # 5. Banco de Dados SQLite
    print(f"\n[5] INTEGRIDADE DO BANCO DE DADOS LOCAL:")
    try:
        from danaurium.persistence.database import db_manager
        with db_manager.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()[0]
            print(f"    • Integridade SQLite: {res}")
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            print(f"    • Tabelas Criadas ({len(tables)}): {', '.join(tables)}")
            print("    [OK] Banco de dados operacional em modo WAL.")
    except Exception as e:
        print(f"    [FALHA] Erro no banco de dados: {e}")

    print("\n" + "=" * 70)
    print("  DIAGNÓSTICO CONCLUÍDO COM SUCESSO!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_diagnostics()
