"""Leer y escribir archivos desde la página: dentro de la raíz o de lo que declaran las apps, y nada más."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import ErrorDeServicio
from telar.servicios import archivos


class LosArchivos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.raiz = base / "repo"
        (self.raiz / "proyectos" / "faro" / "reuniones").mkdir(parents=True)
        (self.raiz / "proyectos" / "faro" / "README.md").write_text("# Faro\n")
        (self.raiz / "proyectos" / "faro" / "reuniones" / "preparacion-1.md").write_text("prep")
        (self.raiz / "proyectos" / "faro" / ".oculto.md").write_text("no")
        self.afuera = base / "secreto.txt"
        self.afuera.write_text("no")
        self.app = base / "vivero.html"
        self.app.write_text("<p>vivero</p>")
        self.memoria = base / "vivero.json"
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=self.raiz, apps=(
            SimpleNamespace(archivo=str(self.app), memoria=str(self.memoria)),)))

    def test_leer_dentro_y_no_afuera(self):
        self.assertEqual(archivos.leer(self.ctx, "proyectos/faro/README.md").texto, "# Faro\n")
        self.assertEqual(archivos.leer(self.ctx, str(self.app)).texto, "<p>vivero</p>")
        for ruta in (str(self.afuera), "../secreto.txt", "proyectos/../../secreto.txt"):
            with self.assertRaises(ErrorDeServicio) as e:
                archivos.leer(self.ctx, ruta)
            self.assertEqual(e.exception.codigo, 403, ruta)
        with self.assertRaises(ErrorDeServicio) as e:
            archivos.leer(self.ctx, "proyectos/faro/NO.md")
        self.assertEqual(e.exception.codigo, 404)

    def test_un_enlace_que_escapa_no_se_sigue(self):
        os.symlink(self.afuera, self.raiz / "atajo.txt")
        with self.assertRaises(ErrorDeServicio) as e:
            archivos.leer(self.ctx, "atajo.txt")
        self.assertEqual(e.exception.codigo, 403)

    def test_buscar_md_sin_ocultos(self):
        r = archivos.buscar_md(self.ctx, "proyectos/faro")
        self.assertEqual(sorted(Path(x.ruta).name for x in r.archivos), ["README.md", "preparacion-1.md"])

    def test_escribir_solo_la_memoria_de_un_lienzo(self):
        archivos.escribir(self.ctx, str(self.memoria), '{"a": 1}')
        self.assertEqual(self.memoria.read_text(), '{"a": 1}')
        archivos.escribir(self.ctx, "proyectos/faro/lienzo.json", "[]")
        for ruta, texto, codigo in ((str(self.afuera), "{}", 403), ("proyectos/faro/README.md", "{}", 403),
                                    (str(self.memoria), "no es json", 422)):
            with self.assertRaises(ErrorDeServicio) as e:
                archivos.escribir(self.ctx, ruta, texto)
            self.assertEqual(e.exception.codigo, codigo, ruta)

    def test_el_lienzo_de_una_pagina_entregada(self):
        estado = Path(self.tmp.name) / "estado"
        estado.mkdir()
        (estado / "babel.html").write_text("<p>babel</p>")
        archivos._de_paginas["archivo"].clear()
        archivos._de_paginas["memoria"].clear()
        self.addCleanup(archivos._de_paginas["archivo"].clear)
        self.addCleanup(archivos._de_paginas["memoria"].clear)
        with self.assertRaises(ErrorDeServicio):
            archivos.leer(self.ctx, str(estado / "babel.html"))
        from telar.servicios import Pagina
        archivos.anotar_lienzos(Pagina(bloques=[{"lienzo": {"archivo": str(estado / "babel.html"),
                                                             "memoria": str(estado / "babel.json")}}]))
        self.assertEqual(archivos.leer(self.ctx, str(estado / "babel.html")).texto, "<p>babel</p>")
        archivos.escribir(self.ctx, str(estado / "babel.json"), '{"nivel": 2}')
        self.assertEqual((estado / "babel.json").read_text(), '{"nivel": 2}')
        with self.assertRaises(ErrorDeServicio):
            archivos.leer(self.ctx, str(estado / "otro.html"))

    def test_un_repo_de_la_configuracion_se_lee_y_no_se_escribe(self):
        otro = Path(self.tmp.name) / "empresa"
        otro.mkdir()
        (otro / "nota.md").write_text("de la empresa")
        (otro / "x.json").write_text("{}")
        self.ctx.config.repos = (SimpleNamespace(nombre="empresa", ruta=otro),)
        self.assertEqual(archivos.leer(self.ctx, str(otro / "nota.md")).texto, "de la empresa")
        with self.assertRaises(ErrorDeServicio):
            archivos.escribir(self.ctx, str(otro / "x.json"), "[]")

    def test_en_otra_maquina_se_le_pide_a_su_nodo(self):
        from unittest import mock

        from telar import bus

        self.ctx.config.bus = SimpleNamespace(url="nats://x", maquina="laptop")
        lejos = {"ruta": "/home/n/vida/docs/x.md", "texto": "lejos", "mtime": 1.0, "recortado": False}
        with mock.patch.object(bus, "hay_bus", return_value=True), \
                mock.patch.object(bus, "pedir", return_value={"ok": True, "archivo": lejos}) as pedir:
            a = archivos.leer_en(self.ctx, "servidor:docs/x.md")
            self.assertEqual((a.texto, a.maquina), ("lejos", "servidor"))
            self.assertEqual(pedir.call_args.args[1:4], ("servidor", "archivo-leer", {"ruta": "docs/x.md"}))
            # la propia máquina, o sin máquina, se lee aquí
            self.assertEqual(archivos.leer_en(self.ctx, "laptop:proyectos/faro/README.md").texto, "# Faro\n")
            self.assertEqual(archivos.leer_en(self.ctx, "proyectos/faro/README.md").texto, "# Faro\n")
            self.assertEqual(pedir.call_count, 1)
        with mock.patch.object(bus, "hay_bus", return_value=True), \
                mock.patch.object(bus, "pedir", return_value={"ok": False, "error": "fuera", "codigo": 403}):
            with self.assertRaises(ErrorDeServicio) as e:
                archivos.leer_en(self.ctx, "docs/x.md", "servidor")
            self.assertEqual(e.exception.codigo, 403)

    def test_lo_que_responde_el_nodo(self):
        self.assertTrue(archivos.leer_para_otra(self.ctx, {"ruta": "proyectos/faro/README.md"})["ok"])
        r = archivos.leer_para_otra(self.ctx, {"ruta": str(self.afuera)})
        self.assertEqual((r["ok"], r["codigo"]), (False, 403))
