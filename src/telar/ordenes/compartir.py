"""`telar compartir` — llevar algo de afuera (un enlace, un texto) a donde corresponde.

    telar compartir --destinos --json                    a dónde se puede llevar
    telar compartir --a hilo:Faro --url URL --texto T    a un hilo o a un agente, como mensaje
    telar compartir --a lecturas --url URL               a un proveedor que recibe cosas
    telar compartir … --json                             lo que pasó, como contrato

Es lo que corre el panel cuando el celular le comparte algo (la hoja «compartir» del teléfono). Los
destinos salen de una tabla fija:

- **Un hilo o un agente** (`hilo:<nombre>`): le llega como mensaje (`telar mensaje`), con lo
  compartido y el texto que se escriba.
- **Un proveedor que recibe** (`<nombre>`): el que declara `recibir` en su configuración, una lista de
  palabras donde `{url}`, `{texto}` y `{titulo}` se reemplazan. Sin shell. Por ejemplo, un feed de
  lecturas:

      [proveedores.lecturas]
      tipo    = "comando"
      comando = ["~/bin/lecturas"]
      recibir = ["~/bin/lecturas", "dejar", "{url}", "--nota", "{texto}"]
      pestana = "leer"

Una dirección tiene que ser http o https. Una palabra que queda vacía (sin url, sin texto) se cae,
junto con la bandera que la precede si es una `--opción`: `--nota {texto}` sin texto no deja un
`--nota` suelto.
"""

from __future__ import annotations

import os
import re
import subprocess

from telar.ordenes import _comun

AYUDA = "Llevar algo de afuera (un enlace, un texto) a un hilo, a un agente o a un proveedor que lo recibe."
MAX = 8000


def receptores(config) -> list[dict]:
    """Los proveedores que reciben cosas compartidas, con su nombre visible."""
    salida = []
    for nombre, p in config.proveedores.items():
        recibir = p.opciones.get("recibir")
        if p.activo and isinstance(recibir, list) and recibir and all(isinstance(x, str) for x in recibir):
            visible = p.opciones.get("pestana") or nombre
            salida.append({"destino": nombre, "nombre": str(visible), "tipo": "proveedor"})
    return salida


def palabras(plantilla: list[str], valores: dict[str, str]) -> list[str]:
    """La plantilla con sus marcas reemplazadas; lo que queda vacío se cae, con su `--opción` delante."""
    salida: list[str] = []
    for i, w in enumerate(plantilla):
        hay_marca = any(f"{{{k}}}" in w for k in valores)
        for k, v in valores.items():
            w = w.replace(f"{{{k}}}", v)
        if hay_marca and not w.strip():
            if salida and salida[-1].startswith("--") and i > 0 and not any(f"{{{k}}}" in plantilla[i - 1] for k in valores):
                salida.pop()
            continue
        salida.append(w)
    if salida:
        salida[0] = os.path.expanduser(salida[0])
    return salida


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("compartir", AYUDA)
    p.epilog = __doc__
    p.add_argument("--destinos", action="store_true", help="a dónde se puede llevar")
    p.add_argument("--a", default="", help="el destino: hilo:<nombre>, o un proveedor que recibe")
    p.add_argument("--url", default="", help="la dirección compartida")
    p.add_argument("--texto", default="", help="el texto compartido o escrito")
    p.add_argument("--titulo", default="", help="el título de lo compartido")
    p.add_argument("--json", action="store_true", help="como JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.destinos:
        lista = receptores(ctx.config)
        if o.json:
            return _comun.escribir_json({"destinos": lista})
        for d in lista:
            print(f"{d['destino']:<16} {d['nombre']}")
        print(_comun.tenue("y cualquier hilo o agente: --a hilo:<nombre>"))
        return 0
    url, texto, titulo = o.url.strip(), o.texto.strip(), o.titulo.strip()
    r = _llevar(ctx, o.a.strip(), url, texto, titulo)
    if o.json:
        _comun.escribir_json(r)
    elif r["ok"]:
        print(r.get("dicho") or "listo")
    else:
        _comun.queja(r["error"])
    return 0 if r["ok"] else 1


def _llevar(ctx, destino: str, url: str, texto: str, titulo: str) -> dict:
    if not destino:
        return {"ok": False, "error": "¿a dónde? --a hilo:<nombre>, o un proveedor que recibe (telar compartir --destinos)"}
    if not (url or texto):
        return {"ok": False, "error": "no hay nada que llevar: --url o --texto"}
    if url and not re.fullmatch(r"https?://\S+", url):
        return {"ok": False, "error": "la dirección tiene que ser http o https"}
    if max(len(url), len(texto), len(titulo)) > MAX:
        return {"ok": False, "error": f"pasa de {MAX} caracteres"}
    if destino.startswith("hilo:"):
        from telar.ordenes import mensaje

        cuerpo = "\n".join(x for x in (texto, f"{titulo}\n{url}".strip() if url else titulo) if x)
        try:
            mensaje.enviar(ctx, destino[5:], f"[compartido desde el celular]\n{cuerpo}")
        except Exception as e:  # noqa: BLE001 - sin bus, o el bus no respondió: se dice
            return {"ok": False, "error": f"no llegó a «{destino[5:]}»: {e}"[:200]}
        return {"ok": True, "dicho": f"le llegó a «{destino[5:]}»"}
    p = ctx.config.proveedores.get(destino)
    plantilla = p.opciones.get("recibir") if p else None
    if not (p and p.activo and isinstance(plantilla, list) and plantilla):
        return {"ok": False, "error": f"«{destino}» no recibe cosas compartidas ([proveedores.{destino}] recibir)"}
    comando = palabras([str(x) for x in plantilla], {"url": url, "texto": texto, "titulo": titulo})
    try:
        c = subprocess.run(comando, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": f"no pude correr {comando[0]}: {type(e).__name__}"}
    if c.returncode != 0:
        return {"ok": False, "error": ((c.stderr or c.stdout).strip().splitlines() or [f"salió con {c.returncode}"])[-1][:200]}
    return {"ok": True, "dicho": (c.stdout.strip().splitlines() or [f"quedó en {p.opciones.get('pestana') or destino}"])[0][:200]}
