"""La página y la API del equipo: lo que una persona de confianza ve de tus tareas y te puede pedir.

Es **otra app** que la de `telar.api`, a propósito: la tuya puede escribirles a tus agentes; esta no tiene
esa fuerza. Corre en el mismo proceso (`telar serve --equipo`, o sola con `telar equipo servir`), pero en
su propio puerto y con sus propias rutas: con la llave de una persona solo se puede leer las tareas marcadas
para el equipo (sin su cuerpo), sugerir subir una prioridad, pedirte una tarea nueva y ver cómo salió. La
lógica está en telar.equipo.

    GET  /               la página
    GET  /api/tareas     las tareas que se comparten y lo que esa persona ya dejó
    POST /api/sugerir    {tarea, motivo}
    POST /api/pedir      {titulo, contexto?, vence?, aunque_exista?}  (409 con `existe` si ya hay algo parecido)
"""

from __future__ import annotations

import json
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from telar import equipo as mod_equipo

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
<h1>equipo</h1><div class="dim" id="quien"></div><div id="msg"></div>
<div class="t" id="pedir"><b>pedirle algo a Nico</b> <span class="dim">(una tarea nueva; él decide si la agrega)</span><br>
<input id="p-titulo" maxlength="150" placeholder="qué necesitas que haga (ej. hacer la sesión 5 de GOA)">
<textarea id="p-contexto" rows="2" maxlength="500" placeholder="contexto (opcional): por qué, para quién, qué depende de esto"></textarea>
<input id="p-vence" type="date" aria-label="para cuándo (opcional)"> <button id="p-enviar">enviar pedido</button></div>
<div id="pedidos"></div><div id="lista"></div>
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
  $('pedidos').innerHTML = '';
  for (const x of mias.filter((y) => y.tipo === 'tarea').slice(-5).reverse()) {
    const e = document.createElement('div'); e.className = 'dim';
    e.textContent = 'tu pedido «' + x.titulo + '»: ' + x.estado + (x.tarea ? ' (ahora es ' + x.tarea + ')' : '') + (x.nota ? ' — ' + x.nota : '');
    $('pedidos').append(e);
  }
  $('lista').innerHTML = '';
  for (const t of d.tareas) {
    const s = mias.filter((x) => x.tipo !== 'tarea' && x.tarea === t.id).slice(-1)[0];
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
function yaExiste(lista) {
  const m = $('msg'); m.innerHTML = '<span class="mal">ya hay una tarea parecida, mira si es lo mismo:</span>';
  for (const t of lista) { const e = document.createElement('div'); e.className = 'dim'; e.textContent = t.resumen; m.append(e); }
  const b = document.createElement('button'); b.textContent = 'es otra cosa: pedirla igual';
  b.onclick = () => enviarPedido(true); m.append(b);
}
$('p-enviar').onclick = () => enviarPedido(false);
async function enviarPedido(insistir) {
  $('msg').innerHTML = '<span class="dim">revisando si Nico ya tiene algo sobre esto…</span>';
  const r = await fetch('api/pedir', { method: 'POST', headers: hdr(), body: JSON.stringify({ titulo: $('p-titulo').value, contexto: $('p-contexto').value, vence: $('p-vence').value, aunque_exista: insistir }) });
  const d = await r.json();
  if (r.status === 409 && d.existe) { yaExiste(d.existe); return; }
  $('msg').innerHTML = d.ok ? '<span class="ok">pedido enviado: Nico lo verá y decide</span>' : '<span class="mal"></span>';
  if (!d.ok) $('msg').firstChild.textContent = d.error; else { $('p-titulo').value = ''; $('p-contexto').value = ''; $('p-vence').value = ''; }
  cargar();
}
cargar(); setInterval(() => { if (!document.hidden && !document.activeElement.matches('textarea, input') && ![...document.querySelectorAll('textarea, input')].some((c) => c.value)) cargar(); }, 60000);
</script></body></html>
"""


def crear(eq: mod_equipo.Equipo) -> FastAPI:
    app = FastAPI(title="telar equipo", docs_url=None, redoc_url=None, openapi_url=None)
    ultimo: dict[str, float] = {}
    ultimo_chequeo: dict[str, float] = {}
    candado = threading.Lock()

    def responder(request: Request, codigo: int, cuerpo: dict, persona: str = "") -> JSONResponse:
        # una línea al diario del servicio: quién, qué ruta y cómo salió; nunca la llave ni el texto
        detalle = cuerpo.get("error", "") if not cuerpo.get("ok", True) else ""
        print(f"{persona or '?'} {request.method} {request.url.path} -> {codigo} {detalle}".rstrip(), flush=True)
        return JSONResponse(cuerpo, status_code=codigo, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    def persona_de(request: Request) -> str:
        cabecera = request.headers.get("authorization", "")
        return mod_equipo.quien(eq, cabecera[7:].strip() if cabecera.startswith("Bearer ") else "")

    @app.get("/")
    def pagina():
        return HTMLResponse(PAGINA, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/tareas")
    def tareas(request: Request):
        persona = persona_de(request)
        if not persona:
            return responder(request, 401, {"ok": False, "error": "llave inválida"})
        mias = [r for r in mod_equipo.leer_bandeja(eq) if r["persona"] == persona]
        return responder(request, 200, {"quien": persona, "tareas": mod_equipo.tareas_visibles(eq), "sugerencias": [
            {k: r.get(k) for k in ("id", "tipo", "tarea", "titulo", "vence", "estado", "nota", "cuando")} for r in mias[-100:]]},
            persona)

    async def cuerpo_de(request: Request) -> dict | None:
        try:
            largo = int(request.headers.get("content-length", "-1"))
        except ValueError:
            largo = -1
        if not 0 < largo <= MAX_CUERPO:
            return None
        datos = await request.body()
        if len(datos) > MAX_CUERPO:
            return None
        try:
            d = json.loads(datos)
        except ValueError:
            return {}
        return d if isinstance(d, dict) else {}

    @app.post("/api/sugerir")
    async def sugerir(request: Request):
        persona = persona_de(request)
        if not persona:
            return responder(request, 401, {"ok": False, "error": "llave inválida"})
        d = await cuerpo_de(request)
        if d is None:
            return responder(request, 400, {"ok": False, "error": "el cuerpo falta o es demasiado grande"}, persona)
        try:
            pedido = (str(d["tarea"]), str(d["motivo"]))
        except KeyError:
            return responder(request, 400, {"ok": False, "error": "se esperaba {tarea, motivo}"}, persona)
        return registrar(request, persona, "sugerir", pedido, None)

    @app.post("/api/pedir")
    async def pedir(request: Request):
        persona = persona_de(request)
        if not persona:
            return responder(request, 401, {"ok": False, "error": "llave inválida"})
        d = await cuerpo_de(request)
        if d is None:
            return responder(request, 400, {"ok": False, "error": "el cuerpo falta o es demasiado grande"}, persona)
        try:
            pedido = (str(d["titulo"]), str(d.get("contexto", "")), str(d.get("vence") or ""))
        except KeyError:
            return responder(request, 400, {"ok": False, "error": "se esperaba {titulo, contexto?, vence?}"}, persona)
        insistir = d.get("aunque_exista") is True
        with candado:  # revisar cuesta una llamada a un modelo: no más de una cada 3 s por persona.
            ahora = time.monotonic()  # Insistir tras un aviso ya pagó su revisión: solo cuenta el límite de los registrados
            if insistir:
                if ahora - ultimo.get(persona, -99) < 5:
                    return responder(request, 429, {"ok": False, "error": "más despacio"}, persona)
            elif ahora - ultimo_chequeo.get(persona, -99) < 3:
                return responder(request, 429, {"ok": False, "error": "más despacio"}, persona)
            else:
                ultimo_chequeo[persona] = ahora
        # antes de molestar a Nico: ¿ya hay una tarea sobre esto (por palabras o por sentido)? Si el equipo la ve, se le contesta su estado
        parecidas = mod_equipo.parecidas(eq, pedido[0], pedido[1])
        ya = [t for t in parecidas if t["compartida"]]
        if ya and not insistir:
            return responder(request, 409, {"ok": False, "existe": [
                {k: t[k] for k in ("id", "titulo", "estado", "prioridad", "vence", "avance", "espera", "cerrada")} | {"resumen": mod_equipo.resumen_de(t)}
                for t in ya[:3]], "error": "ya hay una tarea parecida; si es otra cosa, envíalo con aunque_exista"}, persona)
        return registrar(request, persona, "pedir", pedido, parecidas)

    def registrar(request: Request, persona: str, que: str, pedido: tuple, parecidas):
        with candado:  # una cada 5 s por persona: una mano, no un guion
            ahora = time.monotonic()
            if ahora - ultimo.get(persona, -99) < 5:
                return responder(request, 429, {"ok": False, "error": "más despacio"}, persona)
            ultimo[persona] = ahora
            registro, problema = (mod_equipo.sugerir(eq, persona, *pedido) if que == "sugerir"
                                  else mod_equipo.pedir(eq, persona, *pedido, similares=parecidas))
        if registro is None:
            return responder(request, 400, {"ok": False, "error": problema}, persona)
        titulo = (f"{persona} sugiere subir {registro['tarea']}" if registro["tipo"] == "prioridad"
                  else f"{persona} te pide una tarea")
        texto = (f"{registro['titulo'][:80]}: {registro['motivo'][:140]}" if registro["tipo"] == "prioridad"
                 else f"{registro['titulo'][:120]}" + (f" (para el {registro['vence']})" if registro["vence"] else ""))
        threading.Thread(target=mod_equipo.avisar, args=(titulo, texto), daemon=True).start()
        return responder(request, 200, {"ok": True, "id": registro["id"]}, persona)

    @app.exception_handler(404)
    async def no_hay(request: Request, _exc):
        return responder(request, 404, {"ok": False, "error": "no hay tal ruta"})

    return app
