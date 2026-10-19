"""`telar compartir`: lo que llega del celular va a un hilo o a un proveedor que declara `recibir`."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar.ordenes import compartir


class Compartir(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.guion = self.tmp / "recibir"
        self.guion.write_text('#!/bin/sh\nprintf "%s|" "$@" > "$(dirname "$0")/recibido"; echo "quedó en la entrada"\n')
        self.guion.chmod(0o755)

    def ctx(self, recibir=None):
        opciones = {"tipo": "comando", "comando": ["x"], "pestana": "leer"}
        if recibir is not None:
            opciones["recibir"] = recibir
        return SimpleNamespace(config=mod_config.Config(raiz=self.tmp, estado=self.tmp / "estado",
                               proveedores={"lecturas": mod_config.Proveedor(nombre="lecturas", opciones=opciones)}))

    def test_las_palabras_vacias_se_caen_con_su_opcion(self):
        plantilla = ["prog", "dejar", "{url}", "--nota", "{texto}"]
        self.assertEqual(compartir.palabras(plantilla, {"url": "https://a", "texto": "", "titulo": ""}), ["prog", "dejar", "https://a"])
        self.assertEqual(compartir.palabras(plantilla, {"url": "", "texto": "hola", "titulo": ""}), ["prog", "dejar", "--nota", "hola"])

    def test_solo_los_proveedores_con_recibir_son_destinos(self):
        self.assertEqual(compartir.receptores(self.ctx().config), [])
        self.assertEqual(compartir.receptores(self.ctx([str(self.guion)]).config),
                         [{"destino": "lecturas", "nombre": "leer", "tipo": "proveedor"}])

    def test_al_proveedor_le_llega_cada_cosa_como_palabra_sin_shell(self):
        ctx = self.ctx([str(self.guion), "dejar", "{url}", "--nota", "{texto}"])
        r = compartir._llevar(ctx, "lecturas", "https://x.org/a?b=1;rm", "mira; esto", "")
        self.assertEqual(r, {"ok": True, "dicho": "quedó en la entrada"})
        self.assertEqual((self.tmp / "recibido").read_text(), "dejar|https://x.org/a?b=1;rm|--nota|mira; esto|")

    def test_lo_que_no_sirve_no_corre_nada(self):
        ctx = self.ctx([str(self.guion), "{url}"])
        for destino, url, texto in (("lecturas", "javascript:alert(1)", ""), ("lecturas", "", ""), ("otro", "https://a", ""), ("", "https://a", "")):
            self.assertFalse(compartir._llevar(ctx, destino, url, texto, "")["ok"])
        self.assertFalse((self.tmp / "recibido").exists())

    def test_a_un_hilo_va_como_mensaje(self):
        with mock.patch("telar.ordenes.mensaje.enviar") as enviar:
            r = compartir._llevar(self.ctx(), "hilo:Faro", "https://a", "léelo", "Un título")
        self.assertTrue(r["ok"])
        self.assertEqual(enviar.call_args[0][1], "Faro")
        self.assertIn("léelo\nUn título\nhttps://a", enviar.call_args[0][2])
