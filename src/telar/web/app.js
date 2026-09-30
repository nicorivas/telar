// telar en el navegador: un terminal con color sobre `telar hoy --json` y `telar hilos --json`.
// Sin dependencias ni compilación: se edita y se recarga sola (ver ordenes/web.py).
'use strict';

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...hijos) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...hijos.flat().filter((h) => h != null && h !== false));
  return e;
};
// texto → nodos. Lo que la fuente no trae (un símbolo, un emoji) va en su propia celda (.g): así no
// puede estirar el renglón ni correr la grilla. Un emoji ocupa dos celdas, como en un terminal.
const PROPIO = /[\u0000-\u00ff\u0131\u0152\u0153\u2000-\u206f\u20ac\u2122\u2191\u2193\u2212\u2215]/;
function celdas(texto) {
  const nodos = [];
  let corrido = '';
  for (const c of String(texto ?? '').normalize('NFC')) {
    if (PROPIO.test(c)) { corrido += c; continue; }
    if (corrido) { nodos.push(corrido); corrido = ''; }
    const astral = c.codePointAt(0) > 0xffff;
    nodos.push(el('span', { className: `g${astral ? ' doble' : ''}`, textContent: astral ? c : `${c}\uFE0E` }));  // FE0E: en texto, no en emoji
  }
  if (corrido) nodos.push(corrido);
  return nodos;
}
const txt = (clase, texto) => el('span', { className: clase }, celdas(texto));
// un símbolo ocupa una celda, se vea con la fuente que se vea
const g = (simbolo, clase = '') => el('span', { className: `g ${clase}`.trim(), textContent: simbolo });

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const GLIFO = { trabajando: '●', espera: '○', termino: '✓', ninguna: '·' };
const NOMBRE_ATENCION = { trabajando: 'trabajando', espera: 'te espera', termino: 'terminó' };
const PRIORIDAD = { 1: ['●', 'venc'], 2: ['◐', 'pronto'], 3: ['○', 'dim'] };
const ORDEN_ATENCION = { espera: 0, termino: 1, trabajando: 2, ninguna: 3 };
const TOPE = 12;  // cuántos pendientes se muestran antes de «… y N más»

const guardado = (clave, valor) => {
  try { if (valor === undefined) return localStorage.getItem(clave); localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ }
  return null;
};
const estado = {
  hoy: null, hilos: null, espejos: [], crudo: '', error: '',
  abiertos: new Set(), sinVentana: new Set(), masPendientes: false,
  modo: guardado('telar.modo') === 'todos' ? 'todos' : 'urgentes',
};

// ── tiempo ─────────────────────────────────────────────────
const dos = (n) => String(n).padStart(2, '0');
const hhmm = (f) => `${dos(f.getHours())}:${dos(f.getMinutes())}`;
const duracion = (seg) => {  // 5400 → «1h30»; vacío si no hay ni un minuto
  const m = Math.floor(seg / 60);
  return m <= 0 ? '' : m >= 60 ? `${Math.floor(m / 60)}h${dos(m % 60)}` : `${m}m`;
};
function hace(seg) {  // 45 → «45 s»; 600 → «10 min»; 7200 → «2 h»
  if (seg == null) return '—';
  if (seg < 90) return `${Math.floor(seg)} s`;
  if (seg < 5400) return `${Math.round(seg / 60)} min`;
  return seg < 172800 ? `${Math.round(seg / 3600)} h` : `${Math.round(seg / 86400)} d`;
}
function faltan(t, ahora) {
  const m = Math.round((t - ahora) / 60000);
  if (m < 1) return 'ahora';
  if (m < 60) return `en ${m} min`;
  return `en ${Math.floor(m / 60)}h${m % 60 ? dos(m % 60) : ''}`;
}

// ── pendientes: lo más urgente arriba (la misma regla del dashboard de VS Code) ──
function pendientes(d) {
  const hoy = Date.parse(`${d.fecha || new Date().toISOString().slice(0, 10)}T00:00:00`);
  return (d.pendientes || [])
    .filter((f) => !f.hecho && !(f.pestana || ''))
    .map((f) => {
      const dias = f.cuando ? Math.round((Date.parse(`${f.cuando.slice(0, 10)}T00:00:00`) - hoy) / 86400000) : null;
      const avance = (f.avance || '').split(' ')[0].split(':')[0];
      // el código va aparte del texto: «AGP-11: hacer algo» o el id de la tarea
      let id = f.id && f.id.length <= 8 ? f.id : '';
      let texto = f.texto || '';
      const m = !id && /^([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-\d+)\s*:\s*/.exec(texto);
      if (m) { id = m[1]; texto = texto.slice(m[0].length); }
      return {
        f, id, texto, dias, avance, encurso: !!f.en_curso,
        urgencia: avance ? -1000 + (dias ?? 0) / 1000 : (dias ?? 30) - (f.en_curso ? 0.5 : 0),
        urgente: avance ? true : dias !== null ? dias <= 7 : !!f.en_curso,
      };
    })
    .sort((a, b) => a.urgencia - b.urgencia || (a.f.ref || '').localeCompare(b.f.ref || ''));
}

function plazo(p) {
  if (p.dias === null) return null;
  if (p.dias < 0) return txt('venc', `${p.dias}d`);
  if (p.dias === 0) return txt('pronto', 'hoy');
  if (p.dias <= 7) return txt('pronto', `${p.dias}d`);
  const f = new Date(`${p.f.cuando.slice(0, 10)}T12:00`);
  return txt('dim', `${f.getDate()} ${MESES[f.getMonth()]}`);
}

// ── piezas ─────────────────────────────────────────────────
function bloque(clase, titulo, cuenta, modos, ...filas) {
  return el('section', { className: `bloque ${clase}` },
    el('h2', { className: 'sec' },
      el('span', { className: 'marca' }), titulo,
      cuenta != null ? el('span', { className: 'cuenta', textContent: String(cuenta) }) : null,
      modos),
    ...filas);
}
const vacio = (t) => el('div', { className: 'vacio', textContent: t });

// el detalle de una fila, como un árbol: ├ clave valor
function arbolDatos(pares) {
  const filas = pares.filter(([, v]) => v);
  if (!filas.length) filas.push(['', 'sin más datos']);
  return el('div', { className: 'arbol' }, filas.flatMap(([k, v], i) => [
    g(i === filas.length - 1 ? '└' : '├'), txt('k', k), txt('v', v)]));
}

const arbol = (h, origen = '') => arbolDatos([
  ['de', origen], ['resumen', h.resumen], ['ruta', h.ruta || h.relativa], ['tiempo', duracion(h.tiempo)], ['prioridad', h.prioridad ? String(h.prioridad) : ''],
  ['estado', h.ficha && h.ficha.estado], ['remoto', h.remoto],
  ['sesiones', h.sesiones && h.sesiones.length ? String(h.sesiones.length) : ''],
]);

// `origen`: de qué máquina viene el hilo («» = esta). Un hilo del laptop dice de dónde es.
function filaHilo(h, { lado = 'atencion', origen = '', dondeSub = false } = {}) {
  const clave = `${origen}:${h.nombre}`;
  const abierto = estado.abiertos.has(clave);
  const donde = origen && dondeSub ? `en ${origen}` : '';
  const sub = [donde, h.relativa && h.relativa !== '.' ? h.relativa : (h.remoto ? `en ${h.remoto}` : '')].filter(Boolean).join(' · ');
  const [glifoPri, clasePri] = PRIORIDAD[h.prioridad] || [];
  return [
    el('div', {
      className: 'fila hl clic', role: 'button', tabIndex: 0, 'aria-expanded': String(abierto),
      onclick: () => { estado.abiertos.has(clave) ? estado.abiertos.delete(clave) : estado.abiertos.add(clave); pintar(); },
    },
      g(GLIFO[h.atencion] || '·', `at ${h.atencion}${h.atencion === 'ninguna' && h.vivo ? ' vivo' : ''}`),
      txt('nombre una', h.nombre),
      lado === 'atencion' && NOMBRE_ATENCION[h.atencion]
        ? txt(`lado ${h.atencion}`, NOMBRE_ATENCION[h.atencion])
        : (glifoPri ? el('span', { className: `lado ${clasePri}` }, g(glifoPri)) : null),
      sub ? txt('sub una', sub) : null),
    abierto ? arbol(h, origen) : null,
  ];
}

// ── pantallas ──────────────────────────────────────────────
function pantallaHoy() {
  const d = estado.hoy;
  const ahora = new Date();

  const eventos = (d.agenda || []).map((e) => ({ e, t: e.cuando && e.cuando.length > 10 ? new Date(e.cuando) : null }));
  const proxima = eventos.find(({ t }) => t && t >= ahora);
  const filasAgenda = eventos.map(({ e, t }) => el('div', {
    className: `fila ag${t && t < ahora ? ' pasada' : ''}${proxima && proxima.e === e ? ' proxima' : ''}`,
  },
    txt('hora', t ? hhmm(t) : '  ·  '),
    txt('que dos', e.texto),
    proxima && proxima.e === e ? txt('falta', faltan(t, ahora)) : null));

  // te esperan: los de esta máquina y los de las otras que estén en línea (una apagada no espera nada)
  const esperan = [
    ...(d.atencion || []).map((h) => ({ h, origen: '' })),
    ...estado.espejos.filter((e) => e.en_linea).flatMap((e) => (e.hilos || [])
      .filter((h) => NOMBRE_ATENCION[h.atencion]).map((h) => ({ h, origen: e.nombre }))),
  ].sort((a, b) => ORDEN_ATENCION[a.h.atencion] - ORDEN_ATENCION[b.h.atencion]);
  const llaman = esperan.flatMap(({ h, origen }) => filaHilo(h, { origen, dondeSub: true }));

  const todas = pendientes(d);
  const urgentes = todas.filter((p) => p.urgente);
  const lista = estado.modo === 'todos' ? todas : urgentes;
  const visibles = estado.masPendientes ? lista : lista.slice(0, TOPE);
  const filasPend = visibles.flatMap((p) => {
    const clave = `p:${p.f.ref || p.id || p.texto}`;
    const abierto = estado.abiertos.has(clave);
    return [
      el('div', {
        className: `fila pe clic${p.encurso ? ' encurso' : ''}${abierto ? ' abierto' : ''}`, role: 'button', tabIndex: 0, 'aria-expanded': String(abierto),
        onclick: () => { estado.abiertos.has(clave) ? estado.abiertos.delete(clave) : estado.abiertos.add(clave); pintar(); },
      },
        txt('id', p.id || (p.f.ref || '').split('/').pop().split(':')[0]),
        g(p.encurso ? '▣' : '☐', 'cas'),
        el('span', { className: abierto ? 'todo' : 'dos' }, p.avance ? txt(`av av-${p.avance}`, p.avance) : null, celdas(p.texto)),
        el('span', { className: 'plazo' }, plazo(p))),
      abierto ? arbolDatos([
        ['ref', (p.f.ref || '').replace(/^.*\//, '') || p.id], ['dónde', p.f.ruta], ['hilo', p.f.hilo], ['área', p.f.area],
        ['de', p.f.proveedor && p.f.proveedor !== 'pendientes' ? p.f.proveedor : ''],
        ['para', p.f.cuando ? p.f.cuando.replace('T00:00', '').replace('T', ' ') : ''], ['avance', p.f.avance]]) : null,
    ];
  });
  const modos = el('span', { className: 'modos' },
    ...[['urgentes', urgentes.length], ['todos', todas.length]].map(([m, n]) => el('button', {
      type: 'button', className: estado.modo === m ? 'activo' : '', textContent: `${m} ${n}`,
      onclick: () => { estado.modo = m; estado.masPendientes = false; guardado('telar.modo', m); pintar(); },
    })));
  const resto = lista.length - TOPE;

  const total = d.tiempo && d.tiempo.total;
  const fallas = (d.proveedores && d.proveedores.fallas) || [];
  return [
    bloque('agenda', 'agenda', filasAgenda.length || null, null,
      ...(filasAgenda.length ? filasAgenda : [vacio(d.agenda ? 'nada con hora' : 'sin agenda declarada')])),
    bloque('esperan', 'te esperan', esperan.length || null, null,
      ...(llaman.length ? llaman : [vacio('nadie')])),
    bloque('pendientes', 'pendientes', null, modos,
      ...(filasPend.length ? filasPend : [vacio(estado.modo === 'urgentes' && todas.length ? 'nada urgente' : 'nada pendiente')]),
      resto > 0 || estado.masPendientes ? el('button', {
        type: 'button', className: 'mas', textContent: estado.masPendientes ? '… menos' : `… y ${resto} más`,
        onclick: () => { estado.masPendientes = !estado.masPendientes; pintar(); },
      }) : null),
    total && duracion(total) ? bloque('tiempo', 'hoy', null, null, el('div', { className: 'linea-tiempo', textContent: `${duracion(total)} con los hilos abiertos` })) : null,
    ...fallas.map((f) => el('div', { className: 'falla', textContent: `(proveedor caído · ${f})` })),
  ];
}

function pantallaHilos() {
  const todos = (estado.hilos.hilos || []).filter((h) => !h.archivado);
  const activos = todos.filter((h) => h.vivo || h.atencion !== 'ninguna')
    .sort((a, b) => (ORDEN_ATENCION[a.atencion] - ORDEN_ATENCION[b.atencion]) || a.nombre.localeCompare(b.nombre));
  const otros = todos.filter((h) => !activos.includes(h)).sort((a, b) => a.nombre.localeCompare(b.nombre));
  return [
    bloque('hilos', 'hilos', activos.length, null,
      ...(activos.length ? activos.flatMap((h) => filaHilo(h)) : [vacio('ningún hilo activo')])),
    otros.length ? bloque('otros', 'sin ventana', otros.length, null, ...filasSinVentana(':otros', '', otros, '… mostrar')) : null,
    ...estado.espejos.map(seccionEspejo),
  ];
}

// «… N sin ventana» / «… ocultar»: los hilos que no tienen ventana son muchos y casi nunca se miran
function filasSinVentana(clave, origen, hilos, cerrada = `… ${hilos.length} sin ventana`) {
  const abierta = estado.sinVentana.has(clave);
  return [
    el('button', {
      type: 'button', className: 'mas', textContent: abierta ? '… ocultar' : cerrada,
      onclick: () => { estado.sinVentana.has(clave) ? estado.sinVentana.delete(clave) : estado.sinVentana.add(clave); pintar(); },
    }),
    ...(abierta ? hilos.flatMap((h) => filaHilo(h, { lado: 'prioridad', origen })) : []),
  ];
}

// los hilos de otra máquina, de su última foto: en línea, o apagada y atenuada con su edad
function seccionEspejo(e) {
  const estadoTxt = el('span', { className: `estado-esp ${e.en_linea ? 'en-linea' : 'apagado'}` },
    g(e.en_linea ? '●' : '○'), e.error ? ' sin leer' : (e.en_linea ? ' en línea' : ` apagado · hace ${hace(e.edad)}`));
  const todos = (e.hilos || []).filter((h) => !h.archivado);
  const activos = todos.filter((h) => h.vivo || (h.atencion && h.atencion !== 'ninguna'))
    .sort((a, b) => (ORDEN_ATENCION[a.atencion] ?? 3) - (ORDEN_ATENCION[b.atencion] ?? 3) || a.nombre.localeCompare(b.nombre));
  const otros = todos.filter((h) => !activos.includes(h)).sort((a, b) => a.nombre.localeCompare(b.nombre));
  const cuerpo = e.error ? [el('div', { className: 'falla', textContent: e.error })]
    : activos.length ? activos.flatMap((h) => filaHilo(h, { origen: e.nombre })) : [vacio(todos.length ? 'ningún hilo activo' : 'sin hilos')];
  return bloque(`espejo${e.en_linea ? '' : ' viejo'}`, e.nombre, activos.length, estadoTxt, ...cuerpo,
    ...(otros.length ? filasSinVentana(`${e.nombre}:otros`, e.nombre, otros) : []));
}

const vistaActual = () => (location.hash === '#hilos' ? 'hilos' : 'hoy');

function pintar() {
  const vista = vistaActual();
  for (const a of document.querySelectorAll('#barra a')) {
    a.classList.toggle('activa', a.dataset.vista === vista);
    a.setAttribute('aria-current', a.dataset.vista === vista ? 'page' : 'false');
  }
  const ahora = new Date();
  $('reloj').textContent = hhmm(ahora);
  const fecha = estado.hoy && estado.hoy.fecha ? new Date(`${estado.hoy.fecha}T12:00`) : ahora;
  $('fecha').replaceChildren(`${DIAS[fecha.getDay()]} ${fecha.getDate()} ${MESES[fecha.getMonth()]} `,
    txt('dim', `· sem ${estado.hoy ? estado.hoy.semana : ''}`.trim()));

  const cont = $('vista');
  const y = scrollY;
  if (!estado.hoy || !estado.hilos) {
    cont.replaceChildren(estado.error
      ? el('div', { className: 'error', textContent: estado.error })
      : el('div', { className: 'vacio', textContent: 'leyendo el día…' }));
    return;
  }
  cont.replaceChildren(...(vista === 'hilos' ? pantallaHilos() : pantallaHoy()).filter(Boolean),
    ...(estado.error ? [el('div', { className: 'error', textContent: estado.error })] : []));
  scrollTo(0, y);
}

// ── datos ──────────────────────────────────────────────────
async function pedir(ruta, fresco = false) {
  const r = await fetch(`/api/${ruta}${fresco ? '?fresco=1' : ''}`, { cache: 'no-store' });
  const cuerpo = await r.json();
  if (!r.ok) throw new Error(cuerpo.error || `error ${r.status}`);
  return cuerpo;
}

async function cargar(fresco = false) {
  const aviso = $('aviso');
  aviso.textContent = 'actualizando…';
  aviso.className = '';
  try {
    const [hoy, hilos, fotos] = await Promise.all([pedir('hoy', fresco), pedir('hilos', fresco), pedir('espejos')]);
    // la edad de una foto crece sola: para saber si algo cambió se mira lo demás y si sigue en línea
    const crudo = JSON.stringify([hoy, hilos, (fotos.espejos || []).map((e) => [e.nombre, e.en_linea, e.recibido, e.error])]);
    const cambio = crudo !== estado.crudo || estado.error;
    Object.assign(estado, { hoy, hilos, espejos: fotos.espejos || [], crudo, error: '' });
    aviso.textContent = hhmm(new Date());
    if (cambio) pintar();
  } catch (e) {
    estado.error = e.message;
    aviso.textContent = 'sin conexión';
    aviso.className = 'mal';
    pintar();
  }
}

// ── tema: oscuro por defecto, claro si se elige (la cabecera lo pone antes de pintar) ──
const tema = () => (document.documentElement.dataset.tema === 'claro' ? 'claro' : 'oscuro');
function pintarTema() {
  const claro = tema() === 'claro';
  $('icono-tema').textContent = claro ? '☀' : '☾';
  $('tema').title = claro ? 'tema claro (t para cambiar)' : 'tema oscuro (t para cambiar)';
  document.querySelector('meta[name=color-scheme]').content = claro ? 'light' : 'dark';
  document.querySelector('meta[name=theme-color]').content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
}
function alternarTema() {
  const nuevo = tema() === 'claro' ? 'oscuro' : 'claro';
  if (nuevo === 'claro') document.documentElement.dataset.tema = 'claro'; else delete document.documentElement.dataset.tema;
  guardado('telar.tema', nuevo === 'claro' ? 'claro' : 'oscuro');
  pintarTema();
}
$('tema').onclick = alternarTema;

// ── vida de la página ──────────────────────────────────────
addEventListener('hashchange', () => { scrollTo(0, 0); pintar(); });
$('recargar').onclick = () => cargar(true);
addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || /input|textarea/i.test(e.target.tagName)) return;
  if (e.key === '1') location.hash = '#hoy';
  else if (e.key === '2') location.hash = '#hilos';
  else if (e.key === 'r') cargar(true);
  else if (e.key === 't') alternarTema();
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) cargar(); });
setInterval(() => { if (!document.hidden) cargar(); }, 30000);
// el reloj, y con él la «próxima» de la agenda, se mueven solos cada minuto
let minuto = '';
setInterval(() => { const m = hhmm(new Date()); if (m !== minuto) { minuto = m; pintar(); } }, 5000);

// recarga automática: si cambian los archivos de la página, se recarga sola
let version = null;
setInterval(async () => {
  try {
    const { pagina } = await (await fetch('/api/version', { cache: 'no-store' })).json();
    if (pagina && version && pagina !== version) location.reload();
    version = pagina || version;
  } catch (e) { /* el servidor se está reiniciando: se reintenta */ }
}, 1500);

pintarTema();
pintar();
cargar();
