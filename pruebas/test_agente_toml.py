"""El agente como definición: el `agente.toml` de un residente (telar.agentes, docs/propuestas/agente-como-definicion.md).

Sin el archivo todo es como antes; con él, `nombre`, `para`, `modelo` y `residente` valen donde ya había algo que
los usara, y lo que viene mal se ignora con aviso, sin apagar al agente."""

from __future__ import annotations

import io
import json
import shlex
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agentes as m
from telar import config as mod_config
from telar import objetos
from telar.agente import lanzar
from telar.agente.base import AgenteBase
from telar.agente.claude_code import ClaudeCode


def _cli(config, *argv) -> tuple[int, str, str]:
    from telar import cli

    salida, error = io.StringIO(), io.StringIO()
    with mock.patch.object(cli, "cargar_config", return_value=config), redirect_stdout(salida), redirect_stderr(error):
        codigo = cli.main(list(argv))
    return codigo, salida.getvalue(), error.getvalue()


class ConAgentes(Prueba):
    """Dos residentes, faro y cronista; `definir` le escribe un agente.toml a uno."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        for clave, titulo in (("faro", "# Faro\n"), ("cronista", "# Cronista\n")):
            d = self.raiz / "agentes" / clave
            d.mkdir(parents=True)
            (d / "CLAUDE.md").write_text(f"# {clave}\n\nEres {clave}.\n")
            (d / "README.md").write_text(titulo)
        self.config = mod_config.Config(raiz=self.raiz, estado=self.raiz / ".estado", agentes_carpeta="agentes")

    def definir(self, clave: str, texto: str) -> None:
        (self.raiz / "agentes" / clave / "agente.toml").write_text(texto, encoding="utf-8")

    def agente(self, clave: str, config=None) -> m.Agente:
        return next(a for a in m.descubrir(config or self.config) if a.clave == clave)


class SinArchivo(ConAgentes):
    def test_todo_como_antes(self):
        faro = self.agente("faro")
        self.assertEqual((faro.nombre, faro.para, faro.modelo, faro.residente, faro.definicion, faro.problemas),
                         ("Faro", "", "", True, None, ()))
        self.assertEqual(faro.nombre_de_antes, "Faro")
        self.assertEqual(m.argumentos_de(faro, ClaudeCode(self.config)), [])

    def test_un_archivo_vacio_vale_lo_mismo_que_no_tenerlo(self):
        self.definir("faro", "# nada todavía\n")
        faro = self.agente("faro")
        self.assertEqual((faro.nombre, faro.modelo, faro.residente, faro.problemas), ("Faro", "", True, ()))
        self.assertIsNotNone(faro.definicion)


class LoQueDeclara(ConAgentes):
    def test_nombre_para_modelo_residente_y_lo_que_no_se_usa_todavia(self):
        self.definir("faro", 'nombre = "Lámpara"\npara = """La luz y\n  el turno de noche."""\nmodelo = "opus"\n'
                             'residente = false\ninstrucciones = "CLAUDE.md"\n[politica]\npermisos = "acceptEdits"\n')
        faro = self.agente("faro")
        self.assertEqual((faro.nombre, faro.para, faro.modelo, faro.residente),
                         ("Lámpara", "La luz y el turno de noche.", "opus", False))
        self.assertEqual(faro.hilos[0], "Lámpara")
        self.assertEqual(faro.nombre_de_antes, "Faro")
        self.assertEqual(faro.sin_uso, {"instrucciones": "CLAUDE.md", "politica": {"permisos": "acceptEdits"}})
        self.assertEqual(faro.problemas, ())

    def test_un_toml_que_no_se_lee_se_ignora_entero_y_el_agente_sigue(self):
        self.definir("faro", 'nombre = "Lámpara"\nmodelo = \n')
        faro = self.agente("faro")
        self.assertEqual((faro.nombre, faro.modelo), ("Faro", ""))
        self.assertEqual(len(faro.problemas), 1)
        self.assertIn("se ignora entero", faro.problemas[0])

    def test_un_campo_mal_se_ignora_solo_y_una_clave_desconocida_avisa(self):
        self.definir("faro", 'nombre = "Lámpara"\nmodelo = "--dangerously"\nresidente = "si"\nmemoria = "x"\n'
                             'colores = ["azul"]\n')
        faro = self.agente("faro")
        self.assertEqual((faro.nombre, faro.modelo, faro.residente, faro.sin_uso), ("Lámpara", "", True, {}))
        dice = " ".join(faro.problemas)
        for palabra in ("modelo", "residente", "memoria", "colores", "más nuevo"):
            self.assertIn(palabra, dice)

    def test_un_para_largo_vale_con_aviso(self):
        self.definir("faro", f'para = "{"palabra " * 60}"\n')
        faro = self.agente("faro")
        self.assertTrue(faro.para.startswith("palabra"))
        self.assertIn("una o dos frases", faro.problemas[0])

    def test_dos_con_el_mismo_nombre_no_se_vuelven_un_hilo(self):
        # el de una carpeta que viene después también cuenta: faro no le puede quitar el nombre a cronista
        self.definir("faro", 'nombre = "Cronista"\n')
        self.definir("cronista", 'nombre = "faro"\n')
        cronista, faro = self.agente("cronista"), self.agente("faro")
        self.assertEqual((cronista.nombre, faro.nombre), ("Cronista", "Faro"))
        self.assertIn("ya es de otro agente", faro.problemas[0])
        self.assertIn("ya es de otro agente", cronista.problemas[0])


class ElModelo(ConAgentes):
    def test_claude_code_lo_pasa_con_model_y_un_motor_que_no_sabe_lo_ignora(self):
        self.definir("faro", 'modelo = "opus"\n')
        faro = self.agente("faro")
        self.assertEqual(m.argumentos_de(faro, ClaudeCode(self.config)), ["--model", "opus"])
        self.assertEqual(AgenteBase.con_modelo(object(), "opus"), [])
        self.assertEqual(m.argumentos_de(faro, None), [])

    def test_los_argumentos_de_la_maquina_van_despues_y_ganan_si_ya_traen_el_modelo(self):
        self.definir("faro", 'modelo = "opus"\n')
        extra = mod_config.AgenteExtra(clave="faro", argumentos=("--permission-mode", "acceptEdits"))
        cfg = mod_config.Config(raiz=self.raiz, agentes_carpeta="agentes", agentes_extra=(extra,))
        self.assertEqual(m.argumentos_de(self.agente("faro", cfg), ClaudeCode(cfg)),
                         ["--model", "opus", "--permission-mode", "acceptEdits"])
        extra = mod_config.AgenteExtra(clave="faro", argumentos=("--model", "haiku"))
        cfg = mod_config.Config(raiz=self.raiz, agentes_carpeta="agentes", agentes_extra=(extra,))
        self.assertEqual(m.argumentos_de(self.agente("faro", cfg), ClaudeCode(cfg)), ["--model", "haiku"])
        self.assertEqual(m.argumentos_de(self.agente("faro", cfg), ClaudeCode(cfg), con_config=False), [])

    def _lanzar(self, carpeta):
        motor = SimpleNamespace(conversaciones=lambda hilo: [],
                                nuevo_con_id=lambda mensaje="", id="": (["claude", "--session-id", "s1", *([mensaje] if mensaje else [])], "s1"),
                                con_modelo=lambda modelo: ["--model", modelo])
        cfg = mod_config.Config(raiz=self.raiz, agentes_carpeta="agentes",
                                agente=mod_config.Agente(nombre="claude-code", carpeta="hilo"))
        with mock.patch("telar.agente.lanzar.mod_agente.obtener", return_value=motor):
            return lanzar.para_hilo(cfg, "Faro", carpeta, mensaje="hola")

    def test_el_hilo_del_residente_abre_con_su_modelo_y_un_proyecto_no(self):
        self.definir("faro", 'modelo = "opus"\n')
        casa = self.raiz / "agentes" / "faro"
        self.assertIn("--model opus", self._lanzar(casa).comando[2])
        (casa / "obra").mkdir()
        self.assertNotIn("--model", self._lanzar(casa / "obra").comando[2])
        (casa / "agente.toml").unlink()
        self.assertNotIn("--model", self._lanzar(casa).comando[2])

    def test_al_abrir_su_sesion_por_un_encargo(self):
        from telar import encargos

        self.definir("faro", 'modelo = "opus"\n')
        cfg = mod_config.Config(raiz=self.raiz, estado=self.raiz / ".estado", agentes_carpeta="agentes",
                                agente=mod_config.Agente(nombre="claude-code", carpeta="hilo"))
        abiertos = []
        with mock.patch("telar.movil.crear", side_effect=lambda nombre, carpeta, comando, sesion:
                        abiertos.append(comando) or SimpleNamespace(direccion="telar-faro")), \
                mock.patch("telar.encargos.liberar", return_value=[]):
            encargos._abrir(SimpleNamespace(config=cfg), self.agente("faro", cfg), "revisa la lámpara")
        self.assertIn("'revisa la lámpara' --model opus", abiertos[0][2])


class Residente(ConAgentes):
    def _locales(self):
        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx, n.config, n.yo = SimpleNamespace(config=self.config), self.config, "laptop"
        estado = SimpleNamespace(remotos=lambda: {}, atenciones=lambda: {}, sesiones=lambda: {},
                                 vinculos=lambda: {}, archivados=lambda: set())
        tel = SimpleNamespace(estado=estado, hilos=[])
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.movil.propios", return_value={}), mock.patch("telar.movil.ventanas", return_value=[]):
            return n.locales()

    def test_el_nodo_publica_residente_solo_si_lo_es(self):
        self.definir("faro", "residente = false\n")
        locales = self._locales()
        self.assertEqual(locales["Faro"]["residente"], "")
        self.assertEqual(locales["Cronista"]["residente"], "cronista")


class LaOrden(ConAgentes):
    def test_la_lista_en_json_y_en_texto(self):
        self.definir("faro", 'para = "La luz."\nmodelo = "opus"\nresidente = false\n')
        codigo, salida, _ = _cli(self.config, "agentes", "--json")
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)["agentes"]
        self.assertEqual([a["clave"] for a in datos], ["cronista", "faro"])
        faro = datos[1]
        self.assertEqual({k: faro[k] for k in ("nombre", "direccion", "para", "modelo", "residente", "problemas")},
                         {"nombre": "Faro", "direccion": "agente:faro", "para": "La luz.", "modelo": "opus",
                          "residente": False, "problemas": []})
        self.assertEqual(datos[0]["definicion"], "")
        codigo, salida, _ = _cli(self.config, "agentes")
        self.assertIn("opus · no residente", salida)
        self.assertIn("    La luz.", salida)

    def test_una_fecha_de_toml_en_lo_que_no_se_usa_sale_como_texto(self):
        self.definir("faro", "[memoria]\ndesde = 2026-10-01\n")
        codigo, salida, _ = _cli(self.config, "agentes", "faro", "--json")
        self.assertEqual((codigo, json.loads(salida)["sin_uso"]), (0, {"memoria": {"desde": "2026-10-01"}}))

    def test_uno_entero_y_uno_que_no_existe(self):
        self.definir("faro", 'nombre = "Lámpara"\n[lugar]\npor_defecto = "."\n')
        codigo, salida, _ = _cli(self.config, "agentes", "Lámpara")
        self.assertEqual(codigo, 0)
        self.assertIn("sin agente.toml sería «Faro»", salida)
        self.assertIn("declarado, sin uso todavía", salida)
        codigo, _, error = _cli(self.config, "agentes", "nadie")
        self.assertEqual(codigo, 2)
        self.assertIn("cronista, faro", error)

    def test_sin_agentes(self):
        codigo, salida, _ = _cli(mod_config.Config(raiz=self.raiz), "agentes", "--json")
        self.assertEqual((codigo, json.loads(salida)), (0, {"agentes": []}))


class ElObjeto(ConAgentes):
    def test_agente_se_ve_por_su_carpeta_o_su_nombre(self):
        self.definir("faro", 'para = "La luz."\nmodelo = "opus"\n')
        ctx = SimpleNamespace(config=self.config)
        o = objetos.ver(ctx, "agente:faro")
        self.assertEqual((o.direccion, o.titulo, o.estado, o.resumen, o.campos["modelo"], o.enlaces),
                         ("agente:faro", "Faro", "residente", "La luz.", "opus", ["hilo:Faro"]))
        self.assertEqual(objetos.ver(ctx, "agente:Faro").id, "faro")
        self.assertEqual([a.nombre for a in o.acciones], ["encargar"])
        self.assertIn("agente", objetos.tipos(ctx))

    def test_encargar_pasa_por_el_servicio_de_siempre(self):
        from telar.servicios import encargos
        from telar.servicios import ErrorDeServicio

        ctx = SimpleNamespace(config=self.config)
        with mock.patch.object(encargos, "encargar", return_value=encargos.Encargo(hilo="Faro", estado="entregado")) as e:
            h = objetos.hacer(ctx, "agente:Faro", "encargar", {"texto": "mira la lámpara"})
        e.assert_called_once_with(ctx, "faro", "mira la lámpara")
        self.assertEqual(h.resultado["estado"], "entregado")
        with self.assertRaises(ErrorDeServicio):
            objetos.hacer(ctx, "agente:faro", "encargar", {"texto": " "})
        with self.assertRaises(ErrorDeServicio):
            objetos.ver(ctx, "agente:nadie")


class LoQueVenLosDemas(ConAgentes):
    def test_el_home_dice_para_que_es_arriba_y_enlaza_su_definicion(self):
        from telar.ordenes.seccion import validar

        sin = m.pagina(self.agente("faro"))
        self.assertNotIn("para", [b.get("titulo") for b in sin["bloques"]])
        self.definir("faro", 'para = "La luz."\n')
        p = m.pagina(self.agente("faro"))
        self.assertEqual(validar(p), "")
        self.assertEqual(p["bloques"][0], {"titulo": "para", "texto": "La luz."})
        archivos = next(b for b in p["bloques"] if b.get("titulo") == "archivos")["items"]
        self.assertIn("agente.toml: su definición", [x["titulo"] for x in archivos])

    def test_el_contexto_de_arranque_dice_donde_leer_para_que_es_cada_uno(self):
        from telar.ordenes import agente as orden

        ctx = SimpleNamespace(config=self.config)
        self.assertNotIn("telar agentes", orden._agentes_en_contexto(ctx))
        self.definir("faro", 'para = "La luz."\n')
        linea = orden._agentes_en_contexto(ctx)
        self.assertIn("Agentes residentes (Cronista, Faro)", linea)
        self.assertIn("para qué es cada uno: `telar agentes`", linea)
        self.assertNotIn("La luz.", linea)


class ElDoctor(ConAgentes):
    def _revisar(self, sesiones=None):
        from telar.ordenes import doctor

        est = SimpleNamespace(sesiones=lambda: sesiones or {})
        with mock.patch("telar.ordenes.doctor.mod_estado.abrir", return_value=est):
            return doctor._agentes(SimpleNamespace(config=self.config))

    def test_sin_agentes_no_dice_nada_y_con_ellos_ok(self):
        from telar.ordenes import doctor

        self.assertEqual(doctor._agentes(SimpleNamespace(config=mod_config.Config(raiz=self.raiz))), [])
        self.definir("faro", 'modelo = "opus"\n')
        r = self._revisar()
        self.assertEqual([(x["estado"], x["dice"]) for x in r], [("ok", "Cronista, Faro (1 con agente.toml)")])

    def test_lo_que_no_se_leyo_es_un_aviso_con_su_arreglo(self):
        self.definir("faro", 'modelo = 3\n')
        r = self._revisar()
        self.assertEqual([x["estado"] for x in r], ["aviso"])
        self.assertIn("faro/agente.toml: modelo", r[0]["dice"])
        self.assertIn("agente.toml", r[0]["arreglo"])

    def test_un_nombre_nuevo_que_deja_su_conversacion_con_el_de_antes(self):
        self.definir("faro", 'nombre = "Lámpara"\n')
        r = self._revisar({"Faro": ["s1"]})
        self.assertEqual([x["estado"] for x in r], ["aviso"])
        self.assertEqual(r[0]["arreglo"], f"telar hilo renombrar {shlex.quote('Lámpara')} --hilo Faro")
        self.assertEqual([x["estado"] for x in self._revisar({"Lámpara": ["s1"]})], ["ok"])


class ElEjemplo(Prueba):
    def test_el_taller_trae_un_residente_con_su_definicion(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / "taller"
            shutil.copytree(EJEMPLO, raiz)
            cfg = mod_config.Config(raiz=raiz, agentes_carpeta="agentes")
            [vigia] = m.descubrir(cfg)
            self.assertEqual((vigia.clave, vigia.nombre, vigia.modelo, vigia.residente, vigia.problemas),
                             ("vigia", "Vigía", "sonnet", True, ()))
            self.assertTrue(vigia.para)
            self.assertEqual(vigia.nombre, vigia.nombre_de_antes)
