// Lo que la página del dashboard necesita en un navegador y que en VS Code le da el webview:
// `acquireVsCodeApi` (mandar mensajes y guardar su estado), los mensajes que llegan, y la
// interfaz que en VS Code es nativa —avisos, un campo para escribir, un menú para elegir—.
// El script del dashboard (dia.ts) no cambia: habla con `vscode` como siempre, y aquí ese
// `vscode` es la página que lo contiene (src/navegador), por postMessage. Y las otras páginas de un
// hilo en el navegador: su conversación, su terminal, su carpeta, y la de compartir.

import { estilo, estiloBase } from '../estilo';

export const CSS_WEB = estilo('web');

/** El script que va antes del del dashboard: define `acquireVsCodeApi` y la interfaz. El canal: la página
 *  que contiene al dashboard (src/navegador), por postMessage. */
const CANAL_PADRE = String.raw`
  // la página que contiene al dashboard (src/navegador) le habla por postMessage
  var abierto = false, cola = [];
  function conectar() {
    window.addEventListener('message', function (e) {
      if (e.source !== window.parent || !e.data || !e.data.__telarPadre) return;
      llega(e.data.__telarPadre);
    });
    abierto = true; medir();
  }
  function enviar(s) { window.parent.postMessage({ __telarHijo: s }, location.origin === 'null' ? '*' : location.origin); }`;

function script(canal: string): string {
    return String.raw`
(function () {` + canal + String.raw`
  function llega(m) {
      if (m.__recargar) { location.reload(); return; }
      if (m.__aviso) { avisar(m.__aviso, m.nivel, m.ms); return; }
      if (m.__abrir) { window.open(m.__abrir, '_blank', 'noopener'); return; }
      if (m.__copiar) { try { navigator.clipboard.writeText(m.__copiar); } catch (x) {} return; }
      if (m.__mostrar) { try { parent.postMessage({ __mostrar: m.__mostrar }, location.origin); } catch (x) {} return; }
      if (m.__ui) { preguntar(m); return; }
      window.dispatchEvent(new MessageEvent('message', { data: m }));
  }
  function mandar(m) { var s = JSON.stringify(m); if (abierto) enviar(s); else cola.push(s); }
  // cuánto se ve esta página: el servidor le manda los menús y los avisos a la que se está mirando
  // (en un celular, la lista de hilos y el dashboard no se ven a la vez). Oculta, mide 0
  function medir() {
    var llena = false;
    try { llena = window.innerWidth >= window.parent.innerWidth - 2; } catch (x) {}
    // y la página lo sabe también: la barra se dibuja distinto si ocupa la pantalla (un celular)
    document.documentElement.classList.toggle('llena', llena && window.innerWidth > 0);
    if (abierto) enviar(JSON.stringify({ __ancho: window.innerWidth, __llena: llena }));
  }
  window.__telarWeb = true;
  new ResizeObserver(medir).observe(document.documentElement);
  window.acquireVsCodeApi = function () {
    return {
      postMessage: mandar,
      getState: function () { try { return JSON.parse(localStorage.getItem('telar.' + location.pathname) || 'null'); } catch (x) { return null; } },
      setState: function (s) { try { localStorage.setItem('telar.' + location.pathname, JSON.stringify(s)); } catch (x) {} },
    };
  };
  conectar();

  function el(tag, cls, texto) { var e = document.createElement(tag); if (cls) e.className = cls; if (texto != null) e.textContent = texto; return e; }
  var avisos;
  function avisar(texto, nivel, ms) {
    if (!avisos) { avisos = el('div', 'web-avisos'); document.body.appendChild(avisos); }
    var a = el('div', 'web-aviso ' + (nivel || ''), texto);
    avisos.appendChild(a);
    setTimeout(function () { a.remove(); }, ms || 6000);
  }

  // un pedido del servidor que espera respuesta: un campo, un menú, un aviso con botones
  function preguntar(m) {
    // <dialog>: el navegador pone el fondo, atrapa el foco adentro y cierra con Escape (evento cancel)
    var caja = el('dialog', 'web-caja');
    document.body.appendChild(caja);
    var listo = false;
    function responder(valor) {
      if (listo) return; listo = true; caja.close(); caja.remove();
      mandar({ __ui_r: m.__ui, valor: valor });
    }
    caja.addEventListener('cancel', function (e) { e.preventDefault(); responder(null); });
    // un clic fuera de la caja (en el fondo) es cancelar: el dialog ocupa solo la caja
    caja.addEventListener('click', function (e) {
      var r = caja.getBoundingClientRect();
      if (e.target === caja && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) responder(null);
    });
    if (m.titulo) caja.appendChild(el('h3', null, m.titulo));
    if (m.ayuda) caja.appendChild(el('p', 'ayuda', m.ayuda));
    if (m.tipo === 'campo') {
      var inp = el('input'); inp.value = m.valor || ''; inp.placeholder = m.placeholder || '';
      if (m.password) inp.type = 'password';
      var prob = el('div', 'problema', m.problema || '');
      caja.appendChild(inp); caja.appendChild(prob);
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); responder(inp.value); }
      });
      caja.showModal(); inp.focus(); inp.select();
    } else if (m.tipo === 'elegir') {
      var filtro = el('input'); filtro.placeholder = m.placeholder || 'buscar';
      var lista = el('div', 'web-lista'); caja.appendChild(filtro); caja.appendChild(lista);
      var vis = [], sel = 0;
      function norm(t) { return (t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
      function pintar() {
        lista.innerHTML = ''; vis = []; var q = norm(filtro.value);
        m.opciones.forEach(function (o, i) {
          if (o.separador) { if (!q) lista.appendChild(el('div', 'web-sep', o.label)); return; }
          if (q && norm(o.label + ' ' + (o.description || '') + ' ' + (o.detail || '')).indexOf(q) < 0) return;
          var f = el('div', 'web-op'); f.appendChild(el('span', null, o.label));
          if (o.description) f.appendChild(el('span', 'd', o.description));
          f.addEventListener('click', function () { responder(i); });
          vis.push([f, i]); lista.appendChild(f);
        });
        sel = Math.min(sel, Math.max(0, vis.length - 1));
        vis.forEach(function (v, k) { v[0].classList.toggle('sel', k === sel); });
      }
      filtro.addEventListener('input', function () { sel = 0; pintar(); });
      filtro.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); pintar(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); pintar(); }
        if (e.key === 'Enter') { e.preventDefault(); if (vis[sel]) responder(vis[sel][1]); }
      });
      pintar(); caja.showModal(); filtro.focus();
    } else {
      // un aviso con botones
      caja.appendChild(el('p', null, m.texto));
      var bot = el('div', 'botones');
      (m.botones || []).forEach(function (b) { var a = el('a', null, b); a.addEventListener('click', function () { responder(b); }); bot.appendChild(a); });
      var c = el('a', null, 'cancelar'); c.addEventListener('click', function () { responder(null); }); bot.appendChild(c);
      caja.appendChild(bot);
      caja.showModal();
      var primero = bot.querySelector('a'); if (primero) { primero.tabIndex = 0; primero.focus(); }
    }
  }
})();
`;
}

/** El script del dashboard que corre en el navegador (src/navegador): le habla a la página que lo contiene. */
export const SCRIPT_NAVEGADOR = script(CANAL_PADRE);

/** La carpeta de un hilo y uno de sus archivos, para `paginaDocumento` (en el navegador, de `/api/hilos/documento`). */
export interface Documento {
    hilo: string; titulo: string; error?: string;
    carpeta?: string; archivo?: string; subir?: string;
    archivos?: { nombre: string; ruta: string }[];
    /** el archivo, ya convertido (markdown) o como texto */
    html?: string; texto?: string;
}

const escHtml = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** La carpeta de un hilo y su documento, en la web (lo que en VS Code son la ficha y la vista de
 *  carpeta): la lista de archivos arriba, y el elegido abajo. Solo lee. */
export function paginaDocumento(nonce: string, d: Documento): string {
    const enlace = (ruta: string, texto: string, clase = '') =>
        `<a class="${clase}" href="/documento?hilo=${encodeURIComponent(d.hilo)}&amp;archivo=${encodeURIComponent(ruta)}">${escHtml(texto)}</a>`;
    const cuerpo = d.error ? `<p class="nada">${escHtml(d.error)}</p>`
        : `<nav class="carpeta"><div class="donde">${escHtml(d.carpeta ?? '.')}</div>`
            + (d.subir !== undefined ? enlace(d.subir, '../', 'dir') : '')
            + (d.archivos ?? []).map(a => enlace(a.ruta, a.nombre, `${a.nombre.endsWith('/') ? 'dir' : ''}${a.ruta === d.archivo ? ' sel' : ''}`)).join('')
            + `</nav>`
            + (d.archivo ? `<article><div class="donde">${escHtml(d.archivo)}</div>${d.html ? `<div class="md">${d.html}</div>` : `<pre>${escHtml(d.texto ?? '')}</pre>`}</article>` : '');
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:;">
<title>${escHtml(d.titulo)} · telar</title>
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { ${estilo('documento')} }</style>
</head><body><h1>${escHtml(d.titulo)}</h1>${cuerpo}</body></html>`;
}

/** Lo que el teléfono le comparte al panel instalado como app (`share_target` del manifiesto): un
 *  enlace o un texto, para llevarlo a un hilo, a un agente o a un proveedor que lo recibe (un feed de
 *  lecturas). Lo lleva `telar compartir`. */
export function paginaCompartir(nonce: string, rutas: { consulta?: string } = {}): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src 'self';">
<title>compartir · telar</title>
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { ${estilo('compartir')} }</style>
</head><body>
<header><a href="/" target="_top">◀ telar</a><b>compartir</b></header>
<main>
  <section id="que"></section>
  <textarea id="nota" rows="3" placeholder="una nota, si quieres (va con lo compartido)"></textarea>
  <input id="filtro" placeholder="filtrar destinos" autocomplete="off">
  <div id="destinos"><p class="dim">leyendo destinos…</p></div>
  <p id="dicho" class="dim"></p>
</main>
<script nonce="${nonce}">
(function () {
  // en el navegador (un iframe srcdoc) lo compartido llega por parámetro: la dirección es la de la página de arriba
  var R = ${JSON.stringify(rutas).replace(/</g, '\\u003c')};
  var q = new URLSearchParams(R.consulta != null ? R.consulta : location.search);
  var titulo = (q.get('title') || '').trim(), texto = (q.get('text') || '').trim(), url = (q.get('url') || '').trim();
  // muchas apps mandan el enlace dentro del texto, no en url
  if (!url) { var m = texto.match(/https?:\\/\\/\\S+/); if (m) { url = m[0]; texto = texto.replace(m[0], '').trim(); } }
  function el(tag, cls, t) { var e = document.createElement(tag); if (cls) e.className = cls; if (t != null) e.textContent = t; return e; }
  var que = document.getElementById('que');
  if (titulo) que.appendChild(el('div', 'titulo', titulo));
  if (url) que.appendChild(el('div', 'url', url));
  if (texto) que.appendChild(el('div', 'texto', texto));
  if (!titulo && !url && !texto) que.appendChild(el('div', 'dim', 'nada compartido: escribe una nota y elige a dónde'));
  var dicho = document.getElementById('dicho'), lista = [], filtro = document.getElementById('filtro');
  function pintar() {
    var cont = document.getElementById('destinos'), f = filtro.value.toLowerCase();
    cont.textContent = '';
    var grupos = [['proveedor', 'guardar en'], ['hilo', 'mandar a un hilo']];
    grupos.forEach(function (g) {
      var de = lista.filter(function (d) { return d.tipo === g[0] && (!f || d.nombre.toLowerCase().indexOf(f) >= 0); });
      if (!de.length) return;
      cont.appendChild(el('div', 'grupo', g[1]));
      de.forEach(function (d) {
        var b = el('button', 'destino', d.nombre);
        b.addEventListener('click', function () { llevar(d, b); });
        cont.appendChild(b);
      });
    });
  }
  function llevar(d, b) {
    var nota = document.getElementById('nota').value.trim();
    if (!url && !texto && !nota) { dicho.textContent = 'no hay nada que llevar'; return; }
    b.disabled = true; dicho.className = 'dim'; dicho.textContent = 'llevando a ' + d.nombre + '…';
    fetch('/api/compartir', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ a: d.destino, url: url, titulo: titulo, texto: [nota, texto].filter(Boolean).join('\\n') }) })
      .then(function (r) { return r.json(); })
      .then(function (r) { dicho.className = r.ok ? 'bien' : 'mal'; dicho.textContent = r.ok ? (r.dicho || 'listo') : (r.error || 'no salió'); })
      .catch(function () { dicho.className = 'mal'; dicho.textContent = 'sin conexión con telar'; })
      .then(function () { b.disabled = false; });
  }
  filtro.addEventListener('input', pintar);
  // los proveedores que reciben, y los hilos (de esta máquina y de las otras)
  var hilos = fetch('/api/hilos?ficha=false&red=true', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (d) { return (d.hilos || []).filter(function (h) { return !h.archivado; })
      .map(function (h) { return { destino: 'hilo:' + h.nombre, nombre: h.nombre, tipo: 'hilo' }; }); })
    .catch(function () { return []; });
  fetch('/api/compartir/destinos', { credentials: 'same-origin' }).then(function (r) { return r.json(); })
    .then(function (d) { return hilos.then(function (hs) { lista = (d.destinos || []).concat(hs); pintar(); }); })
    .catch(function () { document.getElementById('destinos').textContent = 'no pude leer los destinos'; });
})();
</script></body></html>`;
}

/** Un hilo leído como conversación, para el celular: los últimos turnos (`telar hilo leer`, releídos
 *  cada pocos segundos), una caja para escribirle y las teclas para contestarle una pregunta (⏎, ⎋,
 *  1-3, ↑↓). Lo escrito va por el mismo canal que la terminal (`/pty`, una vista de `telar mirar`):
 *  es teclear en el hilo, con la misma llave. */
/** De qué hilo es la página de una conversación (un iframe srcdoc no tiene dirección de donde leerlo). Lee
 *  de la API (`/api/hilos/leer`) y escribe por la terminal (`/pty` de telar.api_web) a un hilo de aquí, o
 *  como mensaje (`/api/mensajes`, por el bus) a uno de otra máquina. */
export interface RutasConversacion {
    hilo?: string; maquina?: string;
}

export function paginaConversacion(nonce: string, rutas: RutasConversacion = {}): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src 'self';">
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { ${estilo('conversacion')} }</style>
</head><body>
<main id="turnos"><p class="nada">leyendo…</p></main>
<footer>
  <div id="teclas">
    <button data-t="\\r">⏎</button><button data-t="\\u001b">⎋</button><button data-t="1">1</button><button data-t="2">2</button><button data-t="3">3</button><button data-t="\\u001b[A">↑</button><button data-t="\\u001b[B">↓</button>
  </div>
  <form id="escribir"><textarea id="texto" rows="2" placeholder="escríbele al hilo (⏎ envía, ⇧⏎ línea nueva)"></textarea><button type="submit">enviar</button></form>
  <p id="dijo" class="nada"></p>
</footer>
<script nonce="${nonce}">
(function () {
  var q = new URLSearchParams(location.search), R = ${JSON.stringify(rutas).replace(/</g, '\\u003c')};
  var hilo = R.hilo || q.get('hilo') || '', maquina = R.maquina || q.get('maquina') || '';
  // un hilo de otra máquina se lee por la API y se le escribe como mensaje (por el bus); uno de aquí, por su terminal
  var porMensaje = !!maquina;
  var turnos = document.getElementById('turnos'), texto = document.getElementById('texto'), dijo = document.getElementById('dijo');
  // un hilo de otra máquina se lee y se le escribe por el bus: sin terminal, no hay teclas que apretar
  if (porMensaje) { document.getElementById('teclas').hidden = true; texto.placeholder = (maquina ? 'escríbele al hilo (en ' + maquina + ', por el bus' : 'escríbele al hilo (le llega como mensaje') + '; ⏎ envía, ⇧⏎ línea nueva)'; }
  var QUIEN = { usuario: 'tú', agente: 'agente', herramienta: '·' };
  function el(tag, cls, t) { var e = document.createElement(tag); if (cls) e.className = cls; if (t != null) e.textContent = t; return e; }
  function abajo() { return turnos.scrollHeight - turnos.scrollTop - turnos.clientHeight < 40; }
  var ultimo = '';
  function pintar(d) {
    var firma = JSON.stringify(d);
    if (firma === ultimo) return;
    ultimo = firma;
    var seguir = abajo() || !turnos.dataset.leido;
    turnos.textContent = '';
    if (d.error) { turnos.appendChild(el('p', 'nada', d.error)); return; }
    if (d.fuente === 'panel') { turnos.appendChild(el('pre', 'panel', d.texto || '')); }
    else {
      if (d.recortado || (d.total_turnos || 0) > (d.turnos || []).length) turnos.appendChild(el('p', 'nada', 'turnos anteriores sin mostrar'));
      (d.turnos || []).forEach(function (turno) {
        var t = el('section', 'turno');
        turno.forEach(function (m) {
          var f = el('div', 'msj ' + m.quien);
          if (m.quien !== 'herramienta') f.appendChild(el('span', 'quien', QUIEN[m.quien] || m.quien));
          var c = el('div', m.html ? 'cuerpo md' : 'cuerpo');
          if (m.html) c.innerHTML = m.html; else c.textContent = m.texto || '';
          f.appendChild(c);
          t.appendChild(f);
        });
        turnos.appendChild(t);
      });
      if (!(d.turnos || []).length) turnos.appendChild(el('p', 'nada', 'todavía no hay conversación'));
    }
    turnos.dataset.leido = '1';
    if (seguir) turnos.scrollTop = turnos.scrollHeight;
  }
  var leyendo = false, pronto = 0;
  function leer() {
    if (leyendo) return;
    leyendo = true;
    var url = '/api/hilos/leer?hilo=' + encodeURIComponent(hilo) + '&ultimos=8' + (maquina ? '&maquina=' + encodeURIComponent(maquina) : '');
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json().then(function (d) { return r.ok ? d : { error: d.detail || ('la API respondió ' + r.status) }; }); })
      .then(pintar)
      .catch(function () { /* sin conexión: se reintenta en la vuelta */ })
      .then(function () { leyendo = false; });
  }
  function vuelta() { leer(); setTimeout(vuelta, Date.now() < pronto ? 1500 : (document.hidden ? 20000 : 4000)); }
  vuelta();
  document.addEventListener('visibilitychange', function () { if (!document.hidden) leer(); });

  // escribir: una vista de la terminal del hilo, abierta la primera vez que hace falta
  var ws = null, cola = [];
  // la dirección del WebSocket, desde la de la página (en un iframe srcdoc, la de quien lo armó)
  function enchufe(ruta) { var u = new URL(ruta, document.baseURI); u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'; return u.href; }
  function canal() {
    if (ws && ws.readyState <= 1) return ws;
    ws = new WebSocket(enchufe('/pty?hilo=' + encodeURIComponent(hilo) + '&cols=100&rows=30'));
    ws.onopen = function () { cola.splice(0).forEach(function (d) { ws.send(JSON.stringify({ d: d })); }); };
    ws.onmessage = function () { /* lo que dibuja la terminal no se muestra aquí */ };
    ws.onclose = function () { ws = null; };
    return ws;
  }
  function teclear(d) { var c = canal(); if (c.readyState === 1) c.send(JSON.stringify({ d: d })); else cola.push(d); pronto = Date.now() + 20000; }
  // ⏎ envía; ⇧⏎ es una línea nueva (y mientras se compone una letra con acento, ⏎ es de la composición)
  texto.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); document.getElementById('escribir').requestSubmit(); }
  });
  document.getElementById('escribir').addEventListener('submit', function (e) {
    e.preventDefault();
    var t = texto.value.replace(/\\s+$/, '');
    if (!t) return;
    if (porMensaje) {
      // por el bus, como la persona; le llega al hilo al terminar su turno (o al tiro si espera)
      var envio = fetch('/api/mensajes', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ para: hilo, texto: t, tipo: 'persona', de: 'el panel' }) })
        .then(function (r) { return r.json().then(function (d) { return r.ok ? { ok: true } : { ok: false, error: d.detail }; }); });
      envio
        .then(function (r) {
          dijo.textContent = r.ok ? 'enviado: le llega al terminar su turno, o al tiro si te espera' : (r.error || 'no llegó');
          if (r.ok) { texto.value = ''; pronto = Date.now() + 30000; setTimeout(leer, 3000); }
        })
        .catch(function () { dijo.textContent = 'sin conexión con telar'; });
      return;
    }
    // como un pegado (para que un salto de línea no envíe antes de tiempo), y después ⏎
    teclear('\\u001b[200~' + t + '\\u001b[201~');
    setTimeout(function () { teclear('\\r'); }, 120);
    texto.value = '';
    setTimeout(leer, 1200);
  });
  [].forEach.call(document.querySelectorAll('#teclas button'), function (b) {
    b.addEventListener('click', function () { teclear(JSON.parse('"' + b.getAttribute('data-t') + '"')); setTimeout(leer, 800); });
  });
})();
</script></body></html>`;
}

/** La terminal de un hilo: xterm.js (servido por telar.api_web en `/estatico/xterm`) conectado por
 *  WebSocket a `telar mirar` en un PTY de la máquina (`/pty`, telar.terminal); el de un hilo de otra máquina,
 *  reenviado por la página de aquí a la de allá. */
export function paginaTerminal(nonce: string, rutas: { hilo?: string; maquina?: string } = {}): string {
    const xterm = '/estatico/xterm';
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'nonce-${nonce}'; connect-src 'self';">
<link rel="stylesheet" href="${xterm}/xterm.css">
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { html, body { height: 100%; } #t { position: absolute; inset: 0; padding: var(--e-1) 0 0 var(--h-1); } }</style>
<script src="${xterm}/xterm.js"></script><script src="${xterm}/addon-fit.js"></script>
</head><body><div id="t"></div>
<script nonce="${nonce}">
(function () {
  // los colores, de los tokens (media/css/tokens.css): los mismos del resto de la página
  var css = getComputedStyle(document.documentElement);
  function t(nombre) { return css.getPropertyValue('--' + nombre).trim(); }
  var term = new Terminal({ fontFamily: t('letra') || 'Menlo, monospace', fontSize: parseInt(t('tam'), 10) || 13, cursorBlink: true, allowProposedApi: false,
    theme: { background: t('bg'), foreground: t('fg'), cursor: t('cursor'), selectionBackground: t('negro'),
      black: t('negro'), red: t('rojo'), green: t('verde'), yellow: t('amarillo'), blue: t('azul'), magenta: t('magenta'), cyan: t('cian'), white: t('blanco'),
      brightBlack: t('dim'), brightRed: t('rojo'), brightGreen: t('verde'), brightYellow: t('amarillo'), brightBlue: t('azul'), brightMagenta: t('magenta'), brightCyan: t('cian'), brightWhite: t('blanco-claro') } });
  var fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  var caja = document.getElementById('t'); term.open(caja); fit.fit();
  var hilo = ${JSON.stringify(rutas.hilo ?? '').replace(/</g, '\\u003c')} || new URLSearchParams(location.search).get('hilo') || '';
  // un hilo de otra máquina: la página de aquí la reenvía a la de allá (telar.terminal.reenviar)
  var maquina = ${JSON.stringify(rutas.maquina ?? '').replace(/</g, '\\u003c')};
  // la dirección del WebSocket, desde la de la página (en un iframe srcdoc, la de quien lo armó), con el
  // tamaño de ahora: cada conexión abre una vista nueva del hilo
  function direccion() {
    var u = new URL('/pty?hilo=' + encodeURIComponent(hilo) + '&cols=' + term.cols + '&rows=' + term.rows
      + (maquina ? '&maquina=' + encodeURIComponent(maquina) : ''), document.baseURI);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.href;
  }
  // si la conexión se corta (el laptop durmió, cambió la red, se reinició telar), se reconecta sola: al
  // segundo, y después cada vez más espaciado, hasta cada 15 s; al volver a la pestaña o a la red, al tiro
  var ws = null, esperas = [1000, 2000, 5000, 10000, 15000], intento = 0, pendiente = 0, conectada = false;
  function conectar() {
    clearTimeout(pendiente); pendiente = 0;
    if (ws && ws.readyState <= 1) return;
    ws = new WebSocket(direccion());
    ws.onopen = function () {
      // la vista nueva redibuja la pantalla entera: lo de antes se borra para que no quede mezclado
      if (intento) term.reset();
      intento = 0; conectada = true;
    };
    ws.onmessage = function (e) { term.write(e.data); };
    ws.onclose = function () {
      if (conectada) term.write('\\r\\n\\x1b[2m[se cortó la conexión con la terminal: reconectando…]\\x1b[0m');
      conectada = false;
      pendiente = setTimeout(conectar, esperas[Math.min(intento++, esperas.length - 1)]);
    };
  }
  conectar();
  document.addEventListener('visibilitychange', function () { if (!document.hidden && !conectada) { intento = 0; conectar(); } });
  window.addEventListener('online', function () { if (!conectada) { intento = 0; conectar(); } });
  term.onData(function (d) { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ d: d })); });
  new ResizeObserver(function () {
    fit.fit();
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ r: [term.cols, term.rows] }));
  }).observe(caja);
  window.addEventListener('focus', function () { term.focus(); });
  term.focus();
})();
</script></body></html>`;
}
