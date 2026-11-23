"""Lo que espera a la persona (docs/propuestas/lo-que-espera-a-la-persona.md, paso 1): el contrato `esperando` de cada
tipo de objeto, cada fuente de fábrica (el permiso o la pregunta en vivo de un hilo, el `avance` de una tarea, un
mensaje retenido), la de un módulo, y cómo las junta `telar esperas` (y `GET /esperas`) sin que una que falla tire
las demás."""

from __future__ import annotations

import io
import json
import stat
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

try:
    import nats  # noqa: F401
    HAY_NATS = True
except ImportError:  # sin el extra «bus»
    HAY_NATS = False

from telar import config as cfg
from telar import estado as mod_estado
from telar import modulos, objetos
from telar.modelo import Atencion
from telar.servicios import ErrorDeServicio
from telar.servicios import esperas as servicio


def espera(direccion: str, desde: str, clase: str = "permiso") -> objetos.Espera:
    return objetos.Espera(direccion=direccion, tipo=direccion.split(":")[0], clase=clase, desde=desde)


class ElContrato(Prueba):
    """Lo común: el método de `Tipo`, el orden, las fallas y el filtro por tipo."""

    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=SimpleNamespace(modulos=()))

    def test_un_tipo_sin_esperas_da_una_lista_vacia(self):
        self.assertEqual(objetos.Archivo().esperando(self.ctx), [])
        self.assertEqual(objetos.Tipo().esperando(self.ctx), [])

    def test_de_la_mas_vieja_a_la_mas_nueva_y_sin_fecha_al_final(self):
        por_tipo = {
            "permiso": [espera("permiso:Faro", "2026-11-17T09:00:00"), espera("permiso:Molino", "")],
            "tarea": [espera("tarea:T2", "2026-11-10", "avance:pregunta"), espera("tarea:T1", "2026-11-10T08:00:00", "avance:cerrar")],
            "mensaje": [espera("mensaje:m1", "2026-11-12T10:00:00", "retenido")],
        }
        with self._fuentes(por_tipo):
            r = servicio.esperas(self.ctx)
        self.assertEqual([e.direccion for e in r.esperas],
                         ["tarea:T2", "tarea:T1", "mensaje:m1", "permiso:Faro", "permiso:Molino"])
        self.assertEqual(r.fallas, {})

    def test_una_fuente_que_falla_no_tira_las_demas(self):
        por_tipo = {"permiso": [espera("permiso:Faro", "2026-11-17T09:00:00")],
                    "tarea": ErrorDeServicio("viven en servidor y no respondió", 502),
                    "mensaje": RuntimeError("se cayó")}
        with self._fuentes(por_tipo):
            r = servicio.esperas(self.ctx)
        self.assertEqual([e.direccion for e in r.esperas], ["permiso:Faro"])
        self.assertEqual(r.fallas["tarea"], "viven en servidor y no respondió")
        self.assertEqual(r.fallas["mensaje"], "RuntimeError: se cayó")

    def test_una_fuente_a_medias_da_lo_que_leyo_y_dice_lo_que_falta(self):
        por_tipo = {"tarea": objetos.Incompletas([espera("tarea:T1", "2026-11-10", "avance:pregunta")], "1 archivo no se leyó")}
        with self._fuentes(por_tipo):
            r = servicio.esperas(self.ctx)
        self.assertEqual([e.direccion for e in r.esperas], ["tarea:T1"])
        self.assertEqual(r.fallas, {"tarea": "1 archivo no se leyó"})

    def test_solo_las_de_un_tipo(self):
        por_tipo = {"permiso": [espera("permiso:Faro", "2026-11-17T09:00:00")],
                    "tarea": [espera("tarea:T1", "2026-11-10", "avance:pregunta")]}
        with self._fuentes(por_tipo) as llamadas:
            r = servicio.esperas(self.ctx, tipos=("tarea",))
            self.assertEqual([e.direccion for e in r.esperas], ["tarea:T1"])
            self.assertEqual(llamadas, ["tarea"])  # las otras ni se leen
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.esperas(self.ctx, tipos=("nada",))
        self.assertEqual(e.exception.codigo, 404)

    def test_la_fecha_de_una_espera(self):
        self.assertEqual(objetos.momento("2026-11-17"), "2026-11-17")
        self.assertEqual(objetos.momento("2026-11-17T09:30:12.5"), "2026-11-17T09:30:12")
        # con zona: la hora de esta máquina, sin zona (como las de las atenciones)
        con_zona = "2026-11-16T15:11:43-03:00"
        local = datetime.fromisoformat(con_zona).astimezone().replace(tzinfo=None).isoformat()
        self.assertEqual(objetos.momento(con_zona), local)
        for malo in ("", None, "ayer", "2026-13-01"):
            self.assertEqual(objetos.momento(malo), "")

    def _fuentes(self, por_tipo: dict):
        """Los tipos de fábrica con su `esperando` cambiado por lo de `por_tipo` (una lista o una excepción)."""
        llamadas = []
        test = self

        class _Ctx:
            def __enter__(self):
                self.parches = []
                # las de fábrica que no se dicen, vacías: ninguna prueba de aquí lee el telar de verdad
                for nombre, valor in {"permiso": [], "tarea": [], "mensaje": [], **por_tipo}.items():
                    tipo = objetos.tipos(test.ctx)[nombre]

                    def falso(ctx, _n=nombre, _v=valor):
                        llamadas.append(_n)
                        if isinstance(_v, BaseException):
                            raise _v
                        return list(_v)

                    p = mock.patch.object(type(tipo), "esperando", side_effect=falso, autospec=False)
                    p.start()
                    self.parches.append(p)
                return llamadas

            def __exit__(self, *a):
                for p in self.parches:
                    p.stop()

        return _Ctx()


class LasTareas(Prueba):
    """El `avance` de una tarea: lo que un agente dejó para que la persona decida."""

    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=SimpleNamespace(tipos=(SimpleNamespace(clave="tarea", en="", carpeta="x"),)))

    def tarea(self, id, avance="", historia=(), **mas):
        from telar.servicios import tipos as st
        from telar.tipos.tarea import Cambio

        return st.TareaConVersion(id=id, titulo=f"la {id}", avance=avance, version="v",
                                  historia=[Cambio(**c) for c in historia], **mas)

    def esperando(self, tareas, fallas=None):
        from telar.servicios import tipos as st

        with mock.patch.object(st, "lista", return_value=st.Tareas(tareas=tareas, fallas=fallas or {})) as lista:
            r = objetos.Tarea().esperando(self.ctx)
        self.assertEqual(lista.call_args.args[1:], ("tarea",))  # solo las abiertas: lista sin --todas
        return r

    def test_cada_marca_con_su_clase_su_fecha_y_su_texto(self):
        r = self.esperando([
            self.tarea("T1", "pregunta 2026-11-10", [
                {"fecha": "2026-11-01", "tipo": "avance", "texto": "pregunta: una vieja"},
                {"fecha": "2026-11-10", "hora": "09:15", "tipo": "avance", "texto": "pregunta: ¿la parto en pasos?"},
                {"fecha": "2026-11-11", "tipo": "nota", "texto": "algo después"}], proyecto="proyectos/faro", prioridad=1),
            self.tarea("T2"),  # sin avance: no espera nada
            self.tarea("T3", "cerrar:hecha 2026-11-12", [{"fecha": "2026-11-12", "tipo": "avance", "texto": "cerrar:hecha: ya se mandó"}]),
            self.tarea("T4", "preparado 2026-11-13"),  # sin la línea en la historia: la fecha del avance, sin texto
            self.tarea("T5", "choca 2026-11-14", [{"fecha": "2026-11-14", "tipo": "avance", "texto": "choca: con T1"}]),
        ])
        por_id = {e.direccion: e for e in r}
        self.assertEqual(sorted(por_id), ["tarea:T1", "tarea:T3", "tarea:T4", "tarea:T5"])
        t1 = por_id["tarea:T1"]
        self.assertEqual((t1.tipo, t1.clase, t1.desde, t1.titulo, t1.resumen),
                         ("tarea", "avance:pregunta", "2026-11-10T09:15:00", "la T1", "¿la parto en pasos?"))
        self.assertEqual(t1.enlaces, ["proyecto:proyectos/faro"])
        self.assertEqual((t1.campos["avance"], t1.campos["prioridad"]), ("pregunta 2026-11-10", 1))
        # para contestarla desde la bandeja: la propuesta entera (el resumen se corta) y la versión que se leyó
        self.assertEqual((t1.campos["texto"], t1.campos["version"]), ("¿la parto en pasos?", "v"))
        t3 = por_id["tarea:T3"]
        self.assertEqual((t3.clase, t3.campos["como"], t3.resumen, t3.desde), ("avance:cerrar", "hecha", "ya se mandó", "2026-11-12"))
        self.assertEqual((por_id["tarea:T4"].clase, por_id["tarea:T4"].desde, por_id["tarea:T4"].resumen),
                         ("avance:preparado", "2026-11-13", ""))
        self.assertEqual(por_id["tarea:T5"].clase, "avance:choca")

    def test_lo_que_hizo_el_agente_con_la_respuesta_anterior(self):
        # la última nota «apliqué: …» después de la última [respuesta]; la de un ciclo anterior, no
        historia = [
            {"fecha": "2026-11-10", "tipo": "avance", "texto": "pregunta: ¿12% o 8%?"},
            {"fecha": "2026-11-10", "tipo": "respuesta", "texto": "el 8%"},
            {"fecha": "2026-11-11", "tipo": "nota", "texto": "apliqué: mandé la contraoferta del 8%"},
            {"fecha": "2026-11-12", "tipo": "respuesta", "texto": "que firme el colegio"},
            {"fecha": "2026-11-12", "tipo": "nota", "texto": "algo que no es «apliqué»"},
            {"fecha": "2026-11-13", "hora": "09:00", "tipo": "nota", "texto": "Apliqué: le pedí la firma"},
            {"fecha": "2026-11-13", "hora": "10:00", "tipo": "nota", "texto": "aplique:  y la dejé en la carpeta "},
            {"fecha": "2026-11-14", "tipo": "avance", "texto": "pregunta: ¿la archivo?"},
        ]
        (e,) = self.esperando([self.tarea("T1", "pregunta 2026-11-14", historia)])
        self.assertEqual(e.campos["aplique"], "y la dejé en la carpeta")
        # después de la última respuesta todavía no dice nada: no se toma la del ciclo anterior
        (e,) = self.esperando([self.tarea("T1", "pregunta 2026-11-14", historia[:5] + historia[7:])])
        self.assertNotIn("aplique", e.campos)
        # sin respuesta, nada (una nota «apliqué» suelta no es de ningún ciclo)
        (e,) = self.esperando([self.tarea("T1", "pregunta 2026-11-14", [historia[2], historia[7]])])
        self.assertNotIn("aplique", e.campos)
        # en NFD (la tilde aparte), igual
        self.assertEqual(objetos.aplicado([SimpleNamespace(tipo="respuesta", texto="sí"),
                                           SimpleNamespace(tipo="nota", texto="aplique\u0301: listo")]), "listo")
        self.assertEqual(objetos.aplicado([]), "")

    def test_sin_tareas_en_esta_maquina_no_es_una_falla(self):
        self.ctx.config.tipos = ()
        self.assertEqual(objetos.Tarea().esperando(self.ctx), [])

    def test_un_archivo_que_no_se_leyo_se_dice(self):
        with self.assertRaises(objetos.Incompletas) as e:
            self.esperando([self.tarea("T1", "pregunta 2026-11-10")], fallas={"T9.md": "clave rota"})
        self.assertEqual([x.direccion for x in e.exception.esperas], ["tarea:T1"])
        self.assertIn("T9.md: clave rota", str(e.exception))

    def test_las_de_otra_maquina_se_releen_cada_tanto(self):
        # allá cada pedido corre `telar tipo tarea lista` entero: la bandeja reusa lo leído hace poco
        from telar import bus as mod_bus
        from telar.servicios import tipos as st

        self.ctx.config.tipos = (SimpleNamespace(clave="tarea", en="servidor", carpeta=""),)
        self.addCleanup(setattr, objetos.Tarea, "_reciente", {})
        lista = st.Tareas(tareas=[self.tarea("T1", "pregunta 2026-11-10")])
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(st, "lista", return_value=lista) as pedir, mock.patch("time.monotonic", side_effect=[100.0, 110.0, 200.0, 200.0]):
            for _ in range(3):
                self.assertEqual([e.direccion for e in objetos.Tarea().esperando(self.ctx)], ["tarea:T1"])
        self.assertEqual(pedir.call_count, 2)  # a los 10 s, lo mismo; a los 100, de nuevo

    def test_un_texto_largo_se_corta(self):
        (e,) = self.esperando([self.tarea("T1", "pregunta 2026-11-10",
                                          [{"fecha": "2026-11-10", "tipo": "avance", "texto": "pregunta: " + "x" * 1000}])])
        self.assertEqual(len(e.resumen), objetos.TOPE_RESUMEN)
        self.assertTrue(e.resumen.endswith("…"))


class LasContestadas(Prueba):
    """Del otro lado: las tareas que la persona contestó y por las que el agente todavía no pasa (`contestada`). Entran
    con una [respuesta] después de la última marca del agente; salen cuando el agente deja algo, cuando vuelve a
    proponer (un `avance`) o cuando se cierran."""

    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=SimpleNamespace(tipos=(SimpleNamespace(clave="tarea", en="", carpeta="x"),)))

    def tarea(self, id, historia=(), **mas):
        from telar.servicios import tipos as st
        from telar.tipos.tarea import Cambio

        return st.TareaConVersion(id=id, titulo=f"la {id}", version="v", historia=[Cambio(**c) for c in historia], **mas)

    def contestadas(self, tareas):
        from telar.servicios import tipos as st

        with mock.patch.object(st, "lista", return_value=st.Tareas(tareas=tareas)):
            return objetos.Tarea().contestadas(self.ctx)

    PROPUSO = {"fecha": "2026-11-17", "hora": "16:55", "tipo": "avance", "texto": "pregunta: ¿12% o 8%?"}
    CONTESTO = {"fecha": "2026-11-18", "hora": "11:20", "tipo": "respuesta", "texto": "el 8%"}

    def test_entra_la_que_contesto_y_el_agente_no_vio(self):
        (c,) = self.contestadas([self.tarea("T1", [self.PROPUSO, self.CONTESTO], proyecto="casa/feria")])
        self.assertEqual((c.direccion, c.titulo, c.cuando, c.respuesta, c.encargada, c.enlaces),
                         ("tarea:T1", "la T1", "2026-11-18T11:20:00", "el 8%", "", ["proyecto:casa/feria"]))

    def test_lo_que_puede_ser_de_cualquiera_no_la_saca(self):
        # mover la fecha, editarla o esperar a alguien después de contestar: el agente igual no ha pasado
        for tipo in ("edita", "mover", "espera"):
            despues = {"fecha": "2026-11-18", "hora": "11:30", "tipo": tipo, "texto": "algo"}
            self.assertEqual([c.direccion for c in self.contestadas([self.tarea("T1", [self.PROPUSO, self.CONTESTO, despues])])],
                             ["tarea:T1"], tipo)

    def test_sale_cuando_el_agente_pasa(self):
        for tipo in sorted(objetos.MARCAS_DEL_AGENTE):
            despues = {"fecha": "2026-11-18", "hora": "13:02", "tipo": tipo, "texto": "apliqué: mandé la contraoferta"}
            self.assertEqual(self.contestadas([self.tarea("T1", [self.PROPUSO, self.CONTESTO, despues])]), [], tipo)
        # y vuelve a entrar si después se contesta de nuevo
        otra = {"fecha": "2026-11-18", "hora": "15:00", "tipo": "respuesta", "texto": "instrucción: con copia a la feria"}
        nota = {"fecha": "2026-11-18", "hora": "13:02", "tipo": "nota", "texto": "apliqué: listo"}
        (c,) = self.contestadas([self.tarea("T1", [self.PROPUSO, self.CONTESTO, nota, otra])])
        self.assertEqual((c.cuando, c.respuesta), ("2026-11-18T15:00:00", "instrucción: con copia a la feria"),
                         "solo lo de después de la última marca del agente")

    def test_no_entran_las_que_esperan_a_la_persona_ni_las_cerradas(self):
        historia = [self.PROPUSO, self.CONTESTO]
        self.assertEqual(self.contestadas([
            self.tarea("T1", historia, avance="pregunta 2026-11-18"),  # propuso de nuevo: espera a la persona
            self.tarea("T2", historia, estado="hecha"),
            self.tarea("T3", historia, estado="algun-dia"),
            self.tarea("T4", [self.PROPUSO]),  # nunca la contestó
            self.tarea("T5"),
        ]), [])
        self.assertEqual([c.direccion for c in self.contestadas([self.tarea("T6", historia, estado="espera")])], ["tarea:T6"],
                         "esperando a alguien, el agente igual la revisa")

    def test_lo_que_contesto_y_si_se_le_aviso_al_agente(self):
        historia = [self.PROPUSO, self.CONTESTO,
                    {"fecha": "2026-11-18", "hora": "11:21", "tipo": "respuesta", "texto": "prompt: mándala hoy"},
                    {"fecha": "2026-11-18", "hora": "12:40", "tipo": "respuesta", "texto": "Prompt: revisar ya: te contesté; atiéndela ahora"}]
        (c,) = self.contestadas([self.tarea("T1", historia)])
        # «revisar ya» no es algo que contestó: dice cuándo se le avisó
        self.assertEqual((c.respuesta, c.encargada, c.cuando), ("el 8% · prompt: mándala hoy", "2026-11-18T12:40:00", "2026-11-18T11:21:00"),
                         "encargarla no la mueve: cuándo contestó sigue siendo lo último que dijo")
        (c,) = self.contestadas([self.tarea("T1", historia[:3])])
        self.assertEqual(c.encargada, "2026-11-18T11:21:00", "«hazte cargo ya» también le avisa")
        (c,) = self.contestadas([self.tarea("T1", [self.PROPUSO, {"fecha": "2026-11-18", "tipo": "respuesta", "texto": "x" * 500}])])
        self.assertEqual((len(c.respuesta), c.respuesta[-1], c.cuando), (objetos.TOPE_RESPUESTA, "…", "2026-11-18"), "con tope; sin hora, la fecha")

    def test_de_la_contestada_hace_mas_tiempo_a_la_mas_nueva(self):
        def contesto(hora):
            return [self.PROPUSO, {**self.CONTESTO, "hora": hora}]
        r = self.contestadas([self.tarea("T1", contesto("12:00")), self.tarea("T2", contesto("09:00")), self.tarea("T3", contesto("10:30"))])
        self.assertEqual([c.direccion for c in r], ["tarea:T2", "tarea:T3", "tarea:T1"])

    def test_sin_tareas_en_esta_maquina_ninguna(self):
        self.assertEqual(objetos.Tarea().contestadas(SimpleNamespace(config=SimpleNamespace())), [])

    def test_la_bandeja_las_trae_aparte(self):
        from telar.servicios import tipos as st

        tareas = st.Tareas(tareas=[self.tarea("T1", [self.PROPUSO, self.CONTESTO]),
                                   self.tarea("T2", [self.PROPUSO], avance="pregunta 2026-11-17")])
        ctx = SimpleNamespace(config=SimpleNamespace(tipos=self.ctx.config.tipos, modulos=()))
        with mock.patch.object(st, "lista", return_value=tareas), \
                mock.patch.object(objetos.Permiso, "esperando", return_value=[]), mock.patch.object(objetos.Mensaje, "esperando", return_value=[]):
            r = servicio.esperas(ctx)
            self.assertEqual([e.direccion for e in r.esperas], ["tarea:T2"], "la que espera a la persona, entre las esperas")
            self.assertEqual([c.direccion for c in r.contestadas], ["tarea:T1"], "la contestada, aparte")
            self.assertEqual(servicio.esperas(ctx, tipos=("permiso",)).contestadas, [], "sin leer las tareas, ninguna")
        # si las tareas no se leyeron, ya se dice en sus fallas: no hay contestadas que inventar
        with mock.patch.object(st, "lista", side_effect=ErrorDeServicio("viven en servidor y no respondió", 502)), \
                mock.patch.object(objetos.Permiso, "esperando", return_value=[]), mock.patch.object(objetos.Mensaje, "esperando", return_value=[]):
            r = servicio.esperas(ctx)
        self.assertEqual((r.contestadas, r.fallas), ([], {"tarea": "viven en servidor y no respondió"}))

    def test_contestar_desde_aqui_hace_releer_las_de_otra_maquina(self):
        # la bandeja reusa lo leído hace poco de otra máquina; quien contesta relee al tiro, y tiene que verse
        from telar.servicios import tipos as st

        objetos.Tarea._reciente = {("servidor", 1): (0.0, st.Tareas(tareas=[]))}
        self.addCleanup(setattr, objetos.Tarea, "_reciente", {})
        t = self.tarea("T1", [self.PROPUSO, self.CONTESTO])
        with mock.patch.object(st, "aplicar", return_value=t), mock.patch.object(objetos, "_hay_productos", return_value=[]):
            objetos.Tarea().hacer(self.ctx, objetos.leer("tarea:T1"), "responder", {"texto": "el 8%"})
        self.assertEqual(objetos.Tarea._reciente, {})


class LosPermisos(Prueba):
    """Los hilos que esperan a la persona: los de aquí (con lo que piden y la pregunta en vivo) y los de las otras
    máquinas en línea."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        self.config = cfg.Config(raiz=self.carpeta, estado=self.carpeta / "estado")
        self.ctx = SimpleNamespace(config=self.config)
        self.est = mod_estado.abrir(self.config)

    def hilo(self, nombre, atencion=Atencion.ESPERA, vivo=True, remoto=""):
        return SimpleNamespace(nombre=nombre, id="@" + nombre, remoto=remoto, atencion=atencion, _vivo=vivo)

    def esperando(self, hilos, fotos=None, bus=False):
        from telar import bus as mod_bus
        from telar import espejo
        from telar.ordenes import _comun

        tel = SimpleNamespace(hilos=hilos, vivo=lambda h: h._vivo)

        def json_hilo(h, tel, con_ficha=True):
            return {"nombre": h.nombre, "relativa": f"proyectos/{h.nombre.lower()}", "atencion": h.atencion.value,
                    "atencion_desde": "2026-11-17T09:00:00"}

        with mock.patch.object(_comun, "tejer", return_value=tel), mock.patch.object(_comun, "json_hilo", side_effect=json_hilo), \
                mock.patch.object(mod_bus, "hay_bus", return_value=bus), mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(espejo, "leer_todos", return_value=fotos or []):
            return objetos.Permiso().esperando(self.ctx)

    def test_los_de_aqui_que_esperan_y_estan_vivos(self):
        self.est.anotar_atencion("Faro", Atencion.ESPERA, datetime(2026, 11, 17, 9, 0, 0))
        self.est.anotar_espera("Faro", "Claude needs your permission to use Bash", "permiso", datetime(2026, 11, 17, 9, 0, 0))
        r = self.esperando([self.hilo("Faro"), self.hilo("Molino", Atencion.TRABAJANDO), self.hilo("Viejo", vivo=False),
                            self.hilo("Ajeno", remoto="servidor")])
        (e,) = r
        self.assertEqual((e.direccion, e.tipo, e.clase, e.desde), ("permiso:Faro", "permiso", "permiso", "2026-11-17T09:00:00"))
        self.assertEqual((e.titulo, e.resumen), ("Claude needs your permission to use Bash",) * 2)
        self.assertEqual(e.enlaces, ["hilo:Faro", "proyecto:proyectos/faro"])

    def test_sin_texto_se_sabe_que_espera(self):
        (e,) = self.esperando([self.hilo("Faro")])
        self.assertEqual((e.titulo, e.resumen, e.clase), ("«Faro» te espera", "", "permiso"))

    def test_la_pregunta_en_vivo_con_sus_opciones(self):
        from telar import casilla

        carpeta = casilla.carpeta(self.config, "Faro")
        (carpeta / "mod").mkdir(parents=True)
        (carpeta / casilla.MOD).write_text("1")
        preguntas = [{"question": "¿Qué paleta?", "header": "Colores", "multiSelect": False,
                      "options": [{"label": "Oscura", "description": "fondo oscuro", "preview": "<p>x</p>"},
                                  {"label": "Clara", "description": ""}]},
                     {"question": "¿Qué más?", "header": "Más", "options": [{"label": "Nada"}]}]
        (carpeta / "mod" / "pregunta.json").write_text(json.dumps({"id": "p1", "estado": "abierta", "desde": time.time() * 1000,
                                                                   "preguntas": preguntas}))
        (e,) = self.esperando([self.hilo("Faro")])
        self.assertEqual((e.clase, e.titulo, e.resumen), ("pregunta", "¿Qué paleta?", "Oscura · Clara (y 1 pregunta más)"))
        self.assertEqual(e.campos["preguntas"][0]["opciones"],
                         [{"etiqueta": "Oscura", "descripcion": "fondo oscuro"}, {"etiqueta": "Clara", "descripcion": ""}])
        # su id: con él se contesta desde la bandeja (POST /hilos/responder)
        self.assertEqual(e.campos["pregunta"], "p1")
        # el objeto la muestra igual (permiso:Faro), y la vista previa no viaja
        from telar.ordenes import _comun

        self.est.anotar_atencion("Faro", Atencion.ESPERA, datetime(2026, 11, 17, 9, 0, 0))
        j = {"nombre": "Faro", "relativa": "proyectos/faro", "atencion": "espera", "atencion_desde": "2026-11-17T09:00:00"}
        tel = SimpleNamespace(hilos=[SimpleNamespace(nombre="Faro", id="@1", remoto="")])
        with mock.patch.object(_comun, "tejer", return_value=tel), mock.patch.object(_comun, "json_hilo", return_value=j):
            o = objetos.ver(self.ctx, "permiso:Faro")
        self.assertEqual((o.titulo, o.campos["clase"]), ("¿Qué paleta?", "pregunta"))
        self.assertNotIn("preview", json.dumps(o.campos))
        # cerrada, ya no es una pregunta en vivo
        (carpeta / "mod" / "pregunta.json").write_text(json.dumps({"id": "p1", "estado": "cerrada"}))
        (e,) = self.esperando([self.hilo("Faro")])
        self.assertEqual((e.clase, e.titulo), ("permiso", "«Faro» te espera"))

    def test_los_de_otra_maquina_en_linea(self):
        fotos = [
            {"nombre": "servidor", "en_linea": True, "hilos": [
                {"nombre": "Telar", "relativa": "proyectos/telar", "atencion": "espera", "vivo": True,
                 "atencion_desde": "2026-11-16T20:00:00"},
                {"nombre": "Dormido", "atencion": "espera", "vivo": False},
                {"nombre": "Faro", "atencion": "espera", "vivo": True, "remoto": "laptop"},  # es el de aquí
                {"nombre": "Trabaja", "atencion": "trabajando", "vivo": True}]},
            {"nombre": "apagada", "en_linea": False, "hilos": [{"nombre": "Fantasma", "atencion": "espera", "vivo": True}]},
            {"nombre": "laptop", "en_linea": True, "hilos": [{"nombre": "Yo", "atencion": "espera", "vivo": True}]},
        ]
        r = self.esperando([self.hilo("Faro")], fotos=fotos, bus=True)
        self.assertEqual([e.direccion for e in r], ["permiso:Faro", "permiso:Telar@servidor"])
        e = r[1]
        self.assertEqual((e.maquina, e.clase, e.desde, e.titulo), ("servidor", "permiso", "2026-11-16T20:00:00", "«Telar» te espera"))
        self.assertEqual(e.enlaces, ["hilo:Telar@servidor", "proyecto:proyectos/telar"])
        # sin bus no se miran las fotos
        self.assertEqual([e.direccion for e in self.esperando([], fotos=fotos, bus=False)], [])


REGISTRO = [
    {"id": "m1", "de": "Molino", "para": "Faro", "texto": "uno  retenido\ny soltado", "estado": "retenido",
     "motivo": "cadena de 7", "creado": "2026-11-14T10:00:00"},
    {"id": "m2", "de": "Faro", "para": "Molino", "texto": "salió", "estado": "enviado", "creado": "2026-11-14T10:01:00"},
    {"id": "m3", "de": "Viento", "para": "Faro", "texto": "nadie lo soltó", "estado": "retenido", "motivo": "demasiados por hora",
     "modo": "encargo", "encargo": "e-1a2b3c4d", "creado": "2026-11-15T08:00:00"},
    {"id": "m1", "de": "Molino", "para": "Faro", "texto": "uno retenido y soltado", "estado": "enviado", "creado": "2026-11-14T10:00:00"},
]


class LosRetenidos(Prueba):
    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x")))

    def test_los_que_nadie_solto(self):
        from telar import bus as mod_bus

        with mock.patch.object(mod_bus, "registro_al_dia", return_value=REGISTRO) as registro:
            (e,) = objetos.Mensaje().esperando(self.ctx)
        self.assertEqual(registro.call_args.args[1], objetos.Mensaje.REGISTRO)  # lo mismo que mira --soltar
        self.assertEqual((e.direccion, e.tipo, e.clase, e.desde), ("mensaje:m3", "mensaje", "retenido", "2026-11-15T08:00:00"))
        self.assertEqual((e.titulo, e.resumen), ("«Viento» → «Faro»", "nadie lo soltó"))
        self.assertEqual(e.enlaces, ["hilo:Faro", "hilo:Viento", "encargo:e-1a2b3c4d"])
        self.assertEqual((e.campos["motivo"], e.campos["modo"]), ("demasiados por hora", "encargo"))
        self.assertEqual(e.campos["texto"], "nadie lo soltó")  # entero: el resumen se corta

    def test_sin_bus_no_hay_y_si_el_bus_falla_se_dice(self):
        from telar import bus as mod_bus

        self.assertEqual(objetos.Mensaje().esperando(SimpleNamespace(config=SimpleNamespace(bus=None))), [])
        with mock.patch.object(mod_bus, "registro_al_dia", side_effect=mod_bus.ErrorDeBus("no responde")):
            with self.assertRaises(ErrorDeServicio) as e:
                objetos.Mensaje().esperando(self.ctx)
        self.assertEqual(e.exception.codigo, 502)

    def test_el_objeto_mensaje(self):
        from telar import bus as mod_bus

        with mock.patch.object(mod_bus, "registro_al_dia", return_value=REGISTRO):
            retenido = objetos.ver(self.ctx, "mensaje:m3")
            soltado = objetos.ver(self.ctx, "mensaje:m1")
            with self.assertRaises(ErrorDeServicio) as e:
                objetos.ver(self.ctx, "mensaje:m9")
            self.assertEqual(e.exception.codigo, 404)
            with self.assertRaises(ErrorDeServicio):
                objetos.hacer(self.ctx, "mensaje:m3", "soltar", {})  # de solo lectura: se suelta con la orden
        self.assertEqual((retenido.estado, retenido.titulo, retenido.campos["soltar"]),
                         ("retenido", "«Viento» → «Faro»", "telar mensaje --soltar m3"))
        self.assertEqual((soltado.estado, soltado.resumen), ("enviado", "uno retenido y soltado"))
        self.assertNotIn("motivo", soltado.campos)
        self.assertIn("mensaje", objetos.tipos(self.ctx))


class ElRegistroPorPartes(Prueba):
    """`bus.registro_al_dia`: lo que el proceso ya leyó no se vuelve a pedir; solo lo que llegó después."""

    def msj(self, s, persona="ana"):
        return (s, {"id": f"m{s}", "persona": persona})

    def test_la_primera_vez_la_ventana_entera_y_despues_solo_lo_nuevo(self):
        from telar.bus import _YaLeido

        y = _YaLeido()
        self.assertEqual(y.desde(1, 100, 10), 61)  # las últimas n*4 secuencias del stream
        r = y.sumar([self.msj(s) for s in (70, 80, 90, 100)], 1, 100, 10)
        self.assertEqual([m["id"] for m in r], ["m70", "m80", "m90", "m100"])
        self.assertEqual(y.desde(1, 100, 10), 101)  # nada nuevo: ni se pide
        self.assertEqual(y.desde(1, 105, 10), 101)
        r = y.sumar([self.msj(103)], 1, 105, 10)
        self.assertEqual([m["id"] for m in r], ["m70", "m80", "m90", "m100", "m103"])
        # lo que salió de la ventana no se devuelve
        self.assertEqual(y.desde(1, 135, 10), 106)
        r = y.sumar([], 1, 135, 10)
        self.assertEqual([m["id"] for m in r], ["m100", "m103"])

    def test_una_ventana_mas_grande_o_un_stream_que_volvio_atras_se_releen(self):
        from telar.bus import _YaLeido

        y = _YaLeido()
        y.desde(1, 100, 10)
        y.sumar([self.msj(90)], 1, 100, 10)
        self.assertEqual(y.desde(1, 100, 20), 21)  # 20 pide desde la 21: lo guardado empieza en la 61
        y.sumar([self.msj(30), self.msj(90)], 1, 100, 20)
        self.assertEqual(y.desde(1, 100, 10), 101)  # y ahora alcanza para las dos
        self.assertEqual(y.desde(1, 50, 10), 11)  # el stream se rehízo: de nuevo, entera

    def test_lo_que_el_bus_borro_se_suelta(self):
        from telar.bus import _YaLeido

        y = _YaLeido()
        y.desde(1, 100, 100)
        y.sumar([self.msj(s) for s in (10, 50, 90)], 1, 100, 100)
        self.assertEqual(y.desde(60, 100, 100), 101)
        self.assertEqual([m["id"] for m in y.sumar([], 60, 100, 100)], ["m90"])
        self.assertEqual([s for s, _ in y.leidos], [90])

    @unittest.skipUnless(HAY_NATS, "sin nats-py (el extra «bus»)")
    def test_contra_un_bus_falso(self):
        from telar import bus as mod_bus

        lecturas = []

        async def leer(js, config, desde):
            lecturas.append(desde)
            return [self.msj(s) for s in range(desde, ultimo["n"] + 1) if s % 10 == 0]

        ultimo = {"n": 100}

        def conexion():
            js = mock.MagicMock()
            js.stream_info = mock.AsyncMock(side_effect=lambda _: SimpleNamespace(
                state=SimpleNamespace(last_seq=ultimo["n"], first_seq=1)))
            nc = mock.MagicMock()
            nc.jetstream.return_value = js
            nc.close = mock.AsyncMock()
            return nc

        config = SimpleNamespace(bus=SimpleNamespace(url="nats://falso", persona="ana-prueba", token=""))
        self.addCleanup(mod_bus._YA_LEIDO.pop, ("nats://falso", "ana-prueba"), None)
        with mock.patch.object(mod_bus, "conectar", new=mock.AsyncMock(side_effect=lambda c: conexion())), \
                mock.patch.object(mod_bus, "_leer_registro", side_effect=leer):
            a = mod_bus.registro_al_dia(config, 10)
            b = mod_bus.registro_al_dia(config, 10)
            ultimo["n"] = 120
            c = mod_bus.registro_al_dia(config, 10)
        self.assertEqual(lecturas, [61, 101])  # la segunda no pidió nada; la tercera, solo lo nuevo
        self.assertEqual([m["id"] for m in a], [f"m{s}" for s in range(70, 101, 10)])
        self.assertEqual(a, b)
        self.assertEqual([m["id"] for m in c], [f"m{s}" for s in range(90, 121, 10)])

    def test_retenidos_mira_lo_mismo_que_soltar(self):
        from telar.ordenes.mensaje import VENTANA_RETENIDOS
        from telar.servicios import mensajes

        self.assertEqual(objetos.Mensaje.REGISTRO, VENTANA_RETENIDOS)
        from telar import bus as mod_bus

        ctx = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x")))
        with mock.patch.object(mod_bus, "registro", return_value=REGISTRO) as registro:
            r = mensajes.registro(ctx, 40, retenidos=True)
            self.assertEqual(registro.call_args.args[1], VENTANA_RETENIDOS)
            self.assertEqual([m["id"] for m in r.mensajes], ["m3"])
            mensajes.registro(ctx, 40)
            self.assertEqual(registro.call_args.args[1], 40)  # sin --retenidos, lo de siempre


ESPERAN = """#!/usr/bin/env python3
import json, sys
p = json.load(sys.stdin)
if sys.argv[1] == "esperan":
    assert p == {}, p
    print(json.dumps({"esperas": [
        {"id": "1a2b", "clase": "pregunta", "desde": "2026-11-16T10:00:00", "titulo": "¿Lo archivo?", "resumen": "de ana",
         "enlaces": ["proyecto:correo", 3], "campos": {"de": "ana"}},
        {"id": "3c4d", "titulo": "sin clase"},
        {"titulo": "sin id: no se puede abrir"}, "basura"]}))
elif sys.argv[1] == "mal":
    print(json.dumps({"nada": []}))
else:
    print(json.dumps({"titulo": "el correo " + p["id"]}))
"""

MANIFIESTO = """nombre = "correo"
[ordenes.ver]
comando = ["bin/c", "ver"]
consulta = true
[ordenes.esperan]
comando = ["bin/c", "esperan"]
consulta = true
[ordenes.mal]
comando = ["bin/c", "mal"]
consulta = true
[ordenes.suelta]
comando = ["bin/c", "suelta"]
[objetos.correo]
ver = "ver"
esperando = "esperan"
"""


class LoDeUnModulo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "correo"
        (self.carpeta / "bin").mkdir(parents=True)
        c = self.carpeta / "bin" / "c"
        c.write_text(ESPERAN)
        c.chmod(c.stat().st_mode | stat.S_IEXEC)

    def ctx(self, manifiesto=MANIFIESTO):
        (self.carpeta / "modulo.toml").write_text(manifiesto)
        m = modulos.leer("correo", self.carpeta)
        return SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))

    def test_su_consulta_da_los_suyos(self):
        ctx = self.ctx()
        r = objetos.tipos(ctx)["correo"].esperando(ctx)
        self.assertEqual([e.direccion for e in r], ["correo:1a2b", "correo:3c4d"])
        self.assertEqual((r[0].tipo, r[0].clase, r[0].desde, r[0].titulo, r[0].resumen),
                         ("correo", "pregunta", "2026-11-16T10:00:00", "¿Lo archivo?", "de ana"))
        self.assertEqual((r[0].enlaces, r[0].campos), (["proyecto:correo"], {"de": "ana"}))
        self.assertEqual(r[1].clase, "correo")  # sin clase, la del tipo
        # y entra a la bandeja con las de fábrica
        with mock.patch.object(objetos.Permiso, "esperando", return_value=[]):
            self.assertEqual([e.direccion for e in servicio.esperas(ctx).esperas], ["correo:1a2b", "correo:3c4d"])

    def test_sin_declararlo_no_espera_nada(self):
        ctx = self.ctx(MANIFIESTO.replace('esperando = "esperan"\n', ""))
        self.assertEqual(objetos.tipos(ctx)["correo"].esperando(ctx), [])
        self.assertNotIn("esperando", modulos.leer("correo", self.carpeta).objetos["correo"])

    def test_tiene_que_ser_una_consulta_suya(self):
        for malo in ('esperando = "nada"', 'esperando = "suelta"', "esperando = 3"):
            with self.subTest(malo=malo), self.assertRaises(modulos.ErrorDeModulo) as e:
                self.ctx(MANIFIESTO.replace('esperando = "esperan"', malo))
            self.assertIn("[objetos.correo]", str(e.exception))

    def test_una_respuesta_sin_la_forma_es_una_falla_del_modulo(self):
        ctx = self.ctx(MANIFIESTO.replace('esperando = "esperan"', 'esperando = "mal"'))
        with mock.patch.object(objetos.Permiso, "esperando", return_value=[]):
            r = servicio.esperas(ctx)
        self.assertEqual(r.esperas, [])
        self.assertIn("esperas", r.fallas["correo"])


class LaOrden(Prueba):
    def correr(self, *argv):
        from telar.ordenes import esperas as orden

        salida = io.StringIO()
        with mock.patch("sys.stdout", salida):
            codigo = orden.main(list(argv), SimpleNamespace(config=SimpleNamespace(modulos=())))
        return codigo, salida.getvalue()

    def test_json_y_texto(self):
        r = servicio.Esperas(esperas=[espera("tarea:T1", "2026-11-10", "avance:pregunta"),
                                      espera("permiso:Faro", "2026-11-17T09:00:00")],
                             fallas={"mensaje": "el bus no responde"})
        with mock.patch.object(servicio, "esperas", return_value=r) as llamada:
            codigo, texto = self.correr("--json", "--tipo", "tarea", "--tipo", "permiso")
            self.assertEqual(llamada.call_args.kwargs["tipos"], ("tarea", "permiso"))
            self.assertEqual(codigo, 0)
            j = json.loads(texto)
            self.assertEqual([e["direccion"] for e in j["esperas"]], ["tarea:T1", "permiso:Faro"])
            self.assertEqual(set(j["esperas"][0]), {"direccion", "tipo", "clase", "desde", "titulo", "resumen", "enlaces",
                                                    "maquina", "campos", "mundo", "agente"})
            self.assertEqual(j["mundos"], [])  # sin [mundos], ninguno
            self.assertEqual(j["fallas"], {"mensaje": "el bus no responde"})
            codigo, texto = self.correr()
        self.assertEqual(codigo, 0)
        self.assertIn("tarea:T1", texto)
        self.assertIn("2 esperas: 1 avance:pregunta, 1 permiso", texto)
        self.assertIn("mensaje: no se pudo leer entero: el bus no responde", texto)
        self.assertNotIn("contestada", texto)
        self.assertEqual(j["contestadas"], [])

    def test_las_contestadas_al_final(self):
        r = servicio.Esperas(contestadas=[objetos.Contestada(direccion="tarea:T512", cuando=""),
                                          objetos.Contestada(direccion="tarea:T550", cuando="2026-11-18T09:00:00")])
        with mock.patch.object(servicio, "esperas", return_value=r), mock.patch("telar.ordenes.esperas.hace", side_effect=lambda d: "3 h" if d else ""):
            codigo, texto = self.correr()
        self.assertEqual(codigo, 0)
        self.assertEqual(texto.splitlines()[-1], "2 contestadas esperando al agente: T512, T550 (3 h)")

    def test_nada_que_esperar(self):
        with mock.patch.object(servicio, "esperas", return_value=servicio.Esperas()):
            self.assertEqual(self.correr(), (0, "nada te espera\n"))

    def test_cuanto_lleva(self):
        from telar.ordenes.esperas import hace

        ahora = datetime(2026, 11, 17, 12, 0, 0)
        self.assertEqual([hace(x, ahora) for x in ("2026-11-17T11:59:50", "2026-11-17T11:30:00", "2026-11-17T09:00:00",
                                                    "2026-11-14", "2026-10-01", "", "nunca")],
                         ["recién", "30 min", "3 h", "3 d", "6 sem", "", ""])

    def test_esta_en_la_ayuda(self):
        from telar import cli

        self.assertIn("esperas", cli.ORDENES)


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None


@unittest.skipIf(api is None, "sin fastapi")
class LaApi(Prueba):
    def test_get_esperas(self):
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=SimpleNamespace(modulos=()))
        self.addCleanup(api.app.dependency_overrides.clear)
        r = servicio.Esperas(esperas=[espera("tarea:T1", "2026-11-10", "avance:pregunta")], fallas={"mensaje": "sin bus"})
        with mock.patch.object(servicio, "esperas", return_value=r) as llamada:
            c = TestClient(api.app)
            j = c.get("/esperas").json()
            self.assertEqual(llamada.call_args.kwargs["tipos"], ())
            c.get("/esperas?tipo=tarea&tipo=permiso")
            self.assertEqual(llamada.call_args.kwargs["tipos"], ("tarea", "permiso"))
        self.assertEqual(j["esperas"][0]["clase"], "avance:pregunta")
        self.assertEqual(j["fallas"], {"mensaje": "sin bus"})
        with mock.patch.object(servicio, "esperas", side_effect=ErrorDeServicio("no hay un tipo «x»", 404)):
            self.assertEqual(TestClient(api.app).get("/esperas?tipo=x").status_code, 404)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
