"""Varios repositorios de trabajo (`[repos]`): cada uno con su perfil, juntos en uno (perfil.cargar_todos)."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import lectura
from telar import perfil as mp

PERFIL = textwrap.dedent("""\
    version: 1
    nombre: {nombre}
    arquetipos:
      proyecto:
        ruta: "{ruta}"
        etiqueta: "{etiqueta}"
    """)


class Repos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "vida"
        for carpeta in ("equipo/proyectos/faro", "equipo/proyectos/molino", "nico/proyectos/hondo", "suelto/x"):
            (self.raiz / carpeta).mkdir(parents=True)
            (self.raiz / carpeta / "README.md").write_text("# " + carpeta.rsplit("/", 1)[1] + "\n")
        # el perfil de vida también nombra las carpetas del equipo, como antes de separarlos
        (self.raiz / "telar-perfil.yaml").write_text(
            PERFIL.format(nombre="vida", ruta="*/proyectos/*/", etiqueta="vida"))
        (self.raiz / "equipo" / "telar-perfil.yaml").write_text(
            PERFIL.format(nombre="equipo", ruta="proyectos/*/", etiqueta="equipo"))

    def config(self, *repos):
        return SimpleNamespace(raiz=self.raiz, perfil=None, repos=tuple(repos))

    def test_sin_repos_es_el_perfil_de_la_raiz(self):
        p = mp.cargar_todos(self.config())
        self.assertEqual([a.etiqueta for a in p.arquetipos], ["vida"])

    def test_gana_el_perfil_del_repo_mas_profundo(self):
        p = mp.cargar_todos(self.config(cfg.Repo("vida", self.raiz), cfg.Repo("equipo", self.raiz / "equipo")))
        mapa = lectura.indice(p, self.raiz)
        self.assertEqual(sorted(mapa), ["equipo/proyectos/faro", "equipo/proyectos/molino", "nico/proyectos/hondo"])
        self.assertEqual((mapa["equipo/proyectos/faro"][0].repo, mapa["equipo/proyectos/faro"][0].etiqueta), ("equipo", "equipo"))
        self.assertEqual(mapa["nico/proyectos/hondo"][0].repo, "")

    def test_un_repo_sin_perfil_no_aporta(self):
        p = mp.cargar_todos(self.config(cfg.Repo("suelto", self.raiz / "suelto")))
        self.assertEqual([a.repo for a in p.arquetipos], [""])

    def test_de_que_repo_es_una_carpeta(self):
        c = self.config(cfg.Repo("vida", self.raiz), cfg.Repo("equipo", self.raiz / "equipo"))
        self.assertEqual(mp.repo_de(c, "equipo/proyectos/faro"), "equipo")
        self.assertEqual(mp.repo_de(c, self.raiz / "nico/proyectos/hondo"), "vida")
        self.assertEqual(mp.repo_de(c, "/otra/parte"), "")

    def test_la_configuracion(self):
        c = cfg.desde_dict({"repos": {"equipo": {"ruta": "~/equipo"}, "vida": {"ruta": "/x/vida", "perfil": "/x/p.yaml"}}})
        self.assertEqual([(r.nombre, r.ruta.name, r.perfil) for r in c.repos], [("equipo", "equipo", ""), ("vida", "vida", "/x/p.yaml")])
        with self.assertRaises(cfg.ErrorDeConfig):
            cfg.desde_dict({"repos": {"x": {"ruta": ""}}})
        with self.assertRaises(cfg.ErrorDeConfig):
            cfg.desde_dict({"repos": {"x": {"ruta": "/a", "otra": 1}}})


if __name__ == "__main__":
    unittest.main()
