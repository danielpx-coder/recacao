# -*- coding: utf-8 -*-
"""Testes do motor de localizar/substituir e do histórico de desfazer."""

from plaindoc import PlainDoc
from ps_core import DesignHistory, MatchFinder, offset_to_index, replace_all


def doc_with(text):
    return PlainDoc(text)


class TestIndices:
    def test_offset_para_indice(self):
        assert offset_to_index("abc\ndef\nghi", 0) == "1.0"
        assert offset_to_index("abc\ndef\nghi", 3) == "1.3"
        assert offset_to_index("abc\ndef\nghi", 4) == "2.0"
        assert offset_to_index("abc\ndef\nghi", 9) == "3.1"

    def test_limites(self):
        assert offset_to_index("abc", 99) == "1.3"
        assert offset_to_index("abc", -5) == "1.0"


class TestBusca:
    def test_encontra_para_frente(self):
        doc = doc_with("gato e gato e cachorro")
        f = MatchFinder(doc, "gato")
        m = f.find("1.0")
        assert (m.start, m.end) == ("1.0", "1.4")
        m2 = f.find(m.end)
        assert m2.start == "1.7"

    def test_sem_ocorrencia(self):
        assert MatchFinder(doc_with("abc"), "xyz").find("1.0") is None

    def test_ignora_maiusculas_por_padrao(self):
        doc = doc_with("GATO gato")
        assert MatchFinder(doc, "gato").count() == 2
        assert MatchFinder(doc, "gato", case=True).count() == 1

    def test_volta_ao_inicio(self):
        doc = doc_with("a b a")
        f = MatchFinder(doc, "a")
        m = f.find("1.5")           # depois da última ocorrência
        assert m.start == "1.0"

    def test_para_tras(self):
        doc = doc_with("a b a")
        f = MatchFinder(doc, "a")
        m = f.find("1.2", backward=True)
        assert m.start == "1.0"

    def test_palavra_inteira(self):
        doc = doc_with("gato gatozinho gatão")
        assert MatchFinder(doc, "gato", whole=True).count() == 1
        assert MatchFinder(doc, "gato").count() == 2

    def test_regex(self):
        doc = doc_with("2024 2025 20x6")
        f = MatchFinder(doc, r"\d{4}", regex=True)
        assert f.count() == 2

    def test_regex_invalida(self):
        f = MatchFinder(doc_with("abc"), "([", regex=True)
        assert f.error
        assert f.find("1.0") is None
        assert f.count() == 0

    def test_multilinha(self):
        doc = doc_with("primeira\nsegunda linha\nterceira")
        f = MatchFinder(doc, "linha")
        m = f.find("1.0")
        assert m.start == "2.8" and m.end == "2.13"

    def test_find_all(self):
        doc = doc_with("x x x")
        spans = MatchFinder(doc, "x").spans()
        assert spans == [(0, 1), (2, 3), (4, 5)]


class TestSubstituicao:
    def test_replace_all_simples(self):
        doc = doc_with("casa casaco casa")
        total = replace_all(doc, "casa", "lar")
        assert total == 3          # "casaco" contém "casa" (sem palavra inteira)
        assert doc.get("1.0", "end") == "lar larco lar"

    def test_replace_all_trocando_tamanho(self):
        doc = doc_with("aaa bbb aaa")
        assert replace_all(doc, "aaa", "x") == 2
        assert doc.get("1.0", "end") == "x bbb x"

    def test_replace_all_com_regex(self):
        doc = doc_with("a1 b22 c333")
        total = replace_all(doc, r"\d+", "#", regex=True)
        assert total == 3
        assert doc.get("1.0", "end") == "a# b# c#"

    def test_replace_all_palavra_inteira(self):
        doc = doc_with("rio riozinho")
        assert replace_all(doc, "rio", "R", whole=True) == 1
        assert doc.get("1.0", "end") == "R riozinho"

    def test_replace_all_preserva_tags(self):
        doc = doc_with("texto velho")
        doc.tag_add("bold", "1.0", "1.5")
        replace_all(doc, "velho", "novo")
        assert doc.get("1.0", "end") == "texto novo"
        assert doc.tag_ranges("bold") == ("1.0", "1.5")

    def test_replace_all_padrao_vazio(self):
        doc = doc_with("abc")
        assert replace_all(doc, "", "x") == 0
        assert doc.get("1.0", "end") == "abc"

    def test_replace_all_nao_reprocessa_o_resultado(self):
        doc = doc_with("a b a")
        assert replace_all(doc, "a", "aa") == 2
        assert doc.get("1.0", "end") == "aa b aa"


class TestHistorico:
    def test_desfazer_texto(self):
        doc = doc_with("original")
        h = DesignHistory(doc)
        h.push()
        doc.insert("end", " editado")
        assert doc.get("1.0", "end-1c") == "original editado"
        h.undo()
        assert doc.get("1.0", "end-1c") == "original"

    def test_refazer(self):
        doc = doc_with("a")
        h = DesignHistory(doc)
        h.push()
        doc.insert("end", "b")
        h.undo()
        assert doc.get("1.0", "end-1c") == "a"
        h.redo()
        assert doc.get("1.0", "end-1c") == "ab"

    def test_desfazer_formatacao(self):
        """A falha do 1.0: formatar e dar Ctrl+Z não voltava nada."""
        doc = doc_with("texto")
        h = DesignHistory(doc)
        h.push()
        doc.tag_add("bold", "1.0", "1.5")
        assert doc.tag_ranges("bold")
        h.undo()
        assert doc.tag_ranges("bold") == ()

    def test_desfazer_multilinha_com_tags(self):
        doc = doc_with("um\ndois\ntrês")
        doc.tag_add("h1", "1.0", "1.2")
        doc.tag_add("bold", "2.0", "2.4")
        h = DesignHistory(doc)
        h.push()
        doc.delete("1.0", "end")
        doc.insert("1.0", "tudo diferente")
        h.undo()
        assert doc.get("1.0", "end-1c") == "um\ndois\ntrês"
        assert doc.tag_ranges("h1") == ("1.0", "1.2")
        assert doc.tag_ranges("bold") == ("2.0", "2.4")

    def test_estado_inicial(self):
        h = DesignHistory(doc_with("x"))
        assert not h.can_undo() and not h.can_redo()
        assert h.undo() is None and h.redo() is None

    def test_limite_de_estados(self):
        doc = doc_with("0")
        h = DesignHistory(doc, limit=3)
        for i in range(1, 8):
            h.push()
            doc.insert("end", str(i))
        assert len(h) == 3
        # só os 3 últimos estados sobrevivem: o mais antigo é "01234"
        assert h._undo[0][0] == "01234"
        for _ in range(10):
            h.undo()
        assert doc.get("1.0", "end-1c") == "01234"
        assert not h.can_undo()

    def test_nova_edicao_limpa_refazer(self):
        doc = doc_with("a")
        h = DesignHistory(doc)
        h.push(); doc.insert("end", "b")
        h.undo()
        assert h.can_redo()
        h.push(); doc.insert("end", "c")
        assert not h.can_redo()

    def test_clear(self):
        doc = doc_with("a")
        h = DesignHistory(doc)
        h.push()
        h.clear()
        assert not h.can_undo()
