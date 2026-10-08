"""`telar tarea --accion`: lo escrito llega al comando y, si la acción abre un hilo, a su primer prompt."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import tarea

ACCION = {"nombre": "escribirle", "pide": "qué le dices", "comando": ["todo", "nota", "T7", "a Claude: {texto}"],
          "mensaje": "/tarea T7 {texto}", "nombre_hilo": "T7 ↩"}


class LoEscritoLlegaAlHilo(Prueba):
    def correr(self, accion, *argv):
        corrido, abierto = [], []
        with mock.patch.object(tarea, "detalle_de", return_value=(("x",), "")), \
                mock.patch.object(tarea, "correr", return_value=({"titulo": "T7", "acciones": [accion]}, "")), \
                mock.patch("subprocess.run", side_effect=lambda w, **k: corrido.append(w) or SimpleNamespace(returncode=0, stdout="", stderr="")), \
                mock.patch("telar.ordenes.atajo.abrir", side_effect=lambda ctx, n, m: abierto.append((n, m)) or ""), \
                redirect_stdout(io.StringIO()):
            codigo = tarea.main(["T7", "--accion", "0", *argv], SimpleNamespace())
        return codigo, corrido, abierto

    def test_el_texto_va_al_comando_y_al_mensaje(self):
        codigo, corrido, abierto = self.correr(ACCION, "--texto", "sí, pero con Ana")
        self.assertEqual(codigo, 0)
        self.assertEqual(corrido, [["todo", "nota", "T7", "a Claude: sí, pero con Ana"]])
        self.assertEqual(abierto, [("T7 ↩", "/tarea T7 sí, pero con Ana")])

    def test_sin_texto_no_corre_nada(self):
        accion = {**ACCION, "comando": ["todo", "ver", "T7"]}  # el {texto} solo en el mensaje
        codigo, corrido, abierto = self.correr(accion)
        self.assertNotEqual(codigo, 0)
        self.assertEqual((corrido, abierto), ([], []))


class ProcesarAhoraVaASuHilo(Prueba):
    """«✓ hecha y procesar ahora» cierra la tarea y lleva /avanzar a su hilo (el del proyecto o el
    agente general). Cerrada, su proveedor ya no la lista: adónde va se busca antes del comando."""

    def test_el_destino_se_busca_antes_de_cerrarla(self):
        accion = {"nombre": "✓ hecha y procesar ahora", "comando": ["todo", "done", "T7"],
                  "mensaje": "/avanzar T7", "al_hilo": True}
        orden, llevado = [], []
        fila = {"ref": "T7", "texto": "x", "ruta": "proyectos/faro", "proveedor": "tareas"}

        def buscar(ctx, tel, ref, proveedor=""):
            orden.append("buscar")
            return fila

        def correr_cmd(w, **k):
            orden.append("comando")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        def llevar(argv, ctx, fila=None):
            orden.append("llevar")
            llevado.append((argv, fila))
            print('{"destino": "faro"}')
            return 0

        with mock.patch.object(tarea, "detalle_de", return_value=(("x",), "")), \
                mock.patch.object(tarea, "correr", return_value=({"titulo": "T7", "acciones": [accion]}, "")), \
                mock.patch("telar.ordenes._comun.tejer", return_value=SimpleNamespace()), \
                mock.patch("telar.ordenes.pendiente._buscar", side_effect=buscar), \
                mock.patch("telar.ordenes.pendiente.main", side_effect=llevar), \
                mock.patch("subprocess.run", side_effect=correr_cmd), \
                redirect_stdout(io.StringIO()):
            codigo = tarea.main(["T7", "--accion", "0", "--proveedor", "tareas"], SimpleNamespace())
        self.assertEqual(codigo, 0)
        self.assertEqual(orden, ["buscar", "comando", "llevar"])
        self.assertIs(llevado[0][1], fila)
        self.assertIn("/avanzar T7", llevado[0][0])
