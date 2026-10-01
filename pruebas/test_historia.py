"""Leer lo último de un hilo: turnos, topes, el respaldo del panel y lo que la puerta no entrega."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import conversacion
from telar import historia as h


def m(quien, texto, hora="2026-10-01T12:00:00.000Z"):
    return {"quien": quien, "hora": hora, "texto": texto}


class Turnos(Prueba):
    def test_un_turno_nuevo_con_cada_mensaje_de_la_persona(self):
        msgs = [m("agente", "hola de antes"), m("usuario", "a"), m("herramienta", "Bash · x"),
                m("agente", "b"), m("usuario", "c"), m("agente", "d")]
        self.assertEqual([[x["texto"] for x in t] for t in h.turnos(msgs)],
                         [["hola de antes"], ["a", "Bash · x", "b"], ["c", "d"]])

    def test_los_ultimos_n(self):
        todos = h.turnos([m("usuario", str(i)) for i in range(10)])
        elegidos, cortado = h.recortar(todos, 3)
        self.assertEqual([t[0]["texto"] for t in elegidos], ["7", "8", "9"])
        self.assertFalse(cortado)


class Topes(Prueba):
    def test_un_mensaje_largo_se_corta_y_lo_dice(self):
        elegidos, cortado = h.recortar([[m("agente", "x" * (h.MAX_MENSAJE + 50))]], 1)
        self.assertTrue(cortado)
        self.assertIn("50 caracteres más", elegidos[0][0]["texto"])

    def test_al_pasarse_del_total_se_sueltan_los_mas_viejos(self):
        grande = [m("usuario", "u")] + [m("agente", "y" * h.MAX_MENSAJE) for _ in range(5)]
        todos = [list(grande) for _ in range(10)]
        elegidos, cortado = h.recortar(todos, 10)
        self.assertTrue(cortado)
        self.assertLess(len(elegidos), 10)
        self.assertLessEqual(sum(len(x["texto"]) for t in elegidos for x in t), h.MAX_TOTAL)

    def test_un_turno_solo_que_no_cabe_se_reparte(self):
        turno = [m("usuario", "u")] + [m("agente", "z" * h.MAX_MENSAJE) for _ in range(40)]
        elegidos, cortado = h.recortar([turno], 1)
        self.assertTrue(cortado)
        self.assertEqual(len(elegidos), 1)
        self.assertLessEqual(sum(len(x["texto"]) for x in elegidos[0]), h.MAX_TOTAL + 41 * 40)


class DeDondeSeLee(Prueba):
    def ctx(self, agente="claude-code"):
        return SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(nombre=agente)))

    def test_la_primera_conversacion_con_archivo(self):
        agente = SimpleNamespace(archivo_de=lambda sid: None if sid == "sin-archivo" else Path(f"/x/{sid}.jsonl"),
                                 mensajes=lambda sid: [m("usuario", sid)])
        hilo = SimpleNamespace(nombre="Faro", id="@1", sesiones=("sin-archivo", "con-archivo"))
        with mock.patch("telar.conversacion._agente", return_value=agente), \
                mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime_ns=1, st_size=1)):
            conversacion._cache.clear()
            d = h.leer(self.ctx(), SimpleNamespace(mux=None), hilo)
        self.assertEqual((d["fuente"], d["conversacion"]), ("conversacion", "con-archivo"))

    def test_sin_conversacion_el_panel_sin_relleno(self):
        mux = SimpleNamespace(pane_de=lambda i: SimpleNamespace(id="%1"),
                              capturar_pane=lambda p, n: "linea uno      \nlinea dos   \n\n")
        hilo = SimpleNamespace(nombre="Faro", id="@1", sesiones=())
        d = h.leer(self.ctx(""), SimpleNamespace(mux=mux, vivo=lambda x: True), hilo)
        self.assertEqual((d["fuente"], d["texto"]), ("panel", "linea uno\nlinea dos"))

    def test_sin_nada_que_leer_es_un_error_que_se_entiende(self):
        hilo = SimpleNamespace(nombre="Faro", id="@1", sesiones=())
        with self.assertRaises(h.ErrorDeHistoria):
            h.leer(self.ctx(""), SimpleNamespace(mux=None), hilo)


class Vetado(Prueba):
    def test_por_nombre_o_por_carpeta_y_lo_de_abajo(self):
        self.assertTrue(h.vetado(["diario"], "Diario", ""))
        self.assertTrue(h.vetado(["personal"], "Finanzas", "personal/finanzas"))
        self.assertTrue(h.vetado(["archivo*"], "x", "archivo-viejo"))
        self.assertFalse(h.vetado(["personal"], "Faro", "proyectos/faro"))
        self.assertFalse(h.vetado([], "Diario", "personal"))
        self.assertFalse(h.vetado(["personal"], "Faro", "personales"))


class ComoTexto(Prueba):
    def test_dice_cuantos_de_cuantos_y_las_herramientas_en_una_linea(self):
        d = {"hilo": "Faro", "fuente": "conversacion", "conversacion": "abcdef123", "total_turnos": 9,
             "turnos": [[m("usuario", "¿y?"), m("herramienta", "Bash · ls"), m("agente", "listo")]], "recortado": True}
        t = h.como_texto(d)
        self.assertIn("1 de 9 turno(s) · conversación abcdef12 · recortado", t)
        self.assertIn("  › Bash · ls", t)
