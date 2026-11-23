"""Procesos periódicos: el horario, el archivo, el bloque del crontab, correr y la orden."""

from __future__ import annotations

import io
import json
import os
import subprocess
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


class ElCrontabSinPrivilegiosNuevos(Prueba):
    """El nodo corre con NoNewPrivileges: el setgid de `crontab` no vale y `crontab -l` dice «Permission denied». Ahí
    el crontab se lee y se escribe por `systemd-run --user`, que no hereda la restricción."""

    def correr(self, nnp: bool, hay_systemd_run: bool = True):
        llamadas = []

        def run(orden, **kw):
            llamadas.append((orden, kw.get("input")))
            return subprocess.CompletedProcess(orden, 0, stdout="# lo de antes\n", stderr="")

        which = {"crontab": "/usr/bin/crontab", "systemd-run": "/usr/bin/systemd-run" if hay_systemd_run else None}
        with mock.patch.object(m, "sin_privilegios_nuevos", return_value=nnp), \
                mock.patch.object(m.shutil, "which", side_effect=which.get), \
                mock.patch.object(m.subprocess, "run", side_effect=run):
            m.aplicar(m.Archivo(procesos=[m.Proceso(nombre="eco", cuando="0 9 * * *", comando="echo")]), "/bin/telar")
        return llamadas

    def test_con_no_new_privs_va_por_systemd_run(self):
        (leer, _), (escribir, entrada) = self.correr(nnp=True)
        previo = ["systemd-run", "--user", "--pipe", "--wait", "--quiet", "--collect"]
        self.assertEqual(leer, [*previo, "crontab", "-l"])
        self.assertEqual(escribir, [*previo, "crontab", "-"])
        self.assertIn("periodicos correr eco", entrada)
        self.assertIn("# lo de antes", entrada)

    def test_sin_la_restriccion_crontab_a_secas(self):
        self.assertEqual([o for o, _ in self.correr(nnp=False)], [["crontab", "-l"], ["crontab", "-"]])

    def test_sin_systemd_run_crontab_a_secas(self):
        self.assertEqual([o for o, _ in self.correr(nnp=True, hay_systemd_run=False)], [["crontab", "-l"], ["crontab", "-"]])

    def test_lee_la_marca_del_proceso(self):
        estado = "Name:\tpython3\nNoNewPrivs:\t1\nSeccomp:\t0\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=estado)):
            self.assertTrue(m.sin_privilegios_nuevos())
        with mock.patch("builtins.open", mock.mock_open(read_data=estado.replace("Privs:\t1", "Privs:\t0"))):
            self.assertFalse(m.sin_privilegios_nuevos())
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertFalse(m.sin_privilegios_nuevos(), "en macOS no hay /proc")


class LaOrden(_ConArchivo):
    def test_si_el_crontab_no_se_deja_lo_dice_y_no_parece_hecho(self):
        self.assertEqual(self.orden("nuevo", "eco", "--cuando", "0 9 * * *", "--comando", "echo hola")[0], 0)
        with mock.patch.object(m, "aplicar", side_effect=m.ErrorDePeriodicos("crontab -l falló: Permission denied")):
            codigo, salida = self.orden("pausar", "eco")
        self.assertNotEqual(codigo, 0)
        self.assertIn("eco: pausado en periodicos.toml, pero el crontab sigue como estaba", salida)
        self.assertIn("telar periodicos aplicar", salida)

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

        self.agente = Agente(clave="secretaria", nombre="Secretaría", carpeta=base)
        self.p = m.Proceso(nombre="avanzar", cuando="0 9 * * *", mensaje="/avanzar", agente="secretaria")

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
        self.assertEqual((env.call_args.args[1], env.call_args.kwargs["tipo"]), ("Secretaría", "encargo"))
        tecleado.assert_not_called()

    def test_si_el_bus_falla_va_por_el_camino_de_siempre_y_lo_dice(self):
        from telar import bus

        def falla(*a, **k):
            raise bus.ErrorDeBus("no responde")

        r, _, tecleado = self.correr(falla)
        self.assertEqual(r["codigo"], 0)
        self.assertIn("el bus no lo recibió", r["resultado"])
        tecleado.assert_called_once()


class LaSalidaDeCron(Prueba):
    def test_el_bloque_no_manda_correo(self):
        # cada corrida guarda su salida en su log: por correo era una copia más, en una casilla compartida
        from telar import periodicos as mod
        lineas = mod.bloque(mod.Archivo(procesos=[]), "/x/telar")
        self.assertEqual(lineas[:2], [mod.MARCA_INICIO, 'MAILTO=""'])


class LasDependencias(_ConArchivo):
    """`despues` (la que se declara) y el destino (la que se deduce: dos que van al mismo agente comparten su casilla)."""

    def test_despues_ida_y_vuelta_y_lo_que_no_vale(self):
        a = m.Archivo(procesos=[m.Proceso(nombre="retro", cuando="0 18 * * *", mensaje="/planear retro"),
                                m.Proceso(nombre="plan", cuando="30 20 * * *", mensaje="/planear", despues=("retro",))])
        m.escribir(self.ruta, a)
        self.assertEqual(m.leer(self.ruta).procesos[1].despues, ("retro",))
        with self.assertRaises(m.ErrorDePeriodicos):
            m.Proceso(nombre="plan", cuando="0 9 * * *", comando="x", despues=("plan",)).validar()

    def test_la_orden_lo_pone_lo_quita_y_no_acepta_uno_que_no_existe(self):
        self.orden("nuevo", "retro", "--cuando", "0 18 * * *", "--mensaje", "/planear retro")
        self.assertNotEqual(self.orden("nuevo", "plan", "--cuando", "30 20 * * *", "--mensaje", "/planear", "--despues", "nadie")[0], 0)
        self.assertEqual(self.orden("nuevo", "plan", "--cuando", "30 20 * * *", "--mensaje", "/planear", "--despues", "retro")[0], 0)
        self.assertEqual(m.leer(self.ruta).por_nombre("plan").despues, ("retro",))
        self.assertEqual(self.orden("editar", "plan", "--sin-despues")[0], 0)
        self.assertEqual(m.leer(self.ruta).por_nombre("plan").despues, ())
        # el formulario los manda separados por comas
        self.orden("nuevo", "correo", "--cuando", "0 8 * * *", "--mensaje", "/correo")
        self.assertEqual(self.orden("editar", "plan", "--despues", "retro,correo")[0], 0)
        self.assertEqual(m.leer(self.ruta).por_nombre("plan").despues, ("retro", "correo"))

    def test_a_quien_le_llega(self):
        agentes = [{"clave": "secretaria", "nombre": "Secretaría", "carpeta": "/x", "icono": ""}]
        script = Path(self.tmp.name) / "pasada"
        script.write_text('#!/bin/sh\n[ -n "$x" ] || exit 0\nexec telar encargar secretaria "/lecturas"\n')
        casos = {
            m.Proceso(nombre="a", cuando="* * * * *", mensaje="/avanzar", agente="secretaria"): ("agente", "secretaria", False),
            m.Proceso(nombre="b", cuando="* * * * *", mensaje="/despertar"): ("hilo", "", False),
            m.Proceso(nombre="c", cuando="* * * * *", comando='if true; then telar encargar Secretaría "/resumen"; fi'): ("agente", "secretaria", True),
            m.Proceso(nombre="d", cuando="* * * * *", comando=str(script)): ("agente", "secretaria", True),
            m.Proceso(nombre="e", cuando="* * * * *", comando="bin/bajar", carpeta=self.tmp.name): ("comando", "", False),
        }
        for p, (tipo, agente, inferido) in casos.items():
            d = m.destino(p, agentes)
            self.assertEqual((d["tipo"], d["agente"], d["inferido"]), (tipo, agente, inferido), p.nombre)

    def test_ver_trae_los_agentes_y_lo_de_cada_uno(self):
        self.orden("nuevo", "retro", "--cuando", "0 18 * * *", "--mensaje", "/planear retro", "--agente", "secretaria")
        with mock.patch.object(m, "agentes_de", return_value=[{"clave": "secretaria", "nombre": "Secretaría", "carpeta": "/x", "icono": ""}]):
            datos = json.loads(self.orden("ver", "--json")[1])
        self.assertEqual(datos["agentes"][0]["clave"], "secretaria")
        self.assertEqual((datos["procesos"][0]["destino"]["tipo"], datos["procesos"][0]["despues"]), ("agente", []))


class ElCalendario(Prueba):
    """Las corridas de una semana: las de su horario, con cómo salieron las que pasaron, y las de fuera de horario."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = SimpleNamespace(config=mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado"))
        self.d = m.carpeta_estado(self.ctx.config)
        self.d.mkdir(parents=True)

    def historial(self, nombre, *registros):
        with open(self.d / f"{nombre}.historial.jsonl", "a") as f:
            for r in registros:
                f.write(json.dumps(r) + "\n")

    def test_lo_que_paso_y_lo_que_viene(self):
        from datetime import date

        a = m.Archivo(zona="America/Santiago", procesos=[m.Proceso(nombre="x", cuando="0 9,13,18 * * *", comando="eco")])
        self.historial("x",
                       {"inicio": "2026-11-10T09:00:01-03:00", "codigo": 0, "resultado": "ok"},
                       {"inicio": "2026-11-10T13:00:02-03:00", "codigo": 2, "resultado": "salió con 2"},
                       # el 10 a las 18 no corrió; el 11 a las 9 se saltó; a las 11:20, alguien lo corrió a mano
                       {"inicio": "2026-11-11T09:00:01-03:00", "codigo": 0, "resultado": "saltado: ya hay 1"},
                       {"inicio": "2026-11-11T11:20:00-03:00", "codigo": 0, "resultado": "ok", "manual": True})
        ahora = datetime(2026, 11, 11, 12, 0, tzinfo=SCL)
        cs = m.corridas(SimpleNamespace(config=self.ctx.config), a, date(2026, 11, 9), 3, ahora)["x"]
        estados = [(c["dia"][8:], c["min"], c["estado"], bool(c.get("manual"))) for c in cs]
        self.assertEqual(estados, [
            ("09", 540, "sin-registro", False), ("09", 780, "sin-registro", False), ("09", 1080, "sin-registro", False),
            ("10", 540, "bien", False), ("10", 780, "fallo", False), ("10", 1080, "falto", False),
            ("11", 540, "saltado", False), ("11", 680, "bien", True), ("11", 780, "proxima", False), ("11", 1080, "proxima", False),
        ])

    def test_lo_que_solo_dejo_su_log(self):
        from datetime import date

        a = m.Archivo(zona="America/Santiago", procesos=[m.Proceso(nombre="h", cuando="0 10 * * *", mensaje="/despertar")])
        (self.d / "h.log").write_text("\n── 2026-11-10 10:00:01 · h ──\nabrí «◌ 11/10 10:00»\n"
                                      "\n── 2026-11-11 10:00:02 · h ──\nsaltado: ya hay 3 abiertos\n")
        with mock.patch.dict(os.environ, {"TZ": "America/Santiago"}):
            import time
            time.tzset()
            self.addCleanup(time.tzset)
            cs = m.corridas(SimpleNamespace(config=self.ctx.config), a, date(2026, 11, 10), 2, datetime(2026, 11, 12, 0, 0, tzinfo=SCL))["h"]
        self.assertEqual([c["estado"] for c in cs], ["bien", "saltado"])

    def test_correr_anota_el_historial_y_si_fue_a_mano(self):
        m.correr(self.ctx, m.Proceso(nombre="eco", cuando="* * * * *", comando="true"), manual=True)
        lineas = (self.d / "eco.historial.jsonl").read_text().splitlines()
        self.assertEqual((len(lineas), json.loads(lineas[0])["manual"], json.loads(lineas[0])["codigo"]), (1, True, 0))


class ElPadre(Prueba):
    """Un periódico que abre hilos los cuelga de un padre (el hilo de un agente), como `telar hilo hijo`."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = SimpleNamespace(config=mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                                             agente=mod_config.Agente(nombre="claude-code")))

    def test_el_hilo_que_abre_cuelga_del_padre_y_hereda_sus_etiquetas(self):
        from telar import estado as mod_estado

        est = mod_estado.abrir(self.ctx.config)
        est.etiquetar("Cuaderno", ["personal"])
        falso = SimpleNamespace(nuevo_con_id=lambda texto: (["claude", texto], "sid-1"))
        p = m.Proceso(nombre="nota", cuando="0 10 * * *", mensaje="/pensar", hilo="◌ nota", padre="Cuaderno")
        with mock.patch("telar.movil.hilos", return_value=[]), mock.patch("telar.movil.crear"), \
                mock.patch("telar.agente.obtener", return_value=falso), mock.patch("telar.agente.lanzar.anotar"), \
                mock.patch("telar.encargos.liberar"):
            r = m.correr(self.ctx, p)
        self.assertEqual(r["codigo"], 0, r["resultado"])
        self.assertIn("hijo de «Cuaderno»", r["resultado"])
        est = mod_estado.abrir(self.ctx.config)
        self.assertEqual(est.padres().get(r["hilo"]), "Cuaderno")
        self.assertEqual(tuple(est.etiquetas().get(r["hilo"], ())), ("personal",))

    def test_padre_solo_con_un_hilo_nuevo(self):
        with self.assertRaises(m.ErrorDePeriodicos):
            m.Proceso(nombre="x", cuando="* * * * *", mensaje="/avanzar", agente="secretaria", padre="Secretaría").validar()
        with self.assertRaises(m.ErrorDePeriodicos):
            m.Proceso(nombre="x", cuando="* * * * *", comando="ls", padre="Secretaría").validar()
        a = m.Archivo(procesos=[m.Proceso(nombre="x", cuando="* * * * *", mensaje="/pensar", padre="Cuaderno")])
        # pasarlo a un agente le quita el padre (un encargo va a la sesión del agente: no abre hilos)
        self.assertEqual(m.cambiar(a, "x", agente="secretaria").padre, "")
