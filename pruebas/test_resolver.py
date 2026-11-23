"""Dónde está un archivo que nombró un agente (telar.servicios.resolver): un nombre suelto bajo la carpeta que se
nombró antes en el mismo mensaje, en la carpeta del hilo, por nombre en la raíz (uno se abre, varios se ofrecen), con
tildes compuestas o no, y nada fuera de lo legible."""

from __future__ import annotations

import os
import tempfile
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import ErrorDeServicio
from telar.servicios import archivos, resolver

ARTICULO = "personal/referencia/artículos/2026-06-informe-ia"


class ElNombreSuelto(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.raiz = base / "vida"
        for d in (ARTICULO, "personal/referencia/artículos/2026-05-yc-playbook", "personal/referencia/artículos/2026-10-bench",
                  "personal/proyectos/faro/docs", "node_modules/x", ".oculto"):
            (self.raiz / d).mkdir(parents=True)
        for d in (ARTICULO, "personal/referencia/artículos/2026-05-yc-playbook", "personal/referencia/artículos/2026-10-bench",
                  "node_modules/x", ".oculto"):
            (self.raiz / d / "original.md").write_text(d)
        (self.raiz / "README.md").write_text("la raíz")
        (self.raiz / "personal/proyectos/faro/README.md").write_text("faro")
        (self.raiz / "personal/proyectos/faro/docs/README.md").write_text("docs de faro")
        (self.raiz / "personal/proyectos/faro/docs/unico.md").write_text("único")
        self.afuera = base / "afuera"
        self.afuera.mkdir()
        (self.afuera / "original.md").write_text("no")
        (self.afuera / "solo-afuera.md").write_text("no")
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=self.raiz, apps=()))

    def r(self, ruta, carpeta="", contexto=()):
        return resolver.resolver(self.ctx, ruta, carpeta, list(contexto))

    def test_el_caso_del_articulo_bajo_la_carpeta_nombrada_antes(self):
        # «En `personal/referencia/artículos/…/`:» y abajo «`original.md`», con el hilo en la raíz
        r = self.r("original.md", str(self.raiz), [ARTICULO + "/"])
        self.assertEqual((r.ruta, r.candidatos), (f"{ARTICULO}/original.md", []))
        # la carpeta nombrada, relativa a la del hilo
        r = self.r("original.md", str(self.raiz / "personal/referencia"), ["artículos/2026-06-informe-ia"])
        self.assertEqual(r.ruta, f"{ARTICULO}/original.md")

    def test_la_mas_cercana_que_lo_tenga(self):
        # la más cercana primero; una que no lo tiene se salta
        r = self.r("original.md", "", ["personal/proyectos/faro/docs", "personal/referencia/artículos/2026-10-bench", ARTICULO])
        self.assertEqual(r.ruta, "personal/referencia/artículos/2026-10-bench/original.md")

    def test_un_nombre_suelto_prefiere_la_nombrada_a_la_raiz(self):
        # el README.md de la raíz existe, pero el mensaje nombró la carpeta de faro
        self.assertEqual(self.r("README.md", str(self.raiz), ["personal/proyectos/faro/docs/"]).ruta,
                         "personal/proyectos/faro/docs/README.md")
        # sin carpeta nombrada: la del hilo, y después la raíz
        self.assertEqual(self.r("README.md", str(self.raiz / "personal/proyectos/faro")).ruta, "personal/proyectos/faro/README.md")
        self.assertEqual(self.r("README.md", "").ruta, "README.md")

    def test_una_ruta_con_carpetas_va_tal_cual_primero(self):
        self.assertEqual(self.r("docs/README.md", str(self.raiz / "personal/proyectos/faro"), ["personal/proyectos"]).ruta,
                         "personal/proyectos/faro/docs/README.md")
        # y si tal cual no está, bajo una nombrada
        self.assertEqual(self.r("faro/docs/unico.md", str(self.raiz), ["personal/proyectos/"]).ruta,
                         "personal/proyectos/faro/docs/unico.md")

    def test_por_nombre_uno_se_abre(self):
        r = self.r("unico.md", str(self.raiz))
        self.assertEqual((r.ruta, r.candidatos), ("personal/proyectos/faro/docs/unico.md", ["personal/proyectos/faro/docs/unico.md"]))

    def test_por_nombre_varios_se_ofrecen_los_cercanos_primero(self):
        r = self.r("original.md", str(self.raiz))
        self.assertEqual(r.ruta, "")
        # ni lo oculto ni node_modules ni lo de afuera
        self.assertEqual(sorted(r.candidatos), sorted(f"{d}/original.md" for d in (
            ARTICULO, "personal/referencia/artículos/2026-05-yc-playbook", "personal/referencia/artículos/2026-10-bench")))
        # con una carpeta nombrada que no lo tiene pero está cerca de uno: ese primero
        r = self.r("original.md", str(self.raiz), ["personal/referencia/artículos/2026-10-bench/datos"])
        self.assertEqual(r.candidatos[0], "personal/referencia/artículos/2026-10-bench/original.md")
        # con la carpeta del último tramo, solo los que la tienen
        r = self.r("2026-05-yc-playbook/original.md", str(self.raiz))
        self.assertEqual(r.ruta, "personal/referencia/artículos/2026-05-yc-playbook/original.md")

    def test_tildes_compuestas_o_no(self):
        nfd = unicodedata.normalize("NFD", ARTICULO)
        self.assertNotEqual(nfd, ARTICULO)
        # en macOS las dos formas abren el mismo archivo, y vuelve la que se pidió; en Linux, la que hay en el disco
        nfc = lambda s: unicodedata.normalize("NFC", s)  # noqa: E731
        self.assertEqual(nfc(self.r("original.md", "", [nfd]).ruta), f"{ARTICULO}/original.md")
        self.assertEqual(nfc(self.r(f"{nfd}/original.md").ruta), f"{ARTICULO}/original.md")
        # y por nombre, con la carpeta del último tramo escrita de la otra forma
        self.assertEqual(nfc(self.r(unicodedata.normalize("NFD", "artículos/2026-10-bench/original.md"), "/").ruta),
                         "personal/referencia/artículos/2026-10-bench/original.md")

    def test_nada_fuera_de_lo_legible(self):
        self.assertEqual(self.r("original.md", "", [str(self.afuera)]).candidatos[0].startswith("personal/"), True)
        r = self.r("solo-afuera.md", str(self.afuera), [str(self.afuera)])
        self.assertEqual((r.ruta, r.candidatos), ("", []))
        os.symlink(self.afuera, self.raiz / "atajo")
        self.assertEqual(self.r("solo-afuera.md", str(self.raiz)).candidatos, [])
        self.assertEqual(self.r("atajo/solo-afuera.md", str(self.raiz)).ruta, "")
        with self.assertRaises(ErrorDeServicio):
            self.r("")

    def test_lo_que_responde_el_nodo_y_lo_que_pide_la_otra_maquina(self):
        r = archivos.leer_para_otra(self.ctx, {"resolver": {"ruta": "original.md", "contexto": [ARTICULO]}})
        self.assertEqual((r["ok"], r["resolucion"]["ruta"]), (True, f"{ARTICULO}/original.md"))
        from telar import bus

        self.ctx.config.bus = SimpleNamespace(url="nats://x", maquina="laptop")
        alla = {"ok": True, "resolucion": {"ruta": "", "candidatos": ["a/original.md", "b/original.md"]}}
        with mock.patch.object(bus, "hay_bus", return_value=True), \
                mock.patch.object(bus, "pedir", return_value=alla) as pedir:
            x = resolver.resolver_en(self.ctx, "original.md", "personal", ["a"], "servidor")
            self.assertEqual((x.candidatos, x.maquina), (["a/original.md", "b/original.md"], "servidor"))
            self.assertEqual(pedir.call_args.args[1:4], ("servidor", "archivo-leer", {"resolver": {
                "ruta": "original.md", "carpeta": "personal", "contexto": ["a"]}}))
        # un nodo de antes contesta «¿qué archivo?» a una lectura sin ruta: vuelve sin nada
        with mock.patch.object(bus, "hay_bus", return_value=True), \
                mock.patch.object(bus, "pedir", return_value={"ok": False, "error": "¿qué archivo?", "codigo": 422}):
            self.assertEqual(resolver.resolver_en(self.ctx, "original.md", maquina="servidor").candidatos, [])


class LaCarpetaDelHiloFueraDeLaRaiz(Prueba):
    """El worktree de un hijo con rama está fuera de la raíz: lo nombrado ahí, y la búsqueda por nombre, también."""

    def setUp(self):
        super().setUp()
        from telar import estado as mod_estado

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.raiz = base / "vida"
        self.raiz.mkdir()
        self.worktree = base / "worktrees" / "telar-rama"
        (self.worktree / "docs" / "propuestas").mkdir(parents=True)
        (self.worktree / "docs" / "propuestas" / "idea.md").write_text("idea")
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=self.raiz, apps=(), estado=base / "estado"))
        mod_estado.abrir(self.ctx.config).anotar_rama("Rama", {"rama": "rama", "base": "main", "ruta": str(self.worktree)})

    def test_nombrada_y_por_nombre(self):
        casa = Path.home().resolve()
        como = (lambda p: "~/" + os.path.relpath(p, casa)) if casa in self.worktree.parents else str
        esperada = como(self.worktree / "docs" / "propuestas" / "idea.md")
        self.assertEqual(resolver.resolver(self.ctx, "idea.md", str(self.worktree), ["docs/propuestas/"]).ruta, esperada)
        self.assertEqual(resolver.resolver(self.ctx, "idea.md", str(self.worktree)).ruta, esperada)
