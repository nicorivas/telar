// Lo que la página del dashboard necesita en un navegador y que en VS Code le da el webview:
// `acquireVsCodeApi` (mandar mensajes y guardar su estado), los mensajes que llegan, y la
// interfaz que en VS Code es nativa —avisos, un campo para escribir, un menú para elegir—.
// El script del dashboard (dia.ts) no cambia: habla con `vscode` como siempre, y aquí ese
// `vscode` es un WebSocket con el servidor (servidor.ts).

import { estilo, estiloBase } from '../estilo';

export const CSS_WEB = estilo('web');

/** El script que va antes del del dashboard: define `acquireVsCodeApi` y la interfaz. */
// El canal: con un servidor en Node, un WebSocket; en el navegador (src/navegador), la página que contiene
// al dashboard, por postMessage. El resto del script (la interfaz) es el mismo para los dos.
const CANAL_WS = String.raw`
  // cada página (la barra, el dashboard) tiene su canal: el servidor sabe a quién mandarle qué
  var url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws?v=' + (location.pathname === '/barra' ? 'barra' : 'dash');
  var ws, abierto = false, cola = [];
  function conectar() {
    ws = new WebSocket(url);
    ws.onopen = function () { abierto = true; cola.splice(0).forEach(function (m) { ws.send(m); }); medir(); };
    ws.onclose = function () { abierto = false; avisar('sin conexión con telar; reintentando…', 'aviso'); setTimeout(conectar, 2000); };
    ws.onmessage = function (e) {
      var m; try { m = JSON.parse(e.data); } catch (x) { return; }
      llega(m);
    };
  }
  function enviar(s) { ws.send(s); }`;

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

/** El script que va antes del del dashboard en el panel en Node: el canal es un WebSocket. */
export const SCRIPT_WEB = script(CANAL_WS);
/** El mismo, para el dashboard que corre en el navegador (src/navegador): le habla a la página que lo
 *  contiene, por postMessage. */
export const SCRIPT_NAVEGADOR = script(CANAL_PADRE);

/** La página que junta las dos: la barra de hilos a la izquierda y, a la derecha, lo que la barra
 *  elige: el dashboard o la terminal de un hilo. Cada uno en su marco, con su propio script y su propio
 *  canal, como en VS Code. La barra lo pide con un mensaje a esta página (`__mostrar`); las
 *  terminales abiertas siguen vivas mientras se mira otra cosa (hasta TOPE, las más viejas se cierran).
 *
 *  En una pantalla angosta (un celular, hasta 700 px) se ve una cosa a la vez: primero la lista de
 *  hilos; un toque abre el dashboard o un hilo a pantalla completa, con «◀» arriba (y el botón atrás
 *  del teléfono) para volver. Ahí un hilo se lee como conversación (`/conversacion`), no como
 *  terminal: en un teclado de celular, una terminal de 40 columnas no se puede usar. «terminal»
 *  arriba la abre igual. */
export function paginaCasa(nonce: string): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1e1e2e">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src 'self'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; manifest-src 'self'; img-src 'self'; worker-src 'self';">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>telar</title>
<style>
  html, body { margin: 0; height: 100%; background: #1e1e2e; }
  body { display: grid; grid-template-columns: minmax(240px, 22vw) 1fr; height: 100dvh; }
  iframe { border: 0; width: 100%; height: 100%; display: block; }
  #barra { border-right: 1px solid rgba(205,214,244,.12); grid-row: 1 / span 2; }
  #marcos { position: relative; min-width: 0; grid-row: 1 / span 2; } #marcos iframe { position: absolute; inset: 0; } #marcos iframe[hidden] { display: none; }
  #tira { display: none; align-items: center; gap: 2ch; padding: .45em 1ch; border-bottom: 1px solid rgba(205,214,244,.12);
    font: 15px Menlo, "JetBrains Mono", monospace; color: #cdd6f4; }
  #tira button { font: inherit; color: #89b4fa; background: none; border: 0; padding: .2em .4ch; cursor: pointer; }
  #tira #titulo { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  body.angosto { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  body.angosto #barra { border-right: 0; }
  body.angosto.en-lista #tira, body.angosto.en-lista #marcos, body.angosto.en-detalle #barra { display: none; }
  body.angosto.en-detalle #tira { display: flex; }
  body.angosto.en-detalle #marcos { grid-row: 2; }
</style></head>
<body><div id="tira"><button id="volver" title="volver a los hilos">◀ hilos</button><span id="titulo"></span><button id="modo"></button></div>
<iframe id="barra" src="/barra" title="hilos"></iframe>
<div id="marcos"><iframe data-p="dashboard" src="/dashboard" title="dashboard"></iframe></div>
<script nonce="${nonce}">
(function () {
  var marcos = document.getElementById('marcos'), TOPE = 8, usadas = [], actual = 'dashboard', modo = {};
  var angosto = window.matchMedia('(max-width: 700px)');
  var titulo = document.getElementById('titulo'), botonModo = document.getElementById('modo');
  function marco(p) { return marcos.querySelector('iframe[data-p="' + CSS.escape(p) + '"]'); }
  // un hilo en pantalla angosta se lee como conversación (salvo que se pida la terminal); en ancha, terminal
  // claves: «dashboard», el nombre de un hilo de aquí, «doc:<hilo>» (su carpeta) y «rem:<máquina>:<hilo>» (de otra máquina)
  function forma(clave) { return clave === 'dashboard' || clave.indexOf('doc:') === 0 || clave.indexOf('rem:') === 0 ? '' : (angosto.matches ? (modo[clave] || 'conv') : 'term'); }
  function fuente(clave) {
    if (clave.indexOf('doc:') === 0) return '/documento?hilo=' + encodeURIComponent(clave.slice(4));
    if (clave.indexOf('rem:') === 0) { var r = clave.slice(4), i = r.indexOf(':'); return '/conversacion?maquina=' + encodeURIComponent(r.slice(0, i)) + '&hilo=' + encodeURIComponent(r.slice(i + 1)); }
    return (forma(clave) === 'conv' ? '/conversacion?hilo=' : '/terminal?hilo=') + encodeURIComponent(clave);
  }
  function llave(clave) { var f = forma(clave); return f ? f + ':' + clave : clave; }
  function mostrar(clave, desdeHistoria) {
    actual = clave;
    var p = llave(clave), f = marco(p);
    if (!f) {
      f = document.createElement('iframe');
      f.setAttribute('data-p', p); f.title = clave;
      f.src = fuente(clave);
      marcos.appendChild(f);
    }
    [].forEach.call(marcos.querySelectorAll('iframe'), function (x) { x.hidden = x !== f; });
    // las vistas de hilos que hace rato no se miran se cierran (cada terminal es una vista de tmux abierta)
    if (clave !== 'dashboard') {
      usadas = usadas.filter(function (u) { return u !== p; }).concat([p]);
      while (usadas.length > TOPE) { var vieja = marco(usadas.shift()); if (vieja) vieja.remove(); }
    }
    var nombre = clave.indexOf('doc:') === 0 ? clave.slice(4) + ' · carpeta'
      : clave.indexOf('rem:') === 0 ? (function (r) { var i = r.indexOf(':'); return r.slice(i + 1) + ' · en ' + r.slice(0, i); })(clave.slice(4)) : clave;
    document.title = clave === 'dashboard' ? 'telar' : nombre + ' · telar';
    titulo.textContent = nombre;
    botonModo.hidden = !forma(clave);
    botonModo.textContent = forma(clave) === 'conv' ? 'terminal' : 'conversación';
    if (angosto.matches) {
      document.body.classList.remove('en-lista'); document.body.classList.add('en-detalle');
      if (!desdeHistoria) history.pushState({ d: clave }, '');
    }
    if (f.contentWindow && !angosto.matches) f.contentWindow.focus();
  }
  function lista() { document.body.classList.remove('en-detalle'); document.body.classList.add('en-lista'); }
  function ajustar() {
    document.body.classList.toggle('angosto', angosto.matches);
    if (angosto.matches) lista();
    else { document.body.classList.remove('en-lista', 'en-detalle'); mostrar(actual, true); }
  }
  document.getElementById('volver').addEventListener('click', function () { if (history.state && history.state.d) history.back(); else lista(); });
  botonModo.addEventListener('click', function () {
    modo[actual] = forma(actual) === 'conv' ? 'term' : 'conv';
    mostrar(actual, true);
  });
  window.addEventListener('popstate', function (e) { if (e.state && e.state.d) mostrar(String(e.state.d), true); else lista(); });
  angosto.addEventListener('change', ajustar);
  window.addEventListener('message', function (e) {
    if (e.origin !== location.origin || !e.data || !e.data.__mostrar) return;
    mostrar(String(e.data.__mostrar));
  });
  ajustar();
  // instalable como app (y destino de «compartir» en el teléfono): el service worker no guarda nada
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(function () {});
})();
</script></body></html>`;
}

/** La carpeta de un hilo y uno de sus archivos, para `paginaDocumento` (lo arma servidor.ts). */
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
export function paginaCompartir(nonce: string): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src 'self';">
<title>compartir · telar</title>
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { ${estilo('compartir')} }</style>
</head><body>
<header><a href="/">◀ telar</a><b>compartir</b></header>
<main>
  <section id="que"></section>
  <textarea id="nota" rows="3" placeholder="una nota, si quieres (va con lo compartido)"></textarea>
  <input id="filtro" placeholder="filtrar destinos" autocomplete="off">
  <div id="destinos"><p class="dim">leyendo destinos…</p></div>
  <p id="dicho" class="dim"></p>
</main>
<script nonce="${nonce}">
(function () {
  var q = new URLSearchParams(location.search);
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
  fetch('/api/compartir/destinos', { credentials: 'same-origin' }).then(function (r) { return r.json(); })
    .then(function (d) { lista = d.destinos || []; pintar(); })
    .catch(function () { document.getElementById('destinos').textContent = 'no pude leer los destinos'; });
})();
</script></body></html>`;
}

/** Un hilo leído como conversación, para el celular: los últimos turnos (`telar hilo leer`, releídos
 *  cada pocos segundos), una caja para escribirle y las teclas para contestarle una pregunta (⏎, ⎋,
 *  1-3, ↑↓). Lo escrito va por el mismo canal que la terminal (`/pty`, una vista de `telar mirar`):
 *  es teclear en el hilo, con la misma llave. */
/** De dónde lee y a dónde escribe la página de una conversación. En el panel en Node, sus rutas (`/api/leer`,
 *  y la terminal o `/api/remoto/enviar`); en el navegador (src/navegador), la API de telar: `/api/hilos/leer`,
 *  la terminal (`/pty` de telar.api_web) para un hilo de aquí y `/api/mensajes` para uno de otra máquina. */
export interface RutasConversacion {
    /** el hilo y su máquina, si la página no los lee de su dirección (un iframe con srcdoc no tiene) */
    hilo?: string; maquina?: string;
    navegador?: boolean;
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
  <form id="escribir"><textarea id="texto" rows="2" placeholder="escríbele al hilo"></textarea><button type="submit">enviar</button></form>
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
  if (porMensaje) { document.getElementById('teclas').hidden = true; texto.placeholder = maquina ? 'escríbele al hilo (en ' + maquina + ', por el bus)' : 'escríbele al hilo (le llega como mensaje)'; }
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
    var url = R.navegador ? '/api/hilos/leer?hilo=' + encodeURIComponent(hilo) + '&ultimos=8' + (maquina ? '&maquina=' + encodeURIComponent(maquina) : '')
      : '/api/leer?hilo=' + encodeURIComponent(hilo) + '&n=8' + (maquina ? '&maquina=' + encodeURIComponent(maquina) : '');
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
  document.getElementById('escribir').addEventListener('submit', function (e) {
    e.preventDefault();
    var t = texto.value.replace(/\\s+$/, '');
    if (!t) return;
    if (porMensaje) {
      // por el bus, como la persona; le llega al hilo al terminar su turno (o al tiro si espera)
      var envio = R.navegador
        ? fetch('/api/mensajes', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ para: hilo, texto: t, tipo: 'persona', de: 'el panel' }) })
            .then(function (r) { return r.json().then(function (d) { return r.ok ? { ok: true } : { ok: false, error: d.detail }; }); })
        : fetch('/api/remoto/enviar', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ hilo: hilo, texto: t }) })
            .then(function (r) { return r.json(); });
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

/** La terminal de un hilo: xterm.js conectado por WebSocket a `telar mirar` en un PTY del servidor. En el
 *  panel en Node, el hilo viene en la dirección y xterm de `/xterm`; en el navegador (un iframe srcdoc), los
 *  dos por parámetro, con xterm en `/estatico/xterm` (lo sirve telar.api_web). */
export function paginaTerminal(nonce: string, rutas: { hilo?: string; xterm?: string } = {}): string {
    const xterm = rutas.xterm ?? '/xterm';
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'nonce-${nonce}'; connect-src 'self';">
<link rel="stylesheet" href="${xterm}/xterm.css">
<style>html, body { margin: 0; height: 100%; background: #1e1e2e; } #t { position: absolute; inset: 0; padding: 6px 0 0 8px; }</style>
<script src="${xterm}/xterm.js"></script><script src="${xterm}/addon-fit.js"></script>
</head><body><div id="t"></div>
<script nonce="${nonce}">
(function () {
  var term = new Terminal({ fontFamily: 'Menlo, "JetBrains Mono", monospace', fontSize: 13, cursorBlink: true, allowProposedApi: false,
    theme: { background: '#1e1e2e', foreground: '#cdd6f4', cursor: '#f5e0dc', selectionBackground: '#45475a',
      black: '#45475a', red: '#f38ba8', green: '#a6e3a1', yellow: '#f9e2af', blue: '#89b4fa', magenta: '#f5c2e7', cyan: '#94e2d5', white: '#bac2de',
      brightBlack: '#585b70', brightRed: '#f38ba8', brightGreen: '#a6e3a1', brightYellow: '#f9e2af', brightBlue: '#89b4fa', brightMagenta: '#f5c2e7', brightCyan: '#94e2d5', brightWhite: '#a6adc8' } });
  var fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  var caja = document.getElementById('t'); term.open(caja); fit.fit();
  var hilo = ${JSON.stringify(rutas.hilo ?? '').replace(/</g, '\\u003c')} || new URLSearchParams(location.search).get('hilo') || '';
  // la dirección del WebSocket, desde la de la página (en un iframe srcdoc, la de quien lo armó)
  var u = new URL('/pty?hilo=' + encodeURIComponent(hilo) + '&cols=' + term.cols + '&rows=' + term.rows, document.baseURI);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  var ws = new WebSocket(u.href);
  ws.onmessage = function (e) { term.write(e.data); };
  ws.onclose = function () { term.write('\\r\\n\\x1b[2m[la terminal se cerró: recarga para volver a mirar]\\x1b[0m\\r\\n'); };
  term.onData(function (d) { if (ws.readyState === 1) ws.send(JSON.stringify({ d: d })); });
  new ResizeObserver(function () {
    fit.fit();
    if (ws.readyState === 1) ws.send(JSON.stringify({ r: [term.cols, term.rows] }));
  }).observe(caja);
  window.addEventListener('focus', function () { term.focus(); });
  term.focus();
})();
</script></body></html>`;
}
