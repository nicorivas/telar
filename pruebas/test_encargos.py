"""Encargos a un agente residente: entregar, encolar, abrir (retomando o rotando), repartir y el tope."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.movil import HiloMovil  # noqa: E402

from telar import config as mod_config
from telar import encargos as m
from telar import estado as mod_estado
from telar.agentes import Agente
from telar.modelo import Atencion


class ConEstado(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        (base / "agentes" / "gestion").mkdir(parents=True)
        self.config = mod_config.Config(raiz=base, estado=base / "estado", agentes_rotar_mb=1,
                                        agente=mod_config.Agente(nombre="claude-code", max_vivos=3))
        self.ctx = SimpleNamespace(config=self.config)
        self.est = mod_estado.abrir(self.config)
        self.agente = Agente(clave="gestion", nombre="Gestión", carpeta=base / "agentes" / "gestion",
                             argumentos=("--permission-mode", "acceptEdits"))

    def movil(self, vivos=None, hilos=()):
        """`vivos`: nombre → id de los hilos vivos en la lista (su ventana). Lo que se les escribe queda en
        `escritos`, lo que se abre en `creados` y lo que se cierra en `matados`."""
        escritos, creados, matados = [], [], []
        vivos = dict(vivos or {})
        mux = SimpleNamespace(escribir=lambda i, t, enviar=False: escritos.append((i, t, enviar)))
        tel = SimpleNamespace(mux=mux, vivo=lambda h: True,
                              por_nombre=lambda n: SimpleNamespace(id=vivos[n], nombre=n) if n in vivos else None)
        parches = [
            mock.patch("telar.ordenes._comun.tejer", return_value=tel),
            mock.patch("telar.movil.hilos", return_value=list(hilos)),
            mock.patch("telar.movil.crear", side_effect=lambda n, c, p, principal: creados.append((n, c, p)) or HiloMovil(
                sesion=principal, nombre=n, ventana="@9", marca="m")),
            mock.patch("telar.movil._tmux", side_effect=lambda *a, **k: matados.append(a) or ""),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        return escritos, creados, matados


class Encargar(ConEstado):
    def test_libre_queda_en_su_casilla_como_encargo_y_se_le_avisa(self):
        from telar import casilla, encargo

        escritos, creados, _ = self.movil({"Gestión": "@4"})
        r = m.encargar(self.ctx, self.agente, "/avanzar\nT84")
        self.assertEqual((r["estado"], creados), ("avisado", []))
        self.assertTrue(r["direccion"].startswith("encargo:e-"))
        # se le teclea el aviso de su casilla, no el encargo: el contenido entra por sus ganchos
        self.assertEqual(escritos, [("@4", casilla.aviso(self.config, "Gestión"), True)])
        pendiente = casilla.pendientes(self.config, "Gestión")[0]
        self.assertEqual((pendiente["texto"], pendiente["encargo"]), ("/avanzar\nT84", r["encargo"]))
        self.assertEqual(encargo.leer(self.config, r["encargo"])["estado"], "pedido")
        self.assertEqual(self.est.atencion("Gestión"), Atencion.TRABAJANDO)

    def test_trabajando_espera_en_su_casilla_y_su_gancho_se_lo_entrega(self):
        from telar import casilla, encargo

        escritos, _, _ = self.movil({"Gestión": "@4"})
        self.est.anotar_atencion("Gestión", Atencion.TRABAJANDO)
        r = m.encargar(self.ctx, self.agente, "/correo")
        self.assertEqual((r["estado"], escritos), ("en su casilla", []))
        salida = casilla.para_gancho(self.config, "Gestión", "Stop")
        self.assertIn("/correo", salida)
        self.assertEqual(encargo.leer(self.config, r["encargo"])["estado"], "corriendo")

    def test_sin_sesion_retoma_su_conversacion_con_el_aviso_y_sus_argumentos(self):
        from telar import casilla

        _, creados, _ = self.movil()
        archivo = Path(self.tmp.name) / "conv.jsonl"
        archivo.write_text("{}\n")
        self.est.anotar_sesion("Gestión", "abc")
        falso = SimpleNamespace(archivo_de=lambda sid: archivo, retomar=lambda c: ["claude", "--resume", c.id],
                                nuevo_con_id=lambda t: (["claude", "--session-id", "nuevo", t], "nuevo"),
                                anotar=lambda h, c, panel="": None)
        with mock.patch("telar.agente.obtener", return_value=falso):
            r = m.encargar(self.ctx, self.agente, "/avanzar")
        self.assertEqual((r["estado"], r["retoma"]), ("abierto", "abc"))
        aviso = __import__("shlex").quote(casilla.aviso(self.config, "Gestión"))
        self.assertIn(f"claude --resume abc {aviso} --permission-mode acceptEdits", creados[0][2][-1])

    def test_una_conversacion_que_pesa_demasiado_se_rota(self):
        _, creados, _ = self.movil()
        archivo = Path(self.tmp.name) / "conv.jsonl"
        archivo.write_bytes(b"x" * (2 * 1024 * 1024))
        self.est.anotar_sesion("Gestión", "abc")
        falso = SimpleNamespace(archivo_de=lambda sid: archivo, retomar=lambda c: ["claude", "--resume", c.id],
                                nuevo_con_id=lambda t: (["claude", "--session-id", "nuevo", t], "nuevo"),
                                anotar=lambda h, c, panel="": None)
        with mock.patch("telar.agente.obtener", return_value=falso):
            r = m.encargar(self.ctx, self.agente, "/avanzar")
        self.assertEqual(r["retoma"], "")
        self.assertIn("--session-id nuevo", creados[0][2][-1])


class ElTope(ConEstado):
    def test_cierra_las_ociosas_mas_viejas_y_respeta_a_quien_mira_o_trabaja(self):
        h = lambda n, v, c=0: HiloMovil(nombre=n, sesion="telar", ventana=v, marca="m" + v, clientes=c)  # noqa: E731
        hilos = [h("▶ vieja", "@1"), h("▶ nueva", "@2"), h("mirada", "@3", 1), h("ocupada", "@4"), h("Gestión", "@5")]
        _, _, matados = self.movil(hilos=hilos)
        self.est.anotar_atencion("▶ vieja", Atencion.TERMINO, cuando=__import__("datetime").datetime(2026, 1, 1))
        self.est.anotar_atencion("▶ nueva", Atencion.TERMINO, cuando=__import__("datetime").datetime(2026, 1, 2))
        self.est.anotar_atencion("ocupada", Atencion.TRABAJANDO)
        cerrados = m.liberar(self.config, 1, cuidar=("Gestión",))   # 5 vivas + 1 > 3: sobran 3
        # primero las de paso, la más quieta antes; el residente al final
        self.assertEqual(cerrados, ["▶ vieja", "▶ nueva", "Gestión"])

    def test_en_un_servidor_cuentan_las_ventanas_y_se_cierra_la_ventana(self):
        # nadie enganchado directo a la sesión del telar: sus ventanas son hilos y el tope las cuenta
        hilos = [HiloMovil(nombre=f"h{i}", sesion="telar", ventana=f"@{i}", marca=f"m{i}") for i in range(4)]
        pedidos = []
        with mock.patch("telar.movil.sin_mirar", return_value=True), \
             mock.patch("telar.movil.hilos", side_effect=lambda principal="": pedidos.append(principal) or hilos), \
             mock.patch("telar.movil._tmux", side_effect=lambda *a, **k: pedidos.append(a) or ""):
            cerrados = m.liberar(self.config, 1)
        self.assertEqual(pedidos[0], self.config.sesion)
        self.assertEqual(len(cerrados), 2)
        self.assertIn(("kill-window", "-t", "@0"), pedidos)

    def test_sin_tope_no_cierra_nada(self):
        cfg = mod_config.Config(raiz=self.config.raiz, estado=self.config.estado)
        self.assertEqual(m.liberar(cfg, 5), [])


class ElCicloDeUnEncargo(ConEstado):
    """Lo que la 0.5 le agrega al Encargo: corriendo al entregarse, el recordatorio de cerrarlo y cancelarlo."""

    def test_corriendo_recordado_una_vez_y_cerrado(self):
        from telar import casilla, encargo

        self.movil({"Gestión": "@4"})
        self.est.anotar_atencion("Gestión", Atencion.TRABAJANDO)
        eid = m.encargar(self.ctx, self.agente, "/correo")["encargo"]
        casilla.para_gancho(self.config, "Gestión", "Stop")
        self.assertEqual([e["id"] for e in encargo.sin_cerrar(self.config, "Gestión")], [eid])
        texto = encargo.recordatorio(encargo.sin_cerrar(self.config, "Gestión"))
        self.assertIn(f"encargo:{eid}", texto)
        encargo.recordar(self.config, eid)
        self.assertEqual(encargo.sin_cerrar(self.config, "Gestión"), [])  # una vez
        self.assertEqual([e["id"] for e in encargo.de_hilo(self.config, "Gestión", abiertos=True)], [eid])

    def test_cancelar_antes_de_que_llegue_lo_saca_de_su_casilla(self):
        from telar import casilla, encargo

        self.movil({"Gestión": "@4"})
        self.est.anotar_atencion("Gestión", Atencion.TRABAJANDO)
        eid = m.encargar(self.ctx, self.agente, "/correo")["encargo"]
        e = encargo.hacer(self.ctx, eid, "cancelar", {"motivo": "ya lo hice yo"}, quien="Nico")
        self.assertEqual((e["estado"], e["resultado"]), ("cancelado", "ya lo hice yo"))
        self.assertEqual(casilla.pendientes(self.config, "Gestión"), [])
        self.assertIn("salió de su casilla", e["historia"][-1]["nota"])

    def test_cancelar_uno_que_corre_le_dice_que_pare(self):
        from telar import casilla, encargo

        self.movil({"Gestión": "@4"})
        self.est.anotar_atencion("Gestión", Atencion.TRABAJANDO)
        eid = m.encargar(self.ctx, self.agente, "/correo")["encargo"]
        casilla.para_gancho(self.config, "Gestión", "Stop")
        encargo.hacer(self.ctx, eid, "cancelar", {}, quien="Nico")
        pide = casilla.pendientes(self.config, "Gestión")
        self.assertEqual(len(pide), 1)
        self.assertIn("se canceló", pide[0]["texto"])
        with self.assertRaises(encargo.ErrorDeEncargo):
            encargo.hacer(self.ctx, eid, "cerrar", {"resultado": "x"})  # ya está cerrado
