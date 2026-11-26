"""Lo que hacía lento a `telar serve` (26-nov-2026) y no tiene que volver: resolver la misma ruta decenas de miles de
veces por pedido (enrutar los pendientes del día: 16 de los 21 s de `GET /hoy`), y leer el YAML de los mismos cientos
de frontmatters en cada lista de proyectos. Lo guardado nunca sirve lo de antes: el YAML se guarda por su texto, y las
rutas resueltas viven lo que vive el pedido."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import mapas, perfil
from telar.modelo import Hilo
from telar.ordenes import _comun


class ElYamlDeUnFrontmatter(Prueba):
    def setUp(self):
        super().setUp()
        mapas._yaml.cache_clear()

    def test_el_mismo_texto_se_lee_una_vez(self):
        texto = "---\nmapa: pmo\nfechas: [1, 2]\n---\n# Faro\n"
        with mock.patch("yaml.safe_load", wraps=mapas.yaml.safe_load) as leer:
            self.assertEqual(mapas.frontmatter(texto), {"mapa": "pmo", "fechas": [1, 2]})
            self.assertEqual(mapas.frontmatter(texto + "más cuerpo\n"), {"mapa": "pmo", "fechas": [1, 2]})
        self.assertEqual(leer.call_count, 1)

    def test_un_documento_que_cambio_se_lee_de_nuevo(self):
        self.assertEqual(mapas.frontmatter("---\nmapa: pmo\n---\n"), {"mapa": "pmo"})
        self.assertEqual(mapas.frontmatter("---\nmapa: otro\n---\n"), {"mapa": "otro"})

    def test_lo_que_uno_cambia_no_le_llega_al_siguiente(self):
        texto = "---\nfechas: [1, 2]\n---\n"
        primero = mapas.frontmatter(texto)
        primero["fechas"].append(3)
        primero["nuevo"] = True
        self.assertEqual(mapas.frontmatter(texto), {"fechas": [1, 2]})

    def test_lo_que_no_se_entiende_sigue_siendo_vacio(self):
        self.assertEqual(mapas.frontmatter("---\n: : :\n  - [\n---\n"), {})
        self.assertEqual(mapas.frontmatter("---\n- una lista\n---\n"), {})
        self.assertEqual(mapas.frontmatter("sin frontmatter"), {})


class LasRutasDeUnPedido(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        for c in ("proyectos/faro", "proyectos/norte", "areas/caja"):
            (self.raiz / c).mkdir(parents=True)
        self.hilos = tuple(Hilo(id=f"@{i}", nombre=n, ruta=self.raiz / c)
                           for i, (n, c) in enumerate((("Faro", "proyectos/faro"), ("Norte", "proyectos/norte"),
                                                       ("Caja", "areas/caja"))))
        self.tel = _comun.Telar(hilos=self.hilos, raiz=self.raiz)

    def test_cada_ruta_se_resuelve_una_vez_por_telar(self):
        textos = [f"revisar proyectos/faro #norte {i}" for i in range(50)]
        with mock.patch.object(_comun, "ruta_relativa", wraps=_comun.ruta_relativa) as resolver:
            elegidos = {_comun.enrutar(self.tel, t).nombre for t in textos}
        self.assertEqual(elegidos, {"Faro"})
        self.assertLessEqual(resolver.call_count, len(self.hilos))

    def test_la_relativa_es_la_de_siempre(self):
        for h in self.hilos:
            self.assertEqual(self.tel.relativa(h.ruta), _comun.ruta_relativa(h.ruta, self.raiz))
        self.assertEqual(self.tel.relativa(None), "")
        afuera = Path(tempfile.gettempdir())
        self.assertEqual(self.tel.relativa(afuera), _comun.ruta_relativa(afuera, self.raiz))

    def test_un_telar_nuevo_no_trae_lo_de_otro(self):
        self.tel.relativa(self.hilos[0].ruta)
        otro = _comun.Telar(hilos=self.hilos, raiz=self.raiz / "proyectos")
        self.assertEqual(otro.relativa(self.hilos[0].ruta), "faro")

    def test_el_repo_de_una_carpeta_con_las_carpetas_ya_resueltas(self):
        from telar import config as mod_config

        (self.raiz / "empresa").mkdir()
        (self.raiz / "empresa/operacion").mkdir()
        cfg = mod_config.Config(raiz=self.raiz, estado=self.raiz / "e",
                                repos=[mod_config.Repo(nombre="empresa", ruta="empresa"), mod_config.Repo(nombre="vida", ruta=".")])
        carpetas = perfil.carpetas_de_repos(cfg)
        for ruta in ("empresa/operacion", "proyectos/faro", str(self.raiz / "empresa")):
            self.assertEqual(perfil.repo_de(cfg, ruta, carpetas), perfil.repo_de(cfg, ruta))
        self.assertEqual(perfil.repo_de(cfg, "empresa/operacion", carpetas), "empresa")


class ElProcesoAparte(Prueba):
    """En el servicio, la lista de proyectos y los pendientes de todo el repositorio se calculan en un proceso aparte
    (telar.aparte): su CPU no le quita turno a la lista de hilos. Lo que contesta es lo mismo que calculado aquí."""

    def setUp(self):
        super().setUp()
        import os
        import uuid

        from comun import EJEMPLO
        from telar import aparte

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        config = base / "config.toml"
        config.write_text("", encoding="utf-8")
        for clave, valor in (("TELAR_ESTADO", str(base / "estado")), ("TELAR_RAIZ", str(EJEMPLO)),
                             ("TELAR_SESION", f"telar-pruebas-{uuid.uuid4().hex[:8]}"), ("TELAR_CONFIG", str(config))):
            antes = os.environ.get(clave)
            os.environ[clave] = valor
            self.addCleanup(lambda c=clave, a=antes: os.environ.pop(c, None) if a is None else os.environ.__setitem__(c, a))
        self.aparte = aparte
        self.addCleanup(setattr, aparte, "ACTIVO", aparte.ACTIVO)
        self.addCleanup(aparte.apagar)
        self.ctx = aparte.ContextoDelServicio()()

    def correr(self, nombre, **opciones):
        import asyncio

        r = asyncio.run(self.aparte.correr(nombre, self.ctx, **opciones))
        return r if isinstance(r, dict) else r.model_dump(mode="json")

    def test_lo_de_alla_es_lo_mismo_que_lo_de_aqui(self):
        self.aparte.ACTIVO = False
        aqui = (self.correr("proyectos"), self.correr("pendientes", repo=True))
        self.aparte.ACTIVO = True
        with mock.patch("telar.servicios.proyectos.lista", side_effect=AssertionError("se calculó aquí")):
            alla = (self.correr("proyectos"), self.correr("pendientes", repo=True))
        self.assertTrue(aqui[0]["proyectos"])
        self.assertEqual(alla, aqui)

    def test_si_el_proceso_aparte_se_cae_se_calcula_aqui(self):
        import concurrent.futures

        self.aparte.ACTIVO = True
        roto = mock.Mock()
        roto.submit.side_effect = concurrent.futures.process.BrokenProcessPool("se cayó")
        with mock.patch.object(self.aparte, "_el_pool", return_value=roto), self.assertLogs("telar.aparte", "WARNING"):
            r = self.correr("proyectos")
        self.assertTrue(r["proyectos"])
        roto.shutdown.assert_called_once()

    def test_solo_el_servicio_corriendo_lo_enciende(self):
        """`telar serve` lo enciende mientras corre, y lo deja como estaba al terminar: una prueba que llama a su `main`
        (o la CLI) no se queda mandando lo pesado al proceso aparte ni guardando lo de los proveedores."""
        from telar import alla
        from telar.ordenes import serve

        self.aparte.ACTIVO = False
        durante = []
        with mock.patch.object(serve, "_correr", lambda *a, **k: durante.append((alla.MEMORIA, self.aparte.ACTIVO))):
            serve.main(["--puerto", "8799"], mock.Mock())
        self.assertEqual(durante, [(0, False)])
        self.assertEqual((alla.MEMORIA, self.aparte.ACTIVO), (0, False))
        with mock.patch("asyncio.run", lambda c: (c.close(), durante.append((alla.MEMORIA, self.aparte.ACTIVO)))):
            serve._correr(mock.Mock(Server=mock.Mock()), mock.Mock(), [])
        self.assertEqual(durante[-1], (alla.MEMORIA_SERVE, True))
        self.assertEqual((alla.MEMORIA, self.aparte.ACTIVO), (0, False))
