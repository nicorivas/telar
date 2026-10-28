"""El servidor como mainframe (telar.alojamiento): pedir un lugar por el bus, aprobarlo, y el ayudante de root.

Nada de esto crea usuarios de verdad: el ayudante de root se reemplaza por una función, y el programa
`servidor/telar-alojar` se prueba en seco (sus pasos, su validación), nunca como root."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import RAIZ, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import alojamiento, cuentas, instalacion, personas, unirse

try:
    import bcrypt  # noqa: F401
    HAY_BCRYPT = True
except ImportError:
    HAY_BCRYPT = False

SECRETO_PABLO = "p" * 48
SECRETO_ANA = "a" * 48


def sin_ayudante(_pedido):
    raise AssertionError("no se esperaba hablar con el ayudante de root")


@mock.patch.object(alojamiento, "SPOOL", Path("/no/existe"))
class EnLaMaquinaDelBus(Prueba):
    """«ana» corre el bus y el servidor; «pablo» y «carla» son miembros; «beto» es admin."""

    def setUp(self):
        super().setUp()
        if not HAY_BCRYPT:
            self.skipTest("falta bcrypt (el extra «bus»)")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        entorno = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.secretos = {"ana": SECRETO_ANA, "pablo": SECRETO_PABLO, "carla": "c" * 48, "beto": "b" * 48}
        cuentas.escribir(cuentas.carpeta(), {n: cuentas.hashear(s) for n, s in self.secretos.items()})
        personas.atender("ana", "ana", {"accion": "rol", "nombre": "beto", "rol": "admin"})
        recarga = mock.patch.object(unirse, "recargar_bus", return_value="")
        recarga.start()
        self.addCleanup(recarga.stop)
        self.config = SimpleNamespace(bus=SimpleNamespace(url="nats://100.66.75.117:4222", persona="ana",
                                                          administra="", token="", maquina="telar"))
        self.pedidos_al_ayudante: list[dict] = []

    def ayuda(self, resultado=None):
        def _ayuda(pedido):
            self.pedidos_al_ayudante.append(pedido)
            return resultado if resultado is not None else {"ok": True}
        return _ayuda

    def pedir(self, quien="pablo", **extra):
        datos = {"accion": "pedir", "secreto": self.secretos[quien], "maquina": "laptop", **extra}
        return alojamiento.atender("ana", quien, datos, self.config)

    def aprobar(self, persona="pablo", por="ana", **kw):
        return alojamiento.atender("ana", por, {"accion": "aprobar", "persona": persona}, self.config,
                                   sincrono=True, **kw)

    def estado(self, persona="pablo"):
        return alojamiento.leer()[persona]["estado"]

    # ── la cuenta del servidor ──

    def test_el_servicio_se_exporta_a_todas_y_todas_lo_importan(self):
        conf = (cuentas.carpeta() / "servidor.conf").read_text()
        self.assertIn('{ service: "alojar.ana" }', conf)  # sin `accounts`: cualquiera lo puede importar
        self.assertEqual(conf.count('subject: "alojar.ana"'), 3)  # pablo, carla y beto; ana lo tiene en casa
        bloque_ana = conf.split("  ana: {")[1].split("  beto: {")[0]
        self.assertNotIn('subject: "alojar.ana"', bloque_ana)

    def test_sin_dueno_no_hay_servicio(self):
        self.assertNotIn("alojar.", cuentas.configuracion({"ana": "$2b$11$" + "a" * 53, "pablo": "$2b$11$" + "p" * 53}))

    # ── pedir ──

    def test_pedir_deja_un_pedido_pendiente_y_el_secreto_no_sale_en_ver(self):
        r = self.pedir(llave="ssh-ed25519 AAAAC3Nza pablo@laptop")
        self.assertIn("queda pendiente", r["hecho"])
        a = alojamiento.leer()["pablo"]
        self.assertEqual((a["estado"], a["maquina"], a["secreto"]), ("pendiente", "laptop", SECRETO_PABLO))
        self.assertNotIn(SECRETO_PABLO, json.dumps(r))
        self.assertNotIn(SECRETO_PABLO, json.dumps(alojamiento.atender("ana", "ana", {"accion": "ver"}, self.config)))
        modo = (cuentas.carpeta() / "alojamientos.json").stat().st_mode & 0o777
        self.assertEqual(modo, 0o600)

    def test_el_secreto_tiene_que_ser_el_de_la_cuenta(self):
        with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
            alojamiento.atender("ana", "pablo", {"accion": "pedir", "secreto": SECRETO_ANA}, self.config)
        self.assertEqual(e.exception.codigo, 403)  # el de otra persona, ni aunque sea de verdad
        self.assertEqual(alojamiento.leer(), {})

    def test_lo_que_no_sirve_al_pedir(self):
        casos = (("ana", {}, 409),                                       # el dueño ya es de la casa
                 ("pablo", {"llave": "esto no es una llave"}, 422),
                 ("pablo", {"llave": "ssh-ed25519 AAA\nrm -rf /"}, 422))
        for quien, extra, codigo in casos:
            with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
                alojamiento.atender("ana", quien, {"accion": "pedir", "secreto": self.secretos[quien], **extra}, self.config)
            self.assertEqual(e.exception.codigo, codigo, (quien, extra))
        with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:   # una cuenta que el bus no tiene
            alojamiento.atender("ana", "zoe", {"accion": "pedir", "secreto": "z" * 48}, self.config)
        self.assertEqual(e.exception.codigo, 403)

    def test_un_nombre_del_sistema_no_se_puede_tomar(self):
        for nombre in ("root", "sshd", "a", "Pablo", "pa blo"):
            with self.assertRaises(alojamiento.ErrorDeAlojamiento):
                alojamiento.validar_nombre(nombre)

    def test_pedir_de_nuevo_reemplaza_el_pendiente(self):
        self.pedir()
        self.pedir(llave="ssh-rsa AAAAB3 otra")
        self.assertEqual(alojamiento.leer()["pablo"]["llave"], "ssh-rsa AAAAB3 otra")

    # ── quién puede qué ──

    def test_un_miembro_ve_solo_lo_suyo_y_no_decide(self):
        self.pedir("pablo")
        self.pedir("carla")
        r = alojamiento.atender("ana", "carla", {"accion": "estado"}, self.config)
        self.assertEqual([a["persona"] for a in r["alojamientos"]], ["carla"])
        self.assertFalse(r["administra"])
        for accion in ("ver", "aprobar", "rechazar", "quitar"):
            with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
                alojamiento.atender("ana", "carla", {"accion": accion, "persona": "pablo"}, self.config, ayuda=sin_ayudante)
            self.assertEqual(e.exception.codigo, 403, accion)
        self.assertEqual(self.estado("pablo"), "pendiente")

    def test_un_admin_ve_todo_y_aprueba(self):
        self.pedir("pablo")
        self.pedir("carla")
        r = alojamiento.atender("ana", "beto", {"accion": "ver"}, self.config)
        self.assertEqual(sorted(a["persona"] for a in r["alojamientos"]), ["carla", "pablo"])
        self.aprobar("pablo", por="beto", ayuda=self.ayuda())
        self.assertEqual(self.estado("pablo"), "activo")

    def test_fuera_de_la_maquina_del_bus_no_atiende(self):
        (cuentas.carpeta() / "servidor.conf").unlink()
        with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
            alojamiento.atender("ana", "ana", {"accion": "ver"}, self.config)
        self.assertEqual(e.exception.codigo, 404)

    # ── aprobar, rechazar, quitar ──

    def test_aprobar_le_pide_al_ayudante_su_lugar_y_borra_el_secreto(self):
        self.pedir(llave="ssh-ed25519 AAAAC3Nza pablo@laptop")
        r = self.aprobar(ayuda=self.ayuda())
        self.assertEqual(self.pedidos_al_ayudante, [{
            "accion": "crear", "nombre": "pablo", "llave": "ssh-ed25519 AAAAC3Nza pablo@laptop", "secreto": SECRETO_PABLO,
            "puerto": 8781, "bus": "nats://100.66.75.117:4222", "memoria": alojamiento.MEMORIA, "cpu": alojamiento.CPU}])
        a = alojamiento.leer()["pablo"]
        self.assertEqual((a["estado"], a["usuario"], a["puerto"], a["por"]), ("activo", "pablo", 8781, "ana"))
        self.assertNotIn("secreto", a)
        self.assertNotIn(SECRETO_PABLO, (cuentas.carpeta() / "alojamientos.json").read_text())
        self.assertIn("preparando su lugar", r["hecho"])

    def test_cada_alojado_tiene_su_puerto(self):
        self.pedir("pablo"), self.pedir("carla")
        self.aprobar("pablo", ayuda=self.ayuda())
        self.aprobar("carla", ayuda=self.ayuda())
        self.assertEqual([self.pedidos_al_ayudante[0]["puerto"], self.pedidos_al_ayudante[1]["puerto"]], [8781, 8782])

    def test_si_el_ayudante_falla_queda_fallido_con_el_secreto_para_reintentar(self):
        self.pedir()
        self.aprobar(ayuda=self.ayuda({"ok": False, "error": "«su uv» falló"}))
        a = alojamiento.leer()["pablo"]
        self.assertEqual((a["estado"], a["error"]), ("falló", "«su uv» falló"))
        self.assertEqual(a["secreto"], SECRETO_PABLO)
        self.aprobar(ayuda=self.ayuda())  # se reintenta con el mismo puerto
        self.assertEqual(self.estado(), "activo")
        self.assertEqual(self.pedidos_al_ayudante[0]["puerto"], self.pedidos_al_ayudante[1]["puerto"])

    def test_un_ayudante_que_revienta_no_deja_el_alojamiento_preparando_para_siempre(self):
        self.pedir()

        def revienta(_):
            raise OSError("sin disco")
        self.aprobar(ayuda=revienta)
        self.assertEqual(self.estado(), "falló")
        self.assertIn("sin disco", alojamiento.leer()["pablo"]["error"])

    def test_no_se_aprueba_dos_veces_ni_lo_que_no_se_pidio(self):
        self.pedir()
        self.aprobar(ayuda=self.ayuda())
        for persona, codigo in (("pablo", 409), ("carla", 404)):
            with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
                self.aprobar(persona, ayuda=sin_ayudante)
            self.assertEqual(e.exception.codigo, codigo)

    def test_aprobar_sin_direccion_del_bus_no_llama_al_ayudante(self):
        self.pedir()
        self.config.bus.url = ""
        with self.assertRaises(alojamiento.ErrorDeAlojamiento):
            self.aprobar(ayuda=sin_ayudante)
        self.assertEqual(self.estado(), "pendiente")

    def test_rechazar_borra_el_secreto(self):
        self.pedir()
        alojamiento.atender("ana", "ana", {"accion": "rechazar", "persona": "pablo"}, self.config)
        a = alojamiento.leer()["pablo"]
        self.assertEqual(a["estado"], "rechazado")
        self.assertNotIn("secreto", a)
        self.pedir()  # puede volver a pedir
        self.assertEqual(self.estado(), "pendiente")

    def test_quitar_cierra_el_lugar(self):
        self.pedir()
        self.aprobar(ayuda=self.ayuda())
        alojamiento.atender("ana", "ana", {"accion": "quitar", "persona": "pablo"}, self.config, ayuda=self.ayuda())
        self.assertEqual(self.pedidos_al_ayudante[-1], {"accion": "quitar", "nombre": "pablo"})
        self.assertEqual(self.estado(), "quitado")
        with self.assertRaises(alojamiento.ErrorDeAlojamiento):  # ya no hay nada que quitar
            alojamiento.atender("ana", "ana", {"accion": "quitar", "persona": "pablo"}, self.config, ayuda=sin_ayudante)

    def test_si_no_se_puede_cerrar_sigue_activo(self):
        self.pedir()
        self.aprobar(ayuda=self.ayuda())
        with self.assertRaises(alojamiento.ErrorDeAlojamiento):
            alojamiento.atender("ana", "ana", {"accion": "quitar", "persona": "pablo"}, self.config,
                                ayuda=self.ayuda({"ok": False, "error": "usermod falló"}))
        self.assertEqual(self.estado(), "activo")

    def test_un_preparando_que_nadie_termino_se_da_por_fallido(self):
        self.pedir()
        alojamiento._cambiar("pablo", estado="preparando", empezo=int(time.time()) - 4 * 3600)
        r = alojamiento.ver("ana", "ana")
        self.assertEqual(r["alojamientos"][0]["estado"], "falló")

    # ── por el nodo ──

    def test_el_nodo_sabe_quien_pide_por_la_cabecera_del_servidor(self):
        datos = json.dumps({"accion": "pedir", "secreto": SECRETO_PABLO}).encode()
        r = alojamiento.atender_pedido_del_bus("ana", datos, {"Nats-Request-Info": json.dumps({"acc": "pablo"})}, self.config)
        self.assertEqual((r["ok"], r["quien"]), (True, "pablo"))
        # no puede pedir a nombre de otro: el secreto no es el de la cuenta que el servidor dice
        r = alojamiento.atender_pedido_del_bus("ana", datos, {"Nats-Request-Info": json.dumps({"acc": "carla"})}, self.config)
        self.assertEqual((r["ok"], r["codigo"]), (False, 403))
        r = alojamiento.atender_pedido_del_bus("ana", b"no", None, self.config)
        self.assertEqual((r["ok"], r["codigo"]), (False, 422))
        r = alojamiento.atender_pedido_del_bus("ana", b'{"accion": "borrar"}', None, self.config)
        self.assertEqual((r["ok"], r["codigo"]), (False, 422))

    def test_pedir_en_la_maquina_del_bus_lo_hace_aqui(self):
        r = alojamiento.pedir(self.config, {"accion": "ver"})
        self.assertTrue(r["administra"])

    # ── la CLI ──

    def test_la_cli(self):
        from telar.ordenes import servidor

        ruta = Path(self.tmp.name) / "bus.token"
        ruta.write_text(SECRETO_ANA + "\n")
        self.config.bus.token = str(ruta)
        ctx = SimpleNamespace(config=self.config)
        alojamiento._cambiar("pablo", estado="pendiente", cuando=int(time.time()), maquina="laptop", secreto=SECRETO_PABLO)
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(servidor.main(["pedidos"], ctx), 0)
        self.assertIn("pablo", salida.getvalue())
        self.assertNotIn(SECRETO_PABLO, salida.getvalue())
        with redirect_stdout(io.StringIO()) as s:
            self.assertEqual(servidor.main(["rechazar", "pablo"], ctx), 0)
        self.assertIn("pedido rechazado", s.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(servidor.main(["aprobar"], ctx), 2)  # ¿quién?

    def test_pedir_por_la_cli_manda_el_secreto_de_esta_persona(self):
        from telar.ordenes import servidor

        ruta = Path(self.tmp.name) / "bus.token"
        ruta.write_text(SECRETO_ANA + "\n")
        llave = Path(self.tmp.name) / "id.pub"
        llave.write_text("ssh-ed25519 AAAAC3Nza ana@laptop\n")
        self.config.bus.token = str(ruta)
        datos = servidor._datos_de_pedir(self.config, str(llave))
        self.assertEqual(datos, {"secreto": SECRETO_ANA, "maquina": "telar", "llave": "ssh-ed25519 AAAAC3Nza ana@laptop"})
        self.config.bus.url = ""
        with self.assertRaises(ValueError):
            servidor._datos_de_pedir(self.config, "")


class ElAyudanteDeRoot(Prueba):
    """`alojamiento.ayudante`: el nodo deja un archivo y espera el resultado del servicio de root."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spool = Path(self.tmp.name)
        (self.spool / "pendientes").mkdir()
        (self.spool / "resultados").mkdir()

    def test_deja_el_pedido_y_devuelve_lo_que_contesta_el_ayudante(self):
        def root():
            for _ in range(200):
                for f in (self.spool / "pendientes").glob("*.json"):
                    pedido = json.loads(f.read_text())
                    f.unlink()
                    (self.spool / "resultados" / f.name).write_text(json.dumps({"ok": True, "visto": pedido["nombre"]}))
                    return
                time.sleep(0.01)
        t = threading.Thread(target=root)
        t.start()
        r = alojamiento.ayudante({"accion": "crear", "nombre": "pablo"}, spool=self.spool, espera=5, dormir=lambda s: time.sleep(0.01))
        t.join()
        self.assertEqual(r, {"ok": True, "visto": "pablo"})
        self.assertEqual(list((self.spool / "resultados").iterdir()), [])  # lo leído se borra

    def test_el_pedido_es_privado(self):
        alojamiento.ayudante({"accion": "crear", "secreto": "s"}, spool=self.spool, espera=0)
        # venció el plazo sin ayudante: el pedido no se queda esperando con el secreto adentro
        self.assertEqual(list((self.spool / "pendientes").iterdir()), [])

    def test_sin_ayudante_instalado_dice_como(self):
        r = alojamiento.ayudante({}, spool=self.spool / "nada")
        self.assertFalse(r["ok"])
        self.assertIn("servidor/README.md", r["error"])

    def test_si_no_contesta_en_el_plazo_lo_dice(self):
        r = alojamiento.ayudante({}, spool=self.spool, espera=3, dormir=lambda s: None,
                                 ahora=iter([0, 1, 2, 3, 4, 5, 6]).__next__)
        self.assertFalse(r["ok"])
        self.assertIn("no contestó", r["error"])


def _cargar_ayudante():
    ruta = str(RAIZ / "servidor" / "telar-alojar")
    cargador = importlib.machinery.SourceFileLoader("telar_alojar", ruta)
    spec = importlib.util.spec_from_loader("telar_alojar", cargador)
    mod = importlib.util.module_from_spec(spec)
    cargador.exec_module(mod)
    return mod


class ElProgramaDeRoot(Prueba):
    """`servidor/telar-alojar`, en seco: lo que valida y los pasos que armaría. Nunca corre nada de verdad."""

    def setUp(self):
        super().setUp()
        self.m = _cargar_ayudante()
        self.crear = {"accion": "crear", "nombre": "pablo", "llave": "ssh-ed25519 AAAAC3Nza pablo@laptop",
                      "secreto": "s" * 48, "bus": "nats://100.66.75.117:4222", "puerto": 8781,
                      "memoria": "2500M", "cpu": "100%"}

    def valido(self, **cambios):
        return self.m.validar({**self.crear, **cambios})

    def test_instala_desde_su_casa_y_no_desde_la_carpeta_del_servicio(self):
        # runuser deja la carpeta del servicio (/): sin el cd, `telar instalar` tomaba / como su raíz (le pasó a Pablo)
        instalar = next(p for p in self.m.plan(self.valido()) if "uv, Claude Code" in p.texto)
        guion = instalar.stdin or " ".join(instalar.argv)
        self.assertLess(guion.index('cd "$HOME/trabajo"'), guion.index("telar instalar"))

    def test_uno_a_medias_se_retoma_y_uno_ajeno_no_se_toca(self):
        from types import SimpleNamespace

        def usuario(comentario):
            return mock.patch.object(self.m.pwd, "getpwnam", return_value=SimpleNamespace(pw_gecos=comentario, pw_uid=1001,
                                                                                         pw_dir="/home/pablo"))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(self.m, "REGISTRO", Path(d)):
            with usuario("Pablo de verdad"):
                with self.assertRaises(self.m.Rechazo):
                    self.m.atender(self.crear, seco=False)
            # uno que dejó este programa a medias (falló un paso después de useradd): se sigue, sin crearlo de nuevo
            with usuario(self.m.COMENTARIO.format("pablo")), mock.patch.object(self.m, "correr", return_value=None) as correr:
                self.m.atender(self.crear, seco=False)
            hechos = [x.argv[0] for x in correr.call_args.args[0] if x.argv]
            self.assertNotIn("useradd", hechos)

    def test_el_comentario_del_usuario_no_lleva_dos_puntos(self):
        # el campo de /etc/passwd se separa con «:»: useradd rechaza un comentario que los traiga (le pasó a Pablo)
        useradd = next(p.argv for p in self.m.plan(self.valido()) if p.argv and p.argv[0] == "useradd")
        comentario = useradd[useradd.index("-c") + 1]
        self.assertNotIn(":", comentario)

    def test_acepta_un_pedido_bueno(self):
        v = self.valido()
        self.assertEqual((v["nombre"], v["puerto"]), ("pablo", 8781))

    def test_rechaza_cada_campo_malo(self):
        malos = [{"accion": "borrar"}, {"nombre": "root"}, {"nombre": "Pablo"}, {"nombre": "a;b"}, {"nombre": "../x"},
                 {"nombre": "x" * 40}, {"llave": "ssh-ed25519 AAA; rm -rf /"}, {"llave": "ssh-ed25519 AAA\nssh-rsa B"},
                 {"secreto": "corto"}, {"secreto": "s" * 30 + "$(id)"}, {"bus": "http://x:4222"},
                 {"bus": "nats://x:4222; reboot"}, {"puerto": 80}, {"puerto": "8781"}, {"puerto": True},
                 {"memoria": "mucha"}, {"cpu": "100"}]
        for cambio in malos:
            with self.assertRaises(self.m.Rechazo, msg=str(cambio)):
                self.valido(**cambio)

    def test_quitar_solo_pide_un_nombre_valido(self):
        self.assertEqual(self.m.validar({"accion": "quitar", "nombre": "pablo"}), {"accion": "quitar", "nombre": "pablo"})
        with self.assertRaises(self.m.Rechazo):
            self.m.validar({"accion": "quitar", "nombre": "sshd"})

    def test_lo_que_toca_los_archivos_de_la_persona_lo_hace_como_ella_y_con_su_home(self):
        pasos = self.m.plan(self.valido())
        for p in pasos:
            if p.argv and p.argv[0] == "runuser":
                self.assertEqual(p.argv[:4], ["runuser", "-u", "pablo", "--"], p.texto)
                self.assertEqual(p.argv[4:6], ["env", "-i"], p.texto)   # sin el entorno de root
                self.assertIn("HOME={hogar}", p.argv, p.texto)
        escribe_secreto = next(p for p in pasos if "secreto" in p.texto)
        self.assertEqual(escribe_secreto.stdin, "s" * 48 + "\n")         # el secreto va por la entrada, no en la línea
        self.assertNotIn("s" * 48, " ".join(escribe_secreto.argv))
        self.assertIn("umask 077", " ".join(escribe_secreto.argv))

    def test_el_script_de_instalacion_solo_lleva_lo_validado(self):
        instalar = next(p for p in self.m.plan(self.valido()) if "uv, Claude Code" in p.texto)
        self.assertIn("--bus 'nats://100.66.75.117:4222' --persona 'pablo'", instalar.stdin)
        self.assertIn("--web-puerto 8781 --si", instalar.stdin)
        self.assertNotIn("__", instalar.stdin)

    def test_sin_llave_no_toca_sshd(self):
        textos = [p.texto for p in self.m.plan(self.valido(llave=""))]
        self.assertFalse([t for t in textos if "ssh" in t.lower()])
        self.assertTrue([p for p in self.m.plan(self.valido()) if p.archivo and "sshd_config.d" in p.archivo[0]])

    def test_el_tope_de_recursos_y_el_registro(self):
        pasos = self.m.plan(self.valido())
        slice_ = next(p for p in pasos if p.archivo and "slice.d" in p.archivo[0])
        self.assertIn("MemoryMax=2500M", slice_.archivo[1])
        self.assertIn("CPUQuota=100%", slice_.archivo[1])
        self.assertTrue(any(p.archivo and p.archivo[0].endswith("/pablo.json") for p in pasos))

    def test_la_carpeta_de_pedidos_en_seco(self):
        with tempfile.TemporaryDirectory() as d:
            spool = Path(d)
            os.chmod(spool, 0o700)
            (spool / "pendientes").mkdir()
            (spool / "resultados").mkdir()
            ident = "0123456789abcdef"
            (spool / "pendientes" / f"{ident}.json").write_text(json.dumps({**self.crear, "id": ident}))
            (spool / "pendientes" / "raro.txt").write_text("x")
            with mock.patch.object(self.m, "SPOOL", spool), redirect_stdout(io.StringIO()) as s:
                codigo = self.m.main(["--seco"])
            self.assertEqual(codigo, 0)
            self.assertIn("el usuario pablo", s.getvalue())
            self.assertTrue((spool / "pendientes" / f"{ident}.json").exists())     # en seco no se consume
            self.assertEqual(list((spool / "resultados").iterdir()), [])

    def test_no_se_fia_de_una_carpeta_abierta_ni_de_un_pedido_que_no_es_un_archivo_comun(self):
        with tempfile.TemporaryDirectory() as d:
            spool = Path(d)
            os.chmod(spool, 0o755)
            with mock.patch.object(self.m, "SPOOL", spool), redirect_stdout(io.StringIO()):
                with mock.patch("sys.stderr", new=io.StringIO()):
                    self.assertEqual(self.m.main([]), 2)
            os.chmod(spool, 0o700)
            enlace = spool / "pedido.json"
            enlace.symlink_to("/etc/passwd")
            with self.assertRaises(self.m.Rechazo):
                self.m.leer_pedido(enlace, os.getuid())
            grande = spool / "grande.json"
            grande.write_text(" " * (self.m.TOPE_PEDIDO + 1))
            with self.assertRaises(self.m.Rechazo):
                self.m.leer_pedido(grande, os.getuid())
            ajeno = spool / "ajeno.json"
            ajeno.write_text("{}")
            with self.assertRaises(self.m.Rechazo):
                self.m.leer_pedido(ajeno, os.getuid() + 1)

    def test_el_pedido_malo_se_contesta_y_no_detiene_a_los_demas(self):
        with tempfile.TemporaryDirectory() as d:
            spool = Path(d)
            os.chmod(spool, 0o700)
            (spool / "pendientes").mkdir()
            (spool / "resultados").mkdir()
            (spool / "pendientes" / "aaaaaaaaaaaaaaaa.json").write_text(json.dumps({"accion": "crear", "nombre": "root"}))
            with mock.patch.object(self.m, "SPOOL", spool), redirect_stdout(io.StringIO()):
                self.assertEqual(self.m.main([]), 1)
            r = json.loads((spool / "resultados" / "aaaaaaaaaaaaaaaa.json").read_text())
            self.assertFalse(r["ok"])
            self.assertEqual(list((spool / "pendientes").iterdir()), [])


class ElPuertoDeLaPagina(Prueba):
    def test_telar_instalar_pone_el_puerto_en_el_servicio(self):
        self.assertEqual(instalacion.argumentos(nodo=True, web_puerto=8782), ["serve", "--nodo", "--web", "--web-puerto", "8782"])
        self.assertEqual(instalacion.argumentos(nodo=True), ["serve", "--nodo", "--web"])
        # la unidad de systemd: la de un servidor, aunque la prueba corra en un Mac (que escribiría un plist)
        with mock.patch.object(instalacion.sys, "platform", "linux"):
            _, texto = instalacion.servicio(nodo=True, equipo=False, telar="/x/telar", path="/bin", web_puerto=8782)
        self.assertIn("ExecStart=/x/telar serve --nodo --web --web-puerto 8782", texto)


class LaPaginaDeUnAlojadoSeQueda(unittest.TestCase):
    """`telar instalar` de nuevo, sin banderas, no saca a un alojado de detrás de la puerta: si pasara a `--web`,
    escucharía en el puerto de la persona dueña del servidor, y su servicio no arrancaría."""

    def test_lee_como_sirve_su_pagina_del_servicio_escrito(self):
        from telar import instalacion

        texto = instalacion.unidad_systemd("/x/telar", instalacion.argumentos(
            nodo=True, web_socket="/run/telar/ana/web.sock", web_url="https://telar.ejemplo.ts.net"), "/bin", esperar_tailscale=True)
        self.assertEqual(instalacion.pagina_actual(texto),
                         {"web_socket": "/run/telar/ana/web.sock", "web_url": "https://telar.ejemplo.ts.net"})
        plist = instalacion.plist_launchd("/x/telar", instalacion.argumentos(nodo=True, web_puerto=8790), "/bin", "/log")
        self.assertEqual(instalacion.pagina_actual(plist), {"web_puerto": "8790"})
        self.assertEqual(instalacion.pagina_actual("[Service]\nExecStart=/x/telar serve --nodo --web\n"), {})
