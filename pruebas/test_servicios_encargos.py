"""Encargar y los atajos, como servicios: por el bus, aquí, o el error que dice por qué no."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar.servicios import ErrorDeServicio
from telar.servicios import atajos, encargos


def _ctx(*, bus=True, agentes_en="", atajos_=()):
    return SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x" if bus else ""),
                                                  agentes_en=agentes_en, atajos=atajos_))


AGENTE = SimpleNamespace(clave="gestion", nombre="Gestión", en="")


class Encargar(Prueba):
    def setUp(self):
        super().setUp()
        p = mock.patch("telar.agentes.descubrir", return_value=[AGENTE])
        p.start()
        self.addCleanup(p.stop)

    def test_por_el_bus_y_retenido(self):
        enviado = {"para": "Gestión", "id": "m1", "estado": "enviado", "encargo": "e-1a2b3c4d",
                   "direccion": "encargo:e-1a2b3c4d"}
        with mock.patch("telar.ordenes.mensaje.enviar", return_value=enviado) as enviar:
            r = encargos.encargar(_ctx(), "gestion", "ordena el roadmap")
        # siempre un Encargo como objeto: con su dirección
        self.assertEqual(enviar.call_args.kwargs["modo"], "encargo")
        self.assertEqual(r.model_dump(), {"hilo": "Gestión", "estado": "en su casilla (bus)", "id": "m1",
                                          "encargo": "e-1a2b3c4d", "direccion": "encargo:e-1a2b3c4d"})
        retenido = {"para": "Gestión", "id": "m2", "estado": "retenido", "motivo": "cadena larga"}
        with mock.patch("telar.ordenes.mensaje.enviar", return_value=retenido):
            self.assertEqual(encargos.encargar(_ctx(), "Gestión", "x").estado, "retenido")

    def test_bus_caido_aqui_se_encarga_aqui_y_si_vive_en_otra_no(self):
        caido = mock.patch("telar.ordenes.mensaje.enviar", side_effect=mod_bus.ErrorDeBus("no responde"))
        with caido, mock.patch("telar.encargos.encargar", return_value={"hilo": "Gestión", "estado": "enviado"}) as aqui:
            self.assertEqual(encargos.encargar(_ctx(), "gestion", "x").estado, "enviado")
        aqui.assert_called_once()
        with caido, self.assertRaises(encargos.BusCaido):
            encargos.encargar(_ctx(agentes_en="telar"), "gestion", "x")
        with self.assertRaises(ErrorDeServicio) as e:
            encargos.encargar(_ctx(bus=False, agentes_en="telar"), "gestion", "x")
        self.assertEqual(e.exception.codigo, 502)

    def test_a_quien_no_es_residente_ni_sin_texto(self):
        with self.assertRaises(ErrorDeServicio) as e:
            encargos.encargar(_ctx(), "Telar", "x")
        self.assertEqual(e.exception.codigo, 404)
        with self.assertRaises(ErrorDeServicio):
            encargos.encargar(_ctx(), "gestion", "  ")


class Atajos(Prueba):
    def test_un_atajo_abre_un_hilo_con_su_mensaje(self):
        a = SimpleNamespace(tecla="m", nombre="⚑ correo", mensaje="/correo", descripcion="", agente="")
        with mock.patch("telar.ordenes.atajo.abrir", return_value="") as abrir:
            r = atajos.correr(_ctx(atajos_=(a,)), "m")
        self.assertTrue(r.hilo.startswith("⚑ correo "))
        self.assertEqual((r.mensaje, abrir.call_args.args[2]), ("/correo", "/correo"))
        with mock.patch("telar.ordenes.atajo.abrir", return_value="la sesión no está viva"):
            with self.assertRaises(ErrorDeServicio) as e:
                atajos.correr(_ctx(atajos_=(a,)), "m")
        self.assertEqual(e.exception.codigo, 409)
        with self.assertRaises(ErrorDeServicio):
            atajos.correr(_ctx(atajos_=(a,)), "z")

    def test_el_atajo_de_un_agente_le_encarga_y_lleva_a_su_hilo(self):
        a = SimpleNamespace(tecla="g", nombre="Gestión", mensaje="/revisar", descripcion="", agente="gestion")
        hilo = SimpleNamespace(id="@3", nombre="Gestión")
        tel = SimpleNamespace(por_nombre=lambda n: hilo, vivo=lambda h: True, mux=mock.Mock())
        with mock.patch("telar.agentes.descubrir", return_value=[AGENTE]), \
                mock.patch.object(encargos, "encargar", return_value=encargos.Encargo(hilo="Gestión", estado="en su casilla (bus)")), \
                mock.patch("telar.ordenes._comun.tejer", return_value=tel):
            r = atajos.correr(_ctx(atajos_=(a,)), "g")
        self.assertEqual(r.model_dump(), {"hilo": "Gestión", "mensaje": "/revisar", "encargo": "en su casilla (bus)"})
        tel.mux.ir.assert_called_once_with("@3")
