"""`telar desplegar` (telar.despliegue): llevar main a cada máquina, reiniciar lo que corresponde y comprobar.

Sin red: la «otra máquina» es un clon en otra carpeta, con su propio hogar, y `ssh` es uno de mentira que corre el
comando aquí, en ese hogar. `systemctl` y `launchctl` también son de mentira: lo instalado en cada máquina está en
`<hogar>/.servicios`, un reinicio queda anotado en `<hogar>/.registro` (junto con lo que anotan los pasos declarados)
y uno falla si existe `<hogar>/.falla-<servicio>`.
"""

from __future__ import annotations

import contextlib
import http.server
import io
import json
import os
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import despliegue as D
from telar.ordenes import desplegar as orden

SSH = r"""#!/bin/sh
# ssh de mentira: corre el comando en esta máquina, en el hogar de la otra ($FALSO_HOGARES/<máquina>)
while [ $# -gt 0 ]; do
  case $1 in
    -o|-p|-i|-l|-F|-J) shift 2 ;;
    -*) shift ;;
    *) break ;;
  esac
done
destino=$1; shift
maquina=${destino#*@}
[ -d "$FALSO_HOGARES/$maquina" ] || { echo "ssh: Could not resolve hostname $maquina" >&2; exit 255; }
export HOME="$FALSO_HOGARES/$maquina"
cd "$HOME" || exit 255
[ $# -eq 0 ] && exit 0
exec sh -c "$*"
"""

SYSTEMCTL = r"""#!/bin/sh
[ "$1" = --user ] && shift
verbo=$1; unidad=$2
grep -qx "$unidad" "$HOME/.servicios" 2>/dev/null || { echo "Unit $unidad.service could not be found." >&2; exit 1; }
case $verbo in
  restart) if [ -e "$HOME/.falla-$unidad" ]; then echo "Job for $unidad.service failed." >&2; exit 1; fi
           [ -e "$HOME/.mata-tmux" ] && rm -f "$HOME/.ventanas"
           echo "reinicio $unidad" >> "$HOME/.registro" ;;
  is-active) echo active ;;
esac
exit 0
"""

LAUNCHCTL = r"""#!/bin/sh
verbo=$1; shift
[ "$1" = -k ] && shift
etiqueta=${1##*/}
grep -qx "$etiqueta" "$HOME/.servicios" 2>/dev/null || { echo "Could not find service \"$etiqueta\"" >&2; exit 113; }
case $verbo in
  print) echo "state = running" ;;
  kickstart) if [ -e "$HOME/.falla-$etiqueta" ]; then echo "kickstart: no pude" >&2; exit 1; fi
             [ -e "$HOME/.mata-tmux" ] && rm -f "$HOME/.ventanas"
             echo "reinicio $etiqueta" >> "$HOME/.registro" ;;
esac
exit 0
"""

# el de la otra máquina, para buscar dónde vive allá el repositorio: lo que diga <hogar>/.telar-config.json
TELAR = r"""#!/bin/sh
[ "$1 $2" = "config --json" ] && [ -f "$HOME/.telar-config.json" ] && exec cat "$HOME/.telar-config.json"
exit 1
"""

# las ventanas de tmux de cada máquina (sus hilos), en <hogar>/.ventanas; sin el archivo, no hay servidor
TMUX = '#!/bin/sh\n[ -f "$HOME/.ventanas" ] && exec cat "$HOME/.ventanas"\nexit 1\n'

DECLARACION = """\
preparar:
  - comando: echo "preparar" >> "$HOME/.registro"
    si_cambia: [requisitos.txt]
servicios:
  - systemd: app
    launchd: com.app
despues:
  - comando: echo "skill" >> "$HOME/.registro"
    si_cambia: [agente/]
comprobar:
  - comando: test -f app.py
    plazo: 0
"""


def git(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout.strip()


def commitear(carpeta: Path, archivo: str, texto: str) -> str:
    (carpeta / archivo).parent.mkdir(parents=True, exist_ok=True)
    (carpeta / archivo).write_text(texto)
    git(carpeta, "add", archivo)
    git(carpeta, "commit", "-q", "-m", f"cambio en {archivo}")
    return git(carpeta, "rev-parse", "HEAD")


class _Maquinas(Prueba):
    """Esta máquina («laptop», con el repositorio en <tmp>/vida/proyectos/app) y otra («casa», ssh ana@casa, con un
    clon en ~/vida/proyectos/app de su hogar). Las dos con el servicio `app` (o `com.app` en launchd) instalado."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        falsos = self.dir / "bin"
        falsos.mkdir()
        for nombre, texto in (("ssh", SSH), ("systemctl", SYSTEMCTL), ("launchctl", LAUNCHCTL), ("telar", TELAR),
                              ("tmux", TMUX)):
            (falsos / nombre).write_text(texto)
            (falsos / nombre).chmod(0o755)
        self.hogar = self.dir / "hogar"            # el de esta máquina
        self.hogares = self.dir / "hogares"
        self.alla = self.hogares / "casa"          # el de la otra
        for h in (self.hogar, self.alla):
            h.mkdir(parents=True)
            (h / ".servicios").write_text("app\ncom.app\n")
        entorno = {
            "PATH": f"{falsos}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(self.hogar),
            "FALSO_HOGARES": str(self.hogares),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        }
        parche = mock.patch.dict(os.environ, entorno)
        parche.start()
        self.addCleanup(parche.stop)
        for v in ("GIT_SSH_COMMAND", "GIT_SSH", "GIT_DIR", "GIT_WORK_TREE"):
            os.environ.pop(v, None)
        self.raiz = self.dir / "vida"
        self.repo = self.raiz / "proyectos" / "app"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        commitear(self.repo, ".telar/despliegue.yaml", DECLARACION)
        commitear(self.repo, "app.py", "print('hola')\n")
        self.clon = self.alla / "vida" / "proyectos" / "app"
        self.clon.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", "-q", str(self.repo), str(self.clon)], check=True)
        self.config = N(raiz=self.raiz, remotos=[N(nombre="casa", destino="ana@casa", raiz="~/vida", repos=())],
                        bus=N(maquina="laptop"))

    def desplegar(self, *argv: str) -> tuple[int, dict]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = orden.main(["--repo", str(self.repo), "--json", *argv], N(config=self.config))
        return codigo, json.loads(salida.getvalue())

    def registro(self, hogar: Path) -> list[str]:
        archivo = hogar / ".registro"
        lineas = archivo.read_text().splitlines() if archivo.exists() else []
        # el servicio se llama `app` en systemd y `com.app` en launchd: da igual cuál usó esta máquina
        return ["reinicio" if l.startswith("reinicio ") else l for l in lineas]

    def maquina(self, datos: dict, nombre: str) -> dict:
        return next(m for m in datos["maquinas"] if m["nombre"] == nombre)

    def desplegado(self, carpeta: Path) -> str:
        r = subprocess.run(["git", "-C", str(carpeta), "rev-parse", "-q", "--verify", D.DESPLEGADO],
                           capture_output=True, text=True)
        return r.stdout.strip()


class TodoBien(_Maquinas):
    def test_lleva_main_reinicia_en_las_dos_y_anota_lo_que_corre(self):
        nuevo = commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertTrue(d["ok"])
        self.assertEqual(d["commit"], nuevo)
        # la otra máquina avanzó su main, sin ramas ni referencias de paso
        self.assertEqual(git(self.clon, "rev-parse", "HEAD"), nuevo)
        self.assertEqual(git(self.clon, "symbolic-ref", "--short", "HEAD"), "main")
        self.assertEqual(git(self.clon, "for-each-ref", "refs/telar/llega*"), "")
        # sin nada anotado, todo cuenta como cambiado: se prepara, se reinicia y se hace lo de después en las dos
        for hogar in (self.alla, self.hogar):
            self.assertEqual(self.registro(hogar), ["preparar", "reinicio", "skill"])
        self.assertEqual(self.desplegado(self.clon), nuevo)
        self.assertEqual(self.desplegado(self.repo), nuevo)
        self.assertEqual([m["nombre"] for m in d["maquinas"]], ["casa", "laptop"])
        for m in d["maquinas"]:
            self.assertEqual(m["estado"], "listo")
            self.assertEqual((m["tiene"], m["corre"]), (nuevo, nuevo))

    def test_dos_veces_seguidas_la_segunda_no_reinicia_nada(self):
        commitear(self.repo, "app.py", "print('chao')\n")
        self.assertEqual(self.desplegar()[0], 0)
        antes = (self.registro(self.alla), self.registro(self.hogar))
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0)
        self.assertEqual((self.registro(self.alla), self.registro(self.hogar)), antes)
        self.assertEqual({m["estado"] for m in d["maquinas"]}, {"al-dia"})
        # lo que se comprueba se comprueba igual
        pasos = self.maquina(d, "casa")["pasos"]
        self.assertEqual([p["estado"] for p in pasos if p["fase"] == "comprobar"], ["hecho"])

    def test_con_todo_reinicia_aunque_ya_corra_ese_commit(self):
        self.assertEqual(self.desplegar()[0], 0)
        self.assertEqual(self.desplegar("--todo")[0], 0)
        self.assertEqual(self.registro(self.alla).count("reinicio"), 2)

    def test_una_maquina_donde_no_vive_el_repositorio_se_salta(self):
        self.config.remotos.append(N(nombre="lejos", destino="ana@lejos", raiz="~/vida", repos=()))
        (self.hogares / "lejos").mkdir()
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        lejos = self.maquina(d, "lejos")
        self.assertEqual(lejos["estado"], "no-vive")
        self.assertIn(str((self.hogares / "lejos" / "vida" / "proyectos" / "app").resolve()), lejos["buscadas"])

    def test_lo_encuentra_donde_diga_el_telar_de_alla(self):
        # allá vive en otra carpeta (un módulo en ~/src): la raíz no lo encuentra, la configuración de allá sí
        otra = self.alla / "src" / "app"
        otra.parent.mkdir()
        self.clon.rename(otra)
        (self.alla / ".telar-config.json").write_text(json.dumps(
            {"raiz": str(self.alla / "vida"), "repos": [], "modulos": [{"nombre": "app", "carpeta": str(otra)}]}))
        nuevo = commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertEqual(self.maquina(d, "casa")["ruta"], str(otra.resolve()))
        self.assertEqual(git(otra, "rev-parse", "HEAD"), nuevo)

    def test_otro_repositorio_en_la_misma_carpeta_no_es_este(self):
        # la carpeta existe allá, pero es otro repositorio (otros primeros commits): no se le lleva nada
        subprocess.run(["rm", "-rf", str(self.clon)], check=True)
        self.clon.mkdir()
        git(self.clon, "init", "-q", "-b", "main")
        commitear(self.clon, "otro.txt", "otro\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertEqual(self.maquina(d, "casa")["estado"], "no-vive")
        self.assertEqual(self.registro(self.alla), [])

    def test_solo_en_una_maquina(self):
        commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar("--maquina", "laptop")
        self.assertEqual(codigo, 0)
        self.assertEqual([m["nombre"] for m in d["maquinas"]], ["laptop"])
        self.assertEqual(self.registro(self.alla), [])
        self.assertEqual(self.desplegar("--maquina", "marte")[0], 2)


class SeNiega(_Maquinas):
    def assertSinTocar(self, antes: str):
        self.assertEqual(git(self.clon, "rev-parse", "HEAD"), antes)
        self.assertEqual((self.registro(self.alla), self.registro(self.hogar)), ([], []))
        self.assertEqual((self.desplegado(self.clon), self.desplegado(self.repo)), ("", ""))

    def test_si_la_otra_maquina_tiene_commits_que_aqui_no_estan(self):
        commitear(self.repo, "app.py", "print('chao')\n")
        adelantado = commitear(self.clon, "solo-alla.txt", "x\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn("commits que aquí no están", d["negado"])
        self.assertEqual(self.maquina(d, "casa")["estado"], "negada")
        self.assertSinTocar(adelantado)

    def test_si_lo_versionado_esta_sucio_aqui(self):
        antes = git(self.clon, "rev-parse", "HEAD")
        commitear(self.repo, "requisitos.txt", "uno\n")
        (self.repo / "app.py").write_text("print('a medias')\n")
        (self.repo / "suelto.txt").write_text("lo no versionado no cuenta\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn("app.py", d["negado"])
        self.assertNotIn("suelto.txt", d["negado"])
        self.assertSinTocar(antes)

    def test_si_lo_versionado_esta_sucio_alla(self):
        antes = git(self.clon, "rev-parse", "HEAD")
        commitear(self.repo, "app.py", "print('chao')\n")
        (self.clon / "app.py").write_text("print('editado allá')\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn("casa", d["negado"])
        self.assertSinTocar(antes)

    def test_si_no_se_esta_en_main(self):
        antes = git(self.clon, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-q", "-b", "otra")
        commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn("no estás en main", d["negado"])
        self.assertSinTocar(antes)

    def test_si_la_otra_maquina_no_contesta(self):
        self.config.remotos[0] = N(nombre="casa", destino="ana@apagada", raiz="~/vida", repos=())
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn("no pude mirarla", d["negado"])
        self.assertEqual(self.registro(self.hogar), [])

    def test_sin_declaracion(self):
        git(self.repo, "rm", "-q", ".telar/despliegue.yaml")
        git(self.repo, "commit", "-q", "-m", "sin declaración")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 2)
        self.assertIn(".telar/despliegue.yaml", d["negado"])


class FallaAlReiniciar(_Maquinas):
    def test_se_detiene_y_dice_en_que_quedo_cada_maquina(self):
        antes = git(self.clon, "rev-parse", "HEAD")
        nuevo = commitear(self.repo, "app.py", "print('chao')\n")
        for nombre in ("app", "com.app"):
            (self.alla / f".falla-{nombre}").touch()
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 1)
        self.assertFalse(d["ok"])
        self.assertEqual((d["fallo"]["maquina"], d["fallo"]["fase"]), ("casa", "reiniciar"))
        # lo que dijo systemctl o launchctl
        self.assertRegex(d["fallo"]["detalle"], "Job for app.service failed|kickstart: no pude")
        casa, laptop = self.maquina(d, "casa"), self.maquina(d, "laptop")
        # allá llegó el código y se preparó, pero no se anotó que corra: el próximo despliegue lo vuelve a intentar
        self.assertEqual(casa["estado"], "a-medias")
        self.assertEqual((casa["tenia"], casa["tiene"], casa["corre"]), (antes, nuevo, "?"))
        self.assertEqual(git(self.clon, "rev-parse", "HEAD"), nuevo)
        self.assertEqual(self.desplegado(self.clon), "")
        self.assertEqual(self.registro(self.alla), ["preparar"])
        # a esta no se llegó
        self.assertEqual(laptop["estado"], "sin-tocar")
        self.assertEqual(self.registro(self.hogar), [])
        self.assertEqual({p["estado"] for p in laptop["pasos"] if p["fase"] != "codigo"}, {"pendiente"})

    def test_un_reinicio_que_se_lleva_tmux_falla(self):
        commitear(self.repo, "app.py", "print('chao')\n")
        (self.alla / ".ventanas").write_text("@1\n@2\n@3\n")
        (self.alla / ".mata-tmux").touch()
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 1)
        self.assertEqual((d["fallo"]["maquina"], d["fallo"]["fase"]), ("casa", "reiniciar"))
        self.assertIn("había 3 ventanas de tmux y no queda ninguna", d["fallo"]["detalle"])

    def test_el_texto_dice_el_paso_y_como_quedo_cada_una(self):
        commitear(self.repo, "app.py", "print('chao')\n")
        (self.hogar / ".falla-app").touch()
        (self.hogar / ".falla-com.app").touch()
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = orden.main(["--repo", str(self.repo)], N(config=self.config))
        self.assertEqual(codigo, 1)
        texto = salida.getvalue()
        self.assertIn("falló en laptop, al reiniciar", texto)
        self.assertIn("casa: al día", texto)
        self.assertIn("laptop: algo se reinició, o falló al reiniciar", texto)
        # lo que pasó, antes de cómo quedó: todo por la misma salida, en orden
        self.assertLess(texto.index("✗ reiniciar"), texto.index("quedó así"))


class Ver(_Maquinas):
    def test_dice_que_haria_sin_tocar_nada(self):
        antes = git(self.clon, "rev-parse", "HEAD")
        nuevo = commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar("--ver")
        self.assertEqual(codigo, 0)
        self.assertTrue(d["ver"])
        self.assertEqual(git(self.clon, "rev-parse", "HEAD"), antes)
        self.assertEqual((self.registro(self.alla), self.registro(self.hogar)), ([], []))
        self.assertEqual((self.desplegado(self.clon), self.desplegado(self.repo)), ("", ""))
        casa = self.maquina(d, "casa")
        self.assertEqual(casa["estado"], "ver")
        self.assertEqual([(p["fase"], p["estado"]) for p in casa["pasos"]], [
            ("codigo", "haria"), ("preparar", "haria"), ("reiniciar", "haria"), ("despues", "haria"),
            ("anotar", "haria"), ("comprobar", "haria")])
        self.assertIn(f"{antes[:7]} → {nuevo[:7]} (1 commit)", casa["pasos"][0]["que"])

    def test_el_texto_lo_dice(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = orden.main(["--repo", str(self.repo), "--ver"], N(config=self.config))
        self.assertEqual(codigo, 0)
        texto = salida.getvalue()
        self.assertIn("lo que haría", texto)
        self.assertIn("→ reiniciar", texto)
        self.assertIn("casa · ana@casa:", texto)


class LoQueCambio(_Maquinas):
    def test_la_skill_cambiada_se_reinstala_en_las_dos_y_lo_demas_no(self):
        self.assertEqual(self.desplegar()[0], 0)
        for hogar in (self.alla, self.hogar):
            (hogar / ".registro").unlink()
        commitear(self.repo, "agente/skill.py", "SKILL = 'nueva'\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        for hogar in (self.alla, self.hogar):
            self.assertEqual(self.registro(hogar), ["reinicio", "skill"])
        preparar = next(p for p in self.maquina(d, "casa")["pasos"] if p["fase"] == "preparar")
        self.assertEqual((preparar["estado"], preparar["detalle"]), ("saltado", "no cambió requisitos.txt"))
        # un cambio que no toca la skill reinicia, pero no la reinstala
        for hogar in (self.alla, self.hogar):
            (hogar / ".registro").unlink()
        commitear(self.repo, "README.md", "# app\n")
        self.assertEqual(self.desplegar()[0], 0)
        for hogar in (self.alla, self.hogar):
            self.assertEqual(self.registro(hogar), ["reinicio"])

    def test_lo_que_va_con_un_servicio_solo_donde_esta_instalado(self):
        # compilar el puente va con su servicio, que va primero
        decl = DECLARACION.replace('echo "preparar" >> "$HOME/.registro"\n    si_cambia: [requisitos.txt]',
                                   'echo "compilar" >> "$HOME/.registro"\n    si_corre: puente')
        decl = decl.replace("servicios:\n", "servicios:\n  - systemd: puente\n    launchd: puente\n")
        (self.repo / ".telar" / "despliegue.yaml").write_text(decl)
        git(self.repo, "commit", "-q", "-am", "un puente")
        # el puente corre solo allá
        (self.alla / ".servicios").write_text("app\ncom.app\npuente\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertEqual(self.registro(self.alla), ["compilar", "reinicio", "reinicio", "skill"])
        self.assertEqual(self.registro(self.hogar), ["reinicio", "skill"])
        laptop = self.maquina(d, "laptop")["pasos"]
        self.assertEqual([(p["fase"], p["estado"]) for p in laptop if p["fase"] in ("preparar", "reiniciar")],
                         [("preparar", "saltado"), ("reiniciar", "saltado"), ("reiniciar", "hecho")])


#: el compilador de las pruebas de lo compilado: salida/app.js es fuente.txt en mayúsculas
GENERAR = "from pathlib import Path\nPath('salida').mkdir(exist_ok=True)\n" \
          "Path('salida/app.js').write_text(Path('fuente.txt').read_text().upper())\n"


class LoCompilado(_Maquinas):
    """La red: lo compilado viaja tal cual está commiteado, y si no corresponde a sus fuentes, desplegar avisa."""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitattributes").write_text("salida/app.js merge=telar-compilado\n")
        (self.repo / ".telar" / "compilados.yaml").write_text(
            f"comandos:\n  - carpeta: .\n    comando: {sys.executable} generar.py\n    fuentes: [fuente.txt]\n")
        (self.repo / "generar.py").write_text(GENERAR)
        (self.repo / "fuente.txt").write_text("hola\n")
        (self.repo / "salida").mkdir()
        (self.repo / "salida" / "app.js").write_text("HOLA\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "con lo compilado")

    def test_al_dia_no_avisa(self):
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertEqual(d["compilados"], {"desfasados": [], "error": ""})

    def test_la_fuente_sin_volver_a_generar_avisa_y_despliega_igual(self):
        self.assertEqual(self.desplegar()[0], 0)
        commitear(self.repo, "fuente.txt", "chao\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertEqual(d["compilados"], {"desfasados": ["salida/app.js"], "error": ""})
        self.assertEqual(git(self.clon, "rev-parse", "HEAD"), d["commit"])
        # la carpeta queda como estaba (lo de verdad no se vuelve a generar aquí) y el árbol aparte no queda
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(git(self.repo, "worktree", "list", "--porcelain").split("worktree ")), 2)

    def test_el_texto_lo_dice(self):
        commitear(self.repo, "fuente.txt", "chao\n")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            orden.main(["--repo", str(self.repo), "--ver"], N(config=self.config))
        self.assertIn("no corresponde a sus fuentes: salida/app.js", salida.getvalue())

    def test_si_no_cambia_ni_la_fuente_ni_lo_compilado_no_mira(self):
        self.assertEqual(self.desplegar()[0], 0)
        commitear(self.repo, "app.py", "print('chao')\n")
        codigo, d = self.desplegar()
        self.assertEqual(codigo, 0, d)
        self.assertIsNone(d["compilados"])

    def test_sin_compilados_yaml_no_mira(self):
        git(self.repo, "rm", "-q", ".telar/compilados.yaml")
        git(self.repo, "commit", "-q", "-m", "sin compilados.yaml")
        self.assertIsNone(self.desplegar()[1]["compilados"])


class LaDeclaracion(unittest.TestCase):
    def test_la_de_telar_se_entiende(self):
        raiz = Path(__file__).resolve().parents[1]
        d = D.leer_declaracion(raiz)
        self.assertEqual(d.rama, "main")
        self.assertEqual([s.nombres for s in d.servicios], [("telar-serve", "com.telar.serve")])
        self.assertEqual([(c.pagina, c.igual) for c in d.comprobar], [("/pagina.json", "firma"), ("/api/salud", "")])
        # que la página siga arriba unos segundos después de contestar la primera vez
        self.assertGreaterEqual(d.comprobar[0].sigue, 10)
        self.assertTrue(D.toca(d.despues[0].si_cambia, ["src/telar/agente/skill.py"]))
        self.assertFalse(D.toca(d.despues[0].si_cambia, ["src/telar/api.py"]))
        self.assertTrue(D.toca(d.preparar[0].si_cambia, ["pyproject.toml"]))

    def test_lo_que_no_se_entiende_se_dice(self):
        malas = [
            ([], "un mapa"),
            ({"servicio": []}, "no conozco servicio"),
            ({"servicios": [{"si_cambia": ["x"]}]}, "su nombre"),
            ({"preparar": [{"si_cambia": ["x"]}]}, "falta su `comando`"),
            ({"preparar": [{"comando": "x", "si_cambia": 3}]}, "si_cambia"),
            ({"preparar": [{"comando": "x", "si_corre": "otro"}]}, "no es ninguno de `servicios`"),
            ({"comprobar": [{"pagina": "/a", "comando": "b"}]}, "uno de los dos"),
            ({"comprobar": [{"pagina": "a"}]}, "empieza con /"),
            ({"comprobar": [{"comando": "a", "igual": "firma"}]}, "`igual` va con `pagina`"),
            ({"comprobar": [{"comando": "a", "sigue": 5}]}, "`sigue` va con `pagina`"),
            ({"comprobar": [{"pagina": "/a", "sigue": "pronto"}]}, "son segundos"),
            ({"comprobar": [{"pagina": "/a", "sigue": -1}]}, "0 o más"),
        ]
        for datos, dice in malas:
            with self.subTest(datos=datos), self.assertRaises(D.ErrorDeDespliegue) as e:
                D.interpretar(datos)
            self.assertIn(dice, str(e.exception))

    def test_si_cambia(self):
        self.assertTrue(D.toca((), None))                       # no se sabe qué corre: todo
        self.assertFalse(D.toca((), []))                        # ya corre ese commit: nada
        self.assertTrue(D.toca((), ["x"]))                      # sin si_cambia, cualquier cambio
        self.assertTrue(D.toca(("puente/**",), ["puente/a/b.go"]))
        self.assertTrue(D.toca(("puente/",), ["puente/a/b.go"]))
        self.assertFalse(D.toca(("puente/",), ["bin/puente"]))
        self.assertTrue(D.toca(("*.toml",), ["pyproject.toml"]))


class _Pagina(http.server.BaseHTTPRequestHandler):
    llave = ""
    firma = "f1"
    #: lo que hace el servidor después de contestar (una prueba lo apaga)
    al_contestar = None

    def do_GET(self):
        if self.headers.get("Cookie") != f"telar_panel={self.llave}":
            self.send_response(403)
            self.end_headers()
            return
        cuerpo = json.dumps({"firma": self.firma} if self.path == "/pagina.json" else {"ok": True}).encode()
        self.send_response(200 if self.path in ("/pagina.json", "/api/salud") else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(cuerpo)
        if type(self).al_contestar:
            type(self).al_contestar(self.server)

    def log_message(self, *a):
        pass


class _Salud(http.server.BaseHTTPRequestHandler):
    web = ""

    def do_GET(self):
        cuerpo = json.dumps({"ok": True, "web": self.web}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass

    def address_string(self):
        return "socket"


class _Unix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class LaPagina(Prueba):
    """La comprobación de `pagina`, contra un `telar serve` de mentira: su socket dice dónde está la página, y la
    página pide la llave de esta máquina."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.mkdtemp(prefix="tp", dir="/tmp" if sys.platform == "darwin" else None)  # un socket cabe corto
        self.addCleanup(subprocess.run, ["rm", "-rf", tmp])
        self.dir = Path(tmp)
        (self.dir / "config" / "telar").mkdir(parents=True)
        (self.dir / "config" / "telar" / "panel.llave").write_text("secreta\n")
        (self.dir / "estado" / "telar" / "serve").mkdir(parents=True)
        parche = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.dir / "config"),
                                              "XDG_STATE_HOME": str(self.dir / "estado")})
        parche.start()
        self.addCleanup(parche.stop)
        _Pagina.llave = "secreta"
        pagina = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Pagina)
        threading.Thread(target=pagina.serve_forever, daemon=True).start()
        self.addCleanup(pagina.server_close)
        self.addCleanup(pagina.shutdown)
        _Salud.web = f"http://127.0.0.1:{pagina.server_address[1]}"
        sock = self.dir / "estado" / "telar" / "serve" / "telar.sock"
        salud = _Unix(str(sock), _Salud)
        threading.Thread(target=salud.serve_forever, daemon=True).start()
        self.addCleanup(salud.server_close)
        self.addCleanup(salud.shutdown)
        self.aqui = D.Maquina("laptop")

    def test_pide_la_pagina_con_la_llave_y_no_la_dice(self):
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/pagina.json", "plazo": 0})
        self.assertEqual(r, {"ok": True, "valor": {"firma": "f1"}, "detalle": ""})
        self.assertEqual(self.aqui.ayudante({"accion": "comprobar", "pagina": "/api/salud", "plazo": 0})["ok"], True)

    def test_con_sigue_la_pide_de_nuevo_y_tiene_que_seguir_ahi(self):
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/pagina.json", "plazo": 0, "sigue": 0.2})
        self.assertEqual(r, {"ok": True, "valor": {"firma": "f1"}, "detalle": ""})

    def test_una_pagina_que_contesta_y_se_cae_falla(self):
        """26-nov-2026: el servicio arrancó, la página contestó y a los 8 s ya no escuchaba: con `sigue`, se nota."""
        _Pagina.al_contestar = lambda servidor: threading.Thread(
            target=lambda: (servidor.shutdown(), servidor.server_close()), daemon=True).start()
        self.addCleanup(setattr, _Pagina, "al_contestar", None)
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/pagina.json", "plazo": 0, "sigue": 0.5})
        self.assertFalse(r["ok"])
        self.assertIn("contestó, pero a los 0.5 s ya no", r["detalle"])

    def test_otra_llave_no_entra(self):
        _Pagina.llave = "otra"
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/pagina.json", "plazo": 0})
        self.assertFalse(r["ok"])
        self.assertIn("403", r["detalle"])
        self.assertNotIn("secreta", json.dumps(r))

    def test_una_ruta_que_no_existe(self):
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/salud", "plazo": 0})
        self.assertEqual((r["ok"], r["detalle"]), (False, "/salud contestó 404"))

    def test_un_serve_que_no_dice_su_pagina(self):
        _Salud.web = ""
        r = self.aqui.ayudante({"accion": "comprobar", "pagina": "/pagina.json", "plazo": 0})
        self.assertIn("no dice dónde está su página", r["detalle"])

    def test_iguales_entre_maquinas(self):
        decl = D.interpretar({"comprobar": [{"pagina": "/pagina.json", "igual": "firma"}, {"pagina": "/api/salud"}]})
        d = D.Despliegue(Path("."), decl, "c", "main", [D.Maquina("a", "x@a"), D.Maquina("b")])
        d.maquinas[0].valores = {0: {"firma": "f1"}, 1: {"ok": True}}
        d.maquinas[1].valores = {0: {"firma": "f1"}, 1: {"ok": True}}
        self.assertEqual(D._iguales(d), [{"que": "/pagina.json", "campo": "firma", "ok": True,
                                         "valores": {"a": "f1", "b": "f1"}}])
        d.maquinas[1].valores[0] = {"firma": "f0"}
        self.assertFalse(D._iguales(d)[0]["ok"])


class LaSalud(Prueba):
    def test_salud_dice_donde_esta_la_pagina(self):
        try:
            from fastapi.testclient import TestClient

            from telar import api
        except ImportError:
            self.skipTest("sin el extra serve")
        from telar.config import Config

        api.app.dependency_overrides[api.contexto] = lambda: N(config=Config(raiz=Path("/r"), estado=Path("/e")))
        self.addCleanup(api.app.dependency_overrides.clear)
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            # sin --web, no hay página en un puerto
            self.assertEqual(TestClient(api.app).get("/salud").json()["web"], "")
            api.app.state.web = "http://100.64.0.1:8780"
            self.addCleanup(delattr, api.app.state, "web")
            self.assertEqual(TestClient(api.app).get("/salud").json()["web"], "http://100.64.0.1:8780")


if __name__ == "__main__":
    unittest.main()
