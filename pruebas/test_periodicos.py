"""Procesos periódicos: el horario, el archivo, el bloque del crontab, correr y la orden."""

from __future__ import annotations

import io
import json
import os
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.movil import HiloMovil  # noqa: E402

from telar import config as mod_config
from telar import periodicos as m

SCL = ZoneInfo("America/Santiago")


class ElHorario(Prueba):
    def test_la_proxima(self):
        viernes = datetime(2026, 10, 2, 8, 40, tzinfo=SCL)
        casos = {"0 7-19/2 * * 1-5": (2, 9, 0), "30 8,18 * * *": (2, 18, 30), "*/15 * * * *": (2, 8, 45),
                 "0 9 * * 1": (5, 9, 0), "@daily": (3, 0, 0), "0 10 * * 6,0": (3, 10, 0)}
        for cuando, (dia, h, mi) in casos.items():
            t = m.Horario(cuando).proxima(viernes)
            self.assertEqual((t.day, t.hour, t.minute), (dia, h, mi), cuando)

    def test_dia_del_mes_o_dia_de_la_semana(self):
        # cron: con los dos restringidos, vale cualquiera de los dos
        t = m.Horario("0 9 1 * 1").proxima(datetime(2026, 10, 2, 10, 0, tzinfo=SCL))
        self.assertEqual((t.month, t.day), (10, 5))

    def test_lo_que_no_es_cron(self):
        for malo in ("61 * * * *", "* * *", "a * * * *", "5-1 * * * *", "* 24 * * *", "*/0 * * * *"):
            with self.assertRaises(m.ErrorDePeriodicos, msg=malo):
                m.Horario(malo)


class ElArchivo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "periodicos.toml"

    def test_ida_y_vuelta(self):
        a = m.Archivo(zona="America/Santiago", procesos=[
            m.Proceso(nombre="resumen", cuando="30 8 * * 1-5", comando='~/bin/resumen --dice "hola"'),
            m.Proceso(nombre="correo", cuando="0 */2 * * *", mensaje="/correo", hilo="✉ correo", max_abiertos=2,
                      argumentos=("--permission-mode", "acceptEdits"), activo=False)])
        m.escribir(self.ruta, a)
        b = m.leer(self.ruta)
        self.assertEqual((b.zona, b.procesos), (a.zona, a.procesos))
        m.escribir(self.ruta, b)
        self.assertTrue(self.ruta.with_name("periodicos.toml.anterior").exists())

    def test_lo_mal_definido_no_se_lee(self):
        for texto in ('[x]\ncuando = "0 * * * *"\n', '[x]\ncuando = "0 * * * *"\ncomando = "a"\nmensaje = "b"\n',
                      '[x]\ncuando = "nunca"\ncomando = "a"\n', '[X Y]\ncuando = "0 * * * *"\ncomando = "a"\n',
                      '[x]\ncuando = "0 * * * *"\ncomando = "a"\notra = 1\n', 'zona = "Marte/Olimpo"\n'):
            self.ruta.write_text(texto)
            with self.assertRaises(m.ErrorDePeriodicos, msg=texto):
                m.leer(self.ruta)

    def test_cambiar_de_comando_a_mensaje_deja_el_otro_vacio(self):
        a = m.Archivo(procesos=[m.Proceso(nombre="x", cuando="0 * * * *", comando="ls")])
        p = m.cambiar(a, "x", mensaje="/hola")
        self.assertEqual((p.comando, p.mensaje, p.tipo), ("", "/hola", "mensaje"))


class ElCrontab(Prueba):
    def test_el_bloque_no_toca_lo_de_afuera_y_va_al_final(self):
        a = m.Archivo(zona="America/Santiago", procesos=[
            m.Proceso(nombre="a", cuando="0 9 * * *", comando="x"),
            m.Proceso(nombre="b", cuando="0 10 * * *", comando="y", activo=False)])
        actual = "MAILTO=\"\"\n0 1 * * * /usr/bin/respaldo\n"
        uno = m.con_bloque(actual, m.bloque(a, "/opt/telar"))
        self.assertTrue(uno.startswith(actual))
        self.assertIn("CRON_TZ=America/Santiago", uno)
        self.assertIn("0 9 * * * /opt/telar periodicos correr a --en aqui", uno)
        self.assertIn("# (pausado) 0 10 * * * /opt/telar periodicos correr b --en aqui", uno)
        # otra vez: reemplaza, no duplica
        dos = m.con_bloque(uno + "5 5 * * * despues\n", m.bloque(m.Archivo(), "/opt/telar"))
        self.assertEqual(dos.count(m.MARCA_INICIO), 1)
        self.assertNotIn("correr a", dos)
        self.assertIn("5 5 * * * despues", dos)
        self.assertIn("0 1 * * * /usr/bin/respaldo", dos)


class Correr(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = SimpleNamespace(config=mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado"))

    def test_un_comando_deja_su_log_y_su_resultado(self):
        r = m.correr(self.ctx, m.Proceso(nombre="eco", cuando="* * * * *", comando="echo hola; exit 3"))
        self.assertEqual((r["codigo"], r["resultado"]), (3, "salió con 3"))
        self.assertIn("hola", m.log(self.ctx.config, "eco"))
        self.assertEqual(m.ultima(self.ctx.config, "eco")["codigo"], 3)

    def test_un_mensaje_no_abre_mas_de_la_cuenta(self):
        hoy = datetime.now().strftime("%m/%d")
        abiertos = [HiloMovil(sesion="t", nombre=f"✉ correo {hoy} 08:00", ventana="@1", marca="a"),
                    HiloMovil(sesion="t", nombre=f"✉ correo {hoy} 10:00", ventana="@2", marca="b")]
        p = m.Proceso(nombre="correo", cuando="* * * * *", mensaje="/correo", hilo="✉ correo", max_abiertos=2)
        with mock.patch("telar.movil.hilos", return_value=abiertos), mock.patch("telar.movil.crear") as crear:
            r = m.correr(self.ctx, p)
        self.assertEqual(r["codigo"], 0)
        self.assertIn("saltado", r["resultado"])
        crear.assert_not_called()

    def test_uno_olvidado_de_otro_dia_se_cierra_en_vez_de_frenar(self):
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        ahora = datetime(2026, 10, 7, 20, 30)
        quieto = HiloMovil(sesion="t", nombre="▣ planear 10/05 20:30", ventana="@1", marca="a")
        mirado = HiloMovil(sesion="t", nombre="▣ planear 10/05 21:00", clientes=1, ventana="@2", marca="b")
        ocupado = HiloMovil(sesion="t", nombre="▣ planear 10/06 20:30", ventana="@3", marca="c")
        pegado = HiloMovil(sesion="t", nombre="▣ planear 10/06 20:31", ventana="@4", marca="d")
        est = mod_estado.abrir(self.ctx.config)
        est.anotar_atencion(ocupado.nombre, Atencion.TRABAJANDO, cuando=datetime(2026, 10, 7, 19, 0))
        est.anotar_atencion(pegado.nombre, Atencion.TRABAJANDO, cuando=datetime(2026, 10, 6, 21, 0))
        matados = []
        with mock.patch("telar.movil._tmux", side_effect=lambda *a, **k: matados.append(a) or ""):
            cerrados = m.cerrar_viejos(self.ctx.config, [quieto, mirado, ocupado, pegado], ahora)
        # el quieto y el pegado (trabajando hace más de tres horas) se cierran; el mirado y el ocupado no
        self.assertEqual(cerrados, [quieto.nombre, pegado.nombre])
        self.assertEqual(matados, [("kill-window", "-t", "@1"), ("kill-window", "-t", "@4")])


class _ConArchivo(Prueba):
    """Un config.toml vacío en una carpeta temporal y `aplicar` que no toca el crontab de verdad."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        (base / "config.toml").write_text("")
        self.parches = [mock.patch.dict(os.environ, {"TELAR_CONFIG": str(base / "config.toml")}),
                        mock.patch.object(m, "aplicar", return_value="")]
        for p in self.parches:
            p.start()
            self.addCleanup(p.stop)
        self.ctx = SimpleNamespace(config=mod_config.Config(raiz=base, estado=base / "estado"))
        self.ruta = base / "periodicos.toml"

    def orden(self, *argv):
        from telar.ordenes import periodicos as orden

        salida, err = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(err):
            codigo = orden.main(list(argv), self.ctx)
        return codigo, salida.getvalue() + err.getvalue()


class LaOrden(_ConArchivo):
    def test_crear_cambiar_pausar_borrar(self):
        self.assertEqual(self.orden("nuevo", "eco", "--cuando", "0 9 * * *", "--comando", "echo hola")[0], 0)
        self.assertNotEqual(self.orden("nuevo", "eco", "--cuando", "0 9 * * *", "--comando", "x")[0], 0)
        self.assertEqual(self.orden("editar", "eco", "--cuando", "0 10 * * 1-5")[0], 0)
        self.assertEqual(self.orden("pausar", "eco")[0], 0)
        self.assertEqual(m.leer(self.ruta).procesos[0], m.Proceso(nombre="eco", cuando="0 10 * * 1-5",
                                                                   comando="echo hola", activo=False))
        codigo, salida = self.orden("ver", "--json")
        datos = json.loads(salida)
        self.assertEqual((codigo, datos["procesos"][0]["proxima"]), (0, ""))
        self.assertEqual(self.orden("borrar", "eco")[0], 0)
        self.assertEqual(m.leer(self.ruta).procesos, [])

    def test_lo_invalido_no_se_escribe(self):
        codigo, salida = self.orden("nuevo", "eco", "--cuando", "todos los días", "--comando", "x")
        self.assertNotEqual(codigo, 0)
        self.assertIn("cron", salida)
        self.assertFalse(self.ruta.exists())

    def test_en_otra_maquina_va_por_ssh_sin_rebotar(self):
        ctx = SimpleNamespace(config=mod_config.Config(remotos=(mod_config.Remoto(nombre="srv", destino="u@srv"),),
                                                      periodicos_en="srv"))
        from telar.ordenes import periodicos as orden

        with mock.patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="{}", stderr="")) as run, \
                redirect_stdout(io.StringIO()):
            orden.main(["pausar", "eco", "--json"], ctx)
        linea = run.call_args.args[0][-1]
        self.assertIn("telar periodicos pausar eco --json --en aqui", linea)


class ElFormulario(_ConArchivo):
    """Lo que usa el formulario del dashboard: el horario al escribir, las skills, editar todo junto."""

    def test_el_horario_dice_sus_proximas_o_por_que_no(self):
        codigo, salida = self.orden("horario", "0 9 * * *", "--json", "--n", "2")
        datos = json.loads(salida)
        self.assertEqual((codigo, datos["valido"], len(datos["proximas"])), (0, True, 2))
        codigo, salida = self.orden("horario", "0 25 * * *", "--json")
        datos = json.loads(salida)
        self.assertEqual((codigo, datos["valido"]), (0, False))
        self.assertIn("hora", datos["error"])

    def test_editar_todo_de_una(self):
        self.orden("nuevo", "x", "--cuando", "0 9 * * *", "--mensaje", "/correo", "--arg=--permission-mode", "--arg", "acceptEdits")
        self.assertEqual(m.leer(self.ruta).procesos[0].argumentos, ("--permission-mode", "acceptEdits"))
        codigo, _ = self.orden("editar", "x", "--cuando", "0 10 * * *", "--hilo", "✉", "--max", "2", "--sin-args",
                               "--descripcion", "", "--activo", "no")
        p = m.leer(self.ruta).procesos[0]
        self.assertEqual((codigo, p.cuando, p.hilo, p.max_abiertos, p.argumentos, p.activo), (0, "0 10 * * *", "✉", 2, (), False))

    def test_las_skills_de_una_carpeta(self):
        ctx = SimpleNamespace(config=mod_config.Config(agente=mod_config.Agente(nombre="claude-code")))
        falso = SimpleNamespace(skills=lambda carpeta: [{"nombre": "correo", "descripcion": "el correo", "origen": "proyecto", "ruta": "/x"}])
        from telar.ordenes import periodicos as orden

        with mock.patch("telar.agente.obtener", return_value=falso), redirect_stdout(io.StringIO()) as salida:
            orden.main(["skills", "--carpeta", "/tmp", "--json"], ctx)
        self.assertEqual(json.loads(salida.getvalue())["skills"], [{"nombre": "correo", "descripcion": "el correo", "origen": "proyecto"}])


class ConAgente(Prueba):
    """Un periódico con agente: con bus, el encargo va a la casilla del agente; si el bus falla, se teclea."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.ctx = SimpleNamespace(config=mod_config.Config(raiz=base, estado=base / "estado",
                                                           bus=mod_config.Bus(url="nats://127.0.0.1:1")))
        from telar.agentes import Agente

        self.agente = Agente(clave="gestion", nombre="Gestión", carpeta=base)
        self.p = m.Proceso(nombre="avanzar", cuando="0 9 * * *", mensaje="/avanzar", agente="gestion")

    def correr(self, enviar):
        with mock.patch("telar.agentes.descubrir", return_value=[self.agente]), \
                mock.patch("telar.bus.enviar", side_effect=enviar) as env, \
                mock.patch("telar.encargos.encargar", return_value={"estado": "entregado"}) as tecleado:
            r = m.correr(self.ctx, self.p)
        return r, env, tecleado

    def test_con_bus_va_a_su_casilla_y_no_se_teclea(self):
        r, env, tecleado = self.correr(lambda cfg, para, texto, **k: {"id": "x1"})
        self.assertEqual(r["codigo"], 0)
        self.assertIn("por el bus", r["resultado"])
        self.assertEqual((env.call_args.args[1], env.call_args.kwargs["tipo"]), ("Gestión", "encargo"))
        tecleado.assert_not_called()

    def test_si_el_bus_falla_va_por_el_camino_de_siempre_y_lo_dice(self):
        from telar import bus

        def falla(*a, **k):
            raise bus.ErrorDeBus("no responde")

        r, _, tecleado = self.correr(falla)
        self.assertEqual(r["codigo"], 0)
        self.assertIn("el bus no lo recibió", r["resultado"])
        tecleado.assert_called_once()
