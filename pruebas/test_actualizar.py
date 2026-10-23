"""Versiones nuevas (telar.actualizar): la última de PyPI con caché, cuándo se ofrece el clic, y el proceso de
afuera que instala y anota cómo le fue (corrido de verdad, con un uv y un telar de mentira)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import actualizar as a


def pypi(version):
    return lambda: {"info": {"version": version}}


class LaUltima(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = SimpleNamespace(estado=Path(self.tmp.name))

    def test_se_guarda_una_hora_y_forzar_pregunta_ya(self):
        self.assertEqual(a.ultima(self.config, leer=pypi("9.9.9"), ahora=1000)["version"], "9.9.9")
        # dentro de la hora, aunque PyPI diga otra, vale la guardada
        self.assertEqual(a.ultima(self.config, leer=pypi("9.9.10"), ahora=2000)["version"], "9.9.9")
        self.assertEqual(a.ultima(self.config, leer=pypi("9.9.10"), ahora=2000, forzar=True)["version"], "9.9.10")
        self.assertEqual(a.ultima(self.config, leer=pypi("9.9.11"), ahora=2000 + a.CADA)["version"], "9.9.11")

    def test_sin_red_queda_lo_que_habia_con_el_motivo(self):
        a.ultima(self.config, leer=pypi("9.9.9"), ahora=1000)

        def sin_red():
            raise OSError("sin red")

        r = a.ultima(self.config, leer=sin_red, forzar=True)
        self.assertEqual(r["version"], "9.9.9")
        self.assertIn("sin red", r["error"])
        self.assertIn("PyPI dice", a.ultima(self.config, leer=pypi("1.0.0rc1"), forzar=True)["error"])

    def test_cuando_se_ofrece_el_clic(self):
        with mock.patch.object(a, "como_instalado", return_value="uv"), mock.patch.object(a, "_uv", return_value="/x/uv"):
            r = a.ver(self.config, forzar=True, leer=pypi("99.0.0"))
            self.assertTrue(r["hay_nueva"] and r["puede"])
            self.assertEqual(r["corre"], a.__version__)
            self.assertFalse(a.ver(self.config, forzar=True, leer=pypi("0.0.1"))["hay_nueva"])
        with mock.patch.object(a, "como_instalado", return_value="repo"):
            r = a.ver(self.config, forzar=True, leer=pypi("99.0.0"))
            self.assertTrue(r["hay_nueva"])
            self.assertFalse(r["puede"])  # del repositorio: git pull
            self.assertIn("git pull", r["a_mano"])

    def test_empezar_solo_la_ultima_nueva_y_desde_uv(self):
        a.ultima(self.config, leer=pypi("99.0.0"), forzar=True)
        with mock.patch.object(a, "como_instalado", return_value="repo"):
            with self.assertRaises(a.ErrorDeActualizar):
                a.empezar(self.config, "99.0.0")
        with mock.patch.object(a, "como_instalado", return_value="uv"), mock.patch.object(a, "_uv", return_value="/x/uv"):
            for mala in ("98.0.0", "0.0.1", "99.0.0; rm -rf ~", ""):
                with self.assertRaises(a.ErrorDeActualizar, msg=mala):
                    a.empezar(self.config, mala)
            with mock.patch.object(a.subprocess, "Popen") as lanzar, mock.patch.object(a.sys, "platform", "darwin"):
                p = a.empezar(self.config, "99.0.0")
            self.assertEqual((p["version"], p["estado"]), ("99.0.0", "corriendo"))
            self.assertEqual(lanzar.call_args.args[0][-4:][1:3], ["99.0.0", "/x/uv"])
            self.assertTrue(lanzar.call_args.kwargs["start_new_session"])
            with self.assertRaises(a.ErrorDeActualizar):  # ya hay una corriendo
                a.empezar(self.config, "99.0.0")

    def test_si_el_servicio_ya_corre_la_nueva_esta_lista(self):
        (Path(self.tmp.name) / "actualizar.json").write_text(json.dumps(
            {"version": a.__version__, "estado": "corriendo", "desde": 1}))
        self.assertEqual(a.progreso(self.config)["estado"], "listo")


class ElProcesoDeAfuera(Prueba):
    """El guion de verdad, con un `uv` y un `telar` de mentira que anotan con qué los llamaron."""

    def correr(self, uv_sale=0, telar_sale=0):
        d = Path(self.tmp.name)
        (d / "bin").mkdir(exist_ok=True)
        uv = d / "uv"
        uv.write_text(f'#!/bin/sh\necho "uv $*" >> {d}/llamadas\n[ "$1 $2" = "tool dir" ] && echo {d}/bin && exit 0\n'
                      f"exit {uv_sale}\n")
        telar = d / "bin" / "telar"
        telar.write_text(f'#!/bin/sh\necho "telar $*" >> {d}/llamadas\nexit {telar_sale}\n')
        for f in (uv, telar):
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        estado, log = d / "actualizar.json", d / "actualizar.log"
        with log.open("a") as salida:
            subprocess.run(["/bin/sh", "-c", a.GUION, "x", str(estado), "9.9.9", str(uv), str(log)],
                           stdout=salida, stderr=salida, timeout=30)
        llamadas = (d / "llamadas").read_text().splitlines() if (d / "llamadas").exists() else []
        return json.loads(estado.read_text()), llamadas

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_instala_esa_version_corre_instalar_y_anota_listo(self):
        p, llamadas = self.correr()
        self.assertEqual((p["version"], p["estado"]), ("9.9.9", "listo"))
        self.assertIn("uv tool install --force --refresh telar[serve,bus]==9.9.9", llamadas)
        self.assertIn("telar instalar --si", llamadas)

    def test_si_uv_falla_no_sigue_y_lo_dice(self):
        p, llamadas = self.correr(uv_sale=1)
        self.assertEqual(p["estado"], "fallo")
        self.assertIn("uv no pudo", p["error"])
        self.assertFalse(any(x.startswith("telar") for x in llamadas))

    def test_si_instalar_falla_lo_dice(self):
        p, _ = self.correr(telar_sale=2)
        self.assertEqual(p["estado"], "fallo")
        self.assertIn("telar instalar", p["error"])
