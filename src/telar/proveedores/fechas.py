"""El proveedor `fechas`: lo que tiene día y no está en el documento de una unidad (telar.fechas).

Los cronogramas de los documentos de las unidades se leen siempre, sin declarar nada: leer el repositorio no es
salir al mundo. Un proveedor `fechas` suma otras fuentes, con la misma maquinaria que las tareas (`como =
"fechas"` deja tener varios):

    [proveedores.fechas]
    tipo  = "markdown"
    rutas = ["equipo/calendario.md", "operacion/*/seguimiento.md"]   # globs desde la raíz

    [proveedores.gestion]
    como    = "fechas"
    tipo    = "comando"
    comando = ["bin/fechas-de-la-gestion"]   # imprime fechas en JSON (docs/contratos.md, «telar fechas»)

Las fechas no son pendientes del día: `consultar` no devuelve nada, y quien las quiere pide `leer`.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

from telar import fechas as mod_fechas
from telar import proveedores
from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Item
from telar.proveedores import ErrorDeProveedor

NOMBRE = "fechas"


class DeMarkdown:
    """Documentos que no son de una unidad (un calendario compartido) o que la unidad tiene además del suyo
    (`seguimiento.md`): sus `## Cronograma`, cada fila de la unidad que contiene el documento."""

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        rutas = cfg.opciones.get("rutas", [])
        if isinstance(rutas, str):
            rutas = [rutas]
        if not isinstance(rutas, list) or not rutas or not all(isinstance(r, str) and r for r in rutas):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.rutas: se esperaba una lista de globs desde la raíz")
        if any(r.startswith("/") or ".." in Path(r).parts for r in rutas):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.rutas: relativas a la raíz, sin «..»")
        self.rutas = tuple(rutas)
        self.alcance = f"lee los cronogramas de {', '.join(self.rutas)}"

    def consultar(self, dia: date) -> list[Item]:
        return []

    def leer(self, raiz: Path, unidades: dict, mapas=None) -> mod_fechas.Leidas:
        return mod_fechas.documentos(raiz, unidades, self.rutas, solo_rutas=True, mapas=mapas)


class DeComando:
    """Un programa de afuera imprime las fechas: una lista JSON, un objeto con la clave `fechas`, o un objeto por
    línea. Cada una con la forma de docs/contratos.md; `titulo` e `inicio` son obligatorios. Corre en la raíz."""

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        comando = cfg.opciones.get("comando")
        if not isinstance(comando, list) or not comando or not all(isinstance(x, str) and x for x in comando):
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}.comando: se esperaba una lista de palabras, no una línea de shell")
        self.comando = tuple(comando)
        espera = cfg.opciones.get("tiempo_maximo", 20)
        if isinstance(espera, bool) or not isinstance(espera, (int, float)) or espera <= 0:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tiempo_maximo: se esperaba un número positivo")
        self.tiempo_maximo = float(espera)
        escribir = cfg.opciones.get("escribir")
        if escribir is not None and (not isinstance(escribir, list) or not escribir
                                     or not all(isinstance(x, str) and x for x in escribir)):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.escribir: se esperaba una lista de palabras")
        #: cómo cambia una fecha: recibe por la entrada `{"id", "version", "inicio", "fin"}` (solo lo que cambia) y
        #: responde con la fecha como quedó. Sin él, sus fechas son de solo lectura
        self.escribir = tuple(escribir or ())
        editables = cfg.opciones.get("editables", ["inicio", "fin"])
        self.editables = tuple(x for x in editables if x in ("inicio", "fin")) if self.escribir else ()
        #: dónde corre: la raíz, o su `donde` (la carpeta de un módulo, que lo trae en su `[fechas]`)
        self.donde = Path(str(cfg.opciones["donde"])).expanduser() if cfg.opciones.get("donde") else None
        self.alcance = f"corre `{' '.join(self.comando)}` y lee sus fechas"

    def consultar(self, dia: date) -> list[Item]:
        return []

    def leer(self, raiz: Path, unidades: dict, mapas=None) -> mod_fechas.Leidas:
        try:
            r = subprocess.run(list(self.comando), capture_output=True, text=True, timeout=self.tiempo_maximo,
                               cwd=str(self.donde or raiz), env=dict(os.environ, TELAR_RAIZ=str(raiz)),
                               stdin=subprocess.DEVNULL)
        except FileNotFoundError as e:
            raise ErrorDeProveedor(f"no existe el programa {self.comando[0]!r}") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorDeProveedor(f"{self.comando[0]} no respondió en {self.tiempo_maximo:g} s") from e
        except OSError as e:
            raise ErrorDeProveedor(f"{self.comando[0]}: no se pudo correr: {e}") from e
        if r.returncode != 0:
            queja = (r.stderr or "").strip().splitlines()
            raise ErrorDeProveedor(f"{self.comando[0]} salió con {r.returncode}{': ' + queja[0] if queja else ''}")
        leidas = leer_salida(r.stdout, self.nombre, set(unidades))
        if self.editables:
            leidas.fechas = [replace(f, editable=self.editables, bloqueo="") for f in leidas.fechas]
        else:  # el programa puede decir por qué (`bloqueo`); si no, que su fuente no escribe
            leidas.fechas = [f if f.bloqueo else replace(f, bloqueo=f"su fuente «{self.nombre}» es de solo lectura")
                             for f in leidas.fechas]
        return leidas

    def cambiar(self, raiz: Path, unidades: dict, cambio: dict) -> mod_fechas.Fecha:
        """Le pide al programa que cambie una fecha (`escribir`): le pasa el cambio por la entrada y lee la fecha como
        quedó. Un programa que sale con error es un ErrorDeFecha con lo que dijo (422)."""
        if not self.escribir:
            raise mod_fechas.ErrorDeFecha(f"{self.nombre}: sus fechas son de solo lectura (no declara escribir)", 422)
        try:
            r = subprocess.run(list(self.escribir), input=json.dumps(cambio), capture_output=True, text=True,
                               timeout=self.tiempo_maximo, cwd=str(self.donde or raiz),
                               env=dict(os.environ, TELAR_RAIZ=str(raiz)))
        except (OSError, subprocess.TimeoutExpired) as e:
            raise mod_fechas.ErrorDeFecha(f"{self.escribir[0]}: {e}", 502) from e
        if r.returncode != 0:
            queja = (r.stderr or r.stdout or "").strip().splitlines()
            raise mod_fechas.ErrorDeFecha(f"{self.nombre}: {queja[0] if queja else f'salió con {r.returncode}'}",
                                          409 if r.returncode == 9 else 422)
        leidas = leer_salida(r.stdout, self.nombre, set(unidades))
        if not leidas.fechas:
            raise mod_fechas.ErrorDeFecha(f"{self.nombre}: cambió la fecha pero no la devolvió", 502)
        return replace(leidas.fechas[0], editable=self.editables)


def leer_salida(salida: str, origen: str, unidades: set[str]) -> mod_fechas.Leidas:
    """Las fechas que imprimió un programa: una lista, `{"fechas": […]}` o una por línea. Una que no se entiende
    va a `saltadas` con el porqué; las demás llegan igual. Sin `proyecto`, la unidad que contiene su `fuente`."""
    texto = salida.strip()
    try:
        datos = json.loads(texto) if texto else []
    except json.JSONDecodeError:
        try:
            datos = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
        except json.JSONDecodeError as e:
            raise ErrorDeProveedor(f"{origen}: no imprimió JSON: {e}") from e
    if isinstance(datos, dict):
        # `{"fechas": […]}`, o una sola fecha (un programa que imprimió una, en una línea)
        datos = datos.get("fechas", []) if "fechas" in datos or "inicio" not in datos else [datos]
    if not isinstance(datos, list):
        raise ErrorDeProveedor(f"{origen}: se esperaba una lista de fechas")
    leidas = mod_fechas.Leidas()
    for i, d in enumerate(datos):
        try:
            f = mod_fechas.de_json(d, f"{origen}:{i}")
        except ValueError as e:
            leidas.saltadas.append(str(e))
            continue
        if not f.proyecto:
            ruta = f.fuente.split(":")[0]
            f = replace(f, proyecto=mod_fechas.unidad_de(ruta, unidades))
        leidas.fechas.append(f)
    return leidas


IMPLEMENTACIONES = {"markdown": DeMarkdown, "comando": DeComando}


def construir(cfg: ConfigProveedor):
    tipo = cfg.opciones.get("tipo")
    clase = IMPLEMENTACIONES.get(tipo) if isinstance(tipo, str) else None
    if clase is None:
        conocidas = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tipo: {tipo!r} no es una de: {conocidas}")
    return clase(cfg)


def registrar() -> None:
    """Deja este proveedor disponible. Encenderlo sigue siendo de la configuración."""
    if NOMBRE not in proveedores.REGISTRO:
        proveedores.registrar(NOMBRE, construir)


registrar()
