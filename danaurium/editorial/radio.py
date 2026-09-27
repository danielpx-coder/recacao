"""Cálculo de duração e ritmo para spots de rádio e roteiros com locutores."""

import re
from typing import Dict, Any


def calculate_radio_duration(
    script_text: str,
    reading_speed_wpm: int = 135,
    institutional_signature: str = "",
) -> Dict[str, Any]:
    """Calcula a duração estimada de um texto radiofônico em segundos.
    
    Parâmetros:
    - reading_speed_wpm: Palavras por minuto (padrão profissional para rádio brasileiro: 130 a 140 ppm).
    - script_text: Texto do roteiro incluindo rubricas como [PAUSA 1s], [TRILHA], etc.
    - institutional_signature: Assinatura ou encerramento institucional.
    """
    if not script_text:
        return {
            "estimated_seconds": 0,
            "spoken_words_count": 0,
            "pauses_seconds": 0,
            "sound_cues_seconds": 0,
            "reading_speed_wpm": reading_speed_wpm,
            "formatted_time": "00:00",
            "disclaimer": "Texto vazio.",
        }

    # 1. Detectar e somar pausas explícitas em segundos: [PAUSA 1s], [PAUSA 2.5s], etc.
    pause_matches = re.findall(r"\[PAUSA\s+([0-9\.]+)\s*s?\]", script_text, re.IGNORECASE)
    pauses_seconds = sum(float(p) for p in pause_matches)

    # 2. Detectar rubricas de efeitos sonoros / trilhas: [TRILHA...], [VINHETA...], [BG...]
    # Cada entrada ou corte de efeito sonoro consome em média 1.5 segundo
    cue_matches = re.findall(r"\[(TRILHA|VINHETA|EFEITO|SFX|SOBE|BG)[^\]]*\]", script_text, re.IGNORECASE)
    sound_cues_seconds = len(cue_matches) * 1.5

    # 3. Remover rubricas entre colchetes para contar apenas as palavras efetivamente faladas
    spoken_text = re.sub(r"\[[^\]]*\]", " ", script_text)
    if institutional_signature:
        spoken_text += f" {institutional_signature}"

    # Limpeza e contagem de palavras faladas
    words = [w for w in spoken_text.strip().split() if w and not w.startswith("[")]
    spoken_words_count = len(words)

    # 4. Cálculo do tempo falado (palavras / (ppm / 60))
    words_per_second = reading_speed_wpm / 60.0
    spoken_seconds = spoken_words_count / words_per_second if words_per_second > 0 else 0

    total_seconds = int(round(spoken_seconds + pauses_seconds + sound_cues_seconds))

    minutes = total_seconds // 60
    seconds = total_seconds % 60
    formatted_time = f"{minutes:02d}:{seconds:02d}"

    disclaimer = (
        f"Estimativa baseada no ritmo de {reading_speed_wpm} ppm (palavras por minuto), "
        f"incluindo {spoken_words_count} palavras faladas, {pauses_seconds:.1f}s de pausas e rubricas técnicas. "
        "A duração real varia conforme a entonação do locutor e edição sonora final."
    )

    return {
        "estimated_seconds": total_seconds,
        "spoken_words_count": spoken_words_count,
        "pauses_seconds": pauses_seconds,
        "sound_cues_seconds": sound_cues_seconds,
        "reading_speed_wpm": reading_speed_wpm,
        "formatted_time": formatted_time,
        "disclaimer": disclaimer,
    }
