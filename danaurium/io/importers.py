"""Importação de conteúdos a partir de texto puro, TXT, DOCX e PDFs com camada de texto."""

import os
from pathlib import Path
from typing import Dict, Any, Tuple


class ImportErrorWithDiagnostics(Exception):
    """Exceção levantada com diagnóstico claro para o usuário em caso de falha de importação."""
    pass


def import_txt(file_path: Path) -> str:
    """Lê arquivo TXT testando UTF-8 e recuando para Latin-1/CP1252 caso necessário."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception as e:
            raise ImportErrorWithDiagnostics(f"Falha de codificação ao abrir TXT: {e}")

    if not content.strip():
        raise ImportErrorWithDiagnostics("O arquivo TXT selecionado está completamente vazio.")
    return content.strip()


def import_docx(file_path: Path) -> str:
    """Extrai parágrafos de um documento Word (.docx)."""
    try:
        from docx import Document
        doc = Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        content = "\n\n".join(paragraphs)
        if not content.strip():
            raise ImportErrorWithDiagnostics("O documento DOCX não possui parágrafos de texto legíveis.")
        return content
    except ImportErrorWithDiagnostics:
        raise
    except Exception as e:
        raise ImportErrorWithDiagnostics(f"Erro ao processar arquivo DOCX: {e}")


def import_pdf(file_path: Path) -> str:
    """Extrai texto de PDF com camada de texto selecionável.
    
    Avisa claramente caso o PDF seja digitalizado (imagem escaneada) e exija OCR.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(str(file_path))
        extracted_pages = []
        for idx, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(page_text.strip())

        full_text = "\n\n".join(extracted_pages)
        if not full_text.strip():
            raise ImportErrorWithDiagnostics(
                "O arquivo PDF selecionado não contém camada de texto selecionável "
                "(trata-se de um PDF escaneado ou composto apenas por imagens). "
                "Para utilizá-lo, execute previamente o reconhecimento de caracteres (OCR) no documento."
            )

        return full_text
    except ImportErrorWithDiagnostics:
        raise
    except Exception as e:
        raise ImportErrorWithDiagnostics(f"Erro ao analisar arquivo PDF: {e}")


def import_file(file_path: Path) -> Tuple[str, str]:
    """Identifica a extensão do arquivo e executa a importação correspondente.
    
    Retorna uma tupla (conteudo_texto, sugestao_titulo).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    ext = file_path.suffix.lower()
    title_suggestion = file_path.stem.replace("_", " ").replace("-", " ").title()

    if ext == ".txt":
        text = import_txt(file_path)
    elif ext == ".docx":
        text = import_docx(file_path)
    elif ext == ".pdf":
        text = import_pdf(file_path)
    else:
        # Tentar ler como texto plano por padrão
        text = import_txt(file_path)

    return text, title_suggestion
