"""`telar mensaje Telar@laptop "…"` llega al hilo «Telar» de laptop, y un destino que nadie lee se rechaza.

Lo que pasó (26-nov-2026, 10:03): un agente corrió `telar mensaje "Telar@laptop" "…"`, sin `hilo:`. Solo la
dirección `hilo:nombre@máquina` separaba la máquina; el nombre suelto iba tal cual, y su forma normalizada
(`casilla.nombre_de_carpeta`: «Telar@laptop» → `telar-laptop`) era una casilla que no es de nadie. El bus la aceptó y
la orden contestó «en su casilla». Nadie lo leyó.

Ahora `nombre@máquina` es lo mismo que `hilo:nombre@máquina` (un agente, por su nombre con o sin máquina), y un nombre
que no es de ningún hilo ni agente, en ninguna máquina, se rechaza con los parecidos, sin publicar nada. Nada de esto
toca un bus ni un tmux de verdad: el bus es un falso, los hilos y las máquinas, de juguete.
"""

from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest import mock

from test_casillas_sin_choque import BusFalso, ConEstado, Kv

from telar import casilla


class ConHilosDeJuguete(ConEstado):
    """En laptop (esta máquina), «Telar» y «Faro»; en servidor, «Molino» y un agente. La persona, «ana»."""

    def setUp(self):
        super().setUp()
        self.hilos = [SimpleNamespace(id="@1", nombre="Telar", remoto="", archivado=False),
                      SimpleNamespace(id="@2", nombre="Faro", remoto="", archivado=False),
                      SimpleNamespace(id="@3", nombre="Molino", remoto="servidor", archivado=False)]
        ajenos = {"Molino": {"maquina": "servidor"}, "Cartero": {"maquina": "servidor"}}
        tel = SimpleNamespace(hilos=self.hilos, vivo=lambda h: True,
                              estado=SimpleNamespace(ajenos=lambda viejos=False: ajenos))
        fotos = [{"nombre": "servidor", "hilos": [{"nombre": "Molino"}, {"nombre": "Cartero"}]}]
        self.agentes = [SimpleNamespace(clave="cartero", nombre="Cartero", residente=True, en="")]
        for p in (mock.patch("telar.ordenes._comun.tejer", return_value=tel),
                  mock.patch("telar.agentes.descubrir", return_value=self.agentes),
                  mock.patch("telar.espejo.leer_todos", return_value=fotos),
                  mock.patch.dict(os.environ, {"TELAR_HILO": ""})):
            p.start()
            self.addCleanup(p.stop)
        self.ctx = SimpleNamespace(config=self.config)

    def enviar(self, para: str) -> list[str]:
        from telar.ordenes import mensaje

        with BusFalso(Kv()) as bus:
            mensaje.enviar(self.ctx, para, "hola")
        return bus.temas()

    def rechazado(self, para: str) -> str:
        """El error de mandarle a `para`, comprobando que no se publicó nada en ninguna casilla."""
        from telar.ordenes import mensaje

        with BusFalso(Kv()) as bus:
            with self.assertRaises(mensaje.NoHayHilo) as e:
                mensaje.enviar(self.ctx, para, "hola")
        self.assertEqual(bus.temas(), [], para)
        return str(e.exception)


class NombreArrobaMaquina(ConHilosDeJuguete):
    def test_la_causa_el_nombre_con_maquina_daba_una_casilla_de_nadie(self):
        self.assertEqual(casilla.nombre_de_carpeta("Telar@laptop"), "telar-laptop")

    def test_nombre_arroba_esta_maquina_va_al_hilo_de_aqui(self):
        self.assertEqual(self.enviar("Telar@laptop"), ["casilla.ana.telar"])

    def test_es_lo_mismo_que_la_direccion(self):
        self.assertEqual(self.enviar("hilo:Telar@laptop"), ["casilla.ana.telar"])

    def test_nombre_arroba_otra_maquina_va_al_hilo_de_alla(self):
        self.assertEqual(self.enviar("Molino@servidor"), ["casilla.ana.molino"])

    def test_un_agente_con_su_maquina_es_el_agente(self):
        self.assertEqual(self.enviar("Cartero@servidor"), ["casilla.ana.cartero"])
        self.assertEqual(self.enviar("cartero@servidor"), ["casilla.ana.cartero"])

    def test_un_hilo_que_esa_maquina_no_tiene_se_rechaza_con_los_parecidos(self):
        error = self.rechazado("Telarr@laptop")
        self.assertIn("«Telar@laptop»", error)
        # el de otra máquina no se va a la de aquí aunque aquí haya uno así
        error = self.rechazado("Telar@servidor")
        self.assertIn("servidor no tiene un hilo «Telar»", error)
        self.assertIn("«Molino» está en servidor", self.rechazado("Molino@laptop"))

    def test_una_maquina_que_no_existe_dice_cuales_hay(self):
        error = self.rechazado("Telar@telar")
        self.assertIn("no conozco la máquina «telar»", error)
        self.assertIn("laptop, servidor", error)

    def test_la_persona_en_una_maquina_no_tiene_casilla(self):
        # lo que la persona manda desde un terminal lleva de remitente «ana@laptop»: contestarle ahí no le llega a nadie
        self.assertIn("tu persona", self.rechazado("ana@laptop"))


class NadieLaLee(ConHilosDeJuguete):
    def test_un_nombre_que_no_es_de_nadie_se_rechaza_sin_publicar(self):
        error = self.rechazado("Nadie")
        self.assertIn("no le mandé nada", error)
        self.assertIn("telar hilos --red", error)

    def test_con_los_parecidos(self):
        error = self.rechazado("Tellar")
        self.assertIn("«Telar» (vivo, en esta máquina)", error)

    def test_la_persona_no_es_un_hilo(self):
        self.assertIn("tu persona", self.rechazado("ana"))

    def test_los_que_si_existen_siguen_llegando(self):
        self.assertEqual(self.enviar("Telar"), ["casilla.ana.telar"])
        self.assertEqual(self.enviar("telar"), ["casilla.ana.telar"])  # mayúsculas distintas, uno solo: ese
        self.assertEqual(self.enviar("Molino"), ["casilla.ana.molino"])  # de otra máquina, por el estado
        self.assertEqual(self.enviar("Cartero"), ["casilla.ana.cartero"])
        self.assertEqual(self.enviar("hilo:Faro"), ["casilla.ana.faro"])

    def test_uno_recien_abierto_en_otra_maquina_lo_sabe_el_bus(self):
        from telar.ordenes import mensaje

        with BusFalso(Kv({"ana.nuevo": {"nombre": "Nuevo", "maquina": "servidor", "vivo": True}})) as bus:
            mensaje.enviar(self.ctx, "Nuevo", "hola")
        self.assertEqual(bus.temas(), ["casilla.ana.nuevo"])

    def test_sin_saber_que_hilos_hay_no_se_rechaza(self):
        with mock.patch("telar.ordenes._comun.nombres_conocidos", side_effect=OSError("sin estado")):
            self.assertEqual(self.enviar("Nadie"), ["casilla.ana.nadie"])

    def test_por_el_servicio_es_un_404(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes

        for para in ("Nadie", "Telarr@laptop"):
            with BusFalso(Kv()):
                with self.assertRaises(ErrorDeServicio) as e:
                    mensajes.enviar(self.ctx, para, "hola")
            self.assertEqual(e.exception.codigo, 404, para)


class LoQueDice(ConHilosDeJuguete):
    def correr(self, para: str) -> tuple[int, str, str]:
        from telar.ordenes import mensaje

        salida, error = io.StringIO(), io.StringIO()
        with BusFalso(Kv()), redirect_stdout(salida), redirect_stderr(error):
            codigo = mensaje.main([para, "hola"], self.ctx)
        return codigo, salida.getvalue(), error.getvalue()

    def test_dice_a_que_hilo_llego(self):
        codigo, salida, _ = self.correr("Telar@laptop")
        self.assertEqual(codigo, 0)
        self.assertIn("«Telar» (Telar@laptop): en su casilla", salida)

    def test_si_no_llego_no_dice_en_su_casilla(self):
        codigo, salida, error = self.correr("Telar@telar")
        self.assertNotEqual(codigo, 0)
        self.assertNotIn("en su casilla", salida + error)
        self.assertIn("no conozco la máquina", error)


class Encargar(ConHilosDeJuguete):
    def test_el_agente_con_su_maquina(self):
        from telar.servicios import encargos

        self.assertEqual(encargos.sin_maquina(self.ctx, "Cartero@servidor"), "Cartero")
        self.assertEqual(encargos.sin_maquina(self.ctx, "cartero@telar"), "cartero")
        self.assertEqual(encargos.sin_maquina(self.ctx, "Telar@laptop"), "Telar@laptop")  # no es un agente
        self.assertEqual(encargos._agente(self.ctx, "Cartero@servidor").nombre, "Cartero")

    def test_por_el_bus_va_a_la_casilla_del_agente(self):
        from telar.servicios import encargos

        with BusFalso(Kv()) as bus, mock.patch("telar.encargo.anotar_enviado"):
            r = encargos.por_el_bus(self.ctx, "Cartero@servidor", "/avanzar T1")
        self.assertEqual(bus.temas(), ["casilla.ana.cartero"])
        self.assertEqual(r.hilo, "Cartero")


class ElPeriodicoNoEsPadre(ConEstado):
    """Un hilo que abre un periódico queda anotado como abierto por «periódico a-solas», y eso lo volvía su padre:
    el nodo le avisaba cada turno a una casilla que nadie lee (periodico-a-solas, con 16 avisos sin recoger)."""

    def test_al_que_abrio_un_periodico_no_se_le_avisa_y_al_que_declara_un_padre_si(self):
        from telar import estado as mod_estado
        from telar.ordenes import hilo as orden_hilo
        from telar.ordenes import mensaje
        from telar.ordenes import nodo as mod_nodo

        est = mod_estado.abrir(self.config)
        est.anotar_abierto_por("◌ a solas 11/26 10:00", "periódico a-solas", "")
        est.anotar_abierto_por("◑ componentes 11/26 01:00", "periódico componentes-noche", "")
        est.colgar("◑ componentes 11/26 01:00", "Componentes")  # el periódico declara su padre
        self.assertEqual(orden_hilo.padre_de(est, "◌ a solas 11/26 10:00"), "periódico a-solas")
        self.assertEqual(orden_hilo.padre_que_lee(est, "◌ a solas 11/26 10:00"), "")
        self.assertEqual(orden_hilo.padre_que_lee(est, "◑ componentes 11/26 01:00"), "Componentes")

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        anotado = []
        n.config, n.ctx, n.anotar = self.config, SimpleNamespace(config=self.config), anotado.append
        n._lo_ultimo = lambda est, h: ""
        hilos = ("◌ a solas 11/26 10:00", "◑ componentes 11/26 01:00")
        with mock.patch.object(mensaje, "enviar") as enviar:
            n.avisar_padres({h: {"atencion": "trabajando"} for h in hilos}, ahora=1000)
            self.assertEqual(n.avisar_padres({h: {"atencion": "termino"} for h in hilos}, ahora=1001),
                             ["◑ componentes 11/26 01:00"])
        self.assertEqual([c.args[1] for c in enviar.call_args_list], ["Componentes"])
        self.assertEqual(anotado, [])  # ni la línea «no pudo avisarle»
