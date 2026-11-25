"""Seguir aquí un hilo cuya máquina está apagada, desde la copia de aquí (telar.seguir, la etapa 4 de la mudanza), y la
vuelta: la dueña que vuelve cede sola. Además, los archivados de otra máquina: se ven como de allá y retomarlos va allá.

Sin bus ni tmux: el almacén del bus es uno en memoria con revisiones (comun.KvDeMentira), las conversaciones son
archivos en una carpeta de Claude de mentira ($CLAUDE_CONFIG_DIR) y las fotos de las otras máquinas, archivos en el
estado, como los deja el nodo."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import KvDeMentira, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import dueno, seguir

CLAVE = "ana.faro"


def correr(c):
    return asyncio.run(c)


class ElRegistroAlSeguir(Prueba):
    def test_lo_toma_solo_si_sigue_siendo_de_la_apagada_con_esa_epoca(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 4, "vivo": True, "conversacion": "c1"}})
        self.assertFalse(correr(dueno.seguir(kv, CLAVE, yo="servidor", de_="laptop", epoca_=3, hasta=10)), "época vieja")
        self.assertFalse(correr(dueno.seguir(kv, CLAVE, yo="servidor", de_="otra", epoca_=4, hasta=10)), "otra dueña")
        self.assertTrue(correr(dueno.seguir(kv, CLAVE, yo="servidor", de_="laptop", epoca_=4, hasta=10)))
        v = kv.valor(CLAVE)
        self.assertEqual((v["dueno"], v["maquina"], v["epoca"], v["tomado_de"], v["hasta"], v["mudanza"]["paso"]),
                         ("servidor", "servidor", 5, "laptop", 10, "abrir"))
        self.assertEqual(v["conversacion"], "c1")
        # una segunda vez (otra máquina con la misma época leída): ya no
        self.assertFalse(correr(dueno.seguir(kv, CLAVE, yo="otra", de_="laptop", epoca_=4, hasta=10)))

    def test_en_medio_de_un_traspaso_no(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 4, "cede": "otra"}})
        self.assertFalse(correr(dueno.seguir(kv, CLAVE, yo="servidor", de_="laptop", epoca_=4, hasta=10)))

    def test_el_nodo_lo_lleva_adelante_y_el_traspaso_siguiente_lo_borra(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 1, "conversacion": "c1"}})
        correr(dueno.seguir(kv, CLAVE, yo="servidor", de_="laptop", epoca_=1, hasta=10))
        correr(dueno.abierto(kv, CLAVE, yo="servidor"))
        r = dueno.Registro(kv, "servidor")
        self.assertTrue(correr(r.publicar(CLAVE, {"nombre": "Faro", "vivo": True, "conversacion": "c1"})))
        v = kv.valor(CLAVE)
        self.assertEqual((v["tomado_de"], v["hasta"], "mudanza" in v), ("laptop", 10, False))
        # lo que el nodo sabe del hilo no lo borra, ni lo pisa
        self.assertTrue(correr(r.publicar(CLAVE, {"nombre": "Faro", "vivo": True, "tomado_de": "x"})))
        self.assertEqual(kv.valor(CLAVE)["tomado_de"], "laptop")
        e = correr(dueno.ceder(kv, CLAVE, hilo="Faro", yo="servidor", a="laptop"))
        self.assertTrue(correr(dueno.tomar(kv, CLAVE, yo="laptop", de_="servidor", epoca_=e, valor={})))
        self.assertNotIn("tomado_de", kv.valor(CLAVE))
        self.assertNotIn("hasta", kv.valor(CLAVE))


class ConCarpetas(Prueba):
    """Un estado y una carpeta de Claude de mentira; la máquina de aquí es el servidor, la dueña el laptop."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.estado = base / "estado"
        self.claude = base / "claude"
        (self.estado / "espejos").mkdir(parents=True)
        self.raiz = base / "raiz"
        self.raiz.mkdir()
        self.config = SimpleNamespace(estado=str(self.estado), raiz=str(self.raiz),
                                      bus=SimpleNamespace(url="nats://x", maquina="servidor", persona="ana", token=""))
        self.ctx = SimpleNamespace(config=self.config)
        p = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.claude)})
        p.start()
        self.addCleanup(p.stop)

    def conversacion(self, sid: str, bytes_: int, carpeta: str = "-raiz") -> Path:
        ruta = self.claude / "projects" / carpeta / f"{sid}.jsonl"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(b"x" * bytes_)
        return ruta

    def foto(self, maquina: str, *, hace: float, hilos: list[dict]) -> None:
        (self.estado / "espejos" / f"{maquina}.json").write_text(json.dumps(
            {"recibido": time.time() - hace, "hilos": hilos, "telar": "1"}))
        # el nodo de aquí, al día con el bus: entonces la edad de una foto es la de su máquina
        (self.estado / "espejos" / ".al-dia").touch()


class Revisar(ConCarpetas):
    def revisar(self, registro: dict, *, contesta: bool = False) -> dict:
        with mock.patch.object(dueno, "registro", return_value=registro), \
                mock.patch("telar.bus.pedir", return_value={"ok": contesta}) as pedir:
            r = seguir.revisar(self.ctx, "Faro")
        self.pedido = pedir.call_args
        return r

    REG = {"nombre": "Faro", "dueno": "laptop", "epoca": 3, "conversacion": "c1", "vivo": True}

    def test_con_la_dueña_en_linea_es_traer(self):
        self.conversacion("c1", 100)
        self.foto("laptop", hace=10, hilos=[{"nombre": "Faro", "conv_bytes": 300}])
        r = self.revisar(self.REG)
        self.assertFalse(r["puede"])
        self.assertIn("está en línea", r["por_que_no"])

    def test_apagada_sin_copia_aqui_vuelve_cuando_vuelva(self):
        self.foto("laptop", hace=900, hilos=[{"nombre": "Faro", "conv_bytes": 300}])
        r = self.revisar(self.REG)
        self.assertFalse(r["puede"])
        self.assertIn("aquí no hay copia", r["por_que_no"])
        self.assertIn("vuelve cuando vuelva laptop", r["por_que_no"])

    def test_apagada_con_copia_dice_cuanto_falta(self):
        self.conversacion("c1", 1_000_000)
        self.foto("laptop", hace=900, hilos=[{"nombre": "Faro", "conv_bytes": 3_500_000,
                                              "conv_crecio": "2026-11-24T10:00:00-03:00"}])
        r = self.revisar(self.REG)
        self.assertTrue(r["puede"], r["por_que_no"])
        self.assertEqual((r["dueno"], r["epoca"], r["aqui"]["bytes"], r["alla"]["bytes"]), ("laptop", 3, 1_000_000, 3_500_000))
        self.assertIn("Aquí está como quedó", r["aviso"])
        self.assertIn("pesaba 3,5 MB", r["aviso"])
        self.assertIn("faltan unos 2,5 MB", r["aviso"])
        self.assertIn("cede sola", r["aviso"])
        # se le preguntó a su nodo, por si la foto se atrasó
        self.assertEqual(self.pedido.args[1:3], ("laptop", "mudanza-progreso"))

    def test_sin_el_largo_en_su_foto_lo_dice(self):
        self.conversacion("c1", 1_000)
        self.foto("laptop", hace=900, hilos=[])
        r = self.revisar(self.REG)
        self.assertTrue(r["puede"])
        self.assertIn("no se sabe cuánto pesaba", r["aviso"])

    def test_la_copia_al_dia_no_falta_nada(self):
        self.conversacion("c1", 3_000)
        self.foto("laptop", hace=900, hilos=[{"nombre": "Faro", "conv_bytes": 3_000}])
        self.assertIn("no debería faltar nada", self.revisar(self.REG)["aviso"])

    def test_si_su_nodo_contesta_esta_en_linea(self):
        self.conversacion("c1", 100)
        self.foto("laptop", hace=900, hilos=[])
        r = self.revisar(self.REG, contesta=True)
        self.assertFalse(r["puede"])
        self.assertIn("contesta", r["por_que_no"])

    def test_lo_de_aqui_o_en_traspaso_no(self):
        self.assertIn("ya es de aquí", self.revisar({**self.REG, "dueno": "servidor"})["por_que_no"])
        self.assertIn("traspaso", self.revisar({**self.REG, "cede": "otra"})["por_que_no"])
        self.assertIn("no sabe", self.revisar({})["por_que_no"])
        self.assertIn("no dice cuál es su conversación", self.revisar({**self.REG, "conversacion": ""})["por_que_no"])


class Seguir(ConCarpetas):
    def test_copia_la_conversacion_donde_la_busca_el_agente_lo_toma_y_lo_abre(self):
        origen = self.conversacion("c1", 2_000, carpeta="-otra-carpeta")
        (origen.parent / "c1" / "tool-results").mkdir(parents=True)
        (origen.parent / "c1" / "tool-results" / "a.txt").write_text("hola")
        self.foto("laptop", hace=900, hilos=[{"nombre": "Faro", "conv_bytes": 5_000}])
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 3, "conversacion": "c1", "vivo": True}})
        abiertos = []
        with mock.patch.object(dueno, "registro", side_effect=lambda c, h: kv.valor(CLAVE)), \
                mock.patch.object(dueno, "con_almacen", side_effect=lambda c, hacer: correr(hacer(kv))), \
                mock.patch.object(dueno, "clave", return_value=CLAVE), \
                mock.patch("telar.bus.pedir", return_value={"ok": False}), \
                mock.patch("telar.mudanza.inicio", return_value=(self.raiz, None, "")), \
                mock.patch("telar.mudanza.abrir_tomado", side_effect=lambda ctx, h, r: abiertos.append((h, r)) or (True, "lo abrí")):
            r = seguir.seguir(self.ctx, "Faro")
        self.assertTrue(r["ok"], r)
        from telar import rutas

        destino = self.claude / "projects" / rutas.aplanar(self.raiz.resolve()) / "c1.jsonl"
        self.assertTrue(destino.is_file())
        self.assertTrue(origen.is_file(), "la de origen no se mueve")
        self.assertEqual((destino.parent / "c1" / "tool-results" / "a.txt").read_text(), "hola")
        v = kv.valor(CLAVE)
        self.assertEqual((v["dueno"], v["epoca"], v["tomado_de"], v["hasta"]), ("servidor", 4, "laptop", 2_000))
        self.assertEqual([h for h, _ in abiertos], ["Faro"])
        self.assertIn("cede sola", r["hecho"])

    def test_si_el_registro_cambio_no_abre_nada(self):
        self.conversacion("c1", 2_000, carpeta="-raiz")
        self.foto("laptop", hace=900, hilos=[])
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 3, "conversacion": "c1"}})
        lecturas = iter([kv.valor(CLAVE), kv.valor(CLAVE)])

        def registro(c, h):
            # entre la revisión y la escritura, el laptop volvió y publicó (su época subió)
            try:
                return next(lecturas)
            except StopIteration:
                return kv.valor(CLAVE)

        kv.actual[CLAVE] = (kv.actual[CLAVE][0] + 1, {**kv.valor(CLAVE), "epoca": 4})
        with mock.patch.object(dueno, "registro", side_effect=registro), \
                mock.patch.object(dueno, "con_almacen", side_effect=lambda c, hacer: correr(hacer(kv))), \
                mock.patch.object(dueno, "clave", return_value=CLAVE), \
                mock.patch("telar.bus.pedir", return_value={"ok": False}), \
                mock.patch("telar.mudanza.inicio", return_value=(self.raiz, None, "")), \
                mock.patch("telar.mudanza.abrir_tomado") as abrir:
            r = seguir.seguir(self.ctx, "Faro")
        self.assertFalse(r["ok"])
        self.assertIn("no lo tomé", r["error"])
        abrir.assert_not_called()
        self.assertEqual(kv.valor(CLAVE)["dueno"], "laptop")


class LaQueVuelve(ConCarpetas):
    def setUp(self):
        super().setUp()
        self.config.bus.maquina = "laptop"
        from telar import estado as mod_estado

        self.est = mod_estado.Estado(self.estado)
        self.mux = mock.Mock()
        self.mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@4")]
        self.tel = SimpleNamespace(mux=self.mux, estado=self.est)

    def ceder(self, reg: dict) -> str:
        with mock.patch("telar.ordenes._comun.tejer", return_value=self.tel), mock.patch.object(seguir, "CALMA", 0.0):
            return seguir.ceder_aqui(self.ctx, "Faro", "c1", reg)

    def test_cierra_su_agente_aparta_lo_de_despues_y_avisa(self):
        ruta = self.conversacion("c1", 5_000)
        texto = self.ceder({"dueno": "servidor", "epoca": 4, "tomado_de": "laptop", "hasta": 2_000, "seguido": time.time()})
        self.mux.cerrar.assert_called_once_with("@4")
        self.assertFalse(ruta.exists())
        apartes = list(ruta.parent.glob("c1.de-laptop-*.jsonl.bak"))
        self.assertEqual(len(apartes), 1)
        self.assertEqual(apartes[0].stat().st_size, 5_000)
        self.assertIn("siguió en servidor", texto)
        aviso = json.loads(seguir.aviso_archivo(self.config).read_text())
        self.assertEqual(aviso["nivel"], "aviso")
        self.assertIn("«Faro» siguió en servidor", aviso["linea"])
        self.assertIn("quedó aparte", aviso["linea"])
        self.assertTrue(Path(aviso["informe"]).read_text().count("Faro"))
        # la franja lo dice sin que se declare (telar.avisos)
        from telar import avisos

        with mock.patch("telar.bus.hay_bus", return_value=False):
            dichos = avisos.de_todas(SimpleNamespace(**vars(self.config), avisos=()))["avisos"]
        self.assertEqual([a["clave"] for a in dichos], ["seguidos"])

    def test_sin_nada_despues_de_la_copia_no_aparta(self):
        ruta = self.conversacion("c1", 2_000)
        self.ceder({"dueno": "servidor", "epoca": 4, "tomado_de": "laptop", "hasta": 2_000})
        self.assertTrue(ruta.exists())
        self.assertNotIn("quedó aparte", json.loads(seguir.aviso_archivo(self.config).read_text())["linea"])

    def test_si_no_lo_siguieron_desde_aqui_no_aparta(self):
        ruta = self.conversacion("c1", 5_000)
        self.ceder({"dueno": "servidor", "epoca": 4})
        self.assertTrue(ruta.exists())
        self.mux.cerrar.assert_called_once_with("@4")

    def test_la_ventana_que_mira_alla_no_se_cierra(self):
        self.conversacion("c1", 5_000)
        self.est.anotar_remoto("Faro", "servidor", "")
        self.ceder({"dueno": "servidor", "epoca": 4, "tomado_de": "laptop", "hasta": 2_000})
        self.mux.cerrar.assert_not_called()

    def test_el_aviso_se_va_cuando_pasa_la_semana(self):
        self.conversacion("c1", 2_000)
        self.ceder({"dueno": "servidor", "epoca": 4, "tomado_de": "laptop", "hasta": 2_000})
        with mock.patch("telar.seguir.time.time", return_value=time.time() + seguir.AVISO_DURA + 10):
            seguir.refrescar_aviso(self.config)
        self.assertEqual(json.loads(seguir.aviso_archivo(self.config).read_text())["nivel"], "ok")


class ElNodoCedeAlVolver(Prueba):
    def nodo(self, vistos: dict, dormidos: dict | None = None):
        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        n.config = SimpleNamespace(estado=tmp.name, bus=SimpleNamespace(url="nats://x", maquina="laptop", persona="ana"))
        n.ctx, n.yo, n.persona, n.vistos = SimpleNamespace(config=n.config), "laptop", "ana", vistos
        n.lineas = []
        n.anotar = n.lineas.append
        from telar import estado as mod_estado

        for h, d in (dormidos or {}).items():
            mod_estado.Estado(tmp.name).anotar_dormido(h, d)
        return n

    def ceder(self, n, locales):
        with mock.patch.object(seguir, "ceder_aqui", side_effect=lambda ctx, h, sid, reg: f"cedí {h} {sid}") as c, \
                mock.patch("telar.bus.ficha", side_effect=lambda nombre, config=None: nombre.lower()):
            hechos = correr(n.ceder_seguidos(locales))
        return hechos, c

    def test_cede_el_suyo_que_es_de_otra_con_su_conversacion(self):
        n = self.nodo({CLAVE: {"nombre": "Faro", "dueno": "servidor", "epoca": 4, "conversacion": "c1"}})
        hechos, _ = self.ceder(n, {"Faro": {"vivo": True, "conversacion": "c1"}})
        self.assertEqual(hechos, ["cedí Faro c1"])
        # una vez por época
        hechos, _ = self.ceder(n, {"Faro": {"vivo": True, "conversacion": "c1"}})
        self.assertEqual(hechos, [])

    def test_no_toca_a_otro_que_se_llama_igual_ni_lo_suyo_ni_lo_que_viaja(self):
        casos = [
            ({"dueno": "servidor", "epoca": 4, "conversacion": "c-otra"}, {}),  # otro hilo con su nombre
            ({"dueno": "laptop", "epoca": 4, "conversacion": "c1"}, {}),  # de aquí
            ({"dueno": "servidor", "epoca": 4, "conversacion": "c1", "cede": "laptop"}, {}),  # viene hacia aquí
            ({"dueno": "servidor", "epoca": 4, "conversacion": "c1"}, {"Faro": {"cede": "servidor"}}),  # se iba
        ]
        for reg, dormidos in casos:
            n = self.nodo({CLAVE: {"nombre": "Faro", **reg}}, dormidos)
            hechos, c = self.ceder(n, {"Faro": {"vivo": True, "conversacion": "c1"}})
            self.assertEqual(hechos, [], reg)
        n = self.nodo({CLAVE: {"nombre": "Faro", "dueno": "servidor", "epoca": 4, "conversacion": "c1"}})
        self.assertEqual(self.ceder(n, {"Faro": {"vivo": False, "conversacion": "c1"}})[0], [], "cerrado aquí: nada")


class LaFotoLlevaElLargo(ConCarpetas):
    def test_el_largo_y_cuando_crecio_sin_el_contenido(self):
        from telar import espejo

        self.conversacion("c1", 1234)
        d = espejo._conversacion(["c1", "c0"])
        self.assertEqual(d["conv_bytes"], 1234)
        self.assertTrue(d["conv_crecio"].startswith("20"))
        self.assertEqual(espejo._conversacion([]), {})
        self.assertEqual(espejo._conversacion(["no-esta"]), {})
        limpia = espejo.validar({"version": espejo.VERSION, "hilos": [
            {"nombre": "A", "conv_bytes": 10, "conv_crecio": "2026-11-24T10:00:00-03:00"},
            {"nombre": "B", "conv_bytes": -1}, {"nombre": "C", "conv_bytes": "mucho"}, {"nombre": "D", "conv_bytes": True}]},
            "laptop")
        self.assertEqual([h.get("conv_bytes") for h in limpia["hilos"]], [10, None, None, None])


class LosArchivadosDeOtra(ConCarpetas):
    def test_se_ven_como_de_alla_y_los_cerrados_de_alla_no_se_listan(self):
        from telar import estado as mod_estado
        from telar.ordenes import _comun

        est = mod_estado.Estado(self.estado)
        est.archivar("Viejo")
        est.archivar("Mio")
        est.anotar_sesion("Mio", "c-mio")
        est.anotar_sesion("Cerrado", "c-cerrado")
        est.guardar_ajenos({"Viejo": {"maquina": "laptop", "dueno": "laptop", "conversacion": "c-viejo"},
                            "Mio": {"maquina": "laptop", "dueno": "laptop", "conversacion": "c-otra"},
                            "Cerrado": {"maquina": "laptop", "dueno": "laptop", "conversacion": "c-cerrado"}})
        self.config.intervalos = SimpleNamespace(foco_maximo=600)
        self.config.sesion = "prueba"
        ctx = SimpleNamespace(config=self.config, perfil=None)
        with mock.patch.object(_comun, "_mux", return_value=(None, "")), \
                mock.patch("telar.agentes.descubrir", return_value=[]):
            tel = _comun.tejer(ctx, con_ficha=False)
        nombres = {h.nombre for h in tel.hilos}
        self.assertEqual(nombres, {"Viejo", "Mio"}, "el cerrado de allá se ve en su foto, no aquí")
        self.assertEqual(tel.de_otra, {"Viejo": "laptop"}, "«Mio» tiene aquí otra conversación: es de aquí")
        self.assertEqual(_comun.json_hilo(tel.por_nombre("Viejo"), tel, con_ficha=False)["dueno"], "laptop")
        self.assertEqual(_comun.json_hilo(tel.por_nombre("Mio"), tel, con_ficha=False)["dueno"], "")


class RetomarUnoDeOtra(ConCarpetas):
    def retomar(self, *, fuera: bool, copia: bool = False, respuesta: dict | None = None):
        from telar import alcance
        from telar import estado as mod_estado
        from telar.ordenes import hilo as orden

        est = mod_estado.Estado(self.estado)
        est.archivar("Viejo")
        a = alcance.Alcance(maquina="laptop", conocida=True, en_linea=not fuera, recibido=time.time() - 900)
        with mock.patch("telar.alcance.de", return_value=a), \
                mock.patch.object(seguir, "revisar", return_value={"aqui": {"bytes": 1} if copia else None}), \
                mock.patch("telar.bus.pedir", return_value=respuesta or {"ok": True, "codigo": 0}) as pedir:
            codigo = orden._retomar_alla(self.ctx, est, SimpleNamespace(nombre="Viejo"), "laptop", "")
        return codigo, pedir, est

    def test_con_su_maquina_en_linea_se_retoma_alla(self):
        codigo, pedir, est = self.retomar(fuera=False)
        self.assertEqual(codigo, 0)
        self.assertEqual(pedir.call_args.args[1:3], ("laptop", "hilo"))
        self.assertEqual(pedir.call_args.args[3]["argv"], ["retomar", "--hilo", "Viejo"])
        self.assertNotIn("Viejo", est.archivados(), "aquí sale del archivo: es de allá")

    def test_con_su_maquina_apagada_no_abre_la_copia_de_aqui(self):
        for copia, dice in ((True, "telar hilo seguir"), (False, "vuelve cuando vuelva laptop")):
            with mock.patch("sys.stderr") as err:
                codigo, pedir, est = self.retomar(fuera=True, copia=copia)
            self.assertNotEqual(codigo, 0)
            pedir.assert_not_called()
            self.assertIn(dice, "".join(str(c.args[0]) for c in err.write.call_args_list))
            self.assertIn("Viejo", est.archivados())

    def test_lo_que_dice_su_maquina_si_falla(self):
        with mock.patch("sys.stderr"):
            codigo, _, est = self.retomar(fuera=False, respuesta={"ok": True, "codigo": 1, "error_salida": "telar: no"})
        self.assertNotEqual(codigo, 0)
        self.assertIn("Viejo", est.archivados())
