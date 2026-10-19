"""El correo entre agentes y telar en el celular: lo que decide, sin ssh ni tmux."""

from __future__ import annotations

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import correo as c
from telar import movil as m
from telar import remoto as r
from telar.config import Remoto

CASA = Remoto(nombre="casa", destino="usuario@servidor")


def correo(id="", asunto="", responde="", referencias=(), para="usuario@servidor", fecha="", estado=""):
    return c.Correo(archivo="", id=id, de="otro", para=para, asunto=asunto, fecha=fecha,
                    responde=responde, referencias=tuple(referencias), estado=estado)


class Direcciones(Prueba):
    def test_la_extension_de_un_nombre(self):
        self.assertEqual(c.extension("T42 Faro Norte"), "t42-faro-norte")
        self.assertEqual(c.extension("Pizza Ñandú"), "pizza-nandu")
        self.assertEqual(c.extension("  ◷ 16:00 reunión  "), "16-00-reunion")
        self.assertEqual(c.extension("⇄"), "")

    def test_la_direccion_de_un_hilo(self):
        self.assertEqual(c.direccion(CASA, "Pizza"), "usuario+pizza@servidor")
        self.assertEqual(c.direccion(CASA, "⇄"), "usuario@servidor")
        self.assertEqual(c.direccion(Remoto("casa", "alias"), "Pizza"), "")  # un alias no dice el usuario

    def test_la_extension_de_una_direccion(self):
        self.assertEqual(c.extension_de("<usuario+pizza@servidor>"), "pizza")
        self.assertEqual(c.extension_de("usuario@servidor"), "")


class MovilNuevoHilo(Prueba):
    def test_el_hilo_nuevo_nace_como_los_remotos(self):
        orden = m.ordenes_nuevo("telar-9f9f9f9f", "Kinross", "/home/n/Life", ["claude", "--session-id", "x"])
        self.assertEqual(orden[:6], ["new-session", "-d", "-s", "telar-9f9f9f9f", "-c", "/home/n/Life"])
        linea = orden[-1]
        # se anota su nombre (lo leen el cartero y la lista), va a su carpeta y abre el agente
        self.assertIn("@telar_hilo Kinross", linea)
        self.assertIn("export TELAR_HILO=Kinross", linea)
        self.assertIn("claude --session-id x", linea)
        self.assertTrue(linea.endswith("exec bash -l"))


class NombreEnLaSesionRemota(Prueba):
    def test_la_sesion_de_alla_se_anota_su_nombre_desde_adentro(self):
        linea = r.linea("~/repo", None, "Pizza Ñandú")
        self.assertTrue(linea.startswith(f"tmux set-option {r.OPCION_HILO} 'Pizza Ñandú'"))
        # y el comando que viaja por mosh no encadena nada
        self.assertNotIn(";", r.comando(CASA, "telar-1a2b", linea))


class Enviar(Prueba):
    def enviar(self, direccion, asunto="hola", responde=""):
        from types import SimpleNamespace

        from telar.config import Config
        from telar.ordenes import correo as orden

        ctx = SimpleNamespace(config=Config(remotos=(CASA,)))
        return orden.enviar(ctx, direccion, asunto, "cuerpo", responde=responde)

    def test_lo_que_va_en_cabeceras_no_trae_saltos_de_linea(self):
        self.assertIn("una sola línea", self.enviar("otro@servidor", asunto="hola\nBcc: x@servidor")[1])
        self.assertIn("Message-Id", self.enviar("otro@servidor", responde="<a@b>\nX: y")[1])
        self.assertIn("no es una dirección", self.enviar("otro@servidor -f alguien")[1])

    def test_una_maquina_que_no_esta_en_remotos_no_se_adivina(self):
        from unittest import mock

        from telar.ordenes import agente as orden_agente

        with mock.patch.object(orden_agente, "_cartero_aqui", return_value=False):
            self.assertIn("no sé cómo llegar", self.enviar("otro@lejos")[1])


class Directorio(Prueba):
    def test_el_lector_descarta_un_archivo_que_no_es_de_su_dueno(self):
        import getpass
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        from telar import directorio as d

        yo = getpass.getuser()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, f"{yo}.json").write_text(json.dumps({"usuario": yo, "hilos": []}), encoding="utf-8")
            Path(tmp, "otra.json").write_text(json.dumps({"usuario": "otra", "hilos": []}), encoding="utf-8")
            salida = json.loads(subprocess.run([sys.executable, "-c", d.LEER, tmp], capture_output=True,
                                               text=True, check=True).stdout)
        por = {e["usuario"]: e for e in salida}
        self.assertNotIn("error", por[yo])
        self.assertIn("se descarta", por["otra"]["error"])  # lo escribí yo con el nombre de otra
