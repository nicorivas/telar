"""El espejo: la foto de los hilos de un laptop, guardada en el servidor y leída con su edad."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba, RAIZ  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import espejo as m
from telar.cli import Contexto
from telar.config import Remoto


def hilo(nombre="Faro", **extra):
    return {"nombre": nombre, "atencion": "espera", "vivo": True, "activo": False, "prioridad": 1,
            "tiempo": 12.0, "visto": None, "relativa": "proyectos/faro", "arquetipo": "proyecto", "remoto": "", **extra}


def foto(*hilos, **extra):
    return {"version": m.VERSION, "maquina": "x", "telar": "0.1.9", "publicado": "2026-09-30T10:00:00-03:00",
            "sesion": "faro", "hilos": list(hilos or [hilo()]), **extra}


class ConCarpeta(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = mod_config.Config(raiz=self.base, estado=self.base / "estado")


class Nombres(Prueba):
    def test_un_hostname_se_vuelve_un_nombre_de_archivo(self):
        self.assertEqual(m.nombre_valido("MacBook de Ana"), "macbook-de-ana")
        self.assertEqual(m.nombre_valido("laptop.local"), "laptop-local")
        self.assertEqual(m.nombre_valido("¿¿"), "")

    def test_no_pasa_nada_que_escape_de_la_carpeta(self):
        for malo in ("../x", "a/b", ".oculto", "", "x" * 40, "Mayus"):
            with self.assertRaises(m.ErrorDeEspejo, msg=malo):
                m.validar(foto(), malo)


class Validar(Prueba):
    def test_una_foto_buena_pasa_y_se_limpia(self):
        limpia = m.validar(foto(hilo(secreto="no debe viajar")), "laptop")
        self.assertEqual(limpia["maquina"], "laptop")  # el nombre lo dice quien recibe, no la foto
        self.assertNotIn("secreto", limpia["hilos"][0])

    def test_lo_que_no_es_una_foto_se_rechaza(self):
        for malo in ([], {"version": 99, "hilos": []}, {"version": 1}, {"version": 1, "hilos": "x"},
                     {"version": 1, "hilos": [{"atencion": "espera"}]},
                     {"version": 1, "hilos": [{"nombre": "A", "atencion": 3}]}):
            with self.assertRaises(m.ErrorDeEspejo, msg=str(malo)):
                m.validar(malo, "laptop")


class Guardar(ConCarpeta):
    def test_se_guarda_privado_y_con_la_hora_de_aqui(self):
        antes = time.time()
        m.guardar(self.config, "laptop", json.dumps(foto(publicado="1999-01-01T00:00:00")))
        ruta = m.carpeta(self.config) / "laptop.json"
        self.assertEqual(stat.S_IMODE(ruta.stat().st_mode), 0o600)
        recibido = json.loads(ruta.read_text())["recibido"]
        self.assertGreaterEqual(recibido, antes)  # la edad se mide aquí: la hora de la foto no cuenta
        self.assertEqual(os.listdir(m.carpeta(self.config)), ["laptop.json"])  # sin temporales

    def test_una_foto_nueva_reemplaza_a_la_vieja(self):
        m.guardar(self.config, "laptop", json.dumps(foto(hilo("A"))))
        m.guardar(self.config, "laptop", json.dumps(foto(hilo("B"))))
        self.assertEqual([h["nombre"] for h in m.leer_todos(self.config)[0]["hilos"]], ["B"])

    def test_basura_y_gigantes_se_rechazan_sin_dejar_rastro(self):
        with self.assertRaises(m.ErrorDeEspejo):
            m.guardar(self.config, "laptop", "no es json")
        with self.assertRaises(m.ErrorDeEspejo):
            m.guardar(self.config, "laptop", json.dumps(foto(hilo(nombre="x" * (m.MAXIMO + 1)))))
        self.assertEqual(m.leer_todos(self.config), [])


class Leer(ConCarpeta):
    def test_vigente_hasta_que_pasa_el_plazo_y_despues_apagado(self):
        m.guardar(self.config, "laptop", json.dumps(foto()))
        ahora = time.time()
        vivo = m.leer_todos(self.config, ahora + 10)[0]
        self.assertTrue(vivo["en_linea"])
        self.assertAlmostEqual(vivo["edad"], 10, delta=1)
        viejo = m.leer_todos(self.config, ahora + m.VIGENTE + 60)[0]
        self.assertFalse(viejo["en_linea"])
        self.assertEqual(len(viejo["hilos"]), 1)  # apagado no es borrado: se sigue viendo lo último

    def test_un_archivo_roto_se_dice(self):
        carpeta = m.carpeta(self.config)
        carpeta.mkdir(parents=True)
        (carpeta / "roto.json").write_text("{")
        fila = m.leer_todos(self.config)[0]
        self.assertIn("no se pudo leer", fila["error"])
        self.assertFalse(fila["en_linea"])

    def test_sin_carpeta_no_hay_espejos(self):
        self.assertEqual(m.leer_todos(self.config), [])

    def test_un_reloj_adelantado_no_da_edad_negativa(self):
        m.guardar(self.config, "laptop", json.dumps(foto()))
        self.assertEqual(m.leer_todos(self.config, time.time() - 500)[0]["edad"], 0.0)


class LaFoto(Prueba):
    def test_no_viajan_los_archivados_ni_lo_que_se_queda_alla(self):
        cuerpos = {"A": {**hilo("A"), "ruta": "/home/x/secreto", "sesiones": ["uuid"], "archivado": False,
                         "ficha": {"etiqueta": "Cliente · A", "estado": "Estado: confidencial"}},
                   "B": {**hilo("B"), "archivado": True}}
        tel = SimpleNamespace(sesion="faro", hilos=[SimpleNamespace(archivado=c["archivado"], nombre=n) for n, c in cuerpos.items()])
        with mock.patch("telar.ordenes._comun.json_hilo", side_effect=lambda h, t, **k: cuerpos[h.nombre]):
            f = m.foto(tel, maquina="laptop", version_telar="0.1.9")
        self.assertEqual([h["nombre"] for h in f["hilos"]], ["A"])
        texto = json.dumps(f)
        for prohibido in ("secreto", "uuid", "confidencial"):
            self.assertNotIn(prohibido, texto)
        self.assertEqual(f["hilos"][0]["resumen"], "Cliente · A")
        m.validar(f, "laptop")  # lo que sale, entra


class DeExtremoAExtremo(ConCarpeta):
    """`publicar` en un «laptop» y `recibir` en un «servidor», con un ssh de mentira que corre
    la orden aquí mismo: prueba el guion completo (citado, con el PATH, por la entrada estándar)."""

    def test_publicar_llega_al_servidor(self):
        bin_ = self.base / "bin"
        bin_.mkdir()
        (bin_ / "ssh").write_text('#!/bin/sh\nwhile [ "$1" = "-o" ]; do shift 2; done\nshift\nexec sh -c "$*"\n')
        (bin_ / "telar").write_text(f'#!/bin/sh\nPYTHONPATH="{RAIZ / "src"}" exec "{sys.executable}" -m telar "$@"\n')
        for f in ("ssh", "telar"):
            (bin_ / f).chmod(0o755)
        servidor = self.base / "servidor"
        env = {"PATH": f"{bin_}:{os.environ['PATH']}", "HOME": str(self.base), "TELAR_ESTADO": str(servidor)}
        remoto = Remoto(nombre="casa", destino="nico@servidor")
        config = mod_config.Config(raiz=self.base, estado=self.base / "estado-laptop", remotos=(remoto,))
        from telar.ordenes import espejo as orden
        with mock.patch.dict(os.environ, env):
            error = orden.publicar_una_vez(Contexto(config=config), remoto, "mi-laptop")
        self.assertEqual(error, "")
        llegada = json.loads((servidor / "espejos" / "mi-laptop.json").read_text())
        self.assertEqual(llegada["maquina"], "mi-laptop")
        self.assertIn("hilos", llegada)

    def test_un_ssh_que_falla_se_dice_y_no_levanta_nada(self):
        bin_ = self.base / "bin"
        bin_.mkdir()
        (bin_ / "ssh").write_text('#!/bin/sh\necho "Connection timed out" >&2\nexit 255\n')
        (bin_ / "ssh").chmod(0o755)
        remoto = Remoto(nombre="casa", destino="nico@servidor")
        config = mod_config.Config(raiz=self.base, estado=self.base / "e", remotos=(remoto,))
        from telar.ordenes import espejo as orden
        with mock.patch.dict(os.environ, {"PATH": f"{bin_}:{os.environ['PATH']}"}):
            error = orden.publicar_una_vez(Contexto(config=config), remoto, "mi-laptop")
        self.assertIn("Connection timed out", error)
