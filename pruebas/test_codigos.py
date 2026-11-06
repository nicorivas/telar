"""Los códigos de una carpeta y de una conversación (telar.codigos, telar.servicios.codigos, `telar codigos`)."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import codigos as c
from telar.servicios import ErrorDeServicio
from telar.servicios import codigos as servicio

PLAN = """# Faro

## Hipótesis

### H1 — El equipo adopta si el piloto le ahorra tiempo

Se mide con la encuesta de salida.

- dos semanas

### H2: Los líderes empujan

Sin datos todavía.

## Pendientes

| Código | Pendiente | Dueño |
|---|---|---|
| PEN-01 | Mandar el acta | Ana |
| **PEN-02** | Agendar la mesa | |

## Riesgos

- **R1** — el proveedor no entrega a tiempo
  y se corre el piloto
- **R2 — datos**: la base llega incompleta
- **R1 y R2 (los dos)**: se miran juntos
- **R3 con punto.**: el título no queda con dos signos

```
### H9 — esto es un ejemplo dentro de un bloque
| PEN-99 | tampoco |
```
"""


class LasDefiniciones(Prueba):
    def test_las_tres_formas_con_su_seccion(self):
        defs = {d.codigo: d for d in c.definiciones(PLAN, "plan.md")}
        self.assertEqual(sorted(defs), ["H1", "H2", "PEN-01", "PEN-02", "R1", "R2", "R3"])  # «R1 y R2» no define
        h1 = defs["H1"]
        self.assertEqual((h1.forma, h1.titulo, h1.seccion, h1.linea), ("titulo", "El equipo adopta si el piloto le ahorra tiempo", "Hipótesis", 5))
        self.assertIn("encuesta de salida", h1.texto)
        self.assertNotIn("Los líderes", h1.texto)  # la sección termina en el próximo título de su nivel
        self.assertEqual(defs["H2"].seccion, "Hipótesis")  # su sección es la de arriba, no H1
        p1 = defs["PEN-01"]
        self.assertEqual((p1.forma, p1.titulo, p1.seccion), ("fila", "Mandar el acta", "Pendientes"))
        self.assertEqual(p1.campos, {"Pendiente": "Mandar el acta", "Dueño": "Ana"})
        self.assertEqual(defs["PEN-02"].campos, {"Pendiente": "Agendar la mesa"})
        r1 = defs["R1"]
        self.assertEqual((r1.forma, r1.titulo, r1.seccion), ("viñeta", "el proveedor no entrega a tiempo", "Riesgos"))
        self.assertIn("se corre el piloto", r1.texto)
        self.assertEqual(defs["R2"].titulo, "datos: la base llega incompleta")
        self.assertEqual(defs["R3"].titulo, "con punto: el título no queda con dos signos")

    def test_lo_de_un_bloque_de_codigo_no_define(self):
        self.assertFalse({"H9", "PEN-99"} & {d.codigo for d in c.definiciones(PLAN)})

    def test_el_encabezado_de_una_tabla_no_es_una_definicion(self):
        tabla = "| H1 | H2 |\n|---|---|\n| a | b |\n"
        self.assertEqual(c.definiciones(tabla), [])

    def test_un_codigo_suelto_y_no_pegado(self):
        texto = "Cerré PEN-07, queda `REQ-03` por H3.\nISO-14001 no; aH3 no; H3-b no; T84: sí (tarea:T84)"
        self.assertEqual(c.nombrados(texto), {"PEN-07": [1], "REQ-03": [1], "H3": [1], "T84": [2]})


class LaCarpeta(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "plan.md").write_text(PLAN, encoding="utf-8")
        (self.raiz / "notas").mkdir()
        (self.raiz / "notas" / "semana.md").write_text("Avanzó H1 y se cerró PEN-01.\n", encoding="utf-8")
        # cada entrevista numera a su gente desde P01: rótulos de un documento, no cosas del proyecto
        for n in (1, 2):
            (self.raiz / "notas" / f"entrevista-{n}.md").write_text("| P01 | la jefa |\n| P02 | el analista |\n", encoding="utf-8")
        (self.raiz / ".oculta").mkdir()
        (self.raiz / ".oculta" / "x.md").write_text("Nombra R1 y R2.\n", encoding="utf-8")

    def test_quedan_los_que_salen_de_su_archivo(self):
        k = c.carpeta(self.raiz)
        self.assertEqual(k.archivos, 4)  # la carpeta oculta no se recorre
        self.assertEqual(k.viajan(), {"H1", "PEN-01"})
        self.assertEqual(k.fuera("H1"), {os.path.join("notas", "semana.md"): [1]})
        self.assertEqual(len(k.defs["P01"]), 2)

    def test_la_clase_se_nombra_con_su_seccion(self):
        k = c.carpeta(self.raiz)
        clases = {x["prefijo"]: x for x in c.clases(k, k.viajan())}
        self.assertEqual(clases["H"]["nombre"], "Hipótesis")
        self.assertEqual(clases["PEN-"], {"prefijo": "PEN-", "nombre": "Pendientes", "archivo": "plan.md", "cuantos": 1})

    def test_un_archivo_que_cambia_se_relee(self):
        c.carpeta(self.raiz)
        semana = self.raiz / "notas" / "semana.md"
        semana.write_text("Ahora va R1.\n", encoding="utf-8")
        futuro = time.time() + 5
        os.utime(semana, (futuro, futuro))
        self.assertEqual(c.carpeta(self.raiz).viajan(), {"R1"})

    def test_con_varias_definiciones_vale_la_de_la_casa_de_su_clase(self):
        (self.raiz / "promesas.md").write_text("## Vigentes\n\n| P-01 | Mandar el informe |\n| P-02 | Llamar |\n", encoding="utf-8")
        reunion = self.raiz / "reunion.md"
        reunion.write_text("## Cadenas\n\n| P-01 | La cadena de personas |\n\nVer P-02.\n", encoding="utf-8")
        futuro = time.time() + 5
        os.utime(reunion, (futuro, futuro))  # la reunión es más reciente, pero las promesas viven en promesas.md
        k = c.carpeta(self.raiz)
        self.assertEqual(k.defs["P-01"][0].archivo, "reunion.md")
        self.assertEqual(k.principal("P-01").titulo, "Mandar el informe")

    def test_buscar_sin_tildes_ni_mayusculas(self):
        self.assertTrue(c.coincide("hipotesis tiempo", "H1", "El equipo adopta si le ahorra tiempo", "Hipótesis"))
        self.assertFalse(c.coincide("acta", "H1", "El equipo"))


class LaConversacion(Prueba):
    def test_el_ultimo_nombrado_primero_con_lo_que_se_decia(self):
        mensajes = [{"quien": "usuario", "texto": "¿Cómo va PEN-01?"},
                    {"quien": "agente", "texto": "PEN-01 está listo; queda H1, que depende del piloto."},
                    {"quien": "usuario", "texto": "Dale con H1"}]
        n = c.en_conversacion(mensajes)
        self.assertEqual([(x.codigo, x.veces, x.ultimo) for x in n], [("H1", 2, 2), ("PEN-01", 2, 1)])
        self.assertEqual(n[0].extracto, "Dale con H1")


class ElServicio(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "faro"
        self.carpeta.mkdir()
        (self.carpeta / "plan.md").write_text(PLAN, encoding="utf-8")
        (self.carpeta / "semana.md").write_text("Avanzó H1.\n", encoding="utf-8")

    def correr(self, vinculo, mensajes=(), tareas=None, **kw):
        hilo = SimpleNamespace(nombre="Faro", vinculo=vinculo, sesiones=("s1",) if mensajes else ())
        tel = SimpleNamespace(estado=SimpleNamespace(vinculos=lambda: {}))
        config = SimpleNamespace(raiz=str(self.raiz), tipos=(), bus=SimpleNamespace(no_leer=()), puerta=SimpleNamespace(no_leer=()))
        ctx = SimpleNamespace(config=config)
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.ordenes._comun.resolver", return_value=(hilo, "")), \
                mock.patch("telar.conversacion.mensajes_del_hilo", return_value=("s1", list(mensajes), 0)), \
                mock.patch.object(servicio, "_tareas", return_value=tareas or (None, "")), \
                mock.patch("telar.bus.hay_bus", return_value=False):
            return servicio.de_hilo(ctx, "Faro", **kw)

    def test_los_del_proyecto_y_los_de_la_conversacion(self):
        r = self.correr(self.carpeta, [{"quien": "agente", "texto": "Cerré R2 y PEN-77; va T84"}])
        self.assertEqual(r.carpeta, str(self.carpeta))
        # H1 sale a semana.md; R2, a la conversación; PEN-77 no está definido y no hay tareas
        self.assertEqual([f["codigo"] for f in r.codigos], ["H1", "R2"])
        self.assertEqual([x["codigo"] for x in r.conversacion], ["R2"])
        self.assertEqual(r.codigos[1]["en_conversacion"], 1)
        self.assertEqual({k["prefijo"] for k in r.clases}, {"H", "R"})

    def test_una_tarea_de_otra_maquina_va_sin_titulo(self):
        r = self.correr(self.carpeta, [{"quien": "usuario", "texto": "va T84"}], tareas=(None, "servidor"))
        self.assertEqual(r.conversacion[0]["tipo"], "tarea")
        self.assertEqual(r.conversacion[0]["direccion"], "tarea:T84")
        self.assertNotIn("titulo", r.conversacion[0])
        self.assertEqual(r.tareas_en, "servidor")

    def test_una_tarea_de_aqui_con_su_titulo_y_la_que_no_existe_no(self):
        t84 = SimpleNamespace(titulo="Llamar a Ana", estado="activa")

        def obtener(id):
            if id != "T84":
                raise LookupError(id)
            return t84, "v1"
        r = self.correr(self.carpeta, [{"quien": "usuario", "texto": "va T84 y T99"}],
                        tareas=(SimpleNamespace(obtener=obtener), ""))
        self.assertEqual([(x["codigo"], x.get("titulo")) for x in r.conversacion], [("T84", "Llamar a Ana")])

    def test_todas_las_que_nombra_aunque_sea_de_pasada(self):
        mensajes = [{"quien": "agente", "texto": "Sigo con T84; de paso, también está T433."},
                    {"quien": "herramienta", "texto": "Bash · Find the T12 task"}]
        r = self.correr(self.carpeta, mensajes, tareas=(None, "servidor"))
        self.assertEqual([x["codigo"] for x in r.conversacion], ["T12", "T433", "T84"])

    def test_buscar_y_el_detalle(self):
        r = self.correr(self.carpeta, buscar="adopta")
        self.assertEqual([f["codigo"] for f in r.codigos], ["H1"])
        d = self.correr(self.carpeta, codigo="H1").detalle
        self.assertEqual(d["definiciones"][0]["archivo"], "plan.md")
        self.assertEqual(d["nombrado_en"], [{"archivo": "semana.md", "lineas": [1]}])
        with self.assertRaises(ErrorDeServicio):
            self.correr(self.carpeta, codigo="Z9")

    def test_sin_carpeta_o_en_la_raiz_no_se_recorre(self):
        self.assertIn("sin carpeta", self.correr(None).aviso)
        r = self.correr(self.raiz)
        self.assertEqual((r.carpeta, r.codigos), ("", []))
        self.assertIn("raíz", r.aviso)
