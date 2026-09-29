#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RD5 PageStudio 2.0.0
Editor de páginas HTML com a cara do antigo FrontPage (Office 2000/XP).

Uso:
    python rd5_pagestudio.py [arquivo.htm]

O código está organizado em pacotes:
    ps_core/  lógica pura (análise do HTML, conversão Design ⇄ HTML, busca,
              codificação de arquivos, histórico, configurações) — testável
              sem interface gráfica;
    ps_gui/   interface Tkinter (janela, menus, barras, painéis e diálogos);
    tests/    suíte de testes (pytest).

Novidades da versão 2.0 em relação à 1.0:
    • Blocos protegidos: tabelas, formulários, scripts, folhas de estilo, SVG e
      outros elementos avançados deixam de ser destruídos ao editar em Design;
    • Localizar e substituir de verdade (Ctrl+F / Ctrl+H / F3), com regex,
      palavra inteira e contador de ocorrências;
    • Desfazer/refazer no modo Design passa a incluir a formatação;
    • Codificação preservada (lê cp1252/latin-1 e grava na mesma codificação,
      promovendo para UTF-8 só quando necessário);
    • Arquivos recentes, recuperação automática (autosave) e aviso quando o
      arquivo é alterado por outro programa;
    • Lista de Pastas com filtro por nome e menu de contexto (novo, renomear,
      excluir, abrir no sistema);
    • Inserir tabela, comentário, data, caracteres especiais, link de e-mail;
    • Propriedades da página completas (título, descrição, palavras-chave,
      idioma e cores de fundo/texto/link);
    • Verificação de HTML, contagem de palavras e barra de status informativa.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter  # noqa: F401
except ImportError:
    sys.stderr.write(
        "\nO RD5 PageStudio precisa do Tkinter, que não está instalado neste Python.\n\n"
        "  Windows : reinstale o Python de https://www.python.org/downloads/\n"
        "            marcando a opção \"tcl/tk and IDLE\" (ela já vem marcada).\n"
        "  Debian/Ubuntu : sudo apt install python3-tk\n"
        "  Fedora  : sudo dnf install python3-tkinter\n"
        "  macOS (Homebrew) : brew install python-tk\n\n")
    raise SystemExit(1)

from ps_gui.app import main  # noqa: E402  (import após ajuste do sys.path)

if __name__ == "__main__":
    raise SystemExit(main())
