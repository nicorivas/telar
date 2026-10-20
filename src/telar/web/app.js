var __dirname = "/", __filename = "/app.js"; var process = globalThis.process || { env: {}, platform: "navegador", cwd: function () { return "/"; } };
"use strict";(()=>{var dn=Object.defineProperty;var Yt=(e,a)=>{for(var t in a)dn(e,t,{get:a[t],enumerable:!0})};var Ie=e=>Object.assign(new Error(`en el navegador no hay archivos: ${String(e)}`),{code:"ENOENT"}),la=()=>!1;function ca(e){throw Ie(e)}function Kt(e){throw Ie(e)}function Qt(e){throw Ie(e)}function er(e){throw Ie(e)}function ar(e){throw Ie(e)}function ne(e){let a=e.startsWith("/"),t=[];for(let r of e.split("/"))!r||r==="."||(r===".."?t.length&&t[t.length-1]!==".."?t.pop():a||t.push(".."):t.push(r));return(a?"/":"")+t.join("/")||(a?"/":".")}var z=(...e)=>ne(e.filter(Boolean).join("/")),Va=(...e)=>ne(e.reduce((a,t)=>t.startsWith("/")?t:`${a}/${t}`,"")),Be=e=>{let a=ne(e),t=a.lastIndexOf("/");return t<=0?a.startsWith("/")?"/":".":a.slice(0,t)},Ya=(e,a="")=>{let t=ne(e).split("/").pop()??"";return a&&t.endsWith(a)?t.slice(0,-a.length):t};var da=e=>e.startsWith("/");function Ka(e,a){let t=ne(e).split("/").filter(Boolean),r=ne(a).split("/").filter(Boolean),o=0;for(;o<t.length&&o<r.length&&t[o]===r[o];)o++;return[...t.slice(o).map(()=>".."),...r.slice(o)].join("/")}var Le={trabajando:"\u25CF",espera:"\u25CB",termino:"\u2713"},_e={0:"\xB7",1:"\u25CF",2:"\u25D0",3:"\u25CB"},pa={trabajando:"trabajando",espera:"te espera",termino:"termin\xF3"};function d(e){return e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}function tr(e){let a=Math.floor((e??0)/60);return a<=0?"":a>=60?`${Math.floor(a/60)}h${String(a%60).padStart(2,"0")}`:`${a}m`}function ha(e){if(!e)return"";let a=Date.now()-Date.parse(e);if(Number.isNaN(a))return"";let t=Math.round(a/6e4);return t<60?`${t} min`:t<1440?`${Math.round(t/60)} h`:`${Math.round(t/1440)} d`}function se(e){return ha(e).replace(/ min$/,"m").replace(/ h$/,"h").replace(/ d$/,"d")}var ve=e=>e.replace(/\*\*/g,"").replace(/`/g,""),M=e=>e.normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase(),un=()=>({familia:"Menlo, Consolas, monospace",tam:13,peso:"normal",altoLinea:1});function De(){let e=un(),a=t=>t.replace(/[<>{};]/g,"");return`:root { --letra: ${a(e.familia)}; --tam: ${e.tam}px; --peso: ${a(String(e.peso))}; --alto: ${((e.altoLinea||1)*1.3).toFixed(2)}; }
@layer base { ${B("tokens")}
${B("base")} }`}var et=new Map,Qa="";function rr(e){for(let[a,t]of Object.entries(e))et.set(a,t)}function B(e){let a=et.get(e);if(a!==void 0)return a;if(!Qa){let r=__dirname;for(;!la(z(r,"media","css"))&&Be(r)!==r;)r=Be(r);Qa=z(r,"media","css")}let t="";try{t=ca(z(Qa,`${e}.css`),"utf8")}catch{}return et.set(e,t),t}function Ne(){return Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2)}function fa(e,a,t,r,o=Ne(),i=[]){return`<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${e.cspSource} https: data:; frame-src ${[e.cspSource,...i].join(" ")}; style-src 'unsafe-inline'; script-src 'nonce-${o}';${e.cspConectar?` connect-src ${e.cspConectar};`:""}">
<style>@layer base, vistas;
${De()}
@layer vistas { ${a} }</style></head>
<body data-vscode-context='{"preventDefaultContextMenuItems": true}'>${t}
<script nonce="${o}">const vscode = acquireVsCodeApi();
${r}<\/script></body></html>`}var or=`/* \xABahora\xBB: el bloque del momento (vistas/ahora.ts). */

.ahora-nav { display: flex; gap: 2ch; align-items: baseline; margin: .3lh 0 .6lh; }
.ahora-nav a { color: var(--dim); }
.ahora-cuando { margin-left: auto; } .ahora-nav a.ahora-cuando.simulado { color: var(--amarillo); }
.ahora-elegir { border: 1px solid var(--linea); padding: .3lh 1ch .6lh; margin: 0 0 .8lh; max-width: 70ch; }
.ahora-elegir .cal { margin-top: .5lh; } .ahora-nav a:hover { color: var(--fg); text-decoration: none; background: var(--hover); }
.ahora-bloque { margin-bottom: .8lh; } .ahora-bloque h3 { margin: .1lh 0; }
.ahora-bloque .clase { font-size: var(--t-chica); text-transform: uppercase; color: var(--dim); }
.ahora-bloque .c-estrategico { color: var(--amarillo); } .ahora-bloque .c-reunion { color: var(--azul); }
.ahora-bloque .c-comercial { color: var(--verde); }
.ahora-foco { border-left: 2px solid var(--amarillo); padding: .2lh 1ch; margin: .5lh 0; }
.ahora-foco .paso { font-size: 1.05em; margin: .2lh 0; } .ahora-foco.corto { border-left-color: var(--linea); }
.ahora-ficha { border-left: 2px solid var(--azul); padding: .2lh 1ch; margin: .5lh 0; }
.ahora-ficha ul { margin: 0; padding-left: 3ch; }
#dia h4 { margin: 1lh 0 .3lh; font-size: 1em; text-transform: uppercase; color: var(--dim); font-weight: normal; }
.ahora-doc { max-height: 22lh; overflow-y: auto; }
.ahora-estado { border-top: none; }
`;var ir=`/* La base de todas las vistas: la p\xE1gina, la letra (--letra, --tam, --peso y --alto los pone
   estilo.ts con la de la terminal) y los enlaces. */

html,
body {
  background: var(--bg);
}

body {
  margin: 0;
  color: var(--fg);
  font-family: var(--letra), monospace;
  font-size: var(--tam);
  font-weight: var(--peso);
  line-height: var(--alto);
  -webkit-font-smoothing: antialiased;
}

a {
  color: var(--azul);
  text-decoration: none;
  cursor: pointer;

  &:hover { text-decoration: underline; }
}

.dim { color: var(--dim); }

.aviso {
  padding: var(--e-3) var(--h-2);
  color: var(--dim);

  & code { color: var(--verde); }
}

/* .fila y .tarea son flex: sin esto, hidden no oculta */
[hidden] { display: none !important; }
`;var nr=`/* Lo que el tel\xE9fono le comparte al panel (web/pagina.ts, paginaCompartir): qu\xE9 lleg\xF3, una nota, y a
   d\xF3nde llevarlo. */

header {
  display: flex;
  gap: var(--h-2);
  padding: var(--e-2) var(--h-1);
  border-bottom: var(--borde);
}

main {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-2) var(--h-1) calc(var(--e-3) + env(safe-area-inset-bottom));
}

#que {
  overflow-wrap: anywhere;

  & .titulo { font-weight: bold; }
  & .url { color: var(--azul); }
  & .texto { white-space: pre-wrap; }
}

textarea,
input {
  box-sizing: border-box;
  width: 100%;
  padding: .3em .5ch;
  border: var(--borde);
  outline: none;
  background: transparent;
  color: var(--fg);
  font: inherit;
  font-size: max(16px, 1em); /* bajo 16 px, el iPhone agranda la p\xE1gina al escribir */

  &:focus { border-color: var(--azul); }
}

.grupo {
  margin-top: var(--e-2);
  color: var(--dim);
  font-size: var(--t-menor);
}

.destino {
  display: block;
  width: 100%;
  padding: .45em 1ch;
  border: 0;
  border-bottom: var(--borde);
  background: transparent;
  color: var(--fg);
  font: inherit;
  text-align: left;
  cursor: pointer;

  &:active,
  &:hover { background: var(--sel); }
  &:disabled { color: var(--dim); }
}

.dim { color: var(--dim); }
.bien { color: var(--verde); }
.mal { color: var(--rojo); }
`;var sr=`/* Un hilo le\xEDdo como conversaci\xF3n, en el celular (web/pagina.ts, paginaConversacion): los turnos
   arriba, que se desplazan, y abajo las teclas y la caja para escribirle. */

html,
body {
  height: 100%;
}

body {
  display: flex;
  flex-direction: column;
  height: 100dvh;
}

#turnos {
  flex: 1;
  overflow-y: auto;
  padding: var(--e-2) var(--h-1);
  overscroll-behavior: contain;
}

.nada {
  color: var(--dim);
  font-size: var(--t-menor);
}

.turno {
  padding: var(--e-2) 0;
  border-bottom: var(--borde);
}

.msj {
  margin: var(--e-1) 0;

  & .quien {
    color: var(--dim);
    font-size: var(--t-chica);
  }

  & .cuerpo {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  &.usuario .quien,
  &.usuario .cuerpo { color: var(--azul); }

  &.herramienta {
    margin: 0;
    color: var(--dim);
    font-size: var(--t-chica);

    & .cuerpo::before { content: "\xB7 "; }
  }
}

.panel {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
}

footer {
  padding: var(--e-1) var(--h-1) calc(var(--e-1) + env(safe-area-inset-bottom));
  border-top: var(--borde);
}

#teclas {
  display: flex;
  gap: var(--h-1);
  margin-bottom: var(--e-1);
}

button {
  padding: .3em 1ch;
  border: var(--borde);
  background: transparent;
  color: var(--fg);
  font: inherit;
  cursor: pointer;

  &:active { background: var(--sel); }
}

#escribir {
  display: flex;
  gap: var(--h-1);
  align-items: flex-end;

  /* como el prompt de una terminal: la letra de todo lo dem\xE1s, sin caja; una l\xEDnea a la izquierda que se
     pone azul mientras se escribe. \u23CE env\xEDa, \u21E7\u23CE es una l\xEDnea nueva */
  & textarea {
    flex: 1;
    min-width: 0;
    box-sizing: border-box;
    padding: 0 var(--h-1);
    border: 0;
    border-left: 2px solid var(--linea);
    outline: none;
    background: transparent;
    color: var(--fg);
    font: inherit;
    resize: none;

    &:focus { border-left-color: var(--azul); }
    &::placeholder { color: var(--dim); }

    /* en una pantalla t\xE1ctil, bajo 16 px el iPhone agranda la p\xE1gina al escribir */
    @media (pointer: coarse) { font-size: max(16px, 1em); }
  }

  & button {
    padding: 0;
    border: 0;
    color: var(--azul);
  }
}

/* el markdown de la persona y del agente, ya convertido: compacto, como en una terminal */
.cuerpo.md {
  white-space: normal;

  & p,
  & ul,
  & ol,
  & pre { margin: var(--e-1) 0; }

  & ul,
  & ol { padding-left: var(--h-2); }

  & code {
    color: var(--cian);
    font: inherit;
  }

  & pre {
    overflow-x: auto;
    white-space: pre;
  }

  & strong { color: var(--amarillo); }

  & h1,
  & h2,
  & h3 {
    margin: var(--e-2) 0 var(--e-1);
    font-size: var(--t-normal);
  }

  & table { border-collapse: collapse; }

  & td,
  & th {
    padding: 0 var(--h-1);
    border: var(--borde);
  }
}

#dijo {
  min-height: 1lh;
  margin: var(--e-1) 0 0;
  font-size: var(--t-chica);
}
`;var lr=`/* El d\xEDa y lo que comparten sus pesta\xF1as: secciones, tareas, filas, formularios, la barra de arriba (vistas/dia.ts, vistas/hoy.ts). */

body { padding: 1lh 3ch 3lh; }
#dia { max-width: 120ch; container-type: inline-size; }
.cab { display: flex; gap: 1ch; align-items: baseline; }
.cab .der { margin-left: auto; }
h2 { font-size: 1em; font-weight: bold; text-transform: uppercase; margin: 1lh 0 0; }
h2 small { font-weight: normal; text-transform: none; color: var(--dim); margin-left: 1ch; }
.fila { display: flex; gap: 1ch; align-items: baseline; padding: 0 1ch; white-space: nowrap; }
.fila.clic { cursor: pointer; } .fila.clic:hover { background: var(--hover); }
.fila code { color: var(--verde); }
/* un code largo en una fila (una plantilla) se corta con \xAB\u2026\xBB; lo de la derecha (cambiar\u2026) siempre se ve */
.fila > code { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.fila > .der { flex: none; margin-left: auto; }
.falla { color: var(--rojo); }
.opcion { margin: 1lh 0; padding-left: 1ch; border-left: 2px solid transparent; }
.opcion.activa { border-left-color: var(--azul); }
.opcion .fila.dim { white-space: normal; }
/* una fila tenue que solo trae texto (con su code, b, a o em) es un p\xE1rrafo: se lee de corrido y se parte en
   l\xEDneas; como flex, cada pedazo de texto era una columna aparte (\xABLee tu \u23B5 gws\xBB) y lo largo se sal\xEDa */
.fila.dim:not(:has(> :not(code, b, a, em, i, strong))) { display: block; white-space: normal; }
.tecla { flex: none; width: 3ch; color: var(--dim); }
.hora { flex: none; color: var(--dim); }
.pasada, .pasada .que { color: var(--dim); }
.proxima .que, .proxima .hora { color: var(--fg); font-weight: bold; }
.que { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.cuando { color: var(--amarillo); flex: none; }
.enlace { flex: none; color: var(--azul); }
.titulo-tareas { display: flex; align-items: baseline; gap: 2ch; margin: 1lh 0 0; flex-wrap: wrap; }
.titulo-tareas h2 { margin: 0; }
.titulo-tareas.estrecho { flex-direction: column; align-items: stretch; gap: 0; margin-top: 0; }
.estrecho .modos { margin-left: 0; }
.modos.ordenes { gap: 2ch; }
.areas-t .modos, .duenos-t .modos { margin-left: 0; flex-wrap: wrap; gap: 0 2ch; }
.modos { display: flex; flex-wrap: wrap; gap: 0 2ch; align-items: baseline; margin-left: auto; }
.modos button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; white-space: nowrap; }
.modos button:hover { color: var(--fg); }
/* el seleccionado va solo en color: un subrayado se pegaba a la l\xEDnea de abajo */
.modos button.activo { color: var(--c, var(--verde)); }
#buscar { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
          width: 28ch; max-width: 100%; padding: 0 1ch; outline: none; flex: 1 1 12ch; }
#buscar:focus { border-bottom-color: var(--azul); }
#buscar::placeholder { color: var(--dim); }
.ayuda { color: var(--dim); margin: 0 0 0 1ch; }
#tareas-cuenta { color: var(--dim); }
.tarea.compacta .desc { -webkit-line-clamp: 1; }
.tarea.compacta .id { width: auto; min-width: 4ch; }
.compacta + #tareas-mas, #dia > .titulo-tareas { margin-top: 0; }
.tarea:hover { background: var(--hover); }
.tarea .desc { flex: 1; min-width: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.id, .pri { flex: none; color: var(--dim); } .id { width: 12ch; overflow: hidden; }
.meta { flex: none; color: var(--dim); text-align: right; }
.venc { color: var(--rojo); } .pronto { color: var(--amarillo); } .espera { color: var(--cian); }
.destino { color: var(--magenta); }
.at { flex: none; width: 1ch; } .at.trabajando { color: var(--azul); } .at.espera { color: var(--amarillo); } .at.termino { color: var(--verde); }
.nombre { min-width: 20ch; }
#globo { position: fixed; z-index: 10; pointer-events: none; white-space: pre-wrap; max-width: min(60ch, calc(100vw - 3ch));
         padding: 0 1ch; background: var(--vscode-editorHoverWidget-background, #1e1e2e);
         color: var(--vscode-editorHoverWidget-foreground, var(--fg));
         border: 1px solid var(--vscode-editorHoverWidget-border, var(--linea));
         box-shadow: 0 2px 8px rgb(0 0 0 / 35%); }
.md-pag p { margin: 0; white-space: normal; } .md-pag ul { margin: 0; padding-left: 2ch; }
.md-pag code, .texto-pag code { color: var(--verde); }
.lienzo { display: block; width: 100%; border: 0; margin: 0 0 1lh; background: transparent; }
/* una app a todo el panel: lo que queda bajo la barra y la cabecera */
.lienzo.lleno { height: calc(100vh - 6.5lh); min-height: 320px; margin: 0; }
.sep-pag { border-top: 1px solid var(--linea); margin: 1lh 0; }
.item-pag { padding: 0 1ch; margin: 0; border-left: 2px solid var(--linea); }
.item-pag.clic { cursor: pointer; } .item-pag.clic:hover { background: var(--hover); border-left-color: var(--azul); }
.texto-pag { color: var(--dim); display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.texto-pag p { margin: 0; }
.msg { margin: 1lh 0 0; } .msg .quien { font-weight: bold; } .msg.usuario .quien { color: var(--azul); }
.msg.agente .quien { color: var(--verde); }
.herr { padding-left: 2ch; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* \u2500\u2500 el dashboard: terminal con color \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
   Reglas de terminal: un solo tama\xF1o de letra y sin espaciado entre letras; lo
   horizontal en caracteres enteros (ch) y lo vertical en renglones enteros (lh); nada
   que decore ocupa lugar (bordes \u2192 outline o sombra; teclas en video inverso). */
#dia, #dia * { font-size: inherit !important; letter-spacing: 0 !important; }
small, code, kbd, button, input, b, i { font: inherit; }
/* una tecla: marco fino y borde de abajo m\xE1s grueso, como una tecla de verdad. El marco
   es outline y sombra (no ocupa lugar) y el relleno es medio car\xE1cter por lado: la tecla
   ocupa exactamente dos celdas y la grilla no se corre. */
kbd { padding: 0 .5ch; color: var(--fg); background: color-mix(in srgb, var(--fg) 6%, transparent);
      outline: 1px solid var(--linea); outline-offset: -1px; box-shadow: inset 0 -2px 0 var(--linea); }
.top { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 0 2ch; }
.top .marca-t { display: flex; align-items: baseline; gap: 0 2ch; flex-wrap: wrap; }
.logo { font-weight: bold; color: transparent;
        background: linear-gradient(90deg, var(--azul), var(--violeta), var(--rojo), var(--amarillo), var(--verde), var(--cian), var(--azul));
        background-size: 480px 100%; -webkit-background-clip: text; background-clip: text; animation: flujo 9s linear infinite; }
.fecha { color: var(--fg); } .reloj { color: var(--amarillo); } .sem { color: var(--dim); }
.regla { height: 2px; margin: 0;
         background: linear-gradient(90deg, var(--azul), var(--violeta), var(--rojo), var(--amarillo), var(--verde), var(--cian), var(--azul));
         background-size: 480px 100%; animation: flujo 9s linear infinite; }

@keyframes flujo { from { background-position: 0 0; } to { background-position: 480px 0; } }

.bloque { margin: 1lh 0 0; }
h2.sec { display: flex; align-items: baseline; gap: 1ch; margin: 0; text-transform: uppercase; color: var(--c); font-weight: bold; }
.sec .marca { width: 1ch; align-self: stretch; background: var(--c); }
.sec .cuenta { color: var(--bg); background: var(--c); padding: 0 1ch; }
.bloque > .ag, .bloque > .hl, .bloque #tareas, .bloque > .vacio, .bloque > .titulo-tareas {
    box-shadow: inset 1px 0 0 color-mix(in srgb, var(--c) 35%, transparent); }
.vacio { color: var(--dim); padding: 0 2ch; }
.clic { cursor: pointer; }

/* agenda: tecla \xB7 hora \xB7 qu\xE9 \xB7 lo de al lado */
.plazo-clic { cursor: pointer; } .plazo-clic:hover { text-decoration: underline; }
.menu-fila { cursor: pointer; color: var(--dim); text-align: center; } .menu-fila:hover { color: var(--fg); background: var(--hover); }
.ag { display: grid; grid-template-columns: 7ch minmax(0, 1fr) auto; gap: 1ch; align-items: baseline; padding: 0 1ch; }
.ag .hora { color: var(--c); }
.ag .que { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ag .extra { display: flex; gap: 2ch; align-items: baseline; white-space: nowrap; color: var(--dim); }
.ag.pasada { color: var(--dim); } .ag.pasada .hora { color: var(--dim); } .ag.pasada .que { text-decoration: line-through; text-decoration-color: var(--linea); }
.ag.clic:hover, .hl.clic:hover, .tarea:hover { background: var(--hover); box-shadow: inset 2px 0 0 var(--c); }
.ag.proxima { background: color-mix(in srgb, var(--c) 12%, transparent); box-shadow: inset 2px 0 0 var(--c); }
.ag.proxima .que { color: var(--fg); font-weight: bold; }
.punto { font-style: normal; color: var(--c); animation: latido 1.6s ease-in-out infinite; }
.falta { color: var(--bg); background: var(--amarillo); padding: 0 1ch; font-weight: bold; }
.ag .enlace { color: var(--azul); }

@keyframes latido { 50% { opacity: .2; } }

/* esperan: estado \xB7 hilo \xB7 hace cu\xE1nto */
.hl { display: grid; grid-template-columns: 1ch minmax(0, 1fr) 4ch; gap: 1ch; align-items: baseline; padding: 0 1ch; }
.hl .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.hl .cuando { text-align: right; color: var(--dim); }
.hl .at { width: auto; font-weight: bold; } .hl .at.espera { animation: pulso 2.4s ease-in-out infinite; }

@keyframes pulso { 50% { opacity: .45; } }

/* atajos: teclas-bot\xF3n */
/* los atajos se ven como el resto de las teclas (pesta\xF1as, pie): tecla y nombre, sin marco */

/* pendientes: tecla \xB7 c\xF3digo \xB7 casilla \xB7 texto \xB7 plazo */
.bloque .titulo-tareas { margin: 0; padding: 0 1ch; gap: 0 2ch; }
.bloque .titulo-tareas .modos:first-child { margin-left: 0; }
.bloque .modos button.activo { color: var(--c); }
.tarea { display: grid; grid-template-columns: 6ch 1ch minmax(0, 1fr) auto; gap: 1ch; align-items: baseline; padding: 0 1ch; cursor: pointer; }
.tarea.compacta { grid-template-columns: 5ch 1ch minmax(0, 1fr) auto; padding: 0; }
.tarea .id { width: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dim); }
.tarea.encurso .pri { color: var(--azul); }
.tarea:hover .marcar::after { content: '\u2713'; color: var(--dim); }
.tarea .marcar:hover::after { color: var(--verde); font-weight: bold; }
.tarea .dueno { color: var(--magenta); margin-right: 1ch; }
.tarea.marcada { opacity: .4; text-decoration: line-through; pointer-events: none; }
/* el \u2713 mientras se marca: gira, en verde, hasta que la lista se relee */
.rap.girando { color: var(--verde); opacity: 1; display: inline-block; animation: girar 1s linear infinite; }

@keyframes girar { to { transform: rotate(360deg); } }
.av { font-weight: bold; margin-right: 1ch; }
/* la ficha de una tarea: la propuesta del agente con el color de su estado, y los botones */
#ficha-tarea { --c: var(--verde); }
/* la pesta\xF1a de procesos peri\xF3dicos: una fila por proceso, y su ficha con el log */
.fila.per { display: grid; grid-template-columns: 2ch 22ch 16ch minmax(0, 1fr) max-content; }
.fila.per b, .fila.per .que, .fila.per code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fila.per.dim b { color: var(--dim); }
#ficha-per .fila { white-space: normal; } #ficha-per .fila .que { overflow-wrap: anywhere; }
#ficha-per pre.log { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--dim); max-height: 60vh; overflow: auto;
  box-shadow: inset 2px 0 0 var(--linea); padding: 0 2ch; margin: 0; }
/* el formulario de un peri\xF3dico: etiqueta a la izquierda, control a la derecha */
#form-per .campo { display: grid; grid-template-columns: 12ch minmax(0, 1fr); gap: 2ch; align-items: baseline; margin: .5lh 0; }
#form-per .etiqueta { color: var(--dim); text-align: right; }
#form-per .control { display: flex; flex-direction: column; gap: .25lh; min-width: 0; }
#form-per input:not([type="checkbox"]), #form-per textarea { font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--linea);
  padding: 0 1ch; outline: none; width: 100%; max-width: 80ch; box-sizing: border-box; resize: vertical; }
#form-per input:focus, #form-per textarea:focus { border-color: var(--amarillo); }
#form-per input:disabled { color: var(--dim); }
#form-per input[type="number"] { width: 8ch; }
#form-per input[type="checkbox"] { align-self: flex-start; margin: 0; accent-color: var(--amarillo); }
#form-per .ayuda { font-size: var(--t-menor); }
#form-per .opciones, #form-per .presets { display: flex; flex-wrap: wrap; gap: 0 2ch; }
#form-per .opcion-t, #form-per .presets a { cursor: pointer; color: var(--dim); }
#form-per .opcion-t.activa { color: var(--amarillo); font-weight: bold; }
#form-per .opcion-t:hover, #form-per .presets a:hover { color: var(--fg); }
#form-per.tipo-mensaje .solo-comando, #form-per.tipo-comando .solo-mensaje { display: none; }
#form-per .skills { max-height: 14lh; overflow: auto; max-width: 80ch; box-shadow: inset 2px 0 0 var(--linea); }
#form-per .skill { display: grid; grid-template-columns: 22ch minmax(0, 1fr); gap: 1ch; padding: 0 1ch; cursor: pointer; }
#form-per .skill span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#form-per .skill:hover { background: var(--hover); } #form-per .skill.activa b { color: var(--amarillo); }
#form-per .skill[hidden] { display: none; }
#form-per #per-error { margin: .5lh 0 0 14ch; white-space: pre-wrap; }
#form-per .fila-botones { grid-auto-flow: column; justify-content: start; gap: 3ch; margin-left: 14ch; }

@media (width <= 90ch) { .fila.per { grid-template-columns: 2ch minmax(0, 1fr) max-content; } .fila.per code, .fila.per .que { display: none; } }
.prop { box-shadow: inset 2px 0 0 var(--c); padding: 0 2ch; margin: 1lh 0; }
.sub-ficha { white-space: normal; overflow-wrap: anywhere; }
.prop h2 { color: var(--c); }
/* una acci\xF3n por fila: la tecla en su columna, el nombre en la otra */
.acciones-t { display: grid; grid-template-columns: max-content; margin: 1lh 0; }
.acciones-t .atajo { gap: 1ch; }
.pasar { display: inline-flex; gap: 1ch; } .pasar a { color: var(--c); cursor: pointer; } .pasar a:hover { text-decoration: none; color: var(--fg); }
.acciones-t .atajo.principal span { color: var(--c); font-weight: bold; }
.acciones-t .atajo.principal kbd { outline-color: var(--c); box-shadow: inset 0 -2px 0 var(--c); color: var(--c); }
.av-preparado { color: var(--verde); } .av-cerrar { color: var(--cian); }
.av-pregunta { color: var(--amarillo); } .av-choca { color: var(--rojo); }
.tarea .meta { display: grid; grid-template-columns: 5ch 1ch 1ch; gap: 2ch; white-space: nowrap; }
.tarea .meta > :first-child { text-align: right; }
.tarea.compacta .meta { grid-template-columns: 5ch 1ch; gap: 1ch; font-size: .95em; }
.tarea .destino { color: var(--magenta); overflow: hidden; text-overflow: ellipsis; text-align: left; }
#tareas-mas { color: var(--c); padding: 0 1ch; }

/* la barra de arriba: fija, igual en todas las pesta\xF1as */
.fijo { position: sticky; top: 0; z-index: 5; background: var(--bg); padding: 1lh 0 0; margin-top: -1lh; }
.top .recargar { color: var(--dim); } .top .recargar:hover { color: var(--fg); text-decoration: none; }
.tabs { display: flex; flex-wrap: wrap; gap: 0; margin-top: 1lh; }
.tab { padding: 0 1ch; color: var(--dim); white-space: nowrap; }
.tab:hover { color: var(--fg); text-decoration: none; background: var(--hover); }
.tab.activa { color: var(--bg); background: var(--t, var(--azul)); font-weight: bold; }
.tab.activa kbd { color: var(--bg); background: transparent; outline-color: var(--bg); box-shadow: inset 0 -2px 0 var(--bg); }
.tab[data-accion="dia"] { --t: var(--amarillo); } .tab[data-accion="proyectos"] { --t: var(--cian); }
.tab[data-accion="correo"] { --t: var(--magenta); } .tab[data-accion="seccion"] { --t: var(--violeta); }
.tab[data-accion="config"] { --t: var(--verde); }
.fijo::after { content: ""; display: block; height: 1lh; }
.subcab { display: flex; gap: 0 2ch; align-items: baseline; flex-wrap: wrap; margin: 0 0 1lh; --c: var(--violeta); }
.subcab b { color: var(--fg); } .subcab .der { display: flex; gap: 0 3ch; margin-left: auto; }

/* el atajo: uno solo en todo el dashboard. Tecla y nombre; al pasar el mouse, los dos
   toman el color de su secci\xF3n (--c) */
.atajo { display: inline-flex; gap: 1ch; align-items: baseline; color: var(--fg); white-space: nowrap; cursor: pointer; }
.atajo:hover { color: var(--c, var(--azul)); text-decoration: none; }
.atajo:hover kbd { color: var(--c, var(--azul)); outline-color: var(--c, var(--azul)); box-shadow: inset 0 -2px 0 var(--c, var(--azul)); }
.atajo.pista { color: var(--dim); cursor: default; }
.atajo.pista:hover, .atajo.pista:hover kbd { color: var(--dim); outline-color: var(--linea); box-shadow: inset 0 -2px 0 var(--linea); }
.sec .acciones { margin-left: auto; display: flex; flex-wrap: wrap; gap: 0 3ch; text-transform: none; font-weight: normal; }
.sec .leyenda { color: var(--dim); }
.generales { display: flex; flex-wrap: wrap; gap: 0 3ch; --c: var(--cian); }
.top .atajo { color: var(--dim); } .top .atajo:hover { color: var(--c, var(--azul)); }

/* un bloque del d\xEDa (el correo): marca \xB7 hora \xB7 de \xB7 qu\xE9 */
.cr { display: grid; grid-template-columns: 1ch 6ch 20ch minmax(0, 1fr); gap: 1ch; align-items: baseline; padding: 0 1ch;
      box-shadow: inset 1px 0 0 color-mix(in srgb, var(--c) 35%, transparent); color: var(--dim); }
.cr .mk { color: var(--dim); } .cr .hora { color: var(--dim); }
.cr .de { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cr .que { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* las tareas de cada \xEDtem (las de un correo), separadas por coma; \xAB\u2014\xBB si no tiene */
.cr.con-t { grid-template-columns: 1ch 6ch 20ch minmax(0, 1fr) 16ch; }
/* el cuerpo de un \xEDtem abierto (un correo): cinco l\xEDneas, y entero al desplegarlo */
.cuerpo { white-space: pre-wrap; overflow-wrap: anywhere; margin: .5lh 0 .25lh; padding-left: 1ch; box-shadow: inset 2px 0 0 var(--linea); }
.cuerpo.plegado { display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
.cr .plegar { color: var(--c); cursor: pointer; margin-right: .5ch; } .cr .plegar:hover { color: var(--fg); }
.cr.hijo .que { padding-left: 3ch; } .cr.hijo .de { padding-left: 1ch; }
.cr .tar .cerrada { color: var(--dim); opacity: .6; } .cr .tar .abierta { color: var(--cian); }
.solo-pend { color: var(--dim); cursor: pointer; white-space: nowrap; } .solo-pend:hover, .solo-pend.si { color: var(--fg); }
.cr .tar { color: var(--cian); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: right; }
.cr.nuevo { color: var(--fg); } .cr.nuevo .mk { color: var(--c); } .cr.nuevo .hora { color: var(--c); }
.cr:hover { background: var(--hover); } .cr.clic { cursor: pointer; } .cr.clic:hover .que { color: var(--c); }

/* angosto: lo secundario se va, lo principal nunca */
@container (max-width: 620px) {
  .ag .extra .hilo-ag { display: none; }
  .tarea .meta { grid-template-columns: 5ch 1ch 1ch; }
  .tarea:not(.compacta) { grid-template-columns: 5ch minmax(0, 1fr) auto; } .tarea:not(.compacta) .pri { display: none; }
  .ag { grid-template-columns: 7ch minmax(0, 1fr); } .ag .extra { grid-column: 2; }
  .ag:not(.proxima) .extra { display: none; }
  .cr { grid-template-columns: 1ch 6ch minmax(0, 1fr); } .cr .de { display: none; }
  .cr.con-t { grid-template-columns: 1ch 6ch minmax(0, 1fr) 11ch; }
  .sec .acciones .pista { display: none; }  /* abajo solo va lo de la pr\xF3xima: el resto ser\xEDa un rengl\xF3n vac\xEDo */
}

@media (prefers-reduced-motion: reduce) { .logo, .regla, .punto, .hl .at.espera { animation: none; } }
#revisar #tareas-t .tarea, #revisar .tareas-cab, .tareas-sueltas .tarea { grid-template-columns: 6ch 2ch 1ch 18ch 14ch minmax(0, 1fr) auto; }
/* las acciones a un clic, antes del \u22EF: \u2713 hecha, \u25C9 compartir, \u25B6 a un hilo */
#revisar .tarea .meta, .tareas-sueltas .tarea .meta { grid-template-columns: 5ch 1ch 7ch 1ch; }
.rapidas { display: inline-grid; grid-template-columns: repeat(3, 1ch); gap: 1ch; }

/* la tabla de tareas en un celular: el c\xF3digo y el texto, con espacio para leerlo, y debajo la fecha y
   \u2713 \u25B6 \u22EF; la estrella, el proyecto y el responsable se van (siguen en la ficha) */
@container (max-width: 620px) {
  #revisar #tareas-t .tarea,
  #revisar .tareas-cab,
  .tareas-sueltas .tarea { grid-template-columns: 5ch minmax(0, 1fr); row-gap: 0; padding-block: .2lh; }

  #revisar #tareas-t .tarea > :is(:nth-child(2), :nth-child(3), :nth-child(4), :nth-child(5)),
  #revisar .tareas-cab > :is(:nth-child(2), :nth-child(3), :nth-child(4), :nth-child(5)),
  .tareas-sueltas .tarea > :is(:nth-child(2), :nth-child(3), :nth-child(4), :nth-child(5)) { display: none; }

  #revisar .tarea .meta,
  .tareas-sueltas .tarea .meta { grid-column: 2; justify-self: start; }
}
.rap { color: var(--dim); cursor: pointer; text-align: center; opacity: .55; }
.tarea:hover .rap { opacity: 1; }
.rap.ok:hover { color: var(--verde); font-weight: bold; } .rap.ir:hover { color: var(--azul); }
.rap.eq:hover, .rap.eq.on { color: var(--cian); opacity: 1; }
#revisar .estr { cursor: pointer; color: var(--dim); opacity: 0; } #revisar .tarea:hover .estr { opacity: 1; }
#revisar .estr.on { color: var(--amarillo); opacity: 1; } #revisar .estr:hover { color: var(--amarillo); }
#revisar .eq { cursor: pointer; color: var(--dim); opacity: .35; } #revisar .tarea:hover .eq { opacity: 1; }
#revisar .eq.on { color: var(--cian); opacity: 1; font-weight: 700; } #revisar .eq:hover { color: var(--cian); }
#tareas-t-mas { margin-top: .5lh; color: var(--azul); }
#revisar .tareas-cab { display: grid; gap: 1ch; padding: 0 1ch; color: var(--dim); margin-top: .5lh; }
#revisar .tareas-cab [data-orden-c] { cursor: pointer; } #revisar .tareas-cab [data-orden-c]:hover { color: var(--fg); }
#revisar .tareas-cab .activo { color: var(--azul); }
#revisar .resp { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--amarillo); cursor: pointer; }
#revisar .resp:hover { text-decoration: underline; } #revisar .resp.defecto { color: var(--dim); }
#revisar .resp.dim, #revisar .resp.fijo { cursor: default; text-decoration: none; } #revisar .resp.dim { color: var(--dim); }
#revisar .proy-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--azul); cursor: pointer; }
#revisar .proy-t:hover { text-decoration: underline; } #revisar .proy-t.dim { color: var(--dim); cursor: default; text-decoration: none; }
#buscar-t { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
            width: 20ch; padding: 0 1ch; outline: none; }
#buscar-t:focus { border-bottom-color: var(--azul); }
#tareas-t-cuenta { color: var(--dim); }
.modos button.vacio-m { opacity: .5; }
#buscar-p { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
            width: 28ch; max-width: 100%; padding: 0 1ch; outline: none; flex: 1 1 12ch; }
#buscar-p:focus { border-bottom-color: var(--azul); }
#buscar-p::placeholder { color: var(--dim); }
#proyectos-cuenta { color: var(--dim); }
.proy .que { flex: 1; }
.proy .tipo { flex: none; width: 9ch; overflow: hidden; text-overflow: ellipsis; }
.proy .cuando-p { flex: none; width: 4ch; text-align: right; }
.proy.primera { background: var(--hover); }
`;var cr=`/* La carpeta de un hilo y su documento, en la web (web/pagina.ts, paginaDocumento): los archivos
   arriba, como una lista corta, y el elegido abajo. */

body { padding: var(--e-2) var(--h-2) var(--e-3); }

h1 {
  margin: 0 0 var(--e-2);
  font-size: var(--t-mayor);
}

.donde {
  color: var(--dim);
  font-size: var(--t-menor);
}

.nada { color: var(--dim); }

.carpeta {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--h-2);
  padding-bottom: var(--e-2);
  border-bottom: var(--borde);

  & .donde { flex-basis: 100%; }
  & a { color: var(--fg); }
  & a.dir { color: var(--azul); }
  & a.sel { color: var(--amarillo); }
}

article {
  padding-top: var(--e-2);

  & pre {
    overflow-x: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: inherit;
  }
}

.md {
  max-width: 90ch;
  overflow-wrap: anywhere;

  & h1,
  & h2,
  & h3 {
    margin: var(--e-3) 0 var(--e-1);
    color: var(--amarillo);
    font-size: var(--t-normal);
  }

  & code { color: var(--cian); font: inherit; }

  & pre {
    overflow-x: auto;
    padding: var(--e-1) var(--h-1);
    border: var(--borde);
  }

  & table {
    display: block;
    overflow-x: auto;
    border-collapse: collapse;
  }

  & td,
  & th {
    padding: 0 var(--h-1);
    border: var(--borde);
  }

  & img { max-width: 100%; }
}
`;var dr=`/* La ficha del hilo con foco, en la barra de VS Code (vistas/ficha.ts). */

body { padding: 0 1.5ch 2em; }
.skill { padding: .3em 0; cursor: pointer; } .skill:hover b { text-decoration: underline; }
.skill.usada b { color: var(--vscode-charts-green, #a6e3a1); }
.desc-skill { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.barra { display: flex; gap: 2ch; align-items: baseline; padding: .5em 0 .4em; position: sticky; top: 0;
         background: var(--bg); border-bottom: 1px solid var(--linea); margin-bottom: .6em; }
.barra button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; }
.barra button:hover { color: var(--fg); }
.barra .nuevo { color: var(--amarillo); }
.correo { margin: .8em 0; padding-left: 1ch; border-left: 2px solid var(--linea); }
.correo.nuevo { border-left-color: var(--amarillo); }
.correo .cuerpo { white-space: pre-wrap; margin-top: .3em; }
.barra button.activo { color: var(--fg); text-decoration: underline; text-underline-offset: 3px; }
.barra .sep { flex: 1; }
h1.t { font-size: 1em; font-weight: bold; margin: .3em 0 0; }
.sem { display: inline-block; margin-top: .2em; }
.sem.trabajando { color: var(--azul); } .sem.espera { color: var(--amarillo); } .sem.termino { color: var(--verde); }
h2 { font-size: 1em; font-weight: bold; text-transform: uppercase; margin: 1.1em 0 .1em; }
h2 small { font-size: 1em; font-weight: normal; text-transform: none; color: var(--dim); }
ul { list-style: none; padding: 0; margin: 0; }
li { padding-left: 4ch; text-indent: -2ch; }
li .m { display: inline-block; width: 2ch; text-indent: 0; }
li.pend { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
li.pend a { color: inherit; } li.pend a:hover { color: var(--azul); text-decoration: none; }
.ref { color: var(--dim); margin-right: 1ch; }
.campos div { display: flex; gap: 1ch; }
.campos .k { color: var(--dim); min-width: 14ch; }
.accion { display: block; cursor: pointer; }
.accion .tecla { color: var(--dim); margin-right: 1ch; }
.accion:hover { background: var(--hover); }
.md { max-width: 90ch; }
.md h1, .md h2, .md h3, .md h4 { font-size: 1em; font-weight: bold; text-transform: none; margin: 1.2em 0 .3em; }
.md h1 { color: var(--magenta); } .md h2 { color: var(--azul); } .md h3, .md h4 { color: var(--cian); }
.md h1::before { content: "# "; color: var(--dim); } .md h2::before { content: "## "; color: var(--dim); }
.md h3::before { content: "### "; color: var(--dim); } .md h4::before { content: "#### "; color: var(--dim); }
.md p { margin: .5em 0; }
.md table { border-collapse: collapse; margin: .5em 0; }
.md td, .md th { border: 1px solid var(--linea); padding: 0 1ch; text-align: left; vertical-align: top; }
.md th { font-weight: bold; }
.md code { font: inherit; color: var(--verde); }
.md pre { background: var(--hover); padding: .5em 1ch; overflow-x: auto; } .md pre code { color: var(--fg); }
.md ul, .md ol { padding-left: 3ch; margin: .3em 0; } .md ul { list-style: "- "; }
.md li { padding-left: 0; text-indent: 0; }
.md li::marker { color: var(--dim); }
.md blockquote { border-left: 2px solid var(--linea); margin: .5em 0; padding: 0 1ch; color: var(--dim); }
.md strong { color: var(--fg); } .md em { color: var(--amarillo); font-style: normal; }
.md img { max-width: 100%; } .md hr { border: 0; border-top: 1px dashed var(--linea); margin: 1em 0; }
`;var ur=`/* La barra de hilos (vistas/hilos.ts). */

#lista { padding: .5em 0 1.5em; user-select: none; }
.fila { display: flex; position: relative; white-space: pre; padding: 0 1.5ch; cursor: pointer; }
.fila:hover { background: var(--hover); }
.fila.activa { background: var(--sel); }
.prio { flex: none; width: 1ch; margin-right: 1ch; }
.prio.p0 { color: var(--dim); }
.p1 { color: var(--fg); } .p2 { color: color-mix(in srgb, var(--fg) 65%, var(--bg)); } .p3 { color: var(--dim); }
.nombre { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.muerto .nombre, .archivado .nombre, .archivado .prio { color: var(--dim); }
.at { flex: none; width: 1ch; margin-right: 1ch; text-align: center; }
.remoto { flex: none; width: 1ch; margin-right: 1ch; color: var(--cian); }
/* con la columna ancha (\u21C4 junto a buscar): el nombre de la m\xE1quina; el ancho lo da la fila */
.remoto.ancho { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--amarillo); }
.remoto.ancho.aqui { color: var(--dim); }
.sobre { flex: none; width: 1ch; margin-right: 1ch; color: var(--amarillo); }
.at.trabajando { color: var(--azul); } .at.espera { color: var(--amarillo); } .at.termino { color: var(--verde); }
/* termin\xF3 y ya lo viste: tenue; el que no has visto sigue en verde (te espera) */
.at.termino.visto { color: var(--dim); }
.der { flex: none; margin-left: auto; padding-left: 1ch; color: var(--dim); }
.sep { border-top: 1px solid var(--linea); margin: .4em 1.5ch; }
.cab { color: var(--amarillo); font-weight: bold; }
/* un agente: una l\xEDnea como cualquier hilo, con su nombre en amarillo y su home al final */
.agente .nombre { color: var(--amarillo); } .agente.muerto .nombre { color: color-mix(in srgb, var(--amarillo) 55%, var(--bg)); }
.casa { flex: none; color: var(--azul); }
.hoy .nombre { color: var(--azul); }
.cab .dim { font-weight: normal; }
.nota { color: var(--dim); padding: .2em 1.5ch; white-space: pre-wrap; }
.iconos { position: absolute; right: 1.5ch; top: 0; bottom: 0; display: none; padding-left: 1ch;
         background: linear-gradient(var(--hover), var(--hover)), var(--bg); }
.activa .iconos { background: linear-gradient(var(--sel), var(--sel)), var(--bg); }
.fila:hover .iconos { display: flex; }
.icono { margin-left: 1ch; color: var(--dim); cursor: pointer; font-variant-emoji: text; }
.icono:hover { color: var(--fg); }
.menu-web { display: none; }  /* el \u22EF del navegador: en VS Code el men\xFA es el contextual (web.css lo muestra) */
/* el buscador y los \xF3rdenes de un grupo (HILOS, ARCHIVO), bajo su cabecera */
.herram { display: flex; align-items: center; gap: 1ch; padding: .15em 1.5ch .3em 3.5ch; }
.herram input { flex: 1 1 auto; min-width: 0; font: inherit; color: var(--fg); background: transparent;
                border: 0; border-bottom: 1px solid var(--linea); padding: 0 0 1px; outline: none; }
.herram input:focus { border-bottom-color: var(--azul); }
.herram input::placeholder { color: var(--dim); }
.ord { flex: none; color: var(--dim); cursor: pointer; }
.ord:hover { color: var(--fg); } .ord.si { color: var(--amarillo); }
.vacia { color: var(--dim); padding: 0 1.5ch 0 3.5ch; }
`;var pr=`/* El plan del d\xEDa y el calendario (vistas/plan.ts). */

.plan-nav { display: flex; gap: 2ch; align-items: baseline; padding: 0 1ch .5lh; color: var(--dim); }
.plan-nav a { color: var(--azul); }
.plan-txt { padding: .2lh 1ch; } .plan-txt p { margin: .2lh 0; }
.plan-riesgo { color: var(--rojo); }
.plan-fila { display: grid; grid-template-columns: 12ch minmax(0, 1fr); gap: 1ch; padding: .15lh 1ch; }
.plan-fila .k { color: var(--dim); }
.plan-fila .sub { color: var(--dim); display: block; }
.plan-fila.estrategico .v { font-weight: bold; }
.cal-nav { display: flex; gap: 1.5ch; align-items: baseline; margin: .5lh 0 0 6ch; }
.cal-nav a { color: var(--dim); }
.cal-nav a:hover { color: var(--fg); text-decoration: none; background: var(--hover); }
.cal-nav .cal-fecha { min-width: 14ch; text-align: center; }
.cal-dos { display: grid; grid-template-columns: minmax(28ch, 1fr) minmax(32ch, 1.2fr); gap: 2ch; align-items: start; }
.cal { position: relative; margin: 1lh 0 1lh 6ch; border-left: 1px solid var(--linea); }
.cal-hora { position: absolute; left: -6ch; width: 5ch; text-align: right; color: var(--dim); font-size: var(--t-chica); transform: translateY(-.6em); }
.cal-linea { position: absolute; left: 0; right: 0; border-top: 1px solid var(--linea); }
.cal-ahora { position: absolute; left: 0; right: 0; border-top: 2px solid var(--rojo); z-index: 3; }
.cal-ev { position: absolute; box-sizing: border-box; padding: 2px 6px; overflow: hidden; cursor: pointer;
          background: color-mix(in srgb, var(--azul) 22%, transparent); border-left: 3px solid var(--azul); }
.cal-ev:hover { background: color-mix(in srgb, var(--azul) 34%, transparent); }
.cal-ev.plan { background: transparent; border: 1px dashed var(--amarillo); border-left: 3px solid var(--amarillo); }
.cal-ev.pasado { opacity: .55; }
.cal-ev.sel { outline: 2px solid var(--fg); z-index: 2; }
.cal-ev .h { color: var(--dim); font-size: var(--t-chica); } .cal-ev .t { display: block; }
.cal-ev.corto { white-space: nowrap; text-overflow: ellipsis; } .cal-ev.corto .t { display: inline; margin-left: .5ch; }
.cal-ev .marca-nota { color: var(--amarillo); }
.cal-dia-completo { padding: .2lh 1ch; color: var(--dim); }
.cal-det { position: sticky; top: 4lh; padding: .5lh 1ch; border-left: 1px solid var(--linea); text-align: left; }
.cal-det h3 { margin: 0 0 .3lh; }
.cal-det .cal-meta { color: var(--dim); margin-bottom: .5lh; }
.cal-det .acciones-ev { display: flex; gap: 2ch; margin: .3lh 0 .7lh; }
.cal-nota { padding: .3lh 0; border-top: 1px solid var(--linea); }
.cal-nota .de { color: var(--dim); font-size: var(--t-chica); }
.cal-escribir { margin-top: 1lh; display: flex; flex-direction: column; gap: .4lh; }
.cal-escribir textarea { font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--linea); padding: .3lh 1ch; resize: vertical; }
.cal-escribir textarea:focus { outline: none; border-color: var(--amarillo); }
.cal-escribir a { align-self: flex-end; }
`;var hr=`/* Los proyectos en dos columnas: la lista y el detalle (vistas/proyectos.ts). */

/* la lista se lleva m\xE1s que el detalle: lo que se lee ah\xED es el nombre */
.proy-dos { display: grid; grid-template-columns: minmax(44ch, 1.25fr) minmax(40ch, 1fr); gap: 1.5ch; align-items: start; }
#dia:has(.proy-dos) { max-width: none; }
.proy-lista .fila { gap: .8ch; }
.proy-lista { min-width: 0; }
.proy.sel { background: color-mix(in srgb, var(--azul) 22%, transparent); }
.proy .que { overflow: hidden; text-overflow: ellipsis; }
.proy .cliente { color: var(--azul); }
.proy .cliente + .resto { color: var(--dim); }
.proy-cab { color: var(--dim); }
.proy .menu-col, .proy-cab .menu-col { flex: none; width: 2ch; }
.proy-cab [data-orden-p] { cursor: pointer; } .proy-cab [data-orden-p]:hover { color: var(--fg); }
.proy-cab .activo { color: var(--azul); }
.proy-cab .estado { flex: none; width: 12ch; } .proy-cab .tipo { flex: none; width: 9ch; }
.proy-cab .cuando-p { flex: none; width: 4ch; text-align: right; } .proy-cab .que { flex: 1; }
.proy .estado { flex: none; width: 12ch; overflow: hidden; text-overflow: ellipsis; color: var(--dim); }
.proy .estado.e-activo { color: var(--verde); }
.proy .estado.e-abierto { color: var(--amarillo); }
.proy .estado.e-trabado { color: var(--rojo); }
.proy.cerrado .cliente, .proy.cerrado .estado { color: var(--dim); }
.proy.cerrado { color: var(--dim); }
#proy-det { position: sticky; top: 1lh; max-height: calc(100vh - 3lh); overflow-y: auto; padding: .5lh 1ch;
  border-left: 1px solid var(--linea); min-width: 0; }
#proy-det h3 { margin: 0 0 .2lh; }
#proy-det .proy-meta { color: var(--dim); margin-bottom: .4lh; white-space: normal; }
#proy-det .acciones-ev { display: flex; gap: 2ch; margin: .3lh 0 .7lh; }
#proy-det h4 { margin: 1lh 0 .3lh; font-size: 1em; text-transform: uppercase; color: var(--dim); font-weight: normal; }
#proy-det .tarea { padding: 0; }
.proy-readme { white-space: normal; line-height: 1.45; border-top: 1px solid var(--linea); padding-top: .4lh; }
.proy-readme h1 { font-size: var(--t-mayor); margin: .6lh 0 .3lh; }
.proy-readme h2 { font-size: 1.05em; text-transform: none; margin: .9lh 0 .3lh; }
.proy-readme h3, .proy-readme h4 { font-size: 1em; margin: .7lh 0 .2lh; }
.proy-readme table { border-collapse: collapse; margin: .3lh 0; }
.proy-readme td, .proy-readme th { border: 1px solid var(--linea); padding: 0 1ch; vertical-align: top; }
.proy-readme pre { white-space: pre-wrap; } .proy-readme img { max-width: 100%; }
.proy-readme blockquote { margin: .3lh 0; padding-left: 1ch; border-left: 2px solid var(--linea); color: var(--dim); }
.proy-readme ul, .proy-readme ol { padding-left: 3ch; margin: .2lh 0; }
`;var fr=`/* La terminal de un hilo en el navegador (web/pagina.ts, paginaTerminal): xterm arriba, y abajo una caja
   para escribirle sin el viaje de ida y vuelta de cada tecla (lo escrito va entero al apretar \u23CE). */

html,
body { height: 100%; }

body {
  display: flex;
  flex-direction: column;
  height: 100dvh;
}

#t {
  flex: 1;
  min-height: 0;
  padding: var(--e-1) 0 0 var(--h-1);
}

#escribir {
  display: flex;
  gap: var(--h-1);
  align-items: flex-end;
  padding: var(--e-1) var(--h-1);
  border-top: var(--borde);

  /* como el prompt de una terminal: la letra de todo lo dem\xE1s, sin caja; la l\xEDnea de la izquierda se pone
     azul mientras se escribe aqu\xED (y se apaga cuando las teclas van directo a la terminal) */
  & textarea {
    flex: 1;
    min-width: 0;
    max-height: 8lh;
    box-sizing: border-box;
    padding: 0 var(--h-1);
    border: 0;
    border-left: 2px solid var(--linea);
    outline: none;
    background: transparent;
    color: var(--fg);
    font: inherit;
    resize: none;

    &:focus { border-left-color: var(--azul); }
    &::placeholder { color: var(--dim); }

    @media (pointer: coarse) { font-size: max(16px, 1em); }
  }

  & .ayuda {
    color: var(--dim);
    font-size: var(--t-chica);
    white-space: nowrap;
  }
}
`;var mr=`/* Los tokens: colores, tipograf\xEDa y espacio. Los colores son los del tema de la terminal de VS Code
   (sus variables --vscode-*) y, fuera de VS Code, catppuccin mocha. Todo lo dem\xE1s se arma con estos. */

:root {
  /* colores */
  --fg: var(--vscode-terminal-foreground, var(--vscode-foreground, #cdd6f4));
  --bg: var(--vscode-terminal-background, var(--vscode-panel-background, var(--vscode-editor-background, #1e1e2e)));
  --dim: var(--vscode-terminal-ansiBrightBlack, #6c7086);
  --linea: color-mix(in srgb, var(--fg) 16%, transparent);
  --sel: var(--vscode-terminal-selectionBackground, rgb(128 128 128 / 25%));
  --hover: color-mix(in srgb, var(--fg) 7%, transparent);
  --azul: var(--vscode-terminal-ansiBlue, #89b4fa);
  --amarillo: var(--vscode-terminal-ansiYellow, #f9e2af);
  --verde: var(--vscode-terminal-ansiGreen, #a6e3a1);
  --rojo: var(--vscode-terminal-ansiRed, #f38ba8);
  --magenta: var(--vscode-terminal-ansiBrightMagenta, #f5c2e7);
  --cian: var(--vscode-terminal-ansiCyan, #94e2d5);
  --violeta: var(--vscode-terminal-ansiMagenta, #cba6f7);
  /* lo que completa los 16 colores de una terminal (xterm, en la p\xE1gina) y el fondo de una barra */
  --negro: var(--vscode-terminal-ansiBlack, #45475a);
  --blanco: var(--vscode-terminal-ansiWhite, #bac2de);
  --blanco-claro: var(--vscode-terminal-ansiBrightWhite, #a6adc8);
  --cursor: var(--vscode-terminalCursor-foreground, #f5e0dc);
  --bg-barra: var(--vscode-sideBar-background, #181825);

  /* tipograf\xEDa: una sola letra (la de la terminal) y una escala corta */
  --t-chica: .85em;
  --t-menor: .9em;
  --t-normal: 1em;
  --t-mayor: 1.25em;

  /* espacio: en l\xEDneas (vertical) y en caracteres (horizontal), como una terminal */
  --e-1: .25lh;
  --e-2: .5lh;
  --e-3: 1lh;
  --h-1: 1ch;
  --h-2: 2ch;
  --borde: 1px solid var(--linea);
}
`;var at=`/* Lo que la p\xE1gina web agrega: di\xE1logos y avisos que en VS Code son nativos (web/pagina.ts). */

/* un di\xE1logo (<dialog>): un campo para escribir, un men\xFA para elegir, un aviso con botones */
.web-caja {
  width: min(640px, 92vw);
  margin: 12vh auto auto;
  padding: var(--e-3) var(--h-2);
  border: var(--borde);
  background: var(--bg);
  color: var(--fg);
  box-shadow: 0 8px 32px rgb(0 0 0 / 40%);

  &::backdrop { background: rgb(0 0 0 / 45%); }

  & h3 { margin: 0 0 var(--e-2); font-size: var(--t-normal); }
  & .ayuda { margin: 0 0 var(--e-2); color: var(--dim); white-space: pre-wrap; }

  & input {
    box-sizing: border-box;
    width: 100%;
    padding: .2lh 0;
    border: 0;
    border-bottom: 1px solid var(--azul);
    outline: none;
    background: transparent;
    color: var(--fg);
    font: inherit;
  }

  & .problema { min-height: 1lh; margin-top: .3lh; color: var(--rojo); }

  & .botones {
    display: flex;
    gap: var(--h-2);
    justify-content: flex-end;
    margin-top: .6lh;

    & a { color: var(--azul); cursor: pointer; }
    & a:focus-visible { outline: 1px solid var(--azul); outline-offset: 2px; }
  }
}

/* el men\xFA: un filtro arriba y las opciones, con la elegida marcada */
.web-lista { max-height: 50vh; margin-top: .4lh; overflow: auto; }

.web-op {
  display: flex;
  gap: var(--h-2);
  padding: 0 var(--h-1);
  cursor: pointer;

  & .d { color: var(--dim); }
  &.sel, &:hover { background: var(--sel); }
}

.web-sep { padding: .3lh var(--h-1) 0; color: var(--dim); font-size: var(--t-menor); }

/* en un celular, cada opci\xF3n en dos renglones: el nombre, y debajo para qu\xE9 sirve */
@media (width <= 700px) {
  .web-op { flex-direction: column; gap: 0; padding-block: .15lh; }
  .web-op .d { font-size: var(--t-chica); }
}

/* los avisos: abajo a la derecha, se van solos */
.web-avisos {
  position: fixed;
  z-index: 60;
  right: var(--h-2);
  bottom: var(--e-3);
  display: flex;
  flex-direction: column;
  gap: .3lh;
}

.web-aviso {
  max-width: 60ch;
  padding: .3lh 1.5ch;
  border: var(--borde);
  border-left: 3px solid var(--azul);
  background: var(--bg);
  box-shadow: 0 4px 16px rgb(0 0 0 / 35%);

  &.falla { border-left-color: var(--rojo); }
  &.aviso { border-left-color: var(--amarillo); }
}

/* la barra en el navegador: el \u22EF abre el men\xFA del hilo, que en VS Code es el contextual. En un
   celular no hay hover: el \u22EF se ve siempre, y lo dem\xE1s (\u23F8 \u2715) queda dentro del men\xFA */
.menu-web { display: inline; }

/* la barra sola en la pantalla (\`llena\`, la pone pagina.ts): un celular */
.llena .fila .iconos { position: static; display: flex; padding-left: 0; background: transparent; }
.llena .fila .iconos .icono:not(.menu-web) { display: none; }
.llena .fila .menu-web { padding-inline: 1ch; }

`;rr({ahora:or,base:ir,compartir:nr,conversacion:sr,dia:lr,documento:cr,ficha:dr,hilos:ur,plan:pr,proyectos:hr,terminal:fr,tokens:mr,web:at});var vr=at;var tt={};Yt(tt,{decode:()=>Oe,encode:()=>le,format:()=>Re,parse:()=>He});var gr={};function _n(e){let a=gr[e];if(a)return a;a=gr[e]=[];for(let t=0;t<128;t++){let r=String.fromCharCode(t);a.push(r)}for(let t=0;t<e.length;t++){let r=e.charCodeAt(t);a[r]="%"+("0"+r.toString(16).toUpperCase()).slice(-2)}return a}function ma(e,a){typeof a!="string"&&(a=ma.defaultChars);let t=_n(a);return e.replace(/(%[a-f0-9]{2})+/gi,function(r){let o="";for(let i=0,n=r.length;i<n;i+=3){let s=parseInt(r.slice(i+1,i+3),16);if(s<128){o+=t[s];continue}if((s&224)===192&&i+3<n){let l=parseInt(r.slice(i+4,i+6),16);if((l&192)===128){let c=s<<6&1984|l&63;c<128?o+="\uFFFD\uFFFD":o+=String.fromCharCode(c),i+=3;continue}}if((s&240)===224&&i+6<n){let l=parseInt(r.slice(i+4,i+6),16),c=parseInt(r.slice(i+7,i+9),16);if((l&192)===128&&(c&192)===128){let u=s<<12&61440|l<<6&4032|c&63;u<2048||u>=55296&&u<=57343?o+="\uFFFD\uFFFD\uFFFD":o+=String.fromCharCode(u),i+=6;continue}}if((s&248)===240&&i+9<n){let l=parseInt(r.slice(i+4,i+6),16),c=parseInt(r.slice(i+7,i+9),16),u=parseInt(r.slice(i+10,i+12),16);if((l&192)===128&&(c&192)===128&&(u&192)===128){let h=s<<18&1835008|l<<12&258048|c<<6&4032|u&63;h<65536||h>1114111?o+="\uFFFD\uFFFD\uFFFD\uFFFD":(h-=65536,o+=String.fromCharCode(55296+(h>>10),56320+(h&1023))),i+=9;continue}}o+="\uFFFD"}return o})}ma.defaultChars=";/?:@&=+$,#";ma.componentChars="";var Oe=ma;var br={};function Dn(e){let a=br[e];if(a)return a;a=br[e]=[];for(let t=0;t<128;t++){let r=String.fromCharCode(t);/^[0-9a-z]$/i.test(r)?a.push(r):a.push("%"+("0"+t.toString(16).toUpperCase()).slice(-2))}for(let t=0;t<e.length;t++)a[e.charCodeAt(t)]=e[t];return a}function va(e,a,t){typeof a!="string"&&(t=a,a=va.defaultChars),typeof t>"u"&&(t=!0);let r=Dn(a),o="";for(let i=0,n=e.length;i<n;i++){let s=e.charCodeAt(i);if(t&&s===37&&i+2<n&&/^[0-9a-f]{2}$/i.test(e.slice(i+1,i+3))){o+=e.slice(i,i+3),i+=2;continue}if(s<128){o+=r[s];continue}if(s>=55296&&s<=57343){if(s>=55296&&s<=56319&&i+1<n){let l=e.charCodeAt(i+1);if(l>=56320&&l<=57343){o+=encodeURIComponent(e[i]+e[i+1]),i++;continue}}o+="%EF%BF%BD";continue}o+=encodeURIComponent(e[i])}return o}va.defaultChars=";/?:@&=+$,-_.!~*'()#";va.componentChars="-_.!~*'()";var le=va;function Re(e){let a="";return a+=e.protocol||"",a+=e.slashes?"//":"",a+=e.auth?e.auth+"@":"",e.hostname&&e.hostname.indexOf(":")!==-1?a+="["+e.hostname+"]":a+=e.hostname||"",a+=e.port?":"+e.port:"",a+=e.pathname||"",a+=e.search||"",a+=e.hash||"",a}function ga(){this.protocol=null,this.slashes=null,this.auth=null,this.port=null,this.hostname=null,this.hash=null,this.search=null,this.pathname=null}var Rn=/^([a-z0-9.+-]+:)/i,An=/:[0-9]*$/,En=/^(\/\/?(?!\/)[^\?\s]*)(\?[^\s]*)?$/,Sn=["<",">",'"',"`"," ","\r",`
`,"	"],Pn=["{","}","|","\\","^","`"].concat(Sn),jn=["'"].concat(Pn),yr=["%","/","?",";","#"].concat(jn),wr=["/","?","#"],qn=255,xr=/^[+a-z0-9A-Z_-]{0,63}$/,Fn=/^([+a-z0-9A-Z_-]{0,63})(.*)$/,$r={javascript:!0,"javascript:":!0},kr={http:!0,https:!0,ftp:!0,gopher:!0,file:!0,"http:":!0,"https:":!0,"ftp:":!0,"gopher:":!0,"file:":!0};function Tn(e,a){if(e&&e instanceof ga)return e;let t=new ga;return t.parse(e,a),t}ga.prototype.parse=function(e,a){let t,r,o,i=e;if(i=i.trim(),!a&&e.split("#").length===1){let c=En.exec(i);if(c)return this.pathname=c[1],c[2]&&(this.search=c[2]),this}let n=Rn.exec(i);if(n&&(n=n[0],t=n.toLowerCase(),this.protocol=n,i=i.substr(n.length)),(a||n||i.match(/^\/\/[^@\/]+@[^@\/]+/))&&(o=i.substr(0,2)==="//",o&&!(n&&$r[n])&&(i=i.substr(2),this.slashes=!0)),!$r[n]&&(o||n&&!kr[n])){let c=-1;for(let m=0;m<wr.length;m++)r=i.indexOf(wr[m]),r!==-1&&(c===-1||r<c)&&(c=r);let u,h;c===-1?h=i.lastIndexOf("@"):h=i.lastIndexOf("@",c),h!==-1&&(u=i.slice(0,h),i=i.slice(h+1),this.auth=u),c=-1;for(let m=0;m<yr.length;m++)r=i.indexOf(yr[m]),r!==-1&&(c===-1||r<c)&&(c=r);c===-1&&(c=i.length),i[c-1]===":"&&c--;let p=i.slice(0,c);i=i.slice(c),this.parseHost(p),this.hostname=this.hostname||"";let f=this.hostname[0]==="["&&this.hostname[this.hostname.length-1]==="]";if(!f){let m=this.hostname.split(/\./);for(let b=0,w=m.length;b<w;b++){let k=m[b];if(k&&!k.match(xr)){let C="";for(let v=0,y=k.length;v<y;v++)k.charCodeAt(v)>127?C+="x":C+=k[v];if(!C.match(xr)){let v=m.slice(0,b),y=m.slice(b+1),$=k.match(Fn);$&&(v.push($[1]),y.unshift($[2])),y.length&&(i=y.join(".")+i),this.hostname=v.join(".");break}}}}this.hostname.length>qn&&(this.hostname=""),f&&(this.hostname=this.hostname.substr(1,this.hostname.length-2))}let s=i.indexOf("#");s!==-1&&(this.hash=i.substr(s),i=i.slice(0,s));let l=i.indexOf("?");return l!==-1&&(this.search=i.substr(l),i=i.slice(0,l)),i&&(this.pathname=i),kr[t]&&this.hostname&&!this.pathname&&(this.pathname=""),this};ga.prototype.parseHost=function(e){let a=An.exec(e);a&&(a=a[0],a!==":"&&(this.port=a.substr(1)),e=e.substr(0,e.length-a.length)),e&&(this.hostname=e)};var He=Tn;var st={};Yt(st,{Any:()=>rt,Cc:()=>ot,Cf:()=>zn,P:()=>Ue,S:()=>it,Z:()=>nt});var rt=/[\0-\uD7FF\uE000-\uFFFF]|[\uD800-\uDBFF][\uDC00-\uDFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF]/,ot=/[\0-\x1F\x7F-\x9F]/,zn=/[\xAD\u0600-\u0605\u061C\u06DD\u070F\u0890\u0891\u08E2\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF\uFFF9-\uFFFB]|\uD804[\uDCBD\uDCCD]|\uD80D[\uDC30-\uDC3F]|\uD82F[\uDCA0-\uDCA3]|\uD834[\uDD73-\uDD7A]|\uDB40[\uDC01\uDC20-\uDC7F]/,Ue=/[!-#%-\*,-\/:;\?@\[-\]_\{\}\xA1\xA7\xAB\xB6\xB7\xBB\xBF\u037E\u0387\u055A-\u055F\u0589\u058A\u05BE\u05C0\u05C3\u05C6\u05F3\u05F4\u0609\u060A\u060C\u060D\u061B\u061D-\u061F\u066A-\u066D\u06D4\u0700-\u070D\u07F7-\u07F9\u0830-\u083E\u085E\u0964\u0965\u0970\u09FD\u0A76\u0AF0\u0C77\u0C84\u0DF4\u0E4F\u0E5A\u0E5B\u0F04-\u0F12\u0F14\u0F3A-\u0F3D\u0F85\u0FD0-\u0FD4\u0FD9\u0FDA\u104A-\u104F\u10FB\u1360-\u1368\u1400\u166E\u169B\u169C\u16EB-\u16ED\u1735\u1736\u17D4-\u17D6\u17D8-\u17DA\u1800-\u180A\u1944\u1945\u1A1E\u1A1F\u1AA0-\u1AA6\u1AA8-\u1AAD\u1B4E\u1B4F\u1B5A-\u1B60\u1B7D-\u1B7F\u1BFC-\u1BFF\u1C3B-\u1C3F\u1C7E\u1C7F\u1CC0-\u1CC7\u1CD3\u2010-\u2027\u2030-\u2043\u2045-\u2051\u2053-\u205E\u207D\u207E\u208D\u208E\u2308-\u230B\u2329\u232A\u2768-\u2775\u27C5\u27C6\u27E6-\u27EF\u2983-\u2998\u29D8-\u29DB\u29FC\u29FD\u2CF9-\u2CFC\u2CFE\u2CFF\u2D70\u2E00-\u2E2E\u2E30-\u2E4F\u2E52-\u2E5D\u3001-\u3003\u3008-\u3011\u3014-\u301F\u3030\u303D\u30A0\u30FB\uA4FE\uA4FF\uA60D-\uA60F\uA673\uA67E\uA6F2-\uA6F7\uA874-\uA877\uA8CE\uA8CF\uA8F8-\uA8FA\uA8FC\uA92E\uA92F\uA95F\uA9C1-\uA9CD\uA9DE\uA9DF\uAA5C-\uAA5F\uAADE\uAADF\uAAF0\uAAF1\uABEB\uFD3E\uFD3F\uFE10-\uFE19\uFE30-\uFE52\uFE54-\uFE61\uFE63\uFE68\uFE6A\uFE6B\uFF01-\uFF03\uFF05-\uFF0A\uFF0C-\uFF0F\uFF1A\uFF1B\uFF1F\uFF20\uFF3B-\uFF3D\uFF3F\uFF5B\uFF5D\uFF5F-\uFF65]|\uD800[\uDD00-\uDD02\uDF9F\uDFD0]|\uD801\uDD6F|\uD802[\uDC57\uDD1F\uDD3F\uDE50-\uDE58\uDE7F\uDEF0-\uDEF6\uDF39-\uDF3F\uDF99-\uDF9C]|\uD803[\uDD6E\uDEAD\uDED0\uDF55-\uDF59\uDF86-\uDF89]|\uD804[\uDC47-\uDC4D\uDCBB\uDCBC\uDCBE-\uDCC1\uDD40-\uDD43\uDD74\uDD75\uDDC5-\uDDC8\uDDCD\uDDDB\uDDDD-\uDDDF\uDE38-\uDE3D\uDEA9\uDFD4\uDFD5\uDFD7\uDFD8]|\uD805[\uDC4B-\uDC4F\uDC5A\uDC5B\uDC5D\uDCC6\uDDC1-\uDDD7\uDE41-\uDE43\uDE60-\uDE6C\uDEB9\uDF3C-\uDF3E]|\uD806[\uDC3B\uDD44-\uDD46\uDDE2\uDE3F-\uDE46\uDE9A-\uDE9C\uDE9E-\uDEA2\uDF00-\uDF09\uDFE1]|\uD807[\uDC41-\uDC45\uDC70\uDC71\uDEF7\uDEF8\uDF43-\uDF4F\uDFFF]|\uD809[\uDC70-\uDC74]|\uD80B[\uDFF1\uDFF2]|\uD81A[\uDE6E\uDE6F\uDEF5\uDF37-\uDF3B\uDF44]|\uD81B[\uDD6D-\uDD6F\uDE97-\uDE9A\uDFE2]|\uD82F\uDC9F|\uD836[\uDE87-\uDE8B]|\uD839\uDDFF|\uD83A[\uDD5E\uDD5F]/,it=/[\$\+<->\^`\|~\xA2-\xA6\xA8\xA9\xAC\xAE-\xB1\xB4\xB8\xD7\xF7\u02C2-\u02C5\u02D2-\u02DF\u02E5-\u02EB\u02ED\u02EF-\u02FF\u0375\u0384\u0385\u03F6\u0482\u058D-\u058F\u0606-\u0608\u060B\u060E\u060F\u06DE\u06E9\u06FD\u06FE\u07F6\u07FE\u07FF\u0888\u09F2\u09F3\u09FA\u09FB\u0AF1\u0B70\u0BF3-\u0BFA\u0C7F\u0D4F\u0D79\u0E3F\u0F01-\u0F03\u0F13\u0F15-\u0F17\u0F1A-\u0F1F\u0F34\u0F36\u0F38\u0FBE-\u0FC5\u0FC7-\u0FCC\u0FCE\u0FCF\u0FD5-\u0FD8\u109E\u109F\u1390-\u1399\u166D\u17DB\u1940\u19DE-\u19FF\u1B61-\u1B6A\u1B74-\u1B7C\u1FBD\u1FBF-\u1FC1\u1FCD-\u1FCF\u1FDD-\u1FDF\u1FED-\u1FEF\u1FFD\u1FFE\u2044\u2052\u207A-\u207C\u208A-\u208C\u20A0-\u20C1\u2100\u2101\u2103-\u2106\u2108\u2109\u2114\u2116-\u2118\u211E-\u2123\u2125\u2127\u2129\u212E\u213A\u213B\u2140-\u2144\u214A-\u214D\u214F\u218A\u218B\u2190-\u2307\u230C-\u2328\u232B-\u2429\u2440-\u244A\u249C-\u24E9\u2500-\u2767\u2794-\u27C4\u27C7-\u27E5\u27F0-\u2982\u2999-\u29D7\u29DC-\u29FB\u29FE-\u2B73\u2B76-\u2BFF\u2CE5-\u2CEA\u2E50\u2E51\u2E80-\u2E99\u2E9B-\u2EF3\u2F00-\u2FD5\u2FF0-\u2FFF\u3004\u3012\u3013\u3020\u3036\u3037\u303E\u303F\u309B\u309C\u3190\u3191\u3196-\u319F\u31C0-\u31E5\u31EF\u3200-\u321E\u322A-\u3247\u3250\u3260-\u327F\u328A-\u32B0\u32C0-\u33FF\u4DC0-\u4DFF\uA490-\uA4C6\uA700-\uA716\uA720\uA721\uA789\uA78A\uA828-\uA82B\uA836-\uA839\uAA77-\uAA79\uAB5B\uAB6A\uAB6B\uFB29\uFBB2-\uFBD2\uFD40-\uFD4F\uFD90\uFD91\uFDC8-\uFDCF\uFDFC-\uFDFF\uFE62\uFE64-\uFE66\uFE69\uFF04\uFF0B\uFF1C-\uFF1E\uFF3E\uFF40\uFF5C\uFF5E\uFFE0-\uFFE6\uFFE8-\uFFEE\uFFFC\uFFFD]|\uD800[\uDD37-\uDD3F\uDD79-\uDD89\uDD8C-\uDD8E\uDD90-\uDD9C\uDDA0\uDDD0-\uDDFC]|\uD802[\uDC77\uDC78\uDEC8]|\uD803[\uDD8E\uDD8F\uDED1-\uDED8]|\uD805\uDF3F|\uD807[\uDFD5-\uDFF1]|\uD81A[\uDF3C-\uDF3F\uDF45]|\uD82F\uDC9C|\uD833[\uDC00-\uDCEF\uDCFA-\uDCFC\uDD00-\uDEB3\uDEBA-\uDED0\uDEE0-\uDEF0\uDF50-\uDFC3]|\uD834[\uDC00-\uDCF5\uDD00-\uDD26\uDD29-\uDD64\uDD6A-\uDD6C\uDD83\uDD84\uDD8C-\uDDA9\uDDAE-\uDDEA\uDE00-\uDE41\uDE45\uDF00-\uDF56]|\uD835[\uDEC1\uDEDB\uDEFB\uDF15\uDF35\uDF4F\uDF6F\uDF89\uDFA9\uDFC3]|\uD836[\uDC00-\uDDFF\uDE37-\uDE3A\uDE6D-\uDE74\uDE76-\uDE83\uDE85\uDE86]|\uD838[\uDD4F\uDEFF]|\uD83B[\uDCAC\uDCB0\uDD2E\uDEF0\uDEF1]|\uD83C[\uDC00-\uDC2B\uDC30-\uDC93\uDCA0-\uDCAE\uDCB1-\uDCBF\uDCC1-\uDCCF\uDCD1-\uDCF5\uDD0D-\uDDAD\uDDE6-\uDE02\uDE10-\uDE3B\uDE40-\uDE48\uDE50\uDE51\uDE60-\uDE65\uDF00-\uDFFF]|\uD83D[\uDC00-\uDED8\uDEDC-\uDEEC\uDEF0-\uDEFC\uDF00-\uDFD9\uDFE0-\uDFEB\uDFF0]|\uD83E[\uDC00-\uDC0B\uDC10-\uDC47\uDC50-\uDC59\uDC60-\uDC87\uDC90-\uDCAD\uDCB0-\uDCBB\uDCC0\uDCC1\uDCD0-\uDCD8\uDD00-\uDE57\uDE60-\uDE6D\uDE70-\uDE7C\uDE80-\uDE8A\uDE8E-\uDEC6\uDEC8\uDECD-\uDEDC\uDEDF-\uDEEA\uDEEF-\uDEF8\uDF00-\uDF92\uDF94-\uDFEF\uDFFA]/,nt=/[ \xA0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]/;var Mn=[8364,0,8218,402,8222,8230,8224,8225,710,8240,352,8249,338,0,381,0,0,8216,8217,8220,8221,8226,8211,8212,732,8482,353,8250,339,0,382,376];function Jn(e){return e===0||e>=55296&&e<=57343||e>1114111}function Cr(e){return Jn(e)?65533:e>=128&&e<=159&&Mn[e-128]||e}function _r(e){return e-1>>>0<127||e-160>>>0<55136?String.fromCharCode(e):String.fromCodePoint(Cr(e))}var K=(()=>{let e=new Uint8Array(127),a=0;for(let t=33;t<=126;t++)t!==34&&t!==36&&t!==92&&(e[t]=a++);return e})();function Dr(e,a,t,r,o,i){let s=e.length,l=i*90,c=0,u=()=>{let E=K[e.charCodeAt(c++)];return E<i?E:E*91-l+K[e.charCodeAt(c++)]},h=t-r,p=t+o,f=new Int32Array(p);f.fill(-1,r,i),f.fill(-1,i+h,p);let m=new Int32Array(p),b=new Int32Array(p);function w(E,F){let R=0,N=F,Y=F+E;for(;N<Y;){let X=K[e.charCodeAt(c++)];if(X<89)R+=X,f[N++]=R;else if(X===89){let W=K[e.charCodeAt(c++)]+2;for(;W--;)f[N++]=++R}else{let W=K[e.charCodeAt(c++)];R+=89+(W<90?W*91+K[e.charCodeAt(c++)]:K[e.charCodeAt(c++)]*8281+K[e.charCodeAt(c++)]*91+K[e.charCodeAt(c++)]),f[N++]=R}}}w(r,0),w(h,i);let k=new Int32Array(o*2),C=0,v=0;function y(E,F){for(let R=0;R<E;R++){let N=F+R,Y=u(),X=u();k[v*2]=Y,k[v*2+1]=X,v+=1,m[N]=C;let W=(f[Y]<0?b[Y]:1)+(f[X]<0?b[X]:1);b[N]=W,C+=W}}y(o-i+r,i+h),y(i-r,r);let $=new Uint16Array(C),_=0;for(let E=0;E<v;E++)for(let F=0;F<2;F++){let R=k[E*2+F],N=f[R];if(N<0){let Y=m[R],X=Y+b[R];for(;Y<X;)$[_++]=$[Y++]}else $[_++]=N}let A=new Uint16Array(a),j=0;for(;c<s;){let E=K[e.charCodeAt(c++)];E>=i&&(E=E*91-l+K[e.charCodeAt(c++)]);let F=f[E];if(F<0){let R=m[E],N=R+b[E];for(;R<N;)A[j++]=$[R++]}else A[j++]=F}return A}var Rr=Dr("!}.&u%}'&}*'~!6*)%&,~!J~!J~%L~y<~!R,~~%Lu~~#GD~~#|)1#%}^%}2%+#.##%##%}&%##%'#%##&%#%#'%#&#%#&#'#%%#&#%##%#)%''%&%#%#'%#%%#%%}%%%#%#&(23#%%#&-%0%('1#(##%#'##+%'*.:1}#%#6-+(%'%%#%%%}#L'2351&('%}&/N'(0(/*-%(%%}#'+&T%7.2}#&%&#%#36/5##%&%%#&#%%#))2%%##%&&'0~!#*+&'%1~!%).'3q?&%'1~!.##%6(~!+%%%(Gw'rT~!E#<nA%#jZ~!H%(~!42##~!*31&~!G%U~#)5~#`3~!J~!Z~%]~%Y~%C~!q~!u~#kz~%#~!6'~!D~!U~!?~#T~!c%~!G#'~%7|~!G~!J~!G&~#pb~(Df}#%}*&}#%##%##%##&#-}&'#'&%#.++}%mI,#,@&(}*%}*'%&##&#%##%}&0}#.},U},%}+%}&%}#%##&}B%(}(%}+%)})%##%#&}&%##%&}<%}>%#%&}*%}(%}9%}/%})%}*%}*%}?&}&%}3%}&*#%})%#%#)}#&#-#+*%E%%'%'#%}#*V##&##I}#&&##%&%#&&Qf%%))w/0+&%#(#.%-''''++++7}>%4'',##1,#%#&%##&#'##&#*#9)%&%}#*}%,#+P(%A&%#'&##wSD',9E00#y#@}(+}&%&>~!#~!X}#*}(&&}(&}(,%}%&#+&}#&}I%#%}%)#(},'%#*}4%%#%}(''}#/##(##),%-##%%)#&}(.}&%#&}%%}*&#%},&&}&%}#%*'#%})%}D&}&%}-&}6&#&}-,%}#%})-(~+`~,=?~I9'9%~!,#%})%})%}@%}?%}(~!?~#<~#pP~#BG~#=1#%K+~#?#~%;)~#A~#mF1~#A'~'X%'~#lR~#N~'N~#r~#m#-~#i'?%#'%~#B%##%,%#~#_%#0%~#]732~,w~2+#:&#%&'0%&>%}#>##F+)#%&&#(+_}4&}-%}(&}@&}O7Fdf0@+/v4}&WU##&/0#&'('B#%}.%}'+#%}#%%&#&%#%##+#&#)#6#'#.},%}c%},%#%##%&#&%#&~#>'*-.%##%##%}#%%}%'~#)D1}#%*&~#_%%'(~#S2%'.}#~#=##*'*-%}&'%'##&&~'E%.#&~#M4}%%##&'%#~#O1##%&#'+~#<B%##%%'%+~#;#@%}#&%#&&%#(~#H1}'%'##&&~#?A}&'~#D#%32}'&&&&~#[}'(#%}'~#;C})&}%%#%~#=&%,3}%'(#%%~#^'#&&)#%'~#Y%-~#d-%'~#^%%&#&&&}#~#b~2t*&'~&(~&@~0%~e~3}%*''0})&}+~!9##-}#%-hD*)1fC#%/&/fB#40~!+#)*4~!+~!K'&:~!/*7~!.#~!H~!L':~%x&~!H#~!*~%1~!I#~!+A~#p'~!F~~#-#~,,(~.Z~!V~%;'B'mq-W~!N~%I%#&&#&}#%},%%}'%}+X#%}#&}(%}'%}<%}#%}%%'}'%}:~![)9@~%>~#UA%-%##&~!C%~!-.9:~!1~!-^2/:a~!y,D*J#-5)/4~%23,~#G~!L1~!0X3`~!2+~!!0-~&E~!W~!o,>Y&]~%cZx_&~#O*9#A#'#+I'%#)~!0B*-5A+-((F&*M#)(-7-5+'-3a5Vi~!Y~!?+[)%3),ERHm~!+:D,VG.+)?fB%%*(%)'(#&80%1'8`K8?`+'Z#&O&'H5#*9)A%%5&3))0%39+.*7#()&&*=4@**L)<'_&*+..;(#*+)./&0#3)%')-8(4ixD(&.}%,('aI:,)%,k2231T)I'#/-W7,/'Q#.'Y24+h')37</31&83##&0#),H(?'&?/1##%#&&#%''-%&&&#(&''&#.-'%#%%(,')*'&#&#'##%(%(#%('#&##%%%%('%#%#%%#%#&%##h>w+v<ayvyvcg.uuhKr}g/v|g>u9i[~>g5uI~=RvdwEg;v/g;uk!!TTSx]@RT!U!#!@VBRUU!'UTe-d0c`e&gSdicedFcrdTaqb.kYcAohdYd@a3e+d}dMdtd.aJ#bqcK`dle/e.e'dwdPdodddjbEb}ogd^ofdpduc6j?l%d{drdqc)d7bacOdQ%T#Y)X.sR[yH>6Vyv3[xwLu>vo'!*.[yBacahoj>6Rew3[xqdZa#!a&#^(X-[yG>6Vyu3[xvg3sEr|g.u/Ri9db0T#^(Xa)!-[y;>6Vylg4wKs{JwNZt3@3r=c4Z([xlg;wKt!cpq's@v7A'*a(a+!-a#[y<3Dt?3Dt'>6Vym3[xmg9rxsNJwLZt4~?r?db1T#`-!(Xa,!0[yS>6Vz%NuQs.g4wKtnJwNZtS@3r>c4Z([y%g;wKtrdga8!a(!#&T*Y-Xa#!a0<or[yc3Dtq>6Vz43[y3JwNZtf@3s!Ju}!%Dti:pm3c_%X#tjB5pkd6q!r]u?voC'*-a.a2!0a&a+[yI3DtI3Ds~3DtH>6Vyw3[xx;:s#~<5pKJwNZtE@3r~d`a)!a2T#a.(!+U.X1[yT3Dt`3Dtv>6Vz&3[y&g9rxwzcxstPu.<rAJwLZtT~?r@dZa%!a.&^*Za(/Reu[ya>6Vz23[y1g3sEr}wkg{NuQRg{ci(U#5@b`~,cg#U(2WnH5wugcRh7dX#T(Y,a'Ta!!a,[yZ<]mj>6Vz,3[y+Pv#5ReZKu+=,%!H}7ABwkaS?Rh:BcW(X#<]mrj:ubv/ARekdg%!(!a.*Ta(Y.X1!#sP>Rl*Dt6[y>>6Vyo3Wf*jOvuumvuRgRJuq*!:9<B@bX~3jVv&v@s@5Re[d/rQt{uAvo&a&a*)a2!,0Wf!3Dt0=Bs'>6Re}3[xy~<5s%JwJZt1~Gs)c;&!#2sJkNuXvzq7rxu,Re8dka4!a8(aEZ+a@Y.X1Xa)[yd=Bs(3DtP>6Vz53[y4cX#X&Re:avRe9~<5s&JwJZtQ~Gs*i^rzvdRg+Jv{%!2sbB@bX}kdga,!Za?&^*T1/!a'Dt+[y6>6Vyf3Wf%g/u;s4hGu6?Rh-JvZ,!c%#&RoX54Rivj7uyvf8RgTKvZB%*!2sGh<vu5Rgq<=C::9bb~#dZ#T&Ta6Y.X*Dt>[y93Wf)coZ(T,6VyifluvRgC@95@B@bX~/hFu34cC#T,k/unq8w8Q5RkUklwQuzunq8w8Q5Rk8d/rJu?v8w9)-&!a0a;a&aIWejg3sEr/h1s<DtDJvyZqY5aws3Jvy!&Wei~Hr1:au5@Bag>23E~5c:Z&bX};kKv?w&unuVu5Rjc;>bs)#~@:Rh.=ay<a]C;b`}Vd6s/t{uAvoaxa()!a,a7%-a#a2Dt,[yF2Wo[>6Vyt3[xuNuPRi&NuPwpi#RoWh?vf8Ri%Jv]!%Ri:KvxD!.'2WeAjZu`q9rxu,Re7woeAg-unLq(qA_/*2Wg_g3u5q^9:4E}/jTrxrzv=Wkkd~0UX#^^Xa-a1a5T&a=U1a'*aEa]!a*aPaA-adok[y54Rn>;:p3~Dp5g9rpsFNvZqjg3uJp4~<5p0Pw;5qlJwNZt*@3p1Pw:5p/Ou!5p2JvG'!6Vye=<qnJvh_[xhg3v,Rh3kOwOw-sDuev/Re^dha[a%!%!a+#Ta7)-5TaCaO!aka!a)sf[yb2>Rl!9ARiq5E}Qg=ucRkBE|oJrJ_@Wk~@Wk{JrJ_@Wk|@WkyJrJ_@Wk}@WkzJvO_[y2g-vMRmiKuYC!)&>Ri;>Ri<@3RkNc](X#@9Rk=g5vuRmhKvDB!+'=]meg3u4Rmgd)#Y'Vz3CARmfd`a+!%T'!+#Ta1Ta6TaM-sTDt9[yA9sYd'%Y#s[[xpj:ueunaXRgEjRq,v-vuqdd2'`#6Rev<32@5>:2<E}5xIo9a*X#Y(;5RePJvD_g>vyRgNj8w)v8<wggs:RgXiZt|vjx,hSq3ah!-(~@:Ro/Ou!5RhWj^v(pyw8unRhUdx-UY#^Ua.a3a70!)%UX1TaDa)'omRiRRhE[y:3Dsz=Br,>6Vyj3[xkg6ruwjcqsrPw;5r*Ku]D'Zt-@3r(~?r.i[vwv]dU1a--U#`a4(g/vsRhPOu!5RhLj:rmu9Wo!~@:wdh@g/vsRiTjXuvvNr}:RhBj^v(pyw8unRn]dz1UYa'a+^Y(!aETZalaRY.Ta?a4[yDJw1!#qLsW>6Vyrfzq-pLflpwRe|Js>%!Dt@3Dt&Jvy_[xs~HrnjMuwpsw'RecKu+D#'!t<~Grl~?rjg5u-x,gwp{ah!-(~@:Rg~Ou!5Rh'jXuvvNr}:Rh#cW#X/c;&!#2sLi[v7u7RgpJv)(!iLrxu,Re6j7v@s@5Se[e7d`aW!Za(a`T.a#!a3!&aDa-!9)Dt_=6s+3[x~~DR|h~DS6avhGun5RkZj3w)v-]mkKunB!&*]kb97R|i<ARk<c:Z(6Vy}Juh'!wziMRoS:F|vkLuauJv5vtvQRh1d='T+Y#VyO~DR|jcF#T'7R|g97R|kJv3'!ay<Rj,Jvh&!:ReXcsa6*a+#a#_aIRf9aLRf?c,Z&Rf5Rf7c.Z&Rf;Rf>cQ#%T'p-Rf8Rf=ct#%'(*!,p,Rf4p+Rf6Rf:Rf<d~'Ua%U*^UYa(!a,-!#a4YaTalaEX0a8a<Weo3Dt/3Dsx=Br93Wen~Dr;~<5p<JwNZt2@3p=Pw:5p;Ou!5r3c7&!#:p>3Ds}KvGB)_6Vyk2sM=<r7x'eovA(!hFu1ARf}cV#X&@r5j6rvwQa^Rf3c=Za'wkghJv__g;unRggA53B9=b^}%j6uduo5Jq;!(hIv%2Re`Ou4ARe_e%a#^^^Xa&!a*a2!&a6YaP!*ad!#a:aE/5Rn?[y@>6Vyp;:pE~DrY~<5pBJwNZt8@3pCh=rt3rWPw:5pAJup_[xoNuPpF9c!#'45pD5ARn)d8#X'X*3@rU72s]h>v<<sSjJpqvewOJq/(!hNw'5ReBk0s2u3w/w'5ReE5@Jq.!a+JQ!&WeU23d(#Y&RjG5]jBk!u7w&u0udARjEe#+^^^Ub#!a2/a`Z(agT1!a-a;|@TaG!aS[yV=Re~fow'RguNuPRe?bz#'>RoUWeL>:Cbb|?JwPZtVg6ruRmzJvD'!6Vz(g/vmRh~Jvy_[y(g9voRgyx*cy(#2>Ri2B9b]~9kIw9u7rluJu3Rg]dI#a%UY'@=p%CAx.gQZ&RhwwygtRm{x5g_Z'+ABqR9Woa=Bp&dV#^*Xa'!&@o{g4v]Rk;Jv{!%Rk[wkkiA5RkiwwfUB=x,fUuqC&*!>RfTg8v0RfV~ARfSd;rJsAuAv9wR'ae+/aO!a@aza/a#[yQ@Wg!2Wemg3sEr0JvB_g>uvReWg2v+Re=KupB_+[y!2AbY~-~Hr2AJwD!(h<~El>h<~El?Kun@+_:9b`}Kg-v/Ri3g;vtwyk_9]k_d=&T#*U.6qh@Ab`|K9:H|CJv[!&3Dtex'fDwC%!Rf[9WlMd[(^X,!a%Z06Vz!@WgBg=v~Rgvg,QRe@awd,#Y+jTv|Q~EfWj]uNr|~FRfXdy#Y&^Ua%!aO.!(a)Ua;=!a@aKap!a-,a!Ta]a[rSa]p?[y82sK=Bq~;:p:~<5p8Pw:5p7d'#Y'Wf(;RnRi[u4w&RgJJvG'!6Vyh=<r#ijuuv/sIKuYD'ZtG@3p9~Gr&d2#`(g<vtRgFj`u5w&rqpxRf2CJuY!+:wfnTOu!5Rg}jNs1ucv&RfwJvA!&3@q|BDcC#T,k/unq8w8Q5RkTklwQuzunq8w8Q5Rk9dga#!a'!a=#a0!:+Tb*b@aO.a4!aba8aFJv^}?!VyR~Dr<g;u%Rn.~<5p[x'e`wNZtR@3p]Pw:5pZhNvjBp.woe_g5u-r4JwF!%DtO3:ooc7&!#:p^3DtpLuGw(!+%)Dtk6Vz#2sd=<r8d'#Y([y#<x3gJt`w@!)%}MRiowzikRij=]ilxAf3,U(#B2Rf#g0v-Rm[ck{`U#]giKv3>)!&6Ri154s,KuGB_%@r68r:dJ|t`#X(9<E|u2@H|rx3gJu?w'!+'1Nu7Reg4=H~+9<wxgY95Rm]xLggZ-`(X}U2:Ri4h<uOawRmsJv__5@bb{jbV~3dka#a'a]!,#a+U=a>b6a3b%!/aKa/)!arwve^VyJ;:pR~DpTg3uJpS~<5pOPw;5qmPw:5pNOu!5pQJvG'!6Vyx=<qoJvA!{~Jup!%@qk7Rn/KvyD!}''[xz;>wkh'?Rh,x8gyt`w5D!&),(SgyccRgztJ@3pPB5p#d'(Y#<]mmifubw&RgoJvE&!82s^JvF&!8Rf,ADb]~;x=h'rNu]vK!,%'*0RnORh)4Rh*AqQg-vaRnNg;wHwkh'ba~4cE#Ta*x3gctyw@'!+%RnFRnD<4Rn@hFvK5RnCxWg[#`&a0Ua()`1Rm75Rg[c]%X#qi8Rg^NvdRj>BwzgZauwji7Rm6A4wgg]d1#&(*,.0a#Rm;Rm<Rm=Rm>Rm?Rm@RmARmBe%#^^^Xaea?aC/b+(,!a+a#!a/!>a&Ta<aKbD!2wphBRnk[yPw}hE|.=Br-3Dtm>6Vy~g6urRf.x,hPrNav!%'RnqRo%Ro#Nu;q[Pw;5r+JwNZtM@3r)d'#Y'Weh;xChL#`&RnmRnoKu}>%(!Rne~Bs-;2wjcussJv+'!aYSO}6@B<5?ba~8LrNvj!.%*ROwungw~ng~:9;Ri^>wtnig;wHRnixDh@|(UZ.x1h@|)!#:2<H|*xHn]#-UX'3Ro)z=iT}6ARns=Bwsn_wpnaRncw]aR(#UXa&Ua*a/=]iPd'#Y&Ro'WnXf{QRm2hNvj]nZd`'T~&1`{|`#9b]{}c:'!#Wl{>@=be}]?cl{{U#:5Abb}Jds#^YaF!a*b4a#a3aPa>&Tb!bH!*a_!Eau?/a&RjY<]gj>6Vz*;:pe~DrZg,QRj1JwNZtX@wihspcJvZ&!VyX9WmOJu|!|N2WmHJvh&!]ht~Bpbcn&T(!#RmQ<s7Nu;padH#X'`+WmJ@>RmKCARhnKup=!)&Wf+:RhqNuPpf9c!#'45pd5AwghpARn(Ls@w!%,)!RmP@Wfe<E|IJva!&WmNg8vsRmLd`*.`#Y'Xa!axRn*]hrA8Rhug5s@rXg8u!RmMd8#X'X*3@rV72smdI*#UY&RmICARho~GsgxVgd)Ta'U-Y&Xa!T#RnEWnA@Wffg1uDRi0hFvK5RnBxGnG&#`%owp)@wsf+bX}Ze-*1!a*^^^Ua|!#a.aq&Ya2!a>.a6!a:aO`aJDtL[y`@Wg#>6Vz12@wzoYRoZNuPRi!NuPRhzg=ucRi,@=b`{Yg=ucRi-ACJvB!&Sh[ebSh]ebi`wUuFRm4Jw2_[y0JvB!.<Ju(!&SoG}6Shd}6<Ju(!&SoH}6She}6Kur@._g5vHRieJvx!{L2G{Kx6gd'T#?Rh82Wi5cZ#X(g1w)Rm5dW-Y(Ta#!a)!#aYa=wnfE=su2>>bU{0j9udv:<svj8uQv-7RgHdE%#^'sq9sp=>Bb_{TJv`!&g/r|snj6v(us5d,#Y(56H}[978H}]Jw5!&g1rushJvB!+j;v{u5?zDhd}6}bj;v{u5?zDhe}6}ce*#`(^^^a[aea!=!a6a*aoXb1a.!aAbL!b>,b'aL!aV@Wf|2Wlg3[y/JwNZt^@3piPw:5pgJunZou3@rsJva&!Vy_g<v~Rm#JvG'!6Vz0=<r{Ju{%!:pj@WfsiXuJu3Rm:JvZ&!WfA~Bph@c4Z&Dtwax5rubx(#:awRk1@d,#Y&RfjRfid1#,Y(@Wfp2Wlrg5s@ryKu[@!,'=]ig9wlk?Rk>g5u-rqJvy'!@9RkQcH(T#=>Ri~@<wkj(Wj(KuZB*!&<7rw@9RkRcH(T#=>Ri}@<wkj)Wj)dg(Ta2Xa9X#`-!a*CARhg@@=I}d9x;c~#X%so=<sj>2@@=aybb}XjWv0Q~EfEj3vLv;<d,#Y(56H}`978H}_dgaPaFa'a/!#a3Y0a_a;a|!1(a7-[yE3[xt;:pJNvZrrg3uJrvJwNZt=@3pIh=rt3rxPw:5pGOu!5rpJvG'!6Vys=<rz@c4Z&Dt(ax5rtJvZ!&~BpH@wsfNg-vaRlNci*U#=<wei<F}a5@Jq.!a*JQ!%@qZ23d(#Y&RjH5]jCk!u7w&u0udARjFd/prq=tyvpaEa(a:.!a1aZ(@@=I}:9wpd%=<sX55w_h}@@=I{t=ay<aU@@=I}T=ay<2@@=I})?C9:9au@9Cb]}DP~=x-fAZ(2Wl1=ay<aU@@=I}>5@d##Y+jTv|vV~EfFj]uNpn~FRfGdgaK!Z2&!a8a-Tb({E!acTbM*!a(DtY[yYd'%Y#sl[y*hHvh>Re5x2c{Z}.j4uCvcawRiMd+#X+_x&d!},<5RkX;2Hzw@x,gavfB-!{CcF&T#Roe;RodwWbBg5urRgaKvHC*_6Vz+<4opieuew&Rmq@d]&Y)X,T#X0Rh}<BqP=4qS9:ReMg/ujReNJw0!/<Jui%!bd{kawwnemRelAxUa?a3#*.&UX(Ya+a/RhvRnQ<o}9Wmtd-#Y&RgSRmw9;Rmxay=Rmyg-vaRmuxEhSrNu,v-voC!%(aR.a(a7+1Ro1>Ro5CE{A9b]{@;5x#eO{:g;urRi+KrNA!%(Ro3>Ro79;Ri_Ku@>{;&!x%gX|{KunA_+g5QRj/g3u5Rj#g>uERj%wio/xRhS&!,!#^1U}wba{8>>@=be}qC@:D5ba{7Ku+A&!}x?ba}t>>@=be}se(aA^^^Uat!b0#{pa+awUazbGa#aLb9bgaWac'a5TbS=Br!d1#`%scp_Jvl!#rT>Re0JvX&!VyN=H{Fcm#U&:pY=ReaJv2&!]h0=]nUJvG'!6Vy|=<r%JrM_=]h2@Wlud'#)U'Wf'b]{i=]h/Jvh!&~BpWg=v]RnMx+ny#'Nu;pVwjnu=]nwxJnx,T#`&Reqwjnt=]nvieu9vrRjLLuYwP(#+!th@wih5pX~Gr'g5v/Rh4KunA'!-CARnP@wwiN:Rm_9x'cvw>!|l=<saKvAA!0&3@q}>w^e1bp#&Re2Re3BDx7gH#T|f5H|eKuZ>!%(:qNAH{]Jv6!+3B2B9=b^{X<5<B92:E{ZLvhwA(a;a%!igQuyRmad+#Y}m@3Rh5d8#X'X*:AqUAHzmaxwbh<aXRnVcF}RT#Nw&cj#U(BWnug/vsRntdka)(a3+.Zb7aYYan1!bVa@Xa}[y^@b[{G=H{+hFu73Rj&Pv#5ReQcK%T#sig1v{Rj'Ku+D#'!t]~Grm~?rkKuMB!01d5#`'Vy.ta3Dtu~Hroc8#'{^45s85AwZbP&!#Rn!wghxWn#KvEA!)&2RlA2RlBx:h|#(T,=]j09Wobz>x]z/@awRoTd+#Y(az]hFhCrm4d,#Y+jTv|Q~EfMj]uNr|~FRfOdCa!Xa9_X#@<plJvf!%b`{(9;Rgwc;.!#2x7cw#T|UDb]|T5Ju={(!=@E{&Jv)&!Ab`{'awJvf!~*>>@=be{#KuY>!+&4Ezyi[ugv&RjIdea+T)#UXa&T-T&a!Rh9auRmW=]kLg5vuRn+g3u4Rn-Ow6ARn,hHus5xNk?#UX(U~)/g8v0RkD~AwkkF?Ri.OuNBwkkA?Ri/d|a2`a*^UYa.!aBTZaTa'Xa;!(!2!-a#b2[yC>6Vyq3[xr2Wi?g1rusVh%s?DtF~<5rbJs;%!DtBfswKtCj[uvuSsEu3RgVx3o:u+wN'*Zt;@3rd~Grh~?rfg8w)Lq)qE&-a%!>bI|`jWv0vV~EfCjTv|vV~Ef@j]uNpn~FRfBcK#T']gWNu7x,k7q4ai(0!hHv8<RhmkMu9vrsBuev/RhlCJvB!,g<v{wchh~@:Rhji[vrv{wchi~@:RhkdS&a5UY#Ta!RgPwwiI5BwciI~@:Rh`x'iJvj'!5]iJPu8Bwch]~@:Rhach)U#h3rp]gLh@t|Ax,hTq3ah!-(~@:Ro0Ou!5RhXj^v(pyw8unRhVd|)`,^UYas!a?/a2Z'a^Ta{Tb7Ta(a#!a,Wf&9sZ3DtAadamov=Bqt3[xig8vsRm~>waiL2b`{QJv*_Ouv2qgj<v]v2BqfdR'X*X#Y-@3qr~Gqv~?p6hHv-]glPup5Lq+q?_%*b_{qF{n9b^{rOu4ARhpKvCD!+&~Bqp:5Dbb}nwoiKl&unuTuBv]v+ueunaXRf0=Jvh!0nKufu8v1w&w7q%w&uHrz:Rgnj5w,uxDJq/(!hNw'5ReCk0s2u3w/w'5ReFd>Za&!*UaA=<wkgsRnSJv^!%Refifw3vyRgOKu_B'!,<]gkiiu:w&Rh<=C@a^<B57@2F{[<B5@aW:=3away9A5aW=<B=C@a^<B57@2F{Ie-#`(^^^bCara.b8aza6!/bZ,!adTbnTbOb+aFaS!aAT9@Wf~2Wli3Dtl2@d,#Y&RfnRfmJwJZtN~GqyJva&!VyMg<v~Rm%iXuJu3Rm9Jv[_=]ih9wlkDRkCd1#`(@Wg>2Wls3cH#T(@<Rj*=>Ri|b~'#23s9h<~El.d'#Y&Dtxi^rzvdRl#d*#U%(o|B2s`hJwSaxRmDKv4B&!1:Rmdd5#`'Vx}to~Hq{x'f1v3(!BA5ba|bJv_&!Wfug1v]ReIdO+U/Y#&G}-8wze=Rh{g1v]ReHg/uQRf/by#)ibQwERl/cH#T(@<Rj+=>Ri{cNu+vlax-!(#a0qa9<Rii2;;bU{H;x<i=&X#Rk`<4wwi=C9H~8xAI(Y#<azRi@45wXI<B9;5bb~7dL(X#Xa(+!aL6Vy{g5QqOau:5au2@ay547EzbxOcU(UX-T#Ta#:Cbb|A?wjh/b_|SOw6ARgtihr}u7Rhy<d1#T)X1@@=I|~=ay<2@@=aybb}Sj3vLv;<d,#Y(56H}A978H}@dGpvs@uAu`vcw9*!aFa+ai%(b!aXa8.a?a[ozWey=sU2@G}Nch&U#Rf_WexKu+D#'!t:~Gr`~?r^j]uNr|~FRg*j^psurwJt|RmcKv)@&!)7Rkv~Br[@wxfO:Rl3co#U'6Rezj_q#vIuavjRltwzeyh@vr5JqD0!>aY?C9:9au@9Cb]}9cl#U*5;5<H||jbuus1ucv&Rfvg1v~d/pppzqFr^a--a~!aMat1(hFv;Wiz@@=Izoj5uuv-7Rix~Cw`fk2WlVcZ#X,k)u3vWs@u2]ktg;wEx'fBq(_2Wg/jTv|vV~EfoJv]!15x'hzqG!(P~EfU~CRl_j6v(us5x4i-#T(2WmZ?C2F|d>Kq<aj1!*jTqIsBv=Wl`~Cw`fi2WlWj`v0u*~>RlR=c>Z,k#u3vWs@u2]kr<c1Z+jTqIsBv=Wla~Cw`fm2WlXdmb3!a{(arZa`bkTa%TbQTa-a9+c'!aM!/[yL=Bqug.w'RifhFvyDRj.g>vgwyk^9]k^Jv3_@WfbAARkhJw2_[x|JvB_wkoIRoKwkoJRoLd'(Y#<]gm=<9<H|yd'%_X#skDtb3awwqkgNulRkgdB#^',9:p'hJwSaxRmEBwVb8@4=H|qLu+w50&!)@3qs~?pU>Awwn;;Rn=c:Z'ARn<=<qwKvC@!/&~BqqJv6!&]eVb^z^xRge'/a%+^`#Sge}6<4Rn3=]n0Pw2>Rn8Jw0!&>Rn:>Rn6cY#a7+!a&=<wkaNw~h3z_c5Z{=wjh#=]nLKv^D!&)Vyz=bW|swYb<WetcG#T(2wxa@qVx@gD#Y&b^|V5JwG&!5bb|pg/w&RgD@x=kHs=uAvn!a%%/'+RmSRh694Ro`g-vaRmRhHv-]mlxCcS#`&ba~.5cD#Ta)P~=d,#Y(56H{>978H{Dd_#{2^Y%_+qbbb{6g3sERhsbU{?dfa.,`a(Xa<!aiX#(55RiG54RiHcI#T'WiU3RiVNvdwtfcRlKNvdd,#Y&RlHRlExQgf.1*^T'X#Sgf}6Wn4=]hfPrk>Rn7Jw0!&>Rn5>Rn9Lunw?&a2!,5<oq@@wqfdRlJj5Q~=d,#Y(~ARfcOuN]fdDKw;ay(}i!547E}j?cI#T(@5bV}iCbV}hdv(^^Tb?a40,b##Tbo!a*bR!a<b|a/!aKai!aU[yK=]o^g:v>ReGJwPZtK<7Rh+h<~El,Pv#5ReR@awwxjCg,ulRjDJv6&!]j!z?aQeeg>w=Sh<eeJw;!&axEzOg,Qosc!#*:wkeJ]eJ>x'h-u(!%Ro.w~h.zPdNZ(X,Ya![x{;9ReY;wkgxRiF:x?ap#Y&RmUg<s2Rkod]+UY0TZ'!a&A9sw<=bczLNvuw{gqzNhJwSaxRmCKuLay!#&s_Rf-55b^{uJvZa!!c%#(55Ri654wmiu5RiuawLu,vp!+}^%b_}Y9;wkgxba}o>A9:=b^}zKuh=a''!3awRk3c*'!#aHRk6c+Z&Rk5Rk4Jv)&!awRjSawd9*`#0?C2@EzMj8u<uJ5RmbjQrquJu3x,k>uq@_+=ayb^|W~ARkEOuN]k@7dhzV^X/X&a-#zRzSb`zXcJzTT#2WkVKvDBzW!%FzY9;5bbzWjQrquJu3Jw3%!b`zU=ayb^zQd:#X(T-a!6Vyywxh}=b]{Jg=u1RiAdGp~qHtzv!w(wA+a+a;<!aJaYai'anasb(=azRmV:Cbb{MLq2vb!%')RjuRjrRjtRjqx3jnqCw3!%')Rk(Rk+Rk&Rk)Lq2vb!%')Rj{RjxRjzRjwLq2vb!%')RjsRjpRjfRjex3jcqCw3!%')Rk'Rk*RjkRjl9<CbbzfOu4ARhxLq2vb!%')RjyRjvRjhRjgx=joq*uKvb!%')+-Rk.Rk%Rj~Rk-Rk#Rj}x=jdq*uKvb!%')+-Rk,Rk!Rj|RjmRjjRjidAq&qKs@uAv8Aa.'*-a@a&0!aM@a5[y73Dsy3Ds|3Dt):wxgI2sHJwJZt.~Gqxwsf0ikrzt}Rl0Jvy_[xj~HqzKv_A|D!&WfP8axRoVcf,U#k(v]v+ueunaXRf1Ju}'!g8u#Ri=jQw!sCunLprq>!,')~<5qeGzq9F{W=c##%s5au:5aU3CBE|;d4#X(D!a&6Vygx(b;#(=]ed?C2F{N<capoq2r[a&!aPa9,'Pw;5s:@@=I|,55w_h|@@=IzcP~=x'fCqB_2Wl2>aU@@=I|1OuNBc1Z+jTqIsBv=Wlc~Cw`fl2WlZ~AcTa%!Z+jTqIsBv=Wlb~Cw`fh2WlYk+uNqJsBv=WlSg,u3dca3#UXaMYa)TaB-=cM|7T#<bI}l5@B932:aV2G{BOuNBJq:|M!5Ezt=<B=C@a^<B57@2F{v>cB{/T#=ay<bI{3Jv6!a.6BKq0ah&+!5E}HP~Ef{978BaU@@=Iza<7d#.Y#978BaU@@=IzH~AJq0!(@@=IzG978BaU@@=IzFe,aU*Y&^^^bvJb,b:bFad!a,c2Ta>aL.bo6!a#CbTa'T#Re{2Wlh2@G{yg6t~Ro_NvdRfticuRQRllJv3&!x&c|zs@Jw3!%RflwpfkRlpKuL;%(!Re<@G|C2GzdhIvuBwgjAg-u0RjAKQB%!(GzZ@G|5NuuRl7d='T+Y#Vy[g<v~Rm!==G|>JvA!)@wma=]m1ifuaw&RmnLs@vT'!|/+[y,g:v>ReTJw1!#qX=x!eC{bLu+wT&)ZtZauq_~Graci&U#F|89:r_Lupvq!.)&2RlG8RfaC=x!eF{_h?rpWlmd&'!#X|&]k::xJey#`'T|+<E|&2@H|%dE#(^,g;u.RiEg6vjRiC9xCkA{O|zY#g=ucRmXKs0@!&*@G|m@awRknJuh!,3d(}gY}eJvj!%Rm):Jw3!%Rm+Rm-Ls0w(&!a(a#@b[|6cZ#X'7RkxWgAOu4ARn'dH'U#Y*Vz-Wm'CARm}d]*#a%^a*T'aK!a<9bV{PC=p*Jw4!&SgxcbB5r]idw(wBRmF7xFkt#&`(Rm/Rm8E|!JuY_9:Rl5=wrgr2:bbxd@xXfB(a*#T+!.X0X1Ta/a'T&RlDRfL>RlyARl9b[z[>RfZ:RlL:RfRwlg/ARl;9;RlxKv,A/!%7s69<74=BA5ba{-8Bde#`a<XaKYa1,a'P~=wxfB2bZ}}?C972@@=I}r8@55B9;5bb}G978B2@@=aybb}3j3vLv;<Jw3&!>Rfk=ayb^}4~Ad1#`*@@=aybb{w2@>==<bbz]dx+UY#^UaF!a9!bB'Ya1.!ajXa#%olRhD[y=3Dt#Ov5BrHKuMB%!(Rf^Wep~HrJwkiQjKr|~FRg)Ku+D#'!t5~GrF~?rDdV)UY,Z/_7RkuG{<~BrBg,rlsO:235B@bX}|d?a1!#`(6Vyn5@d##Y+jTv|vV~EfIj]uNpn~FRfH7Lq2vb1!a9-978BaU@@=Iz9978BbU}#~AJq0!(@@=Iz8978BaU@@=Iz7~AJQ|}!978BbU}!JvkaK!AdUa21-U#`a+(g/vsRn~Ou!5RPj:rmu9WhOjXuvvNr}:RhAj^v(pyw8unRn[kPr}p|u7vwv]RiSBd;pppzq@qHQa?(b.!a.a`@.|xa(hFv;Wiyj5uuv-7Riw~Cw`fg2WlU978BbU|wOuNBJqG!(P~EfD~CRlQcZ#X,k)u3vWs@u2]ksg;wEx'f@q1_2Wg.j]uNpn~FRfqJv]!15x'h{qG!(@@=IzK~CRl^j6v(us5x4i,#T(2WmY?C2F{1>Kq<aj1!*jTqIsBv=Wld~Cw`fj2Wl[j`v0u*~>RlT=c>Z,k#u3vWs@u2]kq<c1Z+jTqIsBv=Wle~Cw`fn2Wl]dn1#c(a(b^a2!b/bAT(bj!aDa7bu,a_a{c0!2T0g:v>ReD2@G{42@G{5~DpM~<5rc=Bx6i>{RT#RnI@zCx]y]z:2Jv[!zr5Awyk]9]k]dD(Y+X#6Vz.g=wKtgwhaCwgmTWj2Lu,w%_+/[y-B;b^xeg3u3Rj-2@bX{*KrJ<!+'@Wg(g?QRlC@Jv`!%b[zIwsfII}8JQ_@w|kW|=Jv(%!AqcOuNBJvEzh!bYzjLs@wP#(0!oy@>RkdJwMZtc3Dtd@BcG#T'9bWxg2@2Fznd*#Y+;2x'c}w<zizixNgwa#Z'U+!/!a'!a+w~g~z6wcn{Rn}wcnzRn|5Rh%=]nJg5vuRmvNvdRlvcprJu}w*az*a#!%.a.'Bot9qT]kj@Wg'ay2Gzv@Jv`!%b[zEwsfHI}1;ck#Ux`<Cbbx_Lu+w!a&0*!wko*wwo,So,}6Juqxf!E}PigQuyRm`d3(`#8>Rn%:A5B;bZ~%KvhCa!a2!x>k7#Uxb@b{#xaRk7Jw0!)>wwhlShl}6>wwhmShm}6CJvB!.x'hhvj{!!5Bwkhhbaz}x'hivjz~!5Bwkhibaz|xEhTrNu,v-vpD!a%&/)a3a.,%Ro2t[CE{)@3re9b]{%wjo09:rgc:Z&Ro6=<riifuaw&RmoKrNA!%(Ro4>Ro89;Ri`dSaL'UYzxZb)7Rka3xRhT&!,!#^1U}vbaz{>>@=be}yC@:D5bazzKu+A&!}{?ba}y>>@=be}wxBh[t`u~vJvr!%a!a()a,a0a4RoC=]o;Ju(!%RoGRhdwjh`=]oAg>w#Ro?g5vuRo=NvdRl|Ku]C.!&;RoEJvB!%RoORoMBx'h[v+_?w~h`}~5?w~hd~!xKh]oiptu-utv.vp!#%&a30a@a'a+(a/aOp(o~p!RoDJu(!%RoHRhewjha=]oBNvdRl}g>w#Ro@g5vuRo>c[#X']o<CauRoRAd-#Y':RkpauRoQKu]C.!&;RoFJvB!%RoNRoPBx'h]v+_?w~ha}t5?w~he}ue!/UbhYacXaW^Tc&a;b:a-c/#b&aja1(!cL+!bKbt!bmcRc9aIc?8[yW3Dtt94Rg`Jv}!&SiRMzBhEebShEMNuPRe>x7gL#TzuwjirRipc<Z&>on;>z=h-MSh.Mwqczx'a7vj&!>Re4@=ResJt__NuPRi*NuPRi)j]uNr|~FRfzKrJ>_+@Wfy@Wf]2WocKrJ<!+'@Wg%g/QRl@@Jv`!&awRl<wsfFIzgLu(w*!.*&ShBMwvhIRhI9;RhNx1hK'!#Sn]Mx1hK~0!#:2<H~7cNu+w7D*'1ZtW>Rn1~?rOc:Z&Rn2=<rQ<7wjh&=BSnLMc]#X(6Vz)w[b=a!U#9wzgMc3#&(RgMRitRis<x,gKt`ax!&+SioM=BSilMc3#&(RgKRinRimKurB,!&SiQMzBhDebShDM6BJQ!(P~Efx978B2@@=I}WLrJw!!,a*&@G}O@9wkibRid@@x'fKwC!&SlDMSfLMjUv~Q~EfKKv3@a+!(hFv-]mpx/hYZ(C5RiWz<o/MwkhY?So/M@x,gbvfB*&!SgEM:SoeeehFu3:Rgbda(,^TZa)X/7Sg[eb:2RgI~BrMC@wgkc:wwkcRerx3h(uUvK!&*,SnOM4Sh*MArRg;wHRh(x=h;rJvPwI!a4',a'0@Wg&=BSh/Mg>w=Rh=g3w*wwgGRgGcW(X#;Sg}M2Gzk@Jv`!&awRl=wsfGIz`dKZ*T'Y-:RhR7RhQg5u-p`j6v(us5d,#Y+~Awkia?RicOuNBwkibba}Ld6p~tyu_vbAa'a+!a/'a3aEa8a!>Sh,ebJv{!&Sh@ebSaReb9;SgwebNuPRi(NvdRl)NuPRi'hHu^<Rm^Jvv_@Wl(g;u1Si/ebKu'B&!*Sh?eb@Wl'z@aPeb95Si.ebcpputyvjB)!,&a+0a%ShAMWeK@G}C@WfJ9;RhMwvhH9w{ia}ix,hJvRA1(!zAn[MRhHx1hJ~*!#hFv(BSn[MBJQ!(@@=I~'978B2@@=I}2db.Ua<'X}+T#a0XaG2G}E;wkg|wuh!Rh!x,hZu,@)!&So0MVy)C5RiXACJvB!&5RiY5RiZg8w)cG}*T#2@bU}=KsA>(!a.3wkhZba~(x,h^u(A!&(SoCMRhb5Bz=h[eb?w~hb~6x,h_u(A!&(SoDMRhc5Bz=h]eb?w~hc~6e)aA1T#T,^^^c-bMb&blcPaP(a/!0!bA=b5c@a(!bfbrc#2afwmhARnjwchORnp2Wlf3DtsNvdRl-2@wpa<]m0bx(#:awRk2@Jw3!%RfhwpfgRlnKQB%!(G{V@G|'NuuRl6d='T+Y#VyUg<v~Rl~==G|<Jv+'!aYShC}6@B<5?ba~8@Jw3'!g2QRljhLrpWlOd+#Y'g.w'rIg>w*wgj@g-u0Rj@Lu+wT&)ZtUauq]~GrGci&U#F|39:rELrNvj!.%*RhCwunfw~nf~:9;Ri]>wtnhg;wHRnhx3hDs@v~!/+'@Wfr@9RkSNu&Rlo=@<5GzoKs0@_+@Wl+@awRkmJuh!-3d(}pY#qWJvj!%Rm(:Jw3!%Rm,Rm*de&!1U-U#`)Re;@G|.@9Ri82@wjfvRlq=@<5GzpLvOvr!).&2RlF8Rf`C=x!eE{.Jw3_g2QRlkhLrpWlPde(!#U{s,UXa*Ta'[y'g:v>ReS;x0PZ&RnlRnn~HrKJw1}f!=x!eB|2w]aP(#Xa&a*Ta.Ua2a7=]iOd'#Y&Ro&WnWg;u.RiDg6vjRiBNvdRlzhNvj]nYJuW_2Wm3x)kFze{9d])!a.!,Y01!#&aC!a3RndC=ox~BrC@2b^{pg,rlse7x'ksuq!%Rm.E{xidw(wBRmGx9o+)X#wwo-So-}69:Rl4@xSf@a#XZ'X)X,Ta(/ARl8b[xc>RfY:RlI:RfQwlg.ARl:9;Rlwdn'#^XafaQa1X1TaHTa)@b[{zcZ#X'7RkwWg@Ou4ARn&x)kG#{,g7u/RkGdH'U#Y*Vz'Wm&CARm|bx#(A]gUbUzJj9Q~=d,#Y(56H}l978H{U7d,0#U*2>ABb_xZ978BbU{e~AJQ{g!978BbU{hxMh?ad{oUYZ.x1h?{l!#:2<H{mx3n[t{vl!,&a%3Ro(z=iS}6ARnr=Bwsn^wvn`Rnbd`*T}B0!#^X'BG{c9b]{a>>@=be}F?JvS!&BG{d7BG}(Bde#`a1X,Ya@!a'P~=wxf@2bZ}I56B2@@=aybb}08@55B9;5bb}<j3vLv;<Jw3&!>Rfg=ayb^}&OuNBKuLA!)a!P~=x#fD{f2@>==<bbzl?C972@@=Ix^d6rSu,v7w*C(0a)a6#B+a%!sQ[y?3Dt%3[xn~<5rLOu!5p@Ku+D#'!t7~GrP~?rNKvlaya7'!h+v-5qMg=t|cd,U#5AAaa5Abb{S@52B5@a[@52B5Gx[iXueu;d<#`a(!/549C;ag>23ExY5@Dah89b^~689Jv)!~2b[~1Lv'w(%*!a#bX|aPrmawRe]keu7uhv-q6rxu,q`xTo]/a5aU!bNaDXbi!b-!ao!b<bwA!#5@B932:aV2G|:d-)Y#hJrL>RhG<7@C5<H|_=Cau:5aj5@B932:bJ|ng>vIbs)#?C2F|9jPv0w.vISh-MKvUaz(.!9ABbb|[5;5<H|Eg>unwfh;9:4E|YjQsBt|vjx'hYq3!(?C2F|J:2<BaY?C2F|GOu!5x,g|p{ah!-(?C2F|c9:4E|OjXuvvNr}:Rh&i[w*t|cd+U#jJvsu)vsSn~Mkfrmu9p}u7vwv]So!McW#Xa!ax5@A5aY:5;5<H|>kJv~vYrquJu3x4ib#T)2@SmZM?C2F|Bj:rmu9@xPhI(a*a#U#`a3-5Abb|L~@:RhK9:4E|0@52B5G|#C::aY?C2F|-:2<BaY?C2F|.5Jvk!a)javYrquJu3x4ia#T)2@SmYM?C2F|HAxPhH(!a#U#`a*-5Abb|4~@:RhJ9:4E|R@52B5G|F:2<BaY?C2F|Sc^#Xa2j=Qq5CJvB!-g<v{z;hhM?C2F|Zi[vrv{z;hiM?C2F|XKsA>!a)-g<v{z;h[eb?C2F|]i[vrv{z;h]eb?C2F|^iZu.vix,hZq3ah!.(?C2F|QOu!5ShXM:2<BaY?C2F|P",13494,2713,49,25,61);var T;(function(e){e[e.VALUE_LENGTH=49152]="VALUE_LENGTH",e[e.FLAG13=8192]="FLAG13",e[e.BRANCH_LENGTH=8064]="BRANCH_LENGTH",e[e.JUMP_TABLE=127]="JUMP_TABLE",e[e.VALUE_MASK=8191]="VALUE_MASK"})(T||(T={}));var O;(function(e){e[e.AMP=38]="AMP",e[e.NUM=35]="NUM",e[e.SEMI=59]="SEMI",e[e.EQUALS=61]="EQUALS",e[e.ZERO=48]="ZERO",e[e.NINE=57]="NINE",e[e.LOWER_A=97]="LOWER_A",e[e.LOWER_X=120]="LOWER_X"})(O||(O={}));var ba=32,Sr=21,In=2097151,lt=2047,Pr=0;function Bn(e){let a=e>>>Sr;return a===lt?Pr:a}function jr(e){return e-O.ZERO>>>0<=9}function Ln(e){return(e|ba)-O.LOWER_A>>>0<=5}function qr(e){return(e|ba)-O.LOWER_A>>>0<=25}function Nn(e){return e===O.EQUALS||qr(e)||jr(e)}var Ar;(function(e){e[e.EntityStart=0]="EntityStart",e[e.NumericStart=1]="NumericStart",e[e.NumericDecimal=2]="NumericDecimal",e[e.NumericHex=3]="NumericHex",e[e.NamedEntity=4]="NamedEntity"})(Ar||(Ar={}));var ct;(function(e){e[e.Legacy=0]="Legacy",e[e.Strict=1]="Strict",e[e.Attribute=2]="Attribute"})(ct||(ct={}));function On(e,a,t,r){let o=(a&T.BRANCH_LENGTH)>>7,i=a&T.JUMP_TABLE;if(i){if(o===0)return r===i?t:-1;let l=r-i;if(l>>>0>=o)return-1;let c=e[t+l];return c===0?-1:t+o+c-1&65535}if(o===0)return-1;let n=o+1>>1,s=t+n+o;for(let l=0;l<o;l++){let u=e[t+(l>>1)]>>((l&1)<<3)&255;if(u===r){let h=t+n+l;return s+e[h]&65535}if(u>r)return-1}return-1}function Er(e,a,t){return t===1?String.fromCharCode(e[a]&T.VALUE_MASK):t===2?String.fromCharCode(e[a+1]):String.fromCharCode(e[a+1],e[a+2])}function Hn(e,a,t){let r=a+1,o=0,i=r;if(r<t&&(e.charCodeAt(r)|ba)===O.LOWER_X)for(r+=1,i=r;r<t;){let s=e.charCodeAt(r);if(jr(s))o=o*16+(s-O.ZERO);else if(Ln(s))o=o*16+((s|ba)-O.LOWER_A+10);else break;r+=1}else for(;r<t;){let s=e.charCodeAt(r)-O.ZERO;if(s>>>0>9)break;o=o*10+s,r+=1}if(r===i)return 0;r<t&&e.charCodeAt(r)===O.SEMI&&(r+=1),o>1114111&&(o=1114112);let n=r-a;return n>=lt&&(Pr=n,n=lt),n<<Sr|o}function Un(e,a,t){let r=Rr,o=e.indexOf("&");if(o<0)return e;let i=e.length,n=0,s="",l=r[0],c=l&T.JUMP_TABLE,u=(l&T.BRANCH_LENGTH)>>7;do{let h=o+1,p=e.charCodeAt(h),f,m;if(p===O.NUM){let b=Hn(e,h,i);f=Bn(b),a&&f>0&&e.charCodeAt(h+f-1)!==O.SEMI&&(f=0),m=f===0?"":_r(b&In)}else if(qr(p)){f=0,m="";let b=p-c,w;if(b>>>0<u){let $=r[1+b];w=$===0?-1:u+$&65535}else w=-1;let k=0,C=0,v=w<0?0:r[w],y=h+1;e:for(;y<i;){for(;(v&(T.VALUE_LENGTH|T.FLAG13))===0&&(v&T.JUMP_TABLE)!==0;){let j=v&T.JUMP_TABLE,E=(v&T.BRANCH_LENGTH)>>7;if(E===0){if(e.charCodeAt(y)!==j)break e;w+=1}else{let F=e.charCodeAt(y)-j;if(F>>>0>=E)break e;let R=r[w+1+F];if(R===0)break e;w=w+E+R&65535}if(v=r[w],y+=1,y>=i)break e}if((v&(T.VALUE_LENGTH|T.FLAG13))===T.FLAG13){let j=(v&T.BRANCH_LENGTH)>>7;if(e.charCodeAt(y)!==(v&T.JUMP_TABLE))break;y+=1;let E=j-1,F=w+1,R=0;for(;R+1<E;R+=2){let N=r[F];if(e.charCodeAt(y)!==(N&255)||(y+=1,e.charCodeAt(y)!==(N>>8&255)))break e;y+=1,F+=1}if(R<E){if(e.charCodeAt(y)!==(r[F]&255))break;y+=1}w+=1+(j>>1),v=r[w];continue}let $=v>>>14,_=e.charCodeAt(y);if($!==0){if(_===O.SEMI){f=y-h+1,m=$===1?String.fromCharCode(v&T.VALUE_MASK):Er(r,w,$);break}if(!a&&(v&T.FLAG13)===0&&(f=y-h,k=w,C=$),$===1)break}let A=On(r,v,w+($||1),_);if(A<0)break;w=A,v=r[w],y+=1}if(m===""){let $=v>>>14;$!==0&&!a&&(v&T.FLAG13)===0&&(f=y-h,k=w,C=$),f>0&&(m=Er(r,k,C))}}else f=0,m="";f===0||t&&p!==O.NUM&&e.charCodeAt(h+f-1)!==O.SEMI&&h+f<i&&Nn(e.charCodeAt(h+f))?o=h:(n<o&&(s+=e.slice(n,o)),s+=m,o=n=h+f),e.charCodeAt(o)!==O.AMP&&(o=e.indexOf("&",o))}while(o>=0);return s+e.slice(n)}function ya(e){return Un(e,!0,!1)}var Fr;(function(e){e[e.XML=0]="XML",e[e.HTML=1]="HTML"})(Fr||(Fr={}));var Tr;(function(e){e[e.UTF8=0]="UTF8",e[e.ASCII=1]="ASCII",e[e.Extensive=2]="Extensive",e[e.Attribute=3]="Attribute",e[e.Text=4]="Text"})(Tr||(Tr={}));var Zn=class{src_Any=rt.source;src_Cc=ot.source;src_Z=nt.source;src_P=Ue.source;src_ZPCc=[this.src_Z,this.src_P,this.src_Cc].join("|");src_ZCc=[this.src_Z,this.src_Cc].join("|");cache={};opts={maxLength:1e4,urlAuth:!1,schema_names:[]};constructor(e={}){this.opts={...this.opts,...e}}set(e={}){return this.opts={...this.opts,...e},this.cache={},this}escapeRE(e){return e.replace(/[.?*+^$[\]\\(){}|-]/g,"\\$&")}nestedPairRE(e,a,t=4){let r=this.escapeRE(e),o=this.escapeRE(a),i=`(?:(?!${this.src_ZCc}|${r}|${o}).)`,n=`${r}${i}{0,1000}${o}`;for(let s=2;s<=t;s++)n=`${r}(?:${i}|${n}){0,1000}${o}`;return n}get_text_separators(){return this.cache.text_separators??=/[><\uff5c]/}get_pseudo_letter(){return this.cache.src_pseudo_letter??=new RegExp(`(?:(?!${this.get_text_separators().source}|${this.src_ZPCc})${this.src_Any})`)}get_ipv4_addr(){return this.cache.src_ip4??=new RegExp("(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]|[0-9])[.]){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]|[0-9])")}get_ipv6_addr(){let e="[0-9A-Fa-f]{1,4}",a=`(?:(?:${e}:${e})|${this.get_ipv4_addr().source})`;return this.cache.src_ip6_addr??=new RegExp(`(?:(?:${e}:){6}${a}|::(?:${e}:){5}${a}|(?:${e})?::(?:${e}:){4}${a}|(?:(?:${e}:){0,1}${e})?::(?:${e}:){3}${a}|(?:(?:${e}:){0,2}${e})?::(?:${e}:){2}${a}|(?:(?:${e}:){0,3}${e})?::${e}:${a}|(?:(?:${e}:){0,4}${e})?::${a}|(?:(?:${e}:){0,5}${e})?::${e}|(?:(?:${e}:){0,6}${e})?::)`)}get_ipv6_url_host(){return this.cache.src_ip6_host??=new RegExp(`\\[${this.get_ipv6_addr().source}\\]`)}get_ipv6_mail_host(){return this.cache.src_ipv6_mail_host??=new RegExp(`\\[IPv6:${this.get_ipv6_addr().source}\\]`)}get_auth(){return this.cache.src_auth??=new RegExp(`(?:(?:(?!${this.src_ZCc}|[@/\\[\\]()]).){1,50}@)?`)}get_port(){return this.cache.src_port??=new RegExp("(?::(?:6(?:[0-4]\\d{3}|5(?:[0-4]\\d{2}|5(?:[0-2]\\d|3[0-5])))|[1-5]?\\d{1,4}))?")}get_host_terminator(){return this.cache.src_host_terminator??=new RegExp(`(?=$|${this.get_text_separators().source}|${this.src_ZPCc})(?!${this.opts["---"]?"-(?!--)|":"-|"}_|:\\d|\\.-|\\.(?!$|${this.src_ZPCc}))`)}get_path_terminator(){return this.cache.src_path_terminator??=new RegExp(`${this.src_ZPCc}|${this.get_text_separators().source}`)}get_path(){return this.cache.src_path??=new RegExp(`(?:[/?#](?:${this.nestedPairRE("[","]")}|${this.nestedPairRE("(",")")}|${this.nestedPairRE("{","}")}|\\"(?:(?!${this.src_ZCc}|["]).){1,100}\\"|\\'(?:(?!${this.src_ZCc}|[']).){1,100}\\'|\\'(?=${this.get_pseudo_letter().source}|[-])|\\.{2,20}[:]?[a-zA-Z0-9%/&]|\\.(?!${this.src_ZCc}|[.]|$)|`+(this.opts["---"]?"\\-(?!--(?:[^-]|$))(?:-{0,19})|":"\\-{1,20}|")+`,(?!${this.src_ZCc}|$)|;(?!${this.src_ZCc}|$)|\\!{1,20}(?!${this.src_ZCc}|[!]|$)|\\?(?!${this.src_ZCc}|[?]|$)|`+this.get_path_extra().source+`[\\\\/:%@#&=_~*]|(?!${this.get_path_terminator().source}).){1,${this.opts.maxLength}}|\\/)?`)}get_mail_name(){return this.cache.src_mail_name??=new RegExp("[-!#$%&'*+/=?^_`{|}~a-zA-Z0-9](?:[-!#$%&'*+/=?^_`{|}~a-zA-Z0-9]|[.](?=[-!#$%&'*+/=?^_`{|}~a-zA-Z0-9])){0,63}")}get_xn(){return this.cache.src_xn??=new RegExp("xn--[a-z0-9\\-]{1,59}")}get_tld(){if(this.cache.tld)return this.cache.tld;let e=[...new Set(this.opts.tlds||[])].sort().reverse().join("|");return this.cache.tld=new RegExp(`${e||"$#none#$"}|${this.get_xn().source}`),this.cache.tld}get_domain_root(){return this.cache.src_domain_root??=new RegExp("(?:"+this.get_xn().source+`|${this.get_pseudo_letter().source}{1,63})`)}get_domain(){return this.cache.src_domain??=new RegExp("(?:"+this.get_xn().source+`|(?:${this.get_pseudo_letter().source})|(?:${this.get_pseudo_letter().source}(?:-|${this.get_pseudo_letter().source}){0,61}${this.get_pseudo_letter().source}))`)}get_url_host_port(){return this.cache.url_host_port??=new RegExp("(?:"+this.get_ipv6_url_host().source+`|(?:(?:(?:${this.get_domain().source})\\.){0,10}${this.get_domain().source}))`+this.get_port().source+this.get_host_terminator().source)}get_fuzzy_url_host_port(){return this.cache.fuzzy_url_host_port??=new RegExp("(?:"+(this.opts.fuzzyIP?this.get_ipv4_addr().source+"|":"")+`(?:(?:(?:${this.get_domain().source})\\.){1,10}(?:${this.get_tld().source})))`+this.get_host_terminator().source)}get_mail_host(){return this.cache.src_mail_host??=new RegExp("(?:"+this.get_ipv6_mail_host().source+`|(?:(?:(?:${this.get_domain().source})\\.){0,4}${this.get_domain().source}))`+this.get_host_terminator().source)}get_fuzzy_mail_host(){return this.cache.src_fuzzy_mail_host??=new RegExp("(?:"+this.get_ipv6_mail_host().source+`|(?:(?:(?:${this.get_domain().source})[.]){1,4}${this.get_domain_root().source}))`+this.get_host_terminator().source)}get_path_extra(){return this.cache.src_path_extra??=new RegExp("")}get_fuzzy_mail_host_search(){return this.cache.mail_fuzzy_host_search??=new RegExp(`@${this.get_fuzzy_mail_host().source}`,"ig")}get_fuzzy_link_search(){return this.cache.link_fuzzy_search??=new RegExp(`(^|(?![.:/\\-_@])(?:[$+<=>^\`|\uFF5C]|${this.src_ZPCc}))(?:(?![$+<=>^\`|\uFF5C])${this.get_fuzzy_url_host_port().source}${this.get_path().source})`,"ig")}get_http_validator(){return this.cache.http_validator??=new RegExp("\\/\\/"+(this.opts.urlAuth?this.get_auth().source:"")+this.get_url_host_port().source+this.get_path().source,"iy")}get_relative_proto_validator(){return this.cache.relative_proto_validator??=new RegExp((this.opts.urlAuth?this.get_auth().source:"")+`(?:localhost|${this.get_ipv6_url_host().source}|(?:(?:${this.get_domain().source})[.]){1,10}${this.get_domain_root().source})`+this.get_port().source+this.get_host_terminator().source+this.get_path().source,"iy")}get_mail_name_validator(){return this.cache.mail_name_validator??=new RegExp(`(?:^|${this.get_text_separators().source}|"|\\(|${this.src_ZCc})(${this.get_mail_name().source})$`)}get_mailto_validator(){return this.cache.mailto_validator??=new RegExp(`${this.get_mail_name().source}@${this.get_mail_host().source}`,"iy")}get_schema_names(){return this.cache.schema_names??=new RegExp((this.opts.schema_names||[]).map(e=>this.escapeRE(e)).join("|"))}get_schema_search(){return this.cache.schema_search??=new RegExp(`(^|(?!_)(?:[><\uFF5C]|${this.src_ZPCc}))(${this.get_schema_names().source})`,"ig")}get_schema_at_start(){return this.cache.schema_at_start??=new RegExp(`^${this.get_schema_search().source}`,"i")}},dt={validate:(e,a,t)=>{let r=t.re.get_http_validator();r.lastIndex=a;let o=r.exec(e);return o?o[0].length:0},normalize:(e,a)=>a.normalize(e)},Xn={"http:":dt,"https:":dt,"ftp:":dt,"//":{validate:function(e,a,t){let r=t.re.get_relative_proto_validator();r.lastIndex=a;let o=r.exec(e);return o?a>=3&&e[a-3]===":"||a>=3&&e[a-3]==="/"?0:o[0].length:0},normalize:(e,a)=>a.normalize(e)},"mailto:":{validate:function(e,a,t){let r=t.re.get_mailto_validator();r.lastIndex=a;let o=r.exec(e);return o?o[0].length:0},normalize:(e,a)=>a.normalize(e)}},Gn="a:cdefgilmnoqrstuwxz|b:abdefghijmnorstvwyz|c:acdfghiklmnoruvwxyz|d:ejkmoz|e:cegrstu|f:ijkmor|g:abdefghilmnpqrstuwy|h:kmnrtu|i:delmnoqrst|j:emop|k:eghimnprwyz|l:abcikrstuvy|m:acdeghklmnopqrstuvwxyz|n:acefgilopruz|o:m|p:aefghklmnrstwy|q:a|r:eosuw|s:abcdeghijklmnortuvxyz|t:cdfghjklmnortvwz|u:agksyz|v:aceginu|w:fs|y:et|z:amw",Vn="biz|com|edu|gov|net|org|pro|web|xxx|aero|asia|coop|info|museum|name|shop|\u0440\u0444";function Yn(){let e=Vn.split("|");return Gn.split("|").forEach(a=>{let t=a.indexOf(":"),r=a.slice(0,t);for(let o of a.slice(t+1))e.push(r+o)}),e}var Kn={fuzzyLink:!1,fuzzyEmail:!0,fuzzyIP:!1,"---":!1,tlds:Yn(),urlAuth:!1,maxLength:1e4},zr=class{schema;index;lastIndex;raw;text;url;constructor(e,a,t,r){let o=e.slice(t,r);this.schema=a.toLowerCase(),this.index=t,this.lastIndex=r,this.raw=o,this.text=o,this.url=o}},Mr=class{__opts__;__schemas__;re;constructor(e={}){let{rebuilder:a,...t}=e;this.__opts__={...Kn,...t},this.__schemas__={...Xn},this.re=a||new Zn,this.re.set({...this.__opts__,schema_names:Object.keys(this.__schemas__)})}add(e,a=null){if(!a)delete this.__schemas__[e];else{let t={normalize:(r,o)=>o.normalize(r),...a};this.__schemas__[e]=t}return this.re.set({...this.__opts__,schema_names:Object.keys(this.__schemas__)}),this}set(e={}){return this.__opts__={...this.__opts__,...e},this.re.set({...this.__opts__,schema_names:Object.keys(this.__schemas__)}),this}test(e){if(!e.length)return!1;let a,t;for(t=this.re.get_schema_search(),t.lastIndex=0;(a=t.exec(e))!==null;)if(this.testSchemaAt(e,a[2],t.lastIndex))return!0;if(this.__opts__.fuzzyLink&&this.__schemas__["http:"]&&(t=this.re.get_fuzzy_link_search(),t.lastIndex=0,t.exec(e)!==null))return!0;if(this.__opts__.fuzzyEmail&&this.__schemas__["mailto:"]&&e.indexOf("@")>=0){let r=this.re.get_fuzzy_mail_host_search(),o=this.re.get_mail_name_validator();for(r.lastIndex=0;(a=r.exec(e))!==null;){let i=e.slice(Math.max(0,a.index-65),a.index);if(o.test(i))return!0}}return!1}testSchemaAt(e,a,t){return this.__schemas__[a.toLowerCase()]?this.__schemas__[a.toLowerCase()].validate(e.slice(0,t+this.__opts__.maxLength),t,this):0}match(e){let a=[],t=this.re.get_schema_search(),r,o,i,n,s,l,c=!1,u=!1,h=!1,p=0;if(!e.length)return null;for(t.lastIndex=0,this.__opts__.fuzzyLink&&this.__schemas__["http:"]&&(r=this.re.get_fuzzy_link_search(),r.lastIndex=0),this.__opts__.fuzzyEmail&&this.__schemas__["mailto:"]&&(o=this.re.get_fuzzy_mail_host_search(),o.lastIndex=0,i=this.re.get_mail_name_validator());;){let f=Math.max(p-1,0);if(o&&i&&!h&&(!s||s.index<p))for(o.lastIndex<f&&(o.lastIndex=f);;){let C=o.exec(e);if(!C){h=!0,s=void 0;break}let v=i.exec(e.slice(Math.max(0,C.index-65),C.index));if(v){if(s={schema:"mailto:",index:C.index-v[1].length,lastIndex:C.index+C[0].length},s.index>=p)break;o.lastIndex<f&&(o.lastIndex=f)}}if(r&&!u&&(!n||n.index<p))for(r.lastIndex<f&&(r.lastIndex=f);;){let C=r.exec(e);if(!C){u=!0,n=void 0;break}if(n={schema:"",index:C.index+C[1].length,lastIndex:C.index+C[0].length},n.index>=p)break;r.lastIndex<f&&(r.lastIndex=f)}let m=s;(!m||n&&(n.index<m.index||n.index===m.index&&n.lastIndex>m.lastIndex))&&(m=n);let b;if(!c)for(;;){if(!l){t.lastIndex<f&&(t.lastIndex=f);let y=t.exec(e);if(!y){c=!0;break}l={schema:y[2],index:y.index+y[1].length,lastIndex:y.index+y[0].length}}if(l.index<p){l=void 0;continue}if(m&&l.index>m.index)break;let C=l;l=void 0;let v=this.testSchemaAt(e,C.schema,C.lastIndex);if(v){b={schema:C.schema,index:C.index,lastIndex:C.lastIndex+v};break}}let w=b;if((!w||s&&(s.index<w.index||s.index===w.index&&s.lastIndex>w.lastIndex))&&(w=s),(!w||n&&(n.index<w.index||n.index===w.index&&n.lastIndex>w.lastIndex))&&(w=n),!w)break;w===s?s=void 0:w===n&&(n=void 0);let k=new zr(e,w.schema,w.index,w.lastIndex);k.schema?this.__schemas__[k.schema].normalize(k,this):this.normalize(k),a.push(k),p=w.lastIndex}return a.length?a:null}matchAtStart(e){if(!e.length)return null;let a=this.re.get_schema_at_start().exec(e);if(!a)return null;let t=this.testSchemaAt(e,a[2],a[0].length);if(!t)return null;let r=new zr(e,a[2],a.index+a[1].length,a.index+a[0].length+t);return this.__schemas__[r.schema].normalize(r,this),r}tlds(e,a=!1){return e=Array.isArray(e)?e:[e],a?this.__opts__.tlds=this.__opts__.tlds.concat(e):this.__opts__.tlds=e,this.re.set({...this.__opts__,schema_names:Object.keys(this.__schemas__)}),this}normalize(e){e.schema||(e.url=`http://${e.url}`),e.schema==="mailto:"&&!/^mailto:/i.test(e.url)&&(e.url=`mailto:${e.url}`)}};var Qn=/^xn--/,es=/[^\0-\x7F]/,as=/[\x2E\u3002\uFF0E\uFF61]/g,ts={overflow:"Overflow: input needs wider integers to process","not-basic":"Illegal input >= 0x80 (not a basic code point)","invalid-input":"Invalid input"},ut=35,ae=Math.floor,pt=String.fromCharCode;function ce(e){throw new RangeError(ts[e])}function rs(e,a){let t=[],r=e.length;for(;r--;)t[r]=a(e[r]);return t}function Ir(e,a){let t=e.split("@"),r="";t.length>1&&(r=t[0]+"@",e=t[1]),e=e.replace(as,".");let o=e.split("."),i=rs(o,a).join(".");return r+i}function Br(e){let a=[],t=0,r=e.length;for(;t<r;){let o=e.charCodeAt(t++);if(o>=55296&&o<=56319&&t<r){let i=e.charCodeAt(t++);(i&64512)==56320?a.push(((o&1023)<<10)+(i&1023)+65536):(a.push(o),t--)}else a.push(o)}return a}var os=e=>String.fromCodePoint(...e),is=function(e){return e>=48&&e<58?26+(e-48):e>=65&&e<91?e-65:e>=97&&e<123?e-97:36},Jr=function(e,a){return e+22+75*(e<26)-((a!=0)<<5)},Lr=function(e,a,t){let r=0;for(e=t?ae(e/700):e>>1,e+=ae(e/a);e>ut*26>>1;r+=36)e=ae(e/ut);return ae(r+(ut+1)*e/(e+38))},Nr=function(e){let a=[],t=e.length,r=0,o=128,i=72,n=e.lastIndexOf("-");n<0&&(n=0);for(let s=0;s<n;++s)e.charCodeAt(s)>=128&&ce("not-basic"),a.push(e.charCodeAt(s));for(let s=n>0?n+1:0;s<t;){let l=r;for(let u=1,h=36;;h+=36){s>=t&&ce("invalid-input");let p=is(e.charCodeAt(s++));p>=36&&ce("invalid-input"),p>ae((2147483647-r)/u)&&ce("overflow"),r+=p*u;let f=h<=i?1:h>=i+26?26:h-i;if(p<f)break;let m=36-f;u>ae(2147483647/m)&&ce("overflow"),u*=m}let c=a.length+1;i=Lr(r-l,c,l==0),ae(r/c)>2147483647-o&&ce("overflow"),o+=ae(r/c),r%=c,a.splice(r++,0,o)}return String.fromCodePoint(...a)},Or=function(e){let a=[];e=Br(e);let t=e.length,r=128,o=0,i=72;for(let l of e)l<128&&a.push(pt(l));let n=a.length,s=n;for(n&&a.push("-");s<t;){let l=2147483647;for(let u of e)u>=r&&u<l&&(l=u);let c=s+1;l-r>ae((2147483647-o)/c)&&ce("overflow"),o+=(l-r)*c,r=l;for(let u of e)if(u<r&&++o>2147483647&&ce("overflow"),u===r){let h=o;for(let p=36;;p+=36){let f=p<=i?1:p>=i+26?26:p-i;if(h<f)break;let m=h-f,b=36-f;a.push(pt(Jr(f+m%b,0))),h=ae(m/b)}a.push(pt(Jr(h,0))),i=Lr(o,c,s===n),o=0,++s}++o,++r}return a.join("")},ns=function(e){return Ir(e,function(a){return Qn.test(a)?Nr(a.slice(4).toLowerCase()):a})},ss=function(e){return Ir(e,function(a){return es.test(a)?"xn--"+Or(a):a})},ls={version:"2.3.1",ucs2:{decode:Br,encode:os},decode:Nr,encode:Or,toASCII:ss,toUnicode:ns};var ht=ls;var Hr=Object.defineProperty,to=(e,a)=>{let t={};for(var r in e)Hr(t,r,{get:e[r],enumerable:!0});return a||Hr(t,Symbol.toStringTag,{value:"Module"}),t},cs=to({arrayReplaceAt:()=>ds,asciiTrim:()=>Ca,callable:()=>ro,escapeHtml:()=>de,escapeRE:()=>ws,fromCodePoint:()=>Ze,isMdAsciiPunct:()=>Ve,isPunctChar:()=>io,isPunctCharCode:()=>Ge,isSpace:()=>q,isValidEntityCode:()=>yt,isWhiteSpace:()=>Xe,lib:()=>xs,normalizeReference:()=>ka,unescapeAll:()=>Ae,unescapeMd:()=>fs});function ro(e){let a=function(...t){return Reflect.construct(e,t,new.target&&new.target!==a?new.target:e)};return Object.defineProperty(a,"name",{value:e.name}),Object.setPrototypeOf(a,e),a.prototype=e.prototype,a}function ds(e,a,t){return[].concat(e.slice(0,a),t,e.slice(a+1))}function yt(e){return!(e>=55296&&e<=57343||e>=64976&&e<=65007||(e&65535)===65535||(e&65535)===65534||e>=0&&e<=8||e===11||e>=14&&e<=31||e>=127&&e<=159||e>1114111)}function Ze(e){if(e>65535){e-=65536;let a=55296+(e>>10),t=56320+(e&1023);return String.fromCharCode(a,t)}return String.fromCharCode(e)}var oo=/\\([!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~])/g,us=new RegExp(`${oo.source}|${/&([a-z#][a-z0-9]{1,31});/gi.source}`,"gi"),ps=/^#((?:x[a-f0-9]{1,8}|[0-9]{1,8}))$/i;function hs(e,a){if(a.charCodeAt(0)===35&&ps.test(a)){let r=a[1].toLowerCase()==="x"?parseInt(a.slice(2),16):parseInt(a.slice(1),10);return yt(r)?Ze(r):e}let t=ya(e);return t!==e?t:e}function fs(e){return e.indexOf("\\")<0?e:e.replace(oo,"$1")}function Ae(e){return e.indexOf("\\")<0&&e.indexOf("&")<0?e:e.replace(us,function(a,t,r){return t||hs(a,r)})}var ms=/[&<>"]/,vs=/[&<>"]/g,gs={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"};function bs(e){return gs[e]}function de(e){return ms.test(e)?e.replace(vs,bs):e}var ys=/[.?*+^$[\]\\(){}|-]/g;function ws(e){return e.replace(ys,"\\$&")}function q(e){switch(e){case 9:case 32:return!0}return!1}function Xe(e){if(e>=8192&&e<=8202)return!0;switch(e){case 9:case 10:case 11:case 12:case 13:case 32:case 160:case 5760:case 8239:case 8287:case 12288:return!0}return!1}function io(e){return Ue.test(e)||it.test(e)}function Ge(e){return io(Ze(e))}function Ve(e){switch(e){case 33:case 34:case 35:case 36:case 37:case 38:case 39:case 40:case 41:case 42:case 43:case 44:case 45:case 46:case 47:case 58:case 59:case 60:case 61:case 62:case 63:case 64:case 91:case 92:case 93:case 94:case 95:case 96:case 123:case 124:case 125:case 126:return!0;default:return!1}}function ka(e){return e=e.trim().replace(/\s+/g," "),e.toLowerCase().toUpperCase()}function Ur(e){return e===32||e===9||e===10||e===13}function Ca(e){let a=0;for(;a<e.length&&Ur(e.charCodeAt(a));a++);let t=e.length-1;for(;t>=a&&Ur(e.charCodeAt(t));t--);return e.slice(a,t+1)}var xs={mdurl:tt,ucmicro:st};function $s(e,a,t){let r,o,i,n,s=e.posMax,l=e.pos;for(e.pos=a+1,r=1;e.pos<s;){if(i=e.src.charCodeAt(e.pos),i===93&&(r--,r===0)){o=!0;break}if(n=e.pos,e.md.inline.skipToken(e),i===91){if(n===e.pos-1)r++;else if(t)return e.pos=l,-1}}let c=-1;return o&&(c=e.pos),e.pos=l,c}function ks(e,a,t){let r,o=a,i={ok:!1,pos:0,str:""};if(e.charCodeAt(o)===60){for(o++;o<t;){if(r=e.charCodeAt(o),r===10||r===60)return i;if(r===62)return i.pos=o+1,i.str=Ae(e.slice(a+1,o)),i.ok=!0,i;if(r===92&&o+1<t){o+=2;continue}o++}return i}let n=0;for(;o<t&&(r=e.charCodeAt(o),!(r===32||r<32||r===127));){if(r===92&&o+1<t){if(e.charCodeAt(o+1)===32){o++;continue}o+=2;continue}if(r===40&&(n++,n>32))return i;if(r===41){if(n===0)break;n--}o++}return a===o||n!==0||(i.str=Ae(e.slice(a,o)),i.pos=o,i.ok=!0),i}function Cs(e,a,t,r){let o,i=a,n={ok:!1,can_continue:!1,pos:0,str:"",marker:0};if(r)n.str=r.str,n.marker=r.marker;else{if(i>=t)return n;let s=e.charCodeAt(i);if(s!==34&&s!==39&&s!==40)return n;a++,i++,s===40&&(s=41),n.marker=s}for(;i<t;){if(o=e.charCodeAt(i),o===n.marker)return n.pos=i+1,n.str+=Ae(e.slice(a,i)),n.ok=!0,n;if(o===40&&n.marker===41)return n;o===92&&i+1<t&&i++,i++}return n.can_continue=!0,n.str+=Ae(e.slice(a,i)),n}var _s=to({parseLinkDestination:()=>ks,parseLinkLabel:()=>$s,parseLinkTitle:()=>Cs});function Ye(e){"@babel/helpers - typeof";return Ye=typeof Symbol=="function"&&typeof Symbol.iterator=="symbol"?function(a){return typeof a}:function(a){return a&&typeof Symbol=="function"&&a.constructor===Symbol&&a!==Symbol.prototype?"symbol":typeof a},Ye(e)}function Ds(e,a){if(Ye(e)!="object"||!e)return e;var t=e[Symbol.toPrimitive];if(t!==void 0){var r=t.call(e,a||"default");if(Ye(r)!="object")return r;throw new TypeError("@@toPrimitive must return a primitive value.")}return(a==="string"?String:Number)(e)}function Rs(e){var a=Ds(e,"string");return Ye(a)=="symbol"?a:a+""}function D(e,a,t){return(a=Rs(a))in e?Object.defineProperty(e,a,{value:t,enumerable:!0,configurable:!0,writable:!0}):e[a]=t,e}var be=class{constructor(e,a,t){D(this,"map",null),D(this,"level",0),D(this,"children",null),D(this,"content",""),D(this,"markup",""),D(this,"info",""),D(this,"block",!1),D(this,"hidden",!1),this.type=e,this.tag=a,this.attrs=null,this.nesting=t,this.meta=null}attrIndex(e){if(!this.attrs)return-1;let a=this.attrs;for(let t=0,r=a.length;t<r;t++)if(a[t][0]===e)return t;return-1}attrPush(e){this.attrs?this.attrs.push(e):this.attrs=[e]}attrSet(e,a){let t=this.attrIndex(e),r=[e,a];t<0?this.attrPush(r):this.attrs[t]=r}attrGet(e){let a=this.attrIndex(e),t=null;return a>=0&&(t=this.attrs[a][1]),t}attrJoin(e,a){let t=this.attrIndex(e);t<0?this.attrPush([e,a]):this.attrs[t][1]=`${this.attrs[t][1]} ${a}`}},Ke=class{constructor(){D(this,"__rules__",[]),D(this,"__cache__",null)}__find__(e){for(let a=0;a<this.__rules__.length;a++)if(this.__rules__[a].name===e)return a;return-1}__compile__(){let e=new Set;this.__rules__.forEach(a=>{a.enabled&&a.alt.forEach(t=>{t&&e.add(t)})}),this.__cache__=Object.create(null),this.__cache__[""]=[],this.__rules__.forEach(a=>{a.enabled&&this.__cache__[""].push(a.fn)}),e.forEach(a=>{this.__cache__[a]=[],this.__rules__.forEach(t=>{t.enabled&&t.alt.indexOf(a)>=0&&this.__cache__[a].push(t.fn)})})}at(e,a,t={}){let r=this.__find__(e);if(r===-1)throw new Error(`Parser rule not found: ${e}`);this.__rules__[r].fn=a,this.__rules__[r].alt=t.alt||[],this.__cache__=null}before(e,a,t,r={}){let o=this.__find__(e);if(o===-1)throw new Error(`Parser rule not found: ${e}`);this.__rules__.splice(o,0,{name:a,enabled:!0,fn:t,alt:r.alt||[]}),this.__cache__=null}after(e,a,t,r={}){let o=this.__find__(e);if(o===-1)throw new Error(`Parser rule not found: ${e}`);this.__rules__.splice(o+1,0,{name:a,enabled:!0,fn:t,alt:r.alt||[]}),this.__cache__=null}push(e,a,t={}){this.__rules__.push({name:e,enabled:!0,fn:a,alt:t.alt||[]}),this.__cache__=null}enable(e,a=!1){Array.isArray(e)||(e=[e]);let t=[];return e.forEach(r=>{let o=this.__find__(r);if(o<0){if(a)return;throw new Error(`Rules manager: invalid rule name ${r}`)}this.__rules__[o].enabled=!0,t.push(r)}),this.__cache__=null,t}enableOnly(e,a=!1){Array.isArray(e)||(e=[e]),this.__rules__.forEach(t=>{t.enabled=!1}),this.enable(e,a)}disable(e,a=!1){Array.isArray(e)||(e=[e]);let t=[];return e.forEach(r=>{let o=this.__find__(r);if(o<0){if(a)return;throw new Error(`Rules manager: invalid rule name ${r}`)}this.__rules__[o].enabled=!1,t.push(r)}),this.__cache__=null,t}getRules(e){return this.__cache__||this.__compile__(),this.__cache__[e]||[]}},te={};te.code_inline=function(e,a,t,r,o){let i=e[a];return`<code${o.renderAttrs(i)}>${de(i.content)}</code>`};te.code_block=function(e,a,t,r,o){let i=e[a];return`<pre${o.renderAttrs(i)}><code>${de(e[a].content)}</code></pre>
`};te.fence=function(e,a,t,r,o){let i=e[a],n=i.info?Ae(i.info).trim():"",s="",l="";if(n){let u=n.split(/(\s+)/g);s=u[0],l=u.slice(2).join("")}let c;if(t.highlight?c=t.highlight(i.content,s,l)||de(i.content):c=de(i.content),c.indexOf("<pre")===0)return c+`
`;if(n){let u=i.attrIndex("class"),h=i.attrs?i.attrs.slice():[];u<0?h.push(["class",`${t.langPrefix}${s}`]):(h[u]=[h[u][0],h[u][1]],h[u][1]+=` ${t.langPrefix}${s}`);let p={attrs:h};return`<pre><code${o.renderAttrs(p)}>${c}</code></pre>
`}return`<pre><code${o.renderAttrs(i)}>${c}</code></pre>
`};te.image=function(e,a,t,r,o){let i=e[a];return i.attrs[i.attrIndex("alt")][1]=o.renderInlineAsText(i.children,t,r),o.renderToken(e,a,t)};te.hardbreak=function(e,a,t){return t.xhtmlOut?`<br />
`:`<br>
`};te.softbreak=function(e,a,t){return t.breaks?t.xhtmlOut?`<br />
`:`<br>
`:`
`};te.text=function(e,a){return de(e[a].content)};te.html_block=function(e,a){return e[a].content};te.html_inline=function(e,a){return e[a].content};var no=class{constructor(){D(this,"rules",Object.assign({},te))}renderAttrs(e){let a,t,r;if(!e.attrs)return"";for(r="",a=0,t=e.attrs.length;a<t;a++)r+=` ${de(e.attrs[a][0])}="${de(String(e.attrs[a][1]))}"`;return r}renderToken(e,a,t){let r=e[a],o="";if(r.hidden)return"";let i=a-1;for(;i>=0&&e[i].hidden&&e[i].nesting===0;)i--;r.block&&r.nesting!==-1&&i>=0&&e[i].hidden&&e[i].nesting===-1&&(o+=`
`),o+=(r.nesting===-1?"</":"<")+r.tag,o+=this.renderAttrs(r),r.nesting===0&&t.xhtmlOut&&(o+=" /");let n=!1;if(r.block&&(n=!0,r.nesting===1)){let s=a+1;for(;s<e.length&&e[s].hidden&&e[s].nesting===0;)s++;if(s<e.length){let l=e[s];(l.type==="inline"||l.hidden||l.nesting===-1&&l.tag===r.tag)&&(n=!1)}}return o+=n?`>
`:">",o}renderInline(e,a,t){let r="",o=this.rules;for(let i=0,n=e.length;i<n;i++){let s=e[i].type;typeof o[s]<"u"?r+=o[s](e,i,a,t,this):r+=this.renderToken(e,i,a)}return r}renderInlineAsText(e,a,t){let r="";for(let o=0,i=e.length;o<i;o++)switch(e[o].type){case"text":case"code_inline":r+=e[o].content;break;case"image":r+=this.renderInlineAsText(e[o].children,a,t);break;case"html_inline":case"html_block":r+=e[o].content;break;case"softbreak":case"hardbreak":r+=`
`}return r}render(e,a,t){let r="",o=this.rules;for(let i=0,n=e.length;i<n;i++){let s=e[i].type;s==="inline"?r+=this.renderInline(e[i].children,a,t):typeof o[s]<"u"?r+=o[s](e,i,a,t,this):r+=this.renderToken(e,i,a)}return r}},so=class{constructor(e,a,t){D(this,"tokens",[]),D(this,"inlineMode",!1),D(this,"Token",be),this.src=e,this.env=t,this.md=a}},As=/\r\n?/g,Es=/\0/g;function Ss(e){let a;a=e.src.replace(As,`
`),a=a.replace(Es,"\uFFFD"),e.src=a}function Ps(e){let a;e.inlineMode?(a=new e.Token("inline","",0),a.content=e.src,a.map=[0,1],a.children=[],e.tokens.push(a)):e.md.block.parse(e.src,e.md,e.env,e.tokens)}function js(e){let a=e.tokens,t=0;for(let r=0;r<a.length;r++)a[r].type!=="reference_definition"&&(r!==t&&(a[t]=a[r]),t++);a.length!==t&&(a.length=t)}function qs(e){let a=e.tokens;for(let t=0,r=a.length;t<r;t++){let o=a[t];o.type==="inline"&&e.md.inline.parse(o.content,e.md,e.env,o.children)}}function Fs(e){return/^<a[>\s]/i.test(e)}function Ts(e){return/^<\/a\s*>/i.test(e)}function zs(e){let a=e.tokens;if(e.md.options.linkify)for(let t=0,r=a.length;t<r;t++){if(a[t].type!=="inline"||!e.md.linkify.test(a[t].content))continue;let o=a[t].children,i=[],n=0;for(let s=o.length-1;s>=0;s--){let l=o[s];if(l.type==="link_close"){for(s--;o[s].level!==l.level&&o[s].type!=="link_open";)s--;continue}if(l.type==="html_inline"&&(Fs(l.content)&&n>0&&n--,Ts(l.content)&&n++),!(n>0)&&l.type==="text"&&e.md.linkify.test(l.content)){let c=l.content,u=e.md.linkify.match(c),h=[],p=l.level,f=0;u.length>0&&u[0].index===0&&s>0&&o[s-1].type==="text_special"&&(u=u.slice(1));for(let m=0;m<u.length;m++){let b=u[m].url,w=e.md.normalizeLink(b);if(!e.md.validateLink(w))continue;let k=u[m].text;u[m].schema?u[m].schema==="mailto:"&&!/^mailto:/i.test(k)?k=e.md.normalizeLinkText(`mailto:${k}`).replace(/^mailto:/,""):k=e.md.normalizeLinkText(k):k=e.md.normalizeLinkText(`http://${k}`).replace(/^http:\/\//,"");let C=u[m].index;if(C>f){let _=new e.Token("text","",0);_.content=c.slice(f,C),_.level=p,h.push(_)}let v=new e.Token("link_open","a",1);v.attrs=[["href",w]],v.level=p++,v.markup="linkify",v.info="auto",h.push(v);let y=new e.Token("text","",0);y.content=k,y.level=p,h.push(y);let $=new e.Token("link_close","a",-1);$.level=--p,$.markup="linkify",$.info="auto",h.push($),f=u[m].lastIndex}if(f<c.length){let m=new e.Token("text","",0);m.content=c.slice(f),m.level=p,h.push(m)}i.push({index:s,nodes:h})}}if(i.length>0){let s=o.length;for(let h of i)s+=h.nodes.length-1;let l=new Array(s),c=0,u=0;i.reverse();for(let h=0;h<o.length;h++){let p=i[c];if(p?.index===h){for(let f of p.nodes)l[u++]=f;c++}else l[u++]=o[h]}a[t].children=l}}}var lo=/\+-|\.\.|\?\?\?\?|!!!!|,,|--/,Ms=/\((c|tm|r)\)/i,Js=/\((c|tm|r)\)/gi,Is={c:"\xA9",r:"\xAE",tm:"\u2122"};function Bs(e,a){return Is[a.toLowerCase()]}function Ls(e){let a=0;for(let t=e.length-1;t>=0;t--){let r=e[t];r.type==="text"&&!a&&(r.content=r.content.replace(Js,Bs)),r.type==="link_open"&&r.info==="auto"&&a--,r.type==="link_close"&&r.info==="auto"&&a++}}function Ns(e){let a=0;for(let t=e.length-1;t>=0;t--){let r=e[t];r.type==="text"&&!a&&lo.test(r.content)&&(r.content=r.content.replace(/\+-/g,"\xB1").replace(/\.{2,}/g,"\u2026").replace(/([?!])…/g,"$1..").replace(/([?!]){4,}/g,"$1$1$1").replace(/,{2,}/g,",").replace(/(^|[^-])---(?=[^-]|$)/gm,"$1\u2014").replace(/(^|\s)--(?=\s|$)/gm,"$1\u2013").replace(/(^|[^-\s])--(?=[^-\s]|$)/gm,"$1\u2013")),r.type==="link_open"&&r.info==="auto"&&a--,r.type==="link_close"&&r.info==="auto"&&a++}}function Os(e){let a;if(e.md.options.typographer)for(a=e.tokens.length-1;a>=0;a--)e.tokens[a].type==="inline"&&(Ms.test(e.tokens[a].content)&&Ls(e.tokens[a].children),lo.test(e.tokens[a].content)&&Ns(e.tokens[a].children))}var Hs=/['"]/,Wr=/['"]/g,Zr="\u2019",Us=1e3;function Xr(e,a,t){for(;e.length>t;){let r=e.pop();r.isSingleQuote?a.single=r.prevSameQuoteIdx:a.double=r.prevSameQuoteIdx}}function wa(e,a,t,r){e[a]||(e[a]=[]),e[a].push({pos:t,ch:r})}function Ws(e,a){let t="",r=0;a.sort((o,i)=>o.pos-i.pos);for(let o=0;o<a.length;o++){let i=a[o];t+=e.slice(r,i.pos)+i.ch,r=i.pos+1}return t+e.slice(r)}function Zs(e,a){let t,r=[],o={single:-1,double:-1},i={};for(let n=0;n<e.length;n++){let s=e[n],l=e[n].level;for(t=r.length-1;t>=0&&!(r[t].level<=l);t--);if(Xr(r,o,t+1),s.type!=="text")continue;let c=s.content,u=0,h=c.length;e:for(;u<h;){Wr.lastIndex=u;let p=Wr.exec(c);if(!p)break;let f=!0,m=!0;u=p.index+1;let b=p[0]==="'",w=32;if(p.index-1>=0)w=c.charCodeAt(p.index-1);else for(t=n-1;t>=0&&!(e[t].type==="softbreak"||e[t].type==="hardbreak");t--)if(e[t].content){w=e[t].content.charCodeAt(e[t].content.length-1);break}let k=32;if(u<h)k=c.charCodeAt(u);else for(t=n+1;t<e.length&&!(e[t].type==="softbreak"||e[t].type==="hardbreak");t++)if(e[t].content){k=e[t].content.charCodeAt(0);break}let C=Ve(w)||Ge(w),v=Ve(k)||Ge(k),y=Xe(w),$=Xe(k);if($?f=!1:v&&(y||C||(f=!1)),y?m=!1:C&&($||v||(m=!1)),k===34&&p[0]==='"'&&w>=48&&w<=57&&(m=f=!1),f&&m&&(f=C,m=v),!f&&!m){b&&wa(i,n,p.index,Zr);continue}if(m&&(t=b?o.single:o.double,t>=0&&r[t].level===l)){let _=r[t],A,j;b?(A=a.md.options.quotes[2],j=a.md.options.quotes[3]):(A=a.md.options.quotes[0],j=a.md.options.quotes[1]),wa(i,n,p.index,j),wa(i,_.tokenIdx,_.contentPos,A),Xr(r,o,t);continue e}if(f){if(r.length>=Us)return;r.push({tokenIdx:n,contentPos:p.index,isSingleQuote:b,level:l,prevSameQuoteIdx:b?o.single:o.double}),b?o.single=r.length-1:o.double=r.length-1}else m&&b&&wa(i,n,p.index,Zr)}}Object.keys(i).forEach(function(n){let s=Number(n);e[s].content=Ws(e[s].content,i[n])})}function Xs(e){if(e.md.options.typographer)for(let a=e.tokens.length-1;a>=0;a--)e.tokens[a].type!=="inline"||!Hs.test(e.tokens[a].content)||Zs(e.tokens[a].children,e)}function Gs(e){let a,t,r=e.length;for(a=0;a<r;a++)e[a].type==="text_special"&&(e[a].type="text");for(a=t=0;a<r;a++)e[a].type==="text"&&a+1<r&&e[a+1].type==="text"?e[a+1].content=e[a].content+e[a+1].content:(a!==t&&(e[t]=e[a]),t++);a!==t&&(e.length=t)}function Vs(e){let a,t,r=e.tokens,o=r.length;for(let i=0;i<o;i++){if(r[i].type!=="inline")continue;let n=r[i].children,s=n.length;for(a=0;a<s;a++)n[a].type==="text_special"&&(n[a].type="text"),n[a].children&&Gs(n[a].children);for(a=t=0;a<s;a++)n[a].type==="text"&&a+1<s&&n[a+1].type==="text"?n[a+1].content=n[a].content+n[a+1].content:(a!==t&&(n[t]=n[a]),t++);a!==t&&(n.length=t)}}var ft=[["normalize",Ss],["block",Ps],["strip_references",js],["inline",qs],["linkify",zs],["replacements",Os],["smartquotes",Xs],["text_join",Vs]],co=class{constructor(){D(this,"ruler",new Ke),D(this,"State",so);for(let e=0;e<ft.length;e++)this.ruler.push(ft[e][0],ft[e][1])}process(e){let a=this.ruler.getRules("");for(let t=0,r=a.length;t<r;t++)a[t](e)}},uo=class{constructor(e,a,t,r){D(this,"bMarks",[]),D(this,"eMarks",[]),D(this,"tShift",[]),D(this,"sCount",[]),D(this,"bsCount",[]),D(this,"blkIndent",0),D(this,"line",0),D(this,"lineMax",0),D(this,"tight",!1),D(this,"listIndent",-1),D(this,"parentType","root"),D(this,"level",0),D(this,"Token",be),this.src=e,this.md=a,this.env=t,this.tokens=r;let o=this.src;for(let i=0,n=0,s=0,l=0,c=o.length,u=!1;n<c;n++){let h=o.charCodeAt(n);if(!u)if(q(h)){s++,h===9?l+=4-l%4:l++;continue}else u=!0;(h===10||n===c-1)&&(h!==10&&n++,this.bMarks.push(i),this.eMarks.push(n),this.tShift.push(s),this.sCount.push(l),this.bsCount.push(0),u=!1,s=0,l=0,i=n+1)}this.bMarks.push(o.length),this.eMarks.push(o.length),this.tShift.push(0),this.sCount.push(0),this.bsCount.push(0),this.lineMax=this.bMarks.length-1}push(e,a,t){let r=new be(e,a,t);return r.block=!0,t<0&&this.level--,r.level=this.level,t>0&&this.level++,this.tokens.push(r),r}isEmpty(e){return this.bMarks[e]+this.tShift[e]>=this.eMarks[e]}skipEmptyLines(e){for(let a=this.lineMax;e<a&&!(this.bMarks[e]+this.tShift[e]<this.eMarks[e]);e++);return e}skipSpaces(e){for(let a=this.src.length;e<a&&q(this.src.charCodeAt(e));e++);return e}skipSpacesBack(e,a){if(e<=a)return e;for(;e>a;)if(!q(this.src.charCodeAt(--e)))return e+1;return e}skipChars(e,a){for(let t=this.src.length;e<t&&this.src.charCodeAt(e)===a;e++);return e}skipCharsBack(e,a,t){if(e<=t)return e;for(;e>t;)if(a!==this.src.charCodeAt(--e))return e+1;return e}getLines(e,a,t,r){if(e>=a)return"";let o=new Array(a-e);for(let i=0,n=e;n<a;n++,i++){let s=0,l=this.bMarks[n],c=l,u;for(n+1<a||r?u=this.eMarks[n]+1:u=this.eMarks[n];c<u&&s<t;){let h=this.src.charCodeAt(c);if(q(h))h===9?s+=4-(s+this.bsCount[n])%4:s++;else if(c-l<this.tShift[n])s++;else break;c++}s>t?o[i]=new Array(s-t+1).join(" ")+this.src.slice(c,u):o[i]=this.src.slice(c,u)}return o.join("")}},Ys=65536;function mt(e,a){let t=e.bMarks[a]+e.tShift[a],r=e.eMarks[a];return e.src.slice(t,r)}function Gr(e){let a=[],t=e.length,r=0,o=e.charCodeAt(r),i=!1,n=0,s="";for(;r<t;)o===124&&(i?(s+=e.substring(n,r-1),n=r):(a.push(s+e.substring(n,r)),s="",n=r+1)),i=o===92,r++,o=e.charCodeAt(r);return a.push(s+e.substring(n)),a}function Ks(e,a,t,r){if(a+2>t)return!1;let o=a+1;if(e.sCount[o]<e.blkIndent||e.sCount[o]-e.blkIndent>=4)return!1;let i=e.bMarks[o]+e.tShift[o];if(i>=e.eMarks[o])return!1;let n=e.src.charCodeAt(i++);if(n!==124&&n!==45&&n!==58||i>=e.eMarks[o])return!1;let s=e.src.charCodeAt(i++);if(s!==124&&s!==45&&s!==58&&!q(s)||n===45&&q(s))return!1;for(;i<e.eMarks[o];){let y=e.src.charCodeAt(i);if(y!==124&&y!==45&&y!==58&&!q(y))return!1;i++}let l=mt(e,a+1),c=l.split("|"),u=[];for(let y=0;y<c.length;y++){let $=c[y].trim();if(!$){if(y===0||y===c.length-1)continue;return!1}if(!/^:?-+:?$/.test($))return!1;$.charCodeAt($.length-1)===58?u.push($.charCodeAt(0)===58?"center":"right"):$.charCodeAt(0)===58?u.push("left"):u.push("")}if(l=mt(e,a).trim(),l.indexOf("|")===-1||e.sCount[a]-e.blkIndent>=4)return!1;c=Gr(l),c.length&&c[0]===""&&c.shift(),c.length&&c[c.length-1]===""&&c.pop();let h=c.length;if(h===0||h!==u.length)return!1;if(r)return!0;let p=e.parentType;e.parentType="table";let f=e.md.block.ruler.getRules("blockquote"),m=e.push("table_open","table",1),b=[a,0];m.map=b;let w=e.push("thead_open","thead",1);w.map=[a,a+1];let k=e.push("tr_open","tr",1);k.map=[a,a+1];for(let y=0;y<c.length;y++){let $=e.push("th_open","th",1);u[y]&&($.attrs=[["style",`text-align:${u[y]}`]]);let _=e.push("inline","",0);_.content=c[y].trim(),_.children=[],e.push("th_close","th",-1)}e.push("tr_close","tr",-1),e.push("thead_close","thead",-1);let C,v=0;for(o=a+2;o<t&&!(e.sCount[o]<e.blkIndent);o++){let y=!1;for(let _=0,A=f.length;_<A;_++)if(f[_](e,o,t,!0)){y=!0;break}if(y||(l=mt(e,o).trim(),!l)||e.sCount[o]-e.blkIndent>=4||(c=Gr(l),c.length&&c[0]===""&&c.shift(),c.length&&c[c.length-1]===""&&c.pop(),v+=h-c.length,v>Ys))break;if(o===a+2){let _=e.push("tbody_open","tbody",1);_.map=C=[a+2,0]}let $=e.push("tr_open","tr",1);$.map=[o,o+1];for(let _=0;_<h;_++){let A=e.push("td_open","td",1);u[_]&&(A.attrs=[["style",`text-align:${u[_]}`]]);let j=e.push("inline","",0);j.content=c[_]?c[_].trim():"",j.children=[],e.push("td_close","td",-1)}e.push("tr_close","tr",-1)}return C&&(e.push("tbody_close","tbody",-1),C[1]=o),e.push("table_close","table",-1),b[1]=o,e.parentType=p,e.line=o,!0}function Qs(e,a,t){if(e.sCount[a]-e.blkIndent<4)return!1;let r=a+1,o=r;for(;r<t;){if(e.isEmpty(r)){r++;continue}if(e.sCount[r]-e.blkIndent>=4){r++,o=r;continue}break}e.line=o;let i=e.push("code_block","code",0);return i.content=e.getLines(a,o,4+e.blkIndent,!1)+`
`,i.map=[a,e.line],!0}function el(e,a,t,r){let o=e.bMarks[a]+e.tShift[a],i=e.eMarks[a];if(e.sCount[a]-e.blkIndent>=4||o+3>i)return!1;let n=e.src.charCodeAt(o);if(n!==126&&n!==96)return!1;let s=o;o=e.skipChars(o,n);let l=o-s;if(l<3)return!1;let c=e.src.slice(s,o),u=e.src.slice(o,i);if(n===96&&u.indexOf(String.fromCharCode(n))>=0)return!1;if(r)return!0;let h=a,p=!1;for(;h++,!(h>=t||(o=s=e.bMarks[h]+e.tShift[h],i=e.eMarks[h],o<i&&e.sCount[h]<e.blkIndent));)if(e.src.charCodeAt(o)===n&&!(e.sCount[h]-e.blkIndent>=4)&&(o=e.skipChars(o,n),!(o-s<l)&&(o=e.skipSpaces(o),!(o<i)))){p=!0;break}l=e.sCount[a],e.line=h+(p?1:0);let f=e.push("fence","code",0);return f.info=u,f.content=e.getLines(a+1,h,l,!0),f.markup=c,f.map=[a,e.line],!0}function al(e,a,t,r){let o=e.bMarks[a]+e.tShift[a],i=e.eMarks[a],n=e.lineMax;if(e.sCount[a]-e.blkIndent>=4||e.src.charCodeAt(o)!==62)return!1;if(r)return!0;let s=[],l=[],c=[],u=[],h=e.md.block.ruler.getRules("blockquote"),p=e.parentType;e.parentType="blockquote";let f=!1,m;for(m=a;m<t;m++){let v=e.sCount[m]<e.blkIndent;if(o=e.bMarks[m]+e.tShift[m],i=e.eMarks[m],o>=i)break;if(e.src.charCodeAt(o++)===62&&!v){let $=e.sCount[m]+1,_,A;e.src.charCodeAt(o)===32?(o++,$++,A=!1,_=!0):e.src.charCodeAt(o)===9?(_=!0,(e.bsCount[m]+$)%4===3?(o++,$++,A=!1):A=!0):_=!1;let j=$;for(s.push(e.bMarks[m]),e.bMarks[m]=o;o<i;){let E=e.src.charCodeAt(o);if(q(E))E===9?j+=4-(j+e.bsCount[m]+(A?1:0))%4:j++;else break;o++}f=o>=i,l.push(e.bsCount[m]),e.bsCount[m]=e.sCount[m]+1+(_?1:0),c.push(e.sCount[m]),e.sCount[m]=j-$,u.push(e.tShift[m]),e.tShift[m]=o-e.bMarks[m];continue}if(f)break;let y=!1;for(let $=0,_=h.length;$<_;$++)if(h[$](e,m,t,!0)){y=!0;break}if(y){e.lineMax=m,e.blkIndent!==0&&(s.push(e.bMarks[m]),l.push(e.bsCount[m]),u.push(e.tShift[m]),c.push(e.sCount[m]),e.sCount[m]-=e.blkIndent);break}s.push(e.bMarks[m]),l.push(e.bsCount[m]),u.push(e.tShift[m]),c.push(e.sCount[m]),e.sCount[m]=-1}let b=e.blkIndent;e.blkIndent=0;let w=e.push("blockquote_open","blockquote",1);w.markup=">";let k=[a,0];w.map=k,e.md.block.tokenize(e,a,m);let C=e.push("blockquote_close","blockquote",-1);C.markup=">",e.lineMax=n,e.parentType=p,k[1]=e.line;for(let v=0;v<u.length;v++)e.bMarks[v+a]=s[v],e.tShift[v+a]=u[v],e.sCount[v+a]=c[v],e.bsCount[v+a]=l[v];return e.blkIndent=b,!0}function tl(e,a,t,r){let o=e.eMarks[a];if(e.sCount[a]-e.blkIndent>=4)return!1;let i=e.bMarks[a]+e.tShift[a],n=e.src.charCodeAt(i++);if(n!==42&&n!==45&&n!==95)return!1;let s=1;for(;i<o;){let c=e.src.charCodeAt(i++);if(c!==n&&!q(c))return!1;c===n&&s++}if(s<3)return!1;if(r)return!0;e.line=a+1;let l=e.push("hr","hr",0);return l.map=[a,e.line],l.markup=Array(s+1).join(String.fromCharCode(n)),!0}function Vr(e,a){let t=e.eMarks[a],r=e.bMarks[a]+e.tShift[a],o=e.src.charCodeAt(r++);return o!==42&&o!==45&&o!==43||r<t&&!q(e.src.charCodeAt(r))?-1:r}function Yr(e,a){let t=e.bMarks[a]+e.tShift[a],r=e.eMarks[a],o=t;if(o+1>=r)return-1;let i=e.src.charCodeAt(o++);if(i<48||i>57)return-1;for(;;){if(o>=r)return-1;if(i=e.src.charCodeAt(o++),i>=48&&i<=57){if(o-t>=10)return-1;continue}if(i===41||i===46)break;return-1}return o<r&&(i=e.src.charCodeAt(o),!q(i))?-1:o}function rl(e,a){let t=e.level+2;for(let r=a+2,o=e.tokens.length-2;r<o;r++)e.tokens[r].level===t&&e.tokens[r].type==="paragraph_open"&&(e.tokens[r+2].hidden=!0,e.tokens[r].hidden=!0,r+=2)}function ol(e,a,t,r){let o,i,n,s,l=a,c=!0;if(e.sCount[l]-e.blkIndent>=4||e.listIndent>=0&&e.sCount[l]-e.listIndent>=4&&e.sCount[l]<e.blkIndent)return!1;let u=!1;r&&e.parentType==="paragraph"&&e.sCount[l]>=e.blkIndent&&(u=!0);let h,p,f;if((f=Yr(e,l))>=0){if(h=!0,n=e.bMarks[l]+e.tShift[l],p=Number(e.src.slice(n,f-1)),u&&p!==1)return!1}else if((f=Vr(e,l))>=0)h=!1;else return!1;if(u&&e.skipSpaces(f)>=e.eMarks[l])return!1;if(r)return!0;let m=e.src.charCodeAt(f-1),b=e.tokens.length;h?(s=e.push("ordered_list_open","ol",1),p!==1&&(s.attrs=[["start",p]])):s=e.push("bullet_list_open","ul",1);let w=[l,0];s.map=w,s.markup=String.fromCharCode(m);let k=!1,C=e.md.block.ruler.getRules("list"),v=e.parentType;for(e.parentType="list";l<t;){i=f,o=e.eMarks[l];let y=e.sCount[l]+f-(e.bMarks[l]+e.tShift[l]),$=y;for(;i<o;){let W=e.src.charCodeAt(i);if(W===9)$+=4-($+e.bsCount[l])%4;else if(W===32)$++;else break;i++}let _=i,A;_>=o?A=1:A=$-y,A>4&&(A=1);let j=y+A;s=e.push("list_item_open","li",1),s.markup=String.fromCharCode(m);let E=[l,0];s.map=E,h&&(s.info=e.src.slice(n,f-1));let F=e.tight,R=e.tShift[l],N=e.sCount[l],Y=e.listIndent;if(e.listIndent=e.blkIndent,e.blkIndent=j,e.tight=!0,e.tShift[l]=_-e.bMarks[l],e.sCount[l]=$,_>=o&&e.isEmpty(l+1)?e.line=Math.min(e.line+2,t):e.md.block.tokenize(e,l,t),(!e.tight||k)&&(c=!1),k=e.line-l>1&&e.isEmpty(e.line-1),e.blkIndent=e.listIndent,e.listIndent=Y,e.tShift[l]=R,e.sCount[l]=N,e.tight=F,s=e.push("list_item_close","li",-1),s.markup=String.fromCharCode(m),l=e.line,E[1]=l,l>=t||e.sCount[l]<e.blkIndent||e.sCount[l]-e.blkIndent>=4)break;let X=!1;for(let W=0,cn=C.length;W<cn;W++)if(C[W](e,l,t,!0)){X=!0;break}if(X)break;if(h){if(f=Yr(e,l),f<0)break;n=e.bMarks[l]+e.tShift[l]}else if(f=Vr(e,l),f<0)break;if(m!==e.src.charCodeAt(f-1))break}return h?s=e.push("ordered_list_close","ol",-1):s=e.push("bullet_list_close","ul",-1),s.markup=String.fromCharCode(m),w[1]=l,e.line=l,e.parentType=v,c&&rl(e,b),!0}var vt=999;function il(e){let a=e.length;for(let t=0;t<e.length-1;t++){let r=e.charCodeAt(t);if(r<55296||r>56319)continue;let o=e.charCodeAt(t+1);o>=56320&&o<=57343&&(a--,t++)}return a}function We(e,a){return Math.min(e.eMarks[a]+1,e.src.length)}function xa(e,a){let t=e.lineMax;if(a>=t||e.isEmpty(a))return-1;let r=!1;if(e.sCount[a]-e.blkIndent>3&&(r=!0),e.sCount[a]<0&&(r=!0),!r){let o=e.md.block.ruler.getRules("reference"),i=e.parentType;e.parentType="reference";let n=!1;for(let s=0,l=o.length;s<l;s++)if(o[s](e,a,t,!0)){n=!0;break}if(e.parentType=i,n)return-1}return e.bMarks[a]+e.tShift[a]}function nl(e,a,t,r){let o=e.src,i=e.bMarks[a]+e.tShift[a],n=a+1;if(e.sCount[a]-e.blkIndent>=4||o.charCodeAt(i)!==91)return!1;let s=We(e,a),l="",c=-1,u=++i;for(;i<s;){if(l.length+i-u>vt*2)return!1;let _=o.charCodeAt(i);if(_===91)return!1;if(_===93){c=i;break}if(_===92&&(_=o.charCodeAt(++i)),_===10&&i<s){let A=xa(e,n);if(A<0)return!1;l+=o.slice(u,s),i=u=A,s=We(e,n++);continue}i++}if(c<0||o.charCodeAt(c+1)!==58||(l+=o.slice(u,c),l.length>vt&&il(l)>vt))return!1;for(i=c+2;i<s;){let _=o.charCodeAt(i);if(_===10){let A=xa(e,n);if(A<0)break;i=A,s=We(e,n++)}else if(q(_))i++;else break}let h=e.md.helpers.parseLinkDestination(o,i,s);if(!h.ok)return!1;let p=e.md.normalizeLink(h.str);if(!e.md.validateLink(p))return!1;i=h.pos;let f=i,m=s,b=n;for(;i<s;){let _=o.charCodeAt(i);if(_===10){let A=xa(e,n);if(A<0)break;i=A,s=We(e,n++)}else if(q(_))i++;else break}let w=i,k=e.md.helpers.parseLinkTitle(o,i,s);for(;k.can_continue;){let _=xa(e,n);if(_<0)break;i=_,s=We(e,n++),k=e.md.helpers.parseLinkTitle(o,i,s,k)}let C;for(w!==f&&k.ok?(C=k.str,i=k.pos):(C="",i=f,s=m,n=b);i<s&&q(o.charCodeAt(i));)i++;if(i<s&&o.charCodeAt(i)!==10&&C)for(C="",i=f,s=m,n=b;i<s&&q(o.charCodeAt(i));)i++;if(i<s&&o.charCodeAt(i)!==10)return!1;let v=ka(l);if(!v)return!1;if(r)return!0;typeof e.env.references>"u"&&(e.env.references={}),typeof e.env.references[v]>"u"&&(e.env.references[v]={title:C,href:p});let y=e.push("reference_definition","",0);y.map=[a,n],y.hidden=!0;let $=Object.create(null);return $.label=v,y.meta=$,e.line=n,!0}var sl=["address","article","aside","base","basefont","blockquote","body","caption","center","col","colgroup","dd","details","dialog","dir","div","dl","dt","fieldset","figcaption","figure","footer","form","frame","frameset","h1","h2","h3","h4","h5","h6","head","header","hr","html","iframe","legend","li","link","main","menu","menuitem","nav","noframes","ol","optgroup","option","p","param","search","section","summary","table","tbody","td","tfoot","th","thead","title","tr","track","ul"],po=`<[A-Za-z][A-Za-z0-9\\-]*(?:\\s+[a-zA-Z_:][a-zA-Z0-9:._-]*(?:\\s*=\\s*(?:[^"'=<>\`\\x00-\\x20]+|'[^']*'|"[^"]*"))?)*\\s*\\/?>`,ho="<\\/[A-Za-z][A-Za-z0-9\\-]*\\s*>";new RegExp(`^(?:${po}|${ho}|<!---?>|<!--(?:[^-]|-[^-]|--[^>])*-->|<[?][\\s\\S]*?[?]>|<![A-Za-z][^>]*>|<!\\[CDATA\\[[\\s\\S]*?\\]\\]>)`);var fo=new RegExp(`^(?:${po}|${ho})`),ge=[[/^<(script|pre|style|textarea)(?=(\s|>|$))/i,/<\/(script|pre|style|textarea)>/i,!0],[/^<!--/,/-->/,!0],[/^<\?/,/\?>/,!0],[/^<![A-Za-z]/,/>/,!0],[/^<!\[CDATA\[/,/\]\]>/,!0],[new RegExp(`^</?(${sl.join("|")})(?=(\\s|/?>|$))`,"i"),/^$/,!0],[new RegExp(`${fo.source}\\s*$`),/^$/,!1]];function ll(e,a,t,r){let o=e.bMarks[a]+e.tShift[a],i=e.eMarks[a];if(e.sCount[a]-e.blkIndent>=4||!e.md.options.html||e.src.charCodeAt(o)!==60)return!1;let n=e.src.slice(o,i),s=0;for(;s<ge.length&&!ge[s][0].test(n);s++);if(s===ge.length)return!1;if(r)return ge[s][2];let l=a+1,c=ge[s][1].test("");if(!ge[s][1].test(n)){for(;l<t&&!(e.sCount[l]<e.blkIndent&&(c||!e.isEmpty(l)));l++)if(o=e.bMarks[l]+e.tShift[l],i=e.eMarks[l],n=e.src.slice(o,i),ge[s][1].test(n)){n.length!==0&&l++;break}}e.line=l;let u=e.push("html_block","",0);return u.map=[a,l],u.content=e.getLines(a,l,e.blkIndent,!0),!0}function cl(e,a,t,r){let o=e.bMarks[a]+e.tShift[a],i=e.eMarks[a];if(e.sCount[a]-e.blkIndent>=4)return!1;let n=e.src.charCodeAt(o);if(n!==35||o>=i)return!1;let s=1;for(n=e.src.charCodeAt(++o);n===35&&o<i&&s<=6;)s++,n=e.src.charCodeAt(++o);if(s>6||o<i&&!q(n))return!1;if(r)return!0;i=e.skipSpacesBack(i,o);let l=e.skipCharsBack(i,35,o);l>o&&q(e.src.charCodeAt(l-1))&&(i=l),e.line=a+1;let c=e.push("heading_open",`h${s}`,1);c.markup="########".slice(0,s),c.map=[a,e.line];let u=e.push("inline","",0);u.content=Ca(e.src.slice(o,i)),u.map=[a,e.line],u.children=[];let h=e.push("heading_close",`h${s}`,-1);return h.markup="########".slice(0,s),!0}function dl(e,a,t){let r=e.md.block.ruler.getRules("paragraph");if(e.sCount[a]-e.blkIndent>=4)return!1;let o=e.parentType;e.parentType="paragraph";let i=0,n,s=a+1;for(;s<t&&!e.isEmpty(s);s++){if(e.sCount[s]-e.blkIndent>3)continue;if(e.sCount[s]>=e.blkIndent){let f=e.bMarks[s]+e.tShift[s],m=e.eMarks[s];if(f<m&&(n=e.src.charCodeAt(f),(n===45||n===61)&&(f=e.skipChars(f,n),f=e.skipSpaces(f),f>=m))){i=n===61?1:2;break}}if(e.sCount[s]<0)continue;let p=!1;for(let f=0,m=r.length;f<m;f++)if(r[f](e,s,t,!0)){p=!0;break}if(p)break}if(!i)return e.parentType=o,!1;let l=Ca(e.getLines(a,s,e.blkIndent,!1));e.line=s+1;let c=e.push("heading_open",`h${i}`,1);c.markup=String.fromCharCode(n),c.map=[a,e.line];let u=e.push("inline","",0);u.content=l,u.map=[a,e.line-1],u.children=[];let h=e.push("heading_close",`h${i}`,-1);return h.markup=String.fromCharCode(n),e.parentType=o,!0}function ul(e,a,t){let r=e.md.block.ruler.getRules("paragraph"),o=e.parentType,i=a+1;for(e.parentType="paragraph";i<t&&!e.isEmpty(i);i++){if(e.sCount[i]-e.blkIndent>3||e.sCount[i]<0)continue;let c=!1;for(let u=0,h=r.length;u<h;u++)if(r[u](e,i,t,!0)){c=!0;break}if(c)break}let n=Ca(e.getLines(a,i,e.blkIndent,!1));e.line=i;let s=e.push("paragraph_open","p",1);s.map=[a,e.line];let l=e.push("inline","",0);return l.content=n,l.map=[a,e.line],l.children=[],e.push("paragraph_close","p",-1),e.parentType=o,!0}var $a=[["table",Ks,["paragraph","reference"]],["code",Qs],["fence",el,["paragraph","reference","blockquote","list"]],["blockquote",al,["paragraph","reference","blockquote","list"]],["hr",tl,["paragraph","reference","blockquote","list"]],["list",ol,["paragraph","reference","blockquote"]],["reference",nl],["html_block",ll,["paragraph","reference","blockquote"]],["heading",cl,["paragraph","reference","blockquote"]],["lheading",dl],["paragraph",ul]],mo=class{constructor(){D(this,"ruler",new Ke),D(this,"State",uo);for(let e=0;e<$a.length;e++)this.ruler.push($a[e][0],$a[e][1],{alt:($a[e][2]||[]).slice()})}tokenize(e,a,t){let r=this.ruler.getRules(""),o=r.length,i=e.md.options.maxNesting,n=a,s=!1;for(;n<t&&(e.line=n=e.skipEmptyLines(n),!(n>=t||e.sCount[n]<e.blkIndent));){if(e.level>=i){e.line=t;break}let l=e.line,c=!1;for(let u=0;u<o;u++)if(c=r[u](e,n,t,!1),c){if(l>=e.line)throw new Error("block rule didn't increment state.line");break}if(!c)throw new Error("none of the block rules matched");e.tight=!s,e.isEmpty(e.line-1)&&(s=!0),n=e.line,n<t&&e.isEmpty(n)&&(s=!0,n++,e.line=n)}}parse(e,a,t,r){if(!e)return;let o=new this.State(e,a,t,r);this.tokenize(o,o.line,o.lineMax)}},vo=class{constructor(e,a,t,r){D(this,"pos",0),D(this,"level",0),D(this,"pending",""),D(this,"pendingLevel",0),D(this,"cache",{}),D(this,"backticks",{}),D(this,"backticksScanned",!1),D(this,"skipHtmlSpecial",!1),D(this,"linkLevel",0),D(this,"delimiters",[]),D(this,"_prev_delimiters",[]),D(this,"Token",be),this.src=e,this.env=t,this.md=a,this.tokens=r,this.tokens_meta=Array(r.length),this.posMax=this.src.length}pushPending(){let e=new be("text","",0);return e.content=this.pending,e.level=this.pendingLevel,this.tokens.push(e),this.pending="",e}push(e,a,t){this.pending&&this.pushPending();let r=new be(e,a,t),o;return t<0&&(this.level--,this.delimiters=this._prev_delimiters.pop()),r.level=this.level,t>0&&(this.level++,this._prev_delimiters.push(this.delimiters),this.delimiters=[],o={delimiters:this.delimiters}),this.pendingLevel=this.level,this.tokens.push(r),this.tokens_meta.push(o),r}scanDelims(e,a){let t=this.posMax,r=this.src.charCodeAt(e),o;if(e===0)o=32;else if(e===1)o=this.src.charCodeAt(0),(o&63488)===55296&&(o=65533);else if(o=this.src.charCodeAt(e-1),(o&64512)===56320){let m=this.src.charCodeAt(e-2);o=(m&64512)===55296?65536+(m-55296<<10)+(o-56320):65533}else(o&64512)===55296&&(o=65533);let i=e;for(;i<t&&this.src.charCodeAt(i)===r;)i++;let n=i-e,s=i<t?this.src.charCodeAt(i):32;if((s&64512)===55296){let m=this.src.charCodeAt(i+1);s=(m&64512)===56320?65536+(s-55296<<10)+(m-56320):65533}else(s&64512)===56320&&(s=65533);let l=Ve(o)||Ge(o),c=Ve(s)||Ge(s),u=Xe(o),h=Xe(s),p=!h&&(!c||u||l),f=!u&&(!l||h||c);return{can_open:p&&(a||!f||l),can_close:f&&(a||!p||c),length:n}}};function pl(e){switch(e){case 10:case 33:case 35:case 36:case 37:case 38:case 42:case 43:case 45:case 58:case 60:case 61:case 62:case 64:case 91:case 92:case 93:case 94:case 95:case 96:case 123:case 125:case 126:return!0;default:return!1}}function hl(e,a){let t=e.pos;for(;t<e.posMax&&!pl(e.src.charCodeAt(t));)t++;return t===e.pos?!1:(a||(e.pending+=e.src.slice(e.pos,t)),e.pos=t,!0)}function fl(e){return e>=65&&e<=90||e>=97&&e<=122}function ml(e){return e>=65&&e<=90||e>=97&&e<=122||e>=48&&e<=57||e===43||e===45||e===46}function vl(e,a){if(!e.md.options.linkify||e.linkLevel>0)return!1;let t=e.pos,r=e.posMax;if(t+3>r||e.src.charCodeAt(t)!==58||e.src.charCodeAt(t+1)!==47||e.src.charCodeAt(t+2)!==47)return!1;let o=t-Math.min(10,e.pending.length,t),i=t;for(;i>o&&ml(e.src.charCodeAt(i-1));)i--;if(i===t||!fl(e.src.charCodeAt(i)))return!1;let n=t-i,s=e.md.linkify.matchAtStart(e.src.slice(i));if(!s)return!1;let l=s.url;if(l.length<=n)return!1;let c=l.length;for(;c>0&&l.charCodeAt(c-1)===42;)c--;c!==l.length&&(l=l.slice(0,c));let u=e.md.normalizeLink(l);if(!e.md.validateLink(u))return!1;if(!a){e.pending=e.pending.slice(0,-n);let h=e.push("link_open","a",1);h.attrs=[["href",u]],h.markup="linkify",h.info="auto";let p=e.push("text","",0);p.content=e.md.normalizeLinkText(l);let f=e.push("link_close","a",-1);f.markup="linkify",f.info="auto"}return e.pos+=l.length-n,!0}function gl(e,a){let t=e.pos;if(e.src.charCodeAt(t)!==10)return!1;let r=e.pending.length-1,o=e.posMax;if(!a)if(r>=0&&e.pending.charCodeAt(r)===32)if(r>=1&&e.pending.charCodeAt(r-1)===32){let i=r-1;for(;i>=1&&e.pending.charCodeAt(i-1)===32;)i--;e.pending=e.pending.slice(0,i),e.push("hardbreak","br",0)}else e.pending=e.pending.slice(0,-1),e.push("softbreak","br",0);else e.push("softbreak","br",0);for(t++;t<o&&q(e.src.charCodeAt(t));)t++;return e.pos=t,!0}var wt=[];for(let e=0;e<256;e++)wt.push(0);"\\!\"#$%&'()*+,./:;<=>?@[]^_`{|}~-".split("").forEach(function(e){wt[e.charCodeAt(0)]=1});function bl(e,a){let t=e.pos,r=e.posMax;if(e.src.charCodeAt(t)!==92||(t++,t>=r))return!1;let o=e.src.charCodeAt(t);if(o===10){for(a||e.push("hardbreak","br",0),t++;t<r&&(o=e.src.charCodeAt(t),!!q(o));)t++;return e.pos=t,!0}if(o===32){if(!a){let s=e.push("text_special","",0);s.content="\\",s.markup="\\",s.info="escape"}return e.pos=t,!0}let i=e.src[t];if(o>=55296&&o<=56319&&t+1<r){let s=e.src.charCodeAt(t+1);s>=56320&&s<=57343&&(i+=e.src[t+1],t++)}let n="\\"+i;if(!a){let s=e.push("text_special","",0);o<256&&wt[o]!==0?s.content=i:s.content=n,s.markup=n,s.info="escape"}return e.pos=t+1,!0}function yl(e){let a={},t=0;for(;(t=e.indexOf("`",t))!==-1;){let r=t;for(;e.charCodeAt(++t)===96;);a[t-r]=r}return a}function wl(e,a){var t;let r=e.pos;if(e.src.charCodeAt(r)!==96)return!1;let o=e.posMax,i=r+1;for(;i<o&&e.src.charCodeAt(i)===96;)i++;let n=e.src.slice(r,i),s=n.length;if(e.backticksScanned||(e.backticks=yl(e.src),e.backticksScanned=!0),((t=e.backticks[s])!==null&&t!==void 0?t:-1)>=i){let l=i,c;for(;(c=e.src.indexOf("`",l))!==-1&&c<o;){for(l=c+1;e.src.charCodeAt(l)===96;)l++;if(l>o)break;if(l-c===s){if(!a){let u=e.push("code_inline","code",0);u.markup=n;let h=e.src.slice(i,c).replace(/\n/g," ");h.startsWith(" ")&&h.endsWith(" ")&&/[^ ]/.test(h)&&(h=h.slice(1,-1)),u.content=h}return e.pos=l,!0}}}return a||(e.pending+=n),e.pos=i,!0}function xl(e,a){let t=e.pos,r=e.src.charCodeAt(t);if(a||r!==126)return!1;let o=e.scanDelims(e.pos,!0),i=o.length,n=String.fromCharCode(r);if(i<2)return!1;let s;i%2&&(s=e.push("text","",0),s.content=n,i--);for(let l=0;l<i;l+=2)s=e.push("text","",0),s.content=n+n,e.delimiters.push({marker:r,length:0,token:e.tokens.length-1,end:-1,open:o.can_open,close:o.can_close});return e.pos+=o.length,!0}function Kr(e,a){let t,r=[],o=a.length;for(let i=0;i<o;i++){let n=a[i];if(n.marker!==126||n.end===-1)continue;let s=a[n.end];t=e.tokens[n.token],t.type="s_open",t.tag="s",t.nesting=1,t.markup="~~",t.content="",t=e.tokens[s.token],t.type="s_close",t.tag="s",t.nesting=-1,t.markup="~~",t.content="",e.tokens[s.token-1].type==="text"&&e.tokens[s.token-1].content==="~"&&r.push(s.token-1)}for(;r.length;){let i=r.pop(),n=i+1;for(;n<e.tokens.length&&e.tokens[n].type==="s_close";)n++;n--,i!==n&&(t=e.tokens[n],e.tokens[n]=e.tokens[i],e.tokens[i]=t)}}function $l(e){let a=e.tokens_meta,t=e.tokens_meta.length;Kr(e,e.delimiters);for(let o=0;o<t;o++){var r;let i=(r=a[o])===null||r===void 0?void 0:r.delimiters;i&&Kr(e,i)}}var go={tokenize:xl,postProcess:$l};function kl(e,a){let t=e.pos,r=e.src.charCodeAt(t);if(a||r!==95&&r!==42)return!1;let o=e.scanDelims(e.pos,r===42);for(let i=0;i<o.length;i++){let n=e.push("text","",0);n.content=String.fromCharCode(r),e.delimiters.push({marker:r,length:o.length,token:e.tokens.length-1,end:-1,open:o.can_open,close:o.can_close})}return e.pos+=o.length,!0}function Qr(e,a){let t=a.length;for(let r=t-1;r>=0;r--){let o=a[r];if(o.marker!==95&&o.marker!==42||o.end===-1)continue;let i=a[o.end],n=r>0&&a[r-1].end===o.end+1&&a[r-1].marker===o.marker&&a[r-1].token===o.token-1&&a[o.end+1].token===i.token+1,s=String.fromCharCode(o.marker),l=e.tokens[o.token];l.type=n?"strong_open":"em_open",l.tag=n?"strong":"em",l.nesting=1,l.markup=n?s+s:s,l.content="";let c=e.tokens[i.token];c.type=n?"strong_close":"em_close",c.tag=n?"strong":"em",c.nesting=-1,c.markup=n?s+s:s,c.content="",n&&(e.tokens[a[r-1].token].content="",e.tokens[a[o.end+1].token].content="",r--)}}function Cl(e){let a=e.tokens_meta,t=e.tokens_meta.length;Qr(e,e.delimiters);for(let o=0;o<t;o++){var r;let i=(r=a[o])===null||r===void 0?void 0:r.delimiters;i&&Qr(e,i)}}var bo={tokenize:kl,postProcess:Cl};function _l(e,a){let t,r,o,i,n="",s="",l=e.pos,c=!0;if(e.src.charCodeAt(e.pos)!==91)return!1;let u=e.pos,h=e.posMax,p=e.pos+1,f=e.md.helpers.parseLinkLabel(e,e.pos,!0);if(f<0)return!1;let m=f+1;if(m<h&&e.src.charCodeAt(m)===40){for(c=!1,m++;m<h&&(t=e.src.charCodeAt(m),!(!q(t)&&t!==10));m++);if(m>=h)return!1;if(l=m,o=e.md.helpers.parseLinkDestination(e.src,m,e.posMax),o.ok){for(n=e.md.normalizeLink(o.str),e.md.validateLink(n)?m=o.pos:n="",l=m;m<h&&(t=e.src.charCodeAt(m),!(!q(t)&&t!==10));m++);if(o=e.md.helpers.parseLinkTitle(e.src,m,e.posMax),m<h&&l!==m&&o.ok)for(s=o.str,m=o.pos;m<h&&(t=e.src.charCodeAt(m),!(!q(t)&&t!==10));m++);}(m>=h||e.src.charCodeAt(m)!==41)&&(c=!0),m++}if(c){if(typeof e.env.references>"u")return!1;if(m<h&&e.src.charCodeAt(m)===91?(l=m+1,m=e.md.helpers.parseLinkLabel(e,m),m>=0?r=e.src.slice(l,m++):m=f+1):m=f+1,r||(r=e.src.slice(p,f)),r=ka(r),i=e.env.references[r],!i)return e.pos=u,!1;n=i.href,s=i.title}if(!a){e.pos=p,e.posMax=f;let b=e.push("link_open","a",1),w=[["href",n]];if(b.attrs=w,s&&w.push(["title",s]),r){let k=Object.create(null);k.label=r,b.meta=k}e.linkLevel++,e.md.inline.tokenize(e),e.linkLevel--,e.push("link_close","a",-1)}return e.pos=m,e.posMax=h,!0}function Dl(e,a){let t,r,o,i,n,s,l,c,u="",h=e.pos,p=e.posMax;if(e.src.charCodeAt(e.pos)!==33||e.src.charCodeAt(e.pos+1)!==91)return!1;let f=e.pos+2,m=e.md.helpers.parseLinkLabel(e,e.pos+1,!1);if(m<0)return!1;if(i=m+1,i<p&&e.src.charCodeAt(i)===40){for(i++;i<p&&(t=e.src.charCodeAt(i),!(!q(t)&&t!==10));i++);if(i>=p)return!1;for(c=i,s=e.md.helpers.parseLinkDestination(e.src,i,e.posMax),s.ok&&(u=e.md.normalizeLink(s.str),e.md.validateLink(u)?i=s.pos:u=""),c=i;i<p&&(t=e.src.charCodeAt(i),!(!q(t)&&t!==10));i++);if(s=e.md.helpers.parseLinkTitle(e.src,i,e.posMax),i<p&&c!==i&&s.ok)for(l=s.str,i=s.pos;i<p&&(t=e.src.charCodeAt(i),!(!q(t)&&t!==10));i++);else l="";if(i>=p||e.src.charCodeAt(i)!==41)return e.pos=h,!1;i++}else{if(typeof e.env.references>"u")return!1;if(i<p&&e.src.charCodeAt(i)===91?(c=i+1,i=e.md.helpers.parseLinkLabel(e,i),i>=0?o=e.src.slice(c,i++):i=m+1):i=m+1,o||(o=e.src.slice(f,m)),o=ka(o),n=e.env.references[o],!n)return e.pos=h,!1;u=n.href,l=n.title}if(!a){r=e.src.slice(f,m);let b=[];e.md.inline.parse(r,e.md,e.env,b);let w=e.push("image","img",0),k=[["src",u],["alt",""]];if(w.attrs=k,w.children=b,w.content=r,l&&k.push(["title",l]),o){let C=Object.create(null);C.label=o,w.meta=C}}return e.pos=i,e.posMax=p,!0}var Rl=/^([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)$/,Al=/^([a-zA-Z][a-zA-Z0-9+.-]{1,31}):([^<>\x00-\x20]*)$/;function El(e,a){let t=e.pos;if(e.src.charCodeAt(t)!==60)return!1;let r=e.pos,o=e.posMax;for(;;){if(++t>=o)return!1;let n=e.src.charCodeAt(t);if(n===60)return!1;if(n===62)break}let i=e.src.slice(r+1,t);if(Al.test(i)){let n=e.md.normalizeLink(i);if(!e.md.validateLink(n))return!1;if(!a){let s=e.push("link_open","a",1);s.attrs=[["href",n]],s.markup="autolink",s.info="auto";let l=e.push("text","",0);l.content=e.md.normalizeLinkText(i);let c=e.push("link_close","a",-1);c.markup="autolink",c.info="auto"}return e.pos+=i.length+2,!0}if(Rl.test(i)){let n=e.md.normalizeLink(`mailto:${i}`);if(!e.md.validateLink(n))return!1;if(!a){let s=e.push("link_open","a",1);s.attrs=[["href",n]],s.markup="autolink",s.info="auto";let l=e.push("text","",0);l.content=e.md.normalizeLinkText(i);let c=e.push("link_close","a",-1);c.markup="autolink",c.info="auto"}return e.pos+=i.length+2,!0}return!1}function Sl(e){return/^<a[>\s]/i.test(e)}function Pl(e){return/^<\/a\s*>/i.test(e)}function yo(e){let a=e|32;return a>=97&&a<=122}function jl(e,a){let t=e.src,r,o;if(t.startsWith("<!--",a)){if(t.startsWith(">",a+4))return a+5;if(t.startsWith("->",a+4))return a+6;r=a+4,o="-->"}else if(t.startsWith("<![CDATA[",a))r=a+9,o="]]>";else if(t.charCodeAt(a+1)===63)r=a+2,o="?>";else if(yo(t.charCodeAt(a+2)))r=a+3,o=">";else return-1;if(e.skipHtmlSpecial)return-1;let i=t.indexOf(o,r);return i<0?(e.skipHtmlSpecial=!0,-1):i+o.length}function ql(e,a){if(!e.md.options.html)return!1;let t=e.posMax,r=e.pos;if(e.src.charCodeAt(r)!==60||r+2>=t)return!1;let o,i=e.src.charCodeAt(r+1);if(i===33||i===63)o=jl(e,r);else if(i===47||yo(i)){let n=e.src.slice(r).match(fo);o=n?r+n[0].length:-1}else return!1;if(o<0)return!1;if(!a){let n=e.push("html_inline","",0);n.content=e.src.slice(r,o),Sl(n.content)&&e.linkLevel++,Pl(n.content)&&e.linkLevel--}return e.pos=o,!0}var Fl=/^&#((?:x[a-f0-9]{1,6}|[0-9]{1,7}));/i,Tl=/^&([a-z][a-z0-9]{1,31});/i;function zl(e,a){let t=e.pos,r=e.posMax;if(e.src.charCodeAt(t)!==38||t+1>=r)return!1;if(e.src.charCodeAt(t+1)===35){let o=e.src.slice(t).match(Fl);if(o){if(!a){let i=o[1][0].toLowerCase()==="x"?parseInt(o[1].slice(1),16):parseInt(o[1],10),n=e.push("text_special","",0);n.content=yt(i)?Ze(i):Ze(65533),n.markup=o[0],n.info="entity"}return e.pos+=o[0].length,!0}}else{let o=e.src.slice(t).match(Tl);if(o){let i=ya(o[0]);if(i!==o[0]){if(!a){let n=e.push("text_special","",0);n.content=i,n.markup=o[0],n.info="entity"}return e.pos+=o[0].length,!0}}}return!1}function eo(e){let a={},t=e.length;if(!t)return;let r=0,o=-2,i=[];for(let n=0;n<t;n++){let s=e[n];if(i.push(0),(e[r].marker!==s.marker||o!==s.token-1)&&(r=n),o=s.token,s.length=s.length||0,!s.close)continue;a.hasOwnProperty(s.marker)||(a[s.marker]=[-1,-1,-1,-1,-1,-1]);let l=a[s.marker][(s.open?3:0)+s.length%3],c=r-i[r]-1,u=c;for(;c>l;c-=i[c]+1){let h=e[c];if(h.marker===s.marker&&h.open&&h.end<0){let p=!1;if((h.close||s.open)&&(h.length+s.length)%3===0&&(h.length%3!==0||s.length%3!==0)&&(p=!0),!p){let f=c>0&&!e[c-1].open?i[c-1]+1:0;i[n]=n-c+f,i[c]=f,s.open=!1,h.end=n,h.close=!1,u=-1,o=-2;break}}}u!==-1&&(a[s.marker][(s.open?3:0)+(s.length||0)%3]=u)}}function Ml(e){let a=e.tokens_meta,t=e.tokens_meta.length;eo(e.delimiters);for(let o=0;o<t;o++){var r;let i=(r=a[o])===null||r===void 0?void 0:r.delimiters;i&&eo(i)}}function Jl(e){let a,t,r=0,o=e.tokens,i=e.tokens.length;for(a=t=0;a<i;a++)o[a].nesting<0&&r--,o[a].level=r,o[a].nesting>0&&r++,o[a].type==="text"&&a+1<i&&o[a+1].type==="text"?o[a+1].content=o[a].content+o[a+1].content:(a!==t&&(o[t]=o[a]),t++);a!==t&&(o.length=t)}var gt=[["text",hl],["linkify",vl],["newline",gl],["escape",bl],["backticks",wl],["strikethrough",go.tokenize],["emphasis",bo.tokenize],["link",_l],["image",Dl],["autolink",El],["html_inline",ql],["entity",zl]],bt=[["balance_pairs",Ml],["strikethrough",go.postProcess],["emphasis",bo.postProcess],["fragments_join",Jl]],wo=class{constructor(){D(this,"ruler",new Ke),D(this,"ruler2",new Ke),D(this,"State",vo);for(let e=0;e<gt.length;e++)this.ruler.push(gt[e][0],gt[e][1]);for(let e=0;e<bt.length;e++)this.ruler2.push(bt[e][0],bt[e][1])}skipToken(e){let a=e.pos,t=this.ruler.getRules(""),r=t.length,o=e.md.options.maxNesting,i=e.cache;if(typeof i[a]<"u"){e.pos=i[a];return}let n=!1;if(e.level<o){for(let s=0;s<r;s++)if(e.level++,n=t[s](e,!0),e.level--,n){if(a>=e.pos)throw new Error("inline rule didn't increment state.pos");break}}else e.pos=e.posMax;n||e.pos++,i[a]=e.pos}tokenize(e){let a=this.ruler.getRules(""),t=a.length,r=e.posMax,o=e.md.options.maxNesting;for(;e.pos<r;){let i=e.pos,n=!1;if(e.level<o){for(let s=0;s<t;s++)if(n=a[s](e,!1),n){if(i>=e.pos)throw new Error("inline rule didn't increment state.pos");break}}if(n){if(e.pos>=r)break;continue}e.pending+=e.src[e.pos++]}e.pending&&e.pushPending()}parse(e,a,t,r){let o=new this.State(e,a,t,r);this.tokenize(o);let i=this.ruler2.getRules(""),n=i.length;for(let s=0;s<n;s++)i[s](o)}},Il={default:{options:{html:!1,xhtmlOut:!1,breaks:!1,langPrefix:"language-",linkify:!1,typographer:!1,quotes:"\u201C\u201D\u2018\u2019",highlight:null,maxNesting:100},components:{core:{},block:{},inline:{}}},zero:{options:{html:!1,xhtmlOut:!1,breaks:!1,langPrefix:"language-",linkify:!1,typographer:!1,quotes:"\u201C\u201D\u2018\u2019",highlight:null,maxNesting:20},components:{core:{rules:["normalize","block","strip_references","inline","text_join"]},block:{rules:["paragraph"]},inline:{rules:["text"],rules2:["balance_pairs","fragments_join"]}}},commonmark:{options:{html:!0,xhtmlOut:!0,breaks:!1,langPrefix:"language-",linkify:!1,typographer:!1,quotes:"\u201C\u201D\u2018\u2019",highlight:null,maxNesting:20},components:{core:{rules:["normalize","block","strip_references","inline","text_join"]},block:{rules:["blockquote","code","fence","heading","hr","html_block","lheading","list","reference","paragraph"]},inline:{rules:["autolink","backticks","emphasis","entity","escape","html_inline","image","link","newline","text"],rules2:["balance_pairs","emphasis","fragments_join"]}}}},Bl=/^(vbscript|javascript|file|data):/,Ll=/^data:image\/(gif|png|jpeg|webp);/,ao=["http:","https:","mailto:"],re=class{validateLink(e){let a=e.trim().toLowerCase();return Bl.test(a)?Ll.test(a):!0}normalizeLink(e){let a=He(e,!0);if(a.hostname&&(!a.protocol||ao.indexOf(a.protocol)>=0))try{a.hostname=ht.toASCII(a.hostname)}catch{}return a.auth&&(a.auth=le(a.auth)),a.hostname&&(a.hostname=le(a.hostname)),a.pathname&&(a.pathname=le(a.pathname)),a.search&&(a.search=le(a.search)),a.hash&&(a.hash=le(a.hash)),Re(a)}normalizeLinkText(e){let a=He(e,!0);if(a.hostname&&(!a.protocol||ao.indexOf(a.protocol)>=0))try{a.hostname=ht.toUnicode(a.hostname)}catch{}return Oe(Re(a),Oe.defaultChars+"%")}constructor(...e){D(this,"inline",new wo),D(this,"block",new mo),D(this,"core",new co),D(this,"renderer",new no),D(this,"linkify",new Mr),D(this,"utils",cs),D(this,"helpers",Object.assign({},_s));let[a,t]=e;typeof a=="string"?(this.configure(a),t&&this.set(t)):(this.configure("default"),this.set(a||{}))}set(e){return Object.assign(this.options,e),this}configure(e){let a;if(typeof e=="string"){let o=e;if(a=Il[o],!a)throw new Error(`Wrong 'markdown-it' preset "${o}", check name`)}else a=e;if(!a)throw new Error("Wrong `markdown-it` preset, can't be empty");a.options&&(this.options={...a.options});let t=a.components;if(t){var r;["core","block","inline"].forEach(i=>{var n;let s=(n=t[i])===null||n===void 0?void 0:n.rules;s&&this[i].ruler.enableOnly(s)});let o=(r=t.inline)===null||r===void 0?void 0:r.rules2;o&&this.inline.ruler2.enableOnly(o)}return this}enable(e,a=!1){let t=[];Array.isArray(e)||(e=[e]),["core","block","inline"].forEach(o=>{t=t.concat(this[o].ruler.enable(e,!0))}),t=t.concat(this.inline.ruler2.enable(e,!0));let r=e.filter(o=>t.indexOf(o)<0);if(r.length&&!a)throw new Error(`MarkdownIt. Failed to enable unknown rule(s): ${r}`);return this}disable(e,a=!1){let t=[];Array.isArray(e)||(e=[e]),["core","block","inline"].forEach(o=>{t=t.concat(this[o].ruler.disable(e,!0))}),t=t.concat(this.inline.ruler2.disable(e,!0));let r=e.filter(o=>t.indexOf(o)<0);if(r.length&&!a)throw new Error(`MarkdownIt. Failed to disable unknown rule(s): ${r}`);return this}use(e,...a){return e.apply(e,[this,...a]),this}parse(e,a){if(typeof e!="string")throw new Error("Input data should be a String");let t=new this.core.State(e,this,a);return this.core.process(t),t.tokens}render(e,a={}){return this.renderer.render(this.parse(e,a),this.options,a)}parseInline(e,a){let t=new this.core.State(e,this,a);return t.inlineMode=!0,this.core.process(t),t.tokens}renderInline(e,a={}){return this.renderer.render(this.parseInline(e,a),this.options,a)}};D(re,"Token",be);D(re,"Ruler",Ke);D(re,"Renderer",no);D(re,"ParserCore",co);D(re,"StateCore",so);D(re,"ParserBlock",mo);D(re,"StateBlock",uo);D(re,"ParserInline",wo);D(re,"StateInline",vo);var xo=ro(re);var xt;function $o(e){xt=e}function g(){if(!xt)throw new Error("telar: nadie dijo qui\xE9n muestra el dashboard (anfitrion.usar)");return xt}function _a(e,...a){let t=a.reverse().find(r=>typeof r=="function");setTimeout(()=>t?.(new Error("en el navegador no se corren programas: falta su ruta en la API"),"",""),0)}function ko(){throw new Error("en el navegador no se corren programas")}var Co=()=>{throw new Error("en el navegador, la API va por fetch")};var Da=()=>"/";var Do=(e,a)=>a;function Ro(e){Do=e}function ye(e,a){return Do(e,a)}var kt=()=>(ye("cli","telar")||"telar").trim();function Ao(){let e=[],a=String(ye("config","")).trim(),t=String(ye("raiz","")).trim();return a&&e.push("--config",Va(_o(a))),t&&e.push("--raiz",Va(_o(t))),e}function _o(e){return e==="~"?Da():e.startsWith("~/")?z(Da(),e.slice(2)):e}var Ul=process.env.PATH??"",Ra=()=>{};function Wl(e,a,t,r){return new Promise(o=>{_a(e,a,{env:r??Eo(),timeout:t,encoding:"utf8",maxBuffer:8<<20},(i,n,s)=>{let l=i&&typeof i.code=="number"?i.code:i?-1:0;o({ok:!i,codigo:l,out:n??"",err:(s??"")+(i&&!s?`
${i.message}`:"")})})})}function Eo(){let e={...process.env,PATH:Ul};return delete e.TELAR_HILO,e}async function Qe(e,a=15e3){let t=await Wl(kt(),[...Ao(),...e],a);return t.ok||Ra(`telar ${e.join(" ")} \u2192 ${t.codigo}: ${Aa(t.err)}`),t}async function S(e,a=15e3){let t=await Qe([...e,"--json"],a);if(!t.ok)return{error:Xl(t,e)};try{return{datos:JSON.parse(t.out)}}catch(r){return Ra(`telar ${e.join(" ")} --json: salida ilegible (${r})`),{error:`\xABtelar ${e.join(" ")}\xBB no devolvi\xF3 JSON`}}}function Zl(){let e=process.env.XDG_STATE_HOME||z(Da(),".local","state");return z(e,"telar","serve","telar.sock")}var $t;function So(e){$t=e}function J(e,a,t,r){if($t)return $t(e,a,t,r);let o=Zl();if(!la(o))return Promise.resolve(void 0);let i=r===void 0?void 0:JSON.stringify(r);return new Promise(n=>{let s=Co({socketPath:o,path:a,method:e,timeout:t,headers:i===void 0?{}:{"Content-Type":"application/json","Content-Length":Buffer.byteLength(i)}},l=>{let c="";l.setEncoding("utf8"),l.on("data",u=>{c+=u}),l.on("end",()=>{let u;try{u=JSON.parse(c)}catch{u=void 0}let h=u?.detail;if(l.statusCode===200&&u!==void 0){n({datos:u});return}if(l.statusCode===404&&h==="Not Found"){n(void 0);return}Ra(`telar serve ${e} ${a} \u2192 ${l.statusCode}: ${c.slice(0,200)}`),n({error:typeof h=="string"?h:`la API respondi\xF3 ${l.statusCode}`})})});s.on("timeout",()=>{s.destroy(),Ra(`telar serve ${a}: no respondi\xF3 en ${t} ms`),n({error:"telar serve no respondi\xF3 a tiempo"})}),s.on("error",()=>n(void 0)),i!==void 0&&s.write(i),s.end()})}var H=(e,a)=>J("GET",e,a);function Xl(e,a){let t=Aa(e.err)||Aa(e.out);return/ENOENT|not found|no encontr/i.test(t)&&e.codigo!==2?`no encontr\xE9 \xAB${kt()}\xBB en el PATH (ajusta telar.cli)`:t||`\xABtelar ${a.join(" ")}\xBB fall\xF3 (c\xF3digo ${e.codigo})`}function Aa(e){return e.split(`
`).map(a=>a.trim()).filter(Boolean).pop()??""}async function ea(e,a=""){return await H(`/resultados/${encodeURIComponent(e)}${a?`?dia=${encodeURIComponent(a)}`:""}`,3e4)??S(["resultado",e,...a?[a]:[]],3e4)}async function Po(e,a,t){let r=await J("POST",`/resultados/${encodeURIComponent(e)}/comentario`,9e4,{dia:a,texto:t});return r?r.datos??{ok:!1,error:r.error}:Gl(["resultado",e,a,"--comentar","--json"],t)}var jo=async()=>await H("/espejos",15e3)??S(["espejo","ver","--json"],15e3);function Gl(e,a){return new Promise(t=>{let r=ko(kt(),[...Ao(),...e],{env:Eo()}),o="",i="",n=setTimeout(()=>{r.kill()},9e4);r.stdout.on("data",s=>{o+=s}),r.stderr.on("data",s=>{i+=s}),r.on("error",s=>{clearTimeout(n),t({ok:!1,error:s.message})}),r.on("close",()=>{clearTimeout(n);try{t(JSON.parse(o))}catch{t({ok:!1,error:Aa(i)||"no respondi\xF3"})}}),r.stdin.end(a)})}var Ea=async(e="")=>await H(`/notas${e?`?dia=${encodeURIComponent(e)}`:""}`,3e4)??S(["evento","notas",...e?[e]:[]],3e4),Ct=async(e,a,t,r,o="")=>await J("POST","/notas",3e4,{evento:e,texto:a,de:"Nico",titulo:t,inicio:r,dia:o})??S(["evento","nota",e,a,"--de","Nico","--titulo",t,"--inicio",r,...o?["--dia",o]:[]],3e4),Sa=(e,a,t="",r="",o={})=>S(["reunion",e,a,...t?["--enlace",t]:[],...r?["--evento",r]:[],...o.asistentes?.length?["--asistentes",o.asistentes.join(",")]:[],...o.proyecto?["--proyecto",o.proyecto]:[],...o.preguntar?["--preguntar"]:[],...o.donde?["--donde"]:[],"--json"],4e4),we=async()=>await H("/proyectos",3e4)??S(["proyectos","--json"],3e4),_t=async()=>await H("/pendientes?repo=true",3e4)??S(["pendientes","--json","--repo"],3e4),qo=async e=>await J("POST","/proyectos/abrir",3e4,{ruta:e})??S(["proyectos","abrir",e,"--json"],3e4);async function Fo(e,a){return await H(`/bloques/${encodeURIComponent(e)}/items/${encodeURIComponent(a)}`,7e4)??S(["bloque",e,"--item",a,"--json"],7e4)}async function To(e){return await H(`/bloques/${encodeURIComponent(e)}`,9e4)??S(["bloque",e],9e4)}async function oe(){return await H("/config",2e4)??S(["config","--json"],2e4)}var Ee=async(e,a)=>await J("POST","/encargos",3e4,{agente:e,texto:a})??S(["encargar",e,a],3e4);function Se(e,a){return e.hilos.some(t=>t.endsWith("*")?a.startsWith(t.slice(0,-1)):a===t)}var zo=async e=>await H(`/secciones/${encodeURIComponent(e)}`,4e4)??S(["seccion",e,"--json"],4e4),Mo=async e=>await H(`/apps/${encodeURIComponent(e)}`,4e4)??S(["app",e,"--json"],4e4),Jo=async e=>await J("PUT","/config/pestanas",2e4,{valor:e})??S(["config","--pestanas",e,"--json"],2e4);async function Z(e,a){return await H(`/tareas/${encodeURIComponent(e)}?proveedor=${encodeURIComponent(a)}`,4e4)??S(["tarea",e,"--proveedor",a,"--json"],4e4)}async function Io(e,a,t){return await J("POST",`/tareas/${encodeURIComponent(e)}/accion`,4e4,{proveedor:a,rol:t})??S(["tarea",e,"--proveedor",a,"--rol",t,"--json"],4e4)}async function ie(e,a,t,r="",o=""){return await J("POST",`/tareas/${encodeURIComponent(e)}/accion`,4e4,{proveedor:a,n:t,texto:r,...o?{version:o}:{}})??S(["tarea",e,"--proveedor",a,"--accion",String(t),...r?["--texto",r]:[],...o?["--version",o]:[],"--json"],4e4)}async function Pa(e,a){return await J("POST","/periodicos",a,{argv:e})??S(["periodicos",...e],a)}var Bo=async()=>await H("/periodicos",3e4)??S(["periodicos","ver"],3e4),Lo=e=>Pa(["log",e,"--lineas","200"],3e4),No=e=>Pa(["horario",e,"--n","3"],3e4),Oo=e=>Pa(["skills",...e?["--carpeta",e]:[]],3e4),Dt=e=>Pa(e,6e4),Ho=async e=>await H(`/conversaciones/${encodeURIComponent(e)}`,2e4)??S(["agente","conversacion",e,"--json"],2e4);async function Uo(e,a,t){return await J("POST",`/bloques/${encodeURIComponent(e)}/abrir`,3e4,{mensaje:a,nombre:t})??S(["bloque",e,"--abrir",a,"--nombre",t,"--json"],3e4)}var Wo=async e=>await J("POST",`/atajos/${encodeURIComponent(e)}`,3e4)??S(["atajo",e,"--json"],3e4),Zo=e=>ja("directorios",e,["config","--directorios",e]),Xo=e=>ja("reunion",e,["config","--reunion",e]),Go=e=>ja("proyecto",e,["config","--proyecto",e]),Vo=e=>ja("calendario",e,["config","--calendario",e]);async function ja(e,a,t){let r=await J("PUT",`/config/${e}`,2e4,{valor:a});return r?r.error?{ok:!1,codigo:1,out:"",err:r.error}:{ok:!0,codigo:0,out:r.datos?.archivo??"",err:""}:Qe(t,2e4)}function Yo(e,a){if(!a||!da(a))return e;let t=e.ruta&&!da(e.ruta)&&e.relativa?z(a,e.relativa):e.ruta,r=e.ficha,o=r&&r.documento&&!da(r.documento)&&r.relativo?{...r,documento:z(a,r.relativo)}:r;return t===e.ruta&&o===r?e:{...e,ruta:t,ficha:o}}async function Ko(e,a){let t=new URLSearchParams({orden:a,...e?{}:{ficha:"false"}}).toString();return await H(`/hilos?${t}`,e?3e4:8e3)??S(["hilos",...e?[]:["--sin-ficha"],"--orden",a],e?3e4:8e3)}async function Rt(e,a=""){let t=new URLSearchParams({...e?{local:"true"}:{},...a?{dia:a}:{}}).toString();return await H(`/hoy${t?`?${t}`:""}`,e?2e4:6e4)??S(["hoy",...e?["--local"]:[],...a?["--dia",a]:[]],e?2e4:12e4)}async function Qo(e,a=!1,t=""){let r=await J("POST","/ir",t?6e4:2e4,{hilo:e,crear:a,remoto:t});return r?r.error?{ok:!1,codigo:1,out:"",err:r.error}:{ok:!0,codigo:0,out:`\u2192 \xAB${r.datos?.hilo??e}\xBB`,err:""}:Qe(["ir",e,...a?["--crear"]:[],...t?["--remoto",t]:[]],t?6e4:2e4)}var ei=async(e=60)=>await H(`/mensajes?n=${e}`,3e4)??S(["mensaje","--registro",String(e)],3e4),ai=async e=>await J("POST",`/mensajes/${encodeURIComponent(e)}/soltar`,3e4)??S(["mensaje","--soltar",e],3e4),At=e=>e&&e!=="local"?["--remoto",e]:[],ti=async e=>await H(`/equipo/bandeja?maquina=${encodeURIComponent(e)}`,3e4)??S(["equipo","sugerencias",...At(e)],3e4),ri=async(e,a,t="gestion")=>await J("POST",`/equipo/${encodeURIComponent(a)}/revisando?quien=${encodeURIComponent(t)}`,3e4,{maquina:e})??S(["equipo","revisando",a,"--quien",t,...At(e)],3e4),qa=async(e,a,t,r="",o="")=>await J("POST",`/equipo/${encodeURIComponent(t)}/${a}`,4e4,{nota:r,tarea:o,maquina:e})??S(["equipo",a,t,...r?["--nota",r]:[],...o?["--tarea",o]:[],...At(e)],4e4);async function Pe(e,a,t,r=[]){let o=r.every(i=>i==="--cerrar");if(e!=="llevar"&&o){let i=await J("POST",`/hilo/${encodeURIComponent(e)}`,3e4,{hilo:a,valor:t??"",cerrar:r.includes("--cerrar")});if(i)return i.error?{ok:!1,codigo:1,out:"",err:i.error}:{ok:!0,codigo:0,out:i.datos?.salida??"",err:i.datos?.error??""}}return Qe(["hilo",e,...t?[t]:[],"--hilo",a,...r],e==="llevar"?15*6e4:3e4)}var oi=async(e,a=!1,t="",r="",o=!1)=>await J("POST","/pendiente/llevar",9e4,{ref:e,nuevo:a,proveedor:t,texto:r,enviar:o})??S(["pendiente",e,...a?["--nuevo"]:[],...t?["--proveedor",t]:[],...r?["--texto",r]:[],...o?["--enviar"]:[]],9e4);async function aa(e,a,t){let r=t.indexOf("--responsable"),o={ref:e,esperado:a,hecho:t.includes("--hecho"),linea:t.includes("--linea"),...r>=0?{responsable:t[r+1]??""}:{}};return await J("POST","/pendiente/casilla",6e4,o)??S(["pendiente",e,...t,"--esperado",a,"--json"],6e4)}async function Fa(e=!1){let a=await J("POST","/tejer",e?6e4:2e4,{sumar:e});return a?a.error?{ok:!1,codigo:1,out:"",err:a.error}:{ok:!0,codigo:0,out:a.datos?.salida??"",err:a.datos?.error??""}:Qe(["tejer",...e?["--sumar"]:[]],e?6e4:2e4)}function je(e){return e.ficha?.etiqueta?.trim()||e.nombre}var Vl={leer:async e=>{try{return ca(e,"utf8")}catch{return}},buscarMd:async(e,a)=>{let t=[],r=(o,i)=>{let n=[];try{n=Kt(o,{withFileTypes:!0})}catch{return}for(let s of n){if(s.name.startsWith(".")||s.name==="node_modules"||s.name==="assets")continue;let l=z(o,s.name);if(s.isDirectory()&&i<a)r(l,i+1);else if(s.isFile()&&s.name.endsWith(".md"))try{t.push({ruta:l,mtime:Qt(l).mtimeMs})}catch{}}};return r(e,0),t},escribir:async(e,a)=>{try{Be(e);let t=`${e}.${process.pid}.tmp`;return er(t,a),ar(t,e),!0}catch{return!1}}},ii=Vl;function ni(e){ii=e}var pe=()=>ii;var Et=class{oyentes=new Set;event=a=>(this.oyentes.add(a),{dispose:()=>{this.oyentes.delete(a)}});fire(){for(let a of[...this.oyentes])a()}},St=class{sesion="";multiplexor="";raiz="";viva=!1;clientes=[];aviso="";error="";hilos=[];secciones=[];apps=[];sugerencias=[];sugerenciasVistas;hayRemotos=!1;cambio=new Et;fichas=new Map;firma="";enCurso=!1;ultimaFicha=0;get activo(){return this.hilos.find(a=>a.activo)}get enLista(){return this.hilos.filter(a=>!a.archivado&&(a.vivo||a.propio))}get archivados(){return this.hilos.filter(a=>a.archivado||!a.vivo&&!a.propio)}get esperan(){return this.enLista.filter(a=>a.atencion==="espera").length}get equipoRemoto(){return String(ye("equipoRemoto","")).trim()}async leerEquipo(){let a=this.equipoRemoto;if(!a){this.sugerencias=[];return}let t=await ti(a);if(!t.datos)return;let r=t.datos.sugerencias.filter(s=>!this.sugerenciasVistas?.has(s.id)),o=this.sugerenciasVistas===void 0;if(this.sugerenciasVistas=new Set([...this.sugerenciasVistas??[],...t.datos.sugerencias.map(s=>s.id)]),this.sugerencias=t.datos.sugerencias,this.firma="",this.cambio.fire(),!r.length)return;let i=r.length===1?r[0]:void 0,n=i?i.tipo==="tarea"?`${i.persona} te pide una tarea: \xAB${i.titulo.slice(0,80)}\xBB${i.vence?` (para el ${i.vence})`:""}${i.similares?.length?` \xB7 \xBFya existe ${i.similares[0].id}?`:""}`:`${i.persona} sugiere subir ${i.tarea} \xAB${i.titulo.slice(0,60)}\xBB: ${i.motivo.slice(0,120)}`:`${r.length} cosas del equipo ${o?"esperan":"nuevas"}: ${r.map(s=>s.tipo==="tarea"?`pedido de ${s.persona}`:s.tarea).join(", ")}`;g().aviso(`telar \xB7 ${n}`,"Ver",...i?[i.tipo==="tarea"?"Agregar":"Aceptar"]:[]).then(async s=>{if(s==="Ver")await g().orden("telar.equipoVer",i?.id);else if((s==="Aceptar"||s==="Agregar")&&i){let l=await qa(a,"aceptar",i.id);g().info(l.datos?i.tipo==="tarea"?`telar: agregada${l.datos.sugerencia.tarea?` como ${l.datos.sugerencia.tarea}`:""}`:`telar: ${i.tarea} sube de prioridad`:`telar: no se pudo: ${l.error??""}`),await this.leerEquipo()}})}seccionDe(a){return this.secciones.find(t=>Se(t,a))}porNombre(a){return this.hilos.find(t=>t.nombre===a)}porId(a){return this.hilos.find(t=>t.id===a)}get orden(){return String(ye("orden","mux"))}async sondear(a=!1){if(!this.enCurso){this.enCurso=!0;try{let t=Number(ye("intervaloFicha",6e4)),r=a||Date.now()-this.ultimaFicha>t,o=await Ko(r,this.orden);if(!o.datos){this.error=o.error??"",this.anunciar(["error",this.error]);return}this.error="";let i=o.datos;if(this.sesion=i.sesion,this.multiplexor=i.multiplexor,this.raiz=i.raiz,this.viva=i.viva,this.aviso=i.aviso,this.clientes=i.clientes??[],r){let n=await oe();n.datos&&(this.secciones=n.datos.secciones??[],this.apps=n.datos.apps??[],this.hayRemotos=(n.datos.remotos??[]).length>0),this.leerEquipo(),this.ultimaFicha=Date.now(),this.fichas=new Map(i.hilos.map(s=>[s.nombre,s.ficha??null]))}this.hilos=i.hilos.map(n=>Yo({...n,ficha:n.ficha??this.fichas.get(n.nombre)??null},i.raiz)),this.anunciar(["ok",i.sesion,i.viva,i.aviso,this.hilos,this.secciones])}finally{this.enCurso=!1}}}anunciar(a){let t=JSON.stringify(a);t!==this.firma&&(this.firma=t,this.cambio.fire())}invalidar(){this.ultimaFicha=0}},x=new St;var Yl=B("hilos"),Kl=`
const lista = document.getElementById('lista');
// lo escrito en cada buscador sobrevive a los redibujos (llegan varios por minuto) y a recargar
const est = vscode.getState() || {};
est.q = est.q || {};
const norm = t => (t || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
function filtrar() {
  document.querySelectorAll('input.buscar').forEach(inp => {
    const g = inp.dataset.grupo, q = norm(inp.value.trim());
    let n = 0;
    document.querySelectorAll('.fila[data-grupo="' + g + '"]').forEach(f => {
      const ok = !q || norm(f.dataset.busca).includes(q);
      f.hidden = !ok; if (ok) n++;
    });
    const v = document.querySelector('.vacia[data-grupo="' + g + '"]');
    if (v) v.hidden = !(q && !n);
  });
}
window.addEventListener('message', e => {
  const m = e.data;
  if (m.tipo !== 'lista') return;
  const a = document.activeElement, foco = a && a.classList && a.classList.contains('buscar')
    ? { g: a.dataset.grupo, i: a.selectionStart, j: a.selectionEnd } : null;
  lista.innerHTML = m.html;
  document.querySelectorAll('input.buscar').forEach(inp => { inp.value = est.q[inp.dataset.grupo] || ''; });
  if (foco) {
    const inp = document.querySelector('input.buscar[data-grupo="' + foco.g + '"]');
    if (inp) { inp.focus(); inp.setSelectionRange(foco.i, foco.j); }
  }
  filtrar();
  if (m.mostrar) { const el = document.querySelector(m.mostrar); if (el && !el.hidden) el.scrollIntoView({ block: 'nearest' }); }
});
document.addEventListener('input', e => {
  if (!e.target.classList.contains('buscar')) return;
  est.q[e.target.dataset.grupo] = e.target.value; vscode.setState(est); filtrar();
});
document.addEventListener('keydown', e => {
  if (!e.target.classList || !e.target.classList.contains('buscar')) return;
  if (e.key === 'Escape') { e.target.value = ''; est.q[e.target.dataset.grupo] = ''; vscode.setState(est); filtrar(); }
  // \u23CE: al primero que se ve
  if (e.key === 'Enter') {
    const f = document.querySelector('.fila[data-grupo="' + e.target.dataset.grupo + '"]:not([hidden])');
    if (f) vscode.postMessage({ tipo: 'ir', hilo: f.dataset.hilo });
  }
});
document.addEventListener('click', e => {
  const f = e.target.closest('[data-hilo],[data-accion]');
  if (!f) return;
  if (f.dataset.accion) vscode.postMessage({ tipo: f.dataset.accion, id: f.dataset.id });
  else vscode.postMessage({ tipo: 'ir', hilo: f.dataset.hilo });
});
// en el navegador no hay men\xFA contextual nativo: el clic derecho abre el del hilo (\u22EF)
document.addEventListener('contextmenu', e => {
  if (!window.__telarWeb) return;
  const f = e.target.closest('[data-hilo]');
  if (!f) return;
  e.preventDefault();
  vscode.postMessage({ tipo: 'menu', id: f.dataset.hilo });
});
vscode.postMessage({ tipo: 'listo' });
`,Ql=[["urgencia","\u25CF","urgencia: prioridad alta primero; a igual prioridad, el que te espera y despu\xE9s el m\xE1s reciente"],["nombre","a-z","nombre, alfab\xE9tico"],["reciente","\u25F7","\xFAltima modificaci\xF3n: el \xFAltimo prompt a su agente, lo m\xE1s reciente arriba"]],Pt=e=>e.actividad||e.atencion_desde||"";function si(e,a){if(!a)return e;let t=(o,i)=>Pt(i).localeCompare(Pt(o)),r={urgencia:(o,i)=>(o.prioridad||9)-(i.prioridad||9)||+(i.atencion==="espera")-+(o.atencion==="espera")||t(o,i),nombre:(o,i)=>je(o).localeCompare(je(i),"es",{sensitivity:"base"}),reciente:t};return[...e].sort(r[a])}var Ta=class{vista;listo=!1;ultimoHtml="";ultimoActivo;dashboardActivo=!1;appActiva="";mostrado;otras=[];aqui="";conMaquina(){return!!this.estado?.get("telar.hilos.maquina")}anchoMaquina=1;irAlArchivo=!1;estado;ordenDe(a){return this.estado?.get(`telar.orden.${a}`)??""}invertidas=new Set;get archivoAbierto(){return this.abierta("__archivo",!1)}set archivoAbierto(a){a!==this.archivoAbierto&&this.alternar("__archivo")}abierta(a,t){return t!==this.invertidas.has(a)}alternar(a){this.invertidas.has(a)?this.invertidas.delete(a):this.invertidas.add(a)}conectar(a){this.vista=a,this.pintarMarco()}desconectar(){this.vista=void 0,this.listo=!1}pintarMarco(){this.vista&&(this.listo=!1,this.ultimoHtml="",this.vista.html(fa(this.vista,Yl,'<div id="lista"></div>',Kl)))}mensaje(a){switch(a.tipo){case"listo":this.listo=!0,this.refrescar(!0);break;case"ir":{if(!a.hilo)break;let t=x.hilos.some(r=>r.nombre===a.hilo&&(!r.vivo||r.archivado));g().orden(t?"telar.retomar":"telar.ir",{hilo:a.hilo});break}case"archivar":a.id&&g().orden("telar.archivar",{hilo:a.id});break;case"retomar":a.id&&g().orden("telar.retomar",{hilo:a.id});break;case"cerrar":a.id&&g().orden("telar.cerrar",{hilo:a.id});break;case"archivo":g().orden("telar.archivo");break;case"menu":a.id&&g().orden("telar.menuHilo",{hilo:a.id});break;case"ir-remoto":a.id&&g().orden("telar.irRemoto",a.id);break;case"seccion":if(a.id==="__archivo"){g().orden("telar.archivo");break}a.id&&(this.alternar(a.id),this.refrescar(!0));break;case"equipo":g().orden("telar.equipoVer",a.id);break;case"home":a.id&&g().orden("telar.seccion",a.id);break;case"app":a.id&&g().orden("telar.app",a.id);break;case"ver-maquina":this.estado?.update("telar.hilos.maquina",!this.conMaquina()).then(()=>this.refrescar(!0));break;case"orden-grupo":if(a.id){let[t,r]=a.id.split(":");this.estado?.update(`telar.orden.${t}`,r===this.ordenDe(t)?"":r).then(()=>this.refrescar(!0))}break;case"cmd":a.id?.startsWith("telar.")&&g().orden(a.id);break}}alternarArchivo(){this.archivoAbierto=!this.archivoAbierto,this.irAlArchivo=this.archivoAbierto,this.refrescar(!0)}refrescar(a=!1){let t=this.vista;if(!t)return;let r={alfa:"a-z",reciente:"\u25F7",prioridad:"\u25CF"}[x.orden]??"";if(t.cabecera({titulo:r?`hilos \xB7 ${r}`:"hilos",descripcion:x.error?"sin telar":x.viva?x.sesion:"sesi\xF3n no tejida",insignia:x.esperan?{valor:x.esperan,ayuda:`${x.esperan} te espera${x.esperan===1?"":"n"}`}:void 0}),!this.listo)return;let o=this.html(),i=this.dashboardActivo?"\0dashboard":this.mostrado??x.activo?.nombre,n=i!==this.ultimoActivo;if(!a&&!n&&o===this.ultimoHtml)return;this.ultimoActivo=i,this.ultimoHtml=o;let s=this.irAlArchivo?"#archivo":n||a?".activa":void 0;this.irAlArchivo=!1,t.enviar({tipo:"lista",html:o,mostrar:s})}fila(a,t,r="",o=""){let i=d(JSON.stringify({webviewSection:t,hilo:a.nombre,preventDefaultContextMenuItems:!0})),n=a.atencion==="termino"&&!a.sin_ver,s=`<span class="at ${d(a.atencion)}${n?" visto":""}" title="${d(n?"termin\xF3 (ya lo viste)":a.sin_ver?"termin\xF3 y no lo has visto: \u2325S":pa[a.atencion]??"")}">${Le[a.atencion]??" "}</span>`,l=this.columnaMaquina(a.remoto==="?"?"?":a.remoto??"",a.remoto?a.remoto==="?"?"conectado a otra m\xE1quina":`vive en ${a.remoto}`:""),c=Pt(a),u=se(c),h=this.mostrado!==void 0?a.nombre===this.mostrado:a.activo,p=[t,h&&!this.dashboardActivo?"activa":"",a.vivo?"":"muerto"].filter(Boolean).join(" "),f=o?` data-grupo="${o}" data-busca="${d(`${je(a)} ${a.nombre} ${a.relativa??""} ${a.remoto||this.aqui}`)}"`:"";return`<div class="fila ${p}"${f} data-hilo="${d(a.nombre)}" data-vscode-context="${i}" title="${d(this.tooltip(a))}"><span class="prio p${a.prioridad??0}">${_e[a.prioridad??0]??_e[0]}</span>${s}${l}<span class="nombre">${d(je(a))}</span><span class="der">${d(u)}</span>${r}<span class="iconos"><span class="icono menu-web" data-accion="menu" data-id="${d(a.nombre)}" title="m\xE1s: renombrar, vincular, prioridad, llevar\u2026">\u22EF</span>`+(!a.vivo||t==="archivado"?`<span class="icono" data-accion="retomar" data-id="${d(a.nombre)}" title="retomar: reabre el tab con su conversaci\xF3n">\u25B6</span>`:`<span class="icono" data-accion="archivar" data-id="${d(a.nombre)}" title="archivar: cierra el tab, guarda su conversaci\xF3n y lo manda al archivo">\u23F8</span><span class="icono" data-accion="cerrar" data-id="${d(a.nombre)}" title="cerrar: cierra el tab y lo que corra adentro, y lo saca de la lista; para guardarlo, \u23F8">\u2715</span>`)+"</span></div>"}columnaMaquina(a,t){let r=t?` title="${d(t)}"`:"";if(!this.conMaquina())return`<span class="remoto"${r}>${a?"\u21C4":" "}</span>`;let o=a==="?"?"?":a||this.aqui||"\xB7";return`<span class="remoto ancho${a?"":" aqui"}" style="width: ${this.anchoMaquina}ch"${r||` title="${d(`vive aqu\xED${this.aqui?` (${this.aqui})`:""}`)}"`}>${d(o)}</span>`}herramientas(a,t){let r=a==="hilos"?`<span class="ord${this.conMaquina()?" si":""}" data-accion="ver-maquina" title="${this.conMaquina()?"ver solo \u21C4 en los hilos de otra m\xE1quina":"ver en qu\xE9 m\xE1quina vive cada hilo"}">\u21C4</span>`:"";return`<div class="herram"><input class="buscar" data-grupo="${a}" placeholder="buscar" spellcheck="false" title="buscar por nombre, carpeta o m\xE1quina \xB7 \u23CE abre el primero \xB7 \u238B borra">`+Ql.map(([o,i,n])=>`<span class="ord${o===t?" si":""}" data-accion="orden-grupo" data-id="${a}:${o}" title="${d(`ordenar por ${n}${o===t?" (clic: volver al orden de telar)":""}`)}">${i}</span>`).join("")+r+`</div><div class="vacia" data-grupo="${a}" hidden>nada calza</div>`}tooltip(a){let t=je(a),r=[...t!==a.nombre?[t]:[],`${a.nombre}${a.id!==a.nombre?` \xB7 ${a.id}`:""} \xB7 ${a.relativa||"sin carpeta"}`],o=[];a.arquetipo&&o.push(a.arquetipo),a.remoto&&o.push(a.remoto==="?"?"\u21C4 en otra m\xE1quina":`\u21C4 remoto: ${a.remoto}`),a.vivo||o.push("no vivo"),Le[a.atencion]&&o.push(`${Le[a.atencion]} ${pa[a.atencion]??a.atencion}`),a.prioridad&&o.push(`prioridad ${_e[a.prioridad]} ${["","alta","media","baja"][a.prioridad]}`),a.tiempo>=60&&o.push(`hoy ${tr(a.tiempo)}`),a.actividad&&o.push(`\xFAltimo prompt hace ${ha(a.actividad)}`),a.visto&&o.push(`\xFAltimo foco hace ${ha(a.visto)}`),o.length&&r.push(o.join(" \xB7 "));let i=a.ficha;i?.estado?r.push("",`\u203A ${i.estado}`):i?.nota&&r.push("",i.nota);for(let n of(i?.pendientes??[]).slice(0,6))r.push(`${n.en_curso?"\u25A3":n.hecho?"\u2713":"\u2610"} ${n.texto}`);return r.join(`
`)}html(){if(x.error)return`<div class="aviso">${d(x.error)}<br><br><a data-accion="cmd" data-id="telar.actualizar">reintentar</a></div>`;let a=[];if(x.aviso&&a.push(`<div class="nota">(${d(x.aviso)})</div>`),!x.viva&&!x.hilos.length)return a.join("")+`<div class="aviso">la sesi\xF3n \xAB${d(x.sesion)}\xBB no est\xE1 tejida.<br><br><a data-accion="cmd" data-id="telar.tejer">tejerla en un terminal</a></div>`;if(!x.hilos.length)return a.join("")+'<div class="aviso">ning\xFAn hilo todav\xEDa.<br><br><a data-accion="cmd" data-id="telar.nuevo">abrir uno</a></div>';x.viva||a.push('<div class="nota">la sesi\xF3n no est\xE1 viva; esto es lo que telar recuerda</div>'),a.push(`<div class="fila hoy${this.dashboardActivo&&!this.appActiva?" activa":""}" data-accion="cmd" data-id="telar.hoy" title="el d\xEDa: agenda, tareas y lo que espera"><span class="prio"> </span><span class="nombre">dashboard</span></div>`);let t=p=>[...p.filter(f=>f.vivo),...p.filter(f=>!f.vivo)],r=(p,f,m,b,w)=>{let k=this.abierta(p,b);return a.push('<div class="sep"></div>'),a.push(`<div${p==="__archivo"?' id="archivo"':""} class="fila cab" data-accion="seccion" data-id="${d(p)}" title="${d(w)}: abrir o cerrar"><span class="prio">${k?"\u25BE":"\u25B8"}</span>${d(f)}${m?` <span class="dim">${m}</span>`:""}</div>`),k},o=x.secciones.filter(p=>p.grupo==="agentes");if(o.length&&r("__agentes","AGENTES",0,!0,"los agentes residentes"))for(let p of o){let f=`<span class="icono casa" data-accion="home" data-id="${d(p.clave)}" title="la casa de ${d(p.nombre)}: bit\xE1cora, memoria, archivos">home</span>`,m=t(x.enLista.filter(b=>Se(p,b.nombre)));if(!m.length){let b=x.hilos.find(C=>Se(p,C.nombre)),w=b?`<span class="icono" data-accion="retomar" data-id="${d(b.nombre)}" title="retomar: reabre el hilo con su conversaci\xF3n">\u25B6</span>`:"",k=b?`data-accion="retomar" data-id="${d(b.nombre)}"`:`data-accion="home" data-id="${d(p.clave)}"`;a.push(`<div class="fila agente muerto" ${k} title="${d(p.nombre)}: sin hilo abierto; ${b?"pincha para retomarlo":"su home"}"><span class="prio"> </span><span class="at"> </span><span class="remoto"> </span><span class="nombre">${d(p.nombre)}</span><span class="der"></span>${w}${f}</div>`);continue}m.forEach((b,w)=>a.push(this.fila(b,"hilo",w===0?f:"").replace('class="fila ','class="fila agente ')))}let i=this.ordenDe("hilos"),n=si(t(x.enLista.filter(p=>!x.seccionDe(p.nombre))),i),s=new Set(x.hilos.filter(p=>p.remoto).map(p=>`${p.remoto}|${p.nombre}`)),l=this.otras.flatMap(p=>p.hilos.filter(f=>f.vivo&&!s.has(`${p.nombre}|${f.nombre}`)).map(f=>({m:p,x:f}))),c=[this.aqui,...this.otras.map(p=>p.nombre),...n.map(p=>p.remoto??"")];if(this.anchoMaquina=Math.min(12,Math.max(1,...c.map(p=>p.length))),r("__hilos","HILOS",n.length+l.length,!0,"los hilos abiertos, de esta m\xE1quina y de las otras")){a.push(this.herramientas("hilos",i));for(let p of n)a.push(this.fila(p,"hilo","","hilos"));for(let{m:p,x:f}of l){let m=f.atencion??"ninguna",b=p.en_linea?"":`
${p.nombre} est\xE1 apagado${p.edad!==null?` hace ${se(new Date(Date.now()-p.edad*1e3).toISOString())}`:""}`;a.push(`<div class="fila remota${p.en_linea?"":" muerto"}" data-accion="ir-remoto" data-id="${d(`${p.nombre}|${f.nombre}`)}" data-grupo="hilos" data-busca="${d(`${f.nombre} ${f.relativa??""} ${p.nombre}`)}" title="${d(`${p.nombre}:${f.nombre}${f.relativa?`
${f.relativa}`:""}${f.resumen?`
${f.resumen}`:""}${b}`)}"><span class="prio p${f.prioridad??0}">${_e[f.prioridad??0]??_e[0]}</span><span class="at ${d(m)}" title="${d(pa[m]??"")}">${Le[m]??" "}</span>`+this.columnaMaquina(p.nombre,`vive en ${p.nombre}`)+`<span class="nombre">${d(f.nombre)}</span></div>`)}}for(let p of x.secciones.filter(f=>f.grupo!=="agentes")){let f=t(x.enLista.filter(m=>Se(p,m.nombre)));if(r(p.clave,p.nombre.toUpperCase(),f.length,!0,`la secci\xF3n ${p.nombre}`)){p.home&&a.push(`<div class="fila hoy" data-accion="home" data-id="${d(p.clave)}" title="la p\xE1gina de ${d(p.nombre)}"><span class="prio"> </span><span class="nombre">home</span></div>`);for(let m of f)a.push(this.fila(m,"hilo"))}}if(x.equipoRemoto){let p=x.sugerencias;if(r("__equipo","EQUIPO",p.length,!1,"lo que el equipo te pide")){p.length||a.push('<div class="fila dim"><span class="prio"> </span>nada esperando</div>');for(let f of p){let m=f.tipo==="tarea";a.push(`<div class="fila equipo" data-accion="equipo" data-id="${d(f.id)}" title="${d(`${f.persona}: ${f.titulo}${f.motivo?`
\xAB${f.motivo}\xBB`:""}
clic: acciones`)}"><span class="prio">\u25C6</span><span class="nombre">${d(f.persona)} \xB7 ${d(m?f.titulo:`${f.tarea}: subir`)}</span><span class="der dim">${f.revisando?"Gesti\xF3n":f.similares?.length?"\xBFya existe?":""}</span></div>`)}}}let u=this.ordenDe("archivo"),h=si(x.archivados,u);if(h.length&&r("__archivo","ARCHIVO",h.length,!1,"los hilos archivados")){a.push(this.herramientas("archivo",u));for(let p of h)a.push(this.fila(p,"archivado","","archivo"))}if(x.apps.length&&r("__apps","APPS",0,!1,"lo que se abre en el panel"))for(let p of x.apps){let f=this.dashboardActivo&&this.appActiva===p.clave?" activa":"";a.push(`<div class="fila hoy${f}" data-accion="app" data-id="${d(p.clave)}" title="${d(p.descripcion||p.nombre)}"><span class="prio"> </span><span class="nombre">${d(p.nombre)}</span></div>`)}return a.join("")}};function ec(e){let a=(e.similares??[]).map(t=>`  \xB7 ${t.id} \xAB${t.titulo}\xBB (${t.estado}${t.prioridad===null?"":`, P${t.prioridad}`}${t.vence?`, vence ${t.vence}`:""}${t.compartida?"":", no compartida"})`);return[`[del equipo, a pedido de Nico] ${e.persona} le pide a Nico una tarea. Entrada ${e.id} de la bandeja (\`telar equipo sugerencias\`):`,`  Pide: \xAB${e.titulo}\xBB${e.vence?` \xB7 para el ${e.vence}`:""}`,...e.motivo?[`  Contexto que dio: ${e.motivo}`]:[],...a.length?["Tareas que el sistema ve parecidas:",...a]:[],"","Enc\xE1rgate de procesarla, con tu criterio:","1. Revisa si ya existe algo: `todo search`, las tareas abiertas y las cerradas hace poco (no te quedes con las parecidas de arriba).","2. Decide, y ejecuta lo que corresponda:",`   \xB7 es nueva \u2192 \`telar equipo aceptar ${e.id}\` (la agrega como tarea, P2, etiquetada equipo). Si conviene otra prioridad, c\xE1mbiala despu\xE9s con \`todo edit\`.`,`   \xB7 ya existe y el pedido aporta algo (fecha, contexto, urgencia) \u2192 actualiza esa tarea (\`todo nota\`, \`todo edit --due\`\u2026) y cierra la entrada con \`telar equipo existe ${e.id} --tarea T123 --nota "\u2026"\`.`,`   \xB7 ya existe y no hay nada que agregar \u2192 solo \`telar equipo existe ${e.id} --tarea T123 --nota "\u2026"\`.`,`   \xB7 no corresponde (no es de Nico, no es accionable, es de otro hilo) \u2192 \`telar equipo rechazar ${e.id} --nota "motivo"\`.`,`3. La nota la lee ${e.persona}: escribe solo estado y lo que sirva para su pedido, sin detalles privados de Nico ni de otras personas.`,"4. Cont\xE9stame en una l\xEDnea qu\xE9 decidiste y por qu\xE9."].join(`
`)}async function li(e){let a=await Ee("gestion",ec(e));if(!a.datos){g().falla(`telar: no pude encarg\xE1rselo a Gesti\xF3n: ${a.error??"sin respuesta"}`);return}await ri(x.equipoRemoto,e.id),g().estado("telar: Gesti\xF3n est\xE1 revisando el pedido",5e3),await x.leerEquipo()}async function ci(e,a,t=""){let r="";if(a!=="aceptar"){let i=await g().campo({prompt:a==="existe"?`Qu\xE9 le agregas al estado de ${t} (opcional)`:`Qu\xE9 ver\xE1 ${e.persona} (opcional)`,placeHolder:a==="existe"?"va para el jueves":"ahora no, porque\u2026",ignoreFocusOut:!0});if(i===void 0)return;r=i}let o=await qa(x.equipoRemoto,a,e.id,r,t);o.datos?a==="aceptar"&&e.tipo==="tarea"&&g().info(`telar: agregada${o.datos.sugerencia.tarea?` como ${o.datos.sugerencia.tarea}`:""}`):g().falla(`telar: no se pudo: ${o.error??"sin respuesta"}`),await x.leerEquipo()}async function jt(e){await x.leerEquipo();let a=x.sugerencias;return a.length?e&&a.some(r=>r.id===e)?e:a.length===1?a[0].id:(await g().elegir(a.map(r=>({label:`${r.persona}: ${r.titulo.slice(0,80)}`,description:r.tipo==="tarea"?"pide una tarea":`subir ${r.tarea}`,id:r.id})),{title:"Lo que pide el equipo",placeHolder:"elige una entrada"}))?.id??"":(g().info("telar: el equipo no tiene nada esperando"),"")}function di(e){let a=n=>typeof n=="string"?n:n?.hilo??"";async function t(n,s,l=[],c){let u=a(n);if(!u)return!1;let h=await Pe(s,u,c,l);return h.ok?(x.invalidar(),await x.sondear(),!0):(e.avisar({__aviso:`telar: ${h.err.trim().split(`
`).pop()||`\xABtelar hilo ${s}\xBB fall\xF3`}`,nivel:"falla"}),!1)}async function r(n){let s=a(n),l=x.porNombre(s);if(!s||!l)return;let c=(p,f)=>({label:`prioridad ${f}`,description:String(l.prioridad??"")===p?"la que tiene":"",hacer:()=>t(s,"prioridad",[],p)}),u=[{label:l.archivado||!l.vivo?"retomar":"ver",description:l.archivado||!l.vivo?"reabre su tab con su conversaci\xF3n":"",hacer:async()=>{l.archivado||!l.vivo?await t(s,"retomar")&&e.mostrar(s):e.mostrar(s)}},{label:"renombrar",description:"se mueve con \xE9l lo que telar sab\xEDa",hacer:async()=>{let p=await e.anfitrion.campo({title:`Nombre nuevo para \xAB${s}\xBB`,value:s});p&&p!==s&&await t(s,"renombrar",[],p)}},...l.vinculado?[{label:"ver su carpeta y documento",description:l.relativa||l.ruta,hacer:async()=>e.mostrar(`doc:${s}`)}]:[],{label:"vincular a un proyecto",description:l.relativa?`hoy: ${l.relativa}`:"sin carpeta",hacer:()=>o(s)},...l.vinculado?[{label:"desvincular",description:"soltar su carpeta",hacer:()=>t(s,"desvincular")}]:[],{label:"prioridad",separador:!0},c("1","alta"),c("2","media"),c("3","baja"),c("ninguna","ninguna"),{label:"guardar o cerrar",separador:!0},...l.archivado?[{label:"desarchivar",description:"volver a la lista sin abrirlo",hacer:()=>t(s,"desarchivar")}]:[{label:"archivar",description:"cierra el tab y guarda su conversaci\xF3n",hacer:()=>t(s,"archivar",["--cerrar"])}],...l.vivo?[{label:"cerrar",description:"cierra el tab y lo saca de la lista",hacer:()=>t(s,"cerrar")}]:[],...l.remoto?[]:[{label:"llevar a otra m\xE1quina",description:"su conversaci\xF3n viaja; los archivos no",hacer:()=>i(s)}],{label:"olvidar",description:"telar pierde su carpeta, su prioridad y su atenci\xF3n",hacer:async()=>{await e.anfitrion.aviso(`\xBFQue telar olvide \xAB${s}\xBB? Pierde su carpeta, su prioridad y su atenci\xF3n.`,{modal:!0},"Olvidar")==="Olvidar"&&await t(s,"olvidar")}}];await(await e.anfitrion.elegir(u,{title:s}))?.hacer?.()}async function o(n){let s=await we(),l={label:"otra carpeta\u2026",description:"escribir su ruta",ruta:""},c=[...(s.datos?.proyectos??[]).map(p=>({label:p.nombre,description:p.ruta,ruta:String(p.ruta)})),l],u=await e.anfitrion.elegir(c,{title:`Vincular \xAB${n}\xBB a\u2026`,placeHolder:"filtrar"});if(!u)return;let h=u.ruta||await e.anfitrion.campo({title:`La carpeta de \xAB${n}\xBB`,prompt:"relativa a la ra\xEDz del repositorio, o absoluta"});h&&await t(n,"vincular",[],h)}async function i(n){let s=(await oe()).datos?.remotos??[];if(!s.length){e.avisar({__aviso:"telar: no hay m\xE1quinas en [remotos]",nivel:"aviso"});return}let l=s.length===1?s[0]:(await e.anfitrion.elegir(s.map(u=>({label:u.nombre,description:u.destino,x:u})),{title:`\xBFA qu\xE9 m\xE1quina llevo \xAB${n}\xBB?`}))?.x;if(!l)return;e.avisar({__aviso:`llevando \xAB${n}\xBB a ${l.nombre}\u2026`,nivel:"info",ms:4e3});let c=await Pe("llevar",n,l.nombre);if(!c.ok&&/sin subir/.test(c.err)){let u=c.out.split(`
`).filter(p=>p.trim().startsWith("\xB7")).map(p=>p.trim()).join(`
`);if(await e.anfitrion.aviso(`La conversaci\xF3n de \xAB${n}\xBB viaja, los archivos no. Aqu\xED hay trabajo que all\xE1 no va a estar:
${u}`,{modal:!0},"Llevar igual")!=="Llevar igual")return;c=await Pe("llevar",n,l.nombre,["--si"])}if(!c.ok){e.avisar({__aviso:`telar: ${c.err.trim().split(`
`).pop()||"no se llev\xF3"}`,nivel:"falla"});return}x.invalidar(),await x.sondear()}return{"telar.menuHilo":n=>r(n),"telar.irRemoto":n=>{let[s,...l]=String(n??"").split("|");s&&l.length&&e.mostrar(`rem:${s}:${l.join("|")}`)},"telar.ir":n=>e.mostrar(a(n)),"telar.retomar":async n=>{await t(n,"retomar")&&e.mostrar(a(n))},"telar.archivar":n=>t(n,"archivar",["--cerrar"]),"telar.cerrar":n=>t(n,"cerrar"),"telar.archivo":()=>e.barra.alternarArchivo(),"telar.equipoVer":async n=>{let s=await jt(n);s&&(e.mostrar("dashboard"),await e.hoy.abrirEquipo(s))},"telar.equipo":async()=>{let n=await jt();n&&(e.mostrar("dashboard"),await e.hoy.abrirEquipo(n))},"telar.seccion":n=>{if(n)return e.mostrar("dashboard"),e.hoy.abrirSeccion(n)},"telar.app":n=>{if(n)return e.mostrar("dashboard"),e.hoy.abrirApp(n)},"telar.tarea":n=>n?e.hoy.abrirTarea(n):void 0,"telar.hoy":()=>e.mostrar("dashboard"),"telar.actualizar":()=>x.sondear(!0),"telar.tejer":async()=>{await Fa(),await x.sondear()},"telar.nuevo":async()=>{let n=(await e.anfitrion.campo({prompt:"Nombre del hilo nuevo",placeHolder:"faro"}))?.trim();if(!n)return;let s=(await oe()).datos?.remotos??[],l="";if(s.length){let c=await e.anfitrion.elegir([{label:"Local",description:"en esta m\xE1quina",remoto:""},...s.map(u=>({label:`Remoto: ${u.nombre}`,description:u.destino,remoto:u.nombre}))],{placeHolder:`\xBFD\xF3nde vive el agente de \xAB${n}\xBB?`});if(!c)return;l=c.remoto}await e.anfitrion.irAHilo(n,!0,l)},"telar.tareas":()=>{},"telar.tareasActualizar":()=>{}}}var ui={ahora:"",fecha:"",nombreDia:"",semana:0,agenda:null,pendientes:[],declarados:[],fallas:[]},xe,ta={filas:null,hora:0},qt=[],pi=300*1e3,za;function hi(){return ta.hora}function qe(e=45e3,a=!1){let t=a||Date.now()-ta.hora>pi;return!t&&xe&&Date.now()-xe.hora<e?Promise.resolve(xe.dia):(za||(za=ac(t).finally(()=>{za=void 0})),za)}async function ac(e){let a=await Rt(!e);if(!a.datos){let i={...xe?.dia??ui,error:a.error};return xe={dia:i,hora:Date.now()},i}let t=a.datos;e&&(ta={filas:t.agenda??null,hora:Date.now()},qt=(t.pendientes??[]).filter(i=>i.proveedor));let r=(t.pendientes??[]).filter(i=>!i.proveedor),o={ahora:t.ahora??new Date().toISOString(),fecha:t.fecha??"",nombreDia:t.dia??"",semana:t.semana??0,agenda:e?t.agenda??null:ta.filas,pendientes:e?t.pendientes??[]:[...r,...qt],declarados:t.proveedores?.declarados??[],fallas:t.proveedores?.fallas??[]};return xe={dia:o,hora:Date.now()},o}var Ft=new Map;async function Tt(e){let a=Ft.get(e);if(a&&Date.now()-a.hora<pi)return a.dia;let t=await Rt(!1,e),r=t.datos,o=r?{ahora:r.ahora??new Date().toISOString(),fecha:r.fecha??e,nombreDia:r.dia??"",semana:r.semana??0,agenda:r.agenda??null,pendientes:r.pendientes??[],declarados:r.proveedores?.declarados??[],fallas:r.proveedores?.fallas??[]}:{...ui,fecha:e,error:t.error};return r&&Ft.set(e,{dia:o,hora:Date.now()}),o}function U(){Ft.clear(),xe=void 0,ta={filas:null,hora:0},qt=[]}function ee(e,a=""){let t=Date.parse(`${e.fecha||new Date().toISOString().slice(0,10)}T00:00:00`);return e.pendientes.filter(r=>!r.hecho&&(r.pestana??"")===a).map(r=>{let o=r.cuando??"",i=o?Math.round((Date.parse(o.slice(0,10)+"T00:00:00")-t)/864e5):null,n=!!r.en_curso,s=(r.avance??"").split(" ")[0].split(":")[0];return{fila:r,ref:r.ref||r.id,texto:r.texto,hilo:r.hilo??"",cuando:o,dias:i,enCurso:n,avance:s,urgencia:s?-1e3+(i??0)/1e3:(i??30)-(n?.5:0),urgente:s?!0:i!==null?i<=7:n}}).sort((r,o)=>a?0:r.urgencia-o.urgencia||r.ref.localeCompare(o.ref))}function I(e,a,t="",r=""){return`<section class="bloque" style="--c: var(--${a})"><h2 class="sec"><span class="marca"></span>${d(e)}${t?`<span class="cuenta">${d(t)}</span>`:""}${r?`<span class="acciones">${r}</span>`:""}</h2>`}function he(e,a,t,r="",o=""){return`<a class="atajo" data-accion="${d(t)}"${r?` data-valor="${d(r)}"`:""}${o?` title="${d(o)}"`:""}><kbd>${d(e)}</kbd><span>${d(a)}</span></a>`}function fi(e,a){return`<span class="atajo pista"><kbd>${d(e)}</kbd><span>${d(a)}</span></span>`}var Q={persona:"",nombres:[]};function mi(e){if(!e.trim())return!0;let a=r=>M(r).split(/\s+/)[0]??"",t=a(e);return[Q.persona,...Q.nombres].some(r=>!!r&&a(r)===t)}function vi(e,a){return e.trim()?mi(e):a}function gi(e,a=!0){return` data-dueno="${d(e)}" data-mia="${vi(e,a)?1:0}" data-sin="${!e.trim()&&!a?1:0}"`}function bi(e,a=!1){let t=e.map(([n])=>n),r=e.filter(([n])=>n.trim()&&!mi(n)).length,o=e.filter(([n,s])=>!n.trim()&&!s).length;if(!r&&!o)return"";let i=e.filter(([n,s])=>vi(n,s)).length;return`<div class="titulo-tareas duenos-t"><span class="modos"><button data-dueno-filtro="" title="todas, m\xEDas y de otros">${a?"\u2217":"todas"} ${t.length}</button><button data-dueno-filtro="mias" title="las m\xEDas: mis tareas sin due\xF1o y lo que est\xE1 a mi nombre">${a?"yo":"m\xEDas"} ${i}</button><button data-dueno-filtro="otros" title="de otros: a nombre de otra persona (a qui\xE9n empujar)">${a?"\u2192":"de otros"} ${r}</button><button data-dueno-filtro="sin" title="sin responsable: pendientes de un proyecto que no dicen qui\xE9n (tus tareas sin due\xF1o son tuyas)">${a?"\u2205":"sin responsable"} ${o}</button></span></div>`}function yi(e,a=!1){let t=new Map;for(let r of e)r&&t.set(r,(t.get(r)??0)+1);return t.size<2?"":'<div class="titulo-tareas areas-t"><span class="modos"><button data-area-filtro="">todas</button>'+[...t].sort((r,o)=>o[1]-r[1]).map(([r,o])=>`<button data-area-filtro="${d(r)}" title="${d(r)}">${d(a?r.slice(0,3):r)} ${o}</button>`).join("")+"</span></div>"}function Fe(e){return e===null?"<span></span>":e<0?`<span class="venc">${e}d</span>`:e===0?'<span class="pronto">hoy</span>':e===1?'<span class="pronto">ma\xF1ana</span>':`<span class="dim">${e}d</span>`}var wi=B("dia"),xi=`
const raiz = document.getElementById('dia');
let estado = Object.assign({ modo: 'urgentes', q: '', todas: false, pq: '', po: 'fecha', to: 'urgencia', area: '', dueno: '', pc: false, pf: {}, ordenP: '' }, vscode.getState() || {});
// antes, \xABarea\xBB filtraba por la carpeta de la ra\xEDz (brinca, nico\u2026); ahora es el \xE1rea del documento
// \xABtareas\xBB abre en \xABesta semana\xBB (8-oct): lo que estaba guardado como \xABtodas\xBB pasa una vez a ese modo
if (!estado.tmv) { if (!estado.tm || estado.tm === 'todas') estado.tm = 'semana'; estado.tmv = 1; }
if (!estado.pfv) { estado.pf = Object.assign({}, estado.pf || {}); if (estado.pf.area) { estado.pf.raiz = estado.pf.area; estado.pf.area = ''; } estado.pfv = 2; }
// el \xE1rea y el due\xF1o filtran antes que todo lo dem\xE1s: lo que queda fuera ni se cuenta
function pasa(f) { return pasaArea(f, estado.area) && pasaDueno(f, estado.dueno); }
function pasaArea(f, area) { return !area || f.dataset.area === area; }
function pasaDueno(f, dueno) {
  if (dueno === 'mias' && f.dataset.mia === '0') return false;
  if (dueno === 'otros' && (f.dataset.mia !== '0' || f.dataset.sin === '1')) return false;
  if (dueno === 'sin' && f.dataset.sin !== '1') return false;
  return true;
}
// c\xF3digo de mayor a menor, con los n\xFAmeros como n\xFAmeros (T130 antes que T81): lo m\xE1s nuevo
// arriba, como el orden \xABn\xFAmero descendente\xBB de flow. El texto, sin tildes.
function comparar(a, b) {
  if (estado.to === 'codigo') return b.dataset.ref.localeCompare(a.dataset.ref, undefined, { numeric: true });
  if (estado.to === 'alfa') return a.dataset.alfa.localeCompare(b.dataset.alfa);
  return Number(a.dataset.orden) - Number(b.dataset.orden);
}
function guardar() { vscode.setState(estado); }
function norm(t) { return t.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase(); }
function filas() { const c = document.getElementById('tareas'); return c ? Array.prototype.slice.call(c.querySelectorAll('.tarea')) : []; }
function visibles() { return filas().filter(function (f) { return !f.hidden; }); }
function aplicar() {
  aplicarArea();   // tambi\xE9n en \xABrevisar\xBB, que no tiene la lista de hoy
  const c = document.getElementById('tareas'); if (!c) return;
  // el \xE1rea filtra antes que todo lo dem\xE1s: lo de otra \xE1rea ni se cuenta
  const todas = filas().filter(pasa);
  filas().forEach(function (f) { if (todas.indexOf(f) < 0) f.hidden = true; });
  const partes = norm(estado.q).split(/\\s+/).filter(Boolean);
  let lista = todas;
  if (partes.length) lista = todas.filter(function (f) { return partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); });
  else if (estado.modo === 'urgentes') lista = todas.filter(function (f) { return f.dataset.urgente === '1'; });
  else if (estado.modo === 'propuestas') lista = todas.filter(function (f) { return f.dataset.propuesta === '1'; });
  lista.sort(comparar);
  const limite = partes.length || estado.todas || estado.modo === 'propuestas' ? lista.length : (estado.modo === 'urgentes' ? 8 : 15);
  todas.forEach(function (f) { f.hidden = true; });
  const mas = document.getElementById('tareas-mas');
  lista.forEach(function (f, i) {
    c.insertBefore(f, mas);
    f.hidden = i >= limite;
  });
  const resto = lista.length - Math.min(limite, lista.length);
  mas.hidden = resto <= 0;
  mas.textContent = '+ ' + resto + ' m\xE1s';
  const vacio = document.getElementById('tareas-vacio');
  vacio.hidden = lista.length > 0;
  vacio.textContent = partes.length ? 'sin resultados' : estado.modo === 'propuestas' ? 'nada que decidir' : 'nada urgente';
  document.querySelectorAll('[data-orden-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenT === estado.to); });
  document.querySelectorAll('[data-modo-tareas]').forEach(function (b) { b.classList.toggle('activo', !partes.length && b.dataset.modoTareas === estado.modo); });
  aplicarArea();
  const cuenta = document.getElementById('tareas-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? lista.length + ' de ' + todas.length : '';
}
// el filtro por \xE1rea fuera de la lista de hoy (la pesta\xF1a \xABrevisar\xBB) y el bot\xF3n activo
function aplicarArea() {
  aplicarTareas();
  document.querySelectorAll('[data-area-filtro]').forEach(function (b) { b.classList.toggle('activo', b.dataset.areaFiltro === estado.area); });
  document.querySelectorAll('[data-dueno-filtro]').forEach(function (b) { b.classList.toggle('activo', b.dataset.duenoFiltro === (estado.dueno || '')); });
}
// la pesta\xF1a \xABtareas\xBB: todas, filtradas por modo (por revisar, vencidas\u2026), \xE1rea, due\xF1o y lo buscado
function enModo(f, modo) {
  const m = modo || estado.tm || 'semana', d = f.dataset.dias === '' ? null : Number(f.dataset.dias);
  if (m === 'revisar') return f.dataset.rev === '1';
  if (m === 'vencidas') return d !== null && d < 0;
  if (m === 'semana') return f.dataset.sem === '1';
  if (m === 'estrella') return f.dataset.estrella === '1';
  if (m === 'encurso') return f.dataset.encurso === '1';
  if (m === 'sinfecha') return d === null;
  return true;
}
// el orden de la columna elegida en \xABtareas\xBB; sin elegir, la urgencia. Lo vac\xEDo siempre al final
function compararColumna(a, b) {
  const k = estado.ordenC || '';
  if (!k) return Number(a.dataset.orden) - Number(b.dataset.orden);
  const x = a.dataset[k] || '', y = b.dataset[k] || '';
  if (x !== y) {
    if (!x || !y) return x ? -1 : 1;
    if (k === 'dias') return Number(x) - Number(y);
    // el c\xF3digo, de mayor a menor con los n\xFAmeros como n\xFAmeros (lo m\xE1s nuevo arriba)
    if (k === 'ref') return y.localeCompare(x, undefined, { numeric: true });
    return x.localeCompare(y);
  }
  return Number(a.dataset.orden) - Number(b.dataset.orden);
}
function aplicarTareas() {
  const c = document.getElementById('tareas-t'); if (!c) return;
  const todas = Array.prototype.slice.call(c.querySelectorAll('.tarea'));
  const partes = norm(estado.tq || '').split(/s+/).filter(Boolean);
  const vacio = document.getElementById('tareas-t-vacio');
  todas.sort(compararColumna);
  document.querySelectorAll('.tareas-cab [data-orden-c]').forEach(function (s) {
    const es = s.dataset.ordenC === (estado.ordenC || '');
    s.classList.toggle('activo', es);
    s.textContent = es ? (s.dataset.ordenC === 'ref' ? '\u25BC' : '\u25B2') : '\u2195';
  });
  let n = 0;
  todas.forEach(function (f) {
    c.insertBefore(f, vacio);
    f.hidden = !(pasa(f) && enModo(f) && partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }));
    if (!f.hidden) n += 1;
  });
  vacio.hidden = n > 0 || !todas.length;
  vacio.textContent = partes.length ? 'sin resultados' : 'nada aqu\xED';
  // en \xABesta semana\xBB, lo dem\xE1s queda plegado detr\xE1s de \xABver todas\xBB: cu\xE1ntas m\xE1s hay con los otros filtros
  const mas = document.getElementById('tareas-t-mas');
  if (mas) {
    const resto = (estado.tm || 'semana') === 'semana'
      ? todas.filter(function (f) { return f.hidden && pasa(f) && partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); }).length : 0;
    mas.hidden = resto === 0;
    mas.textContent = 'ver todas (' + resto + ' m\xE1s)';
    c.appendChild(mas);
  }
  document.querySelectorAll('[data-modo-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.modoT === (estado.tm || 'semana')); });
  // cada bot\xF3n dice cu\xE1ntas quedar\xEDan si se lo eligiera, con lo dem\xE1s que est\xE1 filtrado (la b\xFAsqueda y
  // las otras filas de filtros): el del filtro activo es lo que se ve
  const conTexto = function (f) { return partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); };
  const cuantas = function (cond) { return todas.filter(function (f) { return conTexto(f) && cond(f); }).length; };
  const poner = function (b, n) { b.textContent = b.textContent.replace(/\\s*\\d+$/, '') + ' ' + n; b.classList.toggle('vacio-m', n === 0); };
  document.querySelectorAll('#revisar [data-modo-t]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f, b.dataset.modoT) && pasaArea(f, estado.area) && pasaDueno(f, estado.dueno); }));
  });
  document.querySelectorAll('#revisar [data-area-filtro]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f) && pasaArea(f, b.dataset.areaFiltro) && pasaDueno(f, estado.dueno); }));
  });
  document.querySelectorAll('#revisar [data-dueno-filtro]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f) && pasaArea(f, estado.area) && pasaDueno(f, b.dataset.duenoFiltro); }));
  });
  document.querySelectorAll('[data-orden-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenT === estado.to); });
  const cuenta = document.getElementById('tareas-t-cuenta');
  if (cuenta) cuenta.textContent = partes.length || (estado.tm || 'semana') !== 'todas' ? n + ' de ' + todas.length : '';
}
// la pantalla de proyectos: filtrar por todas las palabras, ordenar por nombre o por fecha
function proyectosVisibles() { const c = document.getElementById('proyectos'); return c ? Array.prototype.slice.call(c.querySelectorAll('.proy')).filter(function (f) { return !f.hidden; }) : []; }
function aplicarProyectos() {
  const c = document.getElementById('proyectos'); if (!c) return;
  const todas = Array.prototype.slice.call(c.querySelectorAll('.proy'));
  const partes = norm(estado.pq).split(/\\s+/).filter(Boolean);
  // por defecto: por estado (en marcha arriba, cerrado y sin estado abajo) y despu\xE9s por nombre. Una
  // columna elegida ordena por ella en su sentido natural (lo reciente y lo con hilo primero); lo vac\xEDo al final
  const k = estado.ordenP || '';
  const porNombre = function (a, b) { return a.dataset.nombre.localeCompare(b.dataset.nombre); };
  todas.sort(function (a, b) {
    if (!k || k === 'estado') return (Number(a.dataset.rango) - Number(b.dataset.rango)) || porNombre(a, b);
    const x = a.dataset[k] || '', y = b.dataset[k] || '';
    if (x !== y) {
      if (!x || !y) return x ? -1 : 1;
      return k === 'fecha' || k === 'hilo' ? (x < y ? 1 : -1) : x.localeCompare(y);
    }
    return porNombre(a, b);
  });
  document.querySelectorAll('.proy-cab [data-orden-p]').forEach(function (s) {
    const es = s.dataset.ordenP === k;
    s.classList.toggle('activo', es);
    s.textContent = es ? (k === 'fecha' || k === 'hilo' ? '\u25BC' : '\u25B2') : '\u2195';
  });
  const vacio = document.getElementById('proyectos-vacio');
  let n = 0;
  todas.forEach(function (f) {
    c.insertBefore(f, vacio);
    // los cerrados se esconden salvo que se pidan, o que se los busque por nombre
    const pf = estado.pf || {};
    f.hidden = !partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; })
      || (f.dataset.cerrado === '1' && !estado.pc && !partes.length && pf.tipo !== f.dataset.tipo)
      || (!!pf.raiz && f.dataset.raiz !== pf.raiz) || (!!pf.area && f.dataset.unidad !== pf.area)
      || (!!pf.tipo && f.dataset.tipo !== pf.tipo)
      || (!!pf.hilo && f.dataset.hilo === '0') || (!!pf.pend && !(Number(f.dataset.pend) > 0));
    f.classList.toggle('primera', !f.hidden && n === 0 && partes.length > 0);
    if (!f.hidden) n += 1;
  });
  vacio.hidden = n > 0;
  vacio.textContent = 'sin resultados';
  const cuenta = document.getElementById('proyectos-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? n + ' de ' + todas.length : '';
  const vc = document.getElementById('ver-cerrados');
  if (vc) vc.classList.toggle('activo', !!estado.pc);
  document.querySelectorAll('[data-pf]').forEach(function (b) {
    const v = (estado.pf || {})[b.dataset.pf] || '';
    b.classList.toggle('activo', v === b.dataset.pv);
  });
}
// elegir un proyecto: se marca al tiro y se pide su detalle (la derecha la cambia la extensi\xF3n)
function elegirProy(f) {
  if (!f) return;
  document.querySelectorAll('.proy.sel').forEach(function (x) { x.classList.remove('sel'); });
  f.classList.add('sel');
  f.scrollIntoView({ block: 'nearest' });
  vscode.postMessage({ tipo: 'accion', accion: 'proy-sel', valor: f.dataset.valor });
}
function moverProy(paso) {
  const vis = proyectosVisibles(); if (!vis.length) return;
  const i = vis.findIndex(function (f) { return f.classList.contains('sel'); });
  elegirProy(vis[i < 0 ? 0 : Math.max(0, Math.min(vis.length - 1, i + paso))]);
}
// el globo: el texto entero de una tarea al detenerse sobre ella, cuando la fila lo corta
const globo = document.createElement('div'); globo.id = 'globo'; globo.hidden = true; document.body.appendChild(globo);
let globoEspera = null;
function esconderGlobo() { clearTimeout(globoEspera); globo.hidden = true; }
document.addEventListener('mouseover', function (e) {
  const f = e.target.closest && e.target.closest('[data-completo]');
  if (!f) return esconderGlobo();
  if (!globo.hidden && globo.dataset.de === f.dataset.valor) return;
  esconderGlobo();
  globoEspera = setTimeout(function () {
    globo.textContent = f.dataset.completo; globo.dataset.de = f.dataset.valor; globo.hidden = false;
    const r = f.getBoundingClientRect(), g = globo.getBoundingClientRect();
    const x = Math.max(4, Math.min(r.left + 12, window.innerWidth - g.width - 4));
    const abajo = r.bottom + 4 + g.height <= window.innerHeight;
    globo.style.left = x + 'px';
    globo.style.top = (abajo ? r.bottom + 4 : Math.max(4, r.top - g.height - 4)) + 'px';
  }, 350);
});
document.addEventListener('mouseleave', esconderGlobo);
document.addEventListener('scroll', esconderGlobo, true);
// un lienzo que pide guardar su memoria: solo se acepta de un iframe de lienzo de este panel, y
// la extensi\xF3n decide el archivo (el que declar\xF3 la p\xE1gina), nunca el lienzo
window.addEventListener('message', function (e) {
  const d = e.data;
  if (!d || d.lienzo !== 'guardar' || typeof d.llave !== 'string' || typeof d.datos !== 'string') return;
  const propio = Array.prototype.some.call(document.querySelectorAll('iframe.lienzo'), function (f) { return f.contentWindow === e.source; });
  if (propio) vscode.postMessage({ tipo: 'lienzo-guardar', valor: d.llave, datos: d.datos });
});
window.addEventListener('message', function (e) {
  // un pedazo de la p\xE1gina (el formulario de un peri\xF3dico): se cambia sin tocar lo escrito
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.tipo === 'proy-pend') {   // cu\xE1ntos pendientes tiene cada proyecto: llega despu\xE9s de la lista
    const c = e.data.cuentas || {}; let n = 0;
    document.querySelectorAll('.proy').forEach(function (f) { const k = c[f.dataset.valor] || 0; f.dataset.pend = String(k); if (k) n += 1; });
    const cp = document.getElementById('cuenta-pend'); if (cp) cp.textContent = String(n);
    return aplicarProyectos();
  }
  if (e.data.tipo === 'parcial') { const el = document.getElementById(e.data.id); if (el) { el.innerHTML = e.data.html; filtrarSkills(); } return; }
  if (e.data.tipo !== 'dia') return;
  esconderGlobo();
  const activo = document.activeElement, id = activo && activo.id;
  const pos = id === 'buscar' || id === 'buscar-p' || id === 'buscar-t' ? activo.selectionStart : 0;
  // lo que se est\xE1 escribiendo sobre una reuni\xF3n sobrevive al repintado de cada minuto
  const ta = document.getElementById('ev-texto');
  const previo = ta ? { ev: ta.dataset.evento, v: ta.value, foco: activo === ta, s: ta.selectionStart } : null;
  raiz.innerHTML = e.data.html;
  const nt = document.getElementById('ev-texto');
  if (previo && nt && nt.dataset.evento === previo.ev) { nt.value = previo.v; if (previo.foco) { nt.focus(); nt.setSelectionRange(previo.s, previo.s); } }
  const nb = document.getElementById('buscar');
  if (nb) { nb.value = estado.q; if (id === 'buscar') { nb.focus(); nb.setSelectionRange(pos, pos); } }
  const nt2 = document.getElementById('buscar-t');
  if (nt2) { nt2.value = estado.tq || ''; if (id === 'buscar-t') { nt2.focus(); nt2.setSelectionRange(pos, pos); } }
  const np = document.getElementById('buscar-p');
  if (np) { np.value = estado.pq; if (id === 'buscar-p' || id !== 'buscar') { np.focus(); np.setSelectionRange(pos || np.value.length, pos || np.value.length); } }
  aplicar(); aplicarProyectos();
});
// \u2500\u2500 el formulario de un proceso peri\xF3dico \u2500\u2500
let esperaHorario = 0;
function filtrarSkills() {
  const f = document.getElementById('per-skill-filtro');
  if (!f) return;
  const q = (f.value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
  document.querySelectorAll('#per-skills .skill').forEach(function (x) { x.hidden = !!q && x.dataset.texto.indexOf(q) < 0; });
}
function formPer() {
  const v = function (id) { const el = document.getElementById(id); return el ? el.value : ''; };
  const form = document.getElementById('form-per');
  return { nombre: v('per-nombre'), descripcion: v('per-desc'), tipo: form.classList.contains('tipo-comando') ? 'comando' : 'mensaje',
    mensaje: v('per-mensaje'), comando: v('per-comando'), hilo: v('per-hilo'), max: v('per-max'), args: v('per-args'),
    cuando: v('per-cuando'), carpeta: v('per-carpeta'), activo: !!(document.getElementById('per-activo') || {}).checked };
}
function guardarPer() { vscode.postMessage({ tipo: 'accion', accion: 'per-guardar', valor: JSON.stringify(formPer()) }); }
document.addEventListener('input', function (e) {
  if (e.target.id === 'per-cuando') { clearTimeout(esperaHorario); const c = e.target.value; esperaHorario = setTimeout(function () { vscode.postMessage({ tipo: 'per-horario', valor: c }); }, 350); return; }
  if (e.target.id === 'per-skill-filtro') return filtrarSkills();
});
document.addEventListener('change', function (e) {
  if (e.target.id === 'per-carpeta') vscode.postMessage({ tipo: 'per-skills', valor: e.target.value.trim() });
});
document.addEventListener('click', function (e) {
  // guardar lleva lo escrito: se adelanta al manejador general, que mandar\xEDa la acci\xF3n vac\xEDa
  if (e.target.closest('[data-accion="per-guardar"]')) { e.preventDefault(); e.stopPropagation(); return guardarPer(); }
  const t = e.target.closest('[data-per-tipo]');
  if (t) { const f = document.getElementById('form-per'); f.classList.remove('tipo-mensaje', 'tipo-comando'); f.classList.add('tipo-' + t.dataset.perTipo);
    document.querySelectorAll('[data-per-tipo]').forEach(function (x) { x.classList.toggle('activa', x === t); }); return; }
  const h = e.target.closest('[data-per-horario]');
  if (h) { const c = document.getElementById('per-cuando'); c.value = h.dataset.perHorario; vscode.postMessage({ tipo: 'per-horario', valor: c.value }); return; }
  const sk = e.target.closest('[data-skill]');
  if (sk) {
    const m = document.getElementById('per-mensaje');
    // la skill reemplaza a la que hubiera al principio; lo escrito despu\xE9s se queda
    const resto = m.value.replace(/^\\/[\\w:.-]+\\s*/, '');
    m.value = '/' + sk.dataset.skill + ' ' + resto;
    document.querySelectorAll('#per-skills .skill').forEach(function (x) { x.classList.toggle('activa', x === sk); });
    const hilo = document.getElementById('per-hilo'), nombre = document.getElementById('per-nombre');
    if (nombre && !nombre.value && !nombre.disabled) nombre.value = sk.dataset.skill.replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
    if (hilo && !hilo.value) hilo.placeholder = sk.dataset.skill;
    m.focus(); m.setSelectionRange(m.value.length, m.value.length);
  }
}, true);
document.addEventListener('input', function (e) {
  if (e.target.id === 'buscar-p') { estado.pq = e.target.value; guardar(); return aplicarProyectos(); }
  if (e.target.id === 'buscar-t') { estado.tq = e.target.value; guardar(); return aplicarTareas(); }
  if (e.target.id !== 'buscar') return;
  estado.q = e.target.value; estado.todas = false; guardar(); aplicar();
});
document.addEventListener('click', function (e) {
  const u = e.target.closest('[data-url]');
  if (u) { e.preventDefault(); e.stopPropagation(); return vscode.postMessage({ tipo: 'url', url: u.dataset.url }); }
  const ot = e.target.closest('[data-orden-t]');
  if (ot) { estado.to = ot.dataset.ordenT; guardar(); return aplicar(); }
  const oc = e.target.closest('[data-orden-c]');
  if (oc) { estado.ordenC = estado.ordenC === oc.dataset.ordenC ? '' : oc.dataset.ordenC; guardar(); return aplicarTareas(); }
  if (e.target.closest('#tareas-t-mas')) { estado.tm = 'todas'; guardar(); return aplicarTareas(); }
  const mt = e.target.closest('[data-modo-t]');
  if (mt) { estado.tm = mt.dataset.modoT; guardar(); return aplicarTareas(); }
  const op = e.target.closest('[data-orden-p]');
  // una flecha ordena por su columna; otra vez, vuelve al orden por defecto (estado y nombre)
  if (op) { estado.ordenP = estado.ordenP === op.dataset.ordenP ? '' : op.dataset.ordenP; guardar(); return aplicarProyectos(); }
  if (e.target.closest('#ver-cerrados')) { estado.pc = !estado.pc; guardar(); return aplicarProyectos(); }
  // un filtro de la lista de proyectos: \xE1rea y tipo eligen uno; \xABcon hilo\xBB y \xABcon pendientes\xBB se prenden y apagan
  const bf = e.target.closest('[data-pf]');
  if (bf) { const pf = Object.assign({}, estado.pf || {}), k = bf.dataset.pf;
    pf[k] = pf[k] === bf.dataset.pv && (k === 'hilo' || k === 'pend') ? '' : bf.dataset.pv;
    estado.pf = pf; guardar(); return aplicarProyectos(); }
  const fp = e.target.closest('.proy[data-accion="proy-sel"]');
  // el \u22EF de una fila: la elige y abre el men\xFA de acciones (lo manda el manejador general)
  if (fp && e.target.closest('.menu-fila')) elegirProy(fp);
  else if (fp) { e.preventDefault(); return elegirProy(fp); }
  // un enlace del README: lo abre la extensi\xF3n (un archivo del repositorio o el navegador)
  const ln = e.target.closest('.proy-readme a[href]');
  if (ln) { e.preventDefault(); const base = ln.closest('.proy-readme').dataset.base || '';
    return vscode.postMessage({ tipo: 'accion', accion: 'proy-enlace', valor: ln.getAttribute('href'), datos: base }); }
  const ar = e.target.closest('[data-area-filtro]');
  if (ar) { estado.area = ar.dataset.areaFiltro; guardar(); aplicar(); return aplicarArea(); }
  const du = e.target.closest('[data-dueno-filtro]');
  if (du) { estado.dueno = du.dataset.duenoFiltro; guardar(); aplicar(); return aplicarArea(); }
  const m = e.target.closest('[data-modo-tareas]');
  if (m) { estado.modo = m.dataset.modoTareas; estado.q = ''; estado.todas = false; guardar(); const b = document.getElementById('buscar'); if (b) b.value = ''; return aplicar(); }
  if (e.target.closest('#tareas-mas')) { estado.todas = true; guardar(); return aplicar(); }
  const a = e.target.closest('[data-accion]');
  // el \u2713 tacha la fila al tiro: la lista se relee cuando el proveedor termine
  // (tambi\xE9n los \u2713 de la columna de acciones: la fila se tacha y el \u2713 gira mientras el proveedor trabaja)
  if (a && (a.dataset.accion === 'hecha' || a.dataset.accion === 'hecha-fila' || a.dataset.accion === 'hecha-vineta')) {
    const f = a.closest('.tarea'); if (f) f.classList.add('marcada');
    if (a.classList.contains('rap')) a.classList.add('girando');
  }
  // un bot\xF3n que manda lo escrito en un campo (el de escribirle al agente sobre una reuni\xF3n)
  const campo = a && a.dataset.campo ? document.getElementById(a.dataset.campo) : null;
  if (campo && !campo.value.trim()) { campo.focus(); return; }
  if (a) vscode.postMessage({ tipo: 'accion', accion: a.dataset.accion, valor: a.dataset.valor, nuevo: e.metaKey || e.ctrlKey, datos: campo ? campo.value : undefined });
  if (campo) campo.value = '';
});
document.addEventListener('keydown', function (e) {
  // un di\xE1logo de la p\xE1gina web (un campo, un men\xFA: src/web/pagina.ts) se queda con sus teclas: nada de atajos
  if (e.target && e.target.closest && e.target.closest('dialog')) return;
  // escribi\xE9ndole al agente sobre una reuni\xF3n: las letras son del campo; \u2318\u23CE env\xEDa, \u238B sale del campo
  const activo = document.activeElement;
  if (activo && (activo.id === 'ev-texto' || activo.id === 'plan-texto')) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); const b = document.getElementById(activo.id === 'ev-texto' ? 'ev-enviar' : 'plan-enviar'); if (b) b.click(); return; }
    if (e.key === 'Escape') { e.preventDefault(); activo.blur(); }
    return;
  }
  // escribiendo en el formulario de un peri\xF3dico: las letras son del campo, no atajos
  if (document.getElementById('form-per')) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); return guardarPer(); }
    const el = document.activeElement;
    const escribiendo = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT');
    if (e.key === 'Escape') { e.preventDefault(); if (escribiendo) return el.blur(); return vscode.postMessage({ tipo: 'accion', accion: 'per-cancelar' }); }
    if (escribiendo) return;
  }
  const bp = document.getElementById('buscar-p');
  if (bp && document.activeElement === bp) {         // en proyectos: \u23CE abre el primero que calza
    if (e.key === 'Escape') { e.preventDefault(); if (bp.value) { bp.value = ''; estado.pq = ''; guardar(); aplicarProyectos(); } else vscode.postMessage({ tipo: 'accion', accion: 'dia' }); }
    else if (e.key === 'Enter') { e.preventDefault(); const vis = proyectosVisibles(); const f = vis.find(function (x) { return x.classList.contains('sel'); }) || vis[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); moverProy(e.key === 'ArrowDown' ? 1 : -1); }
    return;
  }
  if (bp && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'j' || e.key === 'k')) { e.preventDefault(); return moverProy(e.key === 'ArrowDown' || e.key === 'j' ? 1 : -1); }
  if (bp && e.key === 'Enter') { const f = document.querySelector('.proy.sel'); if (f && !f.hidden) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); } }
  if (bp && e.key === 'Escape') { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'dia' }); }
  if (bp && e.key === '/') { e.preventDefault(); bp.focus(); return; }
  const b = document.getElementById('buscar');
  if (b && document.activeElement === b) {           // escribiendo: las letras son de la b\xFAsqueda
    if (e.key === 'Escape') { e.preventDefault(); if (b.value) { b.value = ''; estado.q = ''; guardar(); aplicar(); } else b.blur(); }
    else if (e.key === 'Enter') { e.preventDefault(); const f = visibles()[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor, nuevo: e.metaKey || e.ctrlKey }); }
    return;
  }
  // la ficha de una tarea: \u23CE la acci\xF3n principal, \u2190 \u2192 la propuesta anterior o siguiente, \u238B vuelve a hoy
  if (document.getElementById('ficha-tarea') && !e.metaKey && !e.ctrlKey && !e.altKey) {
    const acc = { Enter: 'tarea-principal', ArrowRight: 'tarea-siguiente', ArrowLeft: 'tarea-anterior', Escape: 'volver-ficha' }[e.key];
    if (acc) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: acc }); }
  }
  // en la ficha de un proceso peri\xF3dico: \u23CE lo corre ahora, \u238B vuelve a la lista
  if (document.getElementById('ficha-per') && !e.metaKey && !e.ctrlKey && !e.altKey) {
    if (e.key === 'Enter') { e.preventDefault(); return vscode.postMessage({ tipo: 'tecla', k: '\u23CE' }); }
    if (e.key === 'Escape') { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'periodicos' }); }
  }
  // en el calendario, \u2190 \u2192 cambian de d\xEDa
  if (document.getElementById('cal-nav') && !e.metaKey && !e.ctrlKey && !e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
    e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'cal-dia', valor: e.key === 'ArrowLeft' ? '-1' : '1' });
  }
  // en \xABtareas\xBB: escribir en la b\xFAsqueda; \u23CE abre la primera que se ve; / va a buscar
  const bt = document.getElementById('buscar-t');
  if (bt && document.activeElement === bt) {
    if (e.key === 'Escape') { e.preventDefault(); if (bt.value) { bt.value = ''; estado.tq = ''; guardar(); aplicarTareas(); } else bt.blur(); return; }
    if (e.key !== 'Enter') return;
  }
  if (bt && e.key === '/') { e.preventDefault(); bt.focus(); return; }
  if (document.getElementById('revisar') && e.key === 'Enter') {
    const f = document.querySelector('#revisar .tarea:not([hidden])');
    if (f) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor }); }
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;    // los atajos con modificador son de VS Code
  if (e.key === '/') { e.preventDefault(); if (b) b.focus(); return; }
  if (e.key === 'Escape') return vscode.postMessage({ tipo: 'accion', accion: 'volver' });
  if (e.key.length === 1) { e.preventDefault(); vscode.postMessage({ tipo: 'tecla', k: e.key }); }
});
vscode.postMessage({ tipo: 'listo' });
`;var Ma=56,$i=30,Di=B("plan");function P(e){return d(String(e??"")).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")}function G(e,a,t=""){return`<div class="plan-fila${t?" "+t:""}"><span class="k">${P(e)}</span><span class="v">${a}</span></div>`}function Ri(e,a,t){let r=[];if(!e)return r.push(I("plan del d\xEDa","amarillo")),r.push(`<div class="vacio${a?" falla":""}">${d(a||(t?"leyendo el plan\u2026":"sin plan"))}</div></section>`),r;let o=[...e.dias??[]].sort(),i=o.indexOf(e.dia),n=i>0?o[i-1]:i<0?o.filter(v=>v<e.dia).pop():void 0,s=i>=0&&i<o.length-1?o[i+1]:i<0?o.find(v=>v>e.dia):void 0,l='<div class="plan-nav">'+(n?`<a data-accion="plan-dia" data-valor="${d(n)}">\u2039 ${d(n)}</a>`:"<span></span>")+`<b>${d(e.dia)}</b>`+(s?`<a data-accion="plan-dia" data-valor="${d(s)}">${d(s)} \u203A</a>`:"")+`<a data-accion="plan-dia" data-valor="">hoy</a><span>${e.desde&&e.desde!=="aqu\xED"?`le\xEDdo de ${d(e.desde)}`:"le\xEDdo aqu\xED"}</span></div>`;if(r.push(I(e.nombre||"plan del d\xEDa","amarillo","","")),r.push(l),e.aviso&&r.push(`<div class="vacio falla">${d(e.aviso)}</div>`),e.contenido===null||e.contenido===void 0)return r.push(`<div class="vacio">no hay plan del ${d(e.dia)}</div></section>`),r;if(e.formato==="md")return r.push(`<div class="plan-txt"><p style="white-space:pre-wrap">${d(String(e.contenido))}</p></div>${ki(e)}</section>`),r;let c=e.contenido,u=c.resumen??{};if(u.texto||u.riesgo){let v=u.carga?`${u.carga.reuniones_h??"?"} h de reuniones, ${u.carga.enfocado_min??"?"} min enfocados (tope ${u.carga.tope_min??"?"})`:"";r.push(`<div class="plan-txt"><p>${P(u.texto)}</p>${u.riesgo?`<p class="plan-riesgo">${P(u.riesgo)}</p>`:""}${v?`<p class="dim">${d(v)}</p>`:""}${c.borrador?'<p class="dim">borrador: las prioridades de la semana no est\xE1n aprobadas</p>':""}</div>`)}r.push("</section>");let h=c.foco??{};(h.paso||h.prioridad)&&(r.push(I("foco estrat\xE9gico","magenta",h.bloque??"")),h.prioridad&&r.push(G("prioridad",P(h.prioridad))),h.paso&&r.push(G("el paso",P(h.paso))),h.terminado&&r.push(G("terminado si",P(h.terminado))),r.push("</section>"));let p=c.resultados??[];p.length&&(r.push(I("resultados","verde",String(p.length))),p.forEach((v,y)=>{let $=c.retrospectiva?.resultados?.[y];r.push(G(v.tipo,`${P(v.texto)}${v.logrado_si?`<span class="sub">logrado si: ${P(v.logrado_si)}</span>`:""}${$?`<span class="sub">retro: ${P($)}</span>`:""}`))}),r.push("</section>"));let f=c.agenda??[];if(f.length){r.push(I("agenda","azul",String(f.length),'<a data-accion="calendario">ver en el calendario</a>'));for(let v of f)r.push(G(`${v.inicio??""}${v.fin?"\u2013"+v.fin:""}`,`${P(v.titulo)}${v.nota?`<span class="sub">${P(v.nota)}</span>`:""}${v.ficha?.decision?`<span class="sub">decidir: ${P(v.ficha.decision)}</span>`:""}`,v.estrategico?"estrategico":""));r.push("</section>")}let m=c.tacticos??{},b=m.hoy??[];if(b.length||(m.no_hoy??[]).length){r.push(I("t\xE1cticos","cian",String(b.length)));for(let v of b)r.push(G(v.ref??"",`${P(v.texto)}${v.donde?`<span class="sub">${P(v.donde)}</span>`:""}`));for(let v of m.no_hoy??[])r.push(G(`no hoy ${v.ref??""}`,`<span class="dim">${P(v.texto??v)}</span>`));r.push("</section>")}let w=[["personas","violeta",c.personas??[],v=>[v.quien,P(v.para)]],["personal","verde",c.personal??[],v=>[v.ref??"",P(v.texto)]],["los pr\xF3ximos d\xEDas","azul",c.proximos??[],v=>[v.dia,P(v.texto)]]];for(let[v,y,$,_]of w)if($.length){r.push(I(v,y,String($.length)));for(let A of $){let[j,E]=_(A);r.push(G(j,E))}r.push("</section>")}let k=c.retrospectiva;k&&(r.push(I("retrospectiva","dim")),k.imprevistos&&r.push(G("imprevistos",P(k.imprevistos))),k.energia!==void 0&&r.push(G("energ\xEDa",P(k.energia))),k.nota&&r.push(G("nota",P(k.nota))),r.push("</section>"));let C=c.huecos??[];return C.length&&(r.push(I("lo que la skill no pudo ver","dim",String(C.length))),C.forEach((v,y)=>r.push(G(String(y+1),`<span class="dim">${P(v)}</span>`))),r.push("</section>")),e.comentable&&r.push(`<section>${ki(e)}</section>`),r}function ki(e){return e.comentable?`<div class="cal-escribir"><textarea id="plan-texto" rows="3" spellcheck="false" placeholder="Un comentario sobre este plan: contexto que falta, algo que corregir\u2026 (\u2318\u23CE env\xEDa)"></textarea><a id="plan-enviar" data-accion="plan-comentar" data-campo="plan-texto" data-valor="${d(e.dia)}">enviar comentario</a></div>`:""}function Ci(e,a){return Date.parse(`${e}T${a.length===5?a:a.slice(0,5)}:00`)}function _i(e){return e.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim()}function Ai(e,a){let t=new Set(_i(e).split(" ").filter(o=>o.length>3));return _i(a).split(" ").filter(o=>o.length>3).some(o=>t.has(o))}function Ja(e,a){let t=(e.agenda??[]).filter(r=>r.cuando&&!r.todo_el_dia).map(r=>{let o=Date.parse(r.cuando??""),i=r.fin?Date.parse(r.fin):NaN;return{id:r.id||`${r.cuando}:${r.texto}`,titulo:r.texto,inicio:o,fin:Number.isNaN(i)?o+$i*6e4:i,lugar:r.lugar??"",url:r.url??"",asistentes:r.asistentes??[],soloPlan:!1}});for(let r of a?.agenda??[]){if(!r.inicio)continue;let o=Ci(e.fecha,String(r.inicio));if(Number.isNaN(o))continue;let i=(r.evento?t.find(s=>s.id===r.evento&&!s.plan):void 0)??t.find(s=>!s.plan&&!s.soloPlan&&Math.abs(s.inicio-o)<=10*6e4&&Ai(s.titulo,String(r.titulo??"")));if(i){i.plan=r;continue}let n=r.fin?Ci(e.fecha,String(r.fin)):NaN;t.push({id:`plan:${r.inicio}:${r.titulo}`,titulo:String(r.titulo??""),inicio:o,fin:Number.isNaN(n)?o+$i*6e4:n,lugar:"",url:"",asistentes:[],plan:r,soloPlan:!0})}return t.sort((r,o)=>r.inicio-o.inicio||r.fin-o.fin)}function ra(e,a){let t=a?.eventos??{};if(t[e.id])return t[e.id].notas;let r=new Date(e.inicio).toTimeString().slice(0,5);return Object.values(t).find(i=>i.inicio===r&&i.titulo&&Ai(i.titulo,e.titulo))?.notas??[]}function tc(e){let a=new Map,t=[],r=-1/0,o=()=>{let i=[],n=new Map;for(let s of t){let l=i.findIndex(c=>c<=s.inicio);l<0&&(l=i.length,i.push(0)),i[l]=s.fin,n.set(s.id,l)}for(let s of t)a.set(s.id,[n.get(s.id)??0,i.length]);t=[],r=-1/0};for(let i of e)t.length&&i.inicio>=r&&o(),t.push(i),r=Math.max(r,i.fin);return t.length&&o(),a}var rc=["dom","lun","mar","mi\xE9","jue","vie","s\xE1b"],oc=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];function ic(e,a,t){let r=new Date(`${e}T12:00:00`),o=isNaN(r.getTime())?e:`${rc[r.getDay()]} ${r.getDate()} ${oc[r.getMonth()]}`;return`<div id="cal-nav" class="cal-nav"><a data-accion="cal-dia" data-valor="-1" title="d\xEDa anterior (\u2190)">\u2039</a><span class="cal-fecha">${d(o)}${t?" \u2026":""}</span><a data-accion="cal-dia" data-valor="1" title="d\xEDa siguiente (\u2192)">\u203A</a>`+(e!==a?'<a data-accion="cal-dia" data-valor="hoy">hoy</a>':"")+"</div>"}function Ei(e,a,t,r,o,i,n="",s=e.fecha,l=!1){let c=[I("calendario","azul",e.fecha,`<a data-accion="plan-dia" data-valor="${d(e.fecha)}">plan del d\xEDa</a>`)];i&&c.push(`<div class="vacio falla">${d(i)}</div>`),e.error&&c.push(`<div class="vacio falla">${d(e.error)}</div>`),c.push(ic(e.fecha,s,l));let u=(e.agenda??[]).filter(p=>p.todo_el_dia);for(let p of u)c.push(`<div class="cal-dia-completo">todo el d\xEDa: ${d(p.texto)}</div>`);if(!a.length){let p=e.fecha===s?"nada con hora hoy":"nada con hora ese d\xEDa";return c.push(`<div class="vacio">${l?"cargando\u2026":e.agenda===null?"sin calendario consultado \xB7 <kbd>r</kbd>":p}</div></section>`),c}let h=a.find(p=>p.id===r)??a.find(p=>p.fin>o.getTime())??a[0];return c.push(`<div class="cal-dos"><div>${zt(e,a,h.id,o,t)}</div><div class="cal-det">${lc(h,t,e.fecha)}${sc(h,n)}</div></div></section>`),c}function zt(e,a,t,r,o,i="evento-sel"){if(!a.length)return'<div class="vacio">nada con hora ese d\xEDa</div>';let n=new Date(`${e.fecha}T00:00:00`).getTime(),s=b=>(b-n)/36e5,l=Math.min(8,Math.floor(Math.min(...a.map(b=>s(b.inicio))))),c=Math.max(19,Math.ceil(Math.max(...a.map(b=>s(b.fin))))),u=b=>(s(b)-l)*Ma,h=tc(a),p=a.find(b=>b.id===t),f=[`<div class="cal" style="height:${(c-l)*Ma}px">`];for(let b=l;b<=c;b++)f.push(`<div class="cal-linea" style="top:${(b-l)*Ma}px"></div><div class="cal-hora" style="top:${(b-l)*Ma}px">${String(b).padStart(2,"0")}:00</div>`);let m=r.getTime();s(m)>=l&&s(m)<=c&&f.push(`<div class="cal-ahora" style="top:${u(m)}px"></div>`);for(let b of a){let[w,k]=h.get(b.id)??[0,1],C=Math.max(20,u(b.fin)-u(b.inicio)-2),v=new Date(b.inicio).toTimeString().slice(0,5),y=ra(b,o).length>0||!!b.plan?.nota,$=["cal-ev",b.soloPlan?"plan":"",b.fin<=m?"pasado":"",b===p?"sel":"",C<40?"corto":""].filter(Boolean).join(" ");f.push(`<div class="${$}" data-accion="${i}" data-valor="${d(b.id)}" title="${d(b.titulo)}" style="top:${u(b.inicio)}px;height:${C}px;left:calc(${100*w/k}% + 2px);width:calc(${100/k}% - 4px)"><span class="h">${d(v)}${y?' <span class="marca-nota">\u270E</span>':""}</span><span class="t">${d(b.titulo)}</span></div>`)}return f.push("</div>"),f.join("")}function nc(e){return e.replace(/(^|[\s(:])((?:[\w.-]+\/)+[\w.-]+\.(?:md|json|html))(?=$|[\s).,;])/g,(a,t,r)=>`${t}<a data-accion="abrir-ruta" data-valor="${r}" title="abrir ${r}">${r}</a>`)}function sc(e,a){return a?`<div class="cal-escribir"><textarea id="ev-texto" data-evento="${d(e.id)}" rows="3" spellcheck="false" placeholder="Escr\xEDbele a ${d(a)} sobre esta reuni\xF3n. Le llega con la reuni\xF3n, su proyecto y las notas (\u2318\u23CE env\xEDa)"></textarea><a id="ev-enviar" data-accion="ev-escribir" data-campo="ev-texto" data-valor="${d(e.id)}">enviar a ${d(a)}</a></div>`:""}function lc(e,a,t){let r=s=>new Date(s).toTimeString().slice(0,5),o=[`<h3>${d(e.titulo)}</h3>`,`<div class="cal-meta">${d(r(e.inicio))}\u2013${d(r(e.fin))}${e.lugar?` \xB7 ${d(e.lugar)}`:""}${e.soloPlan?" \xB7 bloque del plan":""}</div>`],i=[];e.url&&i.push(`<a class="enlace" data-url="${d(e.url)}" title="${d(e.url)}">entrar \u2197</a>`),e.soloPlan||i.push(`<a data-accion="reunion" data-valor="${d(JSON.stringify([e.titulo,r(e.inicio),e.url,e.id,e.asistentes]))}">preparar o minuta</a>`),i.push(`<a data-accion="nota-evento" data-valor="${d(JSON.stringify([e.id,e.titulo,r(e.inicio),t]))}">+ nota</a>`),o.push(`<div class="acciones-ev">${i.join("")}</div>`);let n=e.plan;if(n){let s=n.ficha??{},l=h=>Array.isArray(h)&&h.length?"<ul>"+h.map(p=>`<li>${P(p)}</li>`).join("")+"</ul>":"",c=[n.con?.length?`con ${n.con.join(", ")}`:"",n.estado??"",n.accion?`propone: ${n.accion}`:""].filter(Boolean).join(" \xB7 "),u=[c?`<div class="dim">${P(c)}</div>`:"",n.nota?`<div>${P(n.nota)}</div>`:"",s.decision?`<div><b>decidir:</b> ${P(s.decision)}</div>`:"",(s.opciones??[]).length?l(s.opciones.map(h=>h.texto)):"",s.recomendacion?`<div><b>recomendaci\xF3n:</b> ${P(s.recomendacion)}</div>`:"",s.resultado?`<div><b>resultado buscado:</b> ${P(s.resultado)}</div>`:"",(s.llevar??[]).length?`<div><b>llevar</b>${l(s.llevar)}</div>`:"",(s.pedir??[]).length?`<div><b>pedir</b>${l(s.pedir)}</div>`:"",s.riesgo?`<div class="plan-riesgo">${P(s.riesgo)}</div>`:"",s.nota?`<div class="dim">${P(s.nota)}</div>`:"",s.borrador?`<div class="dim">borrador: ${P(s.borrador)}</div>`:""].filter(Boolean);u.length&&o.push(`<div class="cal-nota"><div class="de">del plan del d\xEDa</div>${u.join("")}</div>`)}for(let s of ra(e,a))o.push(`<div class="cal-nota"><div class="de">${d(s.de)} \xB7 ${d((s.creado??"").slice(11,16))}</div><div style="white-space:pre-wrap">${nc(P(s.texto))}</div></div>`);return!e.plan&&!ra(e,a).length&&o.push('<div class="dim">sin notas</div>'),o.join("")}var ji=B("proyectos");function cc(e){let a=M(e);return/^(activo|ganado|en curso|en ejecucion)/.test(a)?"e-activo":/^(prospecto|propuesta|negociacion|entendimiento|poc|lead|diagnostico)/.test(a)?"e-abierto":/pausa|vencido|perdido|trabado|bloquead/.test(a)?"e-trabado":""}function dc(e){let a=M(e);return a?[[/^(activo|ganado|en curso|en ejecucion)/,0],[/^negociacion/,1],[/^propuesta/,2],[/^(entendimiento|poc|diagnostico)/,3],[/^(prospecto|lead)/,4],[/pausa/,5],[/^(vencido|perdido|trabado|bloquead)/,6],[/^(cerrado|terminado|finalizado)/,7]].find(([r])=>r.test(a))?.[1]??8:9}var Ia=e=>e.arquetipo==="servicio",Mt=e=>/cerrad/i.test(e.arquetipo),Si=e=>e.split("/")[0]||e,uc=["PIA","EIC","GT","Upskill","Brinca","Otro"],Pi=e=>e.area||"sin \xE1rea";function Bt(e,a){let t="";for(let r of a)(e===r||e.startsWith(`${r}/`))&&r.length>t.length&&(t=r);return t}function Jt(e,a,t,r=[]){if(t.size<2)return"";let o=i=>{let n=r.indexOf(i);return n<0?r.length:n};return`<div class="titulo-tareas areas-t"><span class="modos"><button data-pf="${e}" data-pv="">${d(a)}</button>`+[...t].sort((i,n)=>o(i[0])-o(n[0])||n[1]-i[1]).map(([i,n])=>`<button data-pf="${e}" data-pv="${d(i)}">${d(i)} ${n}</button>`).join("")+"</span></div>"}function It(e){let a=new Map;for(let t of e)t&&a.set(t,(a.get(t)??0)+1);return a}function qi(e,a,t){let r=e.filter(Mt).length,o=e.filter(s=>s.hilo).length,i=t?e.filter(s=>(t.get(s.ruta)??0)>0).length:0,n=[`<div class="titulo-tareas"><input id="buscar-p" type="text" placeholder="/ buscar en los ${e.length}" spellcheck="false" autocomplete="off"><span class="modos"><span id="proyectos-cuenta"></span>`+(r?`<button id="ver-cerrados" title="mostrar u ocultar los proyectos cerrados">cerrados ${r}</button>`:"")+"</span></div>",Jt("raiz","todas las carpetas",It(e.map(s=>Si(s.ruta)))),Jt("area","todas las \xE1reas",It(e.map(Pi)),[...uc,"sin \xE1rea"]),Jt("tipo","todos los tipos",It(e.map(s=>s.arquetipo))),`<div class="titulo-tareas areas-t"><span class="modos"><button data-pf="hilo" data-pv="1" title="solo los que tienen un hilo (\u25CF abierto, \xB7 dormido)">con hilo ${o}</button><button data-pf="pend" data-pv="1" title="solo los que tienen algo pendiente">con pendientes <span id="cuenta-pend">${t?i:"\u2026"}</span></button></span></div>`,'<div class="fila proy-cab"><span class="at" data-orden-p="hilo" title="ordenar: con hilo primero (otra vez: por estado y nombre)">\u2195</span><span class="que" data-orden-p="nombre" title="ordenar por nombre (otra vez: por estado y nombre)">\u2195</span><span class="estado" data-orden-p="estado" title="ordenar por estado (otra vez: por estado y nombre)">\u2195</span><span class="tipo" data-orden-p="tipo" title="ordenar por tipo (otra vez: por estado y nombre)">\u2195</span><span class="cuando-p" data-orden-p="fecha" title="ordenar por cu\xE1ndo se toc\xF3 (otra vez: por estado y nombre)">\u2195</span><span class="menu-col"></span></div>','<div id="proyectos">'];for(let s of e){let l=s.vivo?"\u25CF":s.hilo?"\xB7":"",c=M(`${s.nombre} ${s.ruta} ${s.arquetipo} ${s.estado??""} ${s.area??""}`),u=s.cliente&&s.nombre.startsWith(s.cliente)?s.cliente:"",h=u?`<span class="cliente">${d(u)}</span><span class="resto">${d(s.nombre.slice(u.length))}</span>`:d(s.nombre),p=s.estado??"",f=s.modificado??"";n.push(`<div class="fila clic proy${s.ruta===a?" sel":""}${Mt(s)?" cerrado":""}" data-accion="proy-sel" data-valor="${d(s.ruta)}" data-cerrado="${Mt(s)?1:0}" data-raiz="${d(Si(s.ruta))}" data-unidad="${d(Pi(s))}" data-tipo="${d(s.arquetipo)}" data-estado="${d(M(p))}" data-rango="${dc(p)}" data-hilo="${s.vivo?2:s.hilo?1:0}" data-pend="${t?t.get(s.ruta)??0:""}" data-texto="${d(c)}" data-nombre="${d(M(s.nombre))}" data-fecha="${d(f)}" title="${d(`${s.ruta}${f?`
modificado ${f.slice(0,16).replace("T"," ")}`:""}${s.hilo?`
hilo: ${s.hilo}`:""}`)}"><span class="at">${l}</span><span class="que">${h}</span><span class="estado ${cc(p)}" title="${d(s.estado_completo||p)}">${d(p)}</span><span class="dim tipo">${d(s.arquetipo)}</span><span class="dim cuando-p">${d(se(f))}</span><span class="menu-fila menu-col" data-accion="proy-menu" data-valor="${d(s.ruta)}" title="acciones de este proyecto">\u22EF</span></div>`)}return n.push('<div id="proyectos-vacio" class="fila dim" hidden></div></div>'),n}function Te(e){let a=e.fila.ficha?`data-accion="tarea" data-valor="${d(JSON.stringify([e.fila.proveedor,e.fila.id||e.ref,e.ref]))}"`:`data-accion="pendiente" data-valor="${d(e.ref)}"`,t=e.fila.proveedor?e.ref:"\xB7";return`<div class="tarea${e.enCurso?" encurso":""}" ${a} data-completo="${d(`${e.ref} \xB7 ${ve(e.texto)}`)}"><span class="id">${d(t)}</span><span class="pri">${e.enCurso?"\u25CF":""}</span><span class="desc">${e.fila.dueno?`<span class="dueno">\u2192 ${d(e.fila.dueno)}</span>`:""}${d(ve(e.texto))}</span><span class="meta">${Fe(e.dias)}${e.fila.proveedor?"<span></span>":`<span class="menu-fila" data-accion="menu-vineta" data-valor="${d(JSON.stringify([e.ref,e.texto,e.hilo,e.fila.dueno??""]))}" title="acciones de este pendiente">\u22EF</span>`}</span></div>`}function Lt(e){if(!e)return'<div class="vacio">elige un proyecto a la izquierda</div>';let{p:a}=e,t=[`<h3>${d(a.nombre)}</h3>`,`<div class="proy-meta">${a.area?`${d(a.area)} \xB7 `:""}${d(a.arquetipo)} \xB7 <a data-accion="abrir-ruta" data-valor="${d(`${a.ruta}/README.md`)}" title="abrir el README">${d(a.ruta)}</a>${a.modificado?` \xB7 tocado ${d(se(a.modificado))}`:""}${a.hilo?` \xB7 hilo \xAB${d(a.hilo)}\xBB${a.vivo?"":" (dormido)"}`:""}</div>`,`<div class="acciones-ev"><a data-accion="proyecto" data-valor="${d(a.ruta)}" title="un hilo con el agente cargando el proyecto, o el que ya hay">${a.vivo?"ir a su hilo":"abrir con el agente"}</a><a data-accion="proy-consolidar" data-valor="${d(a.ruta)}" title="un agente revisa cada pendiente abierto del README, busca si ya se hizo y lo marca con su prueba (/consolidar)">consolidar pendientes</a></div>`],r=e.pendientes?.length;return t.push(`<h4>pendientes${r?` \xB7 ${r}`:""}</h4>`),e.aviso&&t.push(`<div class="vacio falla">${d(e.aviso)}</div>`),e.pendientes===null?t.push('<div class="vacio">leyendo\u2026</div>'):e.pendientes.length?t.push(...e.pendientes.map(Te)):t.push('<div class="vacio">nada pendiente</div>'),t.push("<h4>README</h4>"),e.readme===null?t.push('<div class="vacio">leyendo\u2026</div>'):e.readme?t.push(`<div class="proy-readme" data-base="${d(a.ruta)}">${e.readme}</div>`):t.push('<div class="vacio">sin README</div>'),t.join("")}var pc={reunion:"reuni\xF3n",estrategico:"estrat\xE9gico",comercial:"comercial",correo:"correo y mensajes",reserva:"reserva",almuerzo:"almuerzo",cierre:"cierre",personal:"personal",bloque:"bloque"};function Nt(e){let a=e.plan??{},t=String(a.clase??"").toLowerCase();if(["estrategico","comercial","correo","reserva","personal","cierre"].includes(t))return t;if(!e.soloPlan&&a.tipo!=="bloque"&&a.tipo!=="almuerzo"&&a.tipo!=="cierre")return"reunion";if(a.tipo==="almuerzo")return"almuerzo";if(a.tipo==="cierre")return"cierre";if(a.estrategico)return"estrategico";let r=M(e.titulo);return r.startsWith("estrateg")?"estrategico":r.startsWith("comercial")?"comercial":r.startsWith("correo")?"correo":r.startsWith("reserva")?"reserva":r.startsWith("almuerzo")?"almuerzo":r.startsWith("cierre")?"cierre":a.tipo==="reunion"?"reunion":"bloque"}function Ti(e,a){let t=e.map((o,i)=>[o,i]).filter(([o])=>o.inicio<=a&&a<o.fin);if(t.length)return t.sort((o,i)=>i[0].inicio-o[0].inicio)[0][1];let r=e.findIndex(o=>o.inicio>a);return r>=0?r:e.length-1}function zi(e,a){let t=` ${M(e.replace(/^[^:]*:\s*/,""))} `,r=a.filter(o=>!/cerrad/i.test(o.arquetipo)&&o.cliente&&o.cliente.length>=4&&t.includes(` ${M(o.cliente)} `));return r.sort((o,i)=>+!!i.hilo-+!!o.hilo||(i.modificado??"").localeCompare(o.modificado??"")),r[0]?.ruta??""}function Ba(e){return new Date(e).toTimeString().slice(0,5)}function hc(e,a){if(e.inicio<=a&&a<e.fin)return`en curso \xB7 quedan ${Math.round((e.fin-a)/6e4)} min`;if(e.inicio>a){let t=Math.round((e.inicio-a)/6e4);return t<60?`empieza en ${t} min`:`empieza en ${Math.floor(t/60)} h ${t%60} min`}return"ya pas\xF3"}function Fi(e){return Array.isArray(e)&&e.length?"<ul>"+e.map(a=>`<li>${d(String(a))}</li>`).join("")+"</ul>":""}function La(e,a){let t=e?.foco??{};return!t.paso&&!t.prioridad?"":a?'<div class="ahora-foco">'+(t.prioridad?`<div class="dim">${d(String(t.prioridad))}${t.bloque?` \xB7 ${d(String(t.bloque))}`:""}</div>`:"")+(t.paso?`<div class="paso">${d(String(t.paso))}</div>`:"")+(t.terminado?`<div><b>terminado:</b> ${d(String(t.terminado))}</div>`:"")+(t.pregunta?`<div class="dim">${d(String(t.pregunta))}</div>`:"")+"</div>":`<div class="ahora-foco corto"><span class="dim">foco del d\xEDa:</span> ${d(String(t.paso??t.prioridad??""))}</div>`}function Na(e,a){if(a)return'<div class="vacio">leyendo el proyecto\u2026</div>';if(!e?.proyecto)return e?.sinProyecto?`<div class="vacio">${d(e.sinProyecto)}</div>`:"";let t=e.proyecto,r=[`<h4>${d(t.nombre)} <a data-accion="proy-ir" data-valor="${d(t.ruta)}" class="dim">ver en proyectos</a></h4>`];e.estado&&r.push(`<div class="ahora-estado proy-readme">${e.estado}</div>`);let o=6;return e.pendientes.length&&(r.push(`<div class="dim">pendientes del proyecto \xB7 ${e.pendientes.length}</div>`,...e.pendientes.slice(0,o).map(Te)),e.pendientes.length>o&&r.push(`<div class="dim">+ ${e.pendientes.length-o} m\xE1s en <a data-accion="proy-ir" data-valor="${d(t.ruta)}">proyectos</a></div>`)),r.join("")}function Mi(e){let a=[I("ahora","amarillo","","")];e.aviso&&a.push(`<div class="vacio falla">${d(e.aviso)}</div>`);let t=["dom","lun","mar","mi\xE9","jue","vie","s\xE1b"],r=new Date(e.ahora),o=`<a class="ahora-cuando${e.simulado?" simulado":""}" data-accion="ahora-elegir" title="elegir en el calendario otro momento: qu\xE9 mostrar\xEDa entonces">${e.simulado?`simulando ${t[r.getDay()]} ${r.getDate()} \xB7 ${Ba(e.ahora)}`:"elegir momento"} ${e.elegir!==void 0?"\u25B4":"\u25BE"}</a>`,i=e.elegir===void 0?"":`<div class="ahora-elegir"><div class="cal-nav"><a data-accion="ahora-dia" data-valor="-1" title="d\xEDa anterior">\u2039</a><span class="cal-fecha">${d(e.fechaElegir??"")}</span><a data-accion="ahora-dia" data-valor="1" title="d\xEDa siguiente">\u203A</a></div>`+e.elegir+"</div>",n=e.evs[e.i];if(e.cargandoDia)return a.push(`<div class="ahora-nav">${o}</div>${i}<div class="vacio">leyendo ese d\xEDa\u2026</div></section>`),a;if(!n)return a.push(`<div class="ahora-nav">${o}${e.simulado?'<a data-accion="ahora-soltar">\u21BA volver a ahora</a>':""}</div>${i}<div class="vacio">nada en el calendario ni en el plan de ese d\xEDa</div></section>`),a;let s=Nt(n),l=n.plan??{};a.push(`<div class="ahora-nav"><a data-accion="ahora-mover" data-valor="-1" title="el bloque anterior">\u2039</a><span class="dim">${e.i+1} de ${e.evs.length}</span><a data-accion="ahora-mover" data-valor="1" title="el bloque siguiente">\u203A</a>`+(e.fijo||e.simulado?'<a data-accion="ahora-soltar" title="volver a lo que toca ahora; la vista sigue al reloj">\u21BA volver a ahora</a>':'<a data-accion="ahora-fijar" title="que la vista no cambie sola al pasar al bloque siguiente">fijar</a>')+o+"</div>"+i),a.push(`<div class="ahora-bloque"><span class="clase c-${s}">${d(pc[s])}</span><h3>${d(n.titulo)}</h3><div class="dim">${Ba(n.inicio)}\u2013${Ba(n.fin)} \xB7 ${d(hc(n,e.ahora))}${n.lugar?` \xB7 ${d(n.lugar)}`:""}</div>`+(l.nota?`<div>${d(String(l.nota))}</div>`:"")+"</div>");let c=e.contexto?.tareas?.length?`<h4>tareas del bloque</h4>${e.contexto.tareas.map(Te).join("")}`:"";if(s==="estrategico")a.push(La(e.plan,!0),c,Na(e.contexto,e.cargando));else if(s==="reunion"){let u=l.ficha??{},h=[u.decision?`<div><b>decidir:</b> ${d(String(u.decision))}</div>`:"",u.resultado?`<div><b>resultado buscado:</b> ${d(String(u.resultado))}</div>`:"",(u.llevar??[]).length?`<div><b>llevar</b>${Fi(u.llevar)}</div>`:"",(u.pedir??[]).length?`<div><b>pedir</b>${Fi(u.pedir)}</div>`:"",u.riesgo?`<div class="dim"><b>riesgo:</b> ${d(String(u.riesgo))}</div>`:"",u.nota?`<div class="dim">${d(String(u.nota))}</div>`:""].join(""),p=[n.url?`<a class="enlace" data-url="${d(n.url)}">entrar \u2197</a>`:"",n.soloPlan?"":`<a data-accion="reunion" data-valor="${d(JSON.stringify([n.titulo,Ba(n.inicio),n.url,n.id,n.asistentes]))}">${n.fin<=e.ahora?"procesar la minuta":"preparar o minuta"}</a>`].filter(Boolean).join("");a.push(p?`<div class="acciones-ev">${p}</div>`:""),h&&a.push(`<div class="ahora-ficha">${h}</div>`),n.asistentes.length&&a.push(`<div class="dim">con ${d(n.asistentes.map(f=>f.replace(/\s*<.*>/,"")).slice(0,8).join(", "))}${n.asistentes.length>8?"\u2026":""}</div>`),e.contexto?.preparacion&&a.push(`<h4>preparaci\xF3n <a data-accion="abrir-ruta" data-valor="${d(e.contexto.preparacion.ruta)}" class="dim">abrir</a></h4><div class="proy-readme ahora-doc">${e.contexto.preparacion.html}</div>`),e.contexto?.minuta&&a.push(`<h4>de la minuta anterior <a data-accion="abrir-ruta" data-valor="${d(e.contexto.minuta.ruta)}" class="dim">abrir</a></h4><div class="proy-readme ahora-doc">${e.contexto.minuta.html}</div>`),a.push(c,Na(e.contexto,e.cargando),La(e.plan,!1))}else if(s==="comercial")a.push(c,Na(e.contexto,e.cargando),La(e.plan,!1));else if(s==="reserva"||s==="almuerzo")a.push('<div class="vacio">tiempo libre: no hay nada agendado aqu\xED.</div>'),e.urgentes.length&&a.push("<h4>si sobra, lo m\xE1s urgente</h4>",...e.urgentes.slice(0,3).map(Te));else if(s==="cierre"){let u=e.plan?.retrospectiva??{},h=e.plan?.resultados??[];h.length&&a.push("<h4>los resultados del d\xEDa</h4>"+h.map((p,f)=>`<div>${d(String(p.texto??""))}${u.resultados?.[f]?` <span class="dim">\xB7 ${d(String(u.resultados[f]))}</span>`:""}</div>`).join("")),e.propuestas.length&&a.push(`<h4>lo que dejaron los agentes para decidir \xB7 ${e.propuestas.length}</h4>`,...e.propuestas.slice(0,6).map(Te))}else a.push(c,Na(e.contexto,e.cargando),La(e.plan,!1));return a.push("</section>"),a}function Ot(e){let a=e.split(`
`),t=a.findIndex(i=>/^#{2,4}\s+.*para la pr[oó]xima/i.test(i));if(t<0)return"";let r=(a[t].match(/^#+/)??["##"])[0].length,o=a.findIndex((i,n)=>n>t&&new RegExp(`^#{1,${r}}\\s`).test(i));return a.slice(t+1,o<0?void 0:o).join(`
`).trim()}function Ji(e){let a=e.split(`
`),t=a.findIndex(o=>/^##\s+Estado\s*$/.test(o));if(t<0)return"";let r=a.findIndex((o,i)=>i>t&&/^##?\s/.test(o));return a.slice(t+1,r<0?void 0:r).join(`
`).trim().slice(0,1500)}var Ii=B("ahora");async function fe(e,a,t="",r="",o=!1){let i=await g().progreso({title:`telar: llevando ${e} a su hilo\u2026`},()=>oi(e,a,t,r,o));if(!i.datos){g().aviso(`telar: ${i.error??`no pude llevar \xAB${e}\xBB`}`);return}await x.sondear(),g().mostrarTerminal()}async function Oa(e){let a=p=>`${p.getFullYear()}-${String(p.getMonth()+1).padStart(2,"0")}-${String(p.getDate()).padStart(2,"0")}`,t=p=>{let f=new Date;return f.setDate(f.getDate()+p),f},r=["domingo","lunes","martes","mi\xE9rcoles","jueves","viernes","s\xE1bado"],o=new Date,i=t((8-o.getDay())%7||7),n=new Date(o.getFullYear(),o.getMonth()+1,0),s=[{label:"ma\xF1ana",description:`${r[t(1).getDay()]} ${a(t(1))}`,valor:a(t(1))},{label:"pasado ma\xF1ana",description:`${r[t(2).getDay()]} ${a(t(2))}`,valor:a(t(2))},{label:"el pr\xF3ximo lunes",description:a(i),valor:a(i)},{label:"en una semana",description:`${r[t(7).getDay()]} ${a(t(7))}`,valor:a(t(7))},{label:"fin de mes",description:`${r[n.getDay()]} ${a(n)}`,valor:a(n)},{label:"otra fecha\u2026",description:"AAAA-MM-DD, 15-10, 15-oct o +10d",valor:""}],l=await g().elegir(s,{title:`Nueva fecha \xB7 ${e}`,placeHolder:"para cu\xE1ndo queda",ignoreFocusOut:!0});if(!l)return;if(l.valor)return l.valor;let c=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],u=p=>{if(p=p.trim().toLowerCase(),/^\+\d+d$/.test(p)||/^\d{4}-\d{2}-\d{2}$/.test(p))return p;let f=p.match(/^(\d{1,2})[-/ ](\d{1,2}|[a-zé]{3,})$/);if(!f)return"";let m=/^\d+$/.test(f[2])?Number(f[2]):c.indexOf(f[2].slice(0,3))+1;if(m<1||m>12)return"";let b=new Date(o.getFullYear(),m-1,Number(f[1]));return b.getDate()!==Number(f[1])?"":(b<new Date(o.getFullYear(),o.getMonth(),o.getDate())&&(b=new Date(o.getFullYear()+1,m-1,Number(f[1]))),a(b))},h=await g().campo({title:`Nueva fecha \xB7 ${e}`,prompt:"AAAA-MM-DD, 15-10, 15-oct o +10d",ignoreFocusOut:!0,validateInput:p=>p.trim()&&!u(p)?"no entiendo esa fecha":void 0});return h?.trim()&&u(h)||void 0}async function Bi(e){let[a,t]=JSON.parse(e),r=await Z(t,a),o=r.datos?.acciones?.findIndex(s=>s.rol==="fecha")??-1;if(o<0)return g().aviso(`telar: ${r.error??`${t}: su proveedor no ofrece cambiar la fecha`}`),!1;let i=await Oa(`${t} ${r.datos?.titulo??""}`.trim());if(!i)return!1;let n=await ie(t,a,o,i);return U(),n.datos?(g().estado(`${t} \u2192 ${i}`,5e3),!0):(g().aviso(`telar: ${n.error??`no pude mover ${t}`}`),!1)}async function Ha(e,a,t,r,o=!1){let i=r?r[0].toUpperCase()+r.slice(1):"yo",n=[o?{label:"Sin responsable",description:"la vi\xF1eta no dice qui\xE9n la hace",valor:"none"}:{label:`${i} (sin asignar)`,description:"lo de siempre: una tarea sin due\xF1o es tuya",valor:"none"},{label:i,description:"asignada a ti a prop\xF3sito",valor:i},{label:"",separador:!0},...t.filter(c=>c.toLowerCase()!==i.toLowerCase()).map(c=>({label:c,valor:c})),{label:"",separador:!0},{label:"otra persona\u2026",valor:""}];for(let c of n)c.valor!==void 0&&c.valor&&(c.valor===a||c.valor==="none"&&!a)&&(c.description=`${c.description??""} \u2190 ahora`.trim());let s=await g().elegir(n,{title:e,placeHolder:"qui\xE9n hace esta tarea"});return s?s.valor?s.valor:(await g().campo({title:e,prompt:"el nombre de quien la hace",ignoreFocusOut:!0}))?.trim()||void 0:void 0}async function Li(e,a,t){let[r,o]=JSON.parse(e),i=await Z(o,r),n=i.datos?.acciones??[],s=n.findIndex(u=>u.rol==="dueno");if(s<0)return g().aviso(`telar: ${i.error??`${o}: su proveedor no ofrece cambiar el responsable`}`),!1;let l=await Ha(`${o} ${i.datos?.titulo??""}`.trim(),a,n[s].opciones??[],t);if(!l)return!1;let c=await ie(o,r,s,l);return U(),c.datos?(g().estado(`${o} \u2192 ${l==="none"?"sin asignar":l}`,5e3),!0):(g().aviso(`telar: ${c.error??`no pude asignar ${o}`}`),!1)}async function Ni(e,a,t){let[r,o]=JSON.parse(e),i=await Z(o,r),n=i.datos?.acciones?.findIndex(l=>l.rol===a)??-1;if(n<0)return g().aviso(`telar: ${i.error??`${o}: su proveedor no ofrece ${t}`}`),!1;let s=await ie(o,r,n,"");return U(),s.datos?(g().estado(`${o}: ${i.datos?.acciones?.[n].nombre??t}`,4e3),!0):(g().aviso(`telar: ${s.error??`no pude cambiar ${t} de ${o}`}`),!1)}var Oi=e=>Ni(e,"estrella","la estrella");async function Hi(e){let[a,t]=JSON.parse(e),r=(await Z(t,a)).datos?.acciones?.find(i=>i.rol==="equipo")?.nombre??"";if(!await Ni(e,"equipo","compartir con el equipo"))return!1;let o=r.startsWith("\u25CB");return g().info(o?`telar: ${t} ahora la ve el equipo (t\xEDtulo, estado, prioridad y fecha); pueden sugerir subirla.`:`telar: ${t} dej\xF3 de compartirse con el equipo.`),!0}async function Ht(e){let[a,t]=JSON.parse(e),r=await g().progreso({ventana:!0,title:`\u2713 ${t}\u2026`},()=>Io(t,a,"hecha"));if(r.datos)return U(),g().estado(`\u2713 ${t} hecha`,5e3),!0;if(!/--rol|unrecognized|argumentos/i.test(r.error??""))return g().aviso(`telar: ${r.error??`no pude marcar ${t}`}`),U(),!1;let o=await Z(t,a),i=o.datos?.acciones?.findIndex(s=>s.rol==="hecha")??-1;if(i<0)return g().aviso(`telar: ${o.error??`${t} no se puede marcar hecha desde la lista: \xE1brela`}`),U(),!1;let n=await ie(t,a,i);return U(),n.datos?(g().estado(`\u2713 ${t} hecha`,5e3),!0):(g().aviso(`telar: ${n.error??`no pude marcar ${t}`}`),!1)}var Wa=class{panel;crearSuperficie;datos;pantalla="ahora";bloqueSel="";dashOrden=[];dashOcultas=[];modulosCfg=[];cuerpos=new Map;cuerposAbiertos=new Set;soloPendientes=new Set;gruposAbiertos=new Set;itemSel;bloquePintado="";plan;planError="";planCargando=!1;notas;general;notasAviso="";eventoSel="";periodicos;periodicosError="";periodico;formPer;fichaDesde="revisar";pestana="";fichas=new Map;atajosLanzados=new Map;pestanasCfg=[];ficha;decididas=new Set;mensajesBus;abiertoMsg=new Set;equipoId="";seccion="";marcos=[];pagina;charla;nonce=Ne();memorias=new Map;proyectos;avisoProyectos="";ahoraSel="";ahoraFijo=!1;ahoraCtx=new Map;ahoraCargando="";ahoraSim;ahoraDia;ahoraPlan;ahoraDiaCargando=!1;ahoraElegir=!1;proySel="";proyDet;pendRepo;pendRepoAviso="";atajos=[];bloquesCfg=[];bloquesDatos=new Map;calendario;agenteConfig;hilosConfig;avisoConfig="";enCurso=!1;teclas=new Map;calFecha="";calDatos;calCargando=!1;alCambiarFoco;alternar(){if(this.panel?.activa){g().mostrarTerminal();return}this.abrir()}abrir(){if(this.panel){this.panel.revelar(),this.actualizar();return}if(!this.crearSuperficie)throw new Error("telar: el dashboard no sabe d\xF3nde dibujarse (crearSuperficie)");this.panel=this.crearSuperficie({mensaje:a=>void this.mensaje(a),cerrada:()=>{this.panel=void 0,this.alCambiarFoco?.(!1)},cambio:(a,t)=>{a&&this.actualizar(),this.alCambiarFoco?.(t)}}),this.leerAtajos(),this.alCambiarFoco?.(!0),this.pintarMarco()}pintarMarco(){this.panel&&(this.nonce=Ne(),this.marcos=gc(),this.bloquePintado="",this.panel.html(fa(this.panel,wi+Di+ji+Ii,'<div id="dia"><div class="aviso">leyendo el d\xEDa\u2026</div></div>',xi,this.nonce,this.marcos)))}get appActual(){return this.pantalla==="seccion"&&this.seccion.startsWith("app:")?this.seccion.slice(4):""}async abrirApp(a){let t=x.apps.find(o=>o.clave===a)?.url,r=t?Wi(t):"";this.panel&&r&&!this.marcos.includes(r)&&(this.pagina=void 0,this.pintarMarco()),await this.abrirSeccion(`app:${a}`),this.alCambiarFoco?.(!0)}async actualizar(a=!1){if(!(!this.panel||this.enCurso)){this.enCurso=!0;try{a&&U(),this.datos=await qe(a?0:45e3,a),this.render(),this.leerBloques(a)}finally{this.enCurso=!1}}}render(){if(this.panel&&this.pantalla==="config"){this.renderConfig();return}if(this.panel&&this.pantalla==="revisar"){this.renderRevisar();return}if(this.panel&&this.pantalla==="pestana"){this.renderPestana();return}if(this.panel&&this.pantalla==="periodicos"){this.formPer||this.renderPeriodicos();return}if(this.panel&&this.pantalla==="plan"){this.renderPlan();return}if(this.panel&&this.pantalla==="calendario"){this.renderCalendario();return}if(this.panel&&this.pantalla==="ahora"){this.renderAhora();return}if(!(this.panel&&this.pantalla==="proyectos")&&!(this.panel&&(this.pantalla==="seccion"||this.pantalla==="conversacion"||this.pantalla==="correo"||this.pantalla==="tarea"))){if(this.panel&&this.pantalla==="equipo"){this.renderEquipo();return}this.panel&&this.pantalla==="bloque"&&this.renderBloque()}}renderBloque(){this.teclas.clear();let a=this.bloquesCfg.find(i=>i.clave===this.bloqueSel),t=a?this.bloquesDatos.get(a.clave):void 0,r=this.itemSel!==void 0?(t?.pagina?.bloques??[]).flatMap(i=>i.items??[])[this.itemSel]:void 0;if(a&&r){this.bloquePintado="",this.pintar(this.htmlItem(a,r,this.itemSel));return}let o=`${this.bloqueSel}:${t?.hora??0}`;t?.pagina?.bloques.some(i=>i.lienzo)&&o===this.bloquePintado||(this.bloquePintado=o,this.pintar(a?this.bloques([a]):['<div class="vacio">ese bloque ya no est\xE1 en la configuraci\xF3n</div>']))}async abrirBloque(a,t){this.pantalla="bloque",this.bloquePintado="",this.itemSel=t;let r=t===void 0?void 0:(this.bloquesDatos.get(a)?.pagina?.bloques??[]).flatMap(o=>o.items??[])[t];if(r?.id&&!this.cuerpos.has(`${a}:${r.id}`)){let o=`${a}:${r.id}`;this.cuerpos.set(o,{}),Fo(a,r.id).then(i=>{this.cuerpos.set(o,i.datos?{texto:i.datos.texto}:{error:i.error??"no pude leerlo"}),this.pantalla==="bloque"&&this.bloqueSel===a&&this.itemSel===t&&this.render()})}this.bloqueSel=a,this.render(),await this.leerBloques()}todasLasPestanas(){let a=this.datos,t=[...new Set((a?.pendientes??[]).map(i=>i.pestana??"").filter(Boolean))].map(i=>[`pestana:${i}`,"pestana",i,`${i} ${a?ee(a,i).length:""}`.trim(),this.pestanasCfg.find(n=>n.nombre===i)?.tecla??""]),r=this.propuestas("").length;return[["ahora","ahora","","ahora","n"],["revisar","revisar","",r?`tareas \u25C6${r}`:"tareas","v"],...this.bloquesCfg.filter(i=>!i.en).map(i=>[`bloque:${i.clave}`,"bloque",i.clave,i.nombre,i.tecla??""]),...t,["proyectos","proyectos","","proyectos","p"],["plan","plan","","plan","d"],["calendario","calendario","","calendario","a"],["periodicos","periodicos","","peri\xF3dicos","o"],...x.hayRemotos?[["correo","correo","","agentes","c"]]:[]]}pestanasVisibles(a=this.todasLasPestanas()){let t=r=>{let o=this.dashOrden.indexOf(r);return o<0?this.dashOrden.length+a.findIndex(i=>i[0]===r):o};return a.filter(r=>!this.dashOcultas.includes(r[0])).sort((r,o)=>t(r[0])-t(o[0]))}async cambiarPestanas(a,t){let r=this.todasLasPestanas(),o=c=>{let u=this.dashOrden.indexOf(c);return u<0?this.dashOrden.length+r.findIndex(h=>h[0]===c):u},i=r.map(c=>c[0]).sort((c,u)=>o(c)-o(u)),n=[...this.dashOcultas],s=i.indexOf(t);if(s<0)return;if(a==="ver")n=n.includes(t)?n.filter(c=>c!==t):[...n,t];else{let c=s+(a==="subir"?-1:1);if(c<0||c>=i.length)return;[i[s],i[c]]=[i[c],i[s]]}let l=await Jo(i.map(c=>(n.includes(c)?"-":"")+c).join(","));if(!l.datos){this.avisoConfig=l.error??"no pude guardar las pesta\xF1as",this.renderConfig();return}this.dashOrden=l.datos.dashboard.orden,this.dashOcultas=l.datos.dashboard.ocultas,this.avisoConfig="",this.renderConfig()}nav(){let a=this.datos,t=new Date,r=this.pantalla==="conversacion"?`seccion:${this.seccion}`:this.pantalla==="seccion"?`seccion:${this.seccion}`:this.pantalla==="tarea"?this.fichaDesde.replace(/^(bloque:[^:]*):.*$/,"$1"):this.pantalla==="pestana"?`pestana:${this.pestana}`:this.pantalla==="bloque"?`bloque:${this.bloqueSel}`:this.pantalla,o=this.atajos.filter(s=>(s.en??"hoy")==="hoy").map(s=>he(s.tecla,s.nombre,"atajo",s.tecla,s.descripcion||s.mensaje)).join("")+he("\u238B","terminal","volver","","volver al terminal"),i=(a?.fallas??[]).filter(s=>!s.startsWith("calendario")),n=[...this.pestanasVisibles(),["config","config","","\u2699",""]];return'<div class="fijo"><header class="top"><div class="marca-t"><span class="logo">telar</span>'+(a?`<span class="fecha">${d(mc(a.nombreDia,a.fecha))}</span>`:"")+`<span class="reloj">${t.toTimeString().slice(0,5)}</span>${a?.semana?`<span class="sem">s${a.semana}</span>`:""}</div><span class="generales">${o}</span>`+he("r","recargar","refrescar","","recargar, proveedores incluidos")+'</header><nav class="tabs">'+n.map(([s,l,c,u,h])=>`<a class="tab${s===r?" activa":""}" data-accion="${l}"${c?` data-valor="${d(c)}"`:""}>${h?`<kbd>${h}</kbd> `:""}${d(u)}</a>`).join("")+"</nav>"+i.map(s=>`<div class="fila falla">ca\xEDdo \xB7 ${d(s)}</div>`).join("")+'<div class="regla"></div></div>'}async leerAtajos(){let a=await oe();this.atajos=a.datos?.atajos??[],this.bloquesCfg=a.datos?.bloques??[],this.pestanasCfg=a.datos?.pestanas??[],this.dashOrden=a.datos?.dashboard?.orden??[],this.dashOcultas=a.datos?.dashboard?.ocultas??[],this.modulosCfg=a.datos?.modulos??[],Q.persona=a.datos?.persona??"",Q.nombres=a.datos?.persona_nombres??[],this.general=a.datos?.agente_general?.clave?{clave:a.datos.agente_general.clave,nombre:a.datos.agente_general.nombre??a.datos.agente_general.clave}:void 0,this.render(),this.leerBloques()}bloques(a,t=!1){let r=[];for(let o of a){let i=this.bloquesDatos.get(o.clave);if(t&&!(i?.pagina?.bloques??[]).some(h=>h.items?.length))continue;let s=(i?.pagina?.bloques??[]).flatMap(h=>h.items??[]).some(h=>Array.isArray(h.tareas)),l=this.soloPendientes.has(o.clave),c=s?`<a class="solo-pend${l?" si":""}" data-accion="solo-pendientes" data-valor="${d(o.clave)}" title="${l?"mostrar todos":"mostrar solo los que tienen alguna tarea pendiente"}">${l?"\u2611":"\u2610"} con tareas pendientes</a>`:"",u=this.atajos.filter(h=>h.en===o.clave).map(h=>he(h.tecla,h.nombre,"atajo",h.tecla,h.descripcion||h.mensaje)).join("")+c;if(r.push(I(o.nombre,o.color,i?.pagina?.subtitulo??"",u)),!i)r.push('<div class="vacio">leyendo\u2026</div>');else if(i.error)r.push(`<div class="vacio falla">${d(i.error)}</div>`);else{for(let v of i.pagina?.bloques??[])v.lienzo&&r.push(this.htmlLienzo(v.lienzo)),v.texto&&r.push(`<div class="md-pag">${Ua(v.texto)}</div>`);let h=(i.pagina?.bloques??[]).flatMap(v=>v.items??[]),p=(i.pagina?.bloques??[]).some(v=>v.lienzo||v.texto);!h.length&&!p&&r.push('<div class="vacio">nada</div>');let f=h.some(v=>Array.isArray(v.tareas)),m=this.datos?new Set(ee(this.datos).filter(v=>!this.decididas.has(v.fila.id||v.ref)).map(v=>`${v.fila.proveedor}:${v.fila.id||v.ref}`)):void 0,b=v=>m?m.has(`${v.proveedor}:${v.id}`):!/^(hecha|cerrada|descartada|cancelada)$/.test(v.estado??""),w=(v,y,$={})=>{let _=v.mensaje||v.tareas?.length?` data-accion="ver-item" data-valor="${d(o.clave)}:${y}"`:"",A=$.ts??v.tareas??[],j=f?`<span class="tar" title="${d(A.map(R=>`${R.id} ${b(R)?R.estado||"pendiente":"cerrada"}`).join(`
`)||"sin tareas")}">`+(A.length?A.map(R=>`<span class="${b(R)?"abierta":"cerrada"}">${d(R.id)}</span>`).join(", "):"\u2014")+"</span>":"",E=$.cuantos?`<span class="plegar" data-accion="grupo-item" data-valor="${d($.llave)}" title="${$.abierta?"plegar":`ver los ${$.cuantos} de esta conversaci\xF3n`}">${$.abierta?"\u25BE":"\u25B8"}${$.cuantos}</span> `:"",F=$.nuevo??v.destacado;return`<div class="cr${f?" con-t":""}${$.hijo?" hijo":""}${F?" nuevo":""}${_?" clic":""}"${_} title="${d(_?`clic: ${v.tareas?.length?"sus tareas":"verlo"}${v.mensaje?", y procesarlo en un hilo":""}`:v.titulo)}"><span class="mk">${d($.marca??v.marca??"\xB7")}</span><span class="hora" title="${d((v.fecha??"").replace("T"," "))}">${d(wc(v.fecha??""))}</span><span class="de">${d(f?(v.texto??"").replace(/ · tareas: .*$/,""):v.texto??"")}</span><span class="que">${E}${d(v.titulo)}</span>${j}</div>`},k=new Map;h.forEach((v,y)=>{let $=v.grupo||`#${y}`;k.has($)||k.set($,[]),k.get($).push(y)});let C=0;for(let[v,y]of k){let $=h[y[0]];if(l&&!y.some(R=>(h[R].tareas??[]).some(b)))continue;if(C++,y.length===1){r.push(w($,y[0]));continue}let _=`${o.clave}:${v}`,A=this.gruposAbiertos.has(_),j=y.map(R=>h[R]),E=[...new Map(j.flatMap(R=>R.tareas??[]).map(R=>[R.id,R])).values()],F=j.some(R=>R.destacado);r.push(w($,y[0],{cuantos:y.length,abierta:A,llave:_,ts:E,nuevo:F,marca:F?j.find(R=>R.destacado)?.marca??$.marca:$.marca})),A&&y.slice(1).forEach(R=>r.push(w(h[R],R,{hijo:!0})))}l&&h.length&&!C&&r.push('<div class="vacio">ning\xFAn correo con tareas pendientes</div>')}r.push("</section>")}return r}async leerBloques(a=!1){let t=Date.now();await Promise.all(this.bloquesCfg.map(async r=>{let o=this.bloquesDatos.get(r.clave);if(!a&&o&&t-o.hora<300*1e3)return;let i=await To(r.clave);await this.precargarLienzos(i.datos?.bloques),this.bloquesDatos.set(r.clave,{pagina:i.datos,error:i.datos?"":i.error??"no contest\xF3",hora:Date.now()}),(this.pantalla==="bloque"||this.pantalla==="plan")&&this.render()}))}htmlItem(a,t,r){let o=t.enlace?`<a class="titulo-item" data-accion="item-enlace" data-valor="${d(a.clave)}:${r}" title="${d(`abrirlo: ${t.enlace}`)}"><b>${d(t.titulo)}</b> \u2197</a>`:`<b>${d(t.titulo)}</b>`,i=[`<div class="subcab"><a data-accion="item-volver" title="volver a la lista">\u2039 ${d(a.nombre)}</a>&nbsp; ${o}<span class="dim">${d((t.texto??"").replace(/ · tareas: .*$/,""))}${t.fecha?` \xB7 ${d(t.fecha.slice(0,16).replace("T"," "))}`:""}</span></div>`];if(t.id){let s=`${a.clave}:${t.id}`,l=this.cuerpos.get(s);if(!l||!l.texto&&!l.error)i.push('<div class="fila dim">leyendo el correo\u2026</div>');else if(l.error)i.push(`<div class="fila dim">sin el cuerpo: ${d(l.error)}</div>`);else{let c=this.cuerposAbiertos.has(s),u=l.texto.split(`
`).length>5||l.texto.length>600;i.push(`<div class="cuerpo${c||!u?"":" plegado"}">${d(l.texto)}</div>`),u&&i.push(`<div class="fila"><a data-accion="cuerpo-alternar" data-valor="${d(s)}">${c?"\u25B4 plegar":"\u25BE ver todo"}</a></div>`)}}i.push("<h2>Tareas<small>las que nacieron de este correo o de otro mensaje de su conversaci\xF3n</small></h2>"),t.tareas?.length||i.push('<div class="fila dim">ninguna</div>');let n=(this.datos?ee(this.datos):[]).filter(s=>!this.decididas.has(s.fila.id||s.ref));i.push('<div class="tareas-sueltas">');for(let s of t.tareas??[]){let l=n.find(u=>u.fila.proveedor===s.proveedor&&(u.fila.id===s.id||u.ref===s.id));if(l){i.push(this.filaTarea(l,!!l.avance&&!!l.fila.ficha,!1));continue}let c=d(JSON.stringify([s.proveedor,s.id,s.id]));i.push(`<div class="fila clic" data-accion="tarea" data-valor="${c}" title="clic: su ficha"><span class="dim">${d(s.id)}</span>&nbsp; <span class="dim">ya no est\xE1 pendiente</span></div>`)}return i.push("</div>"),t.mensaje&&(i.push("<h2>Procesar</h2>"),i.push(`<div class="fila"><a data-accion="abrir-item" data-valor="${d(a.clave)}:${r}" title="${d(t.mensaje)}">\u25B6 procesarlo en un hilo</a>&nbsp;<span class="dim">abre un hilo con <code>${d(t.mensaje)}</code></span></div>`)),i}async abrirItem(a){let t=a.lastIndexOf(":"),r=a.slice(0,t),o=(this.bloquesDatos.get(r)?.pagina?.bloques??[]).flatMap(n=>n.items??[])[Number(a.slice(t+1))];if(!o?.mensaje)return;let i=await Uo(r,o.mensaje,o.nombre||o.titulo);if(!i.datos){g().aviso(`telar: ${i.error??"no pude abrir el hilo"}`);return}await x.sondear(),await g().mostrarTerminal()}async lanzarAtajo(a){let t=this.atajos.find(n=>n.tecla===a)?.nombre??a,r=this.atajosLanzados.get(a);if(r&&Date.now()-r<12e4&&await g().aviso(`\xAB${t}\xBB ya se encarg\xF3 hace ${Math.round((Date.now()-r)/1e3)} s. \xBFOtra vez?`,{modal:!0},"S\xED")!=="S\xED"){await g().mostrarTerminal();return}let o=await g().progreso({title:`telar: ${t}\u2026`},()=>Wo(a));if(!o.datos){g().aviso(`telar: ${o.error??"no pude abrir el atajo"}`);return}this.atajosLanzados.set(a,Date.now());let i=o.datos.encargo;g().estado(`telar: ${t} \u2192 ${o.datos.hilo}${i?` (${i})`:""}`,8e3),await x.sondear(),await g().mostrarTerminal()}async abrirSeccion(a){this.abrir();let t=this.appActual;this.pantalla="seccion",this.seccion!==a&&(this.seccion=a,this.pagina=void 0),t!==this.appActual&&this.alCambiarFoco?.(!0);let r=a.startsWith("app:")?a.slice(4):"",o=(r?x.apps.find(n=>n.clave===r)?.nombre:x.secciones.find(n=>n.clave===a)?.nombre)??a;this.pagina||this.pintar([`<div class="subcab"><b>${d(o)}</b></div>`,'<div class="fila dim">leyendo\u2026</div>']);let i=r?await Mo(r):await zo(a);if(await this.precargarLienzos(i.datos?.bloques),!(this.pantalla!=="seccion"||this.seccion!==a)){if(!i.datos){this.pintar([`<div class="subcab"><b>${d(o)}</b></div>`,`<div class="fila falla">${d(i.error??"el home no contest\xF3")}</div>`]);return}this.pagina=i.datos,this.renderSeccion()}}async abrirTarea(a){let[t,r,o]=JSON.parse(a);this.panel?this.panel.visible||this.panel.revelar():this.abrir(),this.pantalla==="revisar"&&(this.fichaDesde=this.pantalla),this.pantalla==="bloque"&&(this.fichaDesde=`bloque:${this.bloqueSel}:${this.itemSel??""}`),(this.pantalla==="pestana"||this.fichaDesde.startsWith("pestana:"))&&(this.fichaDesde=`pestana:${this.pestana}`),this.pantalla="tarea",this.ficha={proveedor:t,id:r,ref:o};let i=this.fichas.get(`${t}:${r}`);if(i&&Date.now()-i.hora<300*1e3){this.ficha.pagina=i.pagina,this.renderTarea(),this.precargar();return}this.pintar([`<div id="ficha-tarea"><div class="subcab"><b>${d(r)}</b></div><div class="fila dim">leyendo\u2026</div></div>`]);let n=await Z(r,t);n.datos&&this.fichas.set(`${t}:${r}`,{pagina:n.datos,hora:Date.now()}),!(this.pantalla!=="tarea"||this.ficha?.id!==r)&&(this.ficha.pagina=n.datos,this.ficha.aviso=n.datos?"":n.error??"la ficha no contest\xF3",this.renderTarea(),this.precargar())}async precargar(){let a=this.propuestas().filter(r=>{let o=this.fichas.get(`${r.proveedor}:${r.id}`);return!o||Date.now()-o.hora>3e5}).slice(0,10),t=async()=>{for(let r=a.shift();r;r=a.shift()){let o=await Z(r.id,r.proveedor);o.datos&&this.fichas.set(`${r.proveedor}:${r.id}`,{pagina:o.datos,hora:Date.now()})}};await Promise.all([t(),t(),t(),t()])}async abrirRevisar(){if(this.panel||this.abrir(),this.pantalla="revisar",this.fichaDesde="revisar",this.datos||(this.datos=await qe()),this.renderRevisar(),!this.proyectos){let a=await we();a.datos&&(this.proyectos=a.datos.proyectos,this.pantalla==="revisar"&&this.renderRevisar())}}proyectoDe(a){let t=a.proyecto||a.ruta;if(!t||!this.proyectos)return;let r=Bt(t,this.proyectos.map(o=>o.ruta));return this.proyectos.find(o=>o.ruta===r)}renderRevisar(){let a=this.datos;a&&(this.teclas.clear(),this.pintar(this.tablaTareas(a)))}filaTarea(a,t,r){let o=k=>t,i=k=>r,[n]=(a.fila.avance??"").split(" "),s=d(JSON.stringify([a.fila.proveedor,a.fila.id||a.ref,a.ref])),l=!!a.fila.ficha,c=this.proyectoDe(a.fila),u=!c?.cliente||/^(brinca|interno)$/i.test(c.cliente),h=c?u?c.nombre.replace(/^(brinca|interno)\s*·\s*/i,""):c.cliente:"",p=M([a.ref,a.texto,a.hilo,a.fila.ruta??"",a.fila.proyecto??"",c?.nombre??"",a.fila.avance??"",a.fila.dueno??""].join(" ")),f=l?`data-accion="tarea" data-valor="${s}" title="clic: leerla y decidir"`:`data-accion="pendiente" data-valor="${d(a.ref)}" title="clic: ${a.hilo?`llevarlo a \xAB${d(a.hilo)}\xBB`:"abrir un hilo donde trabajarlo"}"`,m=a.fila.dueno??"",b=Q.persona?Q.persona[0].toUpperCase()+Q.persona.slice(1):"t\xFA",w=l?`<span class="resp${m?"":" defecto"}" data-accion="dueno-tarea" data-valor="${d(JSON.stringify([a.fila.proveedor,a.fila.id||a.ref,a.ref,m]))}" title="${d(m?`responsable: ${m}
clic: cambiarlo`:`sin asignar: es tuya por defecto
clic: asignarla`)}">${d(m||b)}</span>`:m?`<span class="resp fijo" title="${d(`responsable: ${m}
(lo dice el documento)`)}">${d(m)}</span>`:'<span class="resp dim" title="la vi\xF1eta no dice qui\xE9n la hace">sin responsable</span>';return`<div class="tarea${a.enCurso?" encurso":""}" ${f} data-area="${d(a.fila.area??"")}"${gi(m,l||!!a.fila.proveedor)} data-rev="${o(a)?1:0}" data-dias="${a.dias??""}" data-encurso="${a.enCurso?1:0}" data-texto="${d(p)}" data-sem="${i(a)?1:0}" data-estrella="${a.fila.estrella?1:0}" data-est="${a.fila.estrella?"a":""}" data-orden="${a.urgencia}" data-ref="${d(a.ref)}" data-alfa="${d(M(ve(a.texto)))}" data-proy="${d(M(h))}" data-resp="${d(M(m||(l?b:"")))}"><span class="id">${d(l||a.fila.proveedor?a.ref:"\xB7")}</span>`+(l?`<span class="estr${a.fila.estrella?" on":""}" data-accion="estrella-tarea" data-valor="${s}" title="${a.fila.estrella?"quitar la estrella":"marcar con estrella: va siempre en \xABesta semana\xBB"}">${a.fila.estrella?"\u2605":"\u2606"}</span>`:"<span></span>")+`<span class="pri">${a.enCurso?"\u25CF":""}</span>`+(c?`<span class="proy-t" data-accion="proy-ir" data-valor="${d(c.ruta)}" title="${d(`${c.nombre}
clic: verlo en proyectos`)}">${d(h)}</span>`:'<span class="proy-t dim">\u2014</span>')+w+`<span class="desc">${o(a)?`<span class="av av-${d(a.avance)}">${d(n.replace(":"," "))}</span>`:""}${d(ve(a.texto))}</span><span class="meta">${l?`<span class="plazo-clic" data-accion="reagendar" data-valor="${s}" title="clic: nueva fecha">${a.dias===null?'<span class="dim">fecha</span>':Fe(a.dias)}</span>`:Fe(a.dias)}<span class="destino"></span>${this.rapidas(a.fila,a.ref,a.texto,s,l)}${l?`<span class="menu-fila" data-accion="menu-tarea" data-valor="${s}" title="acciones de esta tarea">\u22EF</span>`:`<span class="menu-fila" data-accion="menu-vineta" data-valor="${d(JSON.stringify([a.ref,a.texto,a.hilo,m]))}" title="acciones de este pendiente">\u22EF</span>`}</span></div>`}rapidas(a,t,r,o,i){let n=!!a.etiquetas?.includes("equipo"),s=i?`<span class="rap ok" data-accion="hecha-fila" data-valor="${o}" title="marcarla hecha">\u2713</span>`:a.proveedor?'<span class="rap"></span>':`<span class="rap ok" data-accion="hecha-vineta" data-valor="${d(JSON.stringify([t,r]))}" title="marcarla hecha: [ ] \u2192 [x] en su documento">\u2713</span>`,l=i&&x.equipoRemoto?`<span class="rap eq${n?" on":""}" data-accion="equipo-tarea" data-valor="${o}" title="${n?"compartida con el equipo: clic para dejar de compartirla":"compartirla con el equipo (ver\xE1n t\xEDtulo, estado y prioridad; pueden sugerir subirla)"}">${n?"\u25C9":"\u25CB"}</span>`:'<span class="rap"></span>',c=`<span class="rap ir" data-accion="hilo-fila" data-valor="${d(JSON.stringify([a.proveedor,t,i?a.id||t:""]))}" title="${i?`trabajarla: /tarea ${d(a.id||t)} en ${a.hilo?`\xAB${d(a.hilo)}\xBB`:"su hilo"}`:a.hilo?`llevarla a \xAB${d(a.hilo)}\xBB`:"abrirla en un hilo"}">\u25B6</span>`;return`<span class="rapidas">${s}${l}${c}</span>`}tablaTareas(a){let t=ee(a).filter(p=>!this.decididas.has(p.fila.id||p.ref)),r=p=>!!p.avance&&!!p.fila.ficha,o=p=>t.filter(p).length,i=p=>p.dias!==null&&p.dias<=7||!!p.fila.destacada||r(p)&&p.dias!==null&&p.dias<=14,n=[["semana","esta semana",o(i)],["todas","todas",t.length],["revisar","\u25C6 por revisar",o(r)],["vencidas","vencidas",o(p=>p.dias!==null&&p.dias<0)],["estrella","\u2605",o(p=>!!p.fila.estrella)],["encurso","en curso",o(p=>p.enCurso)],["sinfecha","sin fecha",o(p=>p.dias===null)]],s=hi(),l=s?Math.round((Date.now()-s)/6e4):-1,c=`<a data-accion="refrescar" title="volver a leer las tareas ahora (tambi\xE9n r)">\u21BB actualizar</a><span class="dim"> \xB7 ${l<0?"sin leer":l===0?"le\xEDdas reci\xE9n":`le\xEDdas hace ${l} min`}</span>`,u=['<div id="revisar">',I("tareas","cian",String(t.length),c),'<div class="titulo-tareas"><span class="modos">'+n.map(([p,f,m])=>`<button data-modo-t="${p}"${m?"":' class="vacio-m"'}>${d(f)} ${m}</button>`).join("")+'<input id="buscar-t" type="text" placeholder="/ buscar" spellcheck="false" autocomplete="off"><span id="tareas-t-cuenta"></span></span></div>',yi(t.map(p=>p.fila.area??"")),bi(t.map(p=>[p.fila.dueno??"",!!p.fila.proveedor]))];t.length||u.push('<div class="vacio">nada pendiente</div>');let h=(p,f)=>`<span data-orden-c="${p}" title="ordenar por ${f} (otra vez: por urgencia)">\u2195</span>`;u.push(`<div class="tareas-cab">${h("ref","c\xF3digo")}${h("est","estrella")}<span></span>${h("proy","proyecto")}${h("resp","responsable")}${h("alfa","el texto")}<span class="meta">${h("dias","fecha")}</span></div>`),u.push('<div id="tareas-t">');for(let p of t)u.push(this.filaTarea(p,r(p),i(p)));return u.push('<div id="tareas-t-vacio" class="vacio" hidden></div><div id="tareas-t-mas" class="vacio clic" hidden></div></div></section></div>'),u}async abrirPlan(a){this.panel||this.abrir(),this.pantalla="plan",this.planCargando=!0,this.renderPlan();let t=await ea("plan",a);this.planCargando=!1,this.plan=t.datos?.ok?t.datos:void 0,this.planError=t.datos?.ok?"":t.datos?.error??t.error??"no contest\xF3",this.pantalla==="plan"&&this.renderPlan()}renderPlan(){this.teclas.clear(),this.pintar([...this.bloques(this.bloquesCfg.filter(a=>a.en==="plan"),!0),...Ri(this.plan,this.planError,this.planCargando)])}diaCal(){return this.calFecha&&this.calFecha!==this.datos?.fecha?this.calDatos:this.datos}async abrirCalendario(a=""){this.panel||this.abrir(),this.pantalla="calendario",this.datos||(this.datos=await qe());let t=this.datos.fecha;this.calFecha=a===t?"":a;let r=this.calFecha||t;this.calCargando=!!this.calFecha&&this.calDatos?.fecha!==r,this.calCargando&&(this.calDatos={...this.datos,fecha:r,agenda:[],pendientes:[],error:void 0},this.notas=void 0),this.renderCalendario();let[o,i,n]=await Promise.all([this.calFecha?Tt(r):Promise.resolve(this.datos),this.plan?.dia===r?Promise.resolve({datos:this.plan}):ea("plan",this.calFecha?r:""),Ea(this.calFecha?r:"")]);(this.calFecha||t)===r&&(this.calFecha&&(this.calDatos=o),this.calCargando=!1,i.datos?.ok&&(this.plan=i.datos),this.notas=n.datos?.ok?n.datos:void 0,this.notasAviso=n.datos?.aviso??(n.datos?.ok?"":n.datos?.error??n.error??""),this.pantalla==="calendario"&&this.renderCalendario())}async moverDiaCal(a){let t=this.datos?.fecha;if(!t)return;if(a==="hoy")return this.eventoSel="",this.abrirCalendario("");let r=new Date(`${this.calFecha||t}T12:00:00`);r.setDate(r.getDate()+(Number(a)||0));let o=i=>String(i).padStart(2,"0");this.eventoSel="",await this.abrirCalendario(`${r.getFullYear()}-${o(r.getMonth()+1)}-${o(r.getDate())}`)}renderCalendario(){let a=this.diaCal();if(!a)return;this.teclas.clear(),this.teclas.set("[",()=>this.moverDiaCal("-1")),this.teclas.set("]",()=>this.moverDiaCal("1"));let t=this.plan?.dia===a.fecha&&this.plan.formato==="json"?this.plan.contenido:void 0;this.pintar(Ei(a,Ja(a,t),this.notas,this.eventoSel,new Date,this.notasAviso,this.general?.nombre??"",this.datos?.fecha??a.fecha,this.calCargando))}async comentarPlan(a,t){let r=await g().progreso({title:"telar: mandando el comentario sobre el plan\u2026"},()=>Po("plan",a,t));if(!r.ok){g().falla(`telar: el comentario no lleg\xF3: ${r.error??"sin respuesta"}`);return}g().info(r.abrio?`telar: se abri\xF3 \xAB${r.abrio}\xBB para atender el comentario`:"telar: comentario recibido"),setTimeout(()=>{this.plan=void 0,this.actualizar(!0)},3e4)}async escribirSobreEvento(a,t){let r=this.diaCal();if(!t.trim()||!r)return;if(!this.general){g().aviso("telar: no hay un agente que reciba lo sin proyecto ([agentes] sin_proyecto)");return}let o=this.plan?.dia===r.fecha&&this.plan.formato==="json"?this.plan.contenido:void 0,i=Ja(r,o).find(p=>p.id===a);if(!i)return;let n=p=>new Date(p).toTimeString().slice(0,5),s="";if(!i.soloPlan){let p=await Sa(i.titulo,n(i.inicio),i.url,i.id,{asistentes:i.asistentes,preguntar:!0,donde:!0});p.datos?.destino&&p.datos.destino!=="gestion"?s=`Proyecto: ${p.datos.destino}${p.datos.recordado?" (elegido por Nico para esta serie)":" (deducido)"}.`:p.datos?.candidatos?.length?s=`Proyecto: no est\xE1 claro; candidatos: ${p.datos.candidatos.slice(0,3).map(f=>`${f.ruta} (${f.motivos.join(", ")})`).join("; ")}.`:s="Proyecto: ninguno deducido."}let l=ra(i,this.notas).map(p=>`${p.de}: ${p.texto}`),c=[`[Nico, desde el calendario del dashboard] ${t.trim()}`,"",`Contexto. La reuni\xF3n: \xAB${i.titulo}\xBB, ${r.fecha} de ${n(i.inicio)} a ${n(i.fin)}${i.lugar?`, ${i.lugar}`:""}${i.soloPlan?" (bloque del plan del d\xEDa, no est\xE1 en el calendario)":""}.`,i.asistentes.length?`Asistentes: ${i.asistentes.join(", ")}.`:"",s,i.plan?.nota?`El plan del d\xEDa dice: ${i.plan.nota}`:"",i.plan?.ficha?.decision?`Decisi\xF3n que pide el plan: ${i.plan.ficha.decision}`:"",l.length?`Notas del evento: ${l.join(" | ")}`:"",`Id del evento: ${i.id}. Si lo que hagas es de esta reuni\xF3n, d\xE9jale una nota: telar evento nota "${i.id}" "\u2026" --de ${this.general.clave} --titulo "${i.titulo}" --inicio ${n(i.inicio)} --dia ${r.fecha}`].filter(Boolean),u=await g().progreso({title:`telar: escribi\xE9ndole a ${this.general.nombre}\u2026`},()=>Ee(this.general.clave,c.join(`
`)));if(!u.datos){g().falla(`telar: no lleg\xF3 a ${this.general.nombre}: ${u.error??"sin respuesta"}`);return}await Ct(i.id,`A ${this.general.nombre}: ${t.trim()}`,i.titulo,n(i.inicio),r.fecha);let h=await Ea(r.fecha);h.datos?.ok&&(this.notas=h.datos),this.eventoSel=a,g().estado(`telar: enviado a ${this.general.nombre} (${u.datos.estado??""})`,6e3),this.pantalla==="calendario"&&this.renderCalendario()}async notaEvento(a){let[t,r,o,i]=JSON.parse(a),n=await g().campo({title:`Nota para \xAB${r}\xBB`,prompt:"Se guarda junto al evento y la ven las skills",ignoreFocusOut:!0});if(!n?.trim())return;let s=await Ct(t,n.trim(),r,o,i);if(!s.datos?.ok){g().falla(`telar: la nota no se guard\xF3: ${s.datos?.error??s.error??"sin respuesta"}`);return}this.eventoSel=t;let l=await Ea(i);l.datos?.ok&&(this.notas=l.datos),this.pantalla==="calendario"&&this.renderCalendario()}async abrirPeriodicos(){this.panel||this.abrir(),this.pantalla="periodicos",this.periodicos||this.pintar(['<div class="vacio">leyendo los procesos peri\xF3dicos\u2026</div>']);let a=await Bo();this.periodicos=a.datos??this.periodicos,this.periodicosError=a.datos?"":a.error??"no contest\xF3",this.pantalla==="periodicos"&&this.renderPeriodicos()}renderPeriodicos(){let a=this.periodicos;if(this.teclas.clear(),this.teclas.set("+",()=>this.nuevoPeriodico()),this.formPer){this.renderFormPer();return}if(this.periodico){this.renderPeriodico();return}let t=a?.procesos??[],r=t.filter(i=>i.activo).length,o=[I(`peri\xF3dicos${a?.maquina?` \xB7 ${a.maquina}`:""}`,"amarillo",t.length?`${r}/${t.length}`:"",he("+","nuevo","per-nuevo","","un proceso nuevo: un comando de shell o un prompt para el agente"))];this.periodicosError&&o.push(`<div class="vacio falla">${d(this.periodicosError)}</div>`),a&&!t.length&&o.push(`<div class="vacio">ninguno todav\xEDa \xB7 <a data-accion="per-nuevo">crear uno</a> \xB7 se guardan en ${d(a.archivo)}</div>`);for(let i of t){let[n,s,l]=Ui(i),c=i.tipo==="mensaje"?`\u2726 ${i.mensaje}`:i.comando,u=i.activo?i.proxima?`en ${Wt(i.proxima)}`:"\u2014":"pausado",h=i.ultima.inicio?`hace ${se(i.ultima.inicio)}`:"nunca";o.push(`<div class="fila clic per${i.activo?"":" dim"}" data-accion="per-ver" data-valor="${d(i.nombre)}" title="${d(`${i.descripcion?i.descripcion+`
`:""}${l}
clic: su ficha y su log`)}"><span style="color: var(--${s})">${n}</span><b>${d(i.nombre)}</b><code class="dim">${d(i.cuando)}</code><span class="que">${d(c)}</span><span class="der dim">${d(u)} \xB7 ${d(h)}</span></div>`)}o.push("</section>"),a&&o.push(`<div class="vacio dim">${d(a.archivo)}${a.zona?` \xB7 hora de ${d(a.zona)}`:""}</div>`),this.pintar(o)}async verPeriodico(a){this.periodico={nombre:a,log:"leyendo\u2026"},this.renderPeriodicos();let t=await Lo(a);this.periodico?.nombre===a&&(this.periodico.log=t.datos?t.datos.log||"(todav\xEDa no ha corrido)":t.error??"no contest\xF3",this.pantalla==="periodicos"&&this.renderPeriodicos())}renderPeriodico(){let a=this.periodico,t=this.periodicos?.procesos.find(c=>c.nombre===a?.nombre);if(!a||!t){this.periodico=void 0,this.renderPeriodicos();return}let[r,o,i]=Ui(t),n=c=>d(JSON.stringify(c)),s=[`<a class="atajo principal" data-accion="per-orden" data-valor="${n(["ahora",t.nombre])}"><kbd>\u23CE</kbd><span>correr ahora</span></a>`,`<a class="atajo" data-accion="per-orden" data-valor="${n([t.activo?"pausar":"activar",t.nombre])}"><kbd>1</kbd><span>${t.activo?"\u23F8 pausar":"\u25B6 activar"}</span></a>`,`<a class="atajo" data-accion="per-editar" data-valor="${d(t.nombre)}"><kbd>2</kbd><span>\u270E editar</span></a>`,`<a class="atajo" data-accion="per-orden" data-valor="${n(["borrar",t.nombre])}"><kbd>3</kbd><span>\u2715 borrar</span></a>`,'<a class="atajo" data-accion="periodicos"><kbd>\u238B</kbd><span>volver</span></a>'];this.teclas.set("\u23CE",()=>this.ordenPeriodico(["ahora",t.nombre])),this.teclas.set("1",()=>this.ordenPeriodico([t.activo?"pausar":"activar",t.nombre])),this.teclas.set("2",()=>this.editarPeriodico(t.nombre)),this.teclas.set("3",()=>this.ordenPeriodico(["borrar",t.nombre]));let l=[["cu\xE1ndo",`${t.cuando}${t.proxima?` \xB7 la pr\xF3xima ${t.proxima.slice(5,16).replace("T"," ")} (en ${Wt(t.proxima)})`:""}`],t.tipo==="mensaje"?["prompt",t.mensaje]:["comando",t.comando],...t.tipo==="mensaje"?[["hilo",`${t.hilo||t.nombre} \xB7 hasta ${t.max_abiertos} abierto(s)`]]:[],...t.argumentos.length?[["argumentos",t.argumentos.join(" ")]]:[],...t.carpeta?[["carpeta",t.carpeta]]:[],["\xFAltima",t.ultima.inicio?`${t.ultima.inicio.slice(5,16).replace("T"," ")} \xB7 ${t.ultima.resultado??"corriendo"}${t.ultima.hilo?` \xB7 \xAB${t.ultima.hilo}\xBB`:""}`:"nunca"]];this.pintar([`<div id="ficha-per" style="--c: var(--${o})">`,`<div class="subcab"><b>${r} ${d(t.nombre)}</b><span class="der dim">${d(i)}</span></div>`,t.descripcion?`<div class="sub-ficha dim">${d(t.descripcion)}</div>`:"",`<div class="acciones-t">${s.join("")}</div>`,...l.map(([c,u])=>`<div class="fila"><span class="dim" style="min-width: 11ch">${d(c)}</span><span class="que">${d(u)}</span></div>`),`<h2 class="sec">log</h2><pre class="log">${d(a.log)}</pre></div>`])}async ordenPeriodico(a){if(a[0]==="borrar"&&await g().aviso(`\xBFBorrar el proceso \xAB${a[1]}\xBB? Deja de correr; el archivo anterior queda en periodicos.toml.anterior.`,{modal:!0},"Borrar")!=="Borrar")return;let t=await Dt(a);if(!t.datos){g().aviso(`telar: ${t.error??"no se pudo"}`);return}if(g().estado(`telar: ${t.datos.hecho}`,5e3),a[0]==="borrar"&&(this.periodico=void 0),await this.abrirPeriodicos(),this.periodico){let r=this.periodico.nombre;setTimeout(()=>{this.periodico?.nombre===r&&this.abrirPeriodicos().then(()=>this.verPeriodico(r))},a[0]==="ahora"?4e3:0)}}async nuevoPeriodico(){let t=(this.periodicos?.procesos??[]).find(o=>o.tipo==="mensaje"),r={nombre:"",cuando:"0 9 * * 1-5",tipo:"mensaje",comando:"",mensaje:"",hilo:"",max_abiertos:1,argumentos:t?.argumentos??["--permission-mode","acceptEdits"],carpeta:t?.carpeta??"",descripcion:"",activo:!0,proxima:"",ultima:{}};await this.abrirFormPer("",r)}async editarPeriodico(a){let t=this.periodicos?.procesos.find(r=>r.nombre===a);t&&await this.abrirFormPer(a,{...t,argumentos:[...t.argumentos]})}async abrirFormPer(a,t){this.panel||this.abrir(),this.pantalla="periodicos",this.formPer={original:a,p:t},this.renderPeriodicos(),await Promise.all([this.previaHorario(t.cuando),this.cargarSkills(t.carpeta)])}renderFormPer(){let a=this.formPer;if(!a)return;let t=a.p;this.teclas.clear();let r=(i,n,s="")=>`<label class="campo"><span class="etiqueta">${d(i)}</span><span class="control">${n}${s?`<span class="ayuda dim">${d(s)}</span>`:""}</span></label>`,o=[["0 9 * * *","todos los d\xEDas 9:00"],["0 9 * * 1-5","lun\u2013vie 9:00"],["0 8-20/2 * * *","cada 2 h, 8\u201320"],["0 * * * *","cada hora"],["*/30 * * * *","cada 30 min"],["30 18 * * 5","viernes 18:30"],["0 9 1 * *","el 1 de cada mes"]];this.pintar([`<div id="form-per" class="tipo-${t.tipo}">`,I(a.original?`editar \xAB${a.original}\xBB`:"un proceso peri\xF3dico nuevo","amarillo",this.periodicos?.maquina??""),r("nombre",`<input id="per-nombre" value="${d(t.nombre)}" placeholder="resumen-diario" spellcheck="false"${a.original?" disabled":""}>`,a.original?"el nombre no se cambia":"min\xFAsculas, n\xFAmeros, - y _"),r("para qu\xE9",`<input id="per-desc" value="${d(t.descripcion)}" placeholder="en una l\xEDnea, para acordarte">`),r("qu\xE9 hace",`<span class="opciones"><a class="opcion-t${t.tipo==="mensaje"?" activa":""}" data-per-tipo="mensaje">\u2726 prompt para el agente</a><a class="opcion-t${t.tipo==="comando"?" activa":""}" data-per-tipo="comando">$ comando de shell</a></span>`),'<div class="solo-mensaje">',r("skill",`<input id="per-skill-filtro" placeholder="buscar una skill\u2026" spellcheck="false" autocomplete="off"><div id="per-skills" class="skills">${this.htmlSkills()}</div>`,"elegir una la pone como prompt; despu\xE9s puedes agregarle texto"),r("prompt",`<textarea id="per-mensaje" rows="4" placeholder="/correo, o lo que quieras pedirle" spellcheck="false">${d(t.mensaje)}</textarea>`),r("hilo",`<input id="per-hilo" value="${d(t.hilo)}" placeholder="${d(t.nombre||"el nombre del proceso")}">`,"su nombre; se le agrega la fecha y la hora"),r("abiertos",`<input id="per-max" type="number" min="1" value="${t.max_abiertos}">`,"con tantos sin cerrar, esa vez no abre otro"),r("argumentos",`<textarea id="per-args" rows="3" spellcheck="false">${d(t.argumentos.join(`
`))}</textarea>`,"para el agente, uno por l\xEDnea (permisos, herramientas)"),'</div><div class="solo-comando">',r("comando",`<input id="per-comando" value="${d(t.comando)}" placeholder="~/bin/resumen --corto" spellcheck="false">`,"una l\xEDnea de bash; su salida queda en el log"),"</div>",r("cu\xE1ndo",`<input id="per-cuando" value="${d(t.cuando)}" spellcheck="false"><span class="presets">${o.map(([i,n])=>`<a data-per-horario="${d(i)}" title="${d(i)}">${d(n)}</a>`).join("")}</span><div id="per-previa" class="dim">\u2026</div>`,"cron: minuto hora d\xEDa-del-mes mes d\xEDa-de-la-semana"),r("carpeta",`<input id="per-carpeta" value="${d(t.carpeta)}" placeholder="~ (el hogar)" spellcheck="false">`,"d\xF3nde corre; las skills de la lista son las de ah\xED"),r("activo",`<input id="per-activo" type="checkbox"${t.activo?" checked":""}>`),'<div id="per-error" class="falla"></div>',`<div class="acciones-t fila-botones"><a class="atajo principal" data-accion="per-guardar"><kbd>\u2318\u23CE</kbd><span>${a.original?"guardar":"crear"}</span></a><a class="atajo" data-accion="per-cancelar"><kbd>\u238B</kbd><span>cancelar</span></a></div>`,"</section></div>"])}htmlSkills(){let a=this.formPer;return a?.skills?a.skills.length?a.skills.map(t=>`<a class="skill" data-skill="${d(t.nombre)}" data-texto="${d(M(`${t.nombre} ${t.descripcion}`))}" title="${d(t.descripcion)}"><b>/${d(t.nombre)}</b><span class="dim">${d(t.descripcion)}</span></a>`).join(""):'<div class="dim">no hay skills en esa carpeta</div>':'<div class="dim">leyendo las skills de all\xE1\u2026</div>'}async previaHorario(a){let t=await No(a),r=t.datos,o=r?r.valido?"las pr\xF3ximas: "+r.proximas.map(i=>`<b>${d(vc(i))}</b>`).join(" \xB7 ")+(r.proximas[0]?` <span class="dim">(en ${d(Wt(r.proximas[0]))})</span>`:""):`<span class="falla">${d(r.error)}</span>`:`<span class="falla">${d(t.error??"no contest\xF3")}</span>`;this.parcial("per-previa",o)}async cargarSkills(a){let t=this.formPer;if(!t||t.skills&&t.skillsDe===a)return;t.skills=void 0,this.parcial("per-skills",this.htmlSkills());let r=await Oo(a);this.formPer===t&&(t.skills=r.datos?.skills??[],t.skillsDe=a,this.parcial("per-skills",r.datos?this.htmlSkills():`<div class="falla">${d(r.error??"no contest\xF3")}</div>`))}parcial(a,t){this.panel?.enviar({tipo:"parcial",id:a,html:t})}async guardarFormPer(a){let t=this.formPer;if(!t)return;let r=JSON.parse(a),o=t.original||r.nombre.trim(),i=r.args.split(`
`).map(l=>l.trim()).filter(Boolean),n=[t.original?"editar":"nuevo",o,"--cuando",r.cuando.trim(),"--descripcion",r.descripcion.trim(),"--carpeta",r.carpeta.trim()];r.tipo==="mensaje"?(n.push("--mensaje",r.mensaje.trim(),"--hilo",r.hilo.trim(),"--max",r.max.trim()||"1"),i.length?n.push(...i.map(l=>`--arg=${l}`)):t.original&&n.push("--sin-args")):(n.push("--comando",r.comando.trim()),t.original&&n.push("--sin-args")),t.original?n.push("--activo",r.activo?"si":"no"):r.activo||n.push("--pausado"),this.parcial("per-error",'<span class="dim">guardando\u2026</span>');let s=await Dt(n);if(!s.datos){this.parcial("per-error",d(s.error??"no se pudo"));return}g().estado(`telar: ${s.datos.hecho}`,5e3),this.formPer=void 0,this.periodico={nombre:o,log:""},await this.abrirPeriodicos(),await this.verPeriodico(o)}async abrirPestana(a){this.panel||this.abrir(),this.pantalla="pestana",this.pestana=a,this.fichaDesde=`pestana:${a}`,this.datos||(this.datos=await qe()),this.precargar();let t=ee(this.datos,a).find(r=>r.fila.ficha&&!this.decididas.has(r.fila.id||r.ref));if(t){await this.abrirTarea(JSON.stringify([t.fila.proveedor,t.fila.id||t.ref,t.ref]));return}this.renderPestana()}renderPestana(){let a=this.datos;if(!a)return;this.teclas.clear();let t=ee(a,this.pestana).filter(o=>!this.decididas.has(o.fila.id||o.ref)),r=['<div id="revisar">',I(this.pestana,"magenta",t.length?String(t.length):"",t.length?fi("\u23CE","el primero"):"")];t.length||r.push('<div class="vacio">nada por ahora</div>');for(let o of t){let[i]=(o.fila.avance??"").split(" "),n=d(JSON.stringify([o.fila.proveedor,o.fila.id||o.ref,o.ref]));r.push(`<div class="tarea" data-accion="tarea" data-valor="${n}" title="clic: leerlo"><span class="id"></span><span class="pri"></span><span class="desc">${i?`<span class="av"${o.fila.color?` style="color: var(--${d(o.fila.color)})"`:""}>${d(i)}</span>`:""}${d(o.texto)}</span><span class="meta">${Fe(o.dias)}<span class="destino"></span></span></div>`)}r.push("</section></div>"),this.pintar(r)}propuestas(a=this.fichaDesde.startsWith("pestana:")?this.fichaDesde.slice(8):""){return this.datos?ee(this.datos,a).filter(t=>(a||t.avance)&&t.fila.ficha&&(!this.decididas.has(t.fila.id||t.ref)||(t.fila.id||t.ref)===this.ficha?.id)).map(t=>({proveedor:t.fila.proveedor,id:t.fila.id||t.ref,ref:t.ref})):[]}async otraPropuesta(a){let t=this.propuestas(),r=t.findIndex(i=>i.id===this.ficha?.id),o=t[r<0?0:r+a];return!o||o.id===this.ficha?.id?!1:(await this.abrirTarea(JSON.stringify([o.proveedor,o.id,o.ref])),!0)}renderTarea(){let a=this.ficha;if(!a)return;let t=a.pagina;if(!t){this.pintar([`<div id="ficha-tarea"><div class="subcab"><b>${d(a.id)}</b></div>`,`<div class="fila falla">${d(a.aviso??"")}</div></div>`]);return}let r=this.propuestas(),o=r.findIndex(c=>c.id===a.id),i=o>=0&&r.length>1?`<span class="pasar"><a data-accion="tarea-anterior" title="la anterior (\u2190)">\u2190</a><span class="dim">${o+1}/${r.length}</span><a data-accion="tarea-siguiente" title="la siguiente (\u2192)">\u2192</a></span>`:"";this.teclas.clear();let n=0,s=(t.acciones??[]).map((c,u)=>{let h=c.principal?"\u23CE":String(++n);return c.principal||this.teclas.set(h,()=>this.accionTarea(u)),`<a class="atajo${c.principal?" principal":""}" data-accion="accion-tarea" data-valor="${u}" title="${d(c.pide?`${c.nombre}: pide ${c.pide}`:c.nombre)}"><kbd>${h}</kbd><span>${d(c.nombre)}</span></a>`}),l=t.bloques.find(c=>c.destacado)?.color;this.pintar([`<div id="ficha-tarea"${l?` style="--c: var(--${d(l)})"`:""}>`,`<div class="subcab"><b>${d(t.titulo)}</b><span class="der">${i}</span></div>`,t.subtitulo?`<div class="sub-ficha dim">${d(t.subtitulo)}</div>`:"",s.length?`<div class="acciones-t">${s.join("")}</div>`:"",...this.htmlBloques(t.bloques),"</div>"])}async accionTarea(a){let t=this.ficha,r=t?.pagina?.acciones?.[a];if(!t||!r)return;let o=r.tipo??"comando";if(o==="hilo"){await fe(t.ref,!1,t.proveedor);return}if(o==="abrir"){r.enlace&&await $e(r.enlace);return}let i="";if(r.rol==="dueno"){let h=await Ha(`${t.id} ${t.pagina?.titulo??""}`.trim(),"",r.opciones??[],Q.persona);if(!h)return;i=h}else if(r.rol==="fecha"){let h=await Oa(`${t.id} ${t.pagina?.titulo??""}`.trim());if(!h)return;i=h}else if(r.pide){let h=await g().campo({prompt:`${t.id} \xB7 ${r.nombre}`,placeHolder:r.pide,ignoreFocusOut:!0});if(h===void 0)return;i=h}if(r.confirmar&&await g().aviso(`\xBF${r.nombre}? ${t.pagina?.titulo??t.id}`,{modal:!0},"S\xED")!=="S\xED")return;let n=t.pagina?.version??"",s=r.mensaje?await g().progreso({title:`telar: ${r.nombre} \xB7 ${t.id}\u2026`},()=>ie(t.id,t.proveedor,a,i,n)):await ie(t.id,t.proveedor,a,i,n);if(!s.datos){/cambió desde que se leyó/.test(s.error??"")&&this.fichas.delete(t.id),g().aviso(`telar: ${s.error??`no pude: ${r.nombre}`}`);return}if(s.datos.hilo){this.decididas.add(t.id),U(),this.actualizar(!0),await x.sondear(),await g().mostrarTerminal();return}let l=!!t.pagina?.bloques.some(h=>h.destacado);this.fichas.delete(`${t.proveedor}:${t.id}`);let c=await Z(t.id,t.proveedor);c.datos&&this.fichas.set(`${t.proveedor}:${t.id}`,{pagina:c.datos,hora:Date.now()});let u=!this.fichaDesde.startsWith("pestana:")&&!!c.datos?.bloques.some(h=>h.destacado);if(U(),this.actualizar(!0),l&&!u){if(this.decididas.add(t.id),await this.otraPropuesta(1))return;if(this.fichaDesde==="revisar"){await this.abrirRevisar();return}if(this.fichaDesde.startsWith("pestana:")){await this.abrirPestana(this.fichaDesde.slice(8));return}}this.pantalla==="tarea"&&this.ficha?.id===t.id&&(this.ficha.pagina=c.datos??this.ficha.pagina,this.renderTarea())}async menuTarea(a){let[t,r,o]=JSON.parse(a),n=this.fichas.get(`${t}:${r}`)?.pagina??(await g().progreso({ventana:!0,title:`telar: ${r}`},()=>Z(r,t))).datos,s=n?.acciones??[];if(!s.length){g().aviso(`telar: ${r} no tiene acciones`);return}let l=s.map((b,w)=>({label:b.nombre,k:w,description:[b.rol==="fecha"?"elige la fecha":b.pide?`pide ${b.pide}`:"",b.confirmar?"pide confirmaci\xF3n":"",b.tipo==="hilo"?"abre su hilo":b.mensaje?"le escribe a Claude":""].filter(Boolean).join(" \xB7 ")})),c=await g().elegir(l,{title:`${r} \xB7 ${n?.titulo??""}`,placeHolder:"qu\xE9 hacer con esta tarea"});if(!c)return;let u=s[c.k],h=u.tipo??"comando";if(h==="hilo"){await fe(o,!1,t);return}if(h==="abrir"){u.enlace&&await $e(u.enlace);return}let p="";if(u.rol==="fecha"){let b=await Oa(`${r} ${n?.titulo??""}`.trim());if(!b)return;p=b}else if(u.pide){let b=await g().campo({prompt:`${r} \xB7 ${u.nombre}`,placeHolder:u.pide,ignoreFocusOut:!0});if(b===void 0)return;p=b}if(u.confirmar&&await g().aviso(`\xBF${u.nombre}? ${n?.titulo??r}`,{modal:!0},"S\xED")!=="S\xED")return;let f=await g().progreso({title:`telar: ${u.nombre} \xB7 ${r}\u2026`},()=>ie(r,t,c.k,p));if(!f.datos){g().aviso(`telar: ${f.error??`no pude: ${u.nombre}`}`);return}if(this.fichas.delete(`${t}:${r}`),U(),f.datos.hilo){this.decididas.add(r),this.actualizar(!0),await x.sondear(),await g().mostrarTerminal();return}let m=await Z(r,t);m.datos&&this.fichas.set(`${t}:${r}`,{pagina:m.datos,hora:Date.now()}),m.datos?.bloques.some(b=>b.destacado)||this.decididas.add(r),g().estado(`${r}: ${u.nombre}`,5e3),await this.actualizar(!0),this.pantalla==="revisar"&&this.renderRevisar()}lienzos=new Map;async precargarLienzos(a){let t=(a??[]).flatMap(r=>r.lienzo?[r.lienzo.archivo,...r.lienzo.memoria?[r.lienzo.memoria]:[]]:[]);await Promise.all(t.map(async r=>{let o=await pe().leer(r);o!==void 0?this.lienzos.set(r,o):this.lienzos.delete(r)}))}htmlBloques(a){let t=[];return this.memorias.clear(),a.forEach((r,o)=>{r.lienzo&&t.push(this.htmlLienzo(r.lienzo)),r.marco&&t.push(bc(r.marco)),r.destacado&&t.push(`<div class="prop" style="--c: var(--${d(r.color??"azul")})">`),r.titulo?t.push(`<h2>${d(r.titulo)}</h2>`):o>0&&!r.destacado&&t.push('<div class="sep-pag"></div>'),r.texto&&t.push(`<div class="md-pag">${Ua(r.texto)}</div>`);for(let i of r.items??[]){let n=i.conversacion?` data-accion="conversacion" data-valor="${d(i.conversacion)}"`:i.hilo?` data-accion="ir" data-valor="${d(i.hilo)}"`:i.enlace?` data-accion="abrir-enlace" data-valor="${d(i.enlace)}"`:"",s=i.fecha?i.fecha.slice(0,16).replace("T"," ").replace(" 00:00",""):"";t.push(`<div class="item-pag${n?" clic":""}"${n} title="${d(i.conversacion?"clic: leer la conversaci\xF3n entera":i.hilo?`clic: ir a \xAB${i.hilo}\xBB`:i.enlace?`clic: abrir ${i.enlace}`:"")}"><div class="fila"><b>${d(i.titulo)}</b><span class="der dim">${d(s)}</span></div>`+(i.texto?`<div class="texto-pag">${Ua(i.texto)}</div>`:"")+"</div>")}r.destacado&&t.push("</div>")}),t}renderSeccion(){let a=this.pagina;if(!a)return;let t=[`<div class="subcab"><b>${d(a.titulo)}</b>${a.subtitulo?`<span class="dim">${d(a.subtitulo)}</span>`:""}<span class="der">`+this.atajos.filter(r=>r.en===`seccion:${this.seccion}`).map(r=>he(r.tecla,r.nombre,"atajo",r.tecla,r.descripcion||r.mensaje)).join("")+(a.acciones??[]).filter(r=>r.tipo==="abrir"&&r.enlace).map(r=>`<a class="atajo" data-accion="abrir-enlace" data-valor="${d(r.enlace)}" title="${d(r.enlace)}"><span>\u2197</span> ${d(r.nombre)}</a>`).join("")+'<a class="atajo" data-accion="recargar-seccion" title="volver a pedir la p\xE1gina"><span>\u21BB</span></a></span></div>'];t.push(...this.htmlBloques(a.bloques)),this.pintar(t)}htmlLienzo(a){let t=this.lienzos.get(a.archivo);if(t===void 0)return`<div class="fila falla">no pude leer ${d(a.archivo)}</div>`;let r={};for(let[s,l]of Object.entries(a.params??{}))r[s]=String(l);let o=JSON.stringify(r).replace(/</g,"\\u003c"),i="";if(a.memoria){let s=Ne();this.memorias.set(s,a.memoria);let l="null";try{let c=this.lienzos.get(a.memoria);c!==void 0&&(JSON.parse(c),l=c)}catch{}i=`window.lienzo.memoria=${l.replace(/</g,"\\u003c")};window.lienzo.guardar=function(d){parent.postMessage({lienzo:'guardar',llave:${JSON.stringify(s)},datos:JSON.stringify(d)},'*')};`}return t=`<script nonce="${this.nonce}">(function(){var p=${o};window.lienzo={params:p};${i}var q=new URLSearchParams(p).toString();if(q){try{history.replaceState(null,'','about:srcdoc?'+q)}catch(e){}}})()<\/script>`+t.replace(/<script(?![^>]*\bnonce=)/gi,`<script nonce="${this.nonce}"`),`<iframe class="lienzo${a.alto==="lleno"?" lleno":""}" sandbox="allow-scripts" srcdoc="${d(t)}"${Zi(a.alto)}></iframe>`}async abrirEquipo(a){this.abrir(),this.pantalla="equipo",this.equipoId=a,this.renderEquipo(),await x.leerEquipo(),this.pantalla==="equipo"&&this.renderEquipo()}renderEquipo(){this.teclas.clear();let a=x.sugerencias.find(s=>s.id===this.equipoId),t='<div class="fila"><a data-accion="dia">\u2190 volver al dashboard</a></div>';if(!a){this.pintar(['<div class="subcab"><b>Equipo</b></div>','<div class="fila dim">esa entrada ya se resolvi\xF3, o no est\xE1.</div>',t]);return}let r=a.tipo==="tarea",o=[`<div class="subcab"><b>${d(a.persona)}</b> ${r?"te pide una tarea":"sugiere subir una prioridad"}<span class="der dim">${d(Ut(a.cuando))}</span></div>`];if(r)o.push(`<h2>\xAB${d(a.titulo)}\xBB${a.vence?`<small>para el ${d(a.vence)}</small>`:""}</h2>`);else{let s=a.prioridad===null?"":` \xB7 hoy P${a.prioridad}, subir\xEDa a P${Math.max(0,a.prioridad-1)}`;o.push(`<h2>${d(a.tarea)} \xB7 ${d(a.titulo)}<small>${d(s.replace(/^ · /,""))}</small></h2>`)}a.motivo&&o.push(`<div class="md-pag"><p style="white-space:pre-wrap">${d(a.motivo)}</p></div>`),a.revisando&&o.push(`<div class="fila dim">${d(a.revisando.quien)} la revisa desde ${d(Ut(a.revisando.desde))}: te contesta en una l\xEDnea cuando decida.</div>`);let i=a.similares??[];if(i.length){o.push("<h2>\xBFya existe?<small>tareas tuyas que parecen lo mismo</small></h2>");for(let s of i)o.push(`<div class="item-pag"><div class="fila"><b>${d(s.id)}</b> ${d(s.titulo)}</div><div class="fila dim">${d(s.estado)}${s.prioridad===null?"":` \xB7 P${s.prioridad}`}${s.vence?` \xB7 vence ${d(s.vence)}`:""}${s.avance?` \xB7 ${d(s.avance)}`:""}${s.compartida?"":" \xB7 no compartida"}</div><div class="fila"><a data-accion="equipo-accion" data-valor="${d(`existe|${a.id}|${s.id}`)}" title="no se agrega nada: ${d(a.persona)} recibe el estado de esa tarea">es esta: contestarle su estado</a></div></div>`)}let n=[["1",a.revisando?"preguntarle de nuevo a Gesti\xF3n":"preguntarle a Gesti\xF3n",`gestion|${a.id}`,"Gesti\xF3n revisa si ya existe y decide: nueva, actualizar una existente o no corresponde"],...r?[["2","agregar como tarea",`aceptar|${a.id}`,"P2, etiquetada equipo"+(a.vence?`, para el ${a.vence}`:"")]]:[["2",`subir la prioridad de ${a.tarea}`,`aceptar|${a.id}`,"un nivel, con el CLI de tareas"]],["3",r?"descartar":"rechazar",`rechazar|${a.id}`,`puedes dejarle una nota a ${a.persona}`]];o.push('<h2>qu\xE9 hacer</h2><div class="acciones-t fila-botones">'+n.map(([s,l,c,u])=>he(s,l,"equipo-accion",c,u)).join("")+"</div>");for(let[s,,l]of n)this.teclas.set(s,()=>this.accionEquipo(l));o.push(t),this.pintar(o)}async accionEquipo(a){let[t,r,o=""]=a.split("|"),i=x.sugerencias.find(n=>n.id===r);i&&(t==="gestion"?await li(i):await ci(i,t,o),this.pantalla==="equipo"&&this.renderEquipo())}async abrirCorreo(){this.pantalla="correo",this.pintar(['<div class="subcab"><b>Mensajes entre hilos</b></div>','<div class="fila dim">leyendo\u2026</div>']);let a=await ei();if(this.pantalla==="correo"){if(this.mensajesBus=a.datos?.mensajes,!this.mensajesBus){this.pintar(['<div class="subcab"><b>Mensajes entre hilos</b></div>',`<div class="fila falla">${d(a.error??"no pude leer el registro del bus")}</div>`]);return}this.renderCorreo()}}renderCorreo(){let a=['<div class="subcab"><b>Mensajes entre hilos</b><span class="der dim"><a data-accion="correo" title="volver a leer">\u21BB</a></span></div>'];this.mensajesBus&&a.push(...this.htmlMensajesBus(this.mensajesBus)),this.pintar(a)}htmlMensajesBus(a){let t=new Set(a.filter(n=>n.estado!=="retenido").map(n=>n.id)),r=a.filter(n=>n.estado==="retenido"&&!t.has(n.id)),o=[`<h2>entre hilos<small>por el bus \xB7 ${a.length} \xFAltimo${a.length===1?"":"s"}${r.length?` \xB7 ${r.length} retenido${r.length===1?"":"s"}`:""}</small></h2>`];a.length||o.push('<div class="fila dim">nada todav\xEDa</div>');let i=(n,s)=>{let l=this.abiertoMsg.has(n.id),c=l?n.texto:n.texto.split(/\s+/).join(" ").slice(0,140);return`<div class="item-pag clic" data-accion="ver-msg" data-valor="${d(n.id)}" title="clic: ${l?"acortar":"el texto entero"}"><div class="fila">${s?'<span class="falla">\u23F8 </span>':""}<b>${d(n.de)}</b><span class="dim"> \u2192 </span><b>${d(n.para)}</b><span class="dim"> \xB7 ${d(n.tipo)}${n.saltos?` \xB7 salto ${n.saltos}`:""}</span><span class="der dim">${d(Ut(n.creado))}`+(s?` \xB7 <a data-accion="soltar-msg" data-valor="${d(n.id)}" title="mandarlo igual: lo decides t\xFA">soltar</a>`:"")+"</span></div>"+(s&&n.motivo?`<div class="fila falla">${d(n.motivo)}</div>`:"")+`<div class="fila${l?"":" dim"}" style="white-space:pre-wrap">${d(c)}</div></div>`};for(let n of r)o.push(i(n,!0));for(let n of[...a].reverse())n.estado!=="retenido"&&o.push(i(n,!1));return o}async soltarMensaje(a){let t=await ai(a);if(!t.datos){g().falla(`telar: no se solt\xF3: ${t.error??"sin respuesta"}`);return}g().estado(`telar: soltado, en la casilla de \xAB${t.datos.para}\xBB`,4e3),await this.abrirCorreo()}async abrirConversacion(a){this.pantalla="conversacion",this.pintar(['<div class="fila dim">leyendo la conversaci\xF3n\u2026</div>']);let t=await Ho(a);if(this.pantalla!=="conversacion")return;if(!t.datos){this.pintar([`<div class="fila falla">${d(t.error??"no pude leerla")}</div>`,'<div class="fila"><a data-accion="volver-seccion">\u2190 volver</a></div>']);return}this.charla=t.datos;let r=t.datos,o=r.hilo&&x.porNombre(r.hilo),i=[`<div class="subcab"><b>Conversaci\xF3n</b><span class="dim">${d(r.conversacion.slice(0,8))}${r.hilo?` \xB7 ${d(r.hilo)}`:""} \xB7 ${r.mensajes.length} mensajes</span><span class="der dim">`+(o?'<a data-accion="retomar-charla" title="volver a esta conversaci\xF3n en su hilo">\u25B6 retomar</a> \xB7 ':"")+(this.seccion?'<a data-accion="volver-seccion">\u2190 '+d(x.secciones.find(n=>n.clave===this.seccion)?.nombre??"volver")+"</a>":"")+"</span></div>"];for(let n of r.mensajes){let s=n.hora?fc(n.hora):"";n.quien==="herramienta"?i.push(`<div class="herr dim">\u203A ${d(n.texto)}</div>`):i.push(`<div class="msg ${n.quien}"><div class="quien">${n.quien==="usuario"?"t\xFA":"agente"}<span class="dim"> ${d(s)}</span></div><div class="md-pag">${Ua(n.texto)}</div></div>`)}this.pintar(i)}async preparar(a,t,r,o="",i=[]){let n=l=>g().progreso({title:`telar: ${a}\u2026`},()=>Sa(a,t,r,o,{asistentes:i,...l})),s=await n({preguntar:!0});if(s.datos?.hecho==="preguntar"){let l=await this.elegirProyecto(a,t,s.datos);if(!l)return;s=await n({proyecto:l})}if(!s.datos){g().aviso(`telar: ${s.error??"no pude abrir la reuni\xF3n"}`);return}g().estado(`telar: \xAB${a}\xBB \u2192 ${s.datos.hilo}: ${s.datos.hecho}`,6e3),await x.sondear(),await g().mostrarTerminal()}async elegirProyecto(a,t,r){let o=u=>({label:u,separador:!0}),i=[],n=r.candidatos??[];if(n.length){i.push(o("sugeridos"));for(let u of n)i.push({label:u.nombre,description:u.ruta,detail:u.motivos.join(" \xB7 "),valor:u.ruta})}i.push(o("otros destinos")),i.push({label:r.gestion||"Gesti\xF3n",description:"el agente de lo que no tiene proyecto",valor:"gestion"}),i.push({label:"Proyecto nuevo\u2026",description:"se le pide al agente crearlo con su nombre",valor:"nuevo"});let s=await we();if(s.datos){i.push(o("todos los proyectos"));let u=new Set(n.map(p=>p.ruta)),h=[...s.datos.proyectos].filter(p=>!u.has(p.ruta)&&!Ia(p)).sort((p,f)=>(f.modificado??"").localeCompare(p.modificado??""));for(let p of h)i.push({label:p.nombre,description:`${p.ruta} \xB7 ${p.arquetipo}`,valor:p.ruta})}let l=await g().elegir(i,{title:`\xBFDe qu\xE9 proyecto es \xAB${a}\xBB (${t})?`,placeHolder:"escribe para buscar un proyecto; la elecci\xF3n se recuerda para esta reuni\xF3n",matchOnDescription:!0,matchOnDetail:!0,ignoreFocusOut:!0});if(!l?.valor)return;if(l.valor!=="nuevo")return l.valor;let c=await g().campo({title:"Proyecto nuevo",prompt:"El nombre del proyecto",ignoreFocusOut:!0});return c?.trim()?`nuevo:${c.trim()}`:void 0}async abrirProyectos(){this.pantalla="proyectos",this.avisoProyectos="",this.pendRepo=void 0,this.proyectos||this.renderProyectos("leyendo los proyectos\u2026");let a=_t().then(r=>{if(this.pendRepo=r.datos?.pendientes??[],this.pendRepoAviso=r.datos?"":r.error??"telar pendientes no contest\xF3",this.pantalla!=="proyectos")return;let o=this.cuentasPendientes();o&&this.panel?.enviar({tipo:"proy-pend",cuentas:Object.fromEntries(o)}),this.proySel&&this.verProyecto(this.proySel,!1)}),t=await we();t.datos?this.proyectos=t.datos.proyectos:this.avisoProyectos=t.error??"telar proyectos no contest\xF3",this.proySel&&!this.proyectos?.some(r=>r.ruta===this.proySel)&&(this.proySel="",this.proyDet=void 0),this.pantalla==="proyectos"&&this.renderProyectos(),this.proySel&&this.verProyecto(this.proySel),await a}pendientesDe(a){let t=this.filasPorProyecto()?.get(a);return t?ee({...this.datos??{fecha:""},pendientes:t}):this.pendRepo?[]:null}filasPorProyecto(){if(!this.pendRepo)return null;let a=(this.proyectos??[]).map(o=>o.ruta),t=new Map,r=(o,i)=>{o&&t.set(o,[...t.get(o)??[],i])};for(let o of this.pendRepo)!o.proveedor&&!o.hecho&&r(o.ruta,o);for(let o of this.datos?.pendientes??[])o.proveedor&&o.clase!=="evento"&&!o.hecho&&!o.pestana&&o.proyecto&&r(Bt(o.proyecto,a),o);return t}cuentasPendientes(){let a=this.filasPorProyecto();return a?new Map([...a].map(([t,r])=>[t,r.length])):void 0}async verProyecto(a,t=!0){let r=this.proyectos?.find(n=>n.ruta===a);if(!r||!this.panel)return;this.proySel=a;let o=this.proyDet?.p.ruta===a?this.proyDet.readme:null;if(this.proyDet={p:r,pendientes:this.pendientesDe(a),aviso:this.pendRepoAviso,readme:t?null:o},this.pintarDetalleProyecto(),!t&&o!==null)return;let i=await this.readmeHtml(a);this.proySel!==a||!this.proyDet||(this.proyDet.readme=i,this.pintarDetalleProyecto())}pintarDetalleProyecto(){this.panel?.enviar({tipo:"parcial",id:"proy-det",html:Lt(this.proyDet)})}async readmeHtml(a){if(!x.raiz||a.includes(".."))return"";let t;for(let r of["README.md","readme.md"])if(t=await pe().leer(z(x.raiz,a,r)),t!==void 0)break;if(t===void 0)return"";try{let r=t.slice(0,3e5);return r=r.replace(/^---\n[\s\S]*?\n---\n/,""),await g().markdown(r)??""}catch(r){return`<p class="falla">no pude leer el README: ${d(String(r))}</p>`}}personas;async personasConocidas(){if(!this.personas){let t=this.datos?.pendientes.find(o=>o.ficha&&o.proveedor),r=t?await Z(t.id||t.ref,t.proveedor):void 0;this.personas=r?.datos?.acciones?.find(o=>o.rol==="dueno")?.opciones??[]}let a=[...this.datos?.pendientes??[],...this.pendRepo??[]].map(t=>t.dueno??"").filter(Boolean);return[...new Set([...this.personas,...a])].sort((t,r)=>t.localeCompare(r))}async menuVineta(a){let[t,r,o,i]=JSON.parse(a),n=async c=>{if(!c.datos){g().falla(`telar: ${c.error??"no pude cambiarla"}`);return}g().estado(`telar: ${c.datos.relativa}:${c.datos.linea} \xB7 ${c.datos.hecho} (sin commitear)`,6e3),U(),this.pendRepo=void 0,await this.actualizar(!0),this.pantalla==="revisar"?this.renderRevisar():this.pantalla==="proyectos"&&await this.abrirProyectos()},s=[{label:o?`Llevarla a \xAB${o}\xBB`:"Llevarla a un hilo",description:"escrita y sin enviar",hacer:()=>fe(t,!1)},{label:"Un hilo nuevo para ella",hacer:()=>fe(t,!0)},{label:"Abrir el README en esa l\xEDnea",hacer:async()=>{let c=await aa(t,r,["--linea"]);if(!c.datos){g().falla(`telar: ${c.error??"no la encontr\xE9"}`);return}await g().abrirArchivo(c.datos.archivo,c.datos.linea)}},{label:"Marcar hecha",description:"[ ] \u2192 [x] en el README",hacer:async()=>{await g().aviso(`\xBFMarcar hecha? ${r.slice(0,90)}`,{modal:!0},"Marcar hecha")==="Marcar hecha"&&await n(await aa(t,r,["--hecho"]))}},{label:"Responsable\u2026",description:i?`ahora: ${i}`:"ahora: sin responsable",hacer:async()=>{let c=await Ha(r.slice(0,80),i,await this.personasConocidas(),Q.persona,!0);c&&await n(await aa(t,r,["--responsable",c]))}}],l=await g().elegir(s,{title:r.slice(0,100),placeHolder:"qu\xE9 hacer con este pendiente"});l&&await l.hacer()}async abrirAhora(){this.panel||this.abrir(),this.pantalla="ahora",this.datos||(this.datos=await qe()),this.renderAhora();let[a,t,r]=await Promise.all([this.plan?.dia===this.datos?.fecha?Promise.resolve(void 0):ea("plan",""),this.proyectos?Promise.resolve(void 0):we(),this.pendRepo?Promise.resolve(void 0):_t()]);a?.datos?.ok&&(this.plan=a.datos),t?.datos&&(this.proyectos=t.datos.proyectos),r?.datos&&(this.pendRepo=r.datos.pendientes),this.ahoraCtx.clear(),this.pantalla==="ahora"&&this.renderAhora()}diaAhora(){if(this.ahoraSim!==void 0&&this.ahoraDia)return{d:this.ahoraDia,plan:this.ahoraPlan};let a=this.datos,t=a&&this.plan?.dia===a.fecha&&this.plan.formato==="json"?this.plan.contenido:void 0;return{d:a,plan:t}}eventosAhora(){let{d:a,plan:t}=this.diaAhora();return a?Ja(a,t):[]}indiceAhora(a){let t=this.ahoraSel?a.findIndex(r=>r.id===this.ahoraSel):-1;return t>=0?t:Ti(a,this.ahoraSim??Date.now())}eventoAhora(){let a=this.eventosAhora();return a[this.indiceAhora(a)]}ahoraAlEvento(a){let t=this.eventosAhora().find(r=>r.id===a);t&&(this.ahoraSim=t.inicio+6e4,this.ahoraSel=t.id,this.ahoraElegir=!1,this.renderAhora())}async ahoraOtroDia(a){let t=new Date(this.ahoraSim??Date.now());t.setDate(t.getDate()+a);let r=new Date(t.getTime()-t.getTimezoneOffset()*6e4).toISOString().slice(0,16);await this.simularAhora(r)}async simularAhora(a){let t=Date.parse(a);if(Number.isNaN(t))return;this.ahoraSim=t,this.ahoraSel="",this.ahoraFijo=!1;let r=a.slice(0,10);if(r===this.datos?.fecha){this.ahoraDia=void 0,this.ahoraPlan=void 0,this.renderAhora();return}this.ahoraDiaCargando=!0,this.renderAhora();let[o,i]=await Promise.all([Tt(r),ea("plan",r)]);this.ahoraSim===t&&(this.ahoraDia=o,this.ahoraPlan=i.datos?.ok&&i.datos.formato==="json"?i.datos.contenido:void 0,this.ahoraDiaCargando=!1,this.pantalla==="ahora"&&this.renderAhora())}moverAhora(a){let t=this.eventosAhora(),r=this.eventoAhora(),o=Math.max(0,Math.min(t.length-1,t.findIndex(i=>i.id===r?.id)+a));this.ahoraSel=t[o]?.id??"",this.ahoraFijo=!0,this.renderAhora()}renderAhora(){let a=this.datos;if(!this.panel||!a)return;this.teclas.clear(),this.teclas.set("[",()=>this.moverAhora(-1)),this.teclas.set("]",()=>this.moverAhora(1)),!this.ahoraFijo&&this.ahoraSim===void 0&&(this.ahoraSel="");let t=this.eventosAhora(),r=t.length?this.indiceAhora(t):-1,o=r>=0?t[r]:void 0,{d:i,plan:n}=this.diaAhora(),s=new Date(this.ahoraSim??Date.now()),l=o?this.ahoraCtx.get(o.id):void 0;o&&!l&&this.ahoraCargando!==o.id&&this.cargarContexto(o,n);let c=ee(a);this.pintar(Mi({evs:t,i:r,ahora:this.ahoraSim??Date.now(),fijo:this.ahoraFijo,plan:n,contexto:l,cargando:!!o&&!l,simulado:this.ahoraSim!==void 0,cargandoDia:this.ahoraDiaCargando,elegir:this.ahoraElegir&&i?zt(i,t,o?.id??"",s,void 0,"ahora-evento"):void 0,fechaElegir:i?.fecha,urgentes:c.filter(u=>u.dias!==null&&u.dias<=0||!!u.fila.destacada),propuestas:c.filter(u=>u.avance&&u.fila.ficha),aviso:n?"":"sin plan para ese d\xEDa: se ve el calendario"}))}async cargarContexto(a,t){this.ahoraCargando=a.id;let r=Nt(a),o=a.plan??{},i={estado:"",pendientes:[],tareas:[]};try{let n=String(o.proyecto??"");if(!n&&r==="reunion"&&!a.soloPlan){let l=new Date(a.inicio).toTimeString().slice(0,5),c=await Sa(a.titulo,l,a.url,a.id,{asistentes:a.asistentes,preguntar:!0,donde:!0});c.datos?.destino&&c.datos.destino!=="gestion"?n=c.datos.destino:i.sinProyecto=c.datos?.candidatos?.length?`no s\xE9 de qu\xE9 proyecto es: quiz\xE1s ${c.datos.candidatos.slice(0,3).map(u=>u.nombre).join(", ")}`:"no s\xE9 de qu\xE9 proyecto es esta reuni\xF3n"}!n&&r!=="reunion"&&this.proyectos&&(n=zi(a.titulo,this.proyectos.filter(l=>!Ia(l)))),i.proyecto=this.proyectos?.find(l=>l.ruta===n);let s=new Set((o.tareas??[]).map(String));if(s.size&&this.datos&&(i.tareas=ee({...this.datos,pendientes:this.datos.pendientes.filter(l=>s.has(l.id))})),i.proyecto&&x.raiz){let l=z(x.raiz,i.proyecto.ruta);i.pendientes=this.pendientesDe(i.proyecto.ruta)??[];let c=await pe().leer(z(l,"README.md")),u=c!==void 0?Ji(c):"";if(u&&(i.estado=await this.markdown(u)),r==="reunion"){let h=await this.masReciente(l,b=>/preparaci[oó]n/i.test(b),a.titulo),p=h?await pe().leer(h):void 0;h&&p!==void 0&&(i.preparacion={ruta:Ka(x.raiz,h),html:await this.markdown(p.slice(0,12e3))});let f=new Map,m=await this.masReciente(l,(b,w)=>/minuta/i.test(b)||/\/reuniones\//.test(w)&&!/preparaci/i.test(b),a.titulo,async b=>{let w=await pe().leer(b)??"";return f.set(b,w),!!Ot(w)});m&&(i.minuta={ruta:Ka(x.raiz,m),html:await this.markdown(Ot(f.get(m)??""))})}}}catch{}this.ahoraCtx.set(a.id,i),this.ahoraCargando="",this.pantalla==="ahora"&&this.renderAhora()}async markdown(a){try{return await g().markdown(a)??""}catch{return d(a)}}async masReciente(a,t,r,o=async()=>!0){let i=(await pe().buscarMd(a,3)).filter(l=>t(Ya(l.ruta),l.ruta)),n=M(r).split(/\s+/).filter(l=>l.length>3),s=l=>n.some(c=>M(Ya(l)).includes(c));i.sort((l,c)=>Number(s(c.ruta))-Number(s(l.ruta))||c.mtime-l.mtime);for(let l of i)if(await o(l.ruta))return l.ruta;return""}async consolidarProyecto(a){let t=this.proyectos?.find(n=>n.ruta===a);if(!this.general){g().aviso("telar: no hay un agente general ([agentes] sin_proyecto) que lo haga");return}let r=this.pendientesDe(a)?.filter(n=>!n.fila.proveedor).length;if(await g().info(`\xBFConsolidar los pendientes de \xAB${t?.nombre??a}\xBB?`,{modal:!0,detail:`${this.general.nombre} revisa ${r??"cada"} pendiente${r===1?"":"s"} abierto${r===1?"":"s"} del README, busca si ya se hizo y marca lo hecho con su prueba. Lo dudoso te lo pregunta.`},"Consolidar")!=="Consolidar")return;let i=await g().progreso({title:`telar: encarg\xE1ndoselo a ${this.general.nombre}\u2026`},()=>Ee(this.general.clave,`/consolidar ${a}`));if(!i.datos){g().falla(`telar: no lleg\xF3 a ${this.general.nombre}: ${i.error??"sin respuesta"}`);return}g().estado(`telar: ${this.general.nombre} consolida ${t?.nombre??a} (${i.datos.estado??""})`,8e3)}async menuProyecto(a){let t=this.proyectos?.find(n=>n.ruta===a);if(!t)return;let r=x.raiz?z(x.raiz,a):"",o=[{label:t.vivo?"Ir a su hilo":t.hilo?"Retomar su hilo":"Abrir con el agente",description:t.hilo?`\xAB${t.hilo}\xBB`:"un hilo nuevo cargando el proyecto",hacer:()=>this.abrirProyecto(a)}];this.general&&(o.push({label:"Consolidar sus pendientes",description:`${this.general.nombre} marca lo hecho con su prueba (/consolidar)`,hacer:()=>this.consolidarProyecto(a)}),o.push({label:`Escribirle a ${this.general.nombre} sobre este proyecto\u2026`,description:"le llega con el proyecto y lo pendiente",hacer:()=>this.escribirSobreProyecto(t)})),r&&o.push({label:"Abrir el README",description:`${a}/README.md`,hacer:()=>$e(z(r,"README.md"))},{label:"Mostrar la carpeta en el explorador",hacer:()=>g().mostrarCarpeta(r)}),o.push({label:"Copiar la ruta",description:a,hacer:async()=>{await g().copiar(a),g().estado(`telar: copiado ${a}`,3e3)}}),t.hilo&&o.push({label:"Archivar su hilo",description:`cierra \xAB${t.hilo}\xBB y lo guarda; \u25B6 lo retoma`,hacer:async()=>{if(await g().aviso(`\xBFArchivar \xAB${t.hilo}\xBB? Se cierra su ventana; su conversaci\xF3n queda para retomarla.`,{modal:!0},"Archivar")!=="Archivar")return;let s=await Pe("archivar",t.hilo,void 0,["--cerrar"]);s.ok||g().falla(`telar: ${s.err.trim()||"no pude archivarlo"}`),await this.abrirProyectos()}});let i=await g().elegir(o,{title:t.nombre,placeHolder:"qu\xE9 hacer con este proyecto"});i&&await i.hacer()}async escribirSobreProyecto(a){if(!this.general)return;let t=await g().campo({title:`A ${this.general.nombre} \xB7 ${a.nombre}`,prompt:"qu\xE9 hacer con este proyecto",ignoreFocusOut:!0});if(!t?.trim())return;let r=this.pendientesDe(a.ruta)??[],o=[`[Nico, desde los proyectos del dashboard] ${t.trim()}`,"",`Contexto. El proyecto: \xAB${a.nombre}\xBB (${a.arquetipo}${a.estado_completo?`, estado: ${a.estado_completo}`:""}), en ${a.ruta}; su README es ${a.ruta}/README.md.`,a.hilo?`Tiene un hilo: \xAB${a.hilo}\xBB${a.vivo?" (abierto)":" (dormido)"}; si el trabajo es suyo, p\xE1saselo con telar mensaje.`:"No tiene hilo abierto.",r.length?`Pendiente: ${r.slice(0,12).map(n=>`${n.fila.proveedor?`${n.ref} `:""}${n.texto}`).join(" | ")}`:""].filter(Boolean),i=await g().progreso({title:`telar: escribi\xE9ndole a ${this.general.nombre}\u2026`},()=>Ee(this.general.clave,o.join(`
`)));if(!i.datos){g().falla(`telar: no lleg\xF3 a ${this.general.nombre}: ${i.error??"sin respuesta"}`);return}g().estado(`telar: enviado a ${this.general.nombre} (${i.datos.estado??""})`,6e3)}async enlaceReadme(a,t){if(/^[a-z][a-z0-9+.-]*:/i.test(a)){await g().abrirExterno(a);return}if(!x.raiz||a.startsWith("#"))return;let r=ne(z(x.raiz,t,decodeURIComponent(a.split("#")[0])));r.startsWith(x.raiz)&&await $e(r)}renderProyectos(a=""){if(!this.panel)return;this.teclas.clear();let t=(this.proyectos??[]).filter(o=>!Ia(o)),r=[`<div class="subcab"><b>Proyectos</b><span class="dim">${t.length||""}</span></div>`];if(this.avisoProyectos&&r.push(`<div class="fila falla">${d(this.avisoProyectos)}</div>`),a){r.push(`<div class="fila dim">${d(a)}</div>`),this.pintar(r);return}r.push('<div class="proy-dos"><div class="proy-lista">',...qi(t,this.proySel,this.cuentasPendientes()),`</div><div id="proy-det">${Lt(this.proySel?this.proyDet:void 0)}</div></div>`),this.pintar(r)}async abrirProyecto(a){let t=await qo(a);if(!t.datos){g().aviso(`telar: ${t.error??"no pude abrir el proyecto"}`);return}await x.sondear(),await g().mostrarTerminal()}async cambiarPlantillaProyecto(a){let t="";if(!a){let o=this.agenteConfig?.proyecto??"",i=await g().campo({title:"Qu\xE9 decirle al agente al abrir un proyecto",prompt:"Marcadores: {nombre} {ruta} {carpeta} {documento}. Una skill (/nombre \u2026) o una instrucci\xF3n en prosa.",value:o,ignoreFocusOut:!0});if(i===void 0||i.trim()===o)return;t=i.trim()}let r=await Go(t);r.ok||(this.avisoConfig=r.err.trim().split(`
`).pop()||"no pude guardar el mensaje"),await this.abrirConfig()}async abrirConfig(){this.pantalla="config",this.avisoConfig="",this.renderConfig("leyendo la configuraci\xF3n\u2026");let a=await oe();this.calendario=a.datos?.calendario,this.agenteConfig=a.datos?.agente,this.hilosConfig=a.datos?.hilos,a.datos||(this.avisoConfig=a.error??"telar config no contest\xF3"),this.renderConfig()}async elegirCalendario(a){if(a==="ics")await g().orden("telar.conectarCalendario");else{let t=await Vo(a);if(!t.ok){this.avisoConfig=t.err.trim().split(`
`).pop()||"no pude cambiar el calendario",this.renderConfig();return}}U(),await this.abrirConfig(),await this.actualizar(!0),this.renderConfig()}async cambiarDirectorios(){let a=(this.hilosConfig?.directorios??[]).join(", "),t=await g().campo({title:"De qu\xE9 carpetas salen los hilos",prompt:"Relativas a la ra\xEDz del repositorio, separadas por coma, en el orden en que se abren. Vac\xEDo: las unidades del perfil.",placeHolder:"operacion/proyectos, negocio/pipeline",value:a,ignoreFocusOut:!0});if(t===void 0||t.trim()===a)return;let r=await Zo(t.trim());if(!r.ok){this.avisoConfig=r.err.trim().split(`
`).pop()||"no pude guardar las carpetas",await this.abrirConfig();return}if(await this.abrirConfig(),await g().info("Carpetas guardadas. \xBFAbrir ahora los hilos que falten? Cada uno arranca su agente.","Abrir ahora")==="Abrir ahora"){let i=await Fa(!0);i.ok||g().aviso(`telar: ${i.err.trim().split(`
`).pop()??"no pude abrirlos"}`),await x.sondear()}}async cambiarPlantilla(a){let t="";if(!a){let o=this.agenteConfig?.reunion??"",i=await g().campo({title:"Qu\xE9 decirle al agente al preparar una reuni\xF3n",prompt:"Marcadores: {titulo} {hora} {fecha} {enlace} {proyecto}. Una skill (/nombre \u2026) o una instrucci\xF3n en prosa.",value:o,ignoreFocusOut:!0});if(i===void 0||i.trim()===o)return;t=i.trim()}let r=await Xo(t);r.ok||(this.avisoConfig=r.err.trim().split(`
`).pop()||"no pude guardar el mensaje"),await this.abrirConfig()}htmlPestanasConfig(){let a=this.todasLasPestanas(),t=o=>{let i=this.dashOrden.indexOf(o);return i<0?this.dashOrden.length+a.findIndex(n=>n[0]===o):i},r=["<h2>Pesta\xF1as<small>cu\xE1les se ven y en qu\xE9 orden; las de un m\xF3dulo nuevo aparecen solas</small></h2>"];[...a].sort((o,i)=>t(o[0])-t(i[0])).forEach(([o,,,i])=>{let n=!this.dashOcultas.includes(o),s=o.startsWith("bloque:")&&this.modulosCfg?.some(l=>l.nombre===o.slice(7))?' <span class="dim">\xB7 m\xF3dulo</span>':"";r.push(`<div class="fila${n?"":" dim"}"><a data-accion="pest-ver" data-valor="${d(o)}" title="${n?"ocultarla":"mostrarla"}">${n?"\u2713":"\xB7"}</a> ${d(i.replace(/ ◆\d+$/,""))}${s}<span class="der"><a data-accion="pest-subir" data-valor="${d(o)}" title="un lugar antes">\u2191</a> <a data-accion="pest-bajar" data-valor="${d(o)}" title="un lugar despu\xE9s">\u2193</a></span></div>`)}),r.push('<div class="fila dim">\u2699 va siempre al final.</div>'),r.push("<h2>M\xF3dulos<small>una carpeta con modulo.toml; se instalan en <code>[modulos]</code> de la configuraci\xF3n</small></h2>"),this.modulosCfg?.length||r.push('<div class="fila dim">ninguno instalado</div>');for(let o of this.modulosCfg??[])r.push(`<div class="fila"><b>${d(o.nombre)}</b>&nbsp;<span class="dim">${d(o.descripcion)}</span></div><div class="fila dim">aporta ${d(o.aporta.join(", ")||"nada")} \xB7 ${d(o.carpeta)}</div>`);return r}renderConfig(a=""){if(!this.panel)return;this.teclas.clear();let t=['<div class="subcab"><b>Configuraci\xF3n</b></div>'];if(a){t.push(`<div class="fila dim">${d(a)}</div>`),this.pintar(t);return}this.avisoConfig&&t.push(`<div class="fila falla">${d(this.avisoConfig)}</div>`),t.push(...this.htmlPestanasConfig());let r=this.calendario;if(t.push("<h2>Calendario<small>de d\xF3nde sale la agenda</small></h2>"),!r){this.pintar(t);return}let o=this.datos?.fallas.find(u=>u.startsWith("calendario")),i=r.tipo==="ninguno"?"sin conectar":o?`no responde (${o.split(": ").pop()})`:this.datos?.agenda?"funcionando":"todav\xEDa sin consultar",n={gws:"Google Workspace (gws)",ics:"iCal",comando:"un comando",ninguno:"ninguno"};t.push(`<div class="fila">En uso: <b>${d(n[r.tipo]??r.tipo)}</b> \xB7 <span class="${o?"falla":"dim"}">${d(i)}</span></div>`);let s=(u,h,p,f)=>{let m=r.tipo===u;t.push(`<div class="opcion${m?" activa":""}"><div class="fila"><b>${m?"\u25CF":"\u25CB"} ${h}</b>`+(m&&u!=="ics"?"":` <span class="der"><a data-accion="calendario" data-valor="${u}">${p}</a></span>`)+"</div>"+f.map(b=>`<div class="fila dim">${b}</div>`).join("")+"</div>")};s("gws","Google Workspace (gws)","usar",["Lee tu calendario con la CLI <code>gws</code>, con la cuenta que ya tenga conectada. No hay direcci\xF3n que pegar ni secreto que guardar, y sirve aunque el administrador del dominio haya desactivado iCal.",r.gws?r.gws_conectado?`Conectado como <b>${d(r.gws_cuenta||"una cuenta")}</b>.`:"Instalado pero sin sesi\xF3n: corre <code>gws auth login</code> en un terminal.":"No est\xE1 instalado en esta m\xE1quina."]),s("ics","iCal",r.tipo==="ics"?"cambiar direcci\xF3n\u2026":"usar\u2026",["Una direcci\xF3n de calendario en formato .ics. En Google Calendar: Configuraci\xF3n \u203A tu calendario \u203A \xABDirecci\xF3n <b>secreta</b> en formato iCal\xBB.",...r.tipo==="ics"&&r.fuente?[`Guardada: <code>${d(r.fuente)}</code> (la parte secreta no se muestra).`]:[],...r.tipo==="ics"&&r.publica?['<span class="falla">Es la direcci\xF3n <b>p\xFAblica</b>: solo funciona si el calendario est\xE1 publicado para todo internet. Usa la secreta.</span>']:[]]),s("ninguno","Ninguno","desconectar",["El dashboard no muestra agenda."]);let l=this.hilosConfig;l&&(t.push("<h2>Hilos<small>de qu\xE9 carpetas salen los de la lista</small></h2>"),t.push('<div class="fila">'+(l.directorios.length?l.directorios.map(u=>`<code>${d(u)}</code>`).join(" \xB7 "):"las unidades del perfil, en su orden")+'<span class="der"><a data-accion="directorios">cambiar\u2026</a></span></div>'),t.push(`<div class="fila dim">Al tejer la sesi\xF3n se abren hasta ${l.tope}, repartidos por turnos: uno de cada carpeta. Los archivados no se reabren solos: \u23F8 en la lista archiva uno y guarda su conversaci\xF3n, \u25B6 lo retoma.</div>`));let c=this.agenteConfig;if(c){let u=c.reunion!==c.reunion_por_defecto;t.push("<h2>Reuniones<small>qu\xE9 se le dice al agente al pinchar una reuni\xF3n</small></h2>"),t.push(`<div class="fila"><code>${d(c.reunion)}</code><span class="der"><a data-accion="plantilla" data-valor="cambiar">cambiar\u2026</a>`+(u?' \xB7 <a data-accion="plantilla" data-valor="restablecer">volver a la de flow</a>':"")+"</span></div>"),t.push(`<div class="fila dim">Se abre un tab \xAB\u25F7 hora reuni\xF3n\xBB con <b>${d(c.nombre||"ning\xFAn agente")}</b> y se le escribe esto. Marcadores: <code>{titulo}</code> <code>{hora}</code> <code>{fecha}</code> <code>{enlace}</code> <code>{proyecto}</code>. El proyecto es la carpeta que comparte palabras con el t\xEDtulo; si no hay, la cola \xAB\xB7 proyecto:\xBB se quita.</div>`),u||t.push('<div class="fila dim">Es la de flow: supone la skill <code>/preparar-reunion</code> instalada en Claude Code.</div>');let h=c.proyecto!==c.proyecto_por_defecto;t.push("<h2>Proyectos<small>qu\xE9 se le dice al agente al abrir un proyecto de la lista</small></h2>"),t.push(`<div class="fila"><code>${d(c.proyecto)}</code><span class="der"><a data-accion="plantilla-proyecto" data-valor="cambiar">cambiar\u2026</a>`+(h?' \xB7 <a data-accion="plantilla-proyecto" data-valor="restablecer">volver a la de f\xE1brica</a>':"")+"</span></div>"),t.push('<div class="fila dim">Se abre un tab con el nombre de la carpeta, vinculado a ella, y se le escribe esto. Marcadores: <code>{nombre}</code> <code>{ruta}</code> <code>{carpeta}</code> <code>{documento}</code>.</div>')}this.pintar(t)}pintar(a){this.panel?.enviar({tipo:"dia",html:this.nav()+a.join(`
`)})}guardarLienzo(a,t){let r=this.memorias.get(a);if(!(!r||t.length>4e6)){try{JSON.parse(t)}catch{return}pe().escribir(r,t).then(o=>{o&&this.lienzos.set(r,t)})}}async mensaje(a){if(a.tipo==="lienzo-guardar"){this.guardarLienzo(a.valor??"",a.datos??"");return}if(a.tipo==="per-horario"){await this.previaHorario(a.valor??"");return}if(a.tipo==="per-skills"){await this.cargarSkills(a.valor??"");return}if(a.tipo==="listo"){this.pantalla==="seccion"&&this.pagina&&this.renderSeccion(),this.pantalla==="ahora"&&this.abrirAhora(),this.render(),this.actualizar();return}if(a.tipo==="url"&&a.url&&/^https:\/\//.test(a.url)){await g().abrirExterno(a.url);return}if(a.tipo==="tecla"&&a.k){let t={p:()=>this.abrirProyectos(),r:()=>this.actualizar(!0),v:()=>this.abrirRevisar(),o:()=>this.abrirPeriodicos(),d:()=>this.abrirPlan(""),a:()=>this.abrirCalendario(),n:()=>this.abrirAhora(),...Object.fromEntries(this.pestanasCfg.filter(r=>r.tecla).map(r=>[r.tecla,()=>this.abrirPestana(r.nombre)])),...Object.fromEntries(this.bloquesCfg.filter(r=>!r.en&&r.tecla).map(r=>[r.tecla,()=>this.abrirBloque(r.clave)])),t:()=>Promise.resolve(g().orden("telar.tareas")),...x.hayRemotos?{c:()=>this.abrirCorreo()}:{},...Object.fromEntries(this.atajos.map(r=>[r.tecla,()=>this.lanzarAtajo(r.tecla)]))};await(this.teclas.get(a.k)??t[a.k])?.();return}if(a.tipo==="accion")switch(a.accion){case"pendiente":a.valor&&await fe(a.valor,!!a.nuevo);break;case"ir":a.valor&&await g().irAHilo(a.valor);break;case"refrescar":await this.actualizar(!0);break;case"volver":g().mostrarTerminal();break;case"reunion":{let[t,r,o,i,n]=JSON.parse(a.valor??"[]");t&&r&&await this.preparar(t,r,o??"",i??"",n??[]);break}case"config":await this.abrirConfig();break;case"proyectos":await this.abrirProyectos();break;case"seccion":a.valor&&await this.abrirSeccion(a.valor);break;case"proyecto":a.valor&&await this.abrirProyecto(a.valor);break;case"proy-sel":a.valor&&await this.verProyecto(a.valor);break;case"ahora":await this.abrirAhora();break;case"ahora-mover":this.moverAhora(Number(a.valor)||0);break;case"ahora-fijar":this.ahoraFijo=!0,this.ahoraSel=this.eventoAhora()?.id??"",this.renderAhora();break;case"ahora-soltar":this.ahoraFijo=!1,this.ahoraSel="",this.ahoraSim=void 0,this.ahoraDia=void 0,this.ahoraPlan=void 0,this.ahoraElegir=!1,this.renderAhora();break;case"ahora-elegir":this.ahoraElegir=!this.ahoraElegir,this.renderAhora();break;case"ahora-evento":a.valor&&this.ahoraAlEvento(a.valor);break;case"ahora-dia":a.valor&&await this.ahoraOtroDia(Number(a.valor)||0);break;case"equipo-tarea":a.valor&&await Hi(a.valor)&&(await this.actualizar(!0),this.pantalla==="revisar"&&this.renderRevisar());break;case"estrella-tarea":a.valor&&await Oi(a.valor)&&(await this.actualizar(!0),this.pantalla==="revisar"&&this.renderRevisar());break;case"dueno-tarea":if(a.valor){let[t,r,o,i]=JSON.parse(a.valor);await Li(JSON.stringify([t,r,o]),i??"",Q.persona)&&(await this.actualizar(!0),this.pantalla==="revisar"&&this.renderRevisar())}break;case"proy-ir":a.valor&&(this.proySel=a.valor,await this.abrirProyectos());break;case"proy-menu":a.valor&&await this.menuProyecto(a.valor);break;case"menu-vineta":a.valor&&await this.menuVineta(a.valor);break;case"proy-consolidar":a.valor&&await this.consolidarProyecto(a.valor);break;case"proy-enlace":a.valor&&await this.enlaceReadme(a.valor,String(a.datos??""));break;case"plantilla-proyecto":await this.cambiarPlantillaProyecto(a.valor==="restablecer");break;case"bloque":a.valor&&await this.abrirBloque(a.valor);break;case"pest-ver":case"pest-subir":case"pest-bajar":a.valor&&await this.cambiarPestanas(a.accion.slice(5),a.valor);break;case"atajo":a.valor&&await this.lanzarAtajo(a.valor);break;case"abrir-item":a.valor&&await this.abrirItem(a.valor);break;case"ver-item":if(a.valor){let t=a.valor.lastIndexOf(":");await this.abrirBloque(a.valor.slice(0,t),Number(a.valor.slice(t+1)))}break;case"item-volver":await this.abrirBloque(this.bloqueSel);break;case"solo-pendientes":a.valor&&(this.soloPendientes.has(a.valor)?this.soloPendientes.delete(a.valor):this.soloPendientes.add(a.valor),this.render());break;case"cuerpo-alternar":a.valor&&(this.cuerposAbiertos.has(a.valor)?this.cuerposAbiertos.delete(a.valor):this.cuerposAbiertos.add(a.valor),this.render());break;case"item-enlace":if(a.valor){let t=a.valor.lastIndexOf(":"),r=(this.bloquesDatos.get(a.valor.slice(0,t))?.pagina?.bloques??[]).flatMap(o=>o.items??[])[Number(a.valor.slice(t+1))];r?.enlace&&await $e(r.enlace,r.reusar)}break;case"grupo-item":a.valor&&(this.gruposAbiertos.has(a.valor)?this.gruposAbiertos.delete(a.valor):this.gruposAbiertos.add(a.valor),this.render());break;case"tarea":if(!a.valor)break;if(a.nuevo){let[t,,r]=JSON.parse(a.valor);await fe(r,!1,t)}else await this.abrirTarea(a.valor);break;case"accion-tarea":a.valor&&await this.accionTarea(Number(a.valor));break;case"hecha-fila":a.valor&&(await Ht(a.valor)&&this.decididas.add(JSON.parse(a.valor)[1]),this.render(),this.actualizar(!0),g().orden("telar.tareasActualizar"));break;case"hecha-vineta":if(a.valor){let[t,r]=JSON.parse(a.valor),o=await aa(t,r,["--hecho"]);o.datos?(g().estado(`\u2713 ${r.slice(0,60)}`,5e3),U(),this.actualizar(!0)):g().aviso(`telar: ${o.error??"no pude marcarla"}`)}break;case"hilo-fila":if(a.valor){let[t,r,o]=JSON.parse(a.valor);await fe(r,!1,t,o?`/tarea ${o}`:"",!!o)}break;case"hecha":if(!a.valor)break;await Ht(a.valor),this.actualizar(!0),g().orden("telar.tareasActualizar");break;case"tarea-principal":{let t=(this.ficha?.pagina?.acciones??[]).findIndex(r=>r.principal);t>=0&&await this.accionTarea(t);break}case"tarea-siguiente":await this.otraPropuesta(1);break;case"revisar":await this.abrirRevisar();break;case"periodicos":this.periodico=void 0,this.formPer=void 0,await this.abrirPeriodicos();break;case"per-ver":a.valor&&await this.verPeriodico(a.valor);break;case"per-nuevo":await this.nuevoPeriodico();break;case"per-editar":a.valor&&await this.editarPeriodico(a.valor);break;case"per-guardar":a.valor&&await this.guardarFormPer(a.valor);break;case"per-cancelar":this.formPer=void 0,this.renderPeriodicos();break;case"per-orden":a.valor&&await this.ordenPeriodico(JSON.parse(a.valor));break;case"pestana":a.valor&&await this.abrirPestana(a.valor);break;case"volver-ficha":if(this.fichaDesde==="revisar")await this.abrirRevisar();else if(this.fichaDesde.startsWith("pestana:"))await this.abrirPestana(this.fichaDesde.slice(8));else if(this.fichaDesde.startsWith("bloque:")){let[,t,r]=this.fichaDesde.split(":");await this.abrirBloque(t,r===""?void 0:Number(r))}else await this.abrirAhora();break;case"tarea-anterior":await this.otraPropuesta(-1);break;case"abrir-enlace":a.valor&&await $e(a.valor);break;case"abrir-ruta":a.valor&&!a.valor.includes("..")&&x.raiz&&await $e(z(x.raiz,a.valor));break;case"tareas":await g().orden("telar.tareas");break;case"recargar-seccion":this.pagina=void 0,this.seccion&&await this.abrirSeccion(this.seccion);break;case"volver-seccion":this.seccion&&this.pagina?(this.pantalla="seccion",this.renderSeccion()):await this.abrirAhora();break;case"conversacion":a.valor&&await this.abrirConversacion(a.valor);break;case"correo":await this.abrirCorreo();break;case"equipo-accion":a.valor&&await this.accionEquipo(a.valor);break;case"ver-msg":a.valor&&(this.abiertoMsg.has(a.valor)?this.abiertoMsg.delete(a.valor):this.abiertoMsg.add(a.valor),this.renderCorreo());break;case"soltar-msg":a.valor&&await this.soltarMensaje(a.valor);break;case"retomar-charla":if(this.charla?.hilo){let t=x.porNombre(this.charla.hilo)?.vivo;await g().orden(t?"telar.ir":"telar.retomar",{hilo:this.charla.hilo})}break;case"calendario":this.pantalla==="config"?await this.elegirCalendario(a.valor??""):await this.abrirCalendario();break;case"plan":await this.abrirPlan("");break;case"plan-dia":await this.abrirPlan(a.valor??"");break;case"evento-sel":a.valor&&(this.eventoSel=a.valor,this.renderCalendario());break;case"cal-dia":a.valor&&await this.moverDiaCal(a.valor);break;case"nota-evento":a.valor&&await this.notaEvento(a.valor);break;case"menu-tarea":a.valor&&await this.menuTarea(a.valor);break;case"reagendar":a.valor&&await Bi(a.valor)&&(await this.actualizar(!0),this.pantalla==="revisar"&&this.renderRevisar());break;case"ev-escribir":a.valor&&await this.escribirSobreEvento(a.valor,a.datos??"");break;case"plan-comentar":a.valor&&a.datos?.trim()&&await this.comentarPlan(a.valor,a.datos);break;case"plantilla":await this.cambiarPlantilla(a.valor==="restablecer");break;case"directorios":await this.cambiarDirectorios();break}}};function Ua(e){let a=r=>d(r).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g,"$1<i>$2</i>").replace(/`([^`]+)`/g,"<code>$1</code>"),t=r=>/^\s*[-*] /.test(r);return e.trim().split(/\n\s*\n/).map(r=>{let o=[],i=[],n=[],s=()=>{i.length&&o.push(`<p>${i.map(a).join(" ")}</p>`),n.length&&o.push("<ul>"+n.map(l=>`<li>${a(l.replace(/^\s*[-*] /,""))}</li>`).join("")+"</ul>"),i=[],n=[]};for(let l of r.split(`
`))t(l)?(i.length&&s(),n.push(l)):n.length&&/^\s+\S/.test(l)?n[n.length-1]+=" "+l.trim():(n.length&&s(),i.push(l));return s(),o.join("")}).join("")}function fc(e){let a=Date.parse(e);return Number.isNaN(a)?"":new Date(a).toTimeString().slice(0,5)}function Ut(e){let a=Date.parse(e);if(Number.isNaN(a))return e;let t=new Date(a),r=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];return`${t.getDate()}-${r[t.getMonth()]} ${t.toTimeString().slice(0,5)}`}function mc(e,a){let t=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],[,r,o]=a.split("-").map(Number);return`${e.slice(0,3)} ${o||""} ${t[(r||1)-1]}`.trim()}async function $e(e,a=""){if(/^https?:\/\//.test(e)){if(a&&await yc(e,a))return;await g().abrirExterno(e);return}if(e.startsWith("/")){await g().abrirArchivo(e);return}g().aviso(`telar: no s\xE9 abrir ${e}`)}function Ui(e){return e.ultima.corriendo?["\u25D0","azul","corriendo ahora"]:e.activo?e.ultima.codigo!==void 0&&e.ultima.codigo!==0?["\u2717","rojo",`la \xFAltima vez: ${e.ultima.resultado??"fall\xF3"}`]:e.ultima.inicio?["\u25CF","verde",`la \xFAltima vez: ${e.ultima.resultado??"bien"}`]:["\u25CB","dim","todav\xEDa no ha corrido"]:["\u23F8","dim","pausado: no corre hasta que lo actives"]}function Wt(e){let a=Math.max(0,Math.round((Date.parse(e)-Date.now())/6e4));return a<60?`${a} min`:a<1440?`${Math.floor(a/60)} h${a%60?` ${a%60}`:""}`:`${Math.round(a/1440)} d`}function vc(e){let a=new Date(e);return`${["dom","lun","mar","mi\xE9","jue","vie","s\xE1b"][a.getDay()]} ${a.getDate()} ${e.slice(11,16)}`}function Wi(e){try{return new URL(e).origin}catch{return""}}function gc(){return[...new Set(x.apps.map(e=>e.url?Wi(e.url):"").filter(Boolean))]}function Zi(e){return e==="lleno"?"":` style="height:${Math.round(e??240)}px"`}function bc(e){return`<iframe class="lienzo${e.alto==="lleno"?" lleno":""}" src="${d(e.url)}" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"${Zi(e.alto)}></iframe>`}async function yc(e,a){if(process.platform!=="darwin")return!1;let t=["on run argv","  set destino to item 1 of argv","  set clave to item 2 of argv",'  if application "Google Chrome" is not running then return "no"','  tell application "Google Chrome"',"    repeat with w in windows","      set i to 0","      repeat with t in tabs of w","        set i to i + 1","        if (title of t contains clave) or (URL of t contains clave) then","          set URL of t to destino","          set active tab index of w to i","          set index of w to 1","          activate",'          return "si"',"        end if","      end repeat","    end repeat","  end tell",'  return "no"',"end run"].join(`
`);return new Promise(r=>{_a("osascript",["-e",t,e,a],{timeout:8e3},(o,i)=>r(!o&&i.trim()==="si"))})}function wc(e){let a=new Date,t=`${a.getFullYear()}-${String(a.getMonth()+1).padStart(2,"0")}-${String(a.getDate()).padStart(2,"0")}`;if(!e||e.slice(0,10)===t)return e.slice(11,16);let[,r,o]=e.slice(0,10).split("-").map(Number);return`${o} ${["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"][(r||1)-1]}`}var rp=B("web"),xc=String.raw`
  // la página que contiene al dashboard (src/navegador) le habla por postMessage
  var abierto = false, cola = [];
  function conectar() {
    window.addEventListener('message', function (e) {
      if (e.source !== window.parent || !e.data || !e.data.__telarPadre) return;
      llega(e.data.__telarPadre);
    });
    abierto = true; medir();
  }
  function enviar(s) { window.parent.postMessage({ __telarHijo: s }, location.origin === 'null' ? '*' : location.origin); }`;function $c(e){return String.raw`
(function () {`+e+String.raw`
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
`}var Xi=$c(xc),ke=e=>e.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");function Gi(e,a){let t=(o,i,n="")=>`<a class="${n}" href="/documento?hilo=${encodeURIComponent(a.hilo)}&amp;archivo=${encodeURIComponent(o)}">${ke(i)}</a>`,r=a.error?`<p class="nada">${ke(a.error)}</p>`:`<nav class="carpeta"><div class="donde">${ke(a.carpeta??".")}</div>`+(a.subir!==void 0?t(a.subir,"../","dir"):"")+(a.archivos??[]).map(o=>t(o.ruta,o.nombre,`${o.nombre.endsWith("/")?"dir":""}${o.ruta===a.archivo?" sel":""}`)).join("")+"</nav>"+(a.archivo?`<article><div class="donde">${ke(a.archivo)}</div>${a.html?`<div class="md">${a.html}</div>`:`<pre>${ke(a.texto??"")}</pre>`}</article>`:"");return`<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:;">
<title>${ke(a.titulo)} \xB7 telar</title>
<style>@layer base, vistas;
${De()}
@layer vistas { ${B("documento")} }</style>
</head><body><h1>${ke(a.titulo)}</h1>${r}</body></html>`}function Vi(e,a={}){return`<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${e}'; connect-src 'self';">
<title>compartir \xB7 telar</title>
<style>@layer base, vistas;
${De()}
@layer vistas { ${B("compartir")} }</style>
</head><body>
<header><a href="/" target="_top">\u25C0 telar</a><b>compartir</b></header>
<main>
  <section id="que"></section>
  <textarea id="nota" rows="3" placeholder="una nota, si quieres (va con lo compartido)"></textarea>
  <input id="filtro" placeholder="filtrar destinos" autocomplete="off">
  <div id="destinos"><p class="dim">leyendo destinos\u2026</p></div>
  <p id="dicho" class="dim"></p>
</main>
<script nonce="${e}">
(function () {
  // en el navegador (un iframe srcdoc) lo compartido llega por par\xE1metro: la direcci\xF3n es la de la p\xE1gina de arriba
  var R = ${JSON.stringify(a).replace(/</g,"\\u003c")};
  var q = new URLSearchParams(R.consulta != null ? R.consulta : location.search);
  var titulo = (q.get('title') || '').trim(), texto = (q.get('text') || '').trim(), url = (q.get('url') || '').trim();
  // muchas apps mandan el enlace dentro del texto, no en url
  if (!url) { var m = texto.match(/https?:\\/\\/\\S+/); if (m) { url = m[0]; texto = texto.replace(m[0], '').trim(); } }
  function el(tag, cls, t) { var e = document.createElement(tag); if (cls) e.className = cls; if (t != null) e.textContent = t; return e; }
  var que = document.getElementById('que');
  if (titulo) que.appendChild(el('div', 'titulo', titulo));
  if (url) que.appendChild(el('div', 'url', url));
  if (texto) que.appendChild(el('div', 'texto', texto));
  if (!titulo && !url && !texto) que.appendChild(el('div', 'dim', 'nada compartido: escribe una nota y elige a d\xF3nde'));
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
    b.disabled = true; dicho.className = 'dim'; dicho.textContent = 'llevando a ' + d.nombre + '\u2026';
    fetch('/api/compartir', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ a: d.destino, url: url, titulo: titulo, texto: [nota, texto].filter(Boolean).join('\\n') }) })
      .then(function (r) { return r.json(); })
      .then(function (r) { dicho.className = r.ok ? 'bien' : 'mal'; dicho.textContent = r.ok ? (r.dicho || 'listo') : (r.error || 'no sali\xF3'); })
      .catch(function () { dicho.className = 'mal'; dicho.textContent = 'sin conexi\xF3n con telar'; })
      .then(function () { b.disabled = false; });
  }
  filtro.addEventListener('input', pintar);
  // los proveedores que reciben, y los hilos (de esta m\xE1quina y de las otras)
  var hilos = fetch('/api/hilos?ficha=false&red=true', { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(function (d) { return (d.hilos || []).filter(function (h) { return !h.archivado; })
      .map(function (h) { return { destino: 'hilo:' + h.nombre, nombre: h.nombre, tipo: 'hilo' }; }); })
    .catch(function () { return []; });
  fetch('/api/compartir/destinos', { credentials: 'same-origin' }).then(function (r) { return r.json(); })
    .then(function (d) { return hilos.then(function (hs) { lista = (d.destinos || []).concat(hs); pintar(); }); })
    .catch(function () { document.getElementById('destinos').textContent = 'no pude leer los destinos'; });
})();
<\/script></body></html>`}function Yi(e,a={}){return`<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${e}'; connect-src 'self';">
<style>@layer base, vistas;
${De()}
@layer vistas { ${B("conversacion")} }</style>
</head><body>
<main id="turnos"><p class="nada">leyendo\u2026</p></main>
<footer>
  <div id="teclas">
    <button data-t="\\r">\u23CE</button><button data-t="\\u001b">\u238B</button><button data-t="1">1</button><button data-t="2">2</button><button data-t="3">3</button><button data-t="\\u001b[A">\u2191</button><button data-t="\\u001b[B">\u2193</button>
  </div>
  <form id="escribir"><textarea id="texto" rows="2" placeholder="escr\xEDbele al hilo (\u23CE env\xEDa, \u21E7\u23CE l\xEDnea nueva)"></textarea><button type="submit">enviar</button></form>
  <p id="dijo" class="nada"></p>
</footer>
<script nonce="${e}">
(function () {
  var q = new URLSearchParams(location.search), R = ${JSON.stringify(a).replace(/</g,"\\u003c")};
  var hilo = R.hilo || q.get('hilo') || '', maquina = R.maquina || q.get('maquina') || '';
  // un hilo de otra m\xE1quina se lee por la API y se le escribe como mensaje (por el bus); uno de aqu\xED, por su terminal
  var porMensaje = !!maquina;
  var turnos = document.getElementById('turnos'), texto = document.getElementById('texto'), dijo = document.getElementById('dijo');
  // un hilo de otra m\xE1quina se lee y se le escribe por el bus: sin terminal, no hay teclas que apretar
  if (porMensaje) { document.getElementById('teclas').hidden = true; texto.placeholder = (maquina ? 'escr\xEDbele al hilo (en ' + maquina + ', por el bus' : 'escr\xEDbele al hilo (le llega como mensaje') + '; \u23CE env\xEDa, \u21E7\u23CE l\xEDnea nueva)'; }
  var QUIEN = { usuario: 't\xFA', agente: 'agente', herramienta: '\xB7' };
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
      if (!(d.turnos || []).length) turnos.appendChild(el('p', 'nada', 'todav\xEDa no hay conversaci\xF3n'));
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
      .then(function (r) { return r.json().then(function (d) { return r.ok ? d : { error: d.detail || ('la API respondi\xF3 ' + r.status) }; }); })
      .then(pintar)
      .catch(function () { /* sin conexi\xF3n: se reintenta en la vuelta */ })
      .then(function () { leyendo = false; });
  }
  function vuelta() { leer(); setTimeout(vuelta, Date.now() < pronto ? 1500 : (document.hidden ? 20000 : 4000)); }
  vuelta();
  document.addEventListener('visibilitychange', function () { if (!document.hidden) leer(); });

  // escribir: una vista de la terminal del hilo, abierta la primera vez que hace falta
  var ws = null, cola = [];
  // la direcci\xF3n del WebSocket, desde la de la p\xE1gina (en un iframe srcdoc, la de quien lo arm\xF3)
  function enchufe(ruta) { var u = new URL(ruta, document.baseURI); u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'; return u.href; }
  function canal() {
    if (ws && ws.readyState <= 1) return ws;
    ws = new WebSocket(enchufe('/pty?hilo=' + encodeURIComponent(hilo) + '&cols=100&rows=30'));
    ws.onopen = function () { cola.splice(0).forEach(function (d) { ws.send(JSON.stringify({ d: d })); }); };
    ws.onmessage = function () { /* lo que dibuja la terminal no se muestra aqu\xED */ };
    ws.onclose = function () { ws = null; };
    return ws;
  }
  function teclear(d) { var c = canal(); if (c.readyState === 1) c.send(JSON.stringify({ d: d })); else cola.push(d); pronto = Date.now() + 20000; }
  // \u23CE env\xEDa; \u21E7\u23CE es una l\xEDnea nueva (y mientras se compone una letra con acento, \u23CE es de la composici\xF3n)
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
          dijo.textContent = r.ok ? 'enviado: le llega al terminar su turno, o al tiro si te espera' : (r.error || 'no lleg\xF3');
          if (r.ok) { texto.value = ''; pronto = Date.now() + 30000; setTimeout(leer, 3000); }
        })
        .catch(function () { dijo.textContent = 'sin conexi\xF3n con telar'; });
      return;
    }
    // como un pegado (para que un salto de l\xEDnea no env\xEDe antes de tiempo), y despu\xE9s \u23CE
    teclear('\\u001b[200~' + t + '\\u001b[201~');
    setTimeout(function () { teclear('\\r'); }, 120);
    texto.value = '';
    setTimeout(leer, 1200);
  });
  [].forEach.call(document.querySelectorAll('#teclas button'), function (b) {
    b.addEventListener('click', function () { teclear(JSON.parse('"' + b.getAttribute('data-t') + '"')); setTimeout(leer, 800); });
  });
})();
<\/script></body></html>`}function Ki(e,a={}){let t="/estatico/xterm";return`<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self' 'nonce-${e}'; connect-src 'self';">
<link rel="stylesheet" href="${t}/xterm.css">
<style>@layer base, vistas;
${De()}
@layer vistas { ${B("terminal")} }</style>
<script src="${t}/xterm.js"><\/script><script src="${t}/addon-fit.js"><\/script><script src="/estatico/eco.js"><\/script>
</head><body><div id="t"></div>
<form id="escribir"><textarea id="texto" rows="1" placeholder="escr\xEDbele al hilo \xB7 \u23CE env\xEDa, \u21E7\u23CE l\xEDnea nueva"></textarea><span class="ayuda" title="con la caja vac\xEDa, \u23CE \u238B \u2191 \u2193 van directo a la terminal; un clic en la terminal teclea en ella">vac\xEDa: \u23CE \u238B \u2191\u2193 directo</span></form>
<script nonce="${e}">
(function () {
  // los colores, de los tokens (media/css/tokens.css): los mismos del resto de la p\xE1gina
  var css = getComputedStyle(document.documentElement);
  function t(nombre) { return css.getPropertyValue('--' + nombre).trim(); }
  // sin parpadeo: Claude Code dibuja su propio cursor, y uno que adem\xE1s parpadea molesta al escribir
  var term = new Terminal({ fontFamily: t('letra') || 'Menlo, monospace', fontSize: parseInt(t('tam'), 10) || 13, cursorBlink: false, allowProposedApi: false,
    theme: { background: t('bg'), foreground: t('fg'), cursor: t('cursor'), selectionBackground: t('negro'),
      black: t('negro'), red: t('rojo'), green: t('verde'), yellow: t('amarillo'), blue: t('azul'), magenta: t('magenta'), cyan: t('cian'), white: t('blanco'),
      brightBlack: t('dim'), brightRed: t('rojo'), brightGreen: t('verde'), brightYellow: t('amarillo'), brightBlue: t('azul'), brightMagenta: t('magenta'), brightCyan: t('cian'), brightWhite: t('blanco-claro') } });
  var fit = new FitAddon.FitAddon(); term.loadAddon(fit);
  window.__terminal = term;  // para revisar desde la consola (el buffer, el eco)
  // el eco (como mosh): lo tecleado en la terminal aparece al tiro, tenue, hasta que el servidor lo muestra
  // (src/navegador/eco). Lo que llega pasa por \xE9l, y le avisa lo que se teclea
  var eco = window.telarEco ? window.telarEco.conEco(term) : null;
  window.__eco = eco;  // para revisar desde la consola: __eco.estado()
  function escribir(datos) { if (eco) eco.escribir(datos); else term.write(datos); }
  var caja = document.getElementById('t'); term.open(caja); fit.fit();
  var hilo = ${JSON.stringify(a.hilo??"").replace(/</g,"\\u003c")} || new URLSearchParams(location.search).get('hilo') || '';
  // un hilo de otra m\xE1quina: la p\xE1gina de aqu\xED la reenv\xEDa a la de all\xE1 (telar.terminal.reenviar)
  var maquina = ${JSON.stringify(a.maquina??"").replace(/</g,"\\u003c")};
  // la direcci\xF3n del WebSocket, desde la de la p\xE1gina (en un iframe srcdoc, la de quien lo arm\xF3), con el
  // tama\xF1o de ahora: cada conexi\xF3n abre una vista nueva del hilo
  function direccion() {
    var u = new URL('/pty?hilo=' + encodeURIComponent(hilo) + '&cols=' + term.cols + '&rows=' + term.rows
      + (maquina ? '&maquina=' + encodeURIComponent(maquina) : ''), document.baseURI);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.href;
  }
  // si la conexi\xF3n se corta (el laptop durmi\xF3, cambi\xF3 la red, se reinici\xF3 telar), se reconecta sola: al
  // segundo, y despu\xE9s cada vez m\xE1s espaciado, hasta cada 15 s; al volver a la pesta\xF1a o a la red, al tiro
  var ws = null, esperas = [1000, 2000, 5000, 10000, 15000], intento = 0, pendiente = 0, conectada = false;
  // para desarrollar (docs/desarrollar.md): localStorage['telar.latencia'] = ms simula esa latencia, la mitad
  // a la ida y la mitad a la vuelta (probar el eco sin depender de la red)
  var simulada = 0;
  try { simulada = Number(localStorage.getItem('telar.latencia')) || 0; } catch (x) { /* sin almac\xE9n */ }
  function luego(f) { if (simulada > 0) setTimeout(f, simulada / 2); else f(); }
  function conectar() {
    clearTimeout(pendiente); pendiente = 0;
    if (ws && ws.readyState <= 1) return;
    ws = new WebSocket(direccion());
    ws.onopen = function () {
      // la vista nueva redibuja la pantalla entera: lo de antes se borra para que no quede mezclado
      if (intento) { term.reset(); if (eco) eco.reiniciar(); }
      intento = 0; conectada = true;
    };
    ws.onmessage = function (e) { luego(function () { escribir(e.data); }); };
    ws.onclose = function () {
      if (conectada) term.write('\\r\\n\\x1b[2m[se cort\xF3 la conexi\xF3n con la terminal: reconectando\u2026]\\x1b[0m');
      conectada = false;
      pendiente = setTimeout(conectar, esperas[Math.min(intento++, esperas.length - 1)]);
    };
  }
  conectar();
  document.addEventListener('visibilitychange', function () { if (!document.hidden && !conectada) { intento = 0; conectar(); } });
  window.addEventListener('online', function () { if (!conectada) { intento = 0; conectar(); } });
  function teclear(d) { luego(function () { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ d: d })); }); }
  term.onData(function (d) { if (eco) eco.tecleado(d); teclear(d); });

  // la caja, a un clic: se escribe aqu\xED entero, sin que Claude redibuje con cada letra; \u23CE lo manda como un
  // pegado, y despu\xE9s un \u23CE. Con la caja vac\xEDa, \u23CE \u238B \u2191 \u2193 van directo (los di\xE1logos de Claude, interrumpirlo)
  var texto = document.getElementById('texto');
  function crecer() { texto.style.height = 'auto'; texto.style.height = texto.scrollHeight + 'px'; fit.fit(); }
  texto.addEventListener('input', crecer);
  texto.addEventListener('keydown', function (e) {
    if (e.isComposing) return;
    var vacia = texto.value === '';
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (vacia) { teclear('\\r'); return; }
      teclear('\\u001b[200~' + texto.value.replace(/\\s+$/, '') + '\\u001b[201~');
      setTimeout(function () { teclear('\\r'); }, 120);
      texto.value = ''; crecer();
    } else if (e.key === 'Escape') {
      e.preventDefault(); teclear('\\u001b');
    } else if (vacia && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault(); teclear(e.key === 'ArrowUp' ? '\\u001b[A' : '\\u001b[B');
    }
  });
  new ResizeObserver(function () {
    fit.fit();
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ r: [term.cols, term.rows] }));
  }).observe(caja);
  // al volver a esta terminal, se escribe en ella (con el eco, sin esperar); la caja queda a un clic
  window.addEventListener('focus', function () { if (document.activeElement !== texto) term.focus(); });
  term.focus();
})();
<\/script></body></html>`}So(async(e,a,t,r)=>{let o;try{o=await fetch(`/api${a}`,{method:e,cache:"no-store",signal:AbortSignal.timeout(t),headers:r===void 0?{}:{"Content-Type":"application/json"},body:r===void 0?void 0:JSON.stringify(r)})}catch(s){return{error:`la API no respondi\xF3: ${s.message}`}}let i;try{i=await o.json()}catch{i=void 0}let n=i?.detail;if(o.ok&&i!==void 0)return{datos:i};if(!(o.status===404&&n==="Not Found"))return{error:typeof n=="string"?n:`la API respondi\xF3 ${o.status}`}});var Xt={};Ro((e,a)=>e in Xt?Xt[e]:a);oe().then(e=>{e.datos?.equipo&&(Xt.equipoRemoto=e.datos.equipo,x.leerEquipo())});ni({leer:async e=>{try{let a=await fetch(`/api/archivos?ruta=${encodeURIComponent(e)}`,{cache:"no-store"});return a.ok?(await a.json()).texto:void 0}catch{return}},buscarMd:async(e,a)=>{try{let t=await fetch(`/api/archivos/md?carpeta=${encodeURIComponent(e)}&hondo=${a}`,{cache:"no-store"});return t.ok?(await t.json()).archivos:[]}catch{return[]}},escribir:async(e,a)=>{try{return(await fetch("/api/archivos",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({ruta:e,texto:a})})).ok}catch{return!1}}});var Me=()=>document.getElementById("marcos"),V,Ce,Qi,Za=new Map,na="dashboard";function Xa(e,a){let t=document.createElement("iframe");return t.dataset.p=e,t.title=e,t.setAttribute("sandbox","allow-scripts allow-same-origin allow-forms allow-popups allow-modals"),a.appendChild(t),t}function Vt(e,a){e?.contentWindow?.postMessage({__telarPadre:a},location.origin)}var oa=e=>Vt(V,e);function kc(){let e=document.body.classList.contains("angosto"),a=document.body.classList.contains("en-lista");return V&&!V.hidden&&!(e&&a)?V:Ce??V}var Je=e=>Vt(kc(),e);function en(e){let a=/'nonce-([^']+)'/.exec(e)?.[1]??"";return e.replace("</style>",`${vr}</style>`).replace("<body",`<script nonce="${a}">${Xi}<\/script><body`)}window.addEventListener("message",e=>{let a=!!Ce&&e.source===Ce.contentWindow;if(!a&&e.source!==V?.contentWindow||typeof e.data?.__telarHijo!="string")return;let t;try{t=JSON.parse(e.data.__telarHijo)}catch{return}if(typeof t.__ui_r=="string"){let r=Za.get(t.__ui_r);r&&(Za.delete(t.__ui_r),r(t.valor));return}"__ancho"in t||(a?L.mensaje(t):Qi?.mensaje(t))});var Cc=e=>{Qi=e;let a={cspSource:"'self'",get visible(){return!document.hidden&&!!V&&!V.hidden},get activa(){return document.hasFocus()},html:t=>{V||(V=Xa("dashboard",Me())),V.srcdoc=en(t)},enviar:t=>oa(t),revelar:()=>sa("dashboard")};return document.addEventListener("visibilitychange",()=>e.cambio(!document.hidden,document.hasFocus())),a},_c={cspSource:"'self'",get visible(){return!document.hidden},html:e=>{Ce||(Ce=Xa("barra",document.getElementById("barra"))),Ce.srcdoc=en(e)},enviar:e=>Vt(Ce,e),cabecera:()=>{}},Dc={get:e=>{try{return JSON.parse(localStorage.getItem(`telar.barra.${e}`)??"null")??void 0}catch{return}},update:async(e,a)=>{try{localStorage.setItem(`telar.barra.${e}`,JSON.stringify(a))}catch{}}},an={},tn=()=>document.body.classList.contains("angosto");function ia(e){return e==="dashboard"||e==="compartir"||e.startsWith("doc:")?"":an[e]??(tn()?"conv":"term")}var Rc=8,ze=[];function sa(e){if(!e)return;na=e;let a;if(e==="dashboard")me.panel||me.abrir(),a=V;else{let i=ia(e),n=i?`${i}:${e}`:e;if(a=[...Me().querySelectorAll("iframe")].find(s=>s.dataset.p===n),e.startsWith("doc:")||e==="compartir")a??=Xa(n,Me()),e==="compartir"?a.srcdoc=Vi(Math.random().toString(36).slice(2),{consulta:location.search}):sn(a,e.slice(4),"");else if(!a){let s=e.startsWith("rem:")?e.slice(4):"",l=s.indexOf(":"),c=s?s.slice(l+1):e,u=s?s.slice(0,l):"",h=Math.random().toString(36).slice(2);a=Xa(n,Me()),a.srcdoc=i==="term"?Ki(h,{hilo:c,maquina:u}):Yi(h,{hilo:c,maquina:u})}if(i==="term"){let s=ze.indexOf(n);for(s>=0&&ze.splice(s,1),ze.push(n);ze.length>Rc;)[...Me().querySelectorAll("iframe")].find(l=>l.dataset.p===ze[0])?.remove(),ze.shift()}}for(let i of Me().querySelectorAll("iframe"))i.hidden=i!==a;let t=document.getElementById("modo");t&&(t.hidden=!ia(e),t.textContent=ia(e)==="term"?"conversaci\xF3n":"terminal"),ia(e)==="term"&&!tn()&&a?.contentWindow?.focus();let r=e.startsWith("rem:")?e.slice(4):"",o=r||(e.startsWith("doc:")?`${e.slice(4)} \xB7 carpeta`:e);window.telar?.donde?.(e==="dashboard"?null:{texto:o,otraMaquina:!!r}),document.title=e==="dashboard"?"telar":`${o} \xB7 telar`,document.body.classList.remove("en-lista"),document.body.classList.add("en-detalle"),L.dashboardActivo=e==="dashboard",L.mostrado=e==="dashboard"?"":e,L.refrescar(!0)}function Gt(e){let a=Math.random().toString(36).slice(2)+Date.now().toString(36);return new Promise(t=>{Za.set(a,t),Je({...e,__ui:a}),setTimeout(()=>{Za.delete(a)&&t(null)},600*1e3)})}function Zt(e){return async(a,...t)=>{let r=t.filter(i=>typeof i=="string");if(!r.length){Je({__aviso:a,nivel:e});return}let o=await Gt({tipo:"aviso",texto:a,botones:r});return typeof o=="string"?o:void 0}}var rn=new xo({html:!1,linkify:!0}),on={aviso:Zt("aviso"),falla:Zt("falla"),info:Zt("info"),estado:(e,a)=>Je({__aviso:e,nivel:"info",ms:a??4e3}),progreso:async(e,a)=>(e.ventana||Je({__aviso:e.title,nivel:"info",ms:2500}),a()),campo:async e=>{let a="",t=e.value??"";for(;;){let r=await Gt({tipo:"campo",titulo:e.title??"",ayuda:e.prompt??"",placeholder:e.placeHolder??"",valor:t,password:!!e.password,problema:a});if(typeof r!="string")return;if(a=e.validateInput?.(r)??"",!a)return r;t=r}},elegir:async(e,a)=>{let t=await Gt({tipo:"elegir",titulo:a?.title??"",placeholder:a?.placeHolder??"",opciones:e.map(r=>({label:r.label,description:r.description,detail:r.detail,separador:!!r.separador}))});return typeof t=="number"?e[t]:void 0},abrirExterno:async e=>{window.open(e,"_blank","noopener")},abrirArchivo:async e=>{oa({__aviso:`${e}: abrir archivos desde el navegador viene despu\xE9s`,nivel:"aviso"})},mostrarCarpeta:async e=>{oa({__aviso:`${e}: abrir carpetas desde el navegador viene despu\xE9s`,nivel:"aviso"})},copiar:async e=>{try{await navigator.clipboard.writeText(e)}catch{}},markdown:async e=>rn.render(e),irAHilo:async(e,a,t)=>{let r=await Qo(e,!!a,t??"");r.ok?oa({__aviso:`\u2192 ${e}, en la terminal`,nivel:"info",ms:2500}):oa({__aviso:`telar: ${r.err.trim()||`no pude ir a \xAB${e}\xBB`}`,nivel:"falla"})},mostrarTerminal:async()=>{},orden:async(e,...a)=>{let t=Ac[e];if(t)return t(...a);Je({__aviso:`\xAB${e}\xBB todav\xEDa no est\xE1 en el navegador`,nivel:"aviso"})}};$o(on);var me=new Wa;me.crearSuperficie=Cc;var L=new Ta;L.estado=Dc;L.dashboardActivo=!0;L.mostrado="";var Ac=di({hoy:me,barra:L,anfitrion:on,avisar:Je,mostrar:sa});L.conectar(_c);me.alCambiarFoco=()=>{let e=me.appActual;L.appActiva!==e&&(L.appActiva=e,L.refrescar(!0))};x.cambio.event(()=>L.refrescar());fetch("/api/salud",{cache:"no-store"}).then(e=>e.json()).then(e=>{L.aqui=e.maquina??"",L.refrescar(!0)}).catch(()=>{});var nn=async()=>{let a=((await jo().catch(()=>{}))?.datos?.espejos??[]).filter(t=>!t.error).map(t=>({nombre:t.nombre,en_linea:t.en_linea,edad:t.edad,hilos:t.hilos.filter(r=>!r.remoto)}));JSON.stringify(a)!==JSON.stringify(L.otras)&&(L.otras=a,L.refrescar(!0))};nn();setInterval(()=>void nn(),30*1e3);async function sn(e,a,t){let r;try{let o=await fetch(`/api/hilos/documento?hilo=${encodeURIComponent(a)}&archivo=${encodeURIComponent(t)}`,{cache:"no-store"}),i=await o.json();r=o.ok?{...i,html:i.markdown?rn.render(i.markdown):void 0,subir:i.subir??void 0}:{hilo:a,titulo:a,error:typeof i.detail=="string"?i.detail:`la API respondi\xF3 ${o.status}`}}catch(o){r={hilo:a,titulo:a,error:`la API no respondi\xF3: ${o.message}`}}e.onload=()=>{e.contentDocument?.addEventListener("click",o=>{let n=o.target.closest?.("a")?.getAttribute("href")??"";if(!n.startsWith("/documento"))return;o.preventDefault();let s=new URLSearchParams(n.slice(n.indexOf("?")+1));sn(e,s.get("hilo")??a,s.get("archivo")??"")})},e.srcdoc=Gi(Math.random().toString(36).slice(2),r)}function Ec(){let e=ia(na);e&&(an[na]=e==="term"?"conv":"term",sa(na))}window.telar={...window.telar??{},mostrar:sa,cambiarModo:Ec};sa(location.pathname==="/compartir"?"compartir":"dashboard");document.body.classList.contains("angosto")&&(document.body.classList.remove("en-detalle"),document.body.classList.add("en-lista"));setInterval(()=>{me.panel&&!document.hidden&&na==="dashboard"&&me.actualizar()},60*1e3);var ln=async()=>{document.hidden||await x.sondear().catch(()=>{}),setTimeout(ln,x.error||!x.viva?5e3:3e3)};x.sondear(!0).catch(()=>{}).then(ln);})();
