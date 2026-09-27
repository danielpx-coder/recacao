"""Testes dos 14 produtos editoriais, diretrizes e cálculo de tempo para rádio."""

from danaurium.editorial.products import EDITORIAL_PRODUCTS
from danaurium.editorial.radio import calculate_radio_duration
from danaurium.editorial.rules import build_generation_prompts


def test_all_14_products_defined():
    expected_ids = [
        "reportagem", "release", "resumo", "cinco_titulos", "subtitulo",
        "spot_radio", "roteiro_dois_locutores", "whatsapp", "instagram_facebook",
        "linkedin", "publicacao_curta", "texto_card", "roteiro_video_curto", "html_wordpress"
    ]
    assert len(EDITORIAL_PRODUCTS) == 14
    for p_id in expected_ids:
        assert p_id in EDITORIAL_PRODUCTS
        p = EDITORIAL_PRODUCTS[p_id]
        assert p.name != ""
        assert p.guidelines_prompt != ""
        assert p.default_char_limit > 0


def test_radio_duration_calculation_with_pauses_and_cues():
    # Texto falado com ~45 palavras (a 135 ppm = 20 segundos falados)
    # + 1 pausa de 2 segundos [PAUSA 2s]
    # + 1 vinheta sonora [VINHETA] (+1.5s)
    # Total esperado: ~23 a 24 segundos
    script = (
        "[VINHETA DE ABERTURA]\n"
        "O Ministério da Educação anunciou nesta terça-feira a expansão da conectividade para mais de "
        "doze mil escolas públicas em todo o país. São quatrocentos e cinquenta milhões de reais investidos "
        "em laboratórios de informática e internet de alta velocidade. "
        "[PAUSA 2s]\n"
        "Mais informações em mec ponto gov ponto br."
    )

    res = calculate_radio_duration(script, reading_speed_wpm=135)
    assert res["pauses_seconds"] == 2.0
    assert res["sound_cues_seconds"] == 1.5
    assert 20 <= res["estimated_seconds"] <= 26
    assert res["formatted_time"].startswith("00:")
    assert "135 ppm" in res["disclaimer"]


def test_build_generation_prompts_contains_required_rules():
    project_data = {
        "title": "Expansão de Escolas",
        "raw_text": "Texto da matéria original do MEC.",
        "extracted_facts": [{"fact": "R$ 450 milhões investidos", "source_ref": "Parágrafo 1", "is_pinned": True}],
        "tone": "Formal e Institucional",
        "audience": "Gestores Escolares",
        "mandatory_words": "Inep, 2026",
        "forbidden_expressions": "divisor de águas",
        "char_limit_preset": 1400,
    }

    prompts = build_generation_prompts("reportagem", project_data)
    sys_prompt = prompts["system_prompt"]
    user_prompt = prompts["user_prompt"]

    assert "jornalista" in sys_prompt.lower()
    assert "portuguesa brasileira" in sys_prompt.lower()

    assert "Formal e Institucional" in user_prompt
    assert "Gestores Escolares" in user_prompt
    assert "Inep, 2026" in user_prompt
    assert "divisor de águas" in user_prompt
    assert "1400 caracteres" in user_prompt
    assert "R$ 450 milhões investidos" in user_prompt
