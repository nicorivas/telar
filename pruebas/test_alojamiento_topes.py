"""Los topes de memoria y CPU de los alojados: los de los nuevos y los de cada uno, cambiados desde ⚙ servidor."""

from __future__ import annotations

from comun import Prueba  # noqa: E402,F401  (pone src/ en el camino)

from telar import alojamiento
import test_alojamiento as base


class LosTopes(base.EnLaMaquinaDelBus):
    def topes(self, por="ana", **pedido):
        return alojamiento.atender("ana", por, {"accion": "topes", **pedido}, self.config, ayuda=self.ayuda())

    def test_los_de_los_nuevos_valen_al_aprobar(self):
        r = self.topes(memoria="1500m", cpu="50")
        self.assertEqual(r["topes"], {"memoria": "1500M", "cpu": "50%"})
        self.pedir()
        self.aprobar(ayuda=self.ayuda())
        crear = self.pedidos_al_ayudante[-1]
        self.assertEqual((crear["memoria"], crear["cpu"]), ("1500M", "50%"))
        a = alojamiento.leer()["pablo"]
        self.assertEqual((a["memoria"], a["cpu"]), ("1500M", "50%"))

    def test_los_de_un_alojado_van_al_ayudante_y_quedan_anotados(self):
        self.pedir()
        self.aprobar(ayuda=self.ayuda())
        r = self.topes(persona="pablo", memoria="4G", cpu="200%")
        self.assertEqual(self.pedidos_al_ayudante[-1], {"accion": "topes", "nombre": "pablo", "memoria": "4G", "cpu": "200%"})
        self.assertIn("desde ya", r["hecho"])
        self.assertEqual(alojamiento.leer()["pablo"]["memoria"], "4G")

    def test_solo_quien_administra_y_solo_a_un_activo(self):
        self.pedir()
        with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
            self.topes(por="pablo", memoria="4G", cpu="100%")
        self.assertEqual(e.exception.codigo, 403)
        with self.assertRaises(alojamiento.ErrorDeAlojamiento) as e:
            self.topes(persona="pablo", memoria="4G", cpu="100%")  # todavía pendiente
        self.assertEqual(e.exception.codigo, 409)

    def test_topes_que_no_sirven(self):
        for memoria, cpu in (("100M", "100%"), ("128G", "100%"), ("mucha", "100%"), ("2G", "5%"), ("2G", "900%"), ("2G", "x")):
            with self.assertRaises(alojamiento.ErrorDeAlojamiento, msg=f"{memoria} {cpu}"):
                self.topes(memoria=memoria, cpu=cpu)


class ElAyudanteCambiaTopes(Prueba):
    def setUp(self):
        super().setUp()
        self.m = base._cargar_ayudante()

    def test_reescribe_su_slice_y_los_aplica_ya(self):
        p = self.m.validar({"accion": "topes", "nombre": "pablo", "memoria": "4G", "cpu": "200%"})
        pasos = self.m.plan(p)
        self.assertIn("MemoryMax=4G", pasos[0].archivo[1])
        self.assertEqual(pasos[-1].argv[:4], ["systemctl", "set-property", "--runtime", "user-{uid}.slice"])
        self.assertIn("CPUQuota=200%", pasos[-1].argv)

    def test_valida_los_topes(self):
        for malo in ({"memoria": "4G; reboot"}, {"cpu": "200"}, {"memoria": None}):
            with self.assertRaises(self.m.Rechazo, msg=str(malo)):
                self.m.validar({"accion": "topes", "nombre": "pablo", "memoria": "4G", "cpu": "200%", **malo})
