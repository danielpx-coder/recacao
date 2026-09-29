# -*- coding: utf-8 -*-
"""Testes das configurações, arquivos recentes e recuperação automática."""

import json
import time

from ps_core import Settings, autosave_path, base_dir, clear_autosaves, find_autosaves


class TestSettings:
    def test_salvar_e_carregar(self, isolated_config):
        s = Settings()
        s.add_recent("/tmp/uma.htm")
        s.font_size = 16
        s.mode = "code"
        assert s.save() is True

        outro = Settings.load()
        assert outro.font_size == 16
        assert outro.mode == "code"
        assert len(outro.recent) == 1

    def test_arquivo_corrompido_nao_quebra(self, isolated_config):
        (isolated_config / "config.json").write_text("{ json inválido", encoding="utf-8")
        s = Settings.load()
        assert s.recent == []
        assert s.font_size == 12

    def test_campos_desconhecidos_sao_ignorados(self, isolated_config):
        (isolated_config / "config.json").write_text(
            json.dumps({"font_size": 14, "campo_do_futuro": True}), encoding="utf-8")
        assert Settings.load().font_size == 14

    def test_recentes_sem_duplicata_e_com_limite(self, isolated_config, tmp_path):
        s = Settings()
        for i in range(15):
            s.add_recent(str(tmp_path / f"p{i}.htm"))
        assert len(s.recent) == 10
        first = s.recent[0]
        s.add_recent(first)
        assert s.recent[0] == first
        assert len(s.recent) == 10

    def test_remove_recente(self, isolated_config, tmp_path):
        p = str(tmp_path / "x.htm")
        s = Settings()
        s.add_recent(p)
        assert s.recent
        s.drop_recent(p)
        assert s.recent == []

    def test_prune_recent(self, isolated_config, tmp_path):
        existe = tmp_path / "existe.htm"
        existe.write_text("x", encoding="utf-8")
        s = Settings()
        s.add_recent(str(existe))
        s.add_recent(str(tmp_path / "sumiu.htm"))
        s.prune_recent()
        assert s.recent == [str(existe)]

    def test_diretorio_isolado_por_variavel_de_ambiente(self, isolated_config):
        assert base_dir() == isolated_config


class TestAutosave:
    def test_caminho_estavel_para_o_mesmo_arquivo(self, isolated_config):
        a = autosave_path("/site/pagina.htm")
        b = autosave_path("/site/pagina.htm")
        assert a == b
        assert a.suffix == ".htm"
        assert a.parent.name == "autosave"

    def test_caminho_diferente_por_arquivo(self, isolated_config):
        assert autosave_path("/site/a.htm") != autosave_path("/site/b.htm")

    def test_documento_novo_tem_caminho(self, isolated_config):
        p = autosave_path(None, "Nova Página 3")
        assert p.exists() is False
        assert "autosave" in str(p)

    def test_lista_e_limpeza(self, isolated_config):
        p = autosave_path("/site/pagina.htm")
        p.write_text("<p>recuperação</p>", encoding="utf-8")
        found = find_autosaves()
        assert len(found) == 1
        assert found[0][0] == p

        # autosave velho (mais de 30 dias) é descartado
        old = autosave_path("/site/velha.htm")
        old.write_text("<p>velho</p>", encoding="utf-8")
        import os
        antigo = time.time() - 40 * 24 * 3600
        os.utime(old, (antigo, antigo))
        assert clear_autosaves() == 1
        assert [x[0] for x in find_autosaves()] == [p]

    def test_sem_autosaves(self, isolated_config):
        assert find_autosaves() == []
        assert clear_autosaves() == 0
