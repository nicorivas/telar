"""Un dueño por hilo, con época (telar.dueno): lo que publica el nodo, condicionado a la revisión que vio, y el
traspaso (ceder, tomar, echarse atrás), que nunca deja dos dueños aunque las dos máquinas escriban a la vez.

El almacén del bus es uno en memoria con revisiones (comun.KvDeMentira): `update` falla si otro escribió entre medio,
como en NATS."""

from __future__ import annotations

import asyncio
from unittest import mock

from comun import KvDeMentira, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import dueno

CLAVE = "ana.faro"


def correr(c):
    return asyncio.run(c)


class QuienPuedePublicar(Prueba):
    def test_lo_suyo_si_lo_de_otra_no(self):
        self.assertEqual(dueno.puede_publicar(None, "laptop", {"vivo": True}), (True, 0))
        self.assertEqual(dueno.puede_publicar({"dueno": "laptop", "epoca": 3}, "laptop", {}), (True, 3))
        # un registro de antes, sin dueño: su máquina
        self.assertEqual(dueno.puede_publicar({"maquina": "laptop"}, "laptop", {}), (True, 0))
        self.assertEqual(dueno.puede_publicar({"dueno": "servidor", "epoca": 2, "vivo": True}, "laptop", {"vivo": True}),
                         (False, 2))

    def test_otro_que_se_llama_igual_toma_el_de_alla_si_alla_esta_muerto(self):
        muerto = {"dueno": "servidor", "epoca": 2, "vivo": False, "conversacion": "s-1"}
        self.assertEqual(dueno.puede_publicar(muerto, "laptop", {"vivo": True, "conversacion": "s-9"}), (True, 3))
        # el mismo hilo (su conversación), abierto aquí con su copia vieja: no, vive allá
        self.assertEqual(dueno.puede_publicar(muerto, "laptop", {"vivo": True, "conversacion": "s-1"}), (False, 2))
        # muerto aquí también: no hay nada que publicar como suyo
        self.assertEqual(dueno.puede_publicar(muerto, "laptop", {"vivo": False, "conversacion": "s-9"}), (False, 2))
        # en medio de un traspaso, nunca
        self.assertFalse(dueno.puede_publicar({**muerto, "mudanza": {"paso": "abrir"}}, "laptop",
                                              {"vivo": True, "conversacion": "s-9"})[0])


class LoQuePublicaElNodo(Prueba):
    def test_publica_lo_suyo_con_dueno_y_epoca(self):
        kv = KvDeMentira()
        r = dueno.Registro(kv, "laptop")
        self.assertTrue(correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": True})))
        self.assertEqual(kv.valor(CLAVE)["dueno"], "laptop")
        self.assertEqual(kv.valor(CLAVE)["epoca"], 0)
        self.assertTrue(correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": False})))
        self.assertEqual(len(kv.puestos), 2, "con la revisión que recordaba: sin leer de nuevo")

    def test_no_publica_lo_de_otra_y_lo_dice_una_vez(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "servidor", "epoca": 4, "vivo": True}})
        lineas = []
        r = dueno.Registro(kv, "laptop", anotar=lineas.append)
        for _ in range(2):
            self.assertFalse(correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": False})))
        self.assertEqual(kv.puestos, [])
        self.assertEqual(len(lineas), 1)
        self.assertIn("vive en servidor", lineas[0])

    def test_lleva_adelante_lo_del_traspaso_que_escribio_otro(self):
        kv = KvDeMentira()
        r = dueno.Registro(kv, "laptop")
        correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": True}))
        # la mudanza cede el hilo (otro proceso, sin pasar por el nodo)
        correr(dueno.ceder(kv, CLAVE, hilo="Faro", yo="laptop", a="servidor", pid=1))
        # el nodo publica lo que cambió: su revisión era vieja, lee de nuevo y no borra la cesión
        self.assertTrue(correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": True, "dormido": True})))
        v = kv.valor(CLAVE)
        self.assertEqual((v["cede"], v["mudanza"]["a"], v["dormido"]), ("servidor", "servidor", True))

    def test_despues_de_que_la_otra_lo_toma_ya_no_lo_publica(self):
        kv = KvDeMentira()
        r = dueno.Registro(kv, "laptop")
        correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": True}))
        e = correr(dueno.ceder(kv, CLAVE, hilo="Faro", yo="laptop", a="servidor", pid=1))
        self.assertTrue(correr(dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e, valor={"nombre": "Faro"})))
        # el nodo de aquí vería el hilo muerto (su ventana se cerró) y lo publicaría: no, ya es de allá
        self.assertFalse(correr(r.publicar(CLAVE, {"nombre": "Faro", "maquina": "laptop", "vivo": False})))
        self.assertEqual(kv.valor(CLAVE)["dueno"], "servidor")

    def test_sin_condicion_como_antes(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "servidor", "vivo": True}})
        r = dueno.Registro(kv, "laptop", simple=True)
        self.assertFalse(correr(r.publicar(CLAVE, {"nombre": "Faro", "vivo": True})), "igual respeta al dueño")
        kv2 = KvDeMentira()
        with mock.patch.object(kv2, "update", side_effect=AssertionError("simple no condiciona")):
            r2 = dueno.Registro(kv2, "laptop", simple=True)
            correr(r2.publicar(CLAVE, {"nombre": "Faro", "vivo": True}))
            correr(r2.publicar(CLAVE, {"nombre": "Faro", "vivo": False}))
        self.assertEqual(len(kv2.puestos), 2)


class ElTraspaso(Prueba):
    def ceder(self, kv):
        return correr(dueno.ceder(kv, CLAVE, hilo="Faro", yo="laptop", a="servidor", pid=4321))

    def test_ceder_tomar_y_abrir(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "maquina": "laptop", "vivo": True, "epoca": 2}})
        e = self.ceder(kv)
        self.assertEqual(e, 2)
        v = kv.valor(CLAVE)
        self.assertEqual((v["dueno"], v["cede"], v["mudanza"]["paso"], v["mudanza"]["pid"]), ("laptop", "servidor", "ceder", 4321))
        correr(dueno.paso(kv, CLAVE, yo="laptop", paso_="copiar"))
        self.assertEqual(kv.valor(CLAVE)["mudanza"]["paso"], "copiar")
        self.assertTrue(correr(dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e,
                                           valor={"nombre": "Faro", "vivo": False, "conversacion": "s-1"})))
        v = kv.valor(CLAVE)
        self.assertEqual((v["dueno"], v["maquina"], v["epoca"], v["mudanza"]["paso"]), ("servidor", "servidor", 3, "abrir"))
        self.assertNotIn("cede", v)
        correr(dueno.abierto(kv, CLAVE, yo="servidor"))
        self.assertNotIn("mudanza", kv.valor(CLAVE))

    def test_si_se_echa_atras_ya_no_se_puede_tomar(self):
        kv = KvDeMentira()
        e = self.ceder(kv)
        self.assertTrue(correr(dueno.abortar(kv, CLAVE, yo="laptop", epoca_=e)))
        v = kv.valor(CLAVE)
        self.assertEqual((v["dueno"], v["epoca"]), ("laptop", e + 1))
        self.assertNotIn("cede", v)
        self.assertFalse(correr(dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e, valor={})))
        self.assertEqual(kv.valor(CLAVE)["dueno"], "laptop")
        self.assertTrue(correr(dueno.abortar(kv, CLAVE, yo="laptop", epoca_=e)), "echarse atrás dos veces: sigue suyo")

    def test_si_ya_lo_tomaron_no_se_puede_echar_atras(self):
        kv = KvDeMentira()
        e = self.ceder(kv)
        correr(dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e, valor={}))
        self.assertFalse(correr(dueno.abortar(kv, CLAVE, yo="laptop", epoca_=e)))
        self.assertEqual(kv.valor(CLAVE)["dueno"], "servidor")

    def test_tomar_solo_lo_cedido_a_esta(self):
        kv = KvDeMentira()
        e = self.ceder(kv)
        self.assertFalse(correr(dueno.tomar(kv, CLAVE, yo="escritorio", de_="laptop", epoca_=e, valor={})))
        self.assertFalse(correr(dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e + 7, valor={})))
        self.assertFalse(correr(dueno.tomar(KvDeMentira(), CLAVE, yo="servidor", de_="laptop", epoca_=0, valor={})))

    def test_no_se_cede_lo_ajeno_ni_lo_que_ya_se_va(self):
        kv = KvDeMentira({CLAVE: {"nombre": "Faro", "dueno": "servidor", "vivo": True}})
        with self.assertRaisesRegex(dueno.ErrorDeDueno, "vive en servidor"):
            self.ceder(kv)
        kv = KvDeMentira()
        self.ceder(kv)
        with self.assertRaisesRegex(dueno.ErrorDeDueno, "ya se está yendo a servidor"):
            correr(dueno.ceder(kv, CLAVE, hilo="Faro", yo="laptop", a="escritorio"))

    def test_a_la_vez_nunca_dos_duenos(self):
        # tomar y echarse atrás en la misma vuelta, cada uno con lo que leyó: gana el primero que escribe, el otro lee
        # de nuevo y decide con lo nuevo
        for primero in ("tomar", "abortar"):
            with self.subTest(primero=primero):
                kv = KvDeMentira()
                e = self.ceder(kv)
                lecturas = []
                original = kv.get

                async def get_lento(k):
                    lecturas.append(k)
                    r = await original(k)
                    await asyncio.sleep(0)  # el otro lee lo mismo antes de que este escriba
                    return r

                kv.get = get_lento

                async def los_dos():
                    t = dueno.tomar(kv, CLAVE, yo="servidor", de_="laptop", epoca_=e, valor={})
                    a = dueno.abortar(kv, CLAVE, yo="laptop", epoca_=e)
                    return await asyncio.gather(*((t, a) if primero == "tomar" else (a, t)))

                r = correr(los_dos())
                tomo, sigue = (r[0], r[1]) if primero == "tomar" else (r[1], r[0])
                self.assertNotEqual(tomo, sigue, "uno y solo uno")
                self.assertEqual(dueno.de(kv.valor(CLAVE)), "servidor" if tomo else "laptop")


class LasMudanzasAMedias(Prueba):
    """Lo que el nodo hace con un traspaso que quedó a medias (`Nodo.mudanzas_colgadas`), con lo que dice el registro."""

    def setUp(self):
        super().setUp()
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from telar import estado as mod_estado

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = SimpleNamespace(estado=str(Path(self._tmp.name) / "estado"),
                                      bus=SimpleNamespace(url="nats://x", maquina="laptop", persona="ana", token=""))
        self.est = mod_estado.Estado(self.config.estado)
        self.hechos = []

    def nodo(self):
        from types import SimpleNamespace

        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.config, n.ctx, n.yo, n.persona = self.config, SimpleNamespace(config=self.config), "laptop", "ana"
        n.lineas = []
        n.anotar = n.lineas.append
        n.propios = {}
        return n

    def correr(self, n, kv):
        from telar import mudanza
        from telar.ordenes import _comun

        with mock.patch.object(mudanza, "reanudar", side_effect=lambda c, h: self.hechos.append(("reanudar", h)) or "despertó"), \
                mock.patch.object(mudanza, "soltar", side_effect=lambda c, t, h: self.hechos.append(("soltar", h))), \
                mock.patch.object(mudanza, "abrir_tomado", side_effect=lambda ctx, h, r: self.hechos.append(("abrir", h)) or (True, "lo abrí")), \
                mock.patch.object(_comun, "tejer", return_value=object()), \
                mock.patch("telar.bus.ficha", side_effect=lambda nombre, config=None: nombre.lower()):
            return correr(n.mudanzas_colgadas(kv))

    def test_uno_que_cedia_y_nadie_conduce_vuelve(self):
        # el proceso de la mudanza se cayó (la tapa del laptop, un kill): se echa atrás y su agente despierta
        self.est.anotar_dormido("Faro", {"cede": "servidor", "panel": "%1"})
        kv = KvDeMentira({"ana.faro": {"nombre": "Faro", "dueno": "laptop", "epoca": 2, "cede": "servidor",
                                       "mudanza": {"pid": 999999, "hora": 0, "a": "servidor"}}})
        self.correr(self.nodo(), kv)
        self.assertEqual(self.hechos, [("reanudar", "Faro")])
        self.assertEqual((kv.valor("ana.faro")["epoca"], "cede" in kv.valor("ana.faro")), (3, False))

    def test_si_la_otra_ya_lo_tomo_su_ventana_de_aqui_se_cierra(self):
        self.est.anotar_dormido("Faro", {"cede": "servidor", "panel": "%1"})
        kv = KvDeMentira({"ana.faro": {"nombre": "Faro", "dueno": "servidor", "epoca": 3}})
        self.correr(self.nodo(), kv)
        self.assertEqual(self.hechos, [("soltar", "Faro")])

    def test_mientras_la_mudanza_corre_no_se_toca(self):
        import os
        import time

        self.est.anotar_dormido("Faro", {"cede": "servidor", "panel": "%1"})
        kv = KvDeMentira({"ana.faro": {"nombre": "Faro", "dueno": "laptop", "epoca": 2, "cede": "servidor",
                                       "mudanza": {"pid": os.getpid(), "hora": time.time(), "a": "servidor"}}})
        self.correr(self.nodo(), kv)
        self.assertEqual(self.hechos, [])
        self.assertEqual(kv.valor("ana.faro")["cede"], "servidor")

    def test_uno_que_tomo_y_no_alcanzo_a_abrir_se_abre(self):
        n = self.nodo()
        n.propios = {"ana.faro": {"nombre": "Faro", "dueno": "laptop", "conversacion": "s-1",
                                  "mudanza": {"paso": "abrir", "a": "laptop", "pid": 999999, "hora": 0}}}
        self.correr(n, KvDeMentira())
        self.assertEqual(self.hechos, [("abrir", "Faro")])
        # el que lo está abriendo (este proceso, hace poco) se deja
        import os
        import time

        self.hechos.clear()
        n.propios["ana.faro"]["mudanza"].update(pid=os.getpid(), hora=time.time())
        self.correr(n, KvDeMentira())
        self.assertEqual(self.hechos, [])


class LaListaDeAqui(Prueba):
    def test_uno_que_vive_en_otra_no_es_un_cerrado_de_aqui(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from telar import estado as mod_estado
        from telar.ordenes import _comun

        with tempfile.TemporaryDirectory() as d:
            config = SimpleNamespace(bus=SimpleNamespace(url="nats://x", maquina="laptop", persona="ana"))
            est = mod_estado.Estado(Path(d))
            est.guardar_ajenos({"Faro": {"maquina": "servidor", "dueno": "servidor", "conversacion": "c-faro"},
                                "Mio": {"maquina": "laptop", "dueno": "laptop"},
                                "Igual": {"maquina": "servidor", "dueno": "servidor", "conversacion": "c-igual"},
                                "Otro": {"maquina": "servidor", "dueno": "servidor", "conversacion": "c-de-alla"},
                                "Basura": {"maquina": "servidor", "dueno": "servidor", "conversacion": ""}})
            sesiones = {"Igual": ["c-igual"], "Otro": ["c-de-aqui"], "Basura": ["c-basura"]}
            # sin conversación aquí, o la misma: de allá. Otra conversación aquí: otro hilo con su nombre, de aquí. Un
            # registro sin conversación no le quita a esta la que tiene
            self.assertEqual(_comun._de_otra(config, est, sesiones), {"Faro": "servidor", "Igual": "servidor"})
            self.assertEqual(_comun._de_otra(SimpleNamespace(bus=SimpleNamespace(url="")), est), {}, "sin bus, nada")


class SoltarLaVentanaQueEsperaba(Prueba):
    def test_cierra_la_que_esperaba_y_no_la_que_mira_alla(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from telar import estado as mod_estado
        from telar import mudanza

        with tempfile.TemporaryDirectory() as d:
            config = SimpleNamespace(estado=str(Path(d)))
            est = mod_estado.Estado(Path(d))
            est.anotar_dormido("Faro", {"cede": "servidor", "ventana": "@5"})
            mux = mock.Mock()
            # el nodo ya trajo la ventana que lo mira en el servidor, con el mismo nombre
            mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@3"), SimpleNamespace(nombre="Faro", id="@5")]
            mudanza.soltar(config, SimpleNamespace(mux=mux), "Faro")
            mux.cerrar.assert_called_once_with("@5")
            self.assertNotIn("Faro", est.dormidos())
