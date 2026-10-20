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
