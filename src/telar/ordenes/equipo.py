"""`telar equipo` — que una persona de confianza vea tus tareas del equipo y te sugiera prioridades.

    telar equipo servir [--host IP] [--puerto N]   la página y la API de la persona (solo lee y sugiere)
    telar equipo sugerencias [--todas] [--json]    la bandeja: lo que falta por decidir
    telar equipo sugerencias --remoto telar        la misma bandeja, leída por ssh desde otra máquina
    telar equipo aceptar ID [--nota "…"]           subir la prioridad un nivel (con el CLI de tareas)
    telar equipo rechazar ID [--nota "…"]          cerrarla; la nota la ve quien la hizo
    telar equipo token PERSONA                     un token nuevo para pegar en `[equipo.personas]`

El servidor es otro proceso y otro puerto que `telar web`, a propósito: `telar web` puede escribirles
a tus agentes; este no tiene esa fuerza. Con el token de una persona solo se puede: leer las tareas
marcadas para el equipo (sin su cuerpo), dejar una sugerencia y ver cómo salió. Cada sugerencia
avisa al laptop con una notificación. Ver `telar.equipo`.
"""

from __future__ import annotations

import json
import secrets
import shlex
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telar import equipo as mod_equipo
from telar.ordenes import _comun
from telar.ordenes.web import ip_de_tailscale

AYUDA = "Que una persona de confianza vea tus tareas del equipo y te sugiera prioridades."
MAX_CUERPO = 4096

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>equipo</title>
<style>
:root{color-scheme:dark;--bg:#2e3440;--fg:#d8dee9;--dim:#8590a6;--azul:#81a1c1;--amarillo:#ebcb8b;--verde:#a3be8c;--rojo:#bf616a}
@media (prefers-color-scheme: light){:root{color-scheme:light;--bg:#eceff4;--fg:#2e3440;--dim:#667085;--azul:#4c6f9a;--amarillo:#9a6f00;--verde:#4f7d3a;--rojo:#b3424d}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/22px ui-monospace,Menlo,Consolas,monospace;padding:16px;max-width:760px;margin:auto}
h1{font-size:16px;margin:0 0 4px}.dim{color:var(--dim)}
.t{border-top:1px solid color-mix(in srgb,var(--fg) 16%,transparent);padding:8px 0}
.p{display:inline-block;min-width:2.4em;color:var(--amarillo);font-weight:700}.p0{color:var(--rojo)}.hecha{opacity:.55}
button{font:inherit;color:var(--azul);background:none;border:1px solid var(--azul);border-radius:3px;padding:0 8px;cursor:pointer}
textarea,input{font:inherit;color:inherit;background:transparent;border:1px solid var(--dim);width:100%;box-sizing:border-box;padding:4px}
.ok{color:var(--verde)}.mal{color:var(--rojo)}
</style></head><body>
<h1>equipo</h1><div class="dim" id="quien"></div><div id="msg"></div><div id="lista"></div>
<script>
let token = '';
// el enlace que se le manda a la persona lleva su llave tras el # (no viaja al servidor): se guarda y se borra de la barra
const enlace = /[#&]k=([^&]+)/.exec(location.hash);
if (enlace) { try { localStorage.setItem('equipo.token', decodeURIComponent(enlace[1])); } catch (e) {} history.replaceState(null, '', location.pathname); }
try { token = localStorage.getItem('equipo.token') || ''; } catch (e) {}
const $ = (id) => document.getElementById(id);
const hdr = () => ({ 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' });
const dec = ['aceptada', 'rechazada'];
async function cargar() {
  if (!token) { token = prompt('tu llave de equipo') || ''; if (!token) return; try { localStorage.setItem('equipo.token', token); } catch (e) {} }
  const r = await fetch('api/tareas', { headers: hdr() });
  if (r.status === 401) { try { localStorage.removeItem('equipo.token'); } catch (e) {} token = ''; $('msg').innerHTML = '<span class="mal">llave inválida</span>'; return; }
  const d = await r.json();
  $('quien').textContent = d.quien + ' · lo que el equipo ve de las tareas de Nico';
  const mias = d.sugerencias;
  $('lista').innerHTML = '';
  for (const t of d.tareas) {
    const s = mias.filter((x) => x.tarea === t.id).slice(-1)[0];
    const div = document.createElement('div'); div.className = 't' + (t.estado === 'hecha' ? ' hecha' : '');
    div.innerHTML = '<span class="p p' + t.prioridad + '">P' + (t.prioridad ?? '?') + '</span> <b></b> <span class="dim"></span>';
    div.querySelector('b').textContent = t.id + ' ' + t.titulo;
    div.querySelector('.dim').textContent = [t.estado, t.vence && 'vence ' + t.vence, t.proyecto, t.espera && 'espera ' + t.espera, t.avance].filter(Boolean).join(' · ');
    if (s) { const e = document.createElement('div'); e.className = 'dim'; e.textContent = 'tu sugerencia: ' + s.estado + (s.nota ? ' — ' + s.nota : ''); div.append(e); }
    if (t.estado !== 'hecha' && t.prioridad !== 0 && !(s && s.estado === 'pendiente')) {
      const b = document.createElement('button'); b.textContent = 'sugerir subir prioridad';
      b.onclick = () => formulario(div, t, b); div.append(document.createElement('br'), b);
    }
    $('lista').append(div);
  }
}
function formulario(div, t, b) {
  b.remove();
  const ta = document.createElement('textarea'); ta.rows = 2; ta.maxLength = 500; ta.placeholder = 'por qué debería subir (obligatorio)';
  const go = document.createElement('button'); go.textContent = 'enviar';
  go.onclick = async () => {
    const r = await fetch('api/sugerir', { method: 'POST', headers: hdr(), body: JSON.stringify({ tarea: t.id, motivo: ta.value }) });
    const d = await r.json();
    $('msg').innerHTML = d.ok ? '<span class="ok">sugerencia enviada: Nico la verá</span>' : '<span class="mal"></span>';
    if (!d.ok) $('msg').firstChild.textContent = d.error;
    cargar();
  };
  div.append(ta, go);
}
cargar(); setInterval(() => { if (!document.hidden && !document.querySelector('textarea')) cargar(); }, 60000);
</script></body></html>
"""


def manejador(eq: mod_equipo.Equipo):
    ultimo: dict[str, float] = {}
    candado = threading.Lock()

    class Manejo(BaseHTTPRequestHandler):
        server_version = "telar-equipo"

        def log_message(self, *a):  # silencio: no hay nada que anotar de más
            pass

        def _responder(self, codigo: int, cuerpo, tipo: str = "application/json; charset=utf-8") -> None:
            datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(datos)

        def _persona(self) -> str:
            cabecera = self.headers.get("Authorization", "")
            return mod_equipo.quien(eq, cabecera[7:].strip() if cabecera.startswith("Bearer ") else "")

        def do_GET(self):  # noqa: N802
            ruta = self.path.partition("?")[0]
            if ruta == "/":
                return self._responder(200, PAGINA.encode(), "text/html; charset=utf-8")
            if ruta != "/api/tareas":
                return self._responder(404, {"ok": False, "error": "no hay tal ruta"})
            persona = self._persona()
            if not persona:
                return self._responder(401, {"ok": False, "error": "llave inválida"})
            mias = [r for r in mod_equipo.leer_bandeja(eq) if r["persona"] == persona]
            self._responder(200, {"quien": persona, "tareas": mod_equipo.tareas_visibles(eq),
                                  "sugerencias": [{k: r.get(k) for k in ("id", "tarea", "estado", "nota", "cuando")} for r in mias[-100:]]})

        def do_POST(self):  # noqa: N802
            if self.path.partition("?")[0] != "/api/sugerir":
                return self._responder(404, {"ok": False, "error": "no hay tal ruta"})
            persona = self._persona()
            if not persona:
                return self._responder(401, {"ok": False, "error": "llave inválida"})
            try:
                largo = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                largo = -1
            if not 0 < largo <= MAX_CUERPO:
                return self._responder(400, {"ok": False, "error": "el cuerpo falta o es demasiado grande"})
            try:
                datos = json.loads(self.rfile.read(largo))
                tarea, motivo = str(datos["tarea"]), str(datos["motivo"])
            except (ValueError, KeyError, TypeError):
                return self._responder(400, {"ok": False, "error": "se esperaba {tarea, motivo}"})
            with candado:  # una sugerencia cada 5 s por persona: una mano, no un guion
                ahora = time.monotonic()
                if ahora - ultimo.get(persona, -99) < 5:
                    return self._responder(429, {"ok": False, "error": "más despacio"})
                ultimo[persona] = ahora
                registro, problema = mod_equipo.sugerir(eq, persona, tarea, motivo)
            if registro is None:
                return self._responder(400, {"ok": False, "error": problema})
            threading.Thread(target=mod_equipo.avisar, args=(
                f"{persona} sugiere subir {registro['tarea']}", f"{registro['titulo'][:80]}: {registro['motivo'][:140]}"), daemon=True).start()
            self._responder(200, {"ok": True, "id": registro["id"]})

    return Manejo


def _cuadro(r: dict) -> str:
    pri = "?" if r["prioridad"] is None else f"P{r['prioridad']}"
    return f"{r['id']}  {r['persona']} · {r['tarea']} ({pri}) {r['titulo'][:60]}\n      «{r['motivo']}»  [{r['estado']}]"


def _por_ssh(ctx, remoto: str, argv: list[str]) -> tuple[str, str]:
    elegido = next((r for r in ctx.config.remotos if r.nombre == remoto), None)
    if elegido is None:
        return "", f"no hay remoto «{remoto}»"
    # `bash -lc`: un ssh sin terminal no trae ~/.local/bin, donde viven telar y uv, en el PATH
    comando = shlex.join(["bash", "-lc", shlex.join(["telar", "equipo", *argv])])
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", elegido.destino, comando],
                           capture_output=True, text=True, timeout=40)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", f"no pude hablar con {elegido.destino}: {e}"
    return r.stdout, "" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or f"ssh salió con {r.returncode}")[-300:]


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("equipo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("servir", "sugerencias", "aceptar", "rechazar", "token"))
    p.add_argument("valor", nargs="?", default="", help="aceptar/rechazar: el id · token: la persona")
    p.add_argument("--host", default="", help="servir: la IP donde escuchar (por defecto, la de Tailscale)")
    p.add_argument("--puerto", type=int, default=0, help="servir: el puerto (por defecto, [equipo] puerto)")
    p.add_argument("--todas", action="store_true", help="sugerencias: también las ya resueltas")
    p.add_argument("--nota", default="", help="aceptar/rechazar: lo que ve quien la hizo")
    p.add_argument("--remoto", default="", help="leer o decidir en otra máquina de [remotos], por ssh")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "token":
        if not o.valor:
            return _comun.queja("¿de quién? telar equipo token marcelo")
        print(f'{o.valor.lower()} = "{secrets.token_urlsafe(24)}"   # pégalo en [equipo.personas]')
        return 0
    if o.remoto:
        if o.verbo == "servir":
            return _comun.queja("servir corre en la máquina donde viven las tareas, no por ssh")
        sub = [o.verbo, *([o.valor] if o.valor else []), *(["--todas"] if o.todas else []),
               *(["--nota", o.nota] if o.nota else []), *(["--json"] if o.json else [])]
        salida, problema = _por_ssh(ctx, o.remoto, sub)
        if problema:
            return _comun.queja(problema)
        print(salida, end="")
        return 0
    try:
        eq = mod_equipo.cargar()
    except ValueError as e:
        return _comun.queja(str(e))
    if o.verbo == "servir":
        if not eq.personas:
            return _comun.queja("no hay nadie en [equipo.personas]: `telar equipo token marcelo` da una llave")
        host = o.host or ip_de_tailscale() or "127.0.0.1"
        puerto = o.puerto or eq.puerto
        servidor = ThreadingHTTPServer((host, puerto), manejador(eq))
        print(f"telar equipo en http://{host}:{puerto}  ·  {', '.join(sorted(eq.personas))}  ·  solo lee tareas «{eq.etiqueta}» y recibe sugerencias")
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print()
        return 0
    if o.verbo == "sugerencias":
        registros = [r for r in mod_equipo.leer_bandeja(eq) if o.todas or r["estado"] == "pendiente"]
        if o.json:
            return _comun.escribir_json({"sugerencias": registros})
        print("\n".join(_cuadro(r) for r in registros) or "ninguna sugerencia pendiente")
        return 0
    if not o.valor:
        return _comun.queja(f"¿cuál? telar equipo {o.verbo} ID")
    r, problema = mod_equipo.resolver(eq, o.valor, o.verbo, o.nota)
    if r is None:
        return _comun.queja(problema)
    if o.json:
        return _comun.escribir_json({"sugerencia": r})
    print(f"{r['id']}: {r['estado']}" + (f" (ahora P{r['prioridad_nueva']})" if "prioridad_nueva" in r else ""))
    return 0
