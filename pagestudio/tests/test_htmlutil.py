# -*- coding: utf-8 -*-
"""Testes de leitura/gravacao, codificacao, metadados, tabela e validacao."""

import pytest

from ps_core import (
    body_of,
    count_words,
    declared_charset,
    get_meta,
    get_title,
    normalize_newlines,
    read_document,
    set_body_attrs,
    set_charset,
    set_meta,
    set_title,
    table_html,
    validate_html,
    write_text,
)


class TestLeitura:
    def test_utf8_sem_declaracao(self, tmp_path):
        p = tmp_path / "a.htm"
        p.write_bytes("<p>Acentuação</p>".encode("utf-8"))
        doc = read_document(str(p))
        assert doc.text == "<p>Acentuação</p>"
        assert doc.encoding == "utf-8"
        assert doc.bom is False

    def test_utf8_com_bom(self, tmp_path):
        p = tmp_path / "b.htm"
        p.write_bytes(b"\xef\xbb\xbf<p>x</p>")
        doc = read_document(str(p))
        assert doc.text == "<p>x</p>"
        assert doc.bom is True

    def test_cp1252_declarado_no_meta(self, tmp_path):
        p = tmp_path / "c.htm"
        p.write_bytes('<meta charset="windows-1252"><p>ação — “aspas”</p>'.encode("cp1252"))
        doc = read_document(str(p))
        assert "ação" in doc.text and "“aspas”" in doc.text
        assert doc.encoding == "cp1252"

    def test_charset_http_equiv(self, tmp_path):
        p = tmp_path / "d.htm"
        p.write_bytes(
            '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">'
            "<p>ç</p>".encode("latin-1"))
        doc = read_document(str(p))
        assert "ç" in doc.text
        assert doc.encoding == "latin-1"

    def test_charset_desconhecido_usa_fallback(self, tmp_path):
        p = tmp_path / "e.htm"
        p.write_bytes('<meta charset="x-mac-romanos"><p>texto</p>'.encode("utf-8"))
        doc = read_document(str(p))
        assert "texto" in doc.text

    def test_crlf_vira_lf(self, tmp_path):
        p = tmp_path / "f.htm"
        p.write_bytes(b"<p>a</p>\r\n<p>b</p>\r\n")
        assert read_document(str(p)).text == "<p>a</p>\n<p>b</p>\n"

    def test_arquivo_inexistente(self, tmp_path):
        with pytest.raises(OSError):
            read_document(str(tmp_path / "nao_existe.htm"))

    def test_declared_charset(self):
        assert declared_charset(b'<meta charset="UTF-8">') == "utf-8"
        assert declared_charset(b"<html>") is None


class TestGravacao:
    def test_preserva_codificacao_original(self, tmp_path):
        p = tmp_path / "g.htm"
        enc, promoted = write_text(str(p), "<p>ação</p>", "cp1252")
        assert enc == "cp1252" and promoted is False
        assert p.read_bytes() == "<p>ação</p>".encode("cp1252")

    def test_promove_para_utf8_quando_nao_cabe(self, tmp_path):
        p = tmp_path / "h.htm"
        html = '<meta charset="windows-1252"><p>ação \u20ac € ✓</p>'
        enc, promoted = write_text(str(p), html, "cp1252")
        assert enc == "utf-8" and promoted is True
        data = p.read_bytes().decode("utf-8")
        assert 'charset="utf-8"' in data
        assert "✓" in data

    def test_bom(self, tmp_path):
        p = tmp_path / "i.htm"
        write_text(str(p), "<p>x</p>", "utf-8", bom=True)
        assert p.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_ida_e_volta(self, tmp_path):
        p = tmp_path / "j.htm"
        write_text(str(p), "<p>Acentuação €</p>", "utf-8")
        assert read_document(str(p)).text == "<p>Acentuação €</p>"

    def test_set_charset(self):
        assert 'charset="utf-8"' in set_charset('<meta charset="cp1252">', "utf-8")
        assert "charset" in set_charset("<html></html>", "utf-8")

    def test_normalize_newlines(self):
        assert normalize_newlines("a\r\nb\rc") == "a\nb\nc"


class TestMetadados:
    HTML = ('<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">'
            "<title>Velho</title></head><body><p>x</p></body></html>")

    def test_get_title(self):
        assert get_title(self.HTML) == "Velho"
        assert get_title("<html></html>") == ""

    def test_title_desescapado(self):
        assert get_title("<title>A &amp; B</title>") == "A & B"

    def test_set_title_existente(self):
        out = set_title(self.HTML, "Novo título")
        assert "<title>Novo título</title>" in out
        assert out.count("<title>") == 1

    def test_set_title_cria_tag(self):
        out = set_title("<html><head></head><body></body></html>", "T")
        assert "<title>T</title>" in out

    def test_set_meta_nova_e_atualizacao(self):
        out = set_meta(self.HTML, "description", "Descrição da página")
        assert 'name="description"' in out and 'content="Descrição da página"' in out
        out2 = set_meta(out, "description", "Outra")
        assert out2.count('name="description"') == 1
        assert get_meta(out2, "description") == "Outra"

    def test_meta_dentro_do_head(self):
        out = set_meta(self.HTML, "keywords", "a, b")
        assert out.index('name="keywords"') < out.index("</head>")

    def test_get_meta_vazio(self):
        assert get_meta(self.HTML, "keywords") == ""

    def test_set_body_attrs(self):
        out = set_body_attrs("<body><p>x</p></body>", bgcolor="#FFFFFF", text="#000000")
        assert 'bgcolor="#FFFFFF"' in out and 'text="#000000"' in out
        out2 = set_body_attrs(out, bgcolor="#000000")
        assert out2.count("bgcolor") == 1
        assert 'bgcolor="#000000"' in out2

    def test_body_of(self):
        assert body_of(self.HTML).strip() == "<p>x</p>"


class TestTabela:
    def test_estrutura(self):
        html = table_html(2, 3, border=1, header=True)
        assert html.startswith("<table ")
        assert html.count("<tr>") == 2
        assert html.count("<td") == 3
        assert html.count("<th") == 3
        assert html.endswith("</table>")

    def test_sem_cabecalho(self):
        html = table_html(2, 2, header=False)
        assert "<th" not in html
        assert html.count("<td") == 4

    def test_borda_zero(self):
        assert 'border="0"' in table_html(1, 1, border=0)

    def test_minimo_uma_linha(self):
        assert table_html(0, 0).count("<tr>") == 1


class TestValidacao:
    def test_documento_completo(self):
        html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>T</title></head>'
                "<body><p>ok</p></body></html>")
        assert validate_html(html) == []

    def test_falta_doctype_charset_titulo(self):
        issues = validate_html("<html><body><p>x</p></body></html>")
        texto = " ".join(issues)
        assert "DOCTYPE" in texto and "charset" in texto and "title" in texto

    def test_tag_aberta(self):
        html = '<!DOCTYPE html><meta charset="utf-8"><title>T</title><body><p>texto</body>'
        issues = validate_html(html)
        assert any("<p>" in i for i in issues)

    def test_fechamento_sobra(self):
        html = '<!DOCTYPE html><meta charset="utf-8"><title>T</title><body></div></body>'
        assert any("</div>" in i for i in validate_html(html))

    def test_aninhamento_errado(self):
        html = ('<!DOCTYPE html><meta charset="utf-8"><title>T</title>'
                "<body><b><i>x</b></i></body>")
        assert validate_html(html)

    def test_atributo_sem_aspas(self):
        html = ('<!DOCTYPE html><meta charset="utf-8"><title>T</title>'
                "<body><p class=x>y</p></body>")
        assert any("aspas" in i for i in validate_html(html))

    def test_script_nao_confunde(self):
        html = ('<!DOCTYPE html><meta charset="utf-8"><title>T</title><body>'
                "<script>if (a < b) { document.write('<p>'); }</script></body>")
        assert validate_html(html) == []

    def test_comentario_ignorado(self):
        html = ('<!DOCTYPE html><meta charset="utf-8"><title>T</title><body>'
                "<!-- <div> --><p>x</p></body>")
        assert validate_html(html) == []

    def test_elementos_vazios(self):
        html = ('<!DOCTYPE html><meta charset="utf-8"><title>T</title><body>'
                "<p>a<br>b<img src='x.png'><hr></p></body>")
        assert validate_html(html) == []


class TestContagem:
    def test_count_words(self):
        assert count_words("um dois três") == 3
        assert count_words("") == 0
        assert count_words("   ") == 0
