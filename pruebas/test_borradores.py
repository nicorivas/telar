"""Los borradores de un hilo (telar.borradores): los próximos prompts que la persona guarda para mandárselos cuando le
toque. Dónde se guardan (el estado de la máquina del hilo), mandarlos (sin ⏎, con ⏎, en espera del fin del turno), la
API, la otra máquina por el bus, la CLI y que viajen con el hilo en la mudanza."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import borradores
from telar import config as mod_config
from telar import estado as mod_estado
from telar.modelo import Atencion, Hilo
from telar.mux import ErrorDeMux


def config_de(tmp: Path) -> mod_config.Config:
    return mod_config.Config(raiz=tmp, estado=tmp / "estado")


class FalsoMux:
    """Lo que `dormir.escribir` usa de un multiplexor: anota lo escrito, o falla si se le pide."""

    def __init__(self):
        self.escritos: list[tuple] = []
        self.falla = False

    def escribir(self, hilo, texto, enviar=False, pegar=False):
        if self.falla:
            raise ErrorDeMux("la ventana se cerró")
        self.escritos.append((hilo, texto, enviar, pegar))


class ConEstado(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-borradores-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.config = config_de(self.tmp)
        self.est = mod_estado.abrir(self.config)
        self.mux = FalsoMux()
        self.vivos = {"Faro", "Molino"}

    def telar(self):
        hilos = (Hilo(id="@1", nombre="Faro"), Hilo(id="@2", nombre="Molino"), Hilo(id="Cerrado", nombre="Cerrado"))
        return SimpleNamespace(mux=self.mux, estado=self.est, hilos=hilos, vivo=lambda h: h.nombre in self.vivos,
                               por_nombre=lambda n: next((h for h in hilos if h.nombre == n), None))

    def ids(self, hilo="Faro"):
        return [b["id"] for b in self.est.borradores(hilo)]


# ── dónde se guardan ──────────────────────────────────────────────────────────

class ElEstado(ConEstado):
    def test_uno_nuevo_va_al_final_y_reescribirlo_lo_deja_en_su_lugar(self):
        a = self.est.guardar_borrador("Faro", "primero", cuando=datetime(2026, 11, 25, 10, 0))
        b = self.est.guardar_borrador("Faro", "segundo")
        self.assertNotEqual(a["id"], b["id"])
        self.est.guardar_borrador("Faro", "primero, mejor dicho", a["id"])
        lista = self.est.borradores("Faro")
        self.assertEqual([x["texto"] for x in lista], ["primero, mejor dicho", "segundo"])
        self.assertEqual(lista[0]["creado"], "2026-11-25T10:00:00", "reescribirlo no cambia cuándo se creó")
        self.assertEqual(self.est.borradores("Molino"), [])
        with self.assertRaises(KeyError):
            self.est.guardar_borrador("Faro", "x", "b-no-existe")

    def test_quitar_esperar_y_tomar_el_que_espera(self):
        a = self.est.guardar_borrador("Faro", "uno")
        b = self.est.guardar_borrador("Faro", "dos")
        self.assertIsNone(self.est.tomar_borrador_en_espera("Faro"), "sin espera, nada que tomar")
        self.est.esperar_borrador("Faro", b["id"], "enviar")
        tomado = self.est.tomar_borrador_en_espera("Faro")
        self.assertEqual((tomado["id"], tomado["al_terminar"]), (b["id"], "enviar"))
        self.assertIsNone(self.est.tomar_borrador_en_espera("Faro"), "el que espera sale una vez")
        self.assertEqual(self.ids(), [a["id"]])
        self.assertEqual(self.est.quitar_borrador("Faro", a["id"])["texto"], "uno")
        self.assertIsNone(self.est.quitar_borrador("Faro", a["id"]))
        self.assertNotIn("Faro", self.est.todos_los_borradores(), "sin borradores, el hilo sale del archivo")

    def test_renombrar_los_lleva_y_olvidar_no_los_borra(self):
        self.est.guardar_borrador("Faro", "lo que escribí")
        self.est.renombrar("Faro", "Faro nuevo")
        self.assertEqual([b["texto"] for b in self.est.borradores("Faro nuevo")], ["lo que escribí"])
        self.est.olvidar("Faro nuevo")
        self.assertEqual(len(self.est.borradores("Faro nuevo")), 1, "lo escribió la persona: no se pierde con el tab")

    def test_la_cuenta_de_uno_de_otra_maquina_la_dice_su_dueno(self):
        self.est.guardar_borrador("Faro", "uno")
        self.est.guardar_borrador("Llevado", "copia vieja de cuando vivía aquí")
        self.est.guardar_ajenos({"Llevado": {"maquina": "servidor", "borradores": 3},
                                 "Otro": {"maquina": "servidor", "borradores": 0}})
        self.assertEqual(self.est.cuentas_borradores(), {"Faro": 1, "Llevado": 3})

    def test_lo_que_no_tiene_forma_de_borrador_no_se_ve(self):
        self.est._escribir("borradores", {"Faro": [{"id": "b1", "texto": "bien"}, {"texto": "sin id"}, "suelto"]})
        self.assertEqual(self.ids(), ["b1"])


class LaFila(ConEstado):
    """El indicio en la fila del hilo: cuántos tiene, de aquí y de otra máquina (la foto de su espejo)."""

    def test_el_json_del_hilo_y_la_foto_de_otra_maquina_lo_llevan(self):
        from telar import espejo
        from telar.ordenes import _comun

        h = Hilo(id="@1", nombre="Faro")
        self.est.guardar_borrador("Faro", "uno")
        tel = _comun.Telar(hilos=(h,), raiz=self.tmp, estado=self.est, borradores=self.est.cuentas_borradores())
        self.assertEqual(_comun.json_hilo(h, tel, con_ficha=False)["borradores"], 1)
        self.assertEqual(_comun.json_hilo(Hilo(id="@2", nombre="Molino"), tel, con_ficha=False)["borradores"], 0)
        foto = {"version": 1, "hilos": [{"nombre": "Faro", "borradores": 2}, {"nombre": "Molino", "borradores": "dos"},
                                         {"nombre": "Otro", "borradores": True}]}
        hilos = espejo.validar(foto, "servidor")["hilos"]
        self.assertEqual([h.get("borradores") for h in hilos], [2, None, None])


# ── mandarlos ─────────────────────────────────────────────────────────────────

class Mandar(ConEstado):
    def test_por_defecto_queda_escrito_sin_enter_y_sale_de_la_lista(self):
        b = self.est.guardar_borrador("Faro", "revisa el plan")
        r = borradores.mandar(self.config, self.telar(), "Faro", b["id"])
        self.assertEqual(r["como"], "escrito")
        self.assertEqual(self.mux.escritos, [("@1", "revisa el plan", False, False)])
        self.assertEqual(self.est.borradores("Faro"), [])

    def test_con_enviar_lleva_su_enter(self):
        b = self.est.guardar_borrador("Faro", "dale")
        self.assertEqual(borradores.mandar(self.config, self.telar(), "Faro", b["id"], enviar=True)["como"], "enviado")
        self.assertEqual(self.mux.escritos, [("@1", "dale", True, False)])

    def test_varias_lineas_sin_enter_van_pegadas(self):
        b = self.est.guardar_borrador("Faro", "uno\r\ndos\n")
        borradores.mandar(self.config, self.telar(), "Faro", b["id"])
        self.assertEqual(self.mux.escritos, [("@1", "uno\ndos", False, True)])

    def test_con_el_agente_trabajando_no_se_mezcla_con_su_turno(self):
        b = self.est.guardar_borrador("Faro", "lo siguiente")
        for atencion, ocupado in ((Atencion.TRABAJANDO, "trabajando"), (Atencion.ESPERA, "espera")):
            with self.subTest(atencion=atencion):
                self.est.anotar_atencion("Faro", atencion)
                with self.assertRaises(borradores.ErrorDeBorrador) as e:
                    borradores.mandar(self.config, self.telar(), "Faro", b["id"])
                self.assertEqual((e.exception.codigo, e.exception.datos), (409, {"ocupado": ocupado}))
        self.assertEqual(self.mux.escritos, [])
        self.assertEqual(self.ids(), [b["id"]], "sigue en la lista")

    def test_en_espera_sale_cuando_termina_su_turno_y_uno_por_turno(self):
        self.est.anotar_atencion("Faro", Atencion.TRABAJANDO)
        a = self.est.guardar_borrador("Faro", "primero")
        b = self.est.guardar_borrador("Faro", "segundo")
        r = borradores.mandar(self.config, self.telar(), "Faro", a["id"], enviar=True, esperar=True)
        self.assertEqual((r["como"], r["al_terminar"]), ("en espera", "enviar"))
        borradores.mandar(self.config, self.telar(), "Faro", b["id"], esperar=True)
        self.assertEqual(self.mux.escritos, [])
        self.assertEqual(borradores.pendientes(self.config), ["Faro"])
        # sigue trabajando: soltar no escribe nada
        self.assertEqual(borradores.soltar(self.config, self.telar(), "Faro", pausa=0), "")
        self.est.anotar_atencion("Faro", Atencion.TERMINO)
        self.assertEqual(borradores.soltar(self.config, self.telar(), "Faro", pausa=0), "enviado")
        self.assertEqual(self.mux.escritos, [("@1", "primero", True, False)])
        self.assertEqual(self.ids(), [b["id"]], "el segundo espera el próximo fin de turno")
        self.est.anotar_atencion("Faro", Atencion.TRABAJANDO)
        self.assertEqual(borradores.soltar(self.config, self.telar(), "Faro", pausa=0), "")
        self.est.anotar_atencion("Faro", Atencion.TERMINO)
        self.assertEqual(borradores.soltar(self.config, self.telar(), "Faro", pausa=0), "escrito")
        self.assertEqual(self.est.borradores("Faro"), [])

    def test_en_espera_de_uno_que_ya_termino_sale_al_tiro(self):
        b = self.est.guardar_borrador("Faro", "ya")
        r = borradores.mandar(self.config, self.telar(), "Faro", b["id"], esperar=True)
        self.assertEqual(r["como"], "escrito")
        self.assertEqual(len(self.mux.escritos), 1)

    def test_si_no_se_pudo_escribir_vuelve_a_su_lugar(self):
        a = self.est.guardar_borrador("Faro", "uno")
        b = self.est.guardar_borrador("Faro", "dos")
        self.est.guardar_borrador("Faro", "tres")
        self.mux.falla = True
        with self.assertRaises(borradores.ErrorDeBorrador) as e:
            borradores.mandar(self.config, self.telar(), "Faro", b["id"])
        self.assertEqual(e.exception.codigo, 502)
        self.assertEqual(self.ids()[:2], [a["id"], b["id"]])
        # y uno en espera que no se pudo escribir vuelve sin la espera, para que la persona lo vea
        self.est.esperar_borrador("Faro", b["id"], "escribir")
        self.est.anotar_atencion("Faro", Atencion.TERMINO)
        self.assertEqual(borradores.soltar(self.config, self.telar(), "Faro", pausa=0), "")
        vuelto = self.est.borradores("Faro")[1]
        self.assertEqual((vuelto["id"], vuelto.get("al_terminar")), (b["id"], None))

    def test_cerrado_vacio_o_que_ya_no_esta(self):
        b = self.est.guardar_borrador("Cerrado", "hola")
        with self.assertRaises(borradores.ErrorDeBorrador) as e:
            borradores.mandar(self.config, self.telar(), "Cerrado", b["id"])
        self.assertEqual((e.exception.codigo, e.exception.datos), (409, {"cerrado": True}))
        vacio = self.est.guardar_borrador("Faro", "  \n")
        with self.assertRaises(borradores.ErrorDeBorrador) as e:
            borradores.mandar(self.config, self.telar(), "Faro", vacio["id"])
        self.assertEqual(e.exception.codigo, 422)
        with self.assertRaises(borradores.ErrorDeBorrador) as e:
            borradores.mandar(self.config, self.telar(), "Faro", "b-ya-no")
        self.assertEqual(e.exception.codigo, 404)

    def test_el_fin_del_turno_lo_suelta_aparte_solo_si_hay_uno_en_espera(self):
        with mock.patch.object(borradores.subprocess, "Popen") as popen:
            self.assertFalse(borradores.al_terminar(self.config, "Faro"))
            b = self.est.guardar_borrador("Faro", "x")
            self.assertFalse(borradores.al_terminar(self.config, "Faro"), "guardado, pero no en espera")
            self.est.esperar_borrador("Faro", b["id"], "escribir")
            self.assertTrue(borradores.al_terminar(self.config, "Faro"))
        argv = popen.call_args.args[0]
        self.assertEqual(argv[-5:], ["hilo", "borradores", "--soltar", "--hilo", "Faro"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_el_evento_de_fin_de_turno_llama_a_soltar(self):
        from telar.ordenes import agente as orden_agente

        with mock.patch.object(borradores, "al_terminar") as al_terminar, \
                mock.patch.object(orden_agente, "_no_interactivo", return_value=False):
            with mock.patch.dict("os.environ", {"TELAR_ESTADO": str(self.config.estado)}):
                ctx = SimpleNamespace(config=self.config)
                for evento in ("empieza", "termina"):
                    orden_agente.main(["evento", "claude-code", "--evento", evento, "--hilo", "Faro"], ctx)
        self.assertEqual(self.est.atenciones()["Faro"][0], Atencion.TERMINO)
        self.assertEqual([c.args[1] for c in al_terminar.call_args_list], ["Faro"])


# ── la API y la otra máquina ──────────────────────────────────────────────────

class LaApi(ConEstado):
    def setUp(self):
        super().setUp()
        try:
            from fastapi.testclient import TestClient
        except ImportError:  # pragma: no cover - sin el extra serve
            self.skipTest("sin fastapi")
        from telar import api
        from telar.ordenes import _comun

        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)
        ctx = SimpleNamespace(config=self.config)
        api.app.dependency_overrides[api.contexto] = lambda: ctx
        self.addCleanup(api.app.dependency_overrides.clear)
        t = mock.patch.object(_comun, "tejer", lambda *a, **k: self.telar())
        t.start()
        self.addCleanup(t.stop)
        self.web = TestClient(api.app)

    def test_guardar_ver_mandar_y_borrar(self):
        r = self.web.post("/hilos/borradores", json={"hilo": "Faro", "texto": "uno"})
        self.assertEqual(r.status_code, 200)
        id = r.json()["id"]
        self.assertEqual(self.web.post("/hilos/borradores", json={"hilo": "Faro", "texto": "uno más", "id": id}).json()["texto"], "uno más")
        dos = self.web.post("/hilos/borradores", json={"hilo": "Faro", "texto": "dos"}).json()["id"]
        d = self.web.get("/hilos/borradores", params={"hilo": "Faro"}).json()
        self.assertEqual(([b["texto"] for b in d["borradores"]], d["ocupado"]), (["uno más", "dos"], ""))
        self.assertEqual(self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id}).json()["como"], "escrito")
        self.assertEqual(self.mux.escritos, [("@1", "uno más", False, False)])
        self.assertEqual(self.web.delete("/hilos/borradores", params={"hilo": "Faro", "id": dos}).status_code, 200)
        self.assertEqual(self.web.delete("/hilos/borradores", params={"hilo": "Faro", "id": dos}).status_code, 404)
        self.assertEqual(self.web.post("/hilos/borradores", json={"hilo": "Faro", "texto": "x", "id": dos}).status_code, 404)

    def test_ocupado_es_un_409_que_dice_por_que_y_esperar_lo_deja_en_espera(self):
        self.est.anotar_atencion("Faro", Atencion.TRABAJANDO)
        id = self.est.guardar_borrador("Faro", "después")["id"]
        self.assertEqual(self.web.get("/hilos/borradores", params={"hilo": "Faro"}).json()["ocupado"], "trabajando")
        r = self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id, "enviar": True})
        self.assertEqual((r.status_code, r.json()["ocupado"]), (409, "trabajando"))
        r = self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id, "enviar": True, "esperar": True})
        self.assertEqual(r.json()["como"], "en espera")
        self.assertEqual(self.est.borradores("Faro")[0]["al_terminar"], "enviar")
        r = self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id, "no_esperar": True})
        self.assertEqual(r.json()["al_terminar"], "")

    def test_de_otra_maquina_por_el_bus(self):
        """La página de aquí pide los de un hilo que vive en «servidor»: su nodo contesta (aquí, el mismo estado)."""
        from telar import bus as mod_bus
        from telar.servicios import borradores as sb

        pedidos = []

        def pedir(config, maquina, verbo, datos, espera=30):
            pedidos.append((maquina, verbo, datos.get("accion")))
            return sb.para_otra(SimpleNamespace(config=self.config), json.loads(json.dumps(datos)))

        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(mod_bus, "pedir", side_effect=pedir):
            id = self.web.post("/hilos/borradores", json={"hilo": "Faro", "texto": "allá", "maquina": "servidor"}).json()["id"]
            d = self.web.get("/hilos/borradores", params={"hilo": "Faro", "maquina": "servidor"}).json()
            self.assertEqual((d["maquina"], [b["id"] for b in d["borradores"]]), ("servidor", [id]))
            self.est.anotar_atencion("Faro", Atencion.TRABAJANDO)
            r = self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id, "maquina": "servidor"})
            self.assertEqual((r.status_code, r.json()["ocupado"]), (409, "trabajando"), "el 409 de allá llega con su porqué")
            self.est.anotar_atencion("Faro", Atencion.TERMINO)
            r = self.web.post("/hilos/borradores/mandar", json={"hilo": "Faro", "id": id, "maquina": "servidor", "enviar": True})
            self.assertEqual((r.json()["como"], r.json()["maquina"]), ("enviado", "servidor"))
        self.assertEqual({p[:2] for p in pedidos}, {("servidor", "borradores")})
        self.assertEqual([p[2] for p in pedidos], ["guardar", "ver", "mandar", "mandar"])


# ── la CLI ────────────────────────────────────────────────────────────────────

class LaCli(ConEstado):
    def correr(self, *argv):
        from telar.ordenes import _comun
        from telar.ordenes import hilo as orden

        salida = io.StringIO()
        with redirect_stdout(salida), mock.patch.object(_comun, "tejer", lambda *a, **k: self.telar()):
            codigo = orden.main(["borradores", *argv], SimpleNamespace(config=self.config))
        return codigo, salida.getvalue()

    def test_agregar_ver_mandar_y_borrar_por_su_numero(self):
        self.assertEqual(self.correr("Faro", "--agregar", "el primero")[0], 0)
        self.correr("Faro", "--agregar", "el segundo, con\nvarias líneas")
        codigo, texto = self.correr("Faro")
        self.assertEqual(codigo, 0)
        self.assertIn("2 borradores", texto)
        self.assertIn("el segundo, con varias líneas", texto)
        d = json.loads(self.correr("--hilo", "Faro", "--json")[1])
        self.assertEqual([b["texto"] for b in d["borradores"]], ["el primero", "el segundo, con\nvarias líneas"])
        self.assertEqual(self.correr("Faro", "--mandar", "2", "--enviar")[0], 0)
        self.assertEqual(self.mux.escritos, [("@1", "el segundo, con\nvarias líneas", True, False)])
        self.assertEqual(self.correr("Faro", "--borrar", d["borradores"][0]["id"])[0], 0)
        self.assertEqual(self.est.borradores("Faro"), [])
        self.assertNotEqual(self.correr("Faro", "--borrar", "1")[0], 0)

    def test_ocupado_dice_que_puede_esperar(self):
        self.est.anotar_atencion("Faro", Atencion.TRABAJANDO)
        self.correr("Faro", "--agregar", "luego")
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertNotEqual(self.correr("Faro", "--mandar", "1")[0], 0)
        self.assertIn("--esperar", err.getvalue())
        codigo, texto = self.correr("Faro", "--mandar", "1", "--esperar")
        self.assertEqual(codigo, 0)
        self.assertIn("termine el turno", texto)


# ── la mudanza ────────────────────────────────────────────────────────────────

class LaMudanza(ConEstado):
    def test_viajan_con_el_hilo_y_su_espera(self):
        from telar import mudanza

        a = self.est.guardar_borrador("Faro", "uno")
        self.est.guardar_borrador("Faro", "dos")
        self.est.esperar_borrador("Faro", a["id"], "enviar")
        registro = json.loads(json.dumps(mudanza.registro_de(self.est, "Faro")))
        alla = mod_estado.Estado(self.tmp / "alla")
        self.assertEqual(mudanza.aplicar_registro(alla, "Faro", registro), [])
        self.assertEqual(alla.borradores("Faro"), self.est.borradores("Faro"))
        self.assertEqual(alla.borradores("Faro")[0]["al_terminar"], "enviar")

    def test_de_un_telar_que_no_los_manda_quedan_los_de_aqui(self):
        from telar import mudanza

        self.est.guardar_borrador("Faro", "de aquí")
        mudanza.aplicar_registro(self.est, "Faro", {"padre": "", "etiquetas": []})
        self.assertEqual(len(self.est.borradores("Faro")), 1)


if __name__ == "__main__":
    unittest.main()
