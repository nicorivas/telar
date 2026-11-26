"""Lo que la vista «esperando» necesita de una tarea que tiene otro: a quién espera, desde cuándo y lo último que pasó.

Lo pone el proveedor del tipo `tarea` (`telar.proveedores.tareas.de_otro`) solo en las que esperan a alguien o tienen
dueño, y la fila de `telar pendientes` lo lleva tal cual (`_de_otro`). Las demás filas no engordan."""

from __future__ import annotations

import datetime as _dt
import shutil
import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

ESPERA = """---
titulo: Molino: esperar los accesos del cliente
estado: espera
prioridad: 1
vence: 2026-10-19
espera: Ana Pérez
area: trabajo
creada: 2026-10-01
---
## Historia
- 2026-10-01 [creada] desde minuta
- 2026-10-15 16:59 [espera] espera a Ana Pérez: quedó de mandarlos el lunes
- 2026-11-12 10:00 [nota] llegaron los repositorios; faltan las credenciales
- 2026-11-17 16:01 [edita] proyecto, tamano
"""

DELEGADA = """---
titulo: Faro: armar el temario
estado: activa
prioridad: 2
dueño: Leo
area: trabajo
creada: 2026-10-20
---
## Historia
- 2026-10-20 [creada] a mano
- 2026-10-29 22:22 [edita] dueño Leo
- 2026-11-17 16:01 [edita] tamano
"""

SIN_MARCA = """---
titulo: Esperar a alguien sin decir desde cuándo
estado: espera
espera: legal
creada: 2026-09-02
---
"""

MIA = """---
titulo: Escribir el informe
estado: activa
creada: 2026-11-01
---
## Historia
- 2026-11-01 [creada] a mano
- 2026-11-02 [nota] ya empecé
"""


class LoQueTieneOtro(Prueba):
    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        for nombre, texto in (("T1", ESPERA), ("T2", DELEGADA), ("T3", SIN_MARCA), ("T4", MIA)):
            (self.dir / f"{nombre}.md").write_text(texto, encoding="utf-8")
        from telar.config import Proveedor
        from telar.proveedores import tareas as P
        self.P = P
        self.prov = P.DeTipo(Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir)}))
        self.items = {i.id: i for i in self.prov.consultar(_dt.date(2026, 11, 26))}

    def test_la_que_espera_dice_desde_su_linea_de_espera_y_lo_ultimo_sin_la_edicion_de_campos(self):
        d = self.items["T1"].datos
        self.assertEqual(d["espera"], "@Ana Pérez")
        self.assertEqual(d["desde"], "2026-10-15 16:59")
        self.assertEqual(d["ultimo"], {"fecha": "2026-11-12 10:00", "tipo": "nota",
                                       "texto": "llegaron los repositorios; faltan las credenciales"})

    def test_la_delegada_dice_desde_que_le_dieron_dueno_y_eso_es_lo_ultimo(self):
        d = self.items["T2"].datos
        self.assertEqual((d["dueno"], d["desde"]), ("Leo", "2026-10-29 22:22"))
        self.assertEqual(d["ultimo"]["texto"], "dueño Leo")

    def test_sin_historia_vale_su_creacion_y_no_hay_ultimo(self):
        d = self.items["T3"].datos
        self.assertEqual((d["desde"], d["ultimo"]), ("2026-09-02", None))

    def test_la_propia_no_lleva_nada_de_eso(self):
        d = self.items["T4"].datos
        self.assertEqual((d["desde"], d["ultimo"]), ("", None))

    def test_lo_ultimo_largo_se_corta(self):
        largo = ESPERA.replace("llegaron los repositorios; faltan las credenciales", "x" * 500)
        from telar.tipos import tarea
        d = self.P.de_otro(tarea.ARCHIVO.leer(largo, "T9"))
        self.assertEqual(len(d["ultimo"][2]), self.P.ULTIMO_MAX)
        self.assertTrue(d["ultimo"][2].endswith("…"))

    def test_la_fila_de_pendientes_lo_lleva_y_las_demas_no_engordan(self):
        from types import SimpleNamespace

        from telar.config import Config, Proveedor
        from telar.ordenes import _comun
        from telar.ordenes import pendientes as orden
        prov = Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir)})
        ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores={"tareas": prov}))
        filas, _ = orden.de_proveedores(ctx, _comun.Telar(hilos=[], raiz=self.dir), _dt.date(2026, 11, 26))
        por = {f["id"]: f for f in filas}
        self.assertEqual(por["T1"]["espera"], "Ana Pérez")
        self.assertEqual(por["T1"]["desde"], "2026-10-15 16:59")
        self.assertEqual(por["T1"]["ultimo"]["tipo"], "nota")
        self.assertNotIn("espera", por["T2"])
        self.assertEqual(por["T2"]["dueno"], "Leo")
        for clave in ("espera", "desde", "ultimo"):
            self.assertNotIn(clave, por["T4"])
