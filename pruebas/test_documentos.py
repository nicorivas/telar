"""La carpeta de un hilo y sus archivos, para la página (`doc:<hilo>`): nada fuera de la carpeta, nada oculto."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import documentos


class LaCarpetaDeUnHilo(Prueba):
    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        raiz = Path(d.name)
        self.base = raiz / "faro"
        (self.base / "docs").mkdir(parents=True)
        (self.base / "README.md").write_text("# Faro\n")
        (self.base / "docs" / "notas.txt").write_text("hola")
        (self.base / ".oculto").write_text("no")
        (self.base / "foto.bin").write_bytes(b"\x00\x01")
        (raiz / "secreto.txt").write_text("no")
        os.symlink(raiz / "secreto.txt", self.base / "atajo.txt")
        hilo = {"ruta": str(self.base), "vinculado": True, "ficha": {"titulo": "Faro", "documento": str(self.base / "README.md")}}
        p = mock.patch("telar.servicios.fichas.ficha", return_value=SimpleNamespace(hilo=hilo))
        p.start()
        self.addCleanup(p.stop)

    def test_su_documento_y_la_lista_sin_ocultos(self):
        d = documentos.documento(None, "faro")
        self.assertEqual((d.titulo, d.archivo, d.markdown, d.subir), ("Faro", "README.md", "# Faro\n", None))
        self.assertEqual([a.nombre for a in d.archivos], ["docs/", "atajo.txt", "foto.bin", "README.md"])

    def test_otra_carpeta_un_texto_y_un_binario(self):
        d = documentos.documento(None, "faro", "docs/notas.txt")
        self.assertEqual((d.carpeta, d.archivo, d.texto, d.subir), ("docs", "docs/notas.txt", "hola", "."))
        self.assertIn("binario", documentos.documento(None, "faro", "foto.bin").texto)

    def test_nada_fuera_de_la_carpeta(self):
        for ruta in ("../secreto.txt", "docs/../../secreto.txt", "atajo.txt"):
            self.assertIn("no es de la carpeta", documentos.documento(None, "faro", ruta).error)


class UnArchivoDeLaRaiz(Prueba):
    """Sin hilo: un archivo o una carpeta cualquiera del repositorio (lo que abre el dashboard), sin salir de él."""

    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.raiz = Path(d.name) / "repo"
        (self.raiz / "proyectos" / "faro").mkdir(parents=True)
        (self.raiz / "proyectos" / "faro" / "README.md").write_text("# Faro\n")
        (self.raiz / "proyectos" / "faro" / "plano.pdf").write_bytes(b"%PDF\x00binario")
        (Path(d.name) / "secreto.txt").write_text("no")
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=self.raiz, apps=()))

    def test_un_archivo_por_su_ruta_absoluta_o_relativa(self):
        for ruta in (str(self.raiz / "proyectos" / "faro" / "README.md"), "proyectos/faro/README.md"):
            d = documentos.documento(self.ctx, "", ruta)
            self.assertEqual((d.titulo, d.archivo, d.markdown, d.error), ("proyectos/faro/README.md", "proyectos/faro/README.md", "# Faro\n", ""))

    def test_una_carpeta_y_lo_que_no_es_texto_se_baja(self):
        d = documentos.documento(self.ctx, "", "proyectos/faro")
        self.assertEqual([a.nombre for a in d.archivos], ["plano.pdf", "README.md"])
        b = documentos.documento(self.ctx, "", "proyectos/faro/plano.pdf")
        self.assertEqual(b.descarga, str((self.raiz / "proyectos" / "faro" / "plano.pdf").resolve()))
        from telar.servicios import archivos
        self.assertEqual(archivos.para_bajar(self.ctx, b.descarga).name, "plano.pdf")

    def test_nada_fuera_de_la_raiz(self):
        self.assertIn("fuera de la raíz", documentos.documento(self.ctx, "", "../secreto.txt").error)
        from telar.servicios import ErrorDeServicio, archivos
        with self.assertRaises(ErrorDeServicio):
            archivos.para_bajar(self.ctx, str(self.raiz.parent / "secreto.txt"))


class LaCarpetaDeUnHiloFueraDeLaRaiz(Prueba):
    """Sin hilo, una ruta que escribió el agente de un hijo con rama: en su worktree, fuera de la raíz. Se muestra y
    se recorre sin salir del worktree; las rutas vuelven enteras, para pedirlas de nuevo."""

    def setUp(self):
        super().setUp()
        from telar import estado as mod_estado

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        base = Path(d.name).resolve()
        self.raiz = base / "vida"
        (self.raiz / "docs").mkdir(parents=True)
        (self.raiz / "docs" / "oauth.md").write_text("el de la raíz")
        self.wt = base / "worktrees" / "faro-base"
        (self.wt / "docs").mkdir(parents=True)
        (self.wt / "README.md").write_text("# Faro\n")
        (self.wt / "docs" / "oauth.md").write_text("# OAuth\n")
        (base / "secreto.txt").write_text("no")
        os.symlink(base / "secreto.txt", self.wt / "docs" / "atajo.txt")
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=self.raiz, apps=(), estado=base / "estado"))
        mod_estado.abrir(self.ctx.config).anotar_rama("Base", {"rama": "base", "base": "main", "ruta": str(self.wt)})
        self.afuera = base / "secreto.txt"

    def test_absoluta_o_relativa_desde_la_raiz(self):
        for ruta in (str(self.wt / "docs" / "oauth.md"), "../worktrees/faro-base/docs/oauth.md"):
            d = documentos.documento(self.ctx, "", ruta)
            self.assertEqual((d.error, d.titulo, d.markdown), ("", "faro-base/docs/oauth.md", "# OAuth\n"), ruta)
            self.assertEqual((d.carpeta, d.archivo, d.subir), (str(self.wt / "docs"), str(self.wt / "docs" / "oauth.md"), str(self.wt)))
            self.assertEqual([a.ruta for a in d.archivos], [str(self.wt / "docs" / "atajo.txt"), str(self.wt / "docs" / "oauth.md")])

    def test_se_sube_hasta_el_worktree_y_no_mas(self):
        d = documentos.documento(self.ctx, "", str(self.wt))
        self.assertEqual((d.titulo, d.subir, [a.nombre for a in d.archivos]), ("faro-base", None, ["docs/", "README.md"]))
        # lo de la raíz sigue como siempre: relativo a ella
        r = documentos.documento(self.ctx, "", "docs/oauth.md")
        self.assertEqual((r.titulo, r.archivo, r.markdown), ("docs/oauth.md", "docs/oauth.md", "el de la raíz"))

    def test_afuera_y_un_enlace_que_sale_no(self):
        for ruta in (str(self.afuera), str(self.wt / "docs" / "atajo.txt"), str(self.wt.parent), "/"):
            self.assertIn("fuera de la raíz", documentos.documento(self.ctx, "", ruta).error, ruta)


class UnDocumentoDeOtraMaquina(Prueba):
    """«servidor:ruta»: lo arma el nodo de allá, y sus rutas vuelven con la máquina delante."""

    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path("/no-existe"), apps=(),
                                                          bus=SimpleNamespace(url="nats://x", maquina="laptop")))

    def _con(self, respuesta):
        from telar import bus

        return mock.patch.object(bus, "hay_bus", return_value=True), mock.patch.object(bus, "pedir", return_value=respuesta)

    def test_con_su_carpeta(self):
        alla = documentos.Documento(hilo="", titulo="faro-base/docs/oauth.md", carpeta="~/worktrees/faro-base/docs",
                                    archivo="~/worktrees/faro-base/docs/oauth.md", subir="~/worktrees/faro-base",
                                    archivos=[documentos.Entrada(nombre="oauth.md", ruta="~/worktrees/faro-base/docs/oauth.md")],
                                    markdown="# OAuth\n", descarga="/home/n/x.bin")
        hay, pedir = self._con({"ok": True, "documento": alla.model_dump()})
        with hay, pedir as p:
            d = documentos.documento(self.ctx, "", "servidor:../worktrees/faro-base/docs/oauth.md")
        self.assertEqual(p.call_args.args[1:4], ("servidor", "archivo-leer", {"ruta": "../worktrees/faro-base/docs/oauth.md", "documento": True}))
        self.assertEqual((d.titulo, d.maquina, d.archivo, d.subir, d.descarga),
                         ("faro-base/docs/oauth.md · en servidor", "servidor", "servidor:~/worktrees/faro-base/docs/oauth.md",
                          "servidor:~/worktrees/faro-base", ""))
        self.assertEqual([a.ruta for a in d.archivos], ["servidor:~/worktrees/faro-base/docs/oauth.md"])

    def test_un_nodo_de_antes_da_solo_el_archivo(self):
        hay, pedir = self._con({"ok": True, "archivo": {"ruta": "/home/n/vida/docs/x.md", "texto": "lejos", "mtime": 1.0, "recortado": True}})
        with hay, pedir:
            d = documentos.documento(self.ctx, "", "servidor:docs/x.md")
        self.assertEqual((d.titulo, d.archivo, d.markdown, d.archivos, d.subir),
                         ("x.md · en servidor", "servidor:/home/n/vida/docs/x.md", "lejos", [], None))
        self.assertIn("más largo", d.aviso)

    def test_lo_que_no_pudo_leer_lo_dice(self):
        hay, pedir = self._con({"ok": False, "error": "fuera", "codigo": 403})
        with hay, pedir:
            self.assertEqual(documentos.documento(self.ctx, "", "servidor:/etc/passwd").error, "fuera")
