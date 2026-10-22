"""La gestión de personas del bus (telar.personas): roles, quién puede qué, el servicio `admin.<dueño>` en la
configuración del servidor, y la acción por el nodo, la CLI y la API."""

from __future__ import annotations

import io
import json
import os
import tempfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cuentas, personas, unirse

QUIEN = {"cuenta": "carla@example.com", "maquina": "pc-de-carla"}
H = {n: "$2b$11$" + c * 53 for n, c in (("ana", "a"), ("beto", "b"), ("carla", "c"), ("dani", "d"))}


class EnLaMaquinaDelBus(Prueba):
    """Las cuentas en una carpeta temporal; «ana» corre el bus."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        entorno = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name})
        entorno.start()
        self.addCleanup(entorno.stop)
        cuentas.escribir(cuentas.carpeta(), {"ana": H["ana"], "beto": H["beto"]})
        recarga = mock.patch.object(unirse, "recargar_bus", return_value="")
        self.recargas = recarga.start()
        self.addCleanup(recarga.stop)

    def pedido(self, persona="carla"):
        return unirse.recibir({"persona": persona, "maquina": "pc", "hash": H[persona], "equipo": "faro"},
                              "100.70.1.3", {**QUIEN, "cuenta": f"{persona}@example.com"})["id"]

    def conf(self) -> str:
        return (cuentas.carpeta() / "servidor.conf").read_text()

    def test_ver_anota_al_dueno_y_ordena_por_rol(self):
        r = personas.atender("ana", "ana", {"accion": "ver"})
        self.assertEqual(r["personas"], [{"nombre": "ana", "rol": "dueño"}, {"nombre": "beto", "rol": "miembro"}])
        self.assertEqual((r["dueno"], r["quien"], r["rol"]), ("ana", "ana", "dueño"))
        self.assertEqual(cuentas.leer_roles(cuentas.carpeta()), {"ana": "dueño"})

    def test_un_miembro_no_puede_nada(self):
        personas.atender("ana", "ana", {"accion": "ver"})
        for pedido in ({"accion": "ver"}, {"accion": "quitar", "nombre": "ana"}, {"accion": "rol", "nombre": "beto", "rol": "admin"}):
            with self.assertRaises(personas.ErrorDePersonas) as e:
                personas.atender("ana", "beto", pedido)
            self.assertEqual(e.exception.codigo, 403)
        with self.assertRaises(personas.ErrorDePersonas):
            personas.atender("ana", "", {"accion": "ver"})

    def test_aprobar_como_admin_y_el_servicio_admin_se_exporta_solo_a_el(self):
        pid = self.pedido()
        r = personas.atender("ana", "ana", {"accion": "aprobar", "pedido": pid, "rol": "admin"})
        self.assertIn("carla: cuenta nueva", r["hecho"])
        self.assertIn({"nombre": "carla", "rol": "admin"}, r["personas"])
        self.assertEqual(self.recargas.call_count, 1)
        p = next(x for x in r["pedidos"] if x["id"] == pid)
        self.assertEqual((p["estado"], p["por"]), ("aprobado", "ana"))
        conf = self.conf()
        self.assertIn('{ service: "admin.ana", accounts: [ "carla" ] }', conf)
        self.assertEqual(conf.count('subject: "admin.ana"'), 1)  # solo carla lo importa
        bloque_beto = conf.split("  beto: {")[1].split("  carla: {")[0]
        self.assertNotIn("admin.ana", bloque_beto)

    def test_un_admin_aprueba_rechaza_quita_y_cambia_roles_salvo_lo_del_dueno(self):
        personas.atender("ana", "ana", {"accion": "rol", "nombre": "beto", "rol": "admin"})
        pid = self.pedido("carla")
        personas.atender("ana", "beto", {"accion": "aprobar", "pedido": pid})
        self.assertIn("carla", cuentas.leer(cuentas.carpeta()))
        pid2 = self.pedido("dani")
        r = personas.atender("ana", "beto", {"accion": "rechazar", "pedido": pid2})
        self.assertNotIn("dani", cuentas.leer(cuentas.carpeta()))
        self.assertEqual(next(x for x in r["pedidos"] if x["id"] == pid2)["por"], "beto")
        personas.atender("ana", "beto", {"accion": "rol", "nombre": "carla", "rol": "admin"})
        personas.atender("ana", "beto", {"accion": "quitar", "nombre": "carla"})
        self.assertNotIn("carla", cuentas.leer(cuentas.carpeta()))
        self.assertNotIn("carla", cuentas.leer_roles(cuentas.carpeta()))  # su rol se fue con la cuenta
        for pedido in ({"accion": "quitar", "nombre": "ana"}, {"accion": "rol", "nombre": "ana", "rol": "miembro"},
                       {"accion": "quitar", "nombre": "beto"}):
            with self.assertRaises(personas.ErrorDePersonas):
                personas.atender("ana", "beto", pedido)
        self.assertEqual(set(cuentas.leer(cuentas.carpeta())), {"ana", "beto"})

    def test_bajar_a_miembro_le_saca_el_servicio(self):
        personas.atender("ana", "ana", {"accion": "rol", "nombre": "beto", "rol": "admin"})
        self.assertIn("admin.ana", self.conf())
        r = personas.atender("ana", "ana", {"accion": "rol", "nombre": "beto", "rol": "miembro"})
        self.assertEqual(r["hecho"], "beto: ahora miembro")
        self.assertNotIn("admin.ana", self.conf())
        r = personas.atender("ana", "ana", {"accion": "rol", "nombre": "beto", "rol": "miembro"})
        self.assertEqual(r["hecho"], "beto ya es miembro")

    def test_lo_que_no_sirve(self):
        for pedido, codigo in (({"accion": "borrar"}, 422), ({"accion": "aprobar"}, 422),
                               ({"accion": "aprobar", "pedido": "x", "rol": "dueño"}, 422),
                               ({"accion": "quitar", "nombre": "zoe"}, 404),
                               ({"accion": "rol", "nombre": "beto", "rol": "jefe"}, 422)):
            with self.assertRaises(personas.ErrorDePersonas) as e:
                personas.atender("ana", "ana", pedido)
            self.assertEqual(e.exception.codigo, codigo, pedido)

    def test_fuera_de_la_maquina_del_bus_no_atiende(self):
        (cuentas.carpeta() / "servidor.conf").unlink()
        with self.assertRaises(personas.ErrorDePersonas) as e:
            personas.atender("ana", "ana", {"accion": "ver"})
        self.assertEqual(e.exception.codigo, 404)

    def test_el_nodo_sabe_quien_pide_por_la_cabecera_del_servidor(self):
        personas.atender("ana", "ana", {"accion": "ver"})
        r = personas.atender_pedido_del_bus("ana", b'{"accion": "ver"}', None)
        self.assertEqual((r["ok"], r["quien"]), (True, "ana"))  # sin cruzar de cuenta: la misma persona
        r = personas.atender_pedido_del_bus("ana", b'{"accion": "ver"}', {"Nats-Request-Info": json.dumps({"acc": "beto"})})
        self.assertEqual((r["ok"], r["codigo"]), (False, 403))
        r = personas.atender_pedido_del_bus("ana", b"no", None)
        self.assertEqual((r["ok"], r["codigo"]), (False, 422))

    def test_pedir_en_la_maquina_del_bus_lo_hace_aqui(self):
        config = SimpleNamespace(bus=SimpleNamespace(url="", persona="ana", administra="", token="", maquina=""))
        r = personas.pedir(config, {"accion": "ver"})
        self.assertEqual(r["rol"], "dueño")

    def test_la_cli(self):
        from telar.ordenes import bus as orden_bus

        ctx = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="", persona="ana", administra="", token="", maquina="")))
        pid = self.pedido()
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(orden_bus.main(["pedidos"], ctx), 0)
            self.assertEqual(orden_bus.main(["aprobar", pid, "--rol", "admin"], ctx), 0)
            self.assertEqual(orden_bus.main(["personas"], ctx), 0)
            self.assertEqual(orden_bus.main(["rol", "carla", "miembro"], ctx), 0)
        texto = salida.getvalue()
        self.assertIn(pid, texto)
        self.assertIn("carla: cuenta nueva en el bus, como admin.", texto)
        self.assertIn("carla: ahora miembro.", texto)
        self.assertRegex(texto, r"ana\s+dueño")


class LaConfiguracionDelServidor(Prueba):
    def test_sin_roles_es_la_de_siempre(self):
        self.assertNotIn("admin.", cuentas.configuracion({"ana": H["ana"], "beto": H["beto"]}))
        # un dueño sin admin no exporta nada: sus máquinas lo piden dentro de su cuenta
        self.assertNotIn("admin.", cuentas.configuracion({"ana": H["ana"]}, {"ana": "dueño"}))

    def test_un_admin_sin_cuenta_no_entra(self):
        conf = cuentas.configuracion({"ana": H["ana"], "beto": H["beto"]}, {"ana": "dueño", "zoe": "admin"})
        self.assertNotIn("admin.", conf)

    def test_roles_que_no_sirven(self):
        with tempfile.TemporaryDirectory() as d:
            for malo in ('{"ana": "jefe"}', '{"ana": "dueño", "beto": "dueño"}', "[]", "no"):
                (cuentas.Path(d) / "roles.json").write_text(malo)
                with self.assertRaises(cuentas.ErrorDeCuentas, msg=malo):
                    cuentas.leer_roles(cuentas.Path(d))


if __name__ == "__main__":
    import unittest

    unittest.main()
