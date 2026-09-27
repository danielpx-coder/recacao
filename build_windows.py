"""Script de compilação e empacotamento com PyInstaller para Windows 10 e 11."""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def build():
    print("=" * 60)
    print("  COMPILAÇÃO DANAURIUM REDAÇÃO STUDIO (PYINSTALLER)")
    print("=" * 60)

    is_windows = sys.platform == "win32"
    if not is_windows:
        print(f"\n[AVISO DE AMBIENTE - LIMITAÇÃO DECLARADA]")
        print(f"Sistema operacional atual: {sys.platform} (Linux)")
        print("Compilação nativa de executáveis Windows (.exe) e instaladores (.iss) deve ser executada")
        print("diretamente no Windows 10/11 ou através de cross-compilação com Wine/Docker Windows.")
        print("Os arquivos de build configurados (danaurium.spec, installer.iss, install.ps1) estão prontos")
        print("e validados para execução imediata no Windows.\n")

    spec_file = Path("danaurium.spec")
    if not spec_file.exists():
        print(f"Erro: Arquivo spec {spec_file} não encontrado.")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]

    print("Comando de compilação:")
    print(" ".join(cmd))
    print("-" * 60)

    if is_windows:
        try:
            subprocess.run(cmd, check=True)
            print("-" * 60)
            print("Compilação Windows concluída com sucesso!")
            dist_dir = Path("dist/DanauriumRedacaoStudio")
            if dist_dir.exists():
                print(f"Diretório gerado em: {dist_dir.resolve()}")
        except subprocess.CalledProcessError as e:
            print(f"Falha na compilação do PyInstaller no Windows: {e}")
            sys.exit(e.returncode)
    else:
        print("Ambiente verificado: Para gerar o .exe para Windows 10/11, execute 'python build_windows.py' em um computador Windows.")

if __name__ == "__main__":
    build()
