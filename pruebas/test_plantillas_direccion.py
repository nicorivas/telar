"""{direccion} en las plantillas de mensajes (docs/configuracion.md): `[agente] pendiente` y `pendiente_nuevo`, y
`mensaje_procesar` y `mensaje_escribir` del proveedor de tareas. Se llena con la dirección del objeto (`tarea:T84`,
telar.objetos); un pendiente sin dirección, como una casilla de un documento, cae a {texto}, igual que {id}.
Los valores por defecto no cambian."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

TAREA = """---
titulo: Llamar a Ana por el faro
estado: activa
prioridad: 1
avance: cerrar:hecha 2026-10-15
---
Que confirme la fecha.

## Historia
- 2026-10-01 [creada] a mano
- 2026-10-15 22:43 [avance] cerrar:hecha: Ana confirmó
"""


class ElMensajeDeUnPendiente(Prueba):
    def test_con_direccion_la_llena(self):
        from telar.ordenes.pendiente import mensaje

        fila = {"id": "T84", "texto": "llamar a Ana", "ref": "T84", "direccion": "tarea:T84"}
        self.assertEqual(mensaje("Veamos {direccion}", fila), "Veamos tarea:T84")
        self.assertEqual(mensaje("/tarea {id} ({direccion})", fila), "/tarea T84 (tarea:T84)")

    def test_sin_direccion_cae_al_texto(self):
        # una casilla de un documento (no hay todavía un tipo «pendiente»), o el ítem de un proveedor `comando`
        from telar.ordenes.pendiente import mensaje

        casilla = {"id": "", "texto": "revisar el contrato", "ref": "faro:2", "direccion": ""}
        self.assertEqual(mensaje("Veamos {direccion}", casilla), "revisar el contrato")
        suelto = {"id": "X1", "texto": "leer el informe", "ref": "X1", "direccion": ""}
        self.assertEqual(mensaje("Veamos {direccion}", suelto), "leer el informe")
        self.assertEqual(mensaje("Veamos {id}", suelto), "Veamos X1")  # {id} sigue como antes
        # una fila de antes, sin la clave
        self.assertEqual(mensaje("Veamos {direccion}", {"id": "T84", "texto": "algo", "ref": "T84"}), "algo")

    def test_los_valores_por_defecto_no_cambian(self):
        from telar import config as mod_config

        self.assertEqual(mod_config.PENDIENTE_POR_DEFECTO, "{texto}")
        cfg = mod_config.desde_dict({"agente": {"pendiente": "Veamos {direccion}", "pendiente_nuevo": "/tarea {direccion}"}})
        self.assertEqual((cfg.agente.pendiente, cfg.agente.pendiente_nuevo), ("Veamos {direccion}", "/tarea {direccion}"))


class LaFilaQueLlegaSinDireccion(Prueba):
    """Una fila de una máquina de antes, o la que pasa entera quien llama: si es de un proveedor del tipo, su
    dirección se arma aquí; si no, se queda sin ella."""

    def ctx(self, **agente):
        from telar.config import Agente, Config, Proveedor

        provs = {"tareas": Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": "/no"}),
                 "otro": Proveedor(nombre="otro", opciones={"comando": ["true"]})}
        return SimpleNamespace(config=Config(raiz=Path("/no"), estado=Path("/no/e"), proveedores=provs, agente=Agente(**agente)))

    def test_del_tipo_la_gana(self):
        from telar.ordenes.pendiente import _con_direccion

        fila = _con_direccion(self.ctx(), {"id": "T84", "proveedor": "tareas", "texto": "algo"})
        self.assertEqual(fila["direccion"], "tarea:T84")

    def test_de_otro_o_sin_id_no(self):
        from telar.ordenes.pendiente import _con_direccion

        ctx = self.ctx()
        self.assertNotIn("direccion", _con_direccion(ctx, {"id": "X1", "proveedor": "otro", "texto": "a"}))
        self.assertNotIn("direccion", _con_direccion(ctx, {"id": "", "proveedor": "tareas", "texto": "a"}))
        self.assertEqual(_con_direccion(ctx, {"id": "", "proveedor": "", "direccion": ""})["direccion"], "")

    def test_llevar_la_usa_en_la_plantilla(self):
        from telar.ordenes import _comun, pendiente

        ctx = self.ctx(pendiente="Veamos {direccion}", pendiente_nuevo="/tarea {direccion}")
        fila = {"id": "T84", "proveedor": "tareas", "texto": "algo", "ref": "T84", "hilo": "", "ruta": ""}
        with mock.patch.object(_comun, "tejer"), mock.patch.object(pendiente, "_destino", return_value=None), \
                mock.patch.object(pendiente, "_destino_remoto", return_value=("Faro", "casa")):
            r, _ = pendiente.llevar(ctx, "T84", donde=True, fila=fila)
        self.assertEqual(r["texto"], "Veamos tarea:T84")


class LosMensajesDeLaFicha(Prueba):
    """`mensaje_procesar` y `mensaje_escribir` del proveedor de tareas, llenos en los botones de la ficha."""

    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")

    def acciones(self, **opciones) -> list[dict]:
        from telar.config import Config, Proveedor
        from telar.servicios import tareas as servicio

        prov = Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir), **opciones})
        ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores={"tareas": prov}))
        return [a for a in servicio.ficha(ctx, "T84").model_dump()["acciones"] if a.get("al_hilo")]

    def test_direccion_e_id_se_llenan_y_texto_queda(self):
        mensajes = [a["mensaje"] for a in self.acciones(mensaje_procesar="/avanzar {direccion}",
                                                        mensaje_escribir="/tarea {direccion} {id} {texto}")]
        self.assertEqual(mensajes, ["/avanzar tarea:T84", "/tarea tarea:T84 T84 {texto}"])

    def test_sin_direccion_en_la_plantilla_como_antes(self):
        mensajes = [a["mensaje"] for a in self.acciones(mensaje_procesar="/avanzar {id}", mensaje_escribir="/tarea {id} {texto}")]
        self.assertEqual(mensajes, ["/avanzar T84", "/tarea T84 {texto}"])
