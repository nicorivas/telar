"""Rotar con relevo (telar.rotacion): el gancho Stop le pide su relevo a un residente que pesa demasiado, el nodo
teclea /clear y después le dice a la conversación nueva que lo lea; en frío, la nueva empieza con el relevo. Y lo
que va con eso: el hilo anota de qué agente es, y `liberar` deja a los residentes para el final."""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agentes as mod_agentes
from telar import config as mod_config
from telar import estado as mod_estado
from telar import rotacion


class ConUnResidente(Prueba):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        d = self.raiz / "agentes" / "faro"
        d.mkdir(parents=True)
        (d / "CLAUDE.md").write_text("# Faro\n")
        self.config = mod_config.Config(raiz=self.raiz, estado=self.raiz / ".estado", agentes_carpeta="agentes",
                                        agentes_rotar_mb=1)
        self.conversacion = self.raiz / "s1.jsonl"

    def pesa(self, mb: float) -> str:
        self.conversacion.write_bytes(b"x" * int(mb * 1024 * 1024))
        return str(self.conversacion)


class ElRelevo(ConUnResidente):
    def test_liviana_no_pasa_nada(self):
        self.assertEqual(rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(0.5)), "")
        self.assertEqual(rotacion.leer(self.config), {})

    def test_un_hilo_que_no_es_de_un_agente_no_rota(self):
        self.assertEqual(rotacion.al_terminar(self.config, "Proyecto X", "s1", self.pesa(3)), "")

    def test_sin_tope_no_rota(self):
        cfg = replace(self.config, agentes_rotar_mb=0)
        self.assertEqual(rotacion.al_terminar(cfg, "Faro", "s1", self.pesa(3)), "")

    def test_de_punta_a_punta(self):
        # 1. termina un turno pesado: no lo deja parar y le pide su relevo
        salida = json.loads(rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(3)))
        self.assertEqual(salida["decision"], "block")
        self.assertIn(str(rotacion.ruta_relevo(self.config, "faro")), salida["reason"])
        self.assertEqual(rotacion.leer(self.config)["Faro"]["fase"], "relevo")
        # 2. termina el turno en que lo escribió: queda para el nodo
        self.assertEqual(rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(3)), "")
        self.assertEqual(rotacion.leer(self.config)["Faro"]["fase"], "limpiar")
        # un Stop más mientras tanto no vuelve a pedirlo
        self.assertEqual(rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(3)), "")
        # 3. el nodo, con el hilo trabajando todavía: nada; quieto: /clear
        tecleado = []
        self.assertEqual(rotacion.avanzar(self.config, "Faro", quieto=False, sesion_actual="s1", escribir=tecleado.append), "")
        self.assertIn("/clear", rotacion.avanzar(self.config, "Faro", quieto=True, sesion_actual="s1", escribir=tecleado.append))
        self.assertEqual(tecleado, ["/clear"])
        # 4. mientras la conversación nueva no está anotada, espera; cuando sí, le dice que lea el relevo
        self.assertEqual(rotacion.avanzar(self.config, "Faro", quieto=True, sesion_actual="s1", escribir=tecleado.append), "")
        self.assertIn("conversación nueva", rotacion.avanzar(self.config, "Faro", quieto=True, sesion_actual="s2",
                                                             escribir=tecleado.append))
        self.assertIn("lee tu relevo", tecleado[-1])
        self.assertEqual(rotacion.leer(self.config), {})

    def test_una_fase_que_no_avanza_se_abandona(self):
        rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(3))
        with mock.patch.object(rotacion.time, "time", return_value=time.time() + rotacion.PLAZO + 1):
            linea = rotacion.avanzar(self.config, "Faro", quieto=False, sesion_actual="", escribir=lambda t: None)
        self.assertIn("la dejo", linea)
        self.assertEqual(rotacion.leer(self.config), {})

    def test_en_frio_la_nueva_empieza_con_el_relevo(self):
        self.assertEqual(rotacion.con_relevo(self.config, "faro", "hola"), "hola")  # sin relevo, tal cual
        relevo = rotacion.ruta_relevo(self.config, "faro")
        relevo.parent.mkdir(parents=True)
        relevo.write_text("iba en la lámpara")
        texto = rotacion.con_relevo(self.config, "faro", "hola")
        self.assertIn(str(relevo), texto)
        self.assertTrue(texto.endswith("hola"))


class ElHiloAnotaSuAgente(ConUnResidente):
    def test_uno_renombrado_sigue_siendo_suyo(self):
        est = mod_estado.abrir(self.config)
        self.assertIsNone(mod_agentes.del_hilo(self.config, "Faro de noche"))
        est.anotar_agente("Faro de noche", "faro")
        self.assertEqual(mod_agentes.del_hilo(self.config, "Faro de noche").clave, "faro")
        est.renombrar("Faro de noche", "Faro 2")
        self.assertEqual(mod_agentes.del_hilo(self.config, "Faro 2").clave, "faro")
        self.assertIn("Faro 2", mod_agentes.del_hilo(self.config, "Faro").hilos)
        est.olvidar("Faro 2")
        self.assertIsNone(mod_agentes.del_hilo(self.config, "Faro 2"))


class LiberarCuidaALosResidentes(ConUnResidente):
    def test_cierra_primero_los_de_paso(self):
        from telar import encargos
        from telar.modelo import Atencion

        cfg = replace(self.config, agente=mod_config.Agente(nombre="claude-code", max_vivos=2))
        est = mod_estado.abrir(cfg)
        # Faro (residente) lleva más rato quieto que el de paso: igual se cierra el de paso
        est.anotar_atencion("Faro", Atencion.TERMINO)
        time.sleep(0.01)
        est.anotar_atencion("de paso", Atencion.TERMINO)
        vivos = [SimpleNamespace(nombre=n, clientes=0, objetivo=f"telar:{n}", direccion=n) for n in ("Faro", "de paso")]
        cerrados = []
        with mock.patch("telar.movil.hilos", return_value=vivos), mock.patch("telar.movil.sin_mirar", return_value=True), \
                mock.patch("telar.movil._tmux", side_effect=lambda *a: cerrados.append(a[-1])):
            self.assertEqual(encargos.liberar(cfg, 1), ["de paso"])
        self.assertEqual(cerrados, ["telar:de paso"])


class LaFichaDeLaBarra(ConUnResidente):
    """Lo que muestra la barra de la derecha al ver el hilo de un agente (telar.servicios.agentes)."""

    def test_su_claude_md_su_relevo_y_su_rotacion(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        ctx = SimpleNamespace(config=self.config)
        f = servicio.del_hilo(ctx, "Faro").model_dump()
        self.assertEqual((f["agente"]["clave"], f["claude_md"], f["relevo"], f["aqui"]), ("faro", "# Faro\n", None, True))
        relevo = rotacion.ruta_relevo(self.config, "faro")
        relevo.parent.mkdir(parents=True)
        relevo.write_text("iba en la lámpara")
        rotacion.al_terminar(self.config, "Faro", "s1", self.pesa(3))
        f = servicio.del_hilo(ctx, "Faro").model_dump()
        self.assertEqual((f["relevo"]["texto"], f["rotacion"]), ("iba en la lámpara", "relevo"))
        # de otra máquina: lo del repositorio sí, lo de allá no
        f = servicio.del_hilo(ctx, "Faro", maquina="servidor").model_dump()
        self.assertEqual((f["aqui"], f["relevo"]), (False, None))
        with self.assertRaises(ErrorDeServicio):
            servicio.del_hilo(ctx, "Proyecto X")


class RotarYa(ConUnResidente):
    def test_la_persona_la_pide_aunque_no_haya_tope(self):
        cfg = replace(self.config, agentes_rotar_mb=0)
        texto = rotacion.forzar(cfg, "Faro", "faro", "s1")
        self.assertIn(str(rotacion.ruta_relevo(cfg, "faro")), texto)
        # al terminar el turno en que lo escribió, queda para el /clear del nodo
        self.assertEqual(rotacion.al_terminar(cfg, "Faro", "s1", self.pesa(0.1)), "")
        self.assertEqual(rotacion.leer(cfg)["Faro"]["fase"], "limpiar")


class QuienAbrioUnHilo(ConUnResidente):
    """Un hilo que abrió el hilo de un agente (o un periódico) lo dice: no es suyo, lo empezó él."""

    def test_lo_anota_solo_si_es_nuevo_y_no_lo_abrio_la_persona(self):
        import os

        from telar.agente import lanzar

        est = mod_estado.abrir(self.config)
        nuevo = lanzar.Lanzamiento(comando=[], carpeta=None, nueva="s9")
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            lanzar.anotar_origen(self.config, "Proyecto X", nuevo)
            # retomar uno no cambia quién lo empezó, ni se anota uno que ya existía
            lanzar.anotar_origen(self.config, "Viejo", lanzar.Lanzamiento(comando=[], carpeta=None, retoma="s1"))
            lanzar.anotar_origen(self.config, "Faro", nuevo)  # se abrió a sí mismo: no
        with mock.patch.dict(os.environ, {"TELAR_HILO": ""}):
            lanzar.anotar_origen(self.config, "De la persona", nuevo)
        lanzar.anotar_origen(self.config, "Del periódico", nuevo, por="periódico correo")
        abiertos = est.abiertos_por()
        self.assertEqual(set(abiertos), {"Proyecto X", "Del periódico"})
        self.assertEqual((abiertos["Proyecto X"]["por"], abiertos["Proyecto X"]["agente"]), ("Faro", "faro"))
        self.assertEqual(abiertos["Del periódico"]["agente"], "")
        # se mueve con el renombre, y se va al olvidarlo
        est.renombrar("Proyecto X", "Proyecto Y")
        self.assertIn("Proyecto Y", est.abiertos_por())
        est.olvidar("Proyecto Y")
        self.assertNotIn("Proyecto Y", est.abiertos_por())


class RelevoDeCualquierHilo(Prueba):
    """/relevo: cualquier hilo (no solo un residente) deja su relevo en el HANDOFF.md de su carpeta, y telar hace el
    /clear y le dice a la conversación nueva que lo lea."""

    def test_dónde_va_y_cómo_avanza(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from telar import rotacion

        with tempfile.TemporaryDirectory() as d:
            config = SimpleNamespace(estado=str(Path(d) / "estado"), raiz=str(Path(d) / "raiz"), agentes_rotar_mb=0)
            self.assertEqual(rotacion.ruta_handoff(config, "Faro", "proyectos/faro"), Path(d) / "raiz/proyectos/faro/HANDOFF.md")
            self.assertEqual(rotacion.ruta_handoff(config, "suelto", "").parent, Path(d) / "estado/relevos")
            ruta = rotacion.ruta_handoff(config, "Faro", "proyectos/faro")
            rotacion.pedir_handoff(config, "Faro", "s1", ruta, "la lámpara nueva")
            # el Stop del turno del relevo no lo detiene (aunque Faro no sea un agente y no haya tope)
            self.assertEqual(rotacion.al_terminar(config, "Faro", "s1"), "")
            tecleado = []
            self.assertIn("/clear", rotacion.avanzar(config, "Faro", quieto=True, sesion_actual="s1", escribir=tecleado.append))
            self.assertEqual(tecleado, ["/clear"])
            # todavía la misma conversación: espera; con la nueva, el aviso con la ruta y el tema
            self.assertEqual(rotacion.avanzar(config, "Faro", quieto=True, sesion_actual="s1", escribir=tecleado.append), "")
            rotacion.avanzar(config, "Faro", quieto=True, sesion_actual="s2", escribir=tecleado.append)
            self.assertIn(str(ruta), tecleado[-1])
            self.assertIn("la lámpara nueva", tecleado[-1])
            self.assertEqual(rotacion.leer(config), {})
