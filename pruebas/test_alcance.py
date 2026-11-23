"""Despertar y escribirle a un hilo de otra máquina, con esa máquina en línea, fuera de línea o con un telar de antes
(telar.alcance). Dos nodos de mentira: el servidor (esta máquina, la que pide) y el laptop, cuyo nodo se reemplaza por
una función que contesta lo que contestaría el suyo; si está fuera de línea, su foto es vieja y el bus no lo alcanza. El
bus mismo no corre: aquí se prueba lo que se decide con lo que se sabe de cada máquina, no NATS (eso es test_bus.py)."""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import alcance
from telar import bus as mod_bus
from telar import config as mod_config
from telar import espejo
from telar.modelo import Hilo


class Nodos:
    """El bus con dos máquinas de mentira. `laptop` contesta con `atender` mientras `en_linea`; fuera de línea, su foto
    envejece y lo que se le pide vuelve como volvería del bus de verdad (sin respuesta a tiempo). `viejo`: su telar no
    sabe de texto (contesta {ok} solo) y no atiende los verbos de `no_atiende`."""

    def __init__(self, prueba: "Base"):
        self.prueba = prueba
        self.pedidos: list[tuple[str, str, dict]] = []
        self.en_linea = True
        self.viejo = False
        self.no_atiende: set[str] = set()
        self.respuesta: dict = {"ok": True, "hecho": "«Catedral» despertó (conversación c4t3dr4l)", "estaba": "dormido"}

    def pedir(self, config, a_maquina, verbo, datos, *, espera=30):
        self.pedidos.append((a_maquina, verbo, dict(datos)))
        if a_maquina != "laptop" or not self.en_linea:
            return mod_bus._sin_respuesta(config, a_maquina, verbo, {
                "ok": False, "error": f"{a_maquina} no respondió a tiempo (¿está apagada o sin su nodo?)"})
        if verbo in self.no_atiende:
            return mod_bus._sin_respuesta(config, a_maquina, verbo, {
                "ok": False, "sin_servicio": True, "error": f"{a_maquina} no atiende «{verbo}»"})
        if self.viejo:
            return {"ok": True}
        return dict(self.respuesta)


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="servidor"))
        self.ctx = SimpleNamespace(config=self.config)
        self.nodos = Nodos(self)
        p = mock.patch.object(mod_bus, "pedir", side_effect=self.nodos.pedir)
        p.start()
        self.addCleanup(p.stop)
        self.enviados: list[dict] = []
        p = mock.patch.object(mod_bus, "enviar", side_effect=lambda config, para, texto, **kw: self.enviados.append(
            {"para": para, "texto": texto, **kw}) or {"id": "m1", "para": para})
        p.start()
        self.addCleanup(p.stop)
        alcance.marcar_al_dia(self.config)
        self.foto(edad=10)

    def foto(self, maquina="laptop", edad=10.0, telar="0.13.0", hilos=None):
        """La foto de `maquina`, llegada hace `edad` segundos (fuera de línea, pasado `espejo.VIGENTE`)."""
        d = espejo.carpeta(self.config)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{maquina}.json").write_text(json.dumps({
            "version": 1, "maquina": maquina, "telar": telar, "publicado": "", "sesion": "telar", "web": "",
            "hilos": hilos if hilos is not None else [{"nombre": "Catedral", "vivo": True, "atencion": "trabajando"}],
            "recibido": time.time() - edad}))

    def fuera(self, horas=2.0):
        self.nodos.en_linea = False
        self.foto(edad=horas * 3600)


class Alcance(Base):
    def test_en_linea_fuera_y_sin_saber(self):
        self.assertFalse(alcance.de(self.config, "laptop").fuera)
        self.fuera()
        a = alcance.de(self.config, "laptop")
        self.assertTrue(a.fuera)
        hace = datetime.fromtimestamp(time.time() - 7200)
        if hace.date() == datetime.now().date():
            self.assertEqual(a.frase(), f"laptop fuera de línea desde {hace:%H:%M}")
        self.assertTrue(a.desde_iso())
        # una máquina sin foto: no se sabe, y se le pregunta como siempre
        self.assertFalse(alcance.de(self.config, "otra").fuera)
        # aquí siempre se alcanza
        self.assertTrue(alcance.de(self.config, "servidor").aqui)

    def test_con_el_nodo_de_aqui_sin_noticias_una_foto_vieja_no_dice_nada(self):
        self.fuera()
        alcance._marca(self.config).unlink()
        self.assertFalse(alcance.de(self.config, "laptop").fuera, "la que no tiene noticias es esta")

    def test_desde_cuando_en_palabras(self):
        ahora = datetime(2026, 11, 22, 16, 30).timestamp()
        self.assertEqual(alcance.desde_texto(datetime(2026, 11, 22, 14, 2).timestamp(), ahora), "14:02")
        self.assertEqual(alcance.desde_texto(datetime(2026, 11, 21, 23, 50).timestamp(), ahora), "ayer 23:50")
        self.assertEqual(alcance.desde_texto(datetime(2026, 11, 2, 9, 5).timestamp(), ahora), "el 2-nov 09:05")
        self.assertEqual(alcance.desde_texto(None), "?")


class Despertar(Base):
    def test_en_linea_va_a_su_nodo_con_el_texto(self):
        r = alcance.despertar(self.ctx, "Catedral", "laptop", "sigue con la nave")
        self.assertEqual(self.nodos.pedidos, [("laptop", "hilo-despertar", {"hilo": "Catedral", "texto": "sigue con la nave"})])
        self.assertIn("despertó", r["hecho"])
        self.assertIn("(en laptop)", r["hecho"])
        self.assertFalse(r["en_cola"])
        self.assertEqual(alcance.cola(self.config), {})

    def test_fuera_de_linea_queda_en_cola_sin_preguntarle(self):
        self.fuera()
        r = alcance.despertar(self.ctx, "Catedral", "laptop", "sigue", por="la página")
        self.assertEqual(self.nodos.pedidos, [], "no se espera el plazo del bus: se sabe que no está")
        self.assertTrue(r["en_cola"])
        self.assertIn("laptop fuera de línea desde", r["hecho"])
        self.assertIn("se despierta cuando vuelva", r["hecho"])
        (p,) = alcance.cola(self.config)["laptop"]
        self.assertEqual((p["hilo"], p["texto"], p["por"]), ("Catedral", "sigue", "la página"))
        # pedirlo de nuevo no deja dos: el texto se suma
        r = alcance.despertar(self.ctx, "Catedral", "laptop", "y revisa el techo")
        self.assertIn("ya estaba en cola", r["hecho"])
        (p,) = alcance.cola(self.config)["laptop"]
        self.assertEqual(p["texto"], "sigue\n\ny revisa el techo")

    def test_se_fue_recien_su_foto_no_envejece_todavia(self):
        self.nodos.en_linea = False  # el bus no lo alcanza, pero su foto tiene 10 s
        with self.assertRaises(RuntimeError) as e:
            alcance.despertar(self.ctx, "Catedral", "laptop")
        self.assertIn("no respondió a tiempo", str(e.exception))
        self.assertEqual(alcance.cola(self.config), {}, "sin saber que se fue, no se deja en cola")

    def test_un_nodo_de_antes_lo_dice(self):
        self.nodos.viejo = True
        r = alcance.despertar(self.ctx, "Catedral", "laptop", "sigue")
        self.assertIn("retomado en laptop", r["hecho"])
        self.assertIn("telar de antes", r["aviso"])
        self.assertIn("el texto no le llegó", r["aviso"])

    def test_un_nodo_que_no_atiende_el_verbo_es_viejo(self):
        self.nodos.no_atiende = {"hilo-despertar"}
        with self.assertRaises(RuntimeError) as e:
            alcance.despertar(self.ctx, "Catedral", "laptop")
        self.assertIn("está en línea pero su telar no atiende «hilo-despertar»", str(e.exception))
        self.assertIn("0.13.0", str(e.exception))


class Cola(Base):
    """Lo que el nodo de aquí hace con la cola (`atender`), cada pocos segundos."""

    def test_al_volver_se_hace_y_se_anota(self):
        self.fuera()
        alcance.despertar(self.ctx, "Catedral", "laptop", "sigue", por_hilo="Telar")
        self.assertEqual(alcance.atender(self.ctx), [], "sigue fuera: nada")
        self.assertEqual(self.nodos.pedidos, [])
        # vuelve: su foto llega de nuevo
        self.nodos.en_linea = True
        self.foto(edad=1)
        dicho = alcance.atender(self.ctx)
        self.assertEqual(self.nodos.pedidos, [("laptop", "hilo-despertar", {"hilo": "Catedral", "texto": "sigue", "en_cola": True})])
        self.assertEqual(len(dicho), 1)
        self.assertIn("en cola para laptop desde", dicho[0])
        self.assertIn("despertó", dicho[0])
        self.assertEqual(alcance.cola(self.config), {})
        (h,) = alcance.hechos(self.config)["laptop"]
        self.assertTrue(h["ok"])
        # a quien lo pidió le llega un aviso, que no lo despierta
        self.assertEqual([(m["para"], m["modo"]) for m in self.enviados], [("Telar", "aviso")])

    def test_sin_respuesta_se_intenta_con_cada_foto_nueva_y_al_final_falla(self):
        self.fuera()
        alcance.despertar(self.ctx, "Catedral", "laptop")
        self.foto(edad=1)  # su foto vuelve, pero su nodo no contesta
        for i in range(alcance.INTENTOS):
            alcance.atender(self.ctx)
            self.assertEqual(len(self.nodos.pedidos), i + 1)
            alcance.atender(self.ctx)
            self.assertEqual(len(self.nodos.pedidos), i + 1, "con la misma foto, no se repite")
            time.sleep(0.01)
            self.foto(edad=0)
        self.assertEqual(alcance.cola(self.config), {})
        (h,) = alcance.hechos(self.config)["laptop"]
        self.assertFalse(h["ok"])
        self.assertIn("no se pudo despertar a «Catedral» en laptop", h["resultado"])

    def test_un_nodo_viejo_hace_lo_suyo_y_se_dice(self):
        self.fuera()
        alcance.despertar(self.ctx, "Catedral", "laptop", "sigue")
        self.nodos.en_linea, self.nodos.viejo = True, True
        self.foto(edad=1)
        (linea,) = alcance.atender(self.ctx)
        self.assertIn("telar de antes: el texto no le llegó", linea)

    def test_lo_que_el_dueno_no_pudo_queda_fallado(self):
        self.fuera()
        alcance.despertar(self.ctx, "Catedral", "laptop")
        self.nodos.en_linea = True
        self.nodos.respuesta = {"ok": False, "error": "aquí no hay un hilo «Catedral»"}
        self.foto(edad=1)
        alcance.atender(self.ctx)
        (h,) = alcance.hechos(self.config)["laptop"]
        self.assertFalse(h["ok"])
        self.assertIn("aquí no hay un hilo", h["resultado"])


class ElDueno(Base):
    """Lo que hace la máquina del hilo cuando se lo piden (`despertar_aqui`, el verbo `hilo-despertar` de su nodo)."""

    def telar(self, *hilos, vivos=()):
        return SimpleNamespace(hilos=list(hilos), vivo=lambda h: h.nombre in vivos, mux=object(), estado=None)

    def test_dormido_despierta_en_su_ventana_con_el_texto(self):
        from telar import dormir

        tel = self.telar(Hilo(id="@1", nombre="Catedral"), vivos=("Catedral",))
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch.object(dormir, "dormido", return_value=True), \
                mock.patch.object(dormir, "despertar", return_value="«Catedral» despertó (conversación c4t3)") as d:
            r = alcance.despertar_aqui(self.ctx, "Catedral", "sigue")
        self.assertEqual(r, {"ok": True, "hecho": "«Catedral» despertó (conversación c4t3)", "estaba": "dormido"})
        self.assertEqual(d.call_args.kwargs["mensaje"], "sigue")

    def test_despierto_queda_como_esta(self):
        from telar import dormir

        tel = self.telar(Hilo(id="@1", nombre="Catedral"), vivos=("Catedral",))
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), mock.patch.object(dormir, "dormido", return_value=False), \
                mock.patch("telar.ordenes.hilo.main") as orden:
            r = alcance.despertar_aqui(self.ctx, "Catedral")
        self.assertEqual(r["estaba"], "despierto")
        orden.assert_not_called()  # ni retomarlo ni moverle el foco

    def test_cerrado_se_retoma_con_su_conversacion(self):
        tel = self.telar(Hilo(id="Catedral", nombre="Catedral", archivado=True))

        def retomar(argv, ctx):
            print("retomado «Catedral» · conversación c4t3")
            return 0

        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.ordenes.hilo.main", side_effect=retomar) as orden:
            r = alcance.despertar_aqui(self.ctx, "Catedral", "sigue")
        self.assertEqual(orden.call_args.args[0], ["retomar", "--hilo", "Catedral", "--texto", "sigue"])
        self.assertEqual(r, {"ok": True, "estaba": "archivado", "hecho": "retomado «Catedral» · conversación c4t3"})

    def test_uno_que_no_conoce_no_se_abre(self):
        with mock.patch("telar.ordenes._comun.tejer", return_value=self.telar()), mock.patch("telar.ordenes.hilo.main") as orden:
            r = alcance.despertar_aqui(self.ctx, "Catedrall")
        self.assertFalse(r["ok"])
        self.assertIn("aquí no hay un hilo «Catedrall»", r["error"])
        orden.assert_not_called()

    def test_la_ventana_que_solo_lo_mira_no_es_su_duena(self):
        tel = self.telar(Hilo(id="@2", nombre="Catedral", remoto="laptop"), vivos=("Catedral",))
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel):
            r = alcance.despertar_aqui(self.ctx, "Catedral")
        self.assertIn("no vive aquí", r["error"])

    def test_su_nodo_le_pasa_el_texto(self):
        from telar.ordenes import nodo

        n = nodo.Nodo.__new__(nodo.Nodo)
        n.ctx = self.ctx
        respondido = {}

        async def responder(m, hacer):
            respondido.update(hacer({"hilo": "Catedral", "texto": "sigue"}))

        n._responder = responder
        with mock.patch.object(alcance, "despertar_aqui", return_value={"ok": True, "hecho": "h"}) as d:
            asyncio.run(n._hilo_despertar(None))
        self.assertEqual(d.call_args.args[1:], ("Catedral", "sigue"))
        self.assertEqual(respondido, {"ok": True, "hecho": "h"})


class Ordenes(Base):
    """Lo que dicen las órdenes: `telar hilo despertar --maquina`, `telar hilo leer --maquina`, `telar mensaje` y
    `telar hilos --red`, con el laptop en línea y fuera de línea."""

    def correr(self, modulo, argv):
        salida, error = io.StringIO(), io.StringIO()
        tel = SimpleNamespace(hilos=[], vivo=lambda h: False, mux=None, viva=False, estado=None, aviso="", sesion="telar",
                              raiz=Path(self.tmp.name), unidades=None, por_nombre=lambda n: None, vivos=frozenset())
        with redirect_stdout(salida), redirect_stderr(error), mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.ordenes._comun.json_hilo", side_effect=lambda h, t, **kw: {"nombre": h.nombre}):
            codigo = modulo.main(argv, self.ctx)
        return codigo, salida.getvalue(), error.getvalue()

    def test_despertar_con_maquina_en_linea(self):
        from telar.ordenes import hilo

        codigo, salida, _ = self.correr(hilo, ["despertar", "Catedral", "--maquina", "laptop"])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.nodos.pedidos[0][:2], ("laptop", "hilo-despertar"))
        self.assertIn("despertó", salida)
        self.assertNotIn("no estaba dormido", salida)

    def test_despertar_con_maquina_fuera_de_linea_queda_en_cola(self):
        from telar.ordenes import hilo

        self.fuera()
        codigo, salida, _ = self.correr(hilo, ["despertar", "Catedral", "--maquina", "laptop", "--texto", "sigue"])
        self.assertEqual(codigo, 0)
        self.assertIn("laptop fuera de línea desde", salida)
        self.assertIn("se despierta cuando vuelva", salida)
        self.assertEqual(self.nodos.pedidos, [])
        self.assertEqual(alcance.cola(self.config)["laptop"][0]["texto"], "sigue")

    def test_despertar_sin_maquina_la_dice_el_bus(self):
        from telar.ordenes import hilo

        with mock.patch.object(mod_bus, "maquina_de", return_value="laptop"):
            codigo, salida, _ = self.correr(hilo, ["despertar", "Catedral", "--json"])
        self.assertEqual(codigo, 0)
        d = json.loads(salida.strip().splitlines()[-1])
        self.assertEqual(d["despertar"]["maquina"], "laptop")
        self.assertEqual(d["codigo"], 0)
        self.assertIn("hilo", d, "la pieza `hilo` de siempre")

    def test_leer_de_una_maquina_fuera_de_linea_lo_dice(self):
        from telar.ordenes import hilo

        self.fuera()
        codigo, _, error = self.correr(hilo, ["leer", "Catedral", "--maquina", "laptop"])
        self.assertEqual(codigo, 2)
        self.assertIn("laptop fuera de línea desde", error)
        self.assertNotIn("no atiende", error)

    def test_un_mensaje_a_un_hilo_de_una_maquina_fuera_de_linea(self):
        from telar.ordenes import mensaje

        self.fuera()
        # abierto allá cuando se fue: el mensaje espera en el bus y lo recoge al volver; nada en cola
        with mock.patch.object(mod_bus, "estado_de", return_value={"maquina": "laptop", "vivo": True}):
            r = mensaje.despertar(self.ctx, "Catedral")
        self.assertIn("laptop fuera de línea desde", r["en_cola"])
        self.assertNotIn("cola", {k for k, v in r.items() if v is True})
        self.assertEqual(alcance.cola(self.config), {})
        # cerrado allá: retomarlo queda en cola para cuando vuelva, sin esperar el plazo del bus
        with mock.patch.object(mod_bus, "estado_de", return_value={"maquina": "laptop", "vivo": False, "archivado": True}):
            r = mensaje.despertar(self.ctx, "Catedral")
        self.assertTrue(r["cola"])
        self.assertEqual(self.nodos.pedidos, [])
        self.assertEqual(alcance.cola(self.config)["laptop"][0]["por"], "un mensaje")

    def test_hilos_red_dice_fuera_de_linea_e_inalcanzables(self):
        from telar.ordenes import hilos
        from telar.servicios import hilos as servicio

        self.fuera()
        alcance.encolar(self.config, "laptop", "Catedral", por="la página")
        registro = {"Catedral": {"nombre": "Catedral", "maquina": "laptop", "vivo": True, "dormido": True,
                                 "atencion": "ninguna"},
                    "Faro": {"nombre": "Faro", "maquina": "laptop", "vivo": False, "atencion": "ninguna"}}
        with mock.patch.object(mod_bus, "estados", return_value=registro):
            otras, maquinas, aviso = servicio._red(self.ctx)
        self.assertEqual(aviso, "")
        cat = next(h for h in otras if h["nombre"] == "Catedral")
        self.assertFalse(cat["alcanzable"])
        self.assertTrue(cat["fuera_de_linea_desde"])
        (lap,) = [m for m in maquinas if m["nombre"] == "laptop"]
        self.assertTrue(lap["desde"])
        self.assertEqual([p["hilo"] for p in lap["cola"]], ["Catedral"])
        salida = io.StringIO()
        r = SimpleNamespace(aviso_red="", otras_maquinas=[servicio.OtroHilo(**h) for h in otras],
                            maquinas=[servicio.Maquina(**m) for m in maquinas])
        with redirect_stdout(salida):
            hilos._imprimir_red(r)
        texto = salida.getvalue()
        self.assertIn("laptop · fuera de línea desde", texto)
        self.assertIn("Catedral  inalcanzable (cuando se fue, dormía)", texto)
        self.assertNotIn("◌", texto, "ni dormido ni vivo: inalcanzable")
        self.assertIn("en cola desde", texto)
        self.assertIn("despertar «Catedral»", texto)

    def test_la_ventana_de_aqui_de_un_hilo_de_alla(self):
        from telar.servicios import hilos as servicio

        self.fuera()
        lista = [{"nombre": "Catedral", "remoto": "laptop"}, {"nombre": "Telar", "remoto": ""}]
        servicio._con_alcance(lista, self.ctx)
        self.assertFalse(lista[0]["alcanzable"])
        self.assertNotIn("alcanzable", lista[1])


class PorElBusDeVerdad(Base):
    """`bus.pedir` con una conexión de mentira que nadie atiende (como test_bus.py): lo que dice depende de la foto."""

    def pedir_sin_nadie(self):
        from nats.errors import NoRespondersError

        class Falsa:
            is_connected = True

            async def request(self, tema, cuerpo, timeout):
                raise NoRespondersError()

        bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=bucle.run_forever, daemon=True)
        hilo.start()
        mod_bus.registrar_conexion(Falsa(), bucle)
        try:
            with mock.patch.object(mod_bus, "REINTENTO_SIN_SERVICIO", 0.01), mock.patch.object(mod_bus, "pedir", self.pedir_real):
                return mod_bus.pedir(self.config, "laptop", "leer", {})
        finally:
            mod_bus.registrar_conexion(None, None)
            bucle.call_soon_threadsafe(bucle.stop)
            hilo.join(2)
            bucle.close()

    def setUp(self):
        self.pedir_real = mod_bus.pedir
        super().setUp()

    def test_en_linea_es_un_telar_viejo(self):
        try:
            import nats  # noqa: F401
        except ImportError:
            self.skipTest("sin nats-py")
        r = self.pedir_sin_nadie()
        self.assertTrue(r["viejo"])
        self.assertIn("laptop está en línea pero su telar no atiende «leer»", r["error"])

    def test_fuera_de_linea_lo_dice_con_su_hora(self):
        try:
            import nats  # noqa: F401
        except ImportError:
            self.skipTest("sin nats-py")
        self.fuera()
        r = self.pedir_sin_nadie()
        self.assertTrue(r["fuera_de_linea"])
        self.assertIn("laptop fuera de línea desde", r["error"])
        self.assertNotIn("no atiende", r["error"])


class LaTerminal(Base):
    """`/pty?maquina=laptop` con el laptop fuera de línea: se cierra diciendo desde cuándo, no que su servicio cayó."""

    def test_fuera_de_linea_lo_dice(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from starlette.websockets import WebSocketDisconnect
        except ImportError:
            self.skipTest("sin el extra serve")
        from telar import api_web as w
        from telar import terminal

        self.fuera()
        with mock.patch.object(w, "_token_del_bus", return_value="token-del-bus"):
            c = TestClient(w.crear(FastAPI(), clave="llave-de-prueba", config=self.config))
        c.cookies.set(w.COOKIE, "llave-de-prueba")
        with mock.patch.object(terminal, "reenviar") as reenviar:
            with c.websocket_connect("/pty?hilo=Catedral&maquina=laptop", headers={"origin": "http://testserver"}) as ws:
                with self.assertRaises(WebSocketDisconnect) as e:
                    ws.receive_text()
        reenviar.assert_not_called()
        self.assertEqual(e.exception.code, terminal.NO_SE_PUDO)
        self.assertIn("laptop fuera de línea desde", e.exception.reason)
        self.assertIn("queda en cola", e.exception.reason)
