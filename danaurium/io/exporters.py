"""Exportação de produtos editoriais para TXT, DOCX, Markdown, WordPress HTML e pacote ZIP."""

import html
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


def sanitize_for_wordpress_html(raw_content: str, title: str = "") -> str:
    """Converte texto editorial em fragmento HTML limpo e semântico para WordPress.
    
    Regras estritas:
    - Retorna apenas o fragmento (sem <html>, <head> ou <body>).
    - Não inclui scripts, iframes ou estilos inline.
    - Usa classes padrão do editor de blocos do WordPress (Gutenberg).
    """
    lines = [line.strip() for line in raw_content.split("\n")]
    html_parts: List[str] = []

    if title:
        escaped_title = html.escape(title)
        html_parts.append(f'<h2 class="wp-block-heading">{escaped_title}</h2>')

    in_list = False
    in_quote = False
    quote_lines: List[str] = []

    for line in lines:
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_quote:
                quote_text = "<br>".join(quote_lines)
                html_parts.append(f'<blockquote class="wp-block-quote"><p>{quote_text}</p></blockquote>')
                in_quote = False
                quote_lines = []
            continue

        # Detectar início de citação em bloco
        if line.startswith("> ") or (line.startswith('"') and line.endswith('"') and len(line) > 60):
            clean_q = line.lstrip("> ").strip().strip('"')
            in_quote = True
            quote_lines.append(html.escape(clean_q))
            continue

        # Detectar itens de lista
        if line.startswith("- ") or line.startswith("* ") or re.match(r"^\d+\.\s+", line):
            if not in_list:
                html_parts.append('<ul class="wp-block-list">')
                in_list = True
            item_text = re.sub(r"^(\-|\*|\d+\.)\s+", "", line)
            html_parts.append(f"<li>{html.escape(item_text)}</li>")
            continue

        if in_list:
            html_parts.append("</ul>")
            in_list = False

        if in_quote:
            quote_text = "<br>".join(quote_lines)
            html_parts.append(f'<blockquote class="wp-block-quote"><p>{quote_text}</p></blockquote>')
            in_quote = False
            quote_lines = []

        # Detectar subtítulos intermediários (Markdown ## ou linhas curtas em caixa alta)
        if line.startswith("## ") or line.startswith("### "):
            heading_txt = line.lstrip("#").strip()
            html_parts.append(f'<h3 class="wp-block-heading">{html.escape(heading_txt)}</h3>')
            continue

        # Parágrafo comum de texto
        escaped_line = html.escape(line)
        # Converter negrito simples **texto** para <strong>
        escaped_line = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", escaped_line)
        # Converter itálico simples *texto* para <em>
        escaped_line = re.sub(r"\*([^\*]+)\*", r"<em>\1</em>", escaped_line)
        html_parts.append(f"<p>{escaped_line}</p>")

    if in_list:
        html_parts.append("</ul>")
    if in_quote:
        quote_text = "<br>".join(quote_lines)
        html_parts.append(f'<blockquote class="wp-block-quote"><p>{quote_text}</p></blockquote>')

    return "\n".join(html_parts)


def export_txt(target_path: Path, content: str):
    """Exporta como TXT com codificação UTF-8 preservando acentuação brasileira."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)


def export_markdown(target_path: Path, title: str, content: str):
    """Exporta em formato Markdown (.md) estruturado."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    md_content = f"# {title}\n\n{content}\n"
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(md_content)


def export_docx(target_path: Path, title: str, content: str):
    """Exporta para documento Microsoft Word (.docx) formatado."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    from docx import Document
    from docx.shared import Pt, Inches

    doc = Document()
    if title:
        p_title = doc.add_heading(title, level=1)
        p_title.style.font.size = Pt(18)

    for paragraph in content.split("\n\n"):
        p_clean = paragraph.strip()
        if not p_clean:
            continue
        if p_clean.startswith(">"):
            # Citação em bloco
            q = doc.add_paragraph(p_clean.lstrip("> ").strip())
            q.style = "Intense Quote"
        elif p_clean.startswith("#"):
            doc.add_heading(p_clean.lstrip("#").strip(), level=2)
        else:
            doc.add_paragraph(p_clean)

    doc.save(str(target_path))


def export_wordpress_html(target_path: Path, title: str, content: str):
    """Exporta fragmento sanitizado em HTML para WordPress."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    clean_html = sanitize_for_wordpress_html(content, title=title)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(clean_html)


def export_project_zip(
    target_zip_path: Path,
    project_title: str,
    products_content: Dict[str, str],
) -> Path:
    """Gera um pacote ZIP organizado com todos os produtos editoriais do projeto."""
    target_zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(target_zip_path), "w", zipfile.ZIP_DEFLATED) as zip_f:
        # 1. Exportar cada produto individualmente nos formatos adequados
        for idx, (prod_id, text_content) in enumerate(products_content.items(), 1):
            base_filename = f"{idx:02d}_{prod_id}"
            
            # Sempre inclui TXT
            zip_f.writestr(f"{base_filename}.txt", text_content.encode("utf-8"))
            # Inclui Markdown
            zip_f.writestr(f"{base_filename}.md", f"# {project_title} - {prod_id}\n\n{text_content}".encode("utf-8"))
            
            # Se for HTML ou matéria jornalística, inclui HTML sanitizado para WordPress
            if prod_id == "html_wordpress":
                wp_html = sanitize_for_wordpress_html(text_content, title=project_title)
                zip_f.writestr(f"{base_filename}.html", wp_html.encode("utf-8"))
            elif prod_id in ("reportagem", "release"):
                wp_html = sanitize_for_wordpress_html(text_content, title=f"{project_title} - {prod_id}")
                zip_f.writestr(f"{base_filename}_wordpress.html", wp_html.encode("utf-8"))

        # 2. Manifesto do pacote
        manifest = (
            f"DANAURIUM REDAÇÃO STUDIO - PACOTE DE EXPORTAÇÃO\n"
            f"Projeto: {project_title}\n"
            f"Total de produtos: {len(products_content)}\n"
            f"Produtos inclusos: {', '.join(products_content.keys())}\n"
            f"Codificação: UTF-8 (Português Brasileiro)\n"
        )
        zip_f.writestr("manifesto.txt", manifest.encode("utf-8"))

    return target_zip_path
