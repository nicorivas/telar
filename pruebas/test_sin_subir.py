"""Lo que no es la conversación al llevar un hilo (telar.sin_subir, y el registro y la casilla de telar.mudanza):
lo sin subir de sus repositorios, que se sube (solo lo suyo) o se lleva igual; el repositorio de allá al día antes de
abrir; y su padre, sus etiquetas, su prioridad y su casilla, que viajan con él.

Los repositorios son de verdad (git, en una carpeta temporal): un «origen» desnudo, el clon de aquí y el de allá."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import casilla, mudanza, sin_subir
from telar import estado as mod_estado


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x",
                            "GIT_COMMITTER_NAME": "Ana", "GIT_COMMITTER_EMAIL": "ana@x"})
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout.strip()


def edicion(ruta: Path | str, herramienta: str = "Edit") -> bytes:
    """Una línea de conversación de Claude Code en que el agente escribe `ruta`."""
    clave = "notebook_path" if herramienta == "NotebookEdit" else "file_path"
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_1", "name": herramienta, "input": {clave: str(ruta), "old_string": "a"}}]}}).encode() + b"\n"


class _Repos(Prueba):
    """Una raíz (aquí y allá) con un proyecto `proyecto/` que es un clon de un origen común."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name).resolve()
        self.origen = d / "origen.git"
        git(d, "init", "-q", "--bare", "-b", "main", str(self.origen))
        semilla = d / "semilla"
        git(d, "clone", "-q", str(self.origen), str(semilla))
        (semilla / "a.txt").write_text("a\n")
        (semilla / "b.txt").write_text("b\n")
        git(semilla, "add", "-A")
        git(semilla, "commit", "-q", "-m", "primero")
        git(semilla, "push", "-q", "origin", "HEAD:main")
        self.raiz, self.raiz_alla = d / "aqui", d / "alla"
        for r in (self.raiz, self.raiz_alla):
            r.mkdir()
            git(r, "clone", "-q", str(self.origen), "proyecto")
            for k, v in (("user.name", "Ana"), ("user.email", "ana@x")):
                git(r / "proyecto", "config", k, v)
        self.repo, self.repo_alla = self.raiz / "proyecto", self.raiz_alla / "proyecto"
        self.config = SimpleNamespace(raiz=str(self.raiz), estado=str(d / "estado"))
        self.ctx_alla = SimpleNamespace(config=SimpleNamespace(raiz=str(self.raiz_alla), estado=str(d / "estado-alla")))
        self.conversacion = d / "c.jsonl"
        self.conversacion.write_bytes(b'{"type":"user"}\n')

    def escribio(self, *rutas: Path, herramienta: str = "Edit") -> None:
        with self.conversacion.open("ab") as f:
            for r in rutas:
                f.write(edicion(r, herramienta))

    def revisar(self, carpeta: Path | None = None) -> dict:
        return sin_subir.revisar(self.config, carpeta if carpeta is not None else self.repo, self.conversacion, "sid")


class LoQueSeMiraAntes(_Repos):
    def test_nada_sin_subir_no_pregunta(self):
        p = self.revisar()
        self.assertFalse(sin_subir.hay_algo(p))
        (r,) = p["repos"]
        self.assertEqual((r["relativa"], r["rama"], r["arriba"]), ("proyecto", "main", "origin/main"))
        self.assertEqual(r["commit"], git(self.repo, "rev-parse", "HEAD"))

    def test_lo_que_escribio_su_conversacion_es_suyo_y_lo_demas_de_su_carpeta_no(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        (self.repo / "nuevo.md").write_text("nuevo\n")
        (self.repo / "generado.png").write_text("lo hizo un programa\n")
        self.escribio(self.repo / "a.txt")
        self.escribio(self.repo / "nuevo.md", herramienta="Write")
        p = self.revisar()
        (r,) = p["repos"]
        self.assertEqual(r["del_hilo"], ["a.txt", "nuevo.md"])
        self.assertEqual(r["en_su_carpeta"], ["generado.png"], "no sé si es suyo: se muestra y no se sube")
        self.assertTrue(r["pendiente"] and r["puede_subir"])
        self.assertTrue(sin_subir.hay_algo(p) and sin_subir.se_puede_subir(p))

    def test_sin_nada_que_diga_que_es_suyo_no_se_ofrece_subir(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        p = self.revisar()
        self.assertEqual(p["repos"][0]["en_su_carpeta"], ["a.txt"])
        self.assertTrue(sin_subir.hay_algo(p))
        self.assertFalse(sin_subir.se_puede_subir(p))

    def test_lo_de_otros_en_la_raiz_no_se_mira(self):
        # el hilo vive en una subcarpeta: lo sin commitear del resto del repositorio no es suyo ni lo detiene
        (self.repo / "sub").mkdir()
        (self.repo / "otro.txt").write_text("de otro hilo\n")
        p = self.revisar(self.repo / "sub")
        self.assertFalse(sin_subir.hay_algo(p))

    def test_sin_carpeta_solo_lo_que_escribio(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        (self.repo / "b.txt").write_text("de otro\n")
        self.escribio(self.repo / "a.txt")
        p = sin_subir.revisar(self.config, None, self.conversacion, "sid")
        (r,) = [x for x in p["repos"] if x["pendiente"]]
        self.assertEqual((r["del_hilo"], r["en_su_carpeta"]), (["a.txt"], []))

    def test_tambien_lo_que_escribieron_sus_subagentes(self):
        (self.repo / "b.txt").write_text("de un subagente\n")
        sub = self.conversacion.parent / "sid" / "subagents" / "agent-1.jsonl"
        sub.parent.mkdir(parents=True)
        sub.write_bytes(edicion(self.repo / "b.txt", "MultiEdit"))
        self.assertEqual(self.revisar()["repos"][0]["del_hilo"], ["b.txt"])

    def test_una_ruta_del_servidor_en_su_conversacion(self):
        # la conversación siguió en otra máquina: nombra /home/ana/…, que aquí es el hogar de aquí
        (self.repo / "a.txt").write_text("cambiado\n")
        casa = self.raiz.parent
        with mock.patch.object(Path, "home", return_value=casa):
            self.escribio(Path("/home/ana") / self.repo.relative_to(casa) / "a.txt")
            self.assertEqual(self.revisar()["repos"][0]["del_hilo"], ["a.txt"])

    def test_commits_sin_subir_y_otro_repositorio_que_escribio(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        git(self.repo, "commit", "-qam", "local")
        otro = self.raiz / "otro"
        git(self.raiz, "init", "-q", "-b", "main", "otro")
        (otro / "x.md").write_text("x\n")
        self.escribio(otro / "x.md")
        p = self.revisar()
        principal, segundo = p["repos"]
        self.assertEqual((principal["n_commits"], principal["commits"][0].split(" ", 1)[1]), (1, "local"))
        self.assertTrue(principal["puede_subir"])
        self.assertEqual((segundo["relativa"], segundo["del_hilo"]), ("otro", ["x.md"]))
        self.assertFalse(segundo["puede_subir"])
        self.assertIn("no tiene una de arriba", segundo["por_que_no"])
        lineas = sin_subir.lineas(p)
        self.assertTrue(any("1 commit sin subir" in x for x in lineas), lineas)
        self.assertTrue(any("no se puede subir" in x for x in lineas), lineas)

    def test_un_repositorio_de_adentro_no_cuenta(self):
        git(self.repo, "init", "-q", "-b", "main", "anidado")
        (self.repo / "anidado" / "y.txt").write_text("y\n")
        self.assertFalse(sin_subir.hay_algo(self.revisar()))


class SubirYLlevar(_Repos):
    def test_commitea_solo_lo_suyo_y_lo_sube(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        (self.repo / "generado.png").write_text("de un programa\n")
        (self.repo / "b.txt").write_text("de otro hilo\n")
        self.escribio(self.repo / "a.txt")
        ok, texto = sin_subir.subir(self.config, self.revisar(), "Faro", "servidor")
        self.assertTrue(ok, texto)
        self.assertIn("subido", texto)
        self.assertEqual(git(self.origen, "log", "-1", "--format=%s"), "Faro: lo suyo sin commitear, antes de llevarlo a servidor")
        self.assertEqual(git(self.origen, "show", "--name-only", "--format=", "main"), "a.txt")
        sucios = git(self.repo, "status", "--porcelain")
        self.assertIn("b.txt", sucios)
        self.assertIn("generado.png", sucios)
        registro = (Path(self.config.estado) / "commits.log").read_text()
        self.assertIn("Faro", registro)

    def test_si_no_sube_lo_dice_y_no_se_lleva(self):
        (self.repo / "a.txt").write_text("cambiado\n")
        self.escribio(self.repo / "a.txt")
        p = self.revisar()
        git(self.repo, "remote", "set-url", "origin", str(self.origen.parent / "no-existe.git"))
        ok, texto = sin_subir.subir(self.config, p, "Faro", "servidor")
        self.assertFalse(ok)
        self.assertIn("quedó aquí", texto)


class AllaAlDia(_Repos):
    def adelantar(self, n: int = 3) -> None:
        for i in range(n):
            (self.repo / "a.txt").write_text(f"{i}\n")
            git(self.repo, "commit", "-qam", f"aquí {i}")
        git(self.repo, "push", "-q")

    def test_alla_va_atras_y_al_llegar_se_pone_al_dia(self):
        self.adelantar(3)
        repos = [{"relativa": "proyecto", "commit": git(self.repo, "rev-parse", "HEAD"), "nombre": "proyecto"}]
        self.assertEqual(sin_subir.en_destino(self.ctx_alla, repos), [{"relativa": "proyecto", "existe": True, "tiene": False}])
        (self.repo_alla / "suelto.txt").write_text("sin commitear allá, no estorba\n")
        avisos = sin_subir.al_dia(self.ctx_alla, repos)
        self.assertEqual(avisos, ["proyecto: llegaron 3 commits de arriba"])
        self.assertEqual(git(self.repo_alla, "rev-parse", "HEAD"), repos[0]["commit"])
        self.assertTrue((self.repo_alla / "suelto.txt").exists())
        self.assertEqual(sin_subir.en_destino(self.ctx_alla, repos)[0]["tiene"], True)
        self.assertEqual(sin_subir.al_dia(self.ctx_alla, repos), [], "al día: nada que decir")

    def test_si_lo_que_llega_toca_lo_sin_commitear_de_alla_lo_dice(self):
        self.adelantar(1)
        (self.repo_alla / "a.txt").write_text("a medias allá\n")
        repos = [{"relativa": "proyecto", "commit": git(self.repo, "rev-parse", "HEAD"), "nombre": "proyecto"}]
        (aviso,) = sin_subir.al_dia(self.ctx_alla, repos)
        self.assertIn("sigue atrás", aviso)
        self.assertIn("a.txt", aviso)
        self.assertEqual((self.repo_alla / "a.txt").read_text(), "a medias allá\n", "lo de allá, intacto")

    def test_lo_que_aqui_no_se_subio_alla_no_llega_y_se_dice(self):
        (self.repo / "a.txt").write_text("local\n")
        git(self.repo, "commit", "-qam", "sin subir")
        repos = [{"relativa": "proyecto", "commit": git(self.repo, "rev-parse", "HEAD"), "nombre": "proyecto"}]
        (aviso,) = sin_subir.al_dia(self.ctx_alla, repos)
        self.assertIn("falta lo que allá no se subió", aviso)

    def test_lo_que_no_esta_alla_o_fuera_de_la_raiz(self):
        repos = [{"relativa": "no-esta", "commit": "abc"}, {"relativa": "", "commit": "abc"},
                 {"relativa": "../fuera", "commit": "abc"}, "raro"]
        self.assertEqual(sin_subir.en_destino(self.ctx_alla, repos),
                         [{"relativa": "no-esta", "existe": False, "tiene": False},
                          {"relativa": "../fuera", "existe": False, "tiene": False}])
        self.assertEqual(sin_subir.al_dia(self.ctx_alla, repos), [])


class ElRegistroYLaCasillaViajan(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.aqui = SimpleNamespace(estado=str(d / "aqui"))
        self.alla = SimpleNamespace(estado=str(d / "alla"))

    def test_su_padre_sus_etiquetas_su_prioridad_su_esfuerzo_y_si_es_publico(self):
        aqui, alla = mod_estado.Estado(self.aqui.estado), mod_estado.Estado(self.alla.estado)
        aqui.colgar("Aspas", "Taller")
        aqui.etiquetar("Aspas", ["cliente", "urgente"])
        aqui.prioridad("Aspas", 1)
        aqui.anotar_esfuerzo("Aspas", "high")
        aqui.publicar("Aspas")
        r = mudanza.registro_de(aqui, "Aspas")
        self.assertEqual(r, {"padre": "Taller", "etiquetas": ["cliente", "urgente"], "prioridad": 1, "esfuerzo": "high",
                             "publico": True, "borradores": []})
        # allá había un registro viejo del mismo hilo: queda el que trae
        alla.colgar("Aspas", "Otro")
        alla.etiquetar("Aspas", ["vieja"])
        self.assertEqual(mudanza.aplicar_registro(alla, "Aspas", json.loads(json.dumps(r))), [])
        self.assertEqual(mudanza.registro_de(alla, "Aspas"), r)
        # sin padre ni etiquetas allá tampoco
        sin = {"padre": "", "etiquetas": [], "prioridad": None, "esfuerzo": "", "publico": False, "borradores": []}
        mudanza.aplicar_registro(alla, "Aspas", sin)
        self.assertEqual(mudanza.registro_de(alla, "Aspas"), sin)

    def test_el_padre_que_es_de_quien_lo_abrio_tambien_viaja(self):
        aqui = mod_estado.Estado(self.aqui.estado)
        aqui.anotar_abierto_por("Hijo", "Telar")
        self.assertEqual(mudanza.registro_de(aqui, "Hijo")["padre"], "Telar")

    def test_un_padre_que_haria_un_circulo_se_dice(self):
        alla = mod_estado.Estado(self.alla.estado)
        alla.colgar("Taller", "Aspas")
        (problema,) = mudanza.aplicar_registro(alla, "Aspas", {"padre": "Taller"})
        self.assertIn("círculo", problema)

    def test_lo_que_esperaba_en_su_casilla_llega_alla_y_sale_de_aqui(self):
        from telar import bus as mod_bus

        m1 = mod_bus.mensaje("revisa el informe", de="Telar", para="Aspas", mid="20261124100000-aaaa")
        m2 = mod_bus.mensaje("para cuando puedas", de="Telar", para="Aspas", modo="aviso", mid="20261124100001-bbbb")
        casilla.dejar(self.aqui, "Aspas", m1)
        casilla.dejar(self.aqui, "Aspas", m2)
        van, quedan = mudanza.casilla_de(self.aqui, "Aspas")
        self.assertEqual(([m["id"] for m in van], quedan), ([m1["id"], m2["id"]], 0))
        self.assertEqual(mudanza.recibir_casilla(self.alla, "Aspas", json.loads(json.dumps(van))), 2)
        self.assertEqual(mudanza.recibir_casilla(self.alla, "Aspas", van), 0, "el mismo id no se deja dos veces")
        self.assertEqual([m["texto"] for m in casilla.pendientes(self.alla, "Aspas")], ["revisa el informe", "para cuando puedas"])
        self.assertEqual([m["id"] for m in casilla.despiertan(self.alla, "Aspas")], [m1["id"]], "el aviso sigue siendo aviso")
        self.assertEqual(casilla.sacar(self.aqui, "Aspas", [m["id"] for m in van]), 2)
        self.assertEqual(casilla.pendientes(self.aqui, "Aspas"), [])

    def test_lo_que_no_cabe_queda_aqui(self):
        from telar import bus as mod_bus

        for i in range(3):
            casilla.dejar(self.aqui, "Aspas", mod_bus.mensaje("x" * 1000, de="Telar", para="Aspas", mid=f"m{i}"))
        with mock.patch.object(mudanza, "TOPE_CASILLA", 2500):
            van, quedan = mudanza.casilla_de(self.aqui, "Aspas")
        self.assertEqual((len(van), quedan), (2, 1))
