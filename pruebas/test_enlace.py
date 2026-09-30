"""La puerta entre dos máquinas: lo que se cumple, lo que se rechaza y lo que queda escrito."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba, RAIZ  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import enlace as m
from telar.cli import Contexto
from telar.config import Enlace, ErrorDeConfig, Puerta

CLAVE = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGxZ3vQ2Z0k5rXn8Qe7bY1JcVhXk4uQwqN0dFgHt2LmP telar-enlace"
OTRA = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOtraLlaveDeOtroCualquierDistintaXXXXXXXXXXXXXXX alguien@laptop"


class ConPuerta(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.entrada = self.base / "entrada"
        self.ctx = self.contexto()

    def contexto(self, **puerta):
        config = mod_config.Config(raiz=self.base, estado=self.base / "estado",
                                   puerta=Puerta(entrada=str(self.entrada), **puerta))
        return Contexto(config=config)

    def leer_log(self):
        ruta = self.base / "estado" / "enlace.log"
        return ruta.read_text().splitlines() if ruta.exists() else []


class Archivos(ConPuerta):
    def test_el_nombre_no_puede_escapar_ni_esconderse(self):
        for crudo, esperado in (("foto.png", "foto.png"), ("../../etc/passwd", "passwd"), ("a/b/c.txt", "c.txt"),
                                ("..\\..\\x.exe", "x.exe"), (".bashrc", "bashrc"), ("..", "archivo"), ("", "archivo"),
                                ("mi archivo (1).pdf", "mi archivo _1_.pdf"), ("é;rm -rf.sh", "_rm -rf.sh")):
            self.assertEqual(m.nombre_de_archivo(crudo), esperado, crudo)
        self.assertLessEqual(len(m.nombre_de_archivo("x" * 500 + ".txt")), 100)

    def test_se_guarda_privado_y_dentro_de_la_carpeta(self):
        ruta = m.guardar_archivo(self.ctx.config, "../../fuera.txt", b"hola")
        self.assertEqual(ruta.parent, self.entrada)
        self.assertEqual(ruta.read_bytes(), b"hola")
        self.assertEqual(stat.S_IMODE(ruta.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.entrada.stat().st_mode), 0o700)

    def test_un_archivo_nunca_pisa_a_otro(self):
        a = m.guardar_archivo(self.ctx.config, "foto.png", b"uno")
        b = m.guardar_archivo(self.ctx.config, "foto.png", b"dos")
        c = m.guardar_archivo(self.ctx.config, "foto.png", b"tres")
        self.assertEqual([p.name for p in (a, b, c)], ["foto.png", "foto-1.png", "foto-2.png"])
        self.assertEqual(a.read_bytes(), b"uno")

    def test_vacio_y_gigante_se_rechazan(self):
        with self.assertRaises(m.ErrorDePuerta):
            m.guardar_archivo(self.ctx.config, "a", b"")
        with mock.patch.object(m, "MAX_ARCHIVO", 10):
            with self.assertRaises(m.ErrorDePuerta):
                m.guardar_archivo(self.ctx.config, "a", b"x" * 11)
        self.assertFalse(self.entrada.exists() and any(self.entrada.iterdir()))


class Servir(ConPuerta):
    def test_ping_dice_quien_es_y_que_hace(self):
        r = m.servir(self.ctx, "ping")
        self.assertTrue(r["ok"])
        self.assertEqual(r["verbos"], list(m.VERBOS_ENLACE))

    def test_lo_que_no_es_un_verbo_no_se_cumple_por_mas_que_se_pida(self):
        for pedido in ("bash", "bash -c 'rm -rf ~'", "cat /etc/passwd", "ping; ls", "ping $(id)", "../ping",
                       "", "   ", "'sin cerrar", "ARCHIVO x"):
            r = m.servir(self.ctx, pedido)
            self.assertFalse(r["ok"], pedido)
        self.assertFalse(list(self.base.glob("**/pwned*")))

    def test_un_verbo_apagado_en_la_configuracion_no_responde(self):
        ctx = self.contexto(verbos=("ping",))
        self.assertTrue(m.servir(ctx, "ping")["ok"])
        r = m.servir(ctx, "archivo x.txt", b"hola")
        self.assertFalse(r["ok"])
        self.assertIn("no hace", r["error"])
        self.assertFalse(self.entrada.exists())

    def test_los_argumentos_sobrantes_se_rechazan(self):
        self.assertFalse(m.servir(self.ctx, "ping extra")["ok"])
        self.assertFalse(m.servir(self.ctx, "archivo")["ok"])
        self.assertFalse(m.servir(self.ctx, "archivo a b", b"x")["ok"])
        self.assertFalse(m.servir(self.ctx, "enviar Faro cosa", b"x")["ok"])

    def test_lo_que_pesa_mas_que_el_tope_se_rechaza_antes_de_hacer_nada(self):
        r = m.servir(self.ctx, "enviar Faro", b"x" * (m.LIMITE["enviar"] + 1))
        self.assertFalse(r["ok"])
        r = m.servir(self.ctx, "ping", b"basura")  # ping no lee nada: cualquier cosa de más es un error
        self.assertFalse(r["ok"])

    def test_archivo_de_extremo_a_extremo(self):
        r = m.servir(self.ctx, "archivo '../mi foto.png'", b"\x89PNG bytes")
        self.assertTrue(r["ok"])
        self.assertEqual(Path(r["ruta"]).parent, self.entrada)
        self.assertEqual(Path(r["ruta"]).read_bytes(), b"\x89PNG bytes")
        self.assertEqual(r["bytes"], 10)

    def test_cada_peticion_queda_anotada_tambien_las_rechazadas(self):
        m.servir(self.ctx, "ping")
        m.servir(self.ctx, "bash -c 'x'")
        lineas = self.leer_log()
        self.assertEqual(len(lineas), 2)
        self.assertIn("\tping\t", lineas[0])
        self.assertIn("\tno: ", lineas[1])

    def test_un_fallo_interno_se_dice_sin_reventar(self):
        with mock.patch.dict(m.VERBO, {"ping": mock.Mock(side_effect=RuntimeError("se rompió"))}):
            r = m.servir(self.ctx, "ping")
        self.assertFalse(r["ok"])
        self.assertIn("se rompió", r["error"])


class Enviar(ConPuerta):
    """Escribirle a un hilo: solo si existe y está vivo, y sin que un salto de línea sea un ↩ colado."""

    def con_hilos(self, vivos=("Faro",)):
        escrito = []
        mux = SimpleNamespace(escribir=lambda h, t, enviar=False: escrito.append((h, t, enviar)))
        hilos = {n: SimpleNamespace(nombre=n) for n in ("Faro", "Dormido")}
        tel = SimpleNamespace(mux=mux, aviso="", por_nombre=hilos.get, vivo=lambda h: h.nombre in vivos)
        return mock.patch("telar.ordenes._comun.tejer", return_value=tel), escrito

    def test_escribe_en_un_hilo_vivo(self):
        parche, escrito = self.con_hilos()
        with parche:
            r = m.servir(self.ctx, "enviar Faro enter", "hola\ny la otra línea".encode())
        self.assertTrue(r["ok"], r)
        self.assertEqual(escrito, [("Faro", "hola\ny la otra línea", True)])

    def test_sin_enter_escribe_pero_no_manda(self):
        parche, escrito = self.con_hilos()
        with parche:
            r = m.servir(self.ctx, "enviar Faro", b"medio escrito")
        self.assertTrue(r["ok"])
        self.assertEqual(escrito, [("Faro", "medio escrito", False)])

    def test_un_salto_de_linea_sin_enter_se_rechaza(self):
        parche, escrito = self.con_hilos()
        with parche:
            r = m.servir(self.ctx, "enviar Faro", b"uno\ndos")
        self.assertFalse(r["ok"])
        self.assertEqual(escrito, [])

    def test_no_se_le_escribe_a_lo_que_no_existe_ni_a_lo_que_no_vive(self):
        parche, escrito = self.con_hilos()
        with parche:
            self.assertFalse(m.servir(self.ctx, "enviar Fantasma enter", b"x")["ok"])
            self.assertFalse(m.servir(self.ctx, "enviar Dormido enter", b"x")["ok"])
        self.assertEqual(escrito, [])

    def test_texto_vacio_o_gigante_o_binario(self):
        parche, escrito = self.con_hilos()
        with parche:
            self.assertFalse(m.servir(self.ctx, "enviar Faro enter", b"  \n ")["ok"])
            self.assertFalse(m.servir(self.ctx, "enviar Faro enter", ("x" * (m.MAX_TEXTO + 1)).encode())["ok"])
            self.assertFalse(m.servir(self.ctx, "enviar Faro enter", b"\xff\xfe\x00")["ok"])
        self.assertEqual(escrito, [])


class ElPath(Prueba):
    """sshd trae `PATH=/usr/bin:/bin:…`: sin tmux, el laptop diría que ningún hilo está vivo."""

    def test_se_agregan_los_lugares_habituales_que_existen_y_no_estaban(self):
        with tempfile.TemporaryDirectory() as tmp:
            brew = Path(tmp) / "brew"
            brew.mkdir()
            with mock.patch.object(m, "DONDE_VIVEN", (str(brew), str(Path(tmp) / "no-existe"), "/usr/bin")):
                path = m.completar_path({"PATH": "/usr/bin:/bin"})
        self.assertEqual(path, f"/usr/bin:/bin:{brew}")  # lo que estaba, en su orden; lo nuevo, al final

    def test_no_repite_ni_pierde_nada(self):
        self.assertEqual(m.completar_path({"PATH": "/a:/b"}).split(":")[:2], ["/a", "/b"])
        self.assertEqual(m.completar_path({}).count("/opt/homebrew/bin") <= 1, True)


class Notificar(ConPuerta):
    def test_el_texto_va_por_el_entorno_no_dentro_del_script(self):
        llamadas = []

        def falso(orden, **kw):
            llamadas.append((orden, kw["env"]))
            return SimpleNamespace(returncode=0, stderr="")

        malo = 'listo" & do shell script "rm -rf ~" & "'
        with mock.patch.object(m.sys, "platform", "darwin"), mock.patch.object(m.shutil, "which", return_value="/usr/bin/osascript"), \
                mock.patch.object(m.subprocess, "run", side_effect=falso):
            r = m.servir(self.ctx, "notificar titulo", malo.encode())
        self.assertTrue(r["ok"], r)
        orden, entorno = llamadas[0]
        self.assertNotIn("rm -rf", " ".join(orden))  # el script no lleva el texto
        self.assertEqual(entorno["TELAR_TEXTO"], malo)

    def test_sin_forma_de_avisar_se_dice(self):
        with mock.patch.object(m.sys, "platform", "linux"), mock.patch.object(m.shutil, "which", return_value=None):
            r = m.servir(self.ctx, "notificar", b"hola")
        self.assertFalse(r["ok"])


class Autorizar(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ssh = Path(self.tmp.name) / ".ssh" / "authorized_keys"

    def test_la_linea_ata_la_llave_a_un_solo_comando_sin_extras(self):
        linea, blob = m.linea_autorizada(CLAVE, "/Users/n/.local/bin/telar")
        self.assertTrue(linea.startswith('restrict,command="/Users/n/.local/bin/telar enlace servir" ssh-ed25519 '))
        self.assertEqual(blob, CLAVE.split()[1])
        self.assertEqual(linea.count("command="), 1)

    def test_lo_que_no_es_una_llave_o_no_se_puede_citar_se_rechaza(self):
        for mala in ("", "hola", 'ssh-ed25519 AAAA"; rm -rf ~', CLAVE + "\nssh-rsa " + "A" * 40, "ssh-dss AAAAAAAAAAAAAAAAAAAAAAAA x"):
            with self.assertRaises(m.ErrorDePuerta, msg=repr(mala)):
                m.linea_autorizada(mala, "/bin/telar")
        for ruta in ('/a b/telar', '/a"/telar', "/a$(x)/telar", "/a;b/telar", ""):
            with self.assertRaises(m.ErrorDePuerta, msg=ruta):
                m.linea_autorizada(CLAVE, ruta)

    def test_autorizar_es_idempotente_y_respeta_las_otras_llaves(self):
        self.ssh.parent.mkdir()
        self.ssh.write_text(f"{OTRA}\n")
        self.assertEqual(m.autorizar(CLAVE, "/bin/telar", self.ssh), "nueva")
        self.assertEqual(m.autorizar(CLAVE, "/bin/telar", self.ssh), "actualizada")
        self.assertEqual(m.autorizar(CLAVE, "/otra/ruta/telar", self.ssh), "actualizada")
        lineas = self.ssh.read_text().splitlines()
        self.assertEqual(len(lineas), 2)
        self.assertEqual(lineas[0], OTRA)
        self.assertIn("/otra/ruta/telar enlace servir", lineas[1])
        self.assertEqual(stat.S_IMODE(self.ssh.stat().st_mode), 0o600)
        self.assertEqual((self.ssh.parent / "authorized_keys.bak-telar").read_text().splitlines()[0], OTRA)

    def test_revocar_quita_solo_lo_de_la_puerta(self):
        self.ssh.parent.mkdir()
        self.ssh.write_text(f"{OTRA}\n")
        m.autorizar(CLAVE, "/bin/telar", self.ssh)
        self.assertEqual(m.revocar(self.ssh), 1)
        self.assertEqual(self.ssh.read_text().splitlines(), [OTRA])
        self.assertEqual(m.revocar(self.ssh), 0)
        self.assertEqual(m.revocar(self.ssh.parent / "nada"), 0)


class Configuracion(Prueba):
    def cargar(self, texto):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.toml"
            ruta.write_text(texto)
            return mod_config.cargar(ruta)

    def test_enlaces_y_puerta_se_leen(self):
        c = self.cargar('[enlaces.laptop]\ndestino = "nico@mac"\n[enlace]\nentrada = "~/x/"\nverbos = ["ping", "archivo"]\n')
        self.assertEqual(c.enlaces, (Enlace(nombre="laptop", destino="nico@mac", llave="~/.ssh/telar_enlace"),))
        self.assertEqual(c.puerta, Puerta(entrada="~/x", verbos=("ping", "archivo")))

    def test_por_defecto_hay_todos_los_verbos_y_ningun_enlace(self):
        c = self.cargar("")
        self.assertEqual(c.enlaces, ())
        self.assertEqual(c.puerta.verbos, m.VERBOS_ENLACE)

    def test_lo_raro_se_rechaza(self):
        for texto in ('[enlaces.a]\n', '[enlaces.a]\ndestino = "-oProxyCommand=x"\n', '[enlaces.a]\ndestino = "x@y"\nllave = "-i"\n',
                      '[enlaces.a]\ndestino = "x@y"\nextra = 1\n', '[enlace]\nverbos = ["bash"]\n', '[enlace]\nverbos = "ping"\n',
                      '[enlace]\nextra = 1\n'):
            with self.assertRaises(ErrorDeConfig, msg=texto):
                self.cargar(texto)


class DeExtremoAExtremo(ConPuerta):
    """El servidor llama y el laptop responde, con un ssh de mentira que hace lo que sshd con un comando
    forzado: ignora lo que pida el cliente y ejecuta `telar enlace servir` con lo pedido en el entorno."""

    def montar(self):
        bin_ = self.base / "bin"
        bin_.mkdir()
        # -i y -o llevan valor; después vienen el destino y la orden (un solo argumento)
        (bin_ / "ssh").write_text(
            '#!/bin/sh\nwhile [ "${1#-}" != "$1" ]; do shift 2; done\nshift\n'
            'SSH_ORIGINAL_COMMAND="$1" exec telar enlace servir\n')
        (bin_ / "telar").write_text(f'#!/bin/sh\nPYTHONPATH="{RAIZ / "src"}" exec "{sys.executable}" -m telar "$@"\n')
        for f in ("ssh", "telar"):
            (bin_ / f).chmod(0o755)
        llave = self.base / "llave"
        llave.write_text("no importa: el ssh de mentira no la usa")
        laptop = self.base / "laptop"
        cfg = laptop / "config.toml"
        laptop.mkdir()
        cfg.write_text(f'estado = "{laptop / "estado"}"\n[enlace]\nentrada = "{self.entrada}"\n')
        env = {"PATH": f"{bin_}:{os.environ['PATH']}", "HOME": str(self.base), "TELAR_CONFIG": str(cfg)}
        return Enlace(nombre="laptop", destino="nico@mac", llave=str(llave)), env

    def test_ping_archivo_y_notificar_pasan_por_la_puerta(self):
        enlace, env = self.montar()
        with mock.patch.dict(os.environ, env):
            r = m.llamar(enlace, "ping")
            self.assertTrue(r["ok"], r)
            r = m.llamar(enlace, "archivo", ["reporte.pdf"], b"%PDF contenido")
            self.assertTrue(r["ok"], r)
            self.assertEqual(Path(r["ruta"]).read_bytes(), b"%PDF contenido")
            self.assertEqual(Path(r["ruta"]).parent, self.entrada)

    def test_pedir_otra_cosa_es_un_no_aunque_el_cliente_lo_intente(self):
        enlace, env = self.montar()
        with mock.patch.dict(os.environ, env):
            for verbo, args in (("bash", ["-c", "touch /tmp/pwned-enlace"]), ("cat", ["/etc/passwd"])):
                r = m.llamar(enlace, verbo, args)
                self.assertFalse(r["ok"], verbo)
        self.assertFalse(Path("/tmp/pwned-enlace").exists())

    def test_sin_llave_o_con_la_otra_maquina_caida_se_dice(self):
        enlace, env = self.montar()
        r = m.llamar(Enlace(nombre="x", destino="a@b", llave=str(self.base / "no-existe")), "ping")
        self.assertFalse(r["ok"])
        self.assertIn("telar enlace instalar", r["error"])
        (self.base / "bin" / "ssh").write_text('#!/bin/sh\necho "Connection timed out" >&2\nexit 255\n')
        with mock.patch.dict(os.environ, env):
            r = m.llamar(enlace, "ping")
        self.assertFalse(r["ok"])
        self.assertIn("Connection timed out", r["error"])
