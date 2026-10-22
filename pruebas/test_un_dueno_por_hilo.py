"""Un dueño por hilo, «dejar de copiar»: el vínculo, el archivo y la conversación de un hilo de otra máquina
se leen de lo que publica su dueño (`ajenos.json`, que escribe el nodo), y aquí no se copian.

Un estado de antes, con copias de esos hilos en los archivos de aquí, se sigue leyendo mientras el dueño no
publique el campo. Nada de esto toca el bus ni tmux: el nodo se arma sin conectarse y el bus es un falso.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from test_ordenes import Orden

from telar import estado as mod_estado
from telar.modelo import Hilo
from telar.ordenes import doctor
from telar.ordenes import hilo as orden_hilo
from telar.ordenes import nodo as mod_nodo


def escribir(carpeta: Path, nombre: str, datos) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


class ConEstado(Prueba):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.carpeta = Path(tmp.name) / "estado"
        # un estado de antes: Faro vive en el servidor y aquí quedaron copias de su registro
        escribir(self.carpeta, "vinculos.json", {"Faro": "proyectos/copia-vieja", "Ana": "proyectos/ana"})
        escribir(self.carpeta, "archivados.json", ["Faro"])
        escribir(self.carpeta, "sesiones.json", {"Faro": ["s-vieja"], "Ana": ["s-ana"]})
        escribir(self.carpeta, "remotos.json", {"Faro": {"remoto": "servidor", "sesion": "@3/1a2b3c4d"}})
        self.est = mod_estado.Estado(self.carpeta)


class LoLeeDeSuDueno(ConEstado):
    def test_sin_lo_del_dueno_se_lee_el_estado_de_antes(self):
        self.assertEqual(self.est.vinculos()["Faro"], "proyectos/copia-vieja")
        self.assertIn("Faro", self.est.archivados())
        self.assertEqual(self.est.sesiones()["Faro"], ("s-vieja",))
        self.assertFalse(self.est.es_ajeno("Faro"))

    def test_lo_que_publica_el_dueno_gana_sobre_la_copia(self):
        self.est.guardar_ajenos({"Faro": {"maquina": "servidor", "vinculo": "proyectos/faro/",
                                          "archivado": False, "conversacion": "s-nueva"}})
        self.assertTrue(self.est.es_ajeno("Faro"))
        self.assertEqual(self.est.vinculos()["Faro"], "proyectos/faro")
        self.assertNotIn("Faro", self.est.archivados())
        self.assertEqual(self.est.sesiones()["Faro"], ("s-nueva",))
        # lo de los hilos de aquí no cambia
        self.assertEqual(self.est.vinculos()["Ana"], "proyectos/ana")
        self.assertEqual(self.est.sesiones()["Ana"], ("s-ana",))
        # y los archivos de aquí quedan como estaban: no se migran ni se borran
        self.assertEqual(json.loads((self.carpeta / "vinculos.json").read_text())["Faro"], "proyectos/copia-vieja")

    def test_el_dueno_dice_que_no_tiene_vinculo_ni_conversacion(self):
        self.est.guardar_ajenos({"Faro": {"maquina": "servidor", "vinculo": "", "archivado": True, "conversacion": ""}})
        self.assertNotIn("Faro", self.est.vinculos())
        self.assertIn("Faro", self.est.archivados())
        self.assertNotIn("Faro", self.est.sesiones())

    def test_un_dueno_de_antes_que_no_publica_el_campo_deja_lo_de_aqui(self):
        self.est.guardar_ajenos({"Faro": {"maquina": "servidor", "conversacion": "s-nueva"}})
        self.assertEqual(self.est.vinculos()["Faro"], "proyectos/copia-vieja")
        self.assertIn("Faro", self.est.archivados())
        self.assertEqual(self.est.sesiones()["Faro"], ("s-nueva",))

    def test_un_hilo_de_aqui_que_se_llama_igual_no_toma_lo_de_alla(self):
        # Ana no tiene ventana ni dirección de otra máquina aquí: es de aquí, aunque el bus traiga una Ana
        self.est.guardar_ajenos({"Ana": {"maquina": "servidor", "vinculo": "otra/parte", "archivado": True}})
        self.assertFalse(self.est.es_ajeno("Ana"))
        self.assertEqual(self.est.vinculos()["Ana"], "proyectos/ana")
        self.assertNotIn("Ana", self.est.archivados())

    def test_un_archivo_roto_o_con_basura_no_rompe_nada(self):
        (self.carpeta / "ajenos.json").write_text("{roto", encoding="utf-8")
        self.assertEqual(self.est.ajenos(), {})
        self.assertEqual(self.est.vinculos()["Faro"], "proyectos/copia-vieja")
        escribir(self.carpeta, "ajenos.json", {"Faro": {"vinculo": "x"}, "T84": "no", "Ana": {"maquina": 3}})
        self.assertEqual(self.est.ajenos(), {})
        escribir(self.carpeta, "ajenos.json", {"Faro": {"maquina": "servidor", "vinculo": 7, "archivado": "sí"}})
        self.assertEqual(self.est.vinculos()["Faro"], "proyectos/copia-vieja")  # tipos raros: se ignoran
        self.assertIn("Faro", self.est.archivados())

    def test_la_lista_se_viste_con_lo_del_dueno(self):
        self.est.guardar_ajenos({"Faro": {"maquina": "servidor", "vinculo": "proyectos/faro",
                                          "archivado": False, "conversacion": "s-nueva"}})
        foto = self.est.foto(tope=600)
        (faro,) = mod_estado.vestir([Hilo(id="@1", nombre="Faro")], raiz=Path("/raiz"), **foto)
        self.assertEqual(faro.vinculo, Path("/raiz/proyectos/faro"))
        self.assertFalse(faro.archivado)
        self.assertEqual(faro.sesiones, ("s-nueva",))
        self.assertEqual(faro.remoto, "servidor")


class ElNodoEspeja(ConEstado):
    def nodo(self):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.config = SimpleNamespace(estado=self.carpeta, bus=SimpleNamespace(persona="ana", maquina="laptop"))
        n.yo, n.vistos, n.ajenos_escritos, n.publicado, n.ausentes = "laptop", {}, None, {}, {}
        n.registro, n.vueltas, n.subs = ({}, set(), {}), 5, {}
        return n

    def test_deja_lo_ultimo_de_cada_hilo_ajeno_y_no_reescribe_si_no_cambio(self):
        n = self.nodo()
        n.vistos = {"ana.faro": {"nombre": "Faro", "maquina": "servidor", "vivo": True, "vinculo": "proyectos/faro",
                                 "archivado": False, "conversacion": "s-1", "ventana": "@3/1a2b3c4d"},
                    "ana.sin-maquina": {"nombre": "Raro"}}
        self.assertTrue(n.espejar_ajenos())
        guardado = json.loads((self.carpeta / "ajenos.json").read_text())
        self.assertEqual(set(guardado), {"Faro"})
        self.assertEqual(guardado["Faro"]["vinculo"], "proyectos/faro")
        self.assertNotIn("ventana", guardado["Faro"])  # la ventana la usa el nodo de memoria
        self.assertFalse(n.espejar_ajenos())
        n.vistos.clear()  # se mudó aquí, o se borró: deja de ser ajeno
        self.assertTrue(n.espejar_ajenos())
        self.assertEqual(json.loads((self.carpeta / "ajenos.json").read_text()), {})

    def test_el_registro_que_publica_el_dueno(self):
        self.assertEqual(mod_nodo.registro_de("Faro", {"Faro": "proyectos/faro"}, {"Faro"}),
                         {"vinculo": "proyectos/faro", "archivado": True})
        self.assertEqual(mod_nodo.registro_de("Ana", {}, set()), {"vinculo": "", "archivado": False})

    def vuelta(self, n, previo, registro):
        clave = "ana.faro"
        n.publicado = {clave: json.dumps(previo, ensure_ascii=False, sort_keys=True)}
        n.registro = registro
        n.locales = lambda: {}
        puestos = []
        kv = SimpleNamespace(put=lambda k, v: _async(puestos.append((k, json.loads(v)))))
        with mock.patch("telar.bus.persona", return_value="ana"), mock.patch("telar.bus.ficha", return_value="faro"):
            asyncio.run(n._vuelta(js=None, kv=kv))
        return puestos

    def test_un_hilo_muerto_que_se_archivo_despues_se_vuelve_a_publicar(self):
        n = self.nodo()
        previo = {"nombre": "Faro", "maquina": "laptop", "vivo": False, "vinculo": "proyectos/faro", "archivado": False}
        puestos = self.vuelta(n, previo, ({"Faro": "proyectos/faro"}, {"Faro"}, {}))
        self.assertEqual(len(puestos), 1)
        self.assertTrue(puestos[0][1]["archivado"])
        # sin cambios, nada
        self.assertEqual(self.vuelta(n, {**previo, "archivado": True}, ({"Faro": "proyectos/faro"}, {"Faro"}, {})), [])

    def test_no_se_pisa_el_estado_de_un_hilo_que_ya_publica_otra_maquina(self):
        n = self.nodo()
        previo = {"nombre": "Faro", "maquina": "laptop", "vivo": False, "vinculo": "", "archivado": False}
        n.vistos = {"ana.faro": {"nombre": "Faro", "maquina": "servidor"}}
        with mock.patch.object(n, "espejar_ajenos"):
            self.assertEqual(self.vuelta(n, previo, ({}, {"Faro"}, {})), [])
        n.vistos = {}
        self.assertEqual(self.vuelta(n, previo, ({}, {"Faro"}, {"Faro": {"remoto": "servidor"}})), [])


async def _nada():
    return None


def _async(_):
    return _nada()


class ConciliaConLoDelDueno(Prueba):
    def nodo(self, vistos, ventanas, archivados=()):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx, n.vistos, n.tocadas = None, vistos, []
        tel = SimpleNamespace(
            mux=object(), viva=True,
            por_nombre=lambda nombre: SimpleNamespace(nombre=nombre) if nombre in ventanas else None,
            vivo=lambda h: h.nombre in ventanas,
            estado=SimpleNamespace(remotos=lambda: {}, archivados=lambda: set(archivados)))
        n.ventana_de = lambda d: n.tocadas.append(d["nombre"])
        return n, tel

    def test_el_archivo_lo_dice_el_dueno_y_si_no_lo_dice_vale_lo_de_aqui(self):
        vistos = {"ana.faro": {"nombre": "Faro", "vivo": True, "maquina": "servidor", "archivado": True},
                  "ana.t84": {"nombre": "T84", "vivo": True, "maquina": "servidor", "archivado": False},
                  "ana.viejo": {"nombre": "Viejo", "vivo": True, "maquina": "servidor"}}
        # T84 y Viejo tienen copia de «archivado» aquí; Faro no
        n, tel = self.nodo(vistos, ventanas=set(), archivados={"T84", "Viejo"})
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel):
            self.assertEqual(n.conciliar(), ["T84"])

    def test_revivir_lo_decide_el_dueno_si_publica_su_archivo(self):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        est = mock.Mock()
        n._revivir(SimpleNamespace(estado=est), "Faro", {"archivado": True, "desde": "2026-10-22T10:00:00"}, "servidor")
        est.desarchivar.assert_not_called()
        est.archivados.assert_not_called()


class NoSeCopiaAlCambiarlo(Orden):
    """`telar hilo vincular|archivar…` de un hilo ajeno: se lo pide a su dueño y aquí no escribe nada."""

    def setUp(self):
        super().setUp()
        self.carpeta = Path(self.tmp.name) / "estado"
        escribir(self.carpeta, "vinculos.json", {"Faro": "proyectos/copia-vieja"})
        escribir(self.carpeta, "remotos.json", {"Faro": {"remoto": "servidor", "sesion": "@3/1a2b3c4d"}})
        escribir(self.carpeta, "ajenos.json", {"Faro": {"maquina": "servidor", "vinculo": "proyectos/faro", "archivado": False}})

    def archivos(self):
        return {n: (self.carpeta / n).read_text() if (self.carpeta / n).exists() else None
                for n in ("vinculos.json", "archivados.json", "archivados_en.json", "sesiones.json")}

    def test_vincular_archivar_y_desvincular_van_solo_al_dueno(self):
        antes = self.archivos()
        with mock.patch.object(orden_hilo, "_dueno", return_value="servidor"), \
                mock.patch.object(orden_hilo, "_al_dueno", return_value="") as al_dueno:
            for argv in (["vincular", "proyectos/faro"], ["archivar"], ["desarchivar"], ["desvincular"]):
                codigo, _, error = self.correr("hilo", *argv, "--hilo", "Faro")
                self.assertEqual(codigo, 0, error)
        self.assertEqual(al_dueno.call_count, 4)
        self.assertEqual(self.archivos(), antes)

    def test_sin_dueno_ajeno_se_escribe_aqui_como_siempre(self):
        with mock.patch.object(orden_hilo, "_dueno", return_value=""):
            codigo, _, error = self.correr("hilo", "archivar", "--hilo", "Faro")
        self.assertEqual(codigo, 0, error)
        self.assertIn("Faro", json.loads((self.carpeta / "archivados.json").read_text()))

    def test_la_lista_muestra_lo_del_dueno(self):
        datos = self.json_de("hilos", "--json")
        faro = next(h for h in datos["hilos"] if h["nombre"] == "Faro")
        self.assertEqual(faro["relativa"], "proyectos/faro")
        self.assertFalse(faro["archivado"])


class LasSesionesPropiasSeRevisan(ConEstado):
    def revisar(self, propias):
        ctx = SimpleNamespace(config=SimpleNamespace(estado=self.carpeta))
        with mock.patch("telar.movil.propios", return_value=propias):
            (r,) = doctor._sesiones_propias(ctx)
        return r

    def test_sin_ninguna_esta_bien(self):
        r = self.revisar({})
        self.assertEqual(r["estado"], doctor.OK)

    def test_las_de_antes_se_avisan_vivas_o_anotadas(self):
        escribir(self.carpeta, "remotos.json", {"Faro": {"remoto": "servidor", "sesion": "telar-1a2b3c4d"}})
        r = self.revisar({"T84": "telar-9f8e7d6c"})
        self.assertEqual(r["estado"], doctor.AVISO)
        self.assertIn("T84", r["dice"])
        self.assertIn("Faro", r["dice"])
        self.assertIn("retomar", r["arreglo"])

    def test_sin_tmux_no_dice_nada_raro(self):
        ctx = SimpleNamespace(config=SimpleNamespace(estado=self.carpeta))
        with mock.patch("telar.movil.propios", side_effect=OSError("sin tmux")):
            (r,) = doctor._sesiones_propias(ctx)
        self.assertEqual(r["estado"], doctor.OK)


if __name__ == "__main__":
    unittest.main()
