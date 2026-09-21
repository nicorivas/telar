"""El despachador: banderas globales, órdenes conocidas y órdenes que faltan."""

from __future__ import annotations

import io
import contextlib
import unittest

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

import telar
from telar import cli


def correr(*argv: str) -> tuple[int, str, str]:
    salida, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
        codigo = cli.main(list(argv))
    return codigo, salida.getvalue(), error.getvalue()


class Banderas(Prueba):
    def test_version(self):
        codigo, salida, _ = correr("--version")
        self.assertEqual(codigo, 0)
        self.assertEqual(salida.strip(), f"telar {telar.__version__}")

    def test_version_corta(self):
        self.assertEqual(correr("-V")[0], 0)

    def test_ayuda_sale_bien(self):
        codigo, salida, _ = correr("--help")
        self.assertEqual(codigo, 0)
        self.assertIn("telar", salida)
        for orden in cli.ORDENES:
            self.assertIn(orden, salida)

    def test_sin_argumentos_muestra_la_ayuda_pero_no_sale_bien(self):
        codigo, salida, _ = correr()
        self.assertEqual(codigo, 1)
        self.assertIn("Órdenes", salida)

    def test_una_bandera_desconocida_se_dice(self):
        codigo, _, error = correr("--inventada")
        self.assertEqual(codigo, 2)
        self.assertIn("inventada", error)

    def test_una_bandera_con_valor_sin_valor_se_dice(self):
        codigo, _, error = correr("--config")
        self.assertEqual(codigo, 2)
        self.assertIn("valor", error)


class Ordenes(Prueba):
    def test_una_orden_que_no_existe_se_dice(self):
        codigo, _, error = correr("inventada")
        self.assertEqual(codigo, 2)
        self.assertIn("inventada", error)

    def test_una_orden_parecida_se_sugiere(self):
        _, _, error = correr("hil")
        self.assertIn("hilos", error)

    def declarar_fantasma(self, nombre: str = "fantasma") -> str:
        """Una orden declarada que nadie escribió, para probar el despachador y nada más."""
        cli.ORDENES[nombre] = "Declarada a propósito y sin módulo, para las pruebas."
        self.addCleanup(cli.ORDENES.pop, nombre, None)
        return nombre

    def test_una_orden_declarada_y_no_escrita_lo_dice_en_voz_alta(self):
        codigo, _, error = correr(self.declarar_fantasma())
        self.assertEqual(codigo, 2)
        self.assertIn("no implementada", error)

    def test_las_banderas_de_la_orden_no_las_toca_el_despachador(self):
        # `--loquesea` va después de la orden: es de ella, no del despachador.
        codigo, _, error = correr(self.declarar_fantasma(), "--loquesea")
        self.assertEqual(codigo, 2)
        self.assertIn("no implementada", error)

    def test_una_bandera_de_la_orden_la_contesta_la_orden(self):
        # el despachador la deja pasar entera; quien se queja es `hilos`
        codigo, _, error = correr("hilos", "--loquesea")
        self.assertEqual(codigo, 2)
        self.assertIn("--loquesea", error)
        self.assertIn("telar hilos", error)

    def test_una_config_que_no_existe_se_dice_antes_de_la_orden(self):
        codigo, _, error = correr("--config", "/no/existe.toml", "hilos")
        self.assertEqual(codigo, 2)
        self.assertIn("no existe", error)


class ContextoDelDespachador(Prueba):
    def test_el_contexto_lee_el_perfil_solo_cuando_se_lo_piden(self):
        from telar.config import Config

        ctx = cli.Contexto(config=Config())
        self.assertIsNone(ctx._perfil)
        self.assertIsNotNone(ctx.perfil)  # se lee al pedirlo
        self.assertIs(ctx.perfil, ctx._perfil)  # y una sola vez


if __name__ == "__main__":
    unittest.main()
