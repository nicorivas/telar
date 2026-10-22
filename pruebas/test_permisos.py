"""Permisos, primer paso (docs/propuestas/permisos.md): lo que un módulo pide (`[permisos]` en su modulo.toml, que
`telar modulos instalar` muestra antes de preguntar y nada hace cumplir todavía) y lo que un hilo espera de la
persona, como el objeto `permiso:<hilo>` de solo lectura."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import estado as mod_estado
from telar import modulos, objetos
from telar.agente.base import Evento
from telar.agente.claude_code import ClaudeCode
from telar.modelo import Atencion
from telar.servicios import ErrorDeServicio

BASE = """nombre = "eco"
descripcion = "repite lo que le dicen"

[ordenes.decir]
comando = ["bin/eco"]
"""

PIDE = BASE + """
[permisos]
leer = ["~/datos/oceano"]
escribir = ["~/.local/state/eco"]
red = ["psl.noaa.gov"]
ordenes = ["telar mensaje", "tipo  tarea", "mensaje"]
"""


def git(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


class LoQuePideUnModulo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "eco"
        (self.carpeta / "bin").mkdir(parents=True)
        (self.carpeta / "bin" / "eco").write_text("#!/bin/sh\necho eco\n")

    def leer(self, manifiesto: str):
        (self.carpeta / "modulo.toml").write_text(manifiesto)
        return modulos.leer("eco", self.carpeta)

    def test_se_lee_y_se_dice_en_palabras(self):
        m = self.leer(PIDE)
        self.assertEqual(m.permisos["leer"], ("~/datos/oceano",))
        self.assertEqual(m.permisos["red"], ("psl.noaa.gov",))
        # «telar mensaje» y «mensaje» son la misma orden; los espacios de más no cuentan
        self.assertEqual(m.permisos["ordenes"], ("mensaje", "tipo tarea"))
        self.assertEqual(m.pide, ["leer ~/datos/oceano", "escribir ~/.local/state/eco", "red: psl.noaa.gov",
                                  "órdenes de telar: mensaje, tipo tarea"])

    def test_sin_la_tabla_no_dice_y_vacia_no_pide_nada(self):
        # no decir qué pide no es lo mismo que no pedir nada
        m = self.leer(BASE)
        self.assertIsNone(m.permisos)
        self.assertIn("no dice qué pide", m.pide[0])
        self.assertEqual(self.leer(BASE + "\n[permisos]\n").pide, ["nada fuera de su carpeta"])
        self.assertEqual(self.leer(BASE + "\n[permisos]\nred = false\n").pide, ["nada fuera de su carpeta"])
        self.assertEqual(self.leer(BASE + "\n[permisos]\nred = true\n").pide, ["red: cualquier sitio"])

    def test_lo_mal_escrito_es_un_error_claro(self):
        for malo in ('leer = "~/datos"', "red = 3", 'red = ["", "x"]', "ordenes = [1]", 'escribir = [""]'):
            with self.subTest(malo=malo), self.assertRaises(modulos.ErrorDeModulo) as e:
                self.leer(BASE + f"\n[permisos]\n{malo}\n")
            self.assertIn("[permisos]", str(e.exception))
        with self.assertRaises(modulos.ErrorDeModulo):
            self.leer(BASE + '\npermisos = "todo"\n')

    def test_telar_solo_no_es_una_orden(self):
        with self.assertRaises(modulos.ErrorDeModulo) as e:
            self.leer(BASE + '\n[permisos]\nordenes = ["telar"]\n')
        self.assertIn("«telar» no es una orden", str(e.exception))

    def test_lo_mismo_en_otro_orden_pide_lo_mismo(self):
        # las mismas rutas en otro orden, o ningún sitio contra `false`, se leen igual (y actualizar no avisa)
        a = self.leer(BASE + '\n[permisos]\nleer = ["~/b", "~/a"]\nred = []\n')
        b = self.leer(BASE + '\n[permisos]\nleer = ["~/a", "~/b", "~/a"]\nred = false\n')
        self.assertEqual(a.permisos, b.permisos)
        self.assertEqual(a.pide, ["leer ~/a, ~/b"])

    def test_un_caracter_de_control_no_tapa_la_linea_del_si(self):
        # un ESC en lo que pide podría borrar la línea «pide:» antes de dar el sí: se muestra escapado
        m = self.leer(BASE + '\n[permisos]\nleer = ["\\u001b[2K\\u001b[1Aoculto"]\n"\\u001bclave" = 1\n')
        self.assertTrue(all("\x1b" not in x for x in m.pide), m.pide)
        self.assertIn("leer \\x1b[2K\\x1b[1Aoculto", m.pide)

    def test_una_clave_que_no_se_entiende_se_muestra_y_no_rompe(self):
        # un módulo escrito para un telar más nuevo se instala igual, y lo que pide no se calla
        m = self.leer(BASE + '\n[permisos]\nleer = ["~/a"]\nsecretos = ["gmail"]\ndesde = 2026-10-22\n')
        self.assertEqual(set(m.permisos["otros"]), {"secretos", "desde"})
        self.assertTrue(any("«secretos»" in x and "no lo entiende" in x for x in m.pide))
        j = modulos.permisos_json(m.permisos)
        self.assertEqual(j["otros"], {"secretos": ["gmail"], "desde": "2026-10-22"})
        json.dumps(j)  # una fecha de TOML no rompe el JSON


class InstalarLoMuestra(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "telar-eco"
        (self.repo / "bin").mkdir(parents=True)
        (self.repo / "bin" / "eco").write_text("#!/bin/sh\necho eco\n")
        (self.repo / "modulo.toml").write_text(PIDE)
        git(self.repo, "init", "-q", "-b", "main")
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            git(self.repo, "config", k, v)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "eco")
        self.conf = base / "conf"
        self.conf.mkdir()
        (self.conf / "config.toml").write_text(f'raiz = "{base}"\nestado = "{base / "estado"}"\n')
        entorno = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(base / "datos")})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.instalados = self.conf / modulos.INSTALADOS

    def orden(self, *argv: str) -> tuple[int, str]:
        from telar.ordenes import modulos as orden

        salida = io.StringIO()
        with mock.patch("sys.stdout", salida), mock.patch("sys.stdin", io.StringIO("")):
            codigo = orden.main(list(argv), SimpleNamespace(config=cfg.cargar(self.conf / "config.toml")))
        return codigo, salida.getvalue()

    def test_antes_de_preguntar_dice_lo_que_pide_y_que_no_se_hace_cumplir(self):
        # sin terminal y sin --si no se instala, pero lo que pide ya se vio
        codigo, texto = self.orden("instalar", str(self.repo))
        self.assertEqual(codigo, 1)
        self.assertIn("pide: leer ~/datos/oceano; escribir ~/.local/state/eco; red: psl.noaa.gov", texto)
        self.assertIn("todavía no lo hace cumplir", texto)
        self.assertLess(texto.index("pide:"), texto.index("repite con --si"))
        self.assertNotIn("eco", modulos.leer_instalados(self.instalados))
        codigo, texto = self.orden("instalar", str(self.repo), "--si")
        self.assertEqual(codigo, 0)
        self.assertIn("instalado eco", texto)

    def test_uno_que_no_lo_declara_se_instala_como_antes(self):
        (self.repo / "modulo.toml").write_text(BASE)
        git(self.repo, "commit", "-qam", "sin permisos")
        codigo, texto = self.orden("instalar", str(self.repo), "--si")
        self.assertEqual(codigo, 0)
        self.assertIn("pide: no dice qué pide", texto)

    def test_la_lista_lo_trae(self):
        self.orden("instalar", str(self.repo), "--si")
        _, texto = self.orden("--json")
        m = json.loads(texto)["modulos"][0]
        self.assertEqual(m["permisos"]["red"], ["psl.noaa.gov"])
        self.assertEqual(m["permisos"]["ordenes"], ["mensaje", "tipo tarea"])
        for campo in ("nombre", "carpeta", "descripcion", "aporta", "fuente", "version"):  # los de antes siguen
            self.assertIn(campo, m)
        _, texto = self.orden()
        self.assertIn("pide: leer ~/datos/oceano", texto)

    def test_actualizar_dice_si_cambio_lo_que_pide(self):
        self.orden("instalar", str(self.repo), "--si")
        self.assertNotIn("pide", modulos.actualizar(self.instalados, "eco"))  # igual: nada que decir
        (self.repo / "modulo.toml").write_text(PIDE.replace('red = ["psl.noaa.gov"]', "red = true"))
        git(self.repo, "commit", "-qam", "más red")
        linea = modulos.actualizar(self.instalados, "eco")
        self.assertIn("lo que pide cambió", linea)
        self.assertIn("red: cualquier sitio", linea)
        self.assertIn("(antes: ", linea)
        self.assertIn("red: psl.noaa.gov", linea)
        self.assertNotIn("pide", modulos.actualizar(self.instalados, "eco"))  # se compara con lo último que se vio

    def test_actualizar_no_avisa_lo_que_se_lee_igual(self):
        (self.repo / "modulo.toml").write_text(BASE + "\n[permisos]\nleer = [\"~/b\", \"~/a\"]\nred = false\n")
        git(self.repo, "commit", "-qam", "así")
        self.orden("instalar", str(self.repo), "--si")
        (self.repo / "modulo.toml").write_text(BASE + "\n[permisos]\nleer = [\"~/a\", \"~/b\"]\nred = []\n")
        git(self.repo, "commit", "-qam", "lo mismo, escrito de otra forma")
        self.assertNotIn("pide", modulos.actualizar(self.instalados, "eco"))

    def test_actualizar_uno_enlazado_tambien_avisa(self):
        # sin pull, la carpeta de antes y la de después son la misma: se compara con lo que se vio al instalarlo
        self.orden("instalar", str(self.repo), "--enlazar", "--si")
        self.assertTrue(modulos.leer_instalados(self.instalados)["eco"]["enlazado"])
        (self.repo / "modulo.toml").write_text(PIDE.replace('red = ["psl.noaa.gov"]', "red = true"))
        linea = modulos.actualizar(self.instalados, "eco")
        self.assertIn("lo que pide cambió: ", linea)
        self.assertIn("(antes: leer ~/datos/oceano", linea)

    def test_uno_anotado_por_un_telar_de_antes_compara_con_su_manifiesto(self):
        # modulos.toml de antes, sin `pide`: vale el manifiesto de antes del pull, y desde ahí queda anotado
        self.orden("instalar", str(self.repo), "--si")
        texto = self.instalados.read_text()
        self.instalados.write_text("\n".join(l for l in texto.split("\n") if not l.startswith("pide = ")))
        self.assertNotIn("pide", modulos.leer_instalados(self.instalados)["eco"])
        (self.repo / "modulo.toml").write_text(PIDE.replace('red = ["psl.noaa.gov"]', "red = true"))
        git(self.repo, "commit", "-qam", "más red")
        self.assertIn("lo que pide cambió", modulos.actualizar(self.instalados, "eco"))
        self.assertIn("red: cualquier sitio", modulos.leer_instalados(self.instalados)["eco"]["pide"])


class LaEsperaDeUnHilo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        self.config = cfg.Config(raiz=self.carpeta, estado=self.carpeta / "estado")
        self.est = mod_estado.abrir(self.config)
        claude = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.carpeta / "claude")
        self.addCleanup(lambda: os.environ.pop("CLAUDE_CONFIG_DIR", None) if claude is None
                        else os.environ.__setitem__("CLAUDE_CONFIG_DIR", claude))

    def correr(self, argv: list[str], entrada: str = "") -> str:
        from telar.cli import Contexto
        from telar.ordenes import agente as orden

        salida = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(entrada)), mock.patch("sys.stdout", salida):
            orden.main(argv, Contexto(config=self.config))
        return salida.getvalue()

    def test_el_gancho_trae_lo_que_pide(self):
        a = ClaudeCode(self.config).leer_aviso({"hook_event_name": "Notification", "notification_type": "permission_prompt",
                                                 "message": "Claude needs your permission to use Bash"})
        self.assertIs(a.evento, Evento.ESPERA)
        self.assertEqual((a.datos["pide"], a.datos["clase"]), ("Claude needs your permission to use Bash", "permiso"))
        a = ClaudeCode(self.config).leer_aviso({"hook_event_name": "Notification", "notification_type": "elicitation_dialog",
                                                 "message": "un MCP quiere saber"})
        self.assertEqual(a.datos["clase"], "pregunta")
        # el aviso de ocioso no es una espera, y no trae nada de esto
        a = ClaudeCode(self.config).leer_aviso({"hook_event_name": "Notification", "notification_type": "idle_prompt",
                                                 "message": "Claude is waiting"})
        self.assertNotIn("pide", a.datos)

    def test_la_espera_es_la_de_ahora_y_no_una_vieja(self):
        ahora = datetime.now().replace(microsecond=0)
        self.assertIsNone(self.est.espera("faro"))
        self.est.anotar_espera("faro", "  ¿borro\nla rama?  ", "pregunta", ahora - timedelta(minutes=5))
        self.est.anotar_atencion("faro", Atencion.ESPERA, ahora)
        # lo anotado es de una espera anterior, ya contestada: se sabe que espera, no qué
        self.assertEqual(self.est.espera("faro"), {"desde": ahora, "pide": "", "clase": ""})
        self.est.anotar_espera("faro", "  ¿borro\nla rama?  ", "pregunta", ahora - timedelta(seconds=1))
        self.assertEqual(self.est.espera("faro")["pide"], "¿borro la rama?")  # el mod avisó un poco después
        self.est.anotar_atencion("faro", Atencion.TRABAJANDO, ahora + timedelta(seconds=9))
        self.assertIsNone(self.est.espera("faro"))
        # un renombre se la lleva, y olvidar el hilo la borra
        self.est.anotar_atencion("faro", Atencion.ESPERA, ahora)
        self.est.renombrar("faro", "molino")
        self.assertEqual(self.est.espera("molino")["pide"], "¿borro la rama?")
        self.est.olvidar("molino")
        self.assertIsNone(self.est.espera("molino"))
        self.assertNotIn("molino", json.loads((self.carpeta / "estado" / "esperas.json").read_text()))

    def test_sin_desde_no_se_sabe_de_cual_espera(self):
        # un atencion.json viejo o escrito a mano, sin `desde`: lo anotado puede ser de cualquier espera anterior
        (self.carpeta / "estado").mkdir(parents=True, exist_ok=True)
        (self.carpeta / "estado" / "atencion.json").write_text('{"faro": {"atencion": "espera"}}')
        self.est.anotar_espera("faro", "viejo", "permiso", datetime(2020, 1, 1))
        self.assertEqual(self.est.espera("faro"), {"desde": None, "pide": "", "clase": ""})

    def test_lo_que_pide_es_una_linea_corta_y_sin_control(self):
        ahora = datetime.now().replace(microsecond=0)
        self.est.anotar_atencion("faro", Atencion.ESPERA, ahora)
        self.est.anotar_espera("faro", "x" * 1000, "permiso", ahora)
        self.assertEqual(len(self.est.espera("faro")["pide"]), mod_estado.TOPE_PIDE)
        self.est.anotar_espera("faro", "¿borro\x1b[2K la rama?", "permiso", ahora)
        self.assertEqual(self.est.espera("faro")["pide"], "¿borro\\x1b[2K la rama?")

    def test_un_esperas_roto_no_tumba_nada(self):
        # es un dato de más: roto, la espera sale sin el texto, y renombrar u olvidar el hilo siguen enteros
        ahora = datetime.now().replace(microsecond=0)
        self.est.anotar_atencion("faro", Atencion.ESPERA, ahora)
        roto = self.carpeta / "estado" / "esperas.json"
        roto.write_text("{roto")
        self.assertEqual(self.est.espera("faro"), {"desde": ahora, "pide": "", "clase": ""})
        self.est.renombrar("faro", "molino")
        self.assertIsNotNone(self.est.espera("molino"))
        self.assertIn("molino", json.loads((self.carpeta / "estado" / "atencion.json").read_text()))
        roto.write_text("{roto")
        self.est.olvidar("molino")
        self.assertIsNone(self.est.espera("molino"))
        roto.write_text("{roto")
        self.est.anotar_espera("ana", "¿subo?", "permiso", ahora)  # la siguiente escritura lo rehace
        self.assertEqual(json.loads(roto.read_text())["ana"]["pide"], "¿subo?")
        # los demás archivos del estado siguen avisando si están rotos
        (self.carpeta / "estado" / "atencion.json").write_text("{roto")
        with self.assertRaises(mod_estado.ErrorDeEstado):
            self.est.espera("ana")

    def test_el_aviso_lo_anota_aunque_avise_el_mod(self):
        from telar import casilla

        os.environ["TELAR_HILO"] = "faro"
        d = casilla.carpeta(self.config, "faro")
        d.mkdir(parents=True)
        (d / casilla.MOD).write_text("1")
        carga = json.dumps({"hook_event_name": "Notification", "notification_type": "permission_prompt",
                            "session_id": "s1", "message": "Claude needs your permission to use Bash"})
        self.assertEqual(json.loads(self.correr(["aviso", "--json"], carga))["motivo"], "lo avisa el mod")
        self.correr(["aviso", "--evento", "espera", "--sesion", "s1"])  # lo que dice el mod
        self.assertEqual(self.est.espera("faro")["pide"], "Claude needs your permission to use Bash")
        self.assertEqual(self.est.espera("faro")["clase"], "permiso")

    def test_cualquier_agente_lo_dice_con_pide(self):
        os.environ["TELAR_HILO"] = "faro"
        self.assertEqual(self.correr(["aviso", "--evento", "espera", "--pide", "¿subo la versión?"]), "")
        self.assertEqual(self.est.espera("faro")["pide"], "¿subo la versión?")
        # --pide con otro evento no anota nada
        self.correr(["aviso", "--evento", "termina", "--pide", "nada"])
        self.assertNotIn("nada", (self.carpeta / "estado" / "esperas.json").read_text())


class ElObjetoPermiso(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        self.config = cfg.Config(raiz=self.carpeta, estado=self.carpeta / "estado")
        self.ctx = SimpleNamespace(config=self.config)
        self.est = mod_estado.abrir(self.config)

    def hilo(self, atencion: str, **mas):
        from telar.ordenes import _comun

        j = {"nombre": "Faro", "relativa": "proyectos/faro", "atencion": atencion, "atencion_desde": "2026-10-22T10:00:00",
             **mas}
        tel = SimpleNamespace(hilos=[SimpleNamespace(nombre="Faro", id="@1", remoto="")])
        return mock.patch.object(_comun, "tejer", return_value=tel), mock.patch.object(_comun, "json_hilo", return_value=j)

    def test_lo_que_espera_un_hilo(self):
        desde = datetime(2026, 10, 22, 10, 0, 0)
        self.est.anotar_atencion("Faro", Atencion.ESPERA, desde)
        self.est.anotar_espera("Faro", "Claude needs your permission to use Bash", "permiso", desde)
        a, b = self.hilo("espera")
        with a, b:
            o = objetos.ver(self.ctx, "permiso:Faro")
            h = objetos.ver(self.ctx, "hilo:Faro")
        self.assertEqual((o.direccion, o.tipo, o.id, o.estado), ("permiso:Faro", "permiso", "Faro", "pendiente"))
        self.assertEqual(o.titulo, "Claude needs your permission to use Bash")
        self.assertEqual((o.campos["hilo"], o.campos["desde"], o.campos["clase"]), ("Faro", "2026-10-22T10:00:00", "permiso"))
        self.assertIn("telar ir Faro", o.campos["contestar"])
        self.assertEqual(o.enlaces, ["hilo:Faro", "proyecto:proyectos/faro"])
        self.assertEqual((o.acciones, o.version), ([], "2026-10-22T10:00:00"))
        # el hilo la nombra, para llegar a ella desde él
        self.assertIn("permiso:Faro", h.enlaces)

    def test_sin_texto_se_sabe_que_espera(self):
        self.est.anotar_atencion("Faro", Atencion.ESPERA, datetime(2026, 10, 22, 10, 0, 0))
        a, b = self.hilo("espera")
        with a, b:
            o = objetos.ver(self.ctx, "permiso:Faro")
        self.assertEqual((o.titulo, o.resumen), ("«Faro» te espera", ""))
        self.assertNotIn("pide", o.campos)

    def test_una_pregunta_sin_texto(self):
        self.est.anotar_atencion("Faro", Atencion.ESPERA, datetime(2026, 10, 22, 10, 0, 0))
        self.est.anotar_espera("Faro", "", "pregunta", datetime(2026, 10, 22, 10, 0, 0))
        a, b = self.hilo("espera")
        with a, b:
            o = objetos.ver(self.ctx, "permiso:Faro")
        self.assertEqual((o.titulo, o.resumen, o.campos["clase"]), ("«Faro» te pregunta algo", "", "pregunta"))

    def test_un_hilo_que_no_espera_no_tiene_permiso(self):
        a, b = self.hilo("trabajando")
        with a, b:
            with self.assertRaises(ErrorDeServicio) as e:
                objetos.ver(self.ctx, "permiso:Faro")
            self.assertEqual(e.exception.codigo, 404)
            self.assertIn("está trabajando", str(e.exception))
            self.assertNotIn("permiso:Faro", objetos.ver(self.ctx, "hilo:Faro").enlaces)

    def test_es_de_solo_lectura(self):
        a, b = self.hilo("espera")
        with a, b, self.assertRaises(ErrorDeServicio) as e:
            objetos.hacer(self.ctx, "permiso:Faro", "aprobar", {})
        self.assertEqual(e.exception.codigo, 404)
        self.assertIn("telar ir Faro", str(e.exception))

    def test_el_de_un_hilo_de_otra_maquina(self):
        # de allá se sabe que espera y desde cuándo (lo publica su dueño); lo que pide, solo allá
        from telar import bus as mod_bus
        from telar import espejo

        self.est.anotar_espera("Faro", "algo de aquí que no es de ese", "permiso")
        fotos = [{"nombre": "servidor", "hilos": [{"nombre": "Faro", "relativa": "proyectos/faro", "atencion": "espera",
                                                    "atencion_desde": "2026-10-22T09:00:00"}]}]
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(espejo, "leer_todos", return_value=fotos):
            o = objetos.ver(self.ctx, "permiso:Faro@servidor")
        self.assertEqual((o.direccion, o.maquina, o.campos["desde"]), ("permiso:Faro@servidor", "servidor", "2026-10-22T09:00:00"))
        self.assertEqual(o.enlaces[0], "hilo:Faro@servidor")
        self.assertNotIn("pide", o.campos)

    def test_es_un_tipo_de_fabrica_y_se_encuentra_en_un_texto(self):
        self.assertIn("permiso", objetos.tipos(self.ctx))
        self.assertEqual([str(d) for d in objetos.buscar(self.ctx, "mira permiso:Faro, que espera")], ["permiso:Faro"])
        from telar.ordenes import objeto as orden

        salida = io.StringIO()
        with mock.patch("sys.stdout", salida):
            orden.main(["--tipos", "--json"], self.ctx)
        self.assertIn("permiso", [t["tipo"] for t in json.loads(salida.getvalue())["tipos"]])


if __name__ == "__main__":  # pragma: no cover
    import unittest

    unittest.main()
