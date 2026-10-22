"""`telar persona`: el plan para dar de alta a un colega, sin ejecutar nada."""

import subprocess
import tempfile
import unittest
from pathlib import Path

import comun  # noqa: F401 (src/ en el camino)

from telar import persona as mod

LLAVE = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP8DI50erz0zIRwdLL7hw00iSxVJwW7yff0p2Cgj7yKQ ramiro@x"


def ramiro(**k):
    datos = dict(nombre="ramiro", perfil="colega", llave=LLAVE, dueno="ana", correo=["faro"], memoria="2500M", cpu="100%")
    datos.update(k)
    return mod.validar(**datos)


class Validar(unittest.TestCase):
    def test_rechaza_lo_que_no_sirve(self):
        for malo in (dict(nombre="Ramiro V"), dict(nombre="a;rm"), dict(perfil="dios"), dict(llave="hola"),
                     dict(llave=LLAVE + "\nssh-rsa AAAA"), dict(memoria="mucha"), dict(cpu="2"), dict(correo=["a b"]),
                     dict(dueno="x y")):
            with self.assertRaises(mod.ErrorDePersona, msg=malo):
                ramiro(**malo)


class Plan(unittest.TestCase):
    def test_las_acciones_y_su_orden(self):
        claves = [a.clave for a in mod.plan(ramiro()).acciones]
        self.assertEqual(claves, ["usuario", "llave", "ssh", "recursos", "correo", "instalar", "definicion"])

    def test_sin_correo_no_toca_la_lista_de_permitidos(self):
        claves = [a.clave for a in mod.plan(ramiro(correo=[])).acciones]
        self.assertNotIn("correo", claves)

    def test_lo_de_seguridad_esta_en_el_guion(self):
        g = mod.plan(ramiro()).guion()
        self.assertIn("gpasswd -d ramiro agentes", g)          # fuera del grupo que lee el correo archivado
        self.assertIn("PasswordAuthentication no", g)
        self.assertIn("AllowTcpForwarding no", g)
        self.assertIn("MemoryMax=2500M", g)
        self.assertIn("CPUQuota=100%", g)
        self.assertIn("sshd -t && systemctl reload ssh", g)     # no se recarga una configuración rota
        self.assertIn("ramiro: faro", g)
        self.assertNotIn("sudo", g.replace("# telar persona: generado, corre con sudo", ""))

    def test_el_guion_es_shell_valido(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.sh"
            f.write_text(mod.plan(ramiro()).guion())
            self.assertEqual(subprocess.run(["bash", "-n", str(f)], capture_output=True).returncode, 0)

    def test_la_llave_con_comillas_no_pasa_la_validacion(self):
        with self.assertRaises(mod.ErrorDePersona):
            ramiro(llave="ssh-ed25519 AAAA'$(id)' x\n")


class Quitar(unittest.TestCase):
    def test_conserva_el_home_salvo_que_se_pida(self):
        sin = mod.plan_quitar("ramiro", "ana")
        con = mod.plan_quitar("ramiro", "ana", borrar_home=True)
        self.assertNotIn("userdel", sin.guion())
        self.assertIn("userdel -r ramiro", con.guion())
        self.assertIn("usermod -L", sin.guion())

    def test_el_guion_es_shell_valido(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "q.sh"
            f.write_text(mod.plan_quitar("ramiro", "ana", borrar_home=True).guion())
            self.assertEqual(subprocess.run(["bash", "-n", str(f)], capture_output=True).returncode, 0)


class Leer(unittest.TestCase):
    def test_lee_lo_anotado_y_no_enseña_la_llave(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ramiro.toml").write_text(ramiro().a_toml())
            (Path(d) / "roto.toml").write_text("esto no es toml [")
            gente = {x["nombre"]: x for x in mod.leer(Path(d))}
        self.assertEqual(gente["ramiro"]["correo"], ["faro"])
        self.assertNotIn("AAAAC3", str(gente["ramiro"]))
        self.assertIn("error", gente["roto"])

    def test_sin_carpeta(self):
        self.assertEqual(mod.leer(Path("/no/existe")), [])


if __name__ == "__main__":
    unittest.main()
