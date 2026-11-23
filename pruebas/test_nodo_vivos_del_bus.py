"""nodo: lo que el bus da por vivo en esta máquina y aquí ya no está se publica muerto, aunque haya muerto con el
nodo apagado; y la ventana de un hilo de otra máquina que allá no contesta no se reabre sin fin.

Lo que pasó (15-nov-2026): el servidor se reinició a la fuerza y tres hilos murieron con él. En el bus siguieron
vivos, porque el nodo solo publicaba muerto lo que había publicado vivo en la misma corrida, y el laptop les
reabría la ventana cada vuelta. Nada de esto toca el bus ni tmux: el nodo se arma sin conectarse, el bus es un
falso y lo de tmux, un SimpleNamespace.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar.ordenes import nodo as mod_nodo

CONFIG = SimpleNamespace(bus=SimpleNamespace(persona="ana", maquina="servidor"), remotos=[])
SOLAS = "◌ un rato 11/15 10:00"


def clave(nombre: str) -> str:
    return mod_bus.clave_estado(CONFIG, nombre)


def entrada(nombre: str, maquina: str = "servidor", **mas) -> dict:
    """Un estado como lo deja `_vuelta` en el bus, con su `actualizado`."""
    return {"nombre": nombre, "maquina": maquina, "vivo": True, "residente": "", "atencion": "espera",
            "desde": "2026-11-15T19:20:00-03:00", "conversacion": "s-1", "vinculo": "", "archivado": False,
            "publico": False, "etiquetas": [], "padre": "", "ventana": "@397/73706700",
            "actualizado": "2026-11-15T19:24:00-03:00", **mas}


class Vigia:
    """El `kv.watch` de nats-py: lo que había, la marca (None) y, si se sigue, nada más."""

    def __init__(self, lista):
        self.lista = list(lista)
        self.parado = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.lista:
            raise StopAsyncIteration
        return self.lista.pop(0)

    async def stop(self):
        self.parado = True


class Kv:
    def __init__(self, entradas: dict[str, dict] | None = None, falla: Exception | None = None):
        self.entradas, self.falla, self.puestos, self.vigias = dict(entradas or {}), falla, [], []

    async def watch(self, claves, **opciones):
        if self.falla:
            raise self.falla
        v = Vigia([*(SimpleNamespace(key=k, value=json.dumps(d, ensure_ascii=False).encode())
                     for k, d in self.entradas.items()), None])
        self.vigias.append(v)
        return v

    async def put(self, k, v):
        self.puestos.append((k, json.loads(v)))


class Js:
    async def pull_subscribe(self, *a, **k):
        return object()


async def _nada(*a, **k):
    return None


def nodo(aqui: dict[str, dict] | None = None) -> mod_nodo.Nodo:
    """Un nodo del servidor sin bus ni tmux: `aqui` es lo que devuelve `locales()`."""
    n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
    n.config, n.persona, n.yo = CONFIG, "ana", "servidor"
    n.publicado, n.ausentes, n.vistos, n.subs = {}, {}, {}, {}
    n.sembrado, n.sembrados, n.reabiertas = False, set(), {}
    n.registro = ({}, set(), {}, set(), {}, {})
    n.vueltas = 1  # ni la rotación (cada 3) ni lo de cada 30 s (cada 15) en las primeras vueltas
    n.lineas = []
    n.anotar = n.lineas.append
    n.locales = lambda: {k: dict(v) for k, v in (aqui or {}).items()}
    # lo que la vuelta hace además de publicar el estado, apagado
    n.releer_config, n._despacho, n._recoger = (lambda: False), (lambda: None), _nada
    n.rotar_relevos, n.avisar_padres, n.foto, n.conciliar = (lambda: None), (lambda locales: []), (lambda: None), (lambda: [])
    return n


def vueltas(n, kv, cuantas: int) -> list[list]:
    """Lo que se puso en el bus en cada vuelta."""
    salida = []
    for _ in range(cuantas):
        antes = len(kv.puestos)
        asyncio.run(n._vuelta(Js(), kv))
        salida.append(kv.puestos[antes:])
    return salida


def sin_actualizado(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "actualizado"}


class AlArrancarSeSiembraLoDelBus(Prueba):
    def test_un_hilo_propio_vivo_en_el_bus_que_aqui_no_esta_se_publica_muerto_a_la_segunda(self):
        kv = Kv({clave(SOLAS): entrada(SOLAS)})
        n = nodo()
        self.assertTrue(asyncio.run(n.sembrar(kv)))
        self.assertTrue(kv.vigias[0].parado)  # el vigía del arranque no queda escuchando
        primera, segunda, tercera = vueltas(n, kv, 3)
        self.assertEqual(primera, [])  # una lectura de tmux que falla una vez no lo mata
        ((k, d),) = segunda
        self.assertEqual(k, clave(SOLAS))
        self.assertEqual((d["vivo"], d["atencion"], d["ventana"], d["maquina"]), (False, "ninguna", "", "servidor"))
        self.assertNotEqual(d["actualizado"], "2026-11-15T19:24:00-03:00")
        self.assertEqual(d["conversacion"], "s-1")  # lo demás, como estaba
        self.assertEqual(tercera, [])  # y una vez
        self.assertEqual(len([x for x in n.lineas if "lo publico muerto" in x]), 1)

    def test_una_entrada_de_otra_maquina_no_se_toca(self):
        # se mudó al laptop: lo publica aquel, aunque aquí no esté
        kv = Kv({clave(SOLAS): entrada(SOLAS, maquina="laptop")})
        n = nodo()
        asyncio.run(n.sembrar(kv))
        self.assertEqual(n.publicado, {})
        self.assertEqual(vueltas(n, kv, 3), [[], [], []])

    def test_una_entrada_ya_muerta_o_sin_nombre_no_se_siembra(self):
        kv = Kv({clave(SOLAS): entrada(SOLAS, vivo=False), "ana.raro": {"maquina": "servidor", "vivo": True},
                 "ana.roto": "no es un estado"})
        n = nodo()
        self.assertTrue(asyncio.run(n.sembrar(kv)))
        self.assertEqual(n.publicado, {})

    def test_un_hilo_vivo_aqui_no_se_publica_muerto(self):
        kv = Kv({clave(SOLAS): entrada(SOLAS)})
        n = nodo({SOLAS: sin_actualizado(entrada(SOLAS))})
        asyncio.run(n.sembrar(kv))
        # igual a lo que ya dice el bus: no hace falta volver a ponerlo
        self.assertEqual(vueltas(n, kv, 3), [[], [], []])
        self.assertEqual(n.lineas, [])

    def test_un_hilo_vivo_aqui_con_otra_ventana_se_publica_vivo(self):
        kv = Kv({clave(SOLAS): entrada(SOLAS)})
        n = nodo({SOLAS: sin_actualizado(entrada(SOLAS, ventana="@12/abcdef01"))})
        asyncio.run(n.sembrar(kv))
        ((_, d),), segunda = vueltas(n, kv, 2)
        self.assertTrue(d["vivo"])
        self.assertEqual(d["ventana"], "@12/abcdef01")
        self.assertEqual(segunda, [])

    def test_un_residente_sin_sesion_que_el_bus_daba_vivo_se_publica_sin_esperar(self):
        # `locales()` siempre trae a los residentes de aquí: vivo o no, no faltan, y se publica lo que son
        kv = Kv({clave("Huerto"): entrada("Huerto", residente="huerto")})
        n = nodo({"Huerto": sin_actualizado(entrada("Huerto", residente="huerto", vivo=False, atencion="ninguna",
                                                     ventana=""))})
        asyncio.run(n.sembrar(kv))
        ((_, d),), segunda = vueltas(n, kv, 2)
        self.assertFalse(d["vivo"])
        self.assertEqual(d["residente"], "huerto")
        self.assertEqual(segunda, [])
        self.assertEqual(n.lineas, [])  # no faltó: no es uno de los que murieron con el nodo apagado

    def test_lo_que_ya_se_publico_en_esta_corrida_no_se_pisa(self):
        # una siembra que se reintenta con el nodo andando: lo de aquí manda sobre lo que lee del bus
        kv = Kv({clave(SOLAS): entrada(SOLAS)})
        n = nodo()
        n.publicado[clave(SOLAS)] = "lo de esta corrida"
        asyncio.run(n.sembrar(kv))
        self.assertEqual(n.publicado[clave(SOLAS)], "lo de esta corrida")

    def test_si_el_bus_no_contesta_se_dice_y_se_reintenta(self):
        kv = Kv({clave(SOLAS): entrada(SOLAS)}, falla=TimeoutError("nats: timeout"))
        n = nodo()
        self.assertFalse(asyncio.run(n.sembrar(kv)))
        self.assertFalse(n.sembrado)
        self.assertIn("lo intento de nuevo", n.lineas[0])
        kv.falla = None
        n.vueltas = mod_nodo.ESPEJO_CADA  # la vuelta en que se reintenta (y la de cada 30 s, apagada abajo)
        n.mirar_deseado = lambda locales: None
        with mock.patch.object(mod_nodo.mod_estado, "abrir"):
            vueltas(n, kv, 2)
        self.assertTrue(n.sembrado)
        self.assertEqual([d["vivo"] for _, d in kv.puestos], [False])

    def test_si_otra_maquina_ya_lo_publica_no_se_le_pisa(self):
        # sembrado como vivo aquí, pero mientras tanto lo publicó el laptop (se mudó allá): el vigía lo dejó en
        # `vistos`, y publicarlo muerto desde aquí le borraría su estado
        kv = Kv({clave(SOLAS): entrada(SOLAS)})
        n = nodo()
        asyncio.run(n.sembrar(kv))
        n.vistos[clave(SOLAS)] = entrada(SOLAS, maquina="laptop")
        self.assertEqual(vueltas(n, kv, 3), [[], [], []])
        self.assertNotIn(clave(SOLAS), n.publicado)


class LaVentanaQueAllaNoContesta(Prueba):
    """`ventana_de` en el laptop, con un hilo del servidor que el bus da por vivo y cuya ventana aquí no está."""

    def armar(self):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx, n.reabiertas, n.lineas = None, {}, []
        n.anotar = n.lineas.append
        n.config = SimpleNamespace(remotos=[SimpleNamespace(nombre="servidor")])
        anotados = {SOLAS: {"remoto": "servidor", "sesion": "@397/73706700"}}
        tel = SimpleNamespace(mux=object(), viva=True, por_nombre=lambda nombre: None, vivo=lambda h: False,
                              estado=SimpleNamespace(remotos=lambda: anotados, archivados=lambda: set(),
                                                     registro_ajeno=lambda: {}))
        traidos = []
        parches = (mock.patch("telar.ordenes._comun.tejer", return_value=tel),
                   mock.patch("telar.remoto.traer", lambda tel, remoto, sesion, aqui: traidos.append((sesion, aqui))))
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        return n, traidos

    def test_la_reapertura_se_corta_a_la_tercera(self):
        n, traidos = self.armar()
        d = entrada(SOLAS)
        for _ in range(5):
            n.ventana_de(d)
        self.assertEqual(len(traidos), 3)
        self.assertEqual(len([x for x in n.lineas if "la reabrí" in x]), 3)
        cortes = [x for x in n.lineas if "no la reabro más" in x]
        self.assertEqual(len(cortes), 1)  # se dice una vez
        self.assertIn("allá no contesta", cortes[0])
        # el hilo publica otra cosa: se le vuelve a abrir
        n.ventana_de({**d, "atencion": "trabajando", "actualizado": "2026-11-16T09:00:00-03:00"})
        self.assertEqual(len(traidos), 4)

    def test_la_cuenta_es_en_cinco_minutos_y_vuelve_a_cero_con_otra_direccion(self):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.reabiertas, n.lineas = {}, []
        n.anotar = n.lineas.append
        d = entrada(SOLAS)
        # reabiertas a lo largo de más de cinco minutos: un laptop que durmió, una red que se cortó
        self.assertTrue(all(n.puede_reabrir(d, ahora=t) for t in (0, 100, 200 + mod_nodo.REABRIR_EN, 300 + 2 * mod_nodo.REABRIR_EN)))
        n.reabiertas.clear()
        self.assertEqual([n.puede_reabrir(d, ahora=t) for t in (0, 10, 20, 30)], [True, True, True, False])
        self.assertFalse(n.puede_reabrir(d, ahora=10_000))  # cortada, queda cortada aunque pase el rato
        self.assertTrue(n.puede_reabrir({**d, "ventana": "@12/abcdef01"}, ahora=10_001))  # otra dirección
        self.assertEqual(len(n.lineas), 1)


if __name__ == "__main__":
    unittest.main()
