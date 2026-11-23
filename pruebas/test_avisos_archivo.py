"""Los avisos que vienen de un archivo (telar.avisos, `[avisos.<clave>]`): lo que se dice y lo que no (ok, viejo, que no
está, que no se entiende), los de otra máquina por el bus (que solo entrega lo que declara), el informe que la página
puede abrir, lo visto (el mismo aviso se calla; uno nuevo, más grave o que volvió tras ok, sale) y `GET /avisos`."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import avisos
from telar import bus as mod_bus
from telar import config as mod_config


class _ConArchivos(Prueba):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.informe = self.dir / "informe.md"
        self.informe.write_text("# El equipo\n\nEl disco está lleno.\n")

    def escribir(self, nombre: str, **datos) -> Path:
        ruta = self.dir / nombre
        ruta.write_text(json.dumps({"nivel": "aviso", "linea": "el disco está al 92%",
                                    "fecha": datetime.now().isoformat(timespec="seconds"),
                                    "informe": str(self.informe), "sugerencias": 3, **datos}))
        return ruta

    def config(self, texto: str) -> mod_config.Config:
        archivo = self.dir / "config.toml"
        archivo.write_text(f'raiz = "{self.dir}"\nestado = "{self.dir}/estado"\n' + texto)
        return mod_config.cargar(archivo)


class LeerUnArchivo(_ConArchivos):
    def test_un_aviso_y_uno_mal_se_dicen(self):
        d = avisos.leer_archivo(self.escribir("a.json"))
        self.assertEqual((d["nivel"], d["linea"], d["informe"], d["sugerencias"]),
                         ("aviso", "el disco está al 92%", str(self.informe), 3))
        self.assertEqual(avisos.leer_archivo(self.escribir("b.json", nivel="mal"))["nivel"], "mal")

    def test_lo_que_no_se_dice(self):
        viejo = (datetime.now() - timedelta(seconds=avisos.VIEJO + 60)).isoformat(timespec="seconds")
        casos = {"ok": self.escribir("ok.json", nivel="ok"), "viejo": self.escribir("viejo.json", fecha=viejo),
                 "otro nivel": self.escribir("raro.json", nivel="pésimo"), "sin línea": self.escribir("mudo.json", linea=" ")}
        (self.dir / "roto.json").write_text("{no es json")
        casos["roto"] = self.dir / "roto.json"
        (self.dir / "lista.json").write_text("[1, 2]")
        casos["lista"] = self.dir / "lista.json"
        casos["no está"] = self.dir / "no-esta.json"
        for que, ruta in casos.items():
            with self.subTest(que):
                self.assertIsNone(avisos.leer_archivo(ruta))

    def test_sin_fecha_vale_cuando_se_escribio(self):
        ruta = self.escribir("a.json", fecha="")
        self.assertIsNotNone(avisos.leer_archivo(ruta))
        self.assertIsNone(avisos.leer_archivo(ruta, ahora=time.time() + avisos.VIEJO + 60))

    def test_una_fecha_con_zona(self):
        ahora = datetime.now().astimezone().isoformat(timespec="seconds")
        self.assertIsNotNone(avisos.leer_archivo(self.escribir("a.json", fecha=ahora)))

    def test_una_linea_larga_o_con_saltos_queda_en_una(self):
        d = avisos.leer_archivo(self.escribir("a.json", linea="uno\n dos\t" + "x" * 500))
        self.assertTrue(d["linea"].startswith("uno dos x"))
        self.assertLessEqual(len(d["linea"]), 300)


class LaConfiguracion(_ConArchivos):
    def test_se_declaran_con_su_archivo_y_su_maquina(self):
        c = self.config('[avisos.equipo]\narchivo = "~/.local/state/equipo/aviso.json"\n'
                        '[avisos.respaldo]\narchivo = "/var/respaldo/aviso.json"\nen = "servidor"\n')
        self.assertEqual([(a.clave, a.archivo, a.en) for a in c.avisos],
                         [("equipo", "~/.local/state/equipo/aviso.json", ""), ("respaldo", "/var/respaldo/aviso.json", "servidor")])

    def test_lo_que_no_se_entiende(self):
        for texto in ('[avisos.equipo]\nen = "laptop"\n', '[avisos.equipo]\narchivo = "a"\nruta = "b"\n',
                      '[avisos.Equipo]\narchivo = "a"\n', '[avisos.equipo]\narchivo = 3\n'):
            with self.subTest(texto), self.assertRaises(mod_config.ErrorDeConfig):
                self.config(texto)


class DeTodas(_ConArchivos):
    def test_los_de_aqui(self):
        self.escribir("equipo.json")
        self.escribir("bien.json", nivel="ok")
        c = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n'
                        f'[avisos.bien]\narchivo = "{self.dir}/bien.json"\n'
                        f'[avisos.falta]\narchivo = "{self.dir}/no-esta.json"\n')
        r = avisos.de_todas(c)
        self.assertEqual([(a["clave"], a["maquina"], a["nivel"]) for a in r["avisos"]], [("equipo", "", "aviso")])
        self.assertEqual(r["fallas"], {})

    def test_los_de_otra_maquina_por_el_bus(self):
        c = self.config('[bus]\nurl = "nats://127.0.0.1:1"\nmaquina = "servidor"\npersona = "ana"\n'
                        '[avisos.equipo]\narchivo = "~/.local/state/equipo/aviso.json"\nen = "laptop"\n'
                        '[avisos.otro]\narchivo = "~/otro.json"\nen = "laptop"\n')
        respuesta = {"ok": True, "avisos": [{"archivo": "~/.local/state/equipo/aviso.json", "nivel": "mal", "linea": "x",
                                             "fecha": "2026-11-18T15:30:00", "informe": "~/i.md", "sugerencias": None}]}
        with mock.patch.object(mod_bus, "pedir", return_value=respuesta) as pedir:
            r = avisos.de_todas(c)
        self.assertEqual(pedir.call_args.args[1:3], ("laptop", "avisos-archivo"))
        self.assertEqual(pedir.call_args.args[3], {"archivos": ["~/.local/state/equipo/aviso.json", "~/otro.json"]})
        self.assertEqual([(a["clave"], a["maquina"], a["nivel"], a["informe"]) for a in r["avisos"]],
                         [("equipo", "laptop", "mal", "~/i.md")])

    def test_una_maquina_que_no_contesta_no_dice_nada(self):
        c = self.config('[bus]\nurl = "nats://127.0.0.1:1"\nmaquina = "servidor"\npersona = "ana"\n'
                        '[avisos.equipo]\narchivo = "~/aviso.json"\nen = "laptop"\n')
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "nadie atiende"}):
            r = avisos.de_todas(c)
        self.assertEqual((r["avisos"], r["fallas"]), ([], {"equipo": "nadie atiende"}))

    def test_la_otra_maquina_solo_entrega_lo_que_declara(self):
        self.escribir("equipo.json")
        self.escribir("secreto.json")
        c = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n')
        r = avisos.para_otra(c, {"archivos": [f"{self.dir}/equipo.json", f"{self.dir}/secreto.json"]})
        self.assertEqual([a["archivo"] for a in r["avisos"]], [f"{self.dir}/equipo.json"])
        self.assertEqual(avisos.para_otra(c, {"archivos": ["/etc/passwd"]})["avisos"], [])


class LoVisto(_ConArchivos):
    """Dar un aviso por visto lo calla mientras sea el mismo (telar.avisos.es_el_mismo)."""

    def preparar(self, **datos):
        self.ruta = self.escribir("equipo.json", **datos)
        self.c = self.config(f'[avisos.equipo]\narchivo = "{self.ruta}"\n')

    def visto(self) -> bool:
        (a,) = avisos.de_todas(self.c)["avisos"]
        return a["visto"]

    def test_el_mismo_problema_se_esconde(self):
        self.preparar(problemas=["memoria", "swap"])
        self.assertFalse(self.visto())
        r = avisos.marcar_visto(self.c, "equipo")
        self.assertEqual((r["ok"], r["visto"]["nivel"], r["visto"]["problemas"]), (True, "aviso", ["memoria", "swap"]))
        self.assertTrue(self.visto())
        # el agente lo vuelve a escribir igual, o con menos problemas: sigue visto
        self.escribir("equipo.json", problemas=["swap", "memoria"])
        self.assertTrue(self.visto())
        self.escribir("equipo.json", problemas=["memoria"], linea="otra línea")
        self.assertTrue(self.visto())
        # y bajar de nivel tampoco lo saca
        self.escribir("equipo.json", nivel="aviso", problemas=[])
        self.assertTrue(self.visto())

    def test_un_problema_nuevo_lo_muestra(self):
        self.preparar(problemas=["memoria"])
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", problemas=["memoria", "disco"])
        self.assertFalse(self.visto())

    def test_subir_de_aviso_a_mal_lo_muestra(self):
        self.preparar(problemas=["memoria"])
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", nivel="mal", problemas=["memoria"])
        self.assertFalse(self.visto())
        # pero un mal visto que baja a aviso, no
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", nivel="aviso", problemas=["memoria"])
        self.assertTrue(self.visto())

    def test_pasar_por_ok_y_volver_lo_muestra(self):
        self.preparar(problemas=["memoria"])
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", nivel="ok", problemas=[])
        self.assertEqual(avisos.de_todas(self.c)["avisos"], [])
        self.escribir("equipo.json", problemas=["memoria"])
        self.assertFalse(self.visto())

    def test_el_nodo_olvida_los_ok_aunque_nadie_lea(self):
        self.preparar()
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", nivel="ok")
        self.assertEqual(avisos.olvidar_los_ok(self.c), [str(self.ruta)])
        self.assertEqual(avisos._leer_vistos(self.c), {})
        self.assertEqual(avisos.olvidar_los_ok(self.c), [])

    def test_sin_problemas_vale_el_nivel(self):
        self.preparar()
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", linea="el disco está al 95%")
        self.assertTrue(self.visto(), "otra línea, mismo nivel: el mismo")
        self.escribir("equipo.json", nivel="mal")
        self.assertFalse(self.visto(), "subió")

    def test_si_lo_visto_no_tenia_problemas_y_ahora_trae_no_es_el_mismo(self):
        self.preparar()
        avisos.marcar_visto(self.c, "equipo")
        self.escribir("equipo.json", problemas=["memoria"])
        self.assertFalse(self.visto())

    def test_lo_que_vio_la_pagina_no_lo_que_dice_ahora(self):
        # la página mostró «memoria»; entre medio el archivo agregó «disco»: el clic no calla el disco
        self.preparar(problemas=["memoria", "disco"])
        r = avisos.marcar_visto(self.c, "equipo", "aviso", ["memoria"])
        self.assertEqual(r["visto"]["problemas"], ["memoria"])
        self.assertFalse(self.visto())

    def test_lo_que_no_se_puede_dar_por_visto(self):
        self.preparar(nivel="ok")
        self.assertFalse(avisos.marcar_visto(self.c, "equipo")["ok"], "no dice nada")
        self.assertFalse(avisos.marcar_visto(self.c, "no-existe")["ok"])
        self.assertFalse(avisos.marcar_visto(self.c, "equipo", "ok")["ok"])
        self.assertFalse(avisos.visto_para_otra(self.c, {"archivo": "/etc/passwd", "nivel": "aviso"})["ok"],
                         "otra máquina solo marca lo que esta declara")

    def test_se_guarda_en_el_estado_por_la_ruta(self):
        self.preparar(problemas=[" memoria ", "memoria", 3, None, True])
        self.assertEqual(avisos.leer_archivo(self.ruta)["problemas"], ["memoria", "3"])
        avisos.marcar_visto(self.c, "equipo")
        guardado = json.loads((self.dir / "estado" / avisos.VISTOS).read_text())
        self.assertEqual(list(guardado), [str(self.ruta)])
        self.assertEqual(guardado[str(self.ruta)]["problemas"], ["memoria", "3"])

    def test_el_visto_de_otra_maquina_se_marca_alla(self):
        c = self.config('[bus]\nurl = "nats://127.0.0.1:1"\nmaquina = "servidor"\npersona = "ana"\n'
                        '[avisos.equipo]\narchivo = "~/aviso.json"\nen = "laptop"\n')
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "clave": "equipo",
                                                               "visto": {"nivel": "mal", "problemas": ["memoria"]}}) as pedir:
            r = avisos.marcar_visto(c, "equipo", "mal", ["memoria"])
        self.assertEqual(pedir.call_args.args[1:4], ("laptop", "avisos-visto",
                                                     {"archivo": "~/aviso.json", "nivel": "mal", "problemas": ["memoria"]}))
        self.assertEqual((r["ok"], r["desde"]), (True, "laptop"))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "nadie atiende"}):
            self.assertEqual(avisos.marcar_visto(c, "equipo")["error"], "nadie atiende")
        self.assertFalse((self.dir / "estado" / avisos.VISTOS).exists(), "aquí no se escribe nada")

    def test_y_alla_lo_guarda_y_lo_dice_al_leer(self):
        # la máquina donde vive: lo que pide la otra por el bus (visto_para_otra) y lo que le entrega después (para_otra)
        self.preparar(nivel="mal", problemas=["memoria"])
        r = avisos.visto_para_otra(self.c, {"archivo": str(self.ruta), "nivel": "mal", "problemas": ["memoria"]})
        self.assertTrue(r["ok"])
        (a,) = avisos.para_otra(self.c, {"archivos": [str(self.ruta)]})["avisos"]
        self.assertTrue(a["visto"])
        # y la que pidió lo pasa tal cual
        c = self.config('[bus]\nurl = "nats://127.0.0.1:1"\nmaquina = "servidor"\npersona = "ana"\n'
                        f'[avisos.equipo]\narchivo = "{self.ruta}"\nen = "laptop"\n')
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "avisos": [a]}):
            (b,) = avisos.de_todas(c)["avisos"]
        self.assertEqual((b["maquina"], b["visto"], b["problemas"]), ("laptop", True, ["memoria"]))


class ElInforme(_ConArchivos):
    def test_la_pagina_puede_abrir_el_informe_y_nada_mas(self):
        from telar.servicios import archivos

        self.escribir("equipo.json")
        otro = self.dir / "afuera" / "otro.md"
        otro.parent.mkdir()
        otro.write_text("no\n")
        raiz = self.dir / "raiz"
        raiz.mkdir()
        config = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n')
        ctx = SimpleNamespace(config=replace(config, raiz=raiz))
        self.assertEqual(avisos.informes(ctx.config), {self.informe})
        self.assertTrue(archivos.legible(ctx, self.informe))
        self.assertFalse(archivos.legible(ctx, otro.resolve()))
        self.assertIn("El disco está lleno", archivos.leer(ctx, str(self.informe)).texto)

    def test_solo_un_md(self):
        script = self.dir / "algo.sh"
        script.write_text("echo\n")
        self.escribir("equipo.json", informe=str(script))
        config = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n')
        self.assertEqual(avisos.informes(config), set())


@unittest.skipUnless(HAY_FASTAPI, "sin el extra serve")
class LaApi(_ConArchivos):
    def test_get_avisos(self):
        from telar import api

        self.escribir("equipo.json", nivel="mal")
        config = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n')
        r = api.get_avisos(SimpleNamespace(config=config))
        self.assertEqual([(a["clave"], a["nivel"]) for a in r["avisos"]], [("equipo", "mal")])

    def test_post_avisos_visto(self):
        from fastapi import HTTPException

        from telar import api

        self.escribir("equipo.json", nivel="mal", problemas=["memoria"])
        config = self.config(f'[avisos.equipo]\narchivo = "{self.dir}/equipo.json"\n')
        ctx = SimpleNamespace(config=config)
        self.assertFalse(api.get_avisos(ctx)["avisos"][0]["visto"])
        r = api.post_avisos_visto(clave="equipo", nivel="mal", problemas=["memoria"], ctx=ctx)
        self.assertEqual(r["visto"]["problemas"], ["memoria"])
        self.assertTrue(api.get_avisos(ctx)["avisos"][0]["visto"])
        with self.assertRaises(HTTPException) as e:
            api.post_avisos_visto(clave="otro", nivel="", problemas=None, ctx=ctx)
        self.assertEqual(e.exception.status_code, 404)

    def test_el_nodo_lee_en_paralelo_y_marca_de_a_uno(self):
        from telar.ordenes import nodo

        self.assertIn("avisos-archivo", nodo.SOLO_LEEN)
        self.assertNotIn("avisos-visto", nodo.SOLO_LEEN)
