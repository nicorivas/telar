"""El correo entre agentes y telar en el celular: lo que decide, sin ssh ni tmux."""

from __future__ import annotations

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import correo as c
from telar import movil as m
from telar import remoto as r
from telar.config import Remoto

CASA = Remoto(nombre="casa", destino="usuario@servidor")


def correo(id="", asunto="", responde="", referencias=(), para="usuario@servidor", fecha="", estado=""):
    return c.Correo(archivo="", id=id, de="otro", para=para, asunto=asunto, fecha=fecha,
                    responde=responde, referencias=tuple(referencias), estado=estado)


class Direcciones(Prueba):
    def test_la_extension_de_un_nombre(self):
        self.assertEqual(c.extension("T42 Faro Norte"), "t42-faro-norte")
        self.assertEqual(c.extension("Pizza Ñandú"), "pizza-nandu")
        self.assertEqual(c.extension("  ◷ 16:00 reunión  "), "16-00-reunion")
        self.assertEqual(c.extension("⇄"), "")

    def test_la_direccion_de_un_hilo(self):
        self.assertEqual(c.direccion(CASA, "Pizza"), "usuario+pizza@servidor")
        self.assertEqual(c.direccion(CASA, "⇄"), "usuario@servidor")
        self.assertEqual(c.direccion(Remoto("casa", "alias"), "Pizza"), "")  # un alias no dice el usuario

    def test_la_extension_de_una_direccion(self):
        self.assertEqual(c.extension_de("<usuario+pizza@servidor>"), "pizza")
        self.assertEqual(c.extension_de("usuario@servidor"), "")


class Registro(Prueba):
    def test_sin_ids_no_se_saben_los_pendientes(self):
        lineas = ["2026-09-24T12:17:58 ENTREGADO de=otro a=s asunto='x' salida=0"]
        self.assertEqual(c.estados(lineas), ({}, False))
        b = c.desde_json({"correos": [{"id": "<1@s>", "para": "usuario+pizza@servidor"}], "log": lineas})
        self.assertEqual(c.pendientes(b), [])

    def test_con_ids_cada_estado(self):
        lineas = ["2026-09-24T12:17:58 ENTREGADO de=a a=s id=<1@s> asunto='x'",
                  "2026-09-24T12:18:00 RETENIDO b no está id=<2@s> asunto='y'",
                  "2026-09-24T12:19:00 SIN SESIÓN de=a id=<3@s> asunto='z'"]
        estados, sabe = c.estados(lineas)
        self.assertTrue(sabe)
        self.assertEqual(estados, {"<1@s>": "entregado", "<2@s>": "retenido", "<3@s>": "sin sesión"})

    def test_pendientes_por_hilo(self):
        f = "Thu, 24 Sep 2026 13:00:00 -0300"
        datos = {"log": ["2026-09-24T12:17:58 ENTREGADO de=a a=s asunto='x' salida=0 id=<1@s>"],
                 "correos": [{"id": "<1@s>", "para": "usuario+pizza@servidor", "fecha": f},
                             {"id": "<2@s>", "para": "usuario+pizza@servidor", "fecha": f},
                             {"id": "<3@s>", "para": "usuario+otro@servidor", "fecha": f}]}
        b = c.desde_json(datos)
        por = c.por_hilo(c.pendientes(b), ["Pizza"])
        self.assertEqual([x.id for x in por["Pizza"]], ["<2@s>"])


    def test_lo_anterior_a_los_ids_no_se_sabe(self):
        # el registro empezó a anotar ids a las 13:17: un correo de las 12:19 pudo entregarse
        datos = {"log": ["2026-09-24T12:19:03 ENTREGADO de=a a=s asunto='viejo' salida=0",
                         "2026-09-24T13:17:02 ENTREGADO de=a a=s asunto='nuevo' salida=0 id=<n@s>"],
                 "correos": [{"id": "<v@s>", "para": "usuario+pizza@servidor", "fecha": "Thu, 24 Sep 2026 12:19:03 -0300"},
                             {"id": "<p@s>", "para": "usuario+pizza@servidor", "fecha": "Thu, 24 Sep 2026 13:30:00 -0300"}]}
        b = c.desde_json(datos)
        self.assertEqual({x.id: x.estado for x in b.correos}, {"<v@s>": "", "<p@s>": "sin sesión"})


    def test_una_copia_de_la_casilla_comun_no_se_juzga(self):
        f = "Thu, 24 Sep 2026 17:09:23 -0300"
        datos = {"log": ["2026-09-24T13:17:02 ENTREGADO de=a a=s asunto='x' salida=0 id=<x@s>"],
                 "correos": [{"id": "<r@s>", "para": "<otro@servidor>", "fecha": f, "propia": False}]}
        (x,) = c.desde_json(datos).correos
        self.assertEqual(x.estado, "")  # iba a otro usuario: su registro no se ve desde aquí


class Conversaciones(Prueba):
    def test_por_referencias_aunque_falte_un_eslabon(self):
        a = correo(id="<a>", asunto="Pizza", fecha="Thu, 24 Sep 2026 10:00:00 -0300")
        # <b> no está: <c> la cita en References igual que a la raíz
        cc = correo(id="<c>", asunto="Re: Pizza", responde="<b>", referencias=("<a>", "<b>"),
                    fecha="Thu, 24 Sep 2026 12:00:00 -0300")
        otro = correo(id="<z>", asunto="Otra cosa", fecha="Thu, 24 Sep 2026 11:00:00 -0300")
        grupos = c.conversaciones([cc, otro, a])
        self.assertEqual([[x.id for x in g] for g in grupos], [["<a>", "<c>"], ["<z>"]])

    def test_sin_encabezados_por_asunto(self):
        grupos = c.conversaciones([correo(asunto="Prueba"), correo(asunto="Re: Prueba")])
        self.assertEqual(len(grupos), 1)

    def test_con_id_y_sin_cabeceras_de_respuesta_tambien_por_asunto(self):
        # `mail -s "Re: …"` responde sin In-Reply-To: el asunto es lo que queda
        grupos = c.conversaciones([correo(id="<o@s>", asunto="Prueba 5: archivo"),
                                   correo(id="<r@s>", asunto="Re: Prueba 5: archivo"),
                                   correo(id="<z@s>", asunto="Otra")])
        self.assertEqual(sorted(len(g) for g in grupos), [1, 2])


class Movil(Prueba):
    def test_la_barra_tiene_los_rangos_y_escapa_el_nombre(self):
        b = m.barra("50# de algo", 2)
        self.assertIn("#[range=user|volver]", b)
        self.assertIn("#[range=user|correo]✉ 2", b)
        self.assertIn("50## de algo", b)
        self.assertNotIn("correo", m.barra("Pizza", 0))

    def test_la_sesion_agrupada_usa_su_propia_tabla(self):
        ordenes = m.ordenes_grupo("telar-1a2b", "movil-1a2b", "Pizza")
        self.assertEqual(ordenes[0], ["new-session", "-d", "-t", "=telar-1a2b", "-s", "movil-1a2b"])
        opciones = {o[3]: o[4] for o in ordenes if o[0] == "set-option"}
        self.assertEqual(opciones["key-table"], m.TABLA)
        self.assertEqual(opciones["status-position"], "top")
        # las opciones van a la agrupada, nunca a la sesión del hilo, que es la que ve el laptop
        self.assertTrue(all(o[2] == "=movil-1a2b:" for o in ordenes if o[0] == "set-option"))
        # y las teclas, a la tabla propia: ni una en root
        self.assertTrue(all(o[2] == m.TABLA for o in ordenes if o[0] == "bind-key"))


class NombreEnLaSesionRemota(Prueba):
    def test_la_sesion_de_alla_se_anota_su_nombre_desde_adentro(self):
        linea = r.linea("~/repo", None, "Pizza Ñandú")
        self.assertTrue(linea.startswith(f"tmux set-option {r.OPCION_HILO} 'Pizza Ñandú'"))
        # y el comando que viaja por mosh no encadena nada
        self.assertNotIn(";", r.comando(CASA, "telar-1a2b", linea))
