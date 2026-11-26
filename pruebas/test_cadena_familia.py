"""El freno de cadenas entre un padre y su hijo (telar.casilla.cadena_familia): su conversación lleva una cuenta
aparte, que no suma a la cadena de ninguno y vuelve a empezar con un commit en la carpeta del hijo; el tope sigue para
lo demás. Sin bus real: `telar.bus.enviar` deja el mensaje en la casilla de aquí, como lo haría el nodo, y entregarlo
es lo que hace el gancho (`casilla.para_gancho`)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import casilla
from telar import config as mod_config
from telar import estado as mod_estado
from telar.ordenes import mensaje


def git(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


class _Familia(Prueba):
    """«Telar» (el padre) con su hijo «Ritmo», que trabaja en su worktree (un repositorio de verdad), y «Secretaría», que
    no es de la familia."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name).resolve()
        self.config = mod_config.Config(raiz=self.raiz, estado=self.raiz / "estado",
                                        bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        self.ctx = SimpleNamespace(config=self.config)
        self.worktree = self.raiz / "worktrees" / "codigo-ritmo"
        self.worktree.mkdir(parents=True)
        git(self.worktree, "init", "-q", "-b", "ritmo")
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            git(self.worktree, "config", k, v)
        self.commit("a.txt", "uno")
        est = mod_estado.abrir(self.config)
        est.colgar("Ritmo", "Telar")
        est.anotar_rama("Ritmo", {"rama": "ritmo", "base": "main", "ruta": str(self.worktree)})
        self.enviados: list[dict] = []
        self.registro: list[dict] = []
        # los hilos de juguete no están en ningún estado: que el destino exista lo prueba test_mensaje_arroba
        p = mock.patch("telar.ordenes.mensaje._alguien_lee")
        p.start()
        self.addCleanup(p.stop)

        def enviar(config, para, texto, *, de, tipo="mensaje", quien="", saltos=0, mid="", retener="", **kw):
            m = mod_bus.mensaje(texto, de=de, para=para, tipo=tipo, mid=mid, persona="ana", saltos=saltos, **kw)
            self.enviados.append(m)
            if retener:
                self.registro.append({**m, "estado": "retenido", "motivo": retener})
                return {**m, "estado": "retenido", "motivo": retener}
            self.registro.append({**m, "estado": "enviado"})
            casilla.dejar(config, para, m)
            return {**m, "secuencia": len(self.enviados), "duplicado": False}

        for objetivo, nombre, valor in ((mod_bus, "enviar", dict(side_effect=enviar)),
                                        (mod_bus, "registro", dict(side_effect=lambda config, n=0: list(self.registro))),
                                        (mensaje, "_por_nombre", dict(side_effect=lambda ctx, para: para)),
                                        (mensaje, "_exacto", dict(side_effect=lambda ctx, para: para)),
                                        (mensaje, "despertar", dict(return_value={}))):
            p = mock.patch.object(objetivo, nombre, **valor)
            p.start()
            self.addCleanup(p.stop)

    def commit(self, archivo: str, texto: str) -> None:
        (self.worktree / archivo).write_text(texto + "\n")
        git(self.worktree, "add", archivo)
        git(self.worktree, "commit", "-q", "-m", texto)

    def de(self, hilo: str, para: str, texto: str = "…") -> dict:
        """`hilo` le escribe a `para` y, si salió, `para` lo recibe (su gancho lo entrega)."""
        with mock.patch.dict(os.environ, {"TELAR_HILO": hilo}):
            r = mensaje.enviar(self.ctx, para, texto)
        if r.get("estado") != "retenido":
            casilla.para_gancho(self.config, para, "UserPromptSubmit", casilla.AVISO)
        return r


class LaConversacionDePadreEHijo(_Familia):
    def test_el_listo_despues_de_traer_main_llega_aunque_el_padre_lleve_una_cadena_larga(self):
        # el padre viene de hablar con otros: su cadena está al tope
        casilla.anotar_cadena(self.config, "Telar", casilla.TOPE_SALTOS)
        listo = self.de("Ritmo", "Telar", "listo")
        self.assertNotEqual(listo.get("estado"), "retenido")
        self.assertEqual((listo["saltos"], listo["familia"]["saltos"]), (0, 1))
        # no le suma al padre, y el padre le contesta sin tope
        self.assertEqual(casilla.cadena(self.config, "Telar"), casilla.TOPE_SALTOS)
        pedido = self.de("Telar", "Ritmo", "haz git merge main")
        self.assertNotEqual(pedido.get("estado"), "retenido")
        self.assertEqual(pedido["familia"], {"padre": "Telar", "hijo": "Ritmo", "saltos": 2})
        # el hijo trae main (un commit) y su segundo listo vuelve a empezar la cuenta
        self.commit("b.txt", "merge main")
        otra = self.de("Ritmo", "Telar", "listo otra vez")
        self.assertNotEqual(otra.get("estado"), "retenido")
        self.assertEqual(otra["familia"]["saltos"], 1)

    def test_sin_trabajo_de_por_medio_el_tope_frena_a_los_dos(self):
        hablan = ["Ritmo", "Telar"] * 4
        for i, quien in enumerate(hablan[:casilla.TOPE_SALTOS]):
            r = self.de(quien, "Telar" if quien == "Ritmo" else "Ritmo")
            self.assertEqual((r["familia"]["saltos"], r.get("estado")), (i + 1, None))
        r = self.de(hablan[casilla.TOPE_SALTOS], "Telar" if hablan[casilla.TOPE_SALTOS] == "Ritmo" else "Ritmo")
        self.assertEqual(r["estado"], "retenido")
        self.assertIn("entre «Telar» y su hijo «Ritmo»", r["motivo"])
        self.assertIn(f"tope {casilla.TOPE_SALTOS}", r["motivo"])

    def test_el_mismo_que_vuelve_a_escribir_no_encadena(self):
        uno = self.de("Ritmo", "Telar", "voy en la mitad")
        dos = self.de("Ritmo", "Telar", "listo")
        self.assertEqual((uno["familia"]["saltos"], dos["familia"]["saltos"]), (1, 1))

    def test_la_persona_que_habla_corta_la_cuenta(self):
        for quien, para in (("Ritmo", "Telar"), ("Telar", "Ritmo"), ("Ritmo", "Telar")):
            self.de(quien, para)
        casilla.para_gancho(self.config, "Telar", "UserPromptSubmit", "¿cómo va Ritmo?")
        self.assertEqual(self.de("Telar", "Ritmo")["familia"]["saltos"], 1)

    def test_soltar_uno_retenido_vuelve_a_empezar(self):
        casilla.anotar_familia(self.config, "Telar", "Ritmo", casilla.TOPE_SALTOS, "Telar")
        r = self.de("Ritmo", "Telar", "¿fusionas?")
        self.assertEqual(r["estado"], "retenido")
        mensaje.soltar(self.ctx, r["id"])
        self.assertEqual(self.de("Telar", "Ritmo", "fusionado")["familia"]["saltos"], 1)

    def test_lo_dice_al_entregarlo(self):
        self.de("Telar", "Ritmo", "haz esto")
        casilla.dejar(self.config, "Ritmo", self.enviados[-1])
        texto, _ = casilla.como_texto([self.enviados[-1]], "ana")
        self.assertIn(f"1 de {casilla.TOPE_SALTOS} entre padre e hijo", texto)
        self.assertEqual(casilla.de_entrega(texto), "hilos")


class ElTopeSigueParaLoDemas(_Familia):
    def test_el_padre_a_otro_hilo_sigue_frenado(self):
        casilla.anotar_cadena(self.config, "Telar", casilla.TOPE_SALTOS)
        r = self.de("Telar", "Secretaría", "¿seguimos?")
        self.assertEqual(r["estado"], "retenido")
        self.assertEqual(r["saltos"], casilla.TOPE_SALTOS + 1)
        self.assertNotIn("familia", r)

    def test_un_nieto_no_es_hijo_directo(self):
        mod_estado.abrir(self.config).colgar("Compás", "Ritmo")
        casilla.anotar_cadena(self.config, "Telar", casilla.TOPE_SALTOS)
        r = self.de("Telar", "Compás", "hola")
        self.assertEqual(r["estado"], "retenido")

    def test_el_tope_por_hora_vale_tambien_en_la_familia(self):
        with mock.patch.object(mensaje, "_enviados_esta_hora", return_value=mensaje.TOPE_HORA):
            r = self.de("Ritmo", "Telar", "listo")
        self.assertEqual(r["estado"], "retenido")
        self.assertIn("esta hora", r["motivo"])
