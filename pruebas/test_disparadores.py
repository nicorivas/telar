"""Disparadores (`[disparadores.<nombre>]`) y el estado deseado: la tecla y el reloj traducidos a lo de hoy, el
despacho de «al cambiar» en el nodo con su freno, los residentes sin sesión, doctor y la orden. Sin bus real
ni crontab ni tmux: el nodo se arma sin conectar y lo que corre un disparador es un doble."""

from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import threading
import tomllib
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import deseado
from telar import disparadores as mod
from telar import periodicos
from telar.ordenes import nodo as mod_nodo


def cfg(toml: str, **extra) -> mod_config.Config:
    return replace(mod_config.desde_dict(tomllib.loads(toml)), **extra)


class LaTeclaEsUnAtajo(Prueba):
    PARES = [
        ('[atajos.m]\nnombre = "⚑ correo"\nmensaje = "/correo"\n',
         '[disparadores.correo]\ntecla = "m"\nhilo = "⚑ correo"\nmensaje = "/correo"\n'),
        ('[atajos.w]\nnombre = "w"\nmensaje = "/whatsapp"\ndescripcion = "el chat"\nen = "seccion:diario"\n',
         '[disparadores.w]\ntecla = "w"\nmensaje = "/whatsapp"\ndescripcion = "el chat"\naparece = "seccion:diario"\n'),
        ('[atajos.g]\nnombre = "Faro"\nmensaje = "/avanzar"\nagente = "faro"\n',
         '[disparadores.g]\ntecla = "g"\nhilo = "Faro"\nmensaje = "/avanzar"\nagente = "faro"\n'),
    ]

    def test_cada_forma_nueva_da_la_misma_config_que_la_de_antes(self):
        for antes, ahora in self.PARES:
            self.assertEqual(cfg(antes).atajos, cfg(ahora).atajos, ahora)

    def test_sin_disparadores_nada_cambia(self):
        c = cfg(self.PARES[0][0])
        self.assertEqual(c.disparadores, ())
        self.assertEqual([a.tecla for a in c.atajos], ["m"])

    def test_van_despues_de_los_de_antes_y_se_listan_todos(self):
        c = cfg('[atajos.w]\nnombre = "w"\nmensaje = "/w"\n'
                '[disparadores.correo]\ntecla = "m"\nmensaje = "/correo"\n'
                '[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "rehacer"\n')
        self.assertEqual([a.tecla for a in c.atajos], ["w", "m"])
        self.assertEqual(c.atajos[1].nombre, "correo")  # sin hilo, el nombre del disparador
        self.assertEqual([(d.nombre, d.tipo) for d in c.disparadores], [("correo", "tecla"), ("tablero", "cambio")])

    def test_una_tecla_en_las_dos_formas_o_dos_veces_es_un_error(self):
        with self.assertRaisesRegex(mod_config.ErrorDeConfig, r"disparadores\.correo\.tecla: .*\[atajos\.m\]"):
            cfg('[atajos.m]\nnombre = "m"\nmensaje = "/m"\n[disparadores.correo]\ntecla = "m"\nmensaje = "/correo"\n')
        with self.assertRaisesRegex(mod_config.ErrorDeConfig, r"disparadores\.otro\.tecla: «m» ya es la de disparadores\.correo"):
            cfg('[disparadores.correo]\ntecla = "m"\nmensaje = "/c"\n[disparadores.otro]\ntecla = "m"\nmensaje = "/o"\n')

    def test_apagada_no_hay_tecla(self):
        c = cfg('[disparadores.correo]\ntecla = "m"\nmensaje = "/c"\nactivo = false\n'
                '[disparadores.otro]\ntecla = "m"\nmensaje = "/o"\n')
        self.assertEqual([a.mensaje for a in c.atajos], ["/o"])


class LoQueNoVale(Prueba):
    CASOS = {
        '[disparadores.x]\ncomando = "a"\n': r"disparadores\.x: cuándo, una sola .*falta",
        '[disparadores.x]\ncuando = "@daily"\ntecla = "m"\ncomando = "a"\n': r"llegaron cuando y tecla",
        '[disparadores.x]\ncuando = "99 * * * *"\ncomando = "a"\n': r"disparadores\.x\.cuando: .*fuera de rango",
        '[disparadores.x]\nal = "correo:ana"\ncomando = "a"\n': r"disparadores\.x\.al: \"cambio:<tema>\"",
        '[disparadores.x]\nal = "cambio:Tareas Nuevas"\ncomando = "a"\n': r"disparadores\.x\.al:",
        '[disparadores.x]\ntecla = "mm"\nmensaje = "a"\n': r"disparadores\.x\.tecla: un solo carácter",
        '[disparadores.x]\ntecla = "m"\ncomando = "a"\n': r"disparadores\.x\.comando: no va con tecla",
        '[disparadores.x]\ntecla = "m"\n': r"falta mensaje",
        '[disparadores.x]\ntecla = "m"\nmensaje = "a"\naparece = " "\n': r"disparadores\.x\.aparece:",
        '[disparadores.x]\ncuando = "@daily"\naparece = "hoy"\ncomando = "a"\n': r"disparadores\.x\.aparece: no va con cuando",
        '[disparadores.x]\ncuando = "@daily"\ncolor = "rojo"\ncomando = "a"\n': r"disparadores\.x\.color: no existe",
        '[disparadores.x]\ncuando = "@daily"\ncomando = "a"\nmensaje = "b"\n': r"comando o mensaje, uno de los dos",
        '[disparadores.x]\nal = "cambio:tareas"\ncomando = "a"\nagente = "faro"\n': r"disparadores\.x\.agente: va con mensaje",
        '[disparadores.x]\ncuando = "@daily"\nmensaje = "a"\nmax_abiertos = true\n': r"disparadores\.x\.max_abiertos:",
        '[disparadores.x]\ncuando = "@daily"\ncomando = "a"\nargumentos = "--uno"\n': r"disparadores\.x\.argumentos:",
        '[disparadores.Resumen]\ncuando = "@daily"\ncomando = "a"\n': r"disparadores\.Resumen: el nombre va en minúsculas",
        'disparadores = 3\n': r"disparadores: se esperaba una tabla",
    }

    def test_cada_error_nombra_el_disparador(self):
        for toml, dice in self.CASOS.items():
            with self.assertRaisesRegex(mod_config.ErrorDeConfig, dice, msg=toml):
                cfg(toml)


class ElRelojEsUnPeriodico(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "periodicos.toml"

    TOML = ('cuando = "0 9-19/2 * * *"\nmensaje = "/correo"\nhilo = "✉ correo"\nmax_abiertos = 2\n'
            'argumentos = ["--permission-mode", "acceptEdits"]\ncarpeta = "~/trabajo"\ndescripcion = "el correo"\n')

    def test_da_el_mismo_proceso_que_en_periodicos_toml(self):
        self.ruta.write_text("[correo]\n" + self.TOML)
        de_antes = periodicos.leer(self.ruta).procesos[0]
        c = cfg("[disparadores.correo]\n" + self.TOML)
        ahora = periodicos.completo(periodicos.Archivo(), c).procesos
        self.assertEqual(len(ahora), 1)
        self.assertTrue(ahora[0].disparador)
        self.assertEqual(replace(ahora[0], disparador=False), de_antes)

    def test_va_al_crontab_pero_no_se_escribe_en_periodicos_toml(self):
        self.ruta.write_text('[eco]\ncuando = "0 8 * * *"\ncomando = "echo"\n')
        c = cfg('[disparadores.resumen]\ncuando = "30 8 * * 1-5"\ncomando = "~/bin/resumen"\n'
                '[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "x"\n'
                '[disparadores.correo]\ntecla = "m"\nmensaje = "/c"\n')
        a = periodicos.completo(periodicos.leer(self.ruta), c)
        self.assertEqual([p.nombre for p in a.procesos], ["eco", "resumen"])  # ni la tecla ni el cambio
        bloque = periodicos.bloque(a, "/bin/telar")
        self.assertIn("30 8 * * 1-5 /bin/telar periodicos correr resumen --en aqui", bloque)
        periodicos.escribir(self.ruta, a)
        self.assertEqual([p.nombre for p in periodicos.leer(self.ruta).procesos], ["eco"])

    def test_un_nombre_en_dos_lados_es_un_error(self):
        self.ruta.write_text('[resumen]\ncuando = "0 8 * * *"\ncomando = "echo"\n')
        for cuerpo in ('cuando = "@daily"\ncomando = "a"\n', 'al = "cambio:tareas"\ncomando = "a"\n'):
            c = cfg("[disparadores.resumen]\n" + cuerpo)
            with self.assertRaisesRegex(periodicos.ErrorDePeriodicos, r"\[disparadores\.resumen\] .*periodicos\.toml"):
                periodicos.completo(periodicos.leer(self.ruta), c)

    def test_en_otra_maquina_que_la_de_los_periodicos_no_corre(self):
        c = cfg('[disparadores.resumen]\ncuando = "@daily"\ncomando = "a"\n[bus]\nmaquina = "laptop"\n',
                periodicos_en="servidor")
        self.assertEqual(periodicos.completo(periodicos.Archivo(), c).procesos, [])
        self.assertFalse(mod.corren_aqui(c))
        # la máquina de los periódicos nombrada por su nombre también es «aquí»
        self.assertTrue(mod.corren_aqui(replace(c, periodicos_en="laptop")))

    def test_el_path_no_crece_en_cada_corrida(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin"}):
            uno = periodicos._entorno()["PATH"]
            with mock.patch.dict(os.environ, {"PATH": uno}):
                self.assertEqual(periodicos._entorno()["PATH"], uno)


class LaOrdenPeriodicos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        (base / "config.toml").write_text("")
        for p in (mock.patch.dict(os.environ, {"TELAR_CONFIG": str(base / "config.toml")}),
                  mock.patch.object(periodicos, "aplicar", return_value="")):
            p.start()
            self.addCleanup(p.stop)
        c = cfg('[disparadores.resumen]\ncuando = "30 8 * * 1-5"\ncomando = "~/bin/resumen"\n')
        self.ctx = SimpleNamespace(config=replace(c, raiz=base, estado=base / "estado", origen=base / "config.toml"))

    def orden(self, *argv):
        from telar.ordenes import periodicos as orden

        salida = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            codigo = orden.main(list(argv), self.ctx)
        return codigo, salida.getvalue()

    def test_se_lista_y_no_se_edita_desde_aqui(self):
        codigo, salida = self.orden("ver", "--json")
        procesos = json.loads(salida)["procesos"]
        self.assertEqual((codigo, procesos[0]["nombre"], procesos[0]["disparador"]), (0, "resumen", True))
        codigo, salida = self.orden("pausar", "resumen")
        self.assertNotEqual(codigo, 0)
        self.assertIn("[disparadores.resumen]", salida)

    def test_correr_lo_corre_como_un_periodico(self):
        with mock.patch.object(periodicos, "correr", return_value={"codigo": 0, "resultado": "ok"}) as correr:
            codigo, _ = self.orden("correr", "resumen")
        self.assertEqual(codigo, 0)
        self.assertEqual(correr.call_args.args[1].comando, "~/bin/resumen")


class ElFreno(Prueba):
    def despacho(self, *nombres, **opciones):
        return mod.Despacho([mod.Disparador(nombre=n, al="cambio:tareas", comando="x") for n in nombres], **opciones)

    def test_una_rafaga_mientras_corre_deja_una_sola_corrida_pendiente(self):
        d = self.despacho("tablero")
        self.assertEqual([x.nombre for x in d.llego("tareas", 0)], ["tablero"])
        for t in range(10):
            self.assertEqual(d.llego("tareas", 1 + t), [])
        d.termino("tablero")
        self.assertEqual(d.listos(10), [])          # la pausa
        self.assertEqual([x.nombre for x in d.listos(30)], ["tablero"])
        d.termino("tablero")
        self.assertEqual(d.listos(1000), [])        # no quedó nada más

    def test_otro_tema_no_lo_dispara(self):
        d = self.despacho("tablero")
        self.assertEqual(d.llego("correos", 0), [])
        self.assertEqual(d.pendientes, {})

    def test_el_tope_por_hora_lo_frena_una_vez_y_lo_suelta(self):
        d = self.despacho("tablero", pausa=0, tope=3)
        for t in range(3):
            self.assertEqual(len(d.llego("tareas", t)), 1)
            d.termino("tablero")
        self.assertEqual(d.llego("tareas", 10), [])
        self.assertEqual(d.llego("tareas", 11), [])
        self.assertEqual(len(d.avisos), 1)
        self.assertIn("¿se dispara a sí mismo?", d.avisos[0])
        self.assertEqual([x.nombre for x in d.listos(3600)], ["tablero"])  # la primera ya salió de la hora

    def test_no_mas_de_dos_a_la_vez_en_el_nodo(self):
        d = self.despacho("uno", "dos", "tres")
        self.assertEqual([x.nombre for x in d.llego("tareas", 0)], ["uno", "dos"])
        d.termino("uno")
        self.assertEqual([x.nombre for x in d.listos(1)], ["tres"])

    def test_solo_los_de_cambio_activos_y_en_la_maquina_de_los_periodicos(self):
        c = cfg('[disparadores.a]\nal = "cambio:tareas"\ncomando = "x"\n'
                '[disparadores.b]\nal = "cambio:tareas"\ncomando = "x"\nactivo = false\n'
                '[disparadores.c]\ncuando = "@daily"\ncomando = "x"\n[bus]\nmaquina = "laptop"\n')
        self.assertEqual([d.nombre for d in mod.de_cambio(c, "laptop")], ["a"])
        self.assertEqual(mod.de_cambio(replace(c, periodicos_en="servidor"), "laptop"), [])


def nodo(config):
    n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
    n.config, n.yo, n.persona, n.ctx = config, "laptop", "ana", SimpleNamespace(config=config)
    n.anotado = []
    n.anotar = n.anotado.append
    return n


class ElNodoDespacha(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.estado = Path(self.tmp.name)

    def config(self, toml):
        return cfg(toml + '[bus]\nurl = "nats://bus"\nmaquina = "laptop"\n', estado=self.estado)

    def cambios(self, n, temas, correr, espera=0.3):
        async def todo():
            for tema in temas:
                await n._cambio(SimpleNamespace(subject=f"cambio.ana.{tema}"))
            await asyncio.sleep(espera)
            while getattr(n, "disparos", None):
                await asyncio.gather(*list(n.disparos))

        with mock.patch.object(mod, "correr", side_effect=correr):
            asyncio.run(todo())

    def test_un_cambio_que_espera_alguien_lo_corre_y_lo_anota(self):
        n = nodo(self.config('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "rehacer"\n'))
        corridos = []
        self.cambios(n, ["tareas", "correos"], lambda ctx, d: corridos.append(d.nombre) or {"resultado": "ok", "codigo": 0})
        self.assertEqual(corridos, ["tablero"])
        self.assertTrue((self.estado / "cambios" / "tareas").exists())  # y el dashboard relee, como antes
        self.assertTrue((self.estado / "cambios" / "correos").exists())
        self.assertIn("disparador «tablero» (cambio:tareas): ok", n.anotado)

    def test_una_rafaga_mientras_corre_es_una_corrida_mas(self):
        n = nodo(self.config('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "rehacer"\n'))
        n.despacho = mod.Despacho(mod.de_cambio(n.config, "laptop"), pausa=0)
        suelta, corridos = threading.Event(), []

        def correr(ctx, d):
            corridos.append(d.nombre)
            suelta.wait(2)
            return {"resultado": "ok", "codigo": 0}

        async def todo():
            for _ in range(5):
                await n._cambio(SimpleNamespace(subject="cambio.ana.tareas"))
            await asyncio.sleep(0.1)
            suelta.set()
            for _ in range(50):
                await asyncio.sleep(0.02)
                if not getattr(n, "disparos", None):
                    break

        with mock.patch.object(mod, "correr", side_effect=correr):
            asyncio.run(todo())
        self.assertEqual(corridos, ["tablero", "tablero"])

    def test_uno_que_falla_no_tumba_el_nodo(self):
        n = nodo(self.config('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "rehacer"\n'))

        def falla(ctx, d):
            raise OSError("no hay disco")

        self.cambios(n, ["tareas"], falla)
        self.assertIn("disparador «tablero» (cambio:tareas): OSError: no hay disco", n.anotado)

    def test_en_otra_maquina_que_la_de_los_periodicos_solo_se_anota(self):
        n = nodo(replace(self.config('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "x"\n'),
                         periodicos_en="servidor"))
        corridos = []
        self.cambios(n, ["tareas"], lambda ctx, d: corridos.append(d) or {})
        self.assertEqual(corridos, [])
        self.assertTrue((self.estado / "cambios" / "tareas").exists())

    def test_la_vuelta_suelta_lo_que_esperaba_su_pausa(self):
        n = nodo(self.config('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "x"\n'))
        n.despacho = mod.Despacho(mod.de_cambio(n.config, "laptop"), pausa=0)
        n.despacho.pendientes["tablero"] = None
        corridos = []

        async def todo():
            n.locales = lambda: (_ for _ in ()).throw(RuntimeError("basta"))  # corta la vuelta después
            with self.assertRaises(RuntimeError):
                await n._vuelta(None, None)
            await asyncio.gather(*list(n.disparos))

        with mock.patch.object(mod, "correr", side_effect=lambda ctx, d: corridos.append(d.nombre) or {}):
            asyncio.run(todo())
        self.assertEqual(corridos, ["tablero"])


class LosResidentesSinSesion(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = mod_config.Config(estado=Path(self.tmp.name))

    LOCALES = {"Faro": {"residente": "faro", "vivo": False}, "Molino": {"residente": "molino", "vivo": True},
               "Puente": {"residente": "", "vivo": False}, "T84": {"residente": "", "vivo": True}}

    def test_cuales_son(self):
        self.assertEqual(deseado.residentes_sin_sesion(self.LOCALES), ["Faro"])

    def test_el_nodo_lo_anota_al_cambiar_no_en_cada_vuelta_y_doctor_lo_lee(self):
        n = nodo(self.config)
        for _ in range(3):
            n.mirar_deseado(self.LOCALES)
        self.assertEqual(n.anotado, ["«Faro» es residente y no tiene sesión: se le abre cuando le llegue algo"])
        n.mirar_deseado({**self.LOCALES, "Faro": {"residente": "faro", "vivo": True}})
        self.assertEqual(n.anotado[-1], "«Faro» tiene sesión de nuevo")
        n.mirar_deseado(self.LOCALES)
        self.assertEqual(len(n.anotado), 3)
        from telar.ordenes import doctor

        r = doctor._deseado(SimpleNamespace(config=self.config))
        self.assertEqual([(x["nombre"], x["estado"]) for x in r], [("deseado", "ok")])
        self.assertIn("Faro", r[0]["dice"])

    def test_si_el_nodo_no_corre_doctor_no_dice_nada(self):
        from telar.ordenes import doctor

        self.assertEqual(doctor._deseado(SimpleNamespace(config=self.config)), [])
        deseado.escribir(self.config, "laptop", ["Faro"], cuando=datetime.now().astimezone() - timedelta(hours=1))
        self.assertEqual(doctor._deseado(SimpleNamespace(config=self.config)), [])
        deseado.escribir(self.config, "laptop", [])
        self.assertEqual(doctor._deseado(SimpleNamespace(config=self.config))[0]["dice"],
                         "los residentes de aquí tienen sesión")


class Doctor(Prueba):
    def revisar(self, c, crontab=""):
        from telar.ordenes import doctor

        with mock.patch("shutil.which", return_value="/usr/bin/crontab"), \
                mock.patch.object(periodicos, "crontab_actual", return_value=crontab):
            return doctor._disparadores(SimpleNamespace(config=c))

    def test_sugiere_el_disparador_de_cada_atajo_y_leido_da_lo_mismo(self):
        antes = cfg('[atajos.m]\nnombre = "⚑ Correo"\nmensaje = "/correo"\nen = "correo"\n'
                    '[atajos.g]\nnombre = "Faro"\nmensaje = "/avanzar"\nagente = "faro"\n')
        r = self.revisar(antes)
        self.assertEqual([x["estado"] for x in r], ["aviso", "aviso"])
        nuevo = "\n".join(x["arreglo"].split("\n", 1)[1] for x in r)
        self.assertIn("[disparadores.correo]", nuevo)
        self.assertEqual(cfg(nuevo).atajos, antes.atajos)

    def test_lo_declarado_que_no_esta_en_el_crontab(self):
        c = cfg('[disparadores.resumen]\ncuando = "@daily"\ncomando = "a"\n'
                '[disparadores.viejo]\ncuando = "@daily"\ncomando = "a"\n')
        bloque = "\n".join([periodicos.MARCA_INICIO, "0 0 * * * /bin/telar periodicos correr resumen --en aqui",
                            "# (pausado) 0 0 * * * /bin/telar periodicos correr viejo --en aqui", periodicos.MARCA_FIN])
        r = self.revisar(c, bloque)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["estado"], r[0]["arreglo"]), ("aviso", "telar periodicos aplicar"))
        self.assertTrue(r[0]["dice"].startswith("viejo:"))

    def test_al_dia_es_un_ok(self):
        c = cfg('[disparadores.resumen]\ncuando = "@daily"\ncomando = "a"\n'
                '[disparadores.correo]\ntecla = "m"\nmensaje = "/c"\n')
        bloque = "\n".join([periodicos.MARCA_INICIO, "0 0 * * * telar periodicos correr resumen --en aqui", periodicos.MARCA_FIN])
        self.assertEqual([(x["estado"], x["dice"]) for x in self.revisar(c, bloque)], [("ok", "1 de reloj, 1 de tecla")])

    def test_uno_de_cambio_sin_bus_no_lo_oye_nadie(self):
        r = self.revisar(cfg('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "a"\n'))
        self.assertEqual(r[0]["estado"], "aviso")
        self.assertIn("sin bus", r[0]["dice"])

    def test_en_otra_maquina_dice_donde_corren(self):
        c = cfg('[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "a"\n[bus]\nmaquina = "laptop"\n',
                periodicos_en="servidor")
        r = self.revisar(c)
        self.assertEqual(r[0]["estado"], "ok")
        self.assertIn("corren en servidor", r[0]["dice"])

    def test_sin_nada_nada(self):
        self.assertEqual(self.revisar(mod_config.Config()), [])


class LaOrden(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        c = cfg('[disparadores.resumen]\ncuando = "30 8 * * 1-5"\ncomando = "~/bin/resumen"\n'
                '[disparadores.correo]\ntecla = "m"\nmensaje = "/correo"\n'
                '[disparadores.tablero]\nal = "cambio:tareas"\ncomando = "rehacer"\n[bus]\nmaquina = "laptop"\n')
        self.ctx = SimpleNamespace(config=replace(c, estado=base / "estado", origen=base / "config.toml"))

    def orden(self, *argv):
        from telar.ordenes import disparadores as orden

        salida = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            codigo = orden.main(list(argv), self.ctx)
        return codigo, salida.getvalue()

    def test_la_lista(self):
        codigo, salida = self.orden("--json")
        datos = json.loads(salida)
        self.assertEqual((codigo, datos["maquina"], datos["corren_aqui"]), (0, "laptop", True))
        self.assertEqual([(d["nombre"], d["tipo"]) for d in datos["disparadores"]],
                         [("resumen", "reloj"), ("correo", "tecla"), ("tablero", "cambio")])
        self.assertTrue(datos["disparadores"][0]["proxima"])
        self.assertEqual(datos["disparadores"][2]["tema"], "tareas")
        codigo, salida = self.orden()
        self.assertEqual(codigo, 0)
        self.assertIn("cambio:tareas", salida)

    def test_correr_uno_de_cambio_y_no_una_tecla(self):
        with mock.patch.object(periodicos, "correr", return_value={"codigo": 0, "resultado": "ok"}) as correr:
            self.assertEqual(self.orden("correr", "tablero"), (0, "tablero: ok\n"))
        self.assertTrue(correr.call_args.args[1].disparador)
        codigo, salida = self.orden("correr", "correo")
        self.assertNotEqual(codigo, 0)
        self.assertIn("telar atajo m", salida)
        self.assertNotEqual(self.orden("correr", "nada")[0], 0)

    def test_esta_en_la_ayuda(self):
        from telar import cli

        self.assertIn("disparadores", cli.ORDENES)
