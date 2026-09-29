# -*- coding: utf-8 -*-
"""Testes da conversão Design ⇄ HTML e da preservação de blocos protegidos."""

import pytest

from conftest import design_html, load_design
from ps_core import (
    BULLET,
    DesignParser,
    ProtectedBlocks,
    design_to_html,
    extract_protected,
    merge_body,
)
from ps_core.design import NBSP_CH


SIMPLE = """<body>
<h1>Titulo</h1>
<p>Texto <b>negrito</b> e <i>italico</i>.</p>
<ul><li>um</li><li>dois</li></ul>
</body>"""


class TestExtracaoProtegida:
    def test_tabela_vira_bloco(self):
        html = '<body><p>antes</p><table border="1"><tr><td>A</td></tr></table><p>depois</p></body>'
        stripped, blocks = extract_protected(html)
        assert len(blocks) == 1
        assert blocks.items[0][0] == "table"
        assert blocks.items[0][1] == '<table border="1"><tr><td>A</td></tr></table>'
        assert "@@RD5PB0@@" in stripped
        assert "<td>" not in stripped
        assert "antes" in stripped and "depois" in stripped

    def test_formulario_com_aninhamento(self):
        html = '<form action="/x"><p>campo</p><input name="q"></form>'
        stripped, blocks = extract_protected(html)
        assert len(blocks) == 1
        assert blocks.items[0][1] == html

    def test_script_e_style(self):
        html = "<script>var a = '<table>';</script><style>p{color:red}</style>"
        _stripped, blocks = extract_protected(html)
        assert [t for t, _ in blocks.items] == ["script", "style"]
        assert blocks.items[0][1] == "<script>var a = '<table>';</script>"

    def test_div_nao_balanceada_nao_engole_documento(self):
        html = '<body><div><p>texto</p><p>mais</p></body>'
        stripped, blocks = extract_protected(html)
        assert blocks.items == []
        assert "mais" in stripped

    def test_comentario_com_tag_nao_confunde(self):
        html = "<!-- <table> fake </table> --><p>ok</p>"
        stripped, blocks = extract_protected(html)
        assert blocks.items == []
        assert "ok" in stripped

    def test_marcador_fica_em_linha_propria(self):
        html = "<body><table><tr><td>x</td></tr></table></body>"
        stripped, _blocks = extract_protected(html)
        lines = [l for l in stripped.splitlines() if "@@RD5PB0@@" in l]
        assert lines and lines[0].strip() == "@@RD5PB0@@"

    def test_tabela_nao_fechada_chega_ao_fim(self):
        html = "<body><p>a</p><table><tr><td>x</td></tr>"
        _stripped, blocks = extract_protected(html)
        assert len(blocks) == 1
        assert blocks.items[0][1].startswith("<table>")

    def test_lista_de_tags_e_rotulos(self):
        blocks = ProtectedBlocks([("table", "<table></table>"), ("form", "<form></form>")])
        assert blocks.tags == {"pb:0", "pb:1"}
        assert blocks.label(0) == "Tabela 1"
        assert blocks.label(1) == "Formulário 2"
        assert blocks.label(9) == "Conteúdo protegido"
        assert blocks.get(9) == ""


class TestAnaliseDesign:
    def test_titulo_e_texto(self):
        parser = DesignParser()
        parser.feed("<html><head><title>Minha &amp; página</title></head>"
                    "<body><h1>Cabeçalho</h1><p>Corpo</p></body></html>")
        parser.close()
        text = "".join(t for t, _ in parser.out)
        assert "Cabeçalho" in text and "Corpo" in text
        assert parser.title == "Minha & página"
        assert "Minha" not in text          # o <title> não entra no corpo

    def test_lista_recebe_marcador(self):
        parser = DesignParser()
        parser.feed("<ul><li>um</li><li>dois</li></ul>")
        parser.close()
        text = "".join(t for t, _ in parser.out)
        assert text.count(BULLET) == 2

    def test_head_e_scripts_nao_vazam(self):
        parser = DesignParser()
        parser.feed("<head><style>p{color:red}</style><meta charset='utf-8'></head>"
                    "<body><p>visível</p><script>alert(1)</script></body>")
        parser.close()
        text = "".join(t for t, _ in parser.out)
        assert "visível" in text
        assert "alert" not in text and "color:red" not in text

    def test_alinhamento_e_cor_viram_tags(self):
        parser = DesignParser()
        parser.feed('<p style="text-align: center"><font color="#ff0000">x</font></p>')
        parser.close()
        tags = {t for _txt, ts in parser.out for t in ts}
        assert "center" in tags and "c:#ff0000" in tags

    def test_imagem_vira_marcacao(self):
        parser = DesignParser()
        parser.feed('<p><img src="fotos/gato.png" alt="gato"></p>')
        parser.close()
        assert any("Imagem: gato.png" in t for t, _ in parser.out)
        assert any(any(g.startswith("img:fotos/gato.png") for g in ts) for _t, ts in parser.out)

    def test_espacos_multiplos_sao_preservados(self):
        parser = DesignParser()
        parser.feed("<p>a   b</p>")
        parser.close()
        text = "".join(t for t, _ in parser.out)
        assert NBSP_CH in text


class TestConversaoParaHtml:
    def test_titulo_e_paragrafo(self):
        out = design_html("<body><h1>Título</h1><p>Texto simples</p></body>")
        assert "<h1>Título</h1>" in out
        assert "<p>Texto&nbsp;simples</p>" in out

    def test_negrito_e_italico(self):
        out = design_html("<body><p>a <b>b</b> <i>c</i></p></body>")
        assert "<b>a</b>" not in out
        assert "<b>b</b>" in out
        assert "<i>c</i>" in out

    def test_link(self):
        out = design_html('<body><p><a href="https://x.y">clique</a></p></body>')
        assert '<a href="https://x.y">clique</a>' in out

    def test_lista(self):
        out = design_html("<body><ul><li>um</li><li>dois</li></ul></body>")
        assert "<ul>" in out and "<li>um</li>" in out and "<li>dois</li>" in out
        assert out.count("<ul>") == 1 and out.count("</ul>") == 1
        assert BULLET not in out

    def test_alinhamento(self):
        out = design_html('<body><p style="text-align: center">meio</p>'
                          '<p style="text-align: right">direita</p></body>')
        assert '<p style="text-align: center">' in out
        assert '<p style="text-align: right">' in out

    def test_linha_horizontal(self):
        out = design_html("<body><p>a</p><hr><p>b</p></body>")
        assert "<hr>" in out

    def test_pre_mantem_espacos_literais(self):
        out = design_html("<body><pre>a   b</pre></body>")
        assert "<pre>a   b</pre>" in out

    def test_caracteres_especiais_escapados(self):
        out = design_html("<body><p>5 &lt; 6 &amp; 7 &gt; 6</p></body>")
        assert "&lt;" in out and "&amp;" in out

    def test_documento_vazio(self):
        assert design_html("<body></body>") == ""


class TestFidelidade:
    """O que o 1.0 destruía: editar em Design não pode apagar elementos."""

    @pytest.mark.parametrize("bloco", [
        '<table border="1"><tr><td>A</td><td>B</td></tr></table>',
        '<form action="/busca"><input name="q"><button>ok</button></form>',
        "<script>var x = 1;</script>",
        "<style>p { color: red }</style>",
        '<iframe src="mapa.html"></iframe>',
        '<svg width="10"><circle r="5"></circle></svg>',
    ])
    def test_bloco_avancado_sobrevive_a_edicao(self, bloco):
        html = f"<body><p>texto</p>{bloco}<p>fim</p></body>"
        doc, blocks = load_design(html)

        # o usuário edita o parágrafo no modo Design
        doc.insert("1.3", " EDITADO")
        out = design_to_html(doc, blocks)

        assert bloco in out, f"bloco perdido: {bloco}"
        assert "EDITADO" in out
        assert "@@RD5PB" not in out

    def test_dois_blocos_preservados_na_ordem(self):
        html = ('<body><table id="a"><tr><td>1</td></tr></table><p>meio</p>'
                '<table id="b"><tr><td>2</td></tr></table></body>')
        out = design_html(html)
        assert out.index('id="a"') < out.index("meio") < out.index('id="b"')

    def test_bloco_apagado_no_design_nao_reaparece(self):
        html = '<body><p>a</p><table><tr><td>x</td></tr></table></body>'
        doc, blocks = load_design(html)
        lines = doc.get("1.0", "end-1c").split("\n")
        alvo = next(i for i, l in enumerate(lines, start=1) if "@@RD5PB0@@" in l)
        doc.delete(f"{alvo}.0", f"{alvo}.end+1c")
        out = design_to_html(doc, blocks)
        assert "<table" not in out

    def test_ciclo_e_estavel(self):
        html = ("<body><h1>Título</h1><p>Texto <b>forte</b> e <i>suave</i>.</p>"
                "<table><tr><td>célula</td></tr></table>"
                "<ul><li>item</li></ul><hr><p>fim</p></body>")
        first = design_html(html)
        second = design_html(merge_body(html, first))
        assert first == second

    def test_head_nao_e_tocado(self):
        html = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
                "<title>T</title><style>p{color:blue}</style></head>"
                "<body><p>a</p></body></html>")
        merged = merge_body(html, "<p>novo</p>")
        assert '<style>p{color:blue}</style>' in merged
        assert "<title>T</title>" in merged
        assert "<p>novo</p>" in merged


class TestMergeBody:
    def test_substitui_apenas_o_corpo(self):
        html = "<html><head><title>T</title></head><body><p>velho</p></body></html>"
        out = merge_body(html, "<p>novo</p>")
        assert "<p>velho</p>" not in out
        assert "<p>novo</p>" in out
        assert "<title>T</title>" in out

    def test_documento_sem_body_ganha_estrutura(self):
        out = merge_body("<h1>solto</h1>", "<p>novo</p>", title="Página")
        assert "<body>" in out and "</body>" in out
        assert "<p>novo</p>" in out
        assert "<title>Página</title>" in out

    def test_documento_sem_body_mantem_head_original(self):
        out = merge_body("<head><title>Original</title></head>", "<p>novo</p>")
        assert "<title>Original</title>" in out
