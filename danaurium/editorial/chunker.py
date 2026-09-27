"""Segmentação de textos longos preservando referências sem truncamento silencioso."""

from typing import List, Dict, Any


def chunk_text_by_paragraphs(
    text: str,
    max_chunk_chars: int = 12000,
    overlap_paragraphs: int = 1,
) -> List[Dict[str, Any]]:
    """Divide um texto extenso em blocos lógicos preservando limites de parágrafo e referências.
    
    Nunca trunca silenciosamente o conteúdo de uma matéria longa.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: List[Dict[str, Any]] = []
    current_paras: List[str] = []
    current_chars = 0
    start_para_idx = 1

    for idx, p in enumerate(paragraphs, 1):
        p_len = len(p)
        if current_paras and (current_chars + p_len > max_chunk_chars):
            chunk_content = "\n\n".join(current_paras)
            chunks.append({
                "chunk_index": len(chunks) + 1,
                "text": chunk_content,
                "start_paragraph": start_para_idx,
                "end_paragraph": idx - 1,
                "char_count": len(chunk_content),
                "is_multisection": True,
            })
            # Overlap para manter contexto de transição
            overlap = paragraphs[max(0, idx - 1 - overlap_paragraphs):idx - 1]
            current_paras = list(overlap)
            current_paras.append(p)
            current_chars = sum(len(x) for x in current_paras)
            start_para_idx = max(1, idx - overlap_paragraphs)
        else:
            current_paras.append(p)
            current_chars += p_len

    if current_paras:
        chunk_content = "\n\n".join(current_paras)
        chunks.append({
            "chunk_index": len(chunks) + 1,
            "text": chunk_content,
            "start_paragraph": start_para_idx,
            "end_paragraph": len(paragraphs),
            "char_count": len(chunk_content),
            "is_multisection": len(chunks) > 0,
        })

    return chunks
