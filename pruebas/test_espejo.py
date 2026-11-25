"""El espejo: la foto de los hilos de un laptop, guardada en el servidor y leída con su edad."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import espejo as m


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


class LoVistoViaja(ConCarpeta):
    """Si terminó sin que la persona lo viera, y desde cuándo: viaja en la foto, para que la otra máquina lo diga igual.
    Y lo que se vio en otra máquina de un hilo de esta vuelve en su foto: aquí también cuenta."""

    def test_sin_ver_y_desde_viajan_y_se_validan(self):
        limpia = m.validar(foto(hilo(sin_ver=True, atencion_desde="2026-11-11T09:00:00")), "laptop")
        self.assertIs(limpia["hilos"][0]["sin_ver"], True)
        self.assertEqual(limpia["hilos"][0]["atencion_desde"], "2026-11-11T09:00:00")
        self.assertNotIn("sin_ver", m.validar(foto(hilo(sin_ver="sí")), "laptop")["hilos"][0])
        with self.assertRaises(m.ErrorDeEspejo):
            m.validar(foto(hilo(atencion_desde=3)), "laptop")

    def test_lo_visto_alla_de_un_hilo_de_aqui_cuenta_aqui(self):
        from datetime import datetime

        from telar.ordenes import _comun

        m.guardar(self.config, "laptop", json.dumps(foto(
            hilo("Faro", remoto="servidor", visto="2026-11-11T11:40:00"),   # vive aquí: cuenta
            hilo("Molino", remoto="otra", visto="2026-11-11T11:40:00"),     # vive en otra: no
            hilo("Puente", remoto="", visto="2026-11-11T11:40:00"))))       # es de allá: no
        aqui = {"Faro": datetime(2026, 11, 10, 9, 0)}
        with mock.patch("telar.bus.maquina", return_value="servidor"):
            vistos = _comun.vistos_de_otras(self.config, aqui)
        self.assertEqual(vistos["Faro"], datetime(2026, 11, 11, 11, 40))
        self.assertNotIn("Molino", vistos)
        self.assertNotIn("Puente", vistos)
        # lo de aquí más nuevo gana
        aqui = {"Faro": datetime(2026, 11, 11, 12, 0)}
        with mock.patch("telar.bus.maquina", return_value="servidor"):
            self.assertEqual(_comun.vistos_de_otras(self.config, aqui)["Faro"], datetime(2026, 11, 11, 12, 0))


class LaPaginaDeLaMaquina(ConCarpeta):
    """La foto dice dónde está la página de su máquina (para reenviarle las terminales): solo esquema, host y
    puerto, y solo mientras la foto está vigente."""

    def test_pasa_una_direccion_y_no_otra_cosa(self):
        self.assertEqual(m.validar(foto(web="http://100.1.2.3:8780"), "laptop")["web"], "http://100.1.2.3:8780")
        for malo in ("javascript:alert(1)", "http://a/b", "http://a:8780/pty?x", "ftp://a", 3, ""):
            self.assertEqual(m.validar(foto(web=malo), "laptop")["web"], "", malo)

    def test_web_de_solo_si_esta_en_linea(self):
        m.guardar(self.config, "laptop", json.dumps(foto(web="http://100.1.2.3:8780")))
        self.assertEqual(m.web_de(self.config, "laptop"), "http://100.1.2.3:8780")
        self.assertEqual(m.web_de(self.config, "otra"), "")
        with mock.patch.object(m.time, "time", return_value=time.time() + m.VIGENTE + 5):
            self.assertEqual(m.web_de(self.config, "laptop"), "")


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
    def test_no_viaja_lo_que_se_queda_alla(self):
        cuerpos = {"A": {**hilo("A"), "ruta": "/home/x/secreto", "sesiones": ["uuid"], "archivado": False,
                         "ficha": {"etiqueta": "Cliente · A", "estado": "Estado: confidencial"}},
                   "B": {**hilo("B"), "archivado": True, "ruta": "/home/x/secreto", "sesiones": ["uuid"]}}
        tel = SimpleNamespace(sesion="faro", hilos=[SimpleNamespace(archivado=c["archivado"], nombre=n) for n, c in cuerpos.items()])
        with mock.patch("telar.ordenes._comun.json_hilo", side_effect=lambda h, t, **k: cuerpos[h.nombre]):
            f = m.foto(tel, maquina="laptop", version_telar="0.1.9")
        self.assertEqual([h["nombre"] for h in f["hilos"]], ["A"])
        texto = json.dumps(f)
        for prohibido in ("secreto", "uuid", "confidencial"):
            self.assertNotIn(prohibido, texto)
        self.assertEqual(f["hilos"][0]["resumen"], "Cliente · A")
        m.validar(f, "laptop")  # lo que sale, entra

    def test_los_archivados_viajan_aparte_y_con_poco(self):
        """Para que el ARCHIVO de la página de otra máquina los liste (el 24-nov, la del servidor mostraba 36 de los
        cientos que tiene el laptop): los suyos, con lo justo; no los que aquí son de otra máquina ni las ventanas."""
        cuerpos = {"Vivo": {**hilo("Vivo"), "archivado": False},
                   "Viejo": {**hilo("Viejo", etiquetas=["trabajo"], padre="Vivo", actividad="2026-11-20T10:00:00", prioridad=None),
                             "archivado": True, "ruta": "/home/x/secreto", "sesiones": ["uuid"], "dueno": ""},
                   "Reciente": {**hilo("Reciente", actividad="2026-11-24T10:00:00"), "archivado": True, "dueno": ""},
                   "De allá": {**hilo("De allá"), "archivado": True, "dueno": "servidor"},
                   "Ventana": {**hilo("Ventana", remoto="servidor"), "archivado": True, "dueno": ""}}
        tel = SimpleNamespace(sesion="faro", hilos=[SimpleNamespace(archivado=c["archivado"], nombre=n) for n, c in cuerpos.items()])
        with mock.patch("telar.ordenes._comun.json_hilo", side_effect=lambda h, t, **k: cuerpos[h.nombre]):
            f = m.foto(tel, maquina="laptop")
        self.assertEqual([h["nombre"] for h in f["hilos"]], ["Vivo"], "los archivados no van entre los hilos")
        self.assertEqual([a["nombre"] for a in f["archivados"]], ["Reciente", "Viejo"], "los suyos, lo más reciente primero")
        self.assertEqual(f["archivados"][1], {"nombre": "Viejo", "relativa": "proyectos/faro", "etiquetas": ["trabajo"],
                                              "padre": "Vivo", "actividad": "2026-11-20T10:00:00"})
        self.assertNotIn("secreto", json.dumps(f["archivados"]))
        limpia = m.validar(f, "laptop")
        self.assertEqual([a["nombre"] for a in limpia["archivados"]], ["Reciente", "Viejo"])
        # lo que llega se limpia: textos, etiquetas de texto, una prioridad entera; uno sin nombre no entra
        sucia = m.validar(foto(archivados=[{"nombre": "X", "relativa": 3, "etiquetas": ["a", 1], "prioridad": True,
                                            "sesiones": ["uuid"]}, {"relativa": "sin nombre"}, "basura"]), "servidor")
        self.assertEqual(sucia["archivados"], [{"nombre": "X", "etiquetas": ["a"]}])
        self.assertNotIn("archivados", m.validar(foto(), "servidor"), "una foto de un telar de antes no los trae")


class SusAgentes(ConCarpeta):
    """La foto trae los agentes residentes de su máquina (su carpeta, su nombre y el mundo que declara su agente.toml):
    así las otras los ven, con su mundo, aunque su carpeta todavía no les haya llegado (una raíz atrasada, 23-nov-2026)."""

    def test_viajan_limpios_y_lo_que_no_se_entiende_se_queda(self):
        agentes = [{"clave": "cocina", "nombre": "Cocina", "mundo": "personal", "carpeta": "/home/x/secreto"},
                   {"clave": "../fuera", "nombre": "Malo", "mundo": ""}, {"clave": "sin-nombre", "nombre": ""},
                   {"clave": "secretaria", "nombre": "Secretaría", "mundo": 3}, "basura"]
        limpia = m.validar(foto(agentes=agentes), "telar")
        self.assertEqual(limpia["agentes"], [{"clave": "cocina", "nombre": "Cocina", "mundo": "personal"}])
        self.assertNotIn("agentes", m.validar(foto(), "telar"), "una foto de un telar de antes no los trae")
        m.guardar(self.config, "telar", json.dumps(foto(agentes=agentes[:1])))
        self.assertEqual(m.leer_todos(self.config)[0]["agentes"][0]["clave"], "cocina")

    def test_los_de_esta_maquina_salen_de_su_carpeta(self):
        carpeta = self.base / "agentes" / "cocina"
        carpeta.mkdir(parents=True)
        (carpeta / "CLAUDE.md").write_text("# Cocina\n")
        (carpeta / "agente.toml").write_text('nombre = "Cocina"\nmundo = "personal"\n')
        c = mod_config.desde_dict({"raiz": str(self.base), "agentes": {"carpeta": "agentes"}})
        self.assertEqual(m.agentes_de(c), [{"clave": "cocina", "nombre": "Cocina", "mundo": "personal",
                                            "fuera_de_su_mundo": "al-final"}])
        self.assertEqual(m.agentes_de(mod_config.desde_dict({"raiz": str(self.base)})), [], "sin carpeta de agentes, ninguno")
        tel = SimpleNamespace(sesion="faro", hilos=[])
        self.assertEqual(m.foto(tel, maquina="telar", agentes=m.agentes_de(c))["agentes"][0]["mundo"], "personal")
        self.assertNotIn("agentes", m.foto(tel, maquina="telar"))
