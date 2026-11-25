"""Los comentarios de un archivo (telar.anclaje, telar.comentarios, telar.servicios.comentarios, `telar comentarios`,
`GET/POST /comentarios` y el tipo `comentario`): el ancla que vuelve a encontrar lo comentado aunque el documento cambie,
el archivo de al lado en el formato de la extensión de editor que lo inventó (y su CLI, si está, lo lee igual), lo que la
página y un agente le hacen, los límites, la otra máquina por el bus y el commit de solo ese archivo."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import anclaje
from telar import comentarios as mod
from telar.config import Config
from telar.servicios import ErrorDeServicio
from telar.servicios import comentarios as servicio

try:
    import fastapi  # noqa: F401

    HAY_FASTAPI = True
except ImportError:
    HAY_FASTAPI = False

DOC = """# Informe de adopción

## Diagnóstico

El 62% de los encuestados declara usar la herramienta a diario.
La cifra viene de la encuesta interna de junio.

## Recomendaciones

Se recomienda avanzar en tres frentes antes de cerrar el trimestre.
"""

#: un .md lleno de markdown, como lo comenta la página (el ancla va contra la fuente, con su formato adentro)
LLENO = """# Informe **de** adopción

El **62%** de los encuestados declara usar la [herramienta](https://x.example/a_(b) "título") a diario (¿o no?).
La cifra viene de la encuesta interna de junio, y se repite: la cifra viene de la encuesta.

- uno con *énfasis* y `código`
- dos con un [enlace relativo](otro.md)

| col a | col **b** |
|---|---|
| celda 1 | celda [dos](http://y.example) |

```python
print("hola")  # la cifra viene
```

> una cita con &amp; entidad 🎉 y después más texto
"""


def anclar(doc: str, cita: str, n: int = 0) -> anclaje.Ancla:
    i = -1
    for _ in range(n + 1):
        i = doc.index(cita, i + 1)
    return anclaje.derivar(doc, i, i + len(cita))


class ElAncla(Prueba):
    """Los cinco caminos, como los de la extensión (sus mismas pruebas, traídas aquí)."""

    def test_guarda_la_cita_y_su_vecindario(self):
        a = anclar(DOC, "El 62% de los encuestados")
        self.assertEqual(a.cita, "El 62% de los encuestados")
        self.assertTrue(a.antes.endswith("\n"))
        self.assertTrue(a.despues.startswith(" declara"))
        self.assertLessEqual(len(a.antes), anclaje.CONTEXTO)

    def test_exacto_y_movido(self):
        a = anclar(DOC, "El 62% de los encuestados")
        r = anclaje.resolver(DOC, a)
        self.assertEqual((r.metodo, DOC[r.inicio:r.fin]), ("exacto", "El 62% de los encuestados"))
        movido = DOC.replace("# Informe de adopción", "# Informe de adopción\n\n> Borrador, agosto 2026.")
        r = anclaje.resolver(movido, a)
        self.assertEqual((r.metodo, movido[r.inicio:r.fin]), ("exacto", "El 62% de los encuestados"))
        self.assertGreater(r.inicio, a.inicio)

    def test_contexto_entre_repeticiones(self):
        doc = "\n\n".join(["La cifra clave es 62%.", "Un párrafo cualquiera en el medio del documento que separa las dos.",
                           "La cifra clave es 62%."])
        segunda = doc.rindex("La cifra clave es 62%.")
        r = anclaje.resolver(doc, anclaje.derivar(doc, segunda, segunda + len("La cifra clave es 62%.")))
        self.assertEqual((r.metodo, r.inicio), ("contexto", segunda))

    def test_normalizado_un_parrafo_reenvuelto(self):
        frase = "Se recomienda avanzar en tres frentes antes de cerrar el trimestre."
        a = anclar(DOC, frase)
        reenvuelto = DOC.replace(frase, "Se recomienda avanzar en tres\nfrentes antes de cerrar el\ntrimestre.")
        r = anclaje.resolver(reenvuelto, a)
        self.assertEqual(r.metodo, "normalizado")
        self.assertEqual(" ".join(reenvuelto[r.inicio:r.fin].split()), frase)

    def test_aproximado_editada_por_dentro(self):
        a = anclar(DOC, "El 62% de los encuestados declara usar la herramienta a diario.")
        editado = DOC.replace("El 62% de los encuestados", "El 58% de las personas encuestadas")
        r = anclaje.resolver(editado, a)
        self.assertEqual(r.metodo, "aproximado")
        self.assertGreaterEqual(r.confianza, 0.6)
        self.assertIn("usar la herramienta a diario", editado[r.inicio:r.fin])

    def test_vecindario_con_los_dos_lados(self):
        a = anclar(DOC, "El 62% de los encuestados")
        corregido = DOC.replace("El 62% de los encuestados", "Cuatro de cada siete participantes")
        r = anclaje.resolver(corregido, a)
        self.assertEqual((r.metodo, corregido[r.inicio:r.fin]), ("vecindario", "Cuatro de cada siete participantes"))

    def test_vecindario_con_un_lado_sin_ancho(self):
        frase = "Se recomienda avanzar en tres frentes antes de cerrar el trimestre."
        a = anclar(DOC, frase)
        sin = DOC.replace(frase, "Nada de esto aplica; el proyecto se archivó por falta de presupuesto.")
        r = anclaje.resolver(sin, a)
        self.assertEqual((r.metodo, r.inicio == r.fin), ("vecindario", True))
        self.assertLessEqual(r.confianza, 0.3)
        self.assertEqual(sin[r.inicio:r.inicio + 9], "Nada de e")

    def test_no_ancla_en_un_documento_ajeno(self):
        a = anclar(DOC, "El 62% de los encuestados declara usar la herramienta a diario.")
        self.assertIsNone(anclaje.resolver("# Recetas\n\nHervir el agua, agregar la sal y esperar diez minutos.\n", a))

    def test_ancla_vacia_y_utilidades(self):
        r = anclaje.resolver(DOC, anclaje.Ancla(cita="", inicio=10, fin=10))
        self.assertEqual((r.inicio, r.fin), (10, 10))
        self.assertEqual(anclaje.similitud("hola mundo", "hola mundo"), 1)
        self.assertLess(anclaje.similitud("hola mundo", "chao planeta"), 0.2)
        self.assertGreater(anclaje.similitud("el 62% de los encuestados", "el 58% de los encuestados"), 0.8)
        self.assertEqual((anclaje.linea_de(DOC, 0), anclaje.linea_de(DOC, DOC.index("El 62%"))), (1, 5))

    def test_recortar_blancos(self):
        i, f = DOC.index("El 62%"), DOC.index("La cifra viene")
        self.assertEqual(DOC[slice(*anclaje.recortar_blancos(DOC, i, f))],
                         "El 62% de los encuestados declara usar la herramienta a diario.")
        self.assertEqual(anclaje.recortar_blancos(DOC, i, i + 6), (i, i + 6))
        j = DOC.index("\n\n")
        self.assertEqual(anclaje.recortar_blancos(DOC, j, j + 2), (j, j + 2))

    def test_las_posiciones_como_las_cuenta_javascript(self):
        texto = "a🎉b🎉c"
        self.assertEqual([anclaje.a_utf16(texto, i) for i in range(6)], [0, 1, 3, 4, 6, 7])
        self.assertEqual([anclaje.de_utf16(texto, u) for u in (0, 1, 2, 3, 4, 6, 7, 99)], [0, 1, 1, 2, 3, 4, 5, 5])


class UnMarkdownLleno(Prueba):
    """El ancla contra la fuente de un .md con formato: lo que manda la página al comentar (el tramo de la fuente que
    calzó con lo seleccionado), y lo que el agente encuentra después de editar."""

    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.md = Path(d.name) / "lleno.md"
        self.md.write_text(LLENO, encoding="utf-8")

    def comentar(self, cita: str, texto: str = "revisar", n: int = 0) -> dict:
        i = -1
        for _ in range(n + 1):
            i = LLENO.index(cita, i + 1)
        return mod.comentar(self.md, anclaje.a_utf16(LLENO, i), anclaje.a_utf16(LLENO, i + len(cita)), texto, "Persona", cita=cita)

    def test_cada_cita_con_su_formato_vuelve_a_su_lugar(self):
        citas = ["**62%** de los encuestados", 'usar la [herramienta](https://x.example/a_(b) "título") a diario',
                 "(¿o no?)", "*énfasis* y `código`", "[enlace relativo](otro.md)", "col **b**", "celda [dos](http://y.example)",
                 'print("hola")', "una cita con &amp; entidad", "y después más texto"]
        for c in citas:
            h = self.comentar(c)
            self.assertEqual((h["metodo"], h["cita"]), ("exacto", c), c)
        # la que va después del emoji guarda su posición como la cuenta JavaScript (una unidad más)
        datos = json.loads(mod.lateral(self.md).read_text(encoding="utf-8"))
        ultimo = datos["hilos"][-1]["ancla"]
        self.assertEqual(ultimo["inicio"], anclaje.a_utf16(LLENO, LLENO.index("y después más texto")))
        self.assertEqual(ultimo["inicio"], LLENO.index("y después más texto") + 1)
        # una frase repetida: la del párrafo, no la del bloque de código
        h = self.comentar("la cifra viene", n=0)
        self.assertEqual((h["linea"], h["metodo"]), (4, "contexto"))

    def test_el_agente_edita_y_los_comentarios_siguen_donde_van(self):
        h1 = self.comentar("**62%** de los encuestados", "esta cifra no cuadra")
        h2 = self.comentar("celda [dos](http://y.example)", "¿y esta celda?")
        h3 = self.comentar("una cita con &amp; entidad", "sácala")
        nuevo = LLENO.replace("**62%** de los encuestados", "**58%** de las personas encuestadas") \
            .replace("\n- uno", "\n> Borrador.\n\n- uno") \
            .replace("> una cita con &amp; entidad 🎉 y después más texto\n", "")
        self.md.write_text(nuevo, encoding="utf-8")
        hilos = {h["id"]: h for h in mod.ubicar(self.md)}
        # lo corregido: en el hueco que dejó, y dice qué hay hoy
        self.assertEqual(hilos[h1["id"]]["metodo"], "vecindario")
        self.assertEqual(hilos[h1["id"]]["actual"], "**58%** de las personas encuestadas")
        # lo que solo se corrió: exacto, dos líneas más abajo
        self.assertEqual((hilos[h2["id"]]["metodo"], hilos[h2["id"]]["linea"]), ("exacto", h2["linea"] + 2))
        # lo que se fue entero, con la marca de cita que lo abría: sin ancla, y al final
        self.assertEqual((hilos[h3["id"]]["anclado"], hilos[h3["id"]]["linea"]), (False, None))
        self.assertEqual([h["id"] for h in mod.ubicar(self.md)][-1], h3["id"])
        # lo que se fue con lo que le seguía, pero queda lo de antes: «era por aquí», sin ancho y con poca confianza
        self.md.write_text(nuevo.replace("tres", "x") + "\nY un párrafo final que no tiene nada que ver.\n", encoding="utf-8")
        h4 = mod.comentar(self.md, anclaje.a_utf16(self.md.read_text(), self.md.read_text().index("nada que ver")),
                          anclaje.a_utf16(self.md.read_text(), self.md.read_text().index("nada que ver") + 12), "x", "Persona")
        self.md.write_text(self.md.read_text().replace("nada que ver.\n", "otra cosa"), encoding="utf-8")
        h = next(x for x in mod.ubicar(self.md) if x["id"] == h4["id"])
        self.assertEqual((h["metodo"], h["inicio"] == h["fin"], h["confianza"]), ("vecindario", True, 0.3))
        # y en un documento que ya no es el mismo, ninguno: sin ancla, al final, sin inventar un lugar
        self.md.write_text("# Recetas\n\nHervir el agua y esperar diez minutos.\n", encoding="utf-8")
        self.assertEqual([(h["anclado"], h["linea"]) for h in mod.ubicar(self.md)], [(False, None)] * 4)


class ElArchivoDeAlLado(Prueba):
    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.md = self.dir / "informe.md"
        self.md.write_text(DOC, encoding="utf-8")

    def comentar(self, cita: str, texto: str = "Esta cifra no cuadra.", autor: str = "Persona") -> dict:
        i = DOC.index(cita)
        return mod.comentar(self.md, i, i + len(cita), texto, autor, cita=cita)

    def test_la_forma_es_la_de_siempre(self):
        self.assertEqual(mod.lateral(self.md), self.dir / ".informe.md.marginalia.json")
        self.assertEqual(mod.documento_de(self.dir / ".informe.md.marginalia.json"), self.md)
        self.assertIsNone(mod.documento_de(self.dir / "informe.md"))
        self.comentar("El 62% de los encuestados")
        crudo = mod.lateral(self.md).read_text(encoding="utf-8")
        # como JSON.stringify(…, null, 2) + "\n": las claves en su orden, sin escapar lo que no es ASCII
        self.assertTrue(crudo.endswith("}\n"))
        self.assertIn('"archivo": "informe.md"', crudo)
        datos = json.loads(crudo)
        self.assertEqual(list(datos), ["version", "archivo", "hilos"])
        h = datos["hilos"][0]
        self.assertEqual(list(h), ["id", "estado", "ancla", "creado", "comentarios"])
        self.assertEqual(list(h["ancla"]), ["cita", "antes", "despues", "inicio", "fin"])
        self.assertEqual(list(h["comentarios"][0]), ["id", "autor", "cuerpo", "fecha"])
        self.assertEqual((h["id"], h["estado"], h["comentarios"][0]["id"]), ("h1", "abierto", "c1"))
        self.assertIn("ó", crudo, "sin \\u00f3")
        self.assertRegex(h["creado"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        self.assertEqual(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", crudo)
        self.assertEqual(mod.lateral(self.md).stat().st_mode & 0o777, 0o644)

    def test_lee_lo_que_escribe_el_otro_y_conserva_lo_que_no_conoce(self):
        # uno escrito por la extensión de editor, con un campo que telar no conoce
        mod.lateral(self.md).write_text(json.dumps({"version": 1, "archivo": "informe.md", "otro": True, "hilos": [{
            "id": "h7", "estado": "abierto", "creado": "2026-08-12T09:00:00-04:00", "propio": "x",
            "ancla": {"cita": "tres frentes", "antes": "Se recomienda avanzar en ", "despues": " antes de cerrar", "inicio": 0, "fin": 0},
            "comentarios": [{"id": "c1", "autor": "Persona", "cuerpo": "¿cuáles?", "fecha": "2026-08-12T09:00:00-04:00"}]}]},
            indent=2) + "\n", encoding="utf-8")
        [h] = mod.ubicar(self.md)
        self.assertEqual((h["id"], h["metodo"], h["linea"]), ("h7", "exacto", 10))
        mod.responder(self.md, "h7", "Tres: A, B y C.", "agente")
        datos = json.loads(mod.lateral(self.md).read_text(encoding="utf-8"))
        self.assertTrue(datos["otro"])
        self.assertEqual(datos["hilos"][0]["propio"], "x")
        self.assertEqual([c["id"] for c in datos["hilos"][0]["comentarios"]], ["c1", "c2"])
        # el siguiente hilo, uno más que el mayor
        self.assertEqual(self.comentar("El 62% de los encuestados")["id"], "h8")

    def test_responder_resolver_reabrir_editar_y_borrar(self):
        h = self.comentar("El 62% de los encuestados")
        mod.responder(self.md, h["id"], "Corregido.", "agente")
        r = mod.resolver(self.md, h["id"], "Hecho: cita el anexo B.", "agente")
        self.assertEqual((r["estado"], [c["cuerpo"] for c in r["comentarios"]]),
                         ("resuelto", ["Esta cifra no cuadra.", "Corregido.", "Hecho: cita el anexo B."]))
        self.assertEqual(mod.reabrir(self.md, h["id"])["estado"], "abierto")
        self.assertEqual(mod.editar(self.md, h["id"], "c1", "  La cifra no cuadra.  ")["comentarios"][0]["cuerpo"], "La cifra no cuadra.")
        self.assertEqual([c["id"] for c in mod.borrar(self.md, h["id"], "c2")["comentarios"]], ["c1", "c3"])
        self.assertEqual(mod.ubicar(self.md, todos=False)[0]["id"], h["id"])
        # el hilo entero; sin hilos, el archivo de al lado se va
        self.assertIsNone(mod.borrar(self.md, h["id"]))
        self.assertFalse(mod.lateral(self.md).exists())
        self.assertEqual(mod.ubicar(self.md), [])

    def test_lo_que_no_se_puede(self):
        with self.assertRaises(mod.ErrorDeComentarios) as e:
            self.comentar("El 62% de los encuestados", "   ")
        self.assertEqual(e.exception.codigo, 422)
        h = self.comentar("El 62% de los encuestados")
        for hacer, codigo in ((lambda: mod.responder(self.md, "h9", "x", "a"), 404),
                              (lambda: mod.editar(self.md, h["id"], "c9", "x"), 404),
                              (lambda: mod.editar(self.md, h["id"], "c1", " "), 422),
                              (lambda: mod.responder(self.md, h["id"], "", "a"), 422)):
            with self.assertRaises(mod.ErrorDeComentarios) as e:
                hacer()
            self.assertEqual(e.exception.codigo, codigo)
        # un archivo de al lado que no se entiende no se pisa
        mod.lateral(self.md).write_text("{roto", encoding="utf-8")
        with self.assertRaises(mod.ErrorDeComentarios) as e:
            self.comentar("tres frentes")
        self.assertEqual(e.exception.codigo, 409)
        self.assertEqual(mod.lateral(self.md).read_text(encoding="utf-8"), "{roto")

    def test_si_el_texto_cambio_desde_que_se_selecciono(self):
        i = DOC.index("tres frentes")
        # se movió: se lo busca, y queda donde está ahora
        self.md.write_text("Nuevo párrafo arriba.\n\n" + DOC, encoding="utf-8")
        h = mod.comentar(self.md, i, i + len("tres frentes"), "¿cuáles?", "Persona", cita="tres frentes",
                         antes="Se recomienda avanzar en ", despues=" antes de cerrar")
        self.assertEqual((h["cita"], h["linea"]), ("tres frentes", 12))
        # ya no está: 409, no un comentario en otra parte
        self.md.write_text(DOC.replace("tres frentes", "dos líneas"), encoding="utf-8")
        with self.assertRaises(mod.ErrorDeComentarios) as e:
            mod.comentar(self.md, i, i + 12, "¿cuáles?", "Persona", cita="tres frentes")
        self.assertEqual(e.exception.codigo, 409)
        # el salto de línea que se lleva el mouse se recorta
        j = DOC.index("El 62%")
        self.md.write_text(DOC, encoding="utf-8")
        h = mod.comentar(self.md, j, DOC.index("La cifra viene"), "todo", "Persona")
        self.assertEqual(h["cita"], "El 62% de los encuestados declara usar la herramienta a diario.")

    def test_buscar_los_de_una_carpeta(self):
        self.comentar("El 62% de los encuestados")
        (self.dir / "sub" / "node_modules").mkdir(parents=True)
        for p in (self.dir / "sub" / "b.md", self.dir / "sub" / "node_modules" / "c.md"):
            p.write_text("hola mundo, aquí hay texto\n", encoding="utf-8")
            mod.comentar(p, 0, 4, "x", "Persona")
        self.assertEqual(mod.buscar(self.dir), [self.md, self.dir / "sub" / "b.md"])
        self.assertEqual(mod.buscar(self.md), [self.md])


class ElServicio(Prueba):
    """Lo que la página y el bus pueden: los límites de la página, y el commit de solo ese archivo."""

    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        base = Path(d.name).resolve()
        self.raiz = base / "vida"
        (self.raiz / "docs").mkdir(parents=True)
        self.md = self.raiz / "docs" / "informe.md"
        self.md.write_text(DOC, encoding="utf-8")
        (base / "afuera.md").write_text(DOC, encoding="utf-8")
        self.afuera = base / "afuera.md"
        self.ctx = SimpleNamespace(config=Config(raiz=self.raiz, estado=base / "estado"))

    def pedido(self, **kw) -> servicio.Pedido:
        return servicio.Pedido(**{"ruta": "docs/informe.md", **kw})

    def comentar(self, cita="El 62% de los encuestados", **kw):
        i = DOC.index(cita)
        return servicio.hacer(self.ctx, self.pedido(accion="comentar", inicio=i, fin=i + len(cita), cita=cita,
                                                    texto="no cuadra", autor="Persona", **kw), subir="no")

    def test_comentar_ver_y_cambiar(self):
        c = self.comentar()
        self.assertEqual((c.hecho, [h.id for h in c.hilos], c.hilos[0].metodo, c.hilos[0].linea), ("h1", ["h1"], "exacto", 5))
        self.assertEqual(Path(c.lateral), self.raiz / "docs" / ".informe.md.marginalia.json")
        c = servicio.hacer(self.ctx, self.pedido(accion="resolver", hilo="h1", texto="hecho", autor="agente"), subir="no")
        self.assertEqual((c.hilos[0].estado, c.hilos[0].comentarios[-1].autor), ("resuelto", "agente"))
        self.assertEqual(servicio.ver(self.ctx, "docs/informe.md").hilos[0].estado, "resuelto")
        # pedir el archivo de al lado es pedir el documento
        self.assertEqual(servicio.ver(self.ctx, "docs/.informe.md.marginalia.json").hilos[0].id, "h1")

    def test_los_limites(self):
        for ruta, codigo in ((str(self.afuera), 403), ("docs/no-hay.md", 404), ("", 422)):
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.ver(self.ctx, ruta)
            self.assertEqual(e.exception.codigo, codigo, ruta)
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.hacer(self.ctx, self.pedido(accion="responder", texto="x"), subir="no")
        self.assertEqual(e.exception.codigo, 422, "sin hilo")
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.hacer(self.ctx, self.pedido(accion="inventar"), subir="no")
        self.assertEqual(e.exception.codigo, 422)
        # `telar comentarios`, desde una carpeta: una ruta relativa a ella, y cualquier archivo (los límites son de la página)
        self.assertEqual(servicio.ver(self.ctx, "afuera.md", desde=self.afuera.parent).hilos, [])

    def test_listar_una_carpeta(self):
        self.comentar()
        servicio.hacer(self.ctx, self.pedido(accion="resolver", hilo="h1"), subir="no")
        self.comentar("tres frentes")
        lst = servicio.listar(self.ctx, "docs")
        self.assertEqual([[h.id for h in c.hilos] for c in lst.archivos], [["h2"]], "solo los abiertos")
        self.assertEqual([[h.id for h in c.hilos] for c in servicio.listar(self.ctx, "", todos=True).archivos], [["h1", "h2"]])

    def test_el_commit_lleva_solo_ese_archivo(self):
        from telar import bus

        git = lambda *a: subprocess.run(["git", "-C", str(self.raiz), *a], capture_output=True, text=True, check=True)  # noqa: E731
        git("init", "-q")
        git("config", "user.name", "Persona de prueba")
        git("config", "user.email", "p@example.com")
        git("add", "-A")
        git("commit", "-qm", "inicio")
        (self.raiz / "a-medias.md").write_text("lo de otro, sin commitear\n", encoding="utf-8")
        i = DOC.index("tres frentes")
        c = servicio.hacer(self.ctx, self.pedido(accion="comentar", inicio=i, fin=i + 12, texto="¿cuáles?"), subir="ya")
        self.assertEqual(c.hilos[0].comentarios[0].autor, "Persona de prueba", "firma el user.name de git del repositorio")
        self.assertEqual(git("log", "-1", "--name-only", "--format=%s").stdout.split(),
                         ["comentarios:", "informe.md", f"({bus.maquina(self.ctx.config)})", "docs/.informe.md.marginalia.json"])
        self.assertIn("a-medias.md", git("status", "--porcelain").stdout, "lo de otro, intacto")
        # al borrar el último, el commit lleva que se fue
        servicio.hacer(self.ctx, self.pedido(accion="borrar", hilo="h1"), subir="ya")
        self.assertEqual(git("log", "-1", "--name-status", "--format=").stdout.split(), ["D", "docs/.informe.md.marginalia.json"])

    def test_al_rato_desde_la_pagina(self):
        with mock.patch("telar.temas.subir_luego") as luego:
            i = DOC.index("tres frentes")
            servicio.hacer(self.ctx, self.pedido(accion="comentar", inicio=i, fin=i + 12, texto="x"))
        self.assertEqual(luego.call_args.kwargs["archivo"], self.raiz / "docs" / ".informe.md.marginalia.json")
        self.assertEqual(luego.call_args.kwargs["espera"], servicio.ESPERA)


class EnOtraMaquina(Prueba):
    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.raiz = Path(d.name).resolve()
        (self.raiz / "x.md").write_text(DOC, encoding="utf-8")
        self.ctx = SimpleNamespace(config=Config(raiz=self.raiz, estado=self.raiz / "estado"))
        for nombre, valor in (("hay_bus", True), ("maquina", "laptop")):
            p = mock.patch(f"telar.bus.{nombre}", return_value=valor)
            p.start()
            self.addCleanup(p.stop)

    def test_leer_y_comentar_por_el_bus(self):
        # lo que contesta el nodo de allá es lo que da su servicio: se prueba con el de aquí
        def pedir(config, maquina, verbo, datos, espera=30):
            self.assertEqual((maquina, verbo), ("servidor", "comentarios"))
            pedir.datos.append(datos)
            return servicio.para_otra(self.ctx, datos)

        pedir.datos = []
        with mock.patch("telar.bus.pedir", side_effect=pedir), mock.patch("telar.temas.subir_luego"):
            i = DOC.index("tres frentes")
            c = servicio.hacer_en(self.ctx, servicio.Pedido(ruta="servidor:x.md", accion="comentar", inicio=i, fin=i + 12,
                                                             cita="tres frentes", texto="¿cuáles?"))
            self.assertEqual((c.ruta, c.maquina, c.hilos[0].cita), ("servidor:x.md", "servidor", "tres frentes"))
            self.assertEqual(pedir.datos[-1]["pedido"]["ruta"], "x.md", "allá, sin la máquina delante")
            self.assertEqual(servicio.ver_en(self.ctx, "servidor:x.md").hilos[0].id, "h1")
            self.assertEqual(pedir.datos[-1], {"ruta": "x.md"})
            lst = servicio.listar_en(self.ctx, "servidor:.")
            self.assertEqual([c.ruta for c in lst.archivos], [f"servidor:{self.raiz / 'x.md'}"])
        # de esta misma máquina, sin bus de por medio
        with mock.patch("telar.bus.pedir") as pedir2:
            self.assertEqual(servicio.ver_en(self.ctx, "laptop:x.md").hilos[0].id, "h1")
        pedir2.assert_not_called()

    def test_un_telar_de_antes_allá(self):
        with mock.patch("telar.bus.pedir", return_value={"ok": False, "sin_servicio": True, "error": "servidor no atiende «comentarios»"}):
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.ver_en(self.ctx, "servidor:x.md")
        self.assertIn("telar de antes", str(e.exception))

    def test_lo_que_responde_el_nodo(self):
        self.assertEqual(servicio.para_otra(self.ctx, {"ruta": "no-hay.md"})["codigo"], 404)
        self.assertEqual(servicio.para_otra(self.ctx, {"pedido": {"ruta": "x.md"}})["codigo"], 422)
        self.assertTrue(servicio.para_otra(self.ctx, {"listar": ""})["ok"])
        from telar.ordenes import nodo

        self.assertNotIn("comentarios", nodo.SOLO_LEEN, "escribe: de a uno")


class LaApi(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.raiz = Path(d.name).resolve()
        (self.raiz / "informe.md").write_text(DOC, encoding="utf-8")
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=Config(raiz=self.raiz, estado=self.raiz / ".estado"))
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)
        p = mock.patch("telar.temas.subir_luego")
        self.luego = p.start()
        self.addCleanup(p.stop)

    def test_comentar_y_responder(self):
        self.assertEqual(self.c.get("/comentarios", params={"ruta": "informe.md"}).json()["hilos"], [])
        i = DOC.index("tres frentes")
        r = self.c.post("/comentarios", json={"ruta": "informe.md", "accion": "comentar", "inicio": i, "fin": i + 12,
                                              "cita": "tres frentes", "antes": DOC[i - 48:i], "despues": DOC[i + 12:i + 60],
                                              "texto": "¿cuáles?"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual((j["hecho"], j["hilos"][0]["linea"], j["hilos"][0]["inicio"], j["hilos"][0]["fin"]), ("h1", 10, i, i + 12))
        self.luego.assert_called_once()
        r = self.c.post("/comentarios", json={"ruta": "informe.md", "accion": "responder", "hilo": "h1", "texto": "A, B y C"})
        self.assertEqual([c["cuerpo"] for c in r.json()["hilos"][0]["comentarios"]], ["¿cuáles?", "A, B y C"])
        self.assertEqual(self.c.get("/comentarios", params={"ruta": "informe.md"}).json()["hilos"][0]["comentarios"][1]["cuerpo"], "A, B y C")

    def test_los_errores(self):
        self.assertEqual(self.c.get("/comentarios", params={"ruta": "no.md"}).status_code, 404)
        self.assertEqual(self.c.get("/comentarios", params={"ruta": "/etc/hosts"}).status_code, 403)
        r = self.c.post("/comentarios", json={"ruta": "informe.md", "accion": "comentar", "inicio": 0, "fin": 5,
                                              "cita": "no está", "texto": "x"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.c.post("/comentarios", json={"ruta": "informe.md", "accion": "resolver", "hilo": "h3"}).status_code, 404)


class LaOrden(Prueba):
    """`telar comentarios`, del lado del agente."""

    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name).resolve()
        (self.dir / "docs").mkdir()
        self.md = self.dir / "docs" / "informe.md"
        self.md.write_text(DOC, encoding="utf-8")
        i = DOC.index("El 62% de los encuestados")
        mod.comentar(self.md, i, i + 25, "Esta cifra no cuadra.", "Persona")
        antes = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, antes)
        self.ctx = SimpleNamespace(config=Config(raiz=self.dir / "otra", estado=self.dir / ".estado"))

    def correr(self, *argv: str) -> tuple[int, str, str]:
        from telar.ordenes import comentarios

        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = comentarios.main(list(argv), self.ctx)
        return codigo, salida.getvalue(), error.getvalue()

    def test_listar_ver_responder_y_resolver(self):
        codigo, salida, _ = self.correr("listar")
        self.assertEqual(codigo, 0)
        self.assertIn("docs/informe.md — 1 abierto", salida)
        self.assertIn("[h1] línea 5", salida)
        self.assertIn("comentó: «El 62% de los encuestados»", salida)
        self.assertIn("Persona: Esta cifra no cuadra.", salida)
        self.assertEqual(self.correr("responder", "docs/informe.md#h1", "Es", "58%.", "--sin-subir")[:2], (0, "docs/informe.md#h1 respondido.\n"))
        codigo, salida, _ = self.correr("resolver", "comentario:docs/informe.md#h1", "Corregido.", "--autor", "Faro", "--sin-subir", "--json")
        j = json.loads(salida)
        self.assertEqual((j["hilos"][0]["estado"], [c["autor"] for c in j["hilos"][0]["comentarios"]]), ("resuelto", ["Persona", "agente", "Faro"]))
        self.assertEqual(self.correr("listar")[1], "No hay comentarios abiertos.\n")
        codigo, salida, _ = self.correr("ver", "docs/informe.md", "--json")
        self.assertEqual(json.loads(salida)["hilos"][0]["comentarios"][1]["cuerpo"], "Es 58%.")
        # el texto cambió: lo dice
        self.md.write_text(DOC.replace("El 62% de los encuestados", "Cuatro de cada siete participantes"), encoding="utf-8")
        salida = self.correr("listar", "--todos")[1]
        self.assertIn("la cita ya no existe; anclado por lo que la rodeaba", salida)
        self.assertIn("hoy dice: «Cuatro de cada siete participantes»", salida)

    def test_lo_que_falla_se_dice(self):
        self.assertEqual(self.correr("responder", "docs/informe.md#h9", "x", "--sin-subir")[0], 1)
        self.assertEqual(self.correr("responder", "docs/informe.md")[0], 2)
        codigo, salida, _ = self.correr("ver", "docs/no.md", "--json")
        self.assertEqual(json.loads(salida.splitlines()[0])["codigo"], 404)

    def test_el_cli_de_la_extension_lee_lo_mismo(self):
        """Compatible de verdad: si el CLI de la extensión de editor está instalado, lee lo que escribe telar (y telar lo
        que escribe él), con la misma línea, el mismo método y la misma cita."""
        import pwd

        cli = shutil.which("marginalia")
        if not cli:
            self.skipTest("sin el CLI «marginalia» en el PATH")
        # su envoltura busca la extensión en el hogar de verdad (las pruebas tienen uno propio): solo lo lee
        entorno = {**os.environ, "HOME": pwd.getpwuid(os.getuid()).pw_dir}
        if subprocess.run([cli, "--help"], capture_output=True, text=True, timeout=30, env=entorno).returncode != 0:
            self.skipTest("el CLI «marginalia» no encuentra su extensión instalada")
        texto = self.md.read_text(encoding="utf-8")
        i = texto.index("tres frentes")
        mod.comentar(self.md, i, i + 12, "¿Cuáles? 🎉", "Persona")
        self.md.write_text("# Arriba\n\nun párrafo nuevo\n\n" + texto.replace("Se recomienda avanzar en tres\u0020frentes",
                                                                                "Se recomienda avanzar en tres\nfrentes"), encoding="utf-8")
        r = subprocess.run([cli, "ver", str(self.md), "--json"], capture_output=True, text=True, timeout=30, env=entorno)
        self.assertEqual(r.returncode, 0, r.stderr)
        suyo = {h["id"]: h for h in json.loads(r.stdout)["hilos"]}
        nuestro = {h["id"]: h for h in mod.ubicar(self.md)}
        self.assertEqual(set(suyo), set(nuestro))
        for k, h in nuestro.items():
            self.assertEqual((suyo[k]["linea"], suyo[k]["metodo"], suyo[k]["cita"], suyo[k]["estado"]),
                             (h["linea"], h["metodo"], h["cita"], h["estado"]), k)
        r = subprocess.run([cli, "resolver", f"{self.md}#h2", "Son A, B y C."], capture_output=True, text=True, timeout=30, env=entorno)
        self.assertEqual(r.returncode, 0, r.stderr)
        h2 = next(h for h in mod.ubicar(self.md) if h["id"] == "h2")
        self.assertEqual((h2["estado"], h2["comentarios"][-1]["cuerpo"]), ("resuelto", "Son A, B y C."))


class ElTipoComentario(Prueba):
    def setUp(self):
        super().setUp()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.raiz = Path(d.name).resolve()
        (self.raiz / "informe.md").write_text(DOC, encoding="utf-8")
        i = DOC.index("tres frentes")
        mod.comentar(self.raiz / "informe.md", i, i + 12, "¿cuáles?", "Persona")
        self.ctx = SimpleNamespace(config=Config(raiz=self.raiz, estado=self.raiz / ".estado"))

    def test_ver_y_resolver(self):
        from telar import objetos

        o = objetos.ver(self.ctx, "comentario:informe.md#h1")
        self.assertEqual((o.tipo, o.estado, o.titulo, o.campos["donde"]), ("comentario", "abierto", "tres frentes", "línea 10"))
        self.assertEqual(o.enlaces, ["archivo:informe.md"])
        self.assertEqual([a.nombre for a in o.acciones], ["responder", "resolver"])
        with mock.patch("telar.temas.subir_luego"):
            h = objetos.hacer(self.ctx, "comentario:informe.md#h1", "resolver", {"texto": "A, B y C."}, o.version)
        self.assertEqual((h.objeto.estado, [a.nombre for a in h.objeto.acciones]), ("resuelto", ["responder", "reabrir"]))
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.hacer(self.ctx, "comentario:informe.md#h1", "reabrir", {}, o.version)
        self.assertEqual(e.exception.codigo, 409, "cambió desde que se leyó")
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.ver(self.ctx, "comentario:informe.md")
        self.assertEqual(e.exception.codigo, 422)
