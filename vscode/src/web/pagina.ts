// Lo que la página del dashboard necesita en un navegador y que en VS Code le da el webview:
// `acquireVsCodeApi` (mandar mensajes y guardar su estado), los mensajes que llegan, y la
// interfaz que en VS Code es nativa —avisos, un campo para escribir, un menú para elegir—.
// El script del dashboard (dia.ts) no cambia: habla con `vscode` como siempre, y aquí ese
// `vscode` es un WebSocket con el servidor (servidor.ts).

import { estilo } from '../estilo';

export const CSS_WEB = estilo('web');

/** El script que va antes del del dashboard: define `acquireVsCodeApi` y la interfaz. */
export const SCRIPT_WEB = String.raw`
(function () {
  // cada página (la barra, el dashboard) tiene su canal: el servidor sabe a quién mandarle qué
  var url = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws?v=' + (location.pathname === '/barra' ? 'barra' : 'dash');
  var ws, abierto = false, cola = [];
  function conectar() {
    ws = new WebSocket(url);
    ws.onopen = function () { abierto = true; cola.splice(0).forEach(function (m) { ws.send(m); }); };
    ws.onclose = function () { abierto = false; avisar('sin conexión con telar; reintentando…', 'aviso'); setTimeout(conectar, 2000); };
    ws.onmessage = function (e) {
      var m; try { m = JSON.parse(e.data); } catch (x) { return; }
      if (m.__recargar) { location.reload(); return; }
      if (m.__aviso) { avisar(m.__aviso, m.nivel, m.ms); return; }
      if (m.__abrir) { window.open(m.__abrir, '_blank', 'noopener'); return; }
      if (m.__copiar) { try { navigator.clipboard.writeText(m.__copiar); } catch (x) {} return; }
      if (m.__mostrar) { try { parent.postMessage({ __mostrar: m.__mostrar }, location.origin); } catch (x) {} return; }
      if (m.__ui) { preguntar(m); return; }
      window.dispatchEvent(new MessageEvent('message', { data: m }));
    };
  }
  function mandar(m) { var s = JSON.stringify(m); if (abierto) ws.send(s); else cola.push(s); }
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

/** La página que junta las dos: la barra de hilos a la izquierda y, a la derecha, lo que la barra
 *  elige: el dashboard o la terminal de un hilo. Cada uno en su marco, con su propio script y su propio
 *  canal, como en VS Code. La barra lo pide con un mensaje a esta página (`__mostrar`); las
 *  terminales abiertas siguen vivas mientras se mira otra cosa (hasta TOPE, las más viejas se cierran). */
export function paginaCasa(nonce: string): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src 'self'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<title>telar</title>
<style>
  html, body { margin: 0; height: 100%; background: #1e1e2e; }
  body { display: grid; grid-template-columns: minmax(240px, 22vw) 1fr; }
  iframe { border: 0; width: 100%; height: 100%; display: block; }
  #barra { border-right: 1px solid rgba(205,214,244,.12); }
  #marcos { position: relative; min-width: 0; } #marcos iframe { position: absolute; inset: 0; } #marcos iframe[hidden] { display: none; }
  @media (max-width: 700px) { body { grid-template-columns: 1fr; grid-template-rows: 35vh 1fr; } }
</style></head>
<body><iframe id="barra" src="/barra" title="hilos"></iframe>
<div id="marcos"><iframe data-p="dashboard" src="/dashboard" title="dashboard"></iframe></div>
<script nonce="${nonce}">
(function () {
  var marcos = document.getElementById('marcos'), TOPE = 8, usadas = [];
  function marco(clave) { return marcos.querySelector('iframe[data-p="' + CSS.escape(clave) + '"]'); }
  function mostrar(clave) {
    var f = marco(clave);
    if (!f) {
      f = document.createElement('iframe');
      f.setAttribute('data-p', clave); f.title = clave; f.src = '/terminal?hilo=' + encodeURIComponent(clave);
      marcos.appendChild(f);
    }
    [].forEach.call(marcos.querySelectorAll('iframe'), function (x) { x.hidden = x !== f; });
    // las terminales que hace rato no se miran se cierran (cada una es una vista de tmux abierta)
    if (clave !== 'dashboard') {
      usadas = usadas.filter(function (u) { return u !== clave; }).concat([clave]);
      while (usadas.length > TOPE) { var vieja = marco(usadas.shift()); if (vieja) vieja.remove(); }
    }
    document.title = clave === 'dashboard' ? 'telar' : clave + ' · telar';
    if (f.contentWindow) f.contentWindow.focus();
  }
  window.addEventListener('message', function (e) {
    if (e.origin !== location.origin || !e.data || !e.data.__mostrar) return;
    mostrar(String(e.data.__mostrar));
  });
})();
</script></body></html>`;
}

/** La terminal de un hilo: xterm.js conectado por WebSocket a `telar mirar` en un PTY del servidor. */
export function paginaTerminal(nonce: string): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'nonce-${nonce}'; connect-src 'self';">
<link rel="stylesheet" href="/xterm/xterm.css">
<style>html, body { margin: 0; height: 100%; background: #1e1e2e; } #t { position: absolute; inset: 0; padding: 6px 0 0 8px; }</style>
<script src="/xterm/xterm.js"></script><script src="/xterm/addon-fit.js"></script>
</head><body><div id="t"></div>
<script nonce="${nonce}">
(function () {
  var term = new Terminal({ fontFamily: 'Menlo, "JetBrains Mono", monospace', fontSize: 13, cursorBlink: true, allowProposedApi: false,
    theme: { background: '#1e1e2e', foreground: '#cdd6f4', cursor: '#f5e0dc', selectionBackground: '#45475a',
      black: '#45475a', red: '#f38ba8', green: '#a6e3a1', yellow: '#f9e2af', blue: '#89b4fa', magenta: '#f5c2e7', cyan: '#94e2d5', white: '#bac2de',
      brightBlack: '#585b70', brightRed: '#f38ba8', brightGreen: '#a6e3a1', brightYellow: '#f9e2af', brightBlue: '#89b4fa', brightMagenta: '#f5c2e7', brightCyan: '#94e2d5', brightWhite: '#a6adc8' } });
  var fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  var caja = document.getElementById('t'); term.open(caja); fit.fit();
  var hilo = new URLSearchParams(location.search).get('hilo') || '';
  var ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/pty?hilo=' + encodeURIComponent(hilo)
    + '&cols=' + term.cols + '&rows=' + term.rows);
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
