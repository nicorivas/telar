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

    def movil(self, propios=None, hilos=()):
        escritos, creados, matados = [], [], []
        parches = [
            mock.patch("telar.movil.propios", return_value=dict(propios or {})),
            mock.patch("telar.movil.hilos", return_value=list(hilos)),
            mock.patch("telar.movil.escribir", side_effect=lambda s, t, enviar=False: escritos.append((s, t, enviar))),
            mock.patch("telar.movil.crear", side_effect=lambda n, c, p, principal="": creados.append((n, c, p)) or HiloMovil(
                sesion=principal or "telar-nuevo", nombre=n, ventana="@9" if principal else "", marca="m" if principal else "")),
            mock.patch("telar.movil._tmux", side_effect=lambda *a, **k: matados.append(a) or ""),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        return escritos, creados, matados


class Encargar(ConEstado):
    def test_libre_se_le_escribe_en_una_linea(self):
        escritos, creados, _ = self.movil({"Gestión": "telar-g"})
        r = m.encargar(self.ctx, self.agente, "/avanzar\nT84")
        self.assertEqual((r["estado"], escritos, creados), ("entregado", [("telar-g", "/avanzar T84", True)], []))
        self.assertEqual(self.est.atencion("Gestión"), Atencion.TRABAJANDO)

    def test_trabajando_queda_en_cola_y_al_terminar_se_reparte(self):
        escritos, _, _ = self.movil({"Gestión": "telar-g"})
        self.est.anotar_atencion("Gestión", Atencion.TRABAJANDO)
        self.assertEqual(m.encargar(self.ctx, self.agente, "/correo")["estado"], "en cola")
        self.assertEqual(m.encargar(self.ctx, self.agente, "/lecturas")["en_cola"], 2)
        self.assertEqual(escritos, [])
        self.assertTrue(m.repartir(self.ctx, "Gestión"))
        self.assertEqual(escritos, [("telar-g", "/correo", True)])
        self.assertEqual([x["texto"] for x in m.pendientes(self.config, "Gestión")], ["/lecturas"])

    def test_sin_sesion_retoma_su_conversacion_con_el_encargo_y_sus_argumentos(self):
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
        self.assertIn("claude --resume abc /avanzar --permission-mode acceptEdits", creados[0][2][-1])

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
        h = lambda n, s, c=0: HiloMovil(nombre=n, sesion=s, clientes=c)  # noqa: E731
        hilos = [h("▶ vieja", "t1"), h("▶ nueva", "t2"), h("mirada", "t3", 1), h("ocupada", "t4"), h("Gestión", "t5")]
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
