// telar en el navegador: un terminal con color sobre `telar hoy --json` y `telar hilos --json`.
// Sin dependencias ni compilación: se edita y se recarga sola (ver ordenes/web.py).
'use strict';

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...hijos) => {
  // las claves con guion (data-*, aria-*) son atributos, no propiedades: Object.assign no las vería
  const e = Object.assign(document.createElement(tag), Object.fromEntries(Object.entries(props).filter(([k]) => !k.includes('-'))));
  for (const [k, v] of Object.entries(props)) if (k.includes('-')) e.setAttribute(k, v);
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
  hoy: null, cal: null, calElegir: null, hilos: null, espejos: [], yo: { escribir: false, plan: false, plan_comentar: false, nuevo: false, enlaces: [] }, proyectos: null, plan: null, diaPlan: '', crudo: '', error: '',
  borradores: new Map(), envios: new Map(), repintar: false,
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
      // el código va aparte del texto: «FAR-11: hacer algo» o el id de la tarea
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
// ── escribirle a un hilo ───────────────────────────────────
// Solo si el servidor arrancó con --escribir y el hilo está vivo; los de otra máquina, además, si esa
// máquina está en línea y hay un enlace para llegar a ella (`telar enlace`).
function puedeEscribir(h, origen) {
  if (!estado.yo.escribir || !(h.vivo || h.propio)) return false;
  if (!origen) return true;
  const e = estado.espejos.find((x) => x.nombre === origen);
  return !!(e && e.en_linea && estado.yo.enlaces.length);
}

async function mandar(clave, origen, h, texto) {
  const dice = (t, ok) => { estado.envios.set(clave, { t, ok }); pintar(true); };
  dice('enviando…', null);
  try {
    const r = await fetch('/api/enviar', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' },
      body: JSON.stringify({ maquina: origen, hilo: h.nombre, texto, enter: true }),
    });
    const cuerpo = await r.json().catch(() => ({}));
    if (r.ok && cuerpo.ok) {
      estado.borradores.delete(clave);
      estado.envios.delete(clave); pintar(true);  // el hilo responde en su lista: no hace falta decir «enviado»
      setTimeout(() => cargar(true), 3000);  // el semáforo del hilo suele cambiar enseguida
    } else {
      dice(cuerpo.error || `no salió (${r.status})`, false);
    }
  } catch (e) {
    dice('sin conexión con el servidor', false);
  }
}

// de este equipo, si el hilo tiene conversaciones anotadas; de otra máquina, si está en línea y hay un enlace para llegar
function puedeVerConversacion(h, origen) {
  if (!origen) return !!(h.sesiones && h.sesiones.length);
  const e = estado.espejos.find((x) => x.nombre === origen);
  return !!(e && e.en_linea && estado.yo.enlaces.length);
}

function compone(h, origen, clave) {
  const campo = el('input', {
    type: 'text', className: 'campo', autocomplete: 'off', autocapitalize: 'sentences', enterKeyHint: 'send',
    placeholder: `escribirle a ${h.nombre}`, value: estado.borradores.get(clave) || '', maxLength: 8000,
    'aria-label': `escribirle a ${h.nombre}`, 'data-clave': clave,
    oninput: () => estado.borradores.set(clave, campo.value),
    onblur: () => { if (estado.repintar) { estado.repintar = false; pintar(); } },
  });
  const enviar = () => {
    const texto = campo.value.trim();
    if (texto) mandar(clave, origen, h, texto);
  };
  campo.onkeydown = (e) => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); enviar(); } };
  const dijo = estado.envios.get(clave);
  return el('div', { className: 'compone' },
    g('›', 'prompt'), campo,
    el('button', { type: 'button', className: 'manda', onclick: enviar }, el('kbd', { textContent: '↩' }), ' enviar'),
    dijo ? el('div', { className: `dijo ${dijo.ok === false ? 'mal' : dijo.ok ? 'bien' : ''}`, textContent: dijo.t }) : null);
}

function filaHilo(h, { lado = 'atencion', origen = '', dondeSub = false } = {}) {
  const clave = `${origen}:${h.nombre}`;
  const abierto = estado.abiertos.has(clave);
  const donde = origen && dondeSub ? `en ${origen}` : '';
  const sub = [donde, h.relativa && h.relativa !== '.' ? h.relativa : (h.remoto ? `en ${h.remoto}` : '')].filter(Boolean).join(' · ');
  const [glifoPri, clasePri] = PRIORIDAD[h.prioridad] || [];
  // con conversación que ver, tocar el hilo entra a ella; sin ella, se despliega lo que se sabe del hilo
  const conversa = puedeVerConversacion(h, origen);
  return [
    el('div', {
      className: 'fila hl clic', role: 'button', tabIndex: 0, ...(conversa ? {} : { 'aria-expanded': String(abierto) }),
      onclick: () => {
        if (conversa) { location.hash = hashConv(h.nombre, origen); return; }
        estado.abiertos.has(clave) ? estado.abiertos.delete(clave) : estado.abiertos.add(clave); pintar();
      },
    },
      g(GLIFO[h.atencion] || '·', `at ${h.atencion}${h.atencion === 'ninguna' && h.vivo ? ' vivo' : ''}`),
      txt('nombre una', h.nombre),
      lado === 'atencion' && NOMBRE_ATENCION[h.atencion]
        ? txt(`lado ${h.atencion}`, NOMBRE_ATENCION[h.atencion])
        : (glifoPri ? el('span', { className: `lado ${clasePri}` }, g(glifoPri)) : null),
      sub ? txt('sub una', sub) : null),
    abierto && !conversa ? arbol(h, origen) : null,
    abierto && !conversa && puedeEscribir(h, origen) ? compone(h, origen, clave) : null,
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
    ...(d.atencion || []).filter((h) => h.vivo || h.propio).map((h) => ({ h, origen: '' })),
    ...estado.espejos.filter((e) => e.en_linea).flatMap((e) => (e.hilos || [])
      .filter((h) => h.vivo && NOMBRE_ATENCION[h.atencion]).map((h) => ({ h, origen: e.nombre }))),
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
    barraAtajos(),
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

// los atajos del dashboard (`[atajos.<tecla>]`): un toque abre el hilo con el agente haciendo eso, o se lo encarga a su agente
function barraAtajos() {
  const atajos = estado.yo.atajos || [];
  if (!atajos.length) return null;
  const dijo = el('div', { className: 'dijo' });
  const botones = atajos.map((a) => {
    const b = el('button', { type: 'button', title: a.descripcion, textContent: a.nombre });
    b.onclick = async () => {
      for (const x of botones) x.disabled = true;
      dijo.className = 'dijo'; dijo.textContent = `abriendo ${a.nombre}…`;
      try {
        const r = await fetch('/api/atajo', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' },
          body: JSON.stringify({ tecla: a.tecla }) });
        const cuerpo = await r.json().catch(() => ({}));
        if (r.ok && cuerpo.ok) {
          cargar(true);
          if (cuerpo.encargo === undefined) estado.recien = cuerpo.hilo;  // un hilo nuevo espera su primera conversación
          location.hash = hashConv(cuerpo.hilo);  // y el encargo a un agente lleva a su hilo de siempre
          return;
        } else { dijo.className = 'dijo mal'; dijo.textContent = cuerpo.error || `no salió (${r.status})`; }
      } catch (e) { dijo.className = 'dijo mal'; dijo.textContent = 'sin conexión con el servidor'; }
      for (const x of botones) x.disabled = false;
    };
    return b;
  });
  return el('div', { className: 'atajos' }, el('div', { className: 'atajos-fila' }, ...botones), dijo);
}

function pantallaHilos() {
  const todos = (estado.hilos.hilos || []).filter((h) => !h.archivado);
  // activo es lo que tiene ventana (o sesión propia): un hilo cerrado que quedó «esperando» ya no espera a nadie
  const activos = todos.filter((h) => h.vivo || h.propio)
    .sort((a, b) => (ORDEN_ATENCION[a.atencion] - ORDEN_ATENCION[b.atencion]) || a.nombre.localeCompare(b.nombre));
  const otros = todos.filter((h) => !activos.includes(h)).sort((a, b) => a.nombre.localeCompare(b.nombre));
  return [
    barraAtajos(),
    estado.yo.nuevo ? el('div', { className: 'nuevo-hilo' }, el('button', { type: 'button', onclick: () => { location.hash = '#nuevo'; } }, '+ nuevo hilo')) : null,
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
  const activos = todos.filter((h) => h.vivo)
    .sort((a, b) => (ORDEN_ATENCION[a.atencion] ?? 3) - (ORDEN_ATENCION[b.atencion] ?? 3) || a.nombre.localeCompare(b.nombre));
  const otros = todos.filter((h) => !activos.includes(h)).sort((a, b) => a.nombre.localeCompare(b.nombre));
  const cuerpo = e.error ? [el('div', { className: 'falla', textContent: e.error })]
    : activos.length ? activos.flatMap((h) => filaHilo(h, { origen: e.nombre })) : [vacio(todos.length ? 'ningún hilo activo' : 'sin hilos')];
  return bloque(`espejo${e.en_linea ? '' : ' viejo'}`, e.nombre, activos.length, estadoTxt, ...cuerpo,
    ...(otros.length ? filasSinVentana(`${e.nombre}:otros`, e.nombre, otros) : []));
}

const vistaActual = () => (location.hash.startsWith('#hilos/') ? 'conversacion' : location.hash.startsWith('#cal') ? 'cal' : location.hash === '#hilos' ? 'hilos' : location.hash === '#plan' ? 'plan' : location.hash === '#nuevo' ? 'nuevo' : 'hoy');

function pintar(forzar = false) {
  // mientras se escribe en un campo, repintar lo destruiría (y con él el teclado): se deja para cuando se suelte.
  // `forzar` (tras un envío) repinta igual y le devuelve el foco al mismo campo.
  const activo = document.activeElement;
  const clave = activo && activo.classList.contains('campo') ? activo.dataset.clave : '';
  if (clave && !forzar) { estado.repintar = true; return; }
  const vista = vistaActual();
  const pestana = vista === 'conversacion' || vista === 'nuevo' ? 'hilos' : vista;
  for (const a of document.querySelectorAll('#barra a')) {
    a.classList.toggle('activa', a.dataset.vista === pestana);
    a.setAttribute('aria-current', a.dataset.vista === pestana ? 'page' : 'false');
  }
  if (vista !== 'conversacion') soltarConversacion();
  const ahora = new Date();
  const fecha = estado.hoy && estado.hoy.fecha ? new Date(`${estado.hoy.fecha}T12:00`) : ahora;
  $('fecha').replaceChildren(`${DIAS[fecha.getDay()]} ${fecha.getDate()} ${MESES[fecha.getMonth()]} `,
    txt('dim', `· sem ${estado.hoy ? estado.hoy.semana : ''}`.trim()));

  $('tab-plan').hidden = !estado.yo.plan;
  const cont = $('vista');
  if (vista === 'conversacion') { pintarConversacion(); return; }
  const y = scrollY;
  if (vista === 'nuevo' && estado.yo.nuevo) {
    if (!estado.proyectos) cargarProyectos();
    cont.replaceChildren(...pantallaNuevo());
    scrollTo(0, 0);
    return;
  }
  if (vista === 'cal') {
    cargarCal(calDiaHash());
    cont.replaceChildren(...pantallaCal().filter(Boolean));
    scrollTo(0, y);
    return;
  }
  if (vista === 'plan' && estado.yo.plan) {
    if (!estado.plan) cargarPlan();
    cont.replaceChildren(...pantallaPlan());
    scrollTo(0, y);
    return;
  }
  if (!estado.hoy || !estado.hilos) {
    cont.replaceChildren(estado.error
      ? el('div', { className: 'error', textContent: estado.error })
      : el('div', { className: 'vacio', textContent: 'leyendo el día…' }));
    return;
  }
  cont.replaceChildren(...(vista === 'hilos' ? pantallaHilos() : pantallaHoy()).filter(Boolean),
    ...(estado.error ? [el('div', { className: 'error', textContent: estado.error })] : []));
  scrollTo(0, y);
  if (clave) {
    const nuevo = [...document.querySelectorAll('.campo')].find((c) => c.dataset.clave === clave);
    if (nuevo) { nuevo.focus({ preventScroll: true }); nuevo.setSelectionRange(nuevo.value.length, nuevo.value.length); }
  }
}

// ── un hilo nuevo, abierto desde la página ──────────────────
async function cargarProyectos() {
  try {
    const r = await fetch('/api/proyectos', { cache: 'no-store' });
    const cuerpo = await r.json();
    estado.proyectos = r.ok ? cuerpo.proyectos || [] : [];
  } catch (e) { estado.proyectos = []; }
  if (vistaActual() === 'nuevo' && !document.activeElement.classList.contains('campo')) pintar();
}

// el nombre es obligatorio, la carpeta y el primer mensaje no; el agente corre en el servidor
function pantallaNuevo() {
  const k = (c) => `nuevo:${c}`;
  const campo = (tag, c, props) => el(tag, { className: 'campo', 'data-clave': k(c), autocomplete: 'off', value: estado.borradores.get(k(c)) || '',
    oninput: (e) => { estado.borradores.set(k(c), e.target.value); }, ...props });
  const nombre = campo('input', 'nombre', { type: 'text', maxLength: 60, placeholder: 'nombre del hilo (obligatorio)', 'aria-label': 'nombre del hilo' });
  const carpeta = campo('input', 'carpeta', { type: 'text', placeholder: 'carpeta del proyecto (opcional)', 'aria-label': 'carpeta' });
  carpeta.setAttribute('list', 'lista-proyectos');  // `list` es solo lectura como propiedad
  const mensaje = campo('textarea', 'mensaje', { rows: 4, maxLength: 4000, placeholder: 'primer mensaje (opcional): lo que quieres que empiece a hacer', 'aria-label': 'primer mensaje' });
  const lista = el('datalist', { id: 'lista-proyectos' }, (estado.proyectos || []).map((p) => el('option', { value: p.ruta }, p.nombre)));
  const dijo = el('div', { className: 'dijo' });
  const boton = el('button', { type: 'button', className: 'manda' }, 'abrir hilo');
  boton.onclick = async () => {
    if (!nombre.value.trim()) { dijo.className = 'dijo mal'; dijo.textContent = 'el hilo necesita un nombre'; nombre.focus(); return; }
    boton.disabled = true; dijo.className = 'dijo'; dijo.textContent = 'abriendo el hilo…';
    try {
      const r = await fetch('/api/hilo/nuevo', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' },
        body: JSON.stringify({ nombre: nombre.value, carpeta: carpeta.value, mensaje: mensaje.value }) });
      const cuerpo = await r.json().catch(() => ({}));
      if (r.ok && cuerpo.ok) {
        for (const c of ['nombre', 'carpeta', 'mensaje']) estado.borradores.delete(k(c));
        estado.recien = cuerpo.hilo;  // su conversación existe recién con el primer mensaje: la pantalla reintenta un rato
        cargar(true);
        location.hash = hashConv(cuerpo.hilo);
        return;
      }
      dijo.className = 'dijo mal'; dijo.textContent = cuerpo.error || `no salió (${r.status})`;
    } catch (e) { dijo.className = 'dijo mal'; dijo.textContent = 'sin conexión con el servidor'; }
    boton.disabled = false;
  };
  return [
    el('div', { className: 'plan-nav' }, el('button', { type: 'button', 'aria-label': 'volver a hilos', onclick: () => { location.hash = '#hilos'; } }, '‹'),
      el('span', { className: 'plan-dia', textContent: 'nuevo hilo' }), el('span')),
    el('section', { className: 'comenta nuevo' },
      el('div', { className: 'dim' }, 'Se abre en el servidor con el agente en modo automático. La carpeta es una unidad de proyectos; sin ella, la del agente.'),
      nombre, carpeta, lista, mensaje, el('div', { className: 'comenta-pie' }, dijo, boton)),
  ];
}

// ── el calendario: lo mismo que el del dashboard de VS Code, en una columna ──
const calDiaHash = () => { const m = location.hash.match(/^#cal\/(\d{4}-\d{2}-\d{2})$/); return m ? m[1] : ''; };
const hmDe = (iso) => (iso || '').slice(11, 16);
const aMin = (h) => Number(h.slice(0, 2)) * 60 + Number(h.slice(3, 5));
const normal = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
const parecidos = (a, b) => { const x = new Set(normal(a).split(' ').filter((w) => w.length > 3)); return normal(b).split(' ').some((w) => w.length > 3 && x.has(w)); };

async function cargarCal(dia, fresco = false) {
  const clave = dia || 'hoy';
  if (estado.cal && estado.cal.clave === clave && (estado.cal.cargando || (!fresco && !estado.cal.error))) return;
  const previo = estado.cal && estado.cal.clave === clave ? estado.cal.datos : null;
  estado.cal = { clave, cargando: true, datos: previo, error: '' };
  if (!previo) pintar();
  let nuevo;
  try {
    const r = await fetch(`/api/calendario${dia ? `?dia=${dia}` : ''}`, { cache: 'no-store' });
    const cuerpo = await r.json();
    if (!r.ok) throw new Error(cuerpo.error || `error ${r.status}`);
    nuevo = { clave, cargando: false, datos: cuerpo, error: '' };
  } catch (e) { nuevo = { clave, cargando: false, datos: previo, error: e.message }; }
  if (!estado.cal || estado.cal.clave !== clave) return;  // se cambió de día mientras cargaba
  estado.cal = nuevo;
  if (vistaActual() === 'cal' && calDiaHash() === dia) pintar();
}

// los eventos del día con lo que el plan dice de cada uno; un bloque del plan sin evento va aparte
function eventosCal(d) {
  const evs = (d.agenda || []).filter((e) => e.cuando && !e.todo_el_dia).map((e) => {
    const ini = aMin(hmDe(e.cuando));
    const fin = e.fin ? aMin(hmDe(e.fin)) : ini + 30;
    return { id: e.id || `${e.cuando}:${e.texto}`, titulo: e.texto, ini, fin: fin > ini ? fin : ini + 30, lugar: e.lugar || '', url: e.url || '',
             asistentes: (e.asistentes || []).filter((a) => !a.includes('resource.calendar')), soloPlan: false, plan: null };
  });
  for (const x of (d.plan && d.plan.agenda) || []) {
    if (!x.inicio) continue;
    const ini = aMin(String(x.inicio));
    const par = (x.evento && evs.find((e) => e.id === x.evento && !e.plan))
      || evs.find((e) => !e.plan && !e.soloPlan && Math.abs(e.ini - ini) <= 10 && parecidos(e.titulo, x.titulo));
    if (par) { par.plan = x; continue; }
    const fin = x.fin ? aMin(String(x.fin)) : ini + 30;
    evs.push({ id: `plan:${x.inicio}:${x.titulo}`, titulo: x.titulo || '', ini, fin: fin > ini ? fin : ini + 30, lugar: '', url: '', asistentes: [], soloPlan: true, plan: x });
  }
  return evs.sort((a, b) => a.ini - b.ini || a.fin - b.fin);
}

function notasCal(e, d) {
  const ev = d.notas || {};
  if (ev[e.id]) return ev[e.id].notas || [];
  const hm = `${String(Math.floor(e.ini / 60)).padStart(2, '0')}:${String(e.ini % 60).padStart(2, '0')}`;
  const otro = Object.values(ev).find((x) => x.inicio === hm && x.titulo && parecidos(x.titulo, e.titulo));
  return (otro && otro.notas) || [];
}

const horaMin = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

async function postCal(ruta, cuerpo) {
  const r = await fetch(ruta, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' }, body: JSON.stringify(cuerpo) });
  const resp = await r.json().catch(() => ({}));
  return r.ok && resp.ok ? resp : { ok: false, error: resp.error || `no salió (${r.status})` };
}

// un campo de texto con su botón, que guarda el borrador y dice cómo salió
function campoCal(clave, placeholder, boton, alMandar) {
  const campo = el('textarea', { rows: 2, className: 'campo', autocomplete: 'off', autocapitalize: 'sentences', maxLength: 4000, placeholder,
    'aria-label': placeholder, 'data-clave': clave, value: estado.borradores.get(clave) || '',
    oninput: () => { estado.borradores.set(clave, campo.value); crece(); },
    onblur: () => { if (estado.repintar) { estado.repintar = false; pintar(); } } });
  const crece = () => { campo.style.height = 'auto'; campo.style.height = `${Math.min(campo.scrollHeight, 160)}px`; };
  const dijo = estado.envios.get(clave);
  const manda = el('button', { type: 'button', className: 'manda', onclick: async () => {
    const texto = campo.value.trim();
    if (!texto) return;
    manda.disabled = true; estado.envios.set(clave, { t: 'enviando…', ok: null });
    const r = await alMandar(texto);
    if (r.ok) { estado.borradores.delete(clave); estado.envios.delete(clave); } else estado.envios.set(clave, { t: r.error, ok: false });
    pintar(true);
  } }, boton);
  return el('div', { className: 'cal-escribir' }, campo, manda,
    dijo ? el('div', { className: `dijo ${dijo.ok === false ? 'mal' : ''}`, textContent: dijo.t }) : null);
}

function detalleEventoCal(e, d, dia) {
  const p = e.plan || {};
  const f = p.ficha || {};
  const pares = [
    ['lugar', e.lugar],
    ['con', (p.con && p.con.length ? p.con : e.asistentes.map((a) => a.split('@')[0])).slice(0, 8).join(', ')],
    ['plan', [p.estado, p.accion ? `propone: ${p.accion}` : ''].filter(Boolean).join(' · ')], ['nota', p.nota],
    ['decisión', f.decision], ['opciones', (f.opciones || []).map((o) => `${o.id}) ${o.texto}`)], ['recomiendo', f.recomendacion],
    ['resultado', f.resultado], ['llevar', f.llevar], ['pedir', f.pedir], ['riesgo', f.riesgo], ['borrador', f.borrador]];
  const notas = notasCal(e, d);
  const clave = `cal:${dia}:${e.id}`;
  const elegir = estado.calElegir && estado.calElegir.id === e.id ? estado.calElegir : null;
  const acciones = [];
  if (e.url && /^https:\/\//.test(e.url)) acciones.push(el('a', { className: 'boton', href: e.url, target: '_blank', rel: 'noopener' }, 'entrar ↗'));
  if (!e.soloPlan && estado.yo.nuevo) {
    acciones.push(el('button', { type: 'button', onclick: async (ev) => {
      ev.target.disabled = true;
      const r = await postCal('/api/evento/reunion', { dia, id: e.id, proyecto: '' });
      if (r.ok && r.hecho === 'preguntar') { estado.calElegir = { id: e.id, candidatos: r.candidatos || [], gestion: r.gestion || 'Gestión' }; pintar(true); }
      else if (r.ok && r.hilo) { estado.recien = r.hilo; cargar(true); location.hash = hashConv(r.hilo); }
      else { estado.envios.set(`${clave}:reunion`, { t: r.error || 'no pude abrir la reunión', ok: false }); pintar(true); }
    } }, 'preparar o minuta'));
  }
  const dReunion = estado.envios.get(`${clave}:reunion`);
  return el('div', { className: 'cal-det' },
    detallePlan(pares),
    ...notas.map((n) => el('div', { className: 'cal-nota' }, txt('k', `${n.de} · ${(n.creado || '').slice(11, 16)}`), el('div', { className: 'v', style: 'white-space:pre-wrap' }, enLinea(n.texto)))),
    acciones.length ? el('div', { className: 'acciones-ev' }, ...acciones) : null,
    dReunion ? el('div', { className: 'dijo mal', textContent: dReunion.t }) : null,
    elegir ? el('div', { className: 'cal-elegir' },
      el('div', { className: 'dim' }, `¿de qué proyecto es «${e.titulo}»? Se recuerda para esta serie.`),
      ...elegir.candidatos.map((c) => el('button', { type: 'button', onclick: () => elige(c.ruta) }, c.nombre || c.ruta, el('span', { className: 'sub' }, (c.motivos || []).join(' · ')))),
      el('button', { type: 'button', onclick: () => elige('gestion') }, elegir.gestion, el('span', { className: 'sub' }, 'el agente de lo que no tiene proyecto'))) : null,
    estado.yo.escribir ? campoCal(`${clave}:nota`, 'una nota sobre esta reunión', '+ nota', async (texto) => {
      const r = await postCal('/api/evento/nota', { dia, id: e.id, texto });
      if (r.ok) cargarCal(calDiaHash(), true);
      return r;
    }) : null,
    estado.yo.escribir && d.general && !e.soloPlan ? campoCal(`${clave}:esc`, `escríbele a ${d.general.nombre} sobre esta reunión`, `enviar a ${d.general.nombre}`, async (texto) => {
      const r = await postCal('/api/evento/escribir', { dia, id: e.id, texto });
      if (r.ok) cargarCal(calDiaHash(), true);
      return r;
    }) : null);

  async function elige(proyecto) {
    const r = await postCal('/api/evento/reunion', { dia, id: e.id, proyecto });
    if (r.ok && r.hilo) { estado.calElegir = null; estado.recien = r.hilo; cargar(true); location.hash = hashConv(r.hilo); }
    else { estado.envios.set(`${clave}:reunion`, { t: r.error || 'no pude abrir la reunión', ok: false }); pintar(true); }
  }
}

// n días hacia adelante (o atrás); el día que se ve y «hoy» salen de lo último que se leyó
function moverDiaCal(n) {
  const d = estado.cal && estado.cal.datos;
  const real = (d && d.dia) || calDiaHash() || (estado.hoy && estado.hoy.fecha) || '';
  const hoyIso = (d && d.hoy) || (estado.hoy && estado.hoy.fecha) || '';
  if (!real) return;
  const f = new Date(`${real}T12:00`); f.setDate(f.getDate() + n);
  const iso = `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`;
  estado.calElegir = null; location.hash = iso === hoyIso ? '#cal' : `#cal/${iso}`;
}

// deslizar el dedo cambia de día: a la derecha el anterior, a la izquierda el siguiente. Solo vale un gesto claramente
// horizontal que no empiece sobre un campo de texto (ahí el dedo selecciona)
(() => {
  let ini = null;
  const principal = document;  // toda la pantalla, no solo la lista: con pocos eventos queda mucho vacío
  principal.addEventListener('touchstart', (e) => {
    const t = e.touches[0];
    ini = e.touches.length === 1 && vistaActual() === 'cal' && !e.target.closest('input, textarea, #barra, header')
      ? { x: t.clientX, y: t.clientY, t: Date.now() } : null;
  }, { passive: true });
  principal.addEventListener('touchend', (e) => {
    if (!ini) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - ini.x, dy = t.clientY - ini.y;
    const rapido = Date.now() - ini.t < 800;
    ini = null;
    if (rapido && Math.abs(dx) >= 60 && Math.abs(dx) > 2 * Math.abs(dy)) moverDiaCal(dx > 0 ? -1 : 1);
  }, { passive: true });
})();

function pantallaCal() {
  const c = estado.cal;
  const dia = calDiaHash();
  const d = c && c.datos;
  const real = (d && d.dia) || dia || estado.hoy && estado.hoy.fecha || '';
  const hoyIso = (d && d.hoy) || (estado.hoy && estado.hoy.fecha) || '';
  const mueve = (n) => () => moverDiaCal(n);
  const f = new Date(`${real}T12:00`);
  const etiqueta = real ? `${DIAS[f.getDay()]} ${f.getDate()} ${MESES[f.getMonth()]}${real === hoyIso ? ' · hoy' : ''}` : 'calendario';
  const nav = el('div', { className: 'plan-nav' },
    el('button', { type: 'button', 'aria-label': 'día anterior', onclick: mueve(-1) }, '‹'),
    el('span', { className: 'plan-dia', textContent: `${etiqueta}${c && c.cargando ? ' …' : ''}` }),
    el('button', { type: 'button', 'aria-label': 'día siguiente', onclick: mueve(1) }, '›'));
  const cola = real && real !== hoyIso ? el('div', { className: 'nuevo-hilo' }, el('button', { type: 'button', onclick: () => { location.hash = '#cal'; } }, 'volver a hoy')) : null;
  if (!d) return [nav, c && c.error ? el('div', { className: 'error', textContent: c.error }) : vacio('leyendo el calendario…')];
  const evs = eventosCal(d);
  const completos = (d.agenda || []).filter((e) => e.todo_el_dia);
  const esHoy = real === hoyIso;
  const ahoraMin = new Date().getHours() * 60 + new Date().getMinutes();
  const proxima = esHoy ? evs.find((e) => e.fin > ahoraMin) : null;
  const filas = evs.flatMap((e) => {
    const nNotas = notasCal(e, d).length;
    const fila = el('div', { className: `fila ag${e.fin <= ahoraMin && esHoy ? ' pasada' : ''}${proxima === e ? ' proxima' : ''}${e.soloPlan ? ' delplan' : ''}` },
      txt('hora', horaMin(e.ini)),
      el('span', { className: 'que' }, txt('titulo', e.titulo), el('span', { className: 'sub' }, `hasta ${horaMin(e.fin)}${e.lugar ? ` · ${e.lugar}` : ''}`)),
      el('span', { className: 'chips' }, nNotas || (!e.soloPlan && e.plan && e.plan.nota) ? txt('chip acc', '✎') : null));
    return plegable(`cal:${real}:${e.id}`, fila, () => detalleEventoCal(e, d, real));
  });
  return [nav,
    c.error ? el('div', { className: 'error', textContent: c.error }) : null,
    d.aviso ? el('div', { className: 'falla', textContent: d.aviso }) : null,
    ...(d.fallas || []).map((x) => el('div', { className: 'falla', textContent: `(proveedor caído · ${x})` })),
    ...completos.map((e) => el('div', { className: 'dim', style: 'padding:0 2ch', textContent: `todo el día: ${e.texto}` })),
    bloque('agenda', 'agenda', evs.length || null, null,
      ...(filas.length ? filas : [vacio(d.agenda === null ? 'sin calendario consultado' : 'nada con hora')])),
    cola];
}

// ── el plan del día ────────────────────────────────────────
async function cargarPlan() {
  try {
    const r = await fetch(`/api/plan${estado.diaPlan ? `?dia=${encodeURIComponent(estado.diaPlan)}` : ''}`, { cache: 'no-store' });
    const cuerpo = await r.json();
    if (!r.ok) throw new Error(cuerpo.error || `error ${r.status}`);
    const igual = estado.plan && JSON.stringify(estado.plan) === JSON.stringify(cuerpo);
    estado.plan = cuerpo;
    if (!igual && vistaActual() === 'plan') pintar();
  } catch (e) {
    estado.plan = { dia: '', dias: [], texto: '', error: e.message };
    if (vistaActual() === 'plan') pintar();
  }
}

function pantallaPlan() {
  const p = estado.plan;
  if (!p) return [el('div', { className: 'vacio', textContent: 'leyendo el plan…' })];
  if (p.error) return [el('div', { className: 'error', textContent: p.error })];
  if (!p.dia) return [el('div', { className: 'vacio', textContent: 'todavía no hay ningún plan escrito' })];
  const i = p.dias.indexOf(p.dia);  // los días vienen del más nuevo al más viejo
  const ir = (dia) => () => { estado.diaPlan = dia; estado.plan = null; cargarPlan(); };
  const f = new Date(`${p.dia}T12:00`);
  const etiqueta = `${DIAS[f.getDay()]} ${f.getDate()} ${MESES[f.getMonth()]}${p.dia === p.hoy ? ' · hoy' : ''}`;
  const nav = el('div', { className: 'plan-nav' },
    el('button', { type: 'button', disabled: i >= p.dias.length - 1, 'aria-label': 'plan anterior', onclick: ir(p.dias[i + 1]) }, '‹'),
    el('span', { className: 'plan-dia', textContent: etiqueta }),
    el('button', { type: 'button', disabled: i <= 0, 'aria-label': 'plan siguiente', onclick: ir(p.dias[i - 1]) }, '›'));
  // los planes de antes eran markdown; los de ahora, JSON (ver el esquema de la skill /planear)
  if (!p.plan) return [nav, el('div', { className: 'plan' }, markdown(p.texto || '', { tablas: true }))];
  return [nav, ...vistaPlan(p.plan, p.dia, p.dia === p.hoy)];
}

const minutos = (h) => Number(h.slice(0, 2)) * 60 + Number(h.slice(3, 5));
const CLASE_TIPO = { estratégico: 'est', táctico: 'tac', desbloqueo: 'des' };

// un plegable: tocar la fila abre o cierra su detalle (el estado se guarda por clave, como las demás filas)
function plegable(clave, fila, detalle) {
  const abierto = estado.abiertos.has(clave);
  fila.classList.add('clic');
  fila.setAttribute('role', 'button'); fila.tabIndex = 0; fila.setAttribute('aria-expanded', String(abierto));
  fila.onclick = () => { estado.abiertos.has(clave) ? estado.abiertos.delete(clave) : estado.abiertos.add(clave); pintar(); };
  return abierto ? [fila, detalle()] : [fila];
}

// pares clave → valor; un valor con lista va una línea por elemento
function detallePlan(pares) {
  const filas = pares.filter(([, v]) => v && (!Array.isArray(v) || v.length));
  return el('div', { className: 'ag-det' }, filas.flatMap(([k, v]) => [
    txt('k', k),
    el('span', { className: 'v' }, Array.isArray(v) ? v.map((x) => el('div', {}, g('•'), ' ', enLinea(x))) : enLinea(v))]));
}

function vistaPlan(plan, dia, esHoy) {
  const r = plan.resumen || {};
  const carga = r.carga || {};
  const pct = carga.tope_min ? Math.min(100, Math.round(((carga.enfocado_min || 0) / carga.tope_min) * 100)) : 0;
  const ahoraMin = new Date().getHours() * 60 + new Date().getMinutes();
  const out = [];

  out.push(el('section', { className: 'plan-resumen' },
    el('div', { className: 'pr-txt' }, enLinea(r.texto || '')),
    r.riesgo ? el('div', { className: 'pr-riesgo' }, g('!'), ' ', enLinea(r.riesgo)) : null,
    carga.tope_min ? el('div', { className: 'carga', title: 'trabajo enfocado planificado contra el tope del día' },
      el('span', { className: 'carga-barra' }, el('span', { className: 'carga-lleno', style: `width:${pct}%` })),
      txt('dim', `${carga.enfocado_min} de ${carga.tope_min} min enfocados${carga.reuniones_h ? ` · ${String(carga.reuniones_h).replace('.', ',')} h de agenda` : ''}`)) : null,
    plan.borrador ? el('div', { className: 'dim' }, 'borrador: las prioridades de la semana no están aprobadas') : null));

  out.push(bloque('hilos', 'resultados', (plan.resultados || []).length, null,
    ...(plan.resultados || []).flatMap((x, k) => plegable(`plan:${dia}:res${k}`,
      el('div', { className: 'fila res' }, txt(`chip ${CLASE_TIPO[x.tipo] || ''}`, x.tipo), txt('que', x.texto)),
      () => detallePlan([['logrado si', x.logrado_si]])))));

  // la agenda: las reuniones y los bloques propios, en una sola lista; el contexto de cada una se abre al tocarla
  const items = plan.agenda || [];
  const reuniones = items.filter((a) => a.tipo === 'reunion' && !a.condicional);
  const choca = (a) => a.tipo === 'reunion' && !a.condicional && reuniones.some((o) => o !== a && minutos(a.inicio) < minutos(o.fin) && minutos(o.inicio) < minutos(a.fin));
  const proxima = esHoy ? items.find((a) => minutos(a.inicio) >= ahoraMin) : null;
  out.push(bloque('agenda', 'agenda', reuniones.length, null,
    ...items.flatMap((a, k) => {
      const f = a.ficha || {};
      const pasada = esHoy && minutos(a.fin) <= ahoraMin;
      const fila = el('div', { className: `fila ag pl ${a.tipo}${a.estrategico ? ' estrategico' : ''}${a.condicional ? ' condicional' : ''}${pasada ? ' pasada' : ''}${proxima === a ? ' proxima' : ''}` },
        txt('hora', a.inicio),
        el('span', { className: 'que' }, txt('titulo', a.titulo),
          a.nota ? el('span', { className: 'sub' }, enLinea(a.nota)) : null),
        el('span', { className: 'chips' },
          a.accion ? txt('chip acc', a.accion) : null,
          choca(a) ? txt('chip choca', 'choca') : null));
      const pares = [
        ['con', (a.con || []).join(', ')], ['lugar', a.lugar], ['invitación', a.estado],
        ['decisión', f.decision], ['llevar', f.llevar], ['pedir', f.pedir], ['resultado', f.resultado], ['riesgo', f.riesgo],
        ['opciones', (f.opciones || []).map((o) => `${o.id}) ${o.texto}`)], ['recomiendo', f.recomendacion],
        ['borrador', f.borrador], ['nota', f.nota]];
      const hayDetalle = pares.some(([, v]) => v && (!Array.isArray(v) || v.length));
      return hayDetalle ? plegable(`plan:${dia}:ag${k}`, fila, () => detallePlan(pares)) : [fila];
    })));

  const t = plan.tacticos || {};
  const noHoy = t.no_hoy || [];
  const noHoyAbierto = estado.sinVentana.has(`plan:${dia}:nohoy`);
  out.push(bloque('pendientes', 'para hoy', (t.hoy || []).length, null,
    ...(t.hoy || []).map((x) => el('div', { className: 'fila pe pl' }, txt('id', x.ref),
      el('span', { className: 'que' }, enLinea(x.texto), x.donde ? el('span', { className: 'sub' }, `→ ${x.donde}`) : null))),
    noHoy.length ? el('button', { type: 'button', className: 'mas', textContent: noHoyAbierto ? '… ocultar lo que no es de hoy' : `… ${noHoy.length} no hoy`,
      onclick: () => { noHoyAbierto ? estado.sinVentana.delete(`plan:${dia}:nohoy`) : estado.sinVentana.add(`plan:${dia}:nohoy`); pintar(); } }) : null,
    ...(noHoyAbierto ? noHoy.map((x) => el('div', { className: 'fila pe pl viejo' }, txt('id', x.ref),
      el('span', { className: 'que' }, enLinea(x.texto), x.razon ? el('span', { className: 'sub' }, x.razon) : null))) : [])));

  const fo = plan.foco || {};
  out.push(bloque('tiempo', 'foco estratégico', null, null,
    detallePlan([['prioridad', fo.prioridad], ['bloque', fo.bloque], ['primer paso', fo.paso], ['terminado', fo.terminado], ['pregunta', fo.pregunta], ['nota', fo.nota]])));

  if ((plan.personas || []).length) {
    out.push(bloque('esperan', 'personas', plan.personas.length, null,
      ...plan.personas.map((x) => el('div', { className: 'fila pl' }, txt('quien', x.quien), el('span', { className: 'que' }, enLinea(x.para))))));
  }
  if ((plan.personal || []).length) {
    out.push(bloque('otros', 'personal', null, null,
      ...plan.personal.map((x) => el('div', { className: 'fila pl' }, txt('id', x.ref || ''), el('span', { className: 'que' }, enLinea(x.texto))))));
  }
  if ((plan.proximos || []).length) {
    out.push(bloque('espejo', 'los días que vienen', null, null,
      ...plan.proximos.map((x) => el('div', { className: 'fila pl' }, txt('quien', x.dia), el('span', { className: 'que' }, enLinea(x.texto))))));
  }
  const re = plan.retrospectiva;
  if (re) {
    out.push(bloque('viejo', 'retrospectiva', null, null, detallePlan([
      ['resultados', (re.resultados || []).join(' · ')], ['imprevistos', re.imprevistos], ['energía', re.energia ? `${re.energia} de 5` : ''], ['nota', re.nota]])));
  }
  const previos = plan.comentarios || [];
  if (previos.length) {
    out.push(bloque('otros', 'comentarios', previos.length, null,
      ...previos.flatMap((c, k) => plegable(`plan:${dia}:com${k}`,
        el('div', { className: 'fila pl com' }, txt('quien', (c.cuando || '').slice(5, 16).replace('T', ' ')), el('span', { className: 'que' }, enLinea(c.texto))),
        () => detallePlan([['qué se hizo', c.resultado || 'todavía sin resultado']])))));
  }
  const huecos = plan.huecos || [];
  if (huecos.length) {
    const abierto = estado.sinVentana.has(`plan:${dia}:huecos`);
    out.push(el('section', { className: 'bloque otros' },
      el('button', { type: 'button', className: 'mas', textContent: abierto ? '… ocultar lo que falta ver' : `… ${huecos.length} datos que faltan`,
        onclick: () => { abierto ? estado.sinVentana.delete(`plan:${dia}:huecos`) : estado.sinVentana.add(`plan:${dia}:huecos`); pintar(); } }),
      ...(abierto ? [detallePlan(huecos.map((h, k) => [String(k + 1), h]))] : [])));
  }
  if (estado.yo.plan_comentar) out.push(cuadroComentario(dia));
  return out;
}

// el cuadro de abajo del plan: un comentario abre una sesión de agente que entiende qué cambia (el plan, la skill, un proyecto…)
function cuadroComentario(dia) {
  const clave = `plan-comentario:${dia}`;
  const campo = el('textarea', {
    rows: 3, className: 'campo', maxLength: 4000, autocomplete: 'off', autocapitalize: 'sentences', 'data-clave': clave,
    placeholder: 'Comentarios sobre este plan: contexto que falta, algo que corregir…', 'aria-label': 'comentario sobre el plan',
    value: estado.borradores.get(clave) || '',
    oninput: () => { estado.borradores.set(clave, campo.value); },
    onfocus: () => document.body.classList.add('escribiendo'),
    onblur: () => document.body.classList.remove('escribiendo'),
  });
  const dijo = el('div', { className: 'dijo' });
  const boton = el('button', { type: 'button', className: 'manda' }, 'enviar comentario');
  boton.onclick = async () => {
    const texto = campo.value.trim();
    if (!texto) return;
    boton.disabled = true; dijo.className = 'dijo'; dijo.textContent = 'abriendo una sesión…';
    try {
      const r = await fetch('/api/plan/comentar', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' },
        body: JSON.stringify({ dia, texto }) });
      const cuerpo = await r.json().catch(() => ({}));
      if (r.ok && cuerpo.ok) {
        estado.borradores.delete(clave); campo.value = '';
        dijo.className = 'dijo bien';
        dijo.replaceChildren(`Se abrió «${cuerpo.hilo}». `, el('a', { href: '#hilos' }, 'verlo en hilos'));
        setTimeout(() => cargarPlan(), 20000);  // la sesión anota el comentario en el plan
      } else { dijo.className = 'dijo mal'; dijo.textContent = cuerpo.error || `no salió (${r.status})`; }
    } catch (e) { dijo.className = 'dijo mal'; dijo.textContent = 'sin conexión con el servidor'; }
    boton.disabled = false;
  };
  return el('section', { className: 'comenta' }, campo, el('div', { className: 'comenta-pie' }, dijo, boton));
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
  aviso.className = 'dim';
  $('menu').classList.remove('mal');
  try {
    const [hoy, hilos, fotos, yo] = await Promise.all([pedir('hoy', fresco), pedir('hilos', fresco), pedir('espejos'), pedir('yo')]);
    // la edad de una foto crece sola: para saber si algo cambió se mira lo demás y si sigue en línea
    const crudo = JSON.stringify([hoy, hilos, yo, (fotos.espejos || []).map((e) => [e.nombre, e.en_linea, e.recibido, e.error])]);
    const cambio = crudo !== estado.crudo || estado.error;
    Object.assign(estado, { hoy, hilos, yo, espejos: fotos.espejos || [], crudo, error: '' });
    if (yo.plan && (vistaActual() === 'plan' || !estado.plan)) cargarPlan();
    aviso.textContent = `· ${hhmm(new Date())}`;
    if (cambio) pintar();
  } catch (e) {
    estado.error = e.message;
    aviso.textContent = '· sin conexión';
    aviso.className = 'mal';
    $('menu').classList.add('mal');
    pintar();
  }
}

// ── la conversación de un hilo ─────────────────────────────
// Se pide por páginas (`/api/conversacion`): al abrir, los últimos; «… N anteriores» va hacia atrás; cada 3 s se
// piden los que llegaron después. Los mensajes están numerados por su posición, así que agregar es solo agregar.
// `origen` vacío es un hilo de esta máquina (mensajes numerados: «anteriores», «lo que llegó después»); con un nombre
// es un hilo de otra máquina, que entrega sus últimos N turnos por la puerta: «más turnos» y volver a pedir.
const conv = { nombre: '', origen: '', sesion: '', sesiones: [], msgs: [], desde: 0, total: 0, hilo: null, error: '', nuevos: 0,
               expandidos: new Set(), timer: 0, cargando: false, turnos: 10, totalTurnos: 0, fuente: '', firma: '' };

const hashConv = (nombre, origen = '') => `#hilos/${encodeURIComponent(nombre)}${origen ? `@${encodeURIComponent(origen)}` : ''}`;
function refConv() {
  const r = location.hash.slice('#hilos/'.length);
  const i = r.lastIndexOf('@');
  return i < 0 ? { nombre: decodeURIComponent(r), origen: '' } : { nombre: decodeURIComponent(r.slice(0, i)), origen: decodeURIComponent(r.slice(i + 1)) };
}
const renglon = () => parseFloat(getComputedStyle(document.body).lineHeight) || 22;
const alFinal = () => scrollTo(0, document.documentElement.scrollHeight);
const pegado = () => innerHeight + scrollY >= document.documentElement.scrollHeight - 4 * renglon();
const dia = (iso) => { const f = new Date(iso); return isNaN(f) ? '' : `${DIAS[f.getDay()]} ${f.getDate()} ${MESES[f.getMonth()]}`; };
const claveDia = (iso) => (iso || '').slice(0, 10);

function soltarConversacion() {
  if (conv.timer) { clearInterval(conv.timer); conv.timer = 0; }
  if (conv.nombre) { conv.nombre = ''; conv.origen = ''; document.body.classList.remove('escribiendo', 'en-conv'); document.documentElement.style.removeProperty('--dock-h'); }
}

async function pedirConv(params) {
  const q = new URLSearchParams({ hilo: conv.nombre, ...(conv.origen ? { maquina: conv.origen } : {}), ...params });
  const r = await fetch(`/api/conversacion?${q}`, { cache: 'no-store' });
  const cuerpo = await r.json();
  if (!r.ok) throw new Error(cuerpo.error || `error ${r.status}`);
  return cuerpo;
}

// texto con `código`, **negrita** y [enlaces](https://…) → nodos
function enLinea(texto) {
  const nodos = [];
  const re = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\))/g;
  let i = 0;
  for (let m = re.exec(texto); m; m = re.exec(texto)) {
    if (m.index > i) nodos.push(...celdas(texto.slice(i, m.index)));
    const t = m[0];
    if (t[0] === '`') nodos.push(el('code', {}, celdas(t.slice(1, -1))));
    else if (t[0] === '*') nodos.push(el('b', {}, celdas(t.slice(2, -2))));
    else { const [, nombre, url] = /\[([^\]]+)\]\(([^)]+)\)/.exec(t); nodos.push(el('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, celdas(nombre))); }
    i = m.index + t.length;
  }
  if (i < texto.length) nodos.push(...celdas(texto.slice(i)));
  return nodos;
}

// una tabla de markdown como filas apilables: la primera columna a la izquierda, lo demás debajo (en el celular una tabla ancha no se lee)
function tablaTarjetas(filas) {
  const partir = (f) => f.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
  const cuerpo = filas.filter((f) => !/^\s*\|[\s:|-]+\|?\s*$/.test(f)).slice(1).map(partir);  // sin la cabecera ni la regla
  return el('div', { className: 'blq tabla' }, cuerpo.map(([primera, segunda, ...resto]) => el('div', { className: 'fila-t' },
    el('span', { className: 'c1' }, enLinea(primera || '')),
    el('span', { className: 'c2' }, enLinea(segunda || '')),
    resto.length && resto.join('') ? el('span', { className: 'c3' }, enLinea(resto.join(' · '))) : null)));
}

// el markdown que escriben los agentes, sin dependencias: cercados de código, títulos, listas, tablas y párrafos
const ES_LISTA = /^\s*([-*•]|\d+[.)])\s+/;
const ES_BLOQUE = (l) => /^\s*```/.test(l) || /^\s*#{1,6}\s/.test(l) || ES_LISTA.test(l) || /^\s*\|/.test(l);
function markdown(texto, { tablas = false } = {}) {
  const lineas = String(texto).replace(/\r\n?/g, '\n').split('\n');
  const bloques = [];
  let i = 0;
  while (i < lineas.length) {
    const l = lineas[i];
    if (/^\s*```/.test(l)) {
      const cod = [];
      for (i++; i < lineas.length && !/^\s*```/.test(lineas[i]); i++) cod.push(lineas[i]);
      i++;
      bloques.push(el('div', { className: 'blq codigo' }, celdas(cod.join('\n'))));
    } else if (!l.trim()) {
      i++;
    } else if (/^\s*#{1,6}\s/.test(l)) {
      bloques.push(el('div', { className: `blq tit n${/^\s*(#+)/.exec(l)[1].length}` }, enLinea(l.replace(/^\s*#{1,6}\s+/, ''))));
      i++;
    } else if (ES_LISTA.test(l)) {
      const items = [];
      for (; i < lineas.length && ES_LISTA.test(lineas[i]); i++) {
        const m = /^(\s*)([-*•]|\d+[.)])\s+(.*)$/.exec(lineas[i]);
        items.push(el('div', { className: 'li', style: `--n:${Math.min(2, Math.floor(m[1].length / 2))}` },
          el('span', { className: 'marca-li' }, /\d/.test(m[2]) ? m[2] : '•'), el('span', { className: 'li-t' }, enLinea(m[3]))));
      }
      bloques.push(el('div', { className: 'blq lista' }, items));
    } else if (/^\s*\|/.test(l)) {
      const filas = [];
      for (; i < lineas.length && /^\s*\|/.test(lineas[i]); i++) filas.push(lineas[i]);
      bloques.push(tablas ? tablaTarjetas(filas) : el('div', { className: 'blq codigo' }, celdas(filas.join('\n'))));
    } else {
      const par = [];
      for (; i < lineas.length && lineas[i].trim() && !ES_BLOQUE(lineas[i]); i++) par.push(lineas[i]);
      bloques.push(el('div', { className: 'blq parr' }, par.flatMap((x, k) => (k ? [document.createElement('br'), ...enLinea(x)] : enLinea(x)))));
    }
  }
  return bloques;
}

// un mensaje: quién y a qué hora, y su cuerpo; los largos van recogidos hasta que se toca «ver todo»
function nodoMensaje(m, i) {
  const largo = m.texto.length > 1500 || (m.texto.match(/\n/g) || []).length > 22;
  const abierto = conv.expandidos.has(i);
  const f = new Date(m.hora);
  const cuerpo = el('div', { className: `cuerpo${largo && !abierto ? ' recogido' : ''}` },
    m.quien === 'panel' ? el('div', { className: 'blq codigo' }, celdas(m.texto)) : markdown(m.texto));
  return el('div', { className: `msg ${m.quien}`, 'data-i': String(i) },
    el('div', { className: 'de' }, txt('quien', m.quien), isNaN(f) ? null : txt('cuando', hhmm(f))),
    cuerpo,
    m.recortado ? el('div', { className: 'nota', textContent: `… se recortó: faltan ${m.recortado} caracteres` }) : null,
    largo ? el('button', { type: 'button', className: 'mas-msg', textContent: abierto ? '▴ recoger' : '▾ ver todo', onclick: () => {
      conv.expandidos.has(i) ? conv.expandidos.delete(i) : conv.expandidos.add(i);
      const antes = $('conv-lista').querySelector(`[data-i="${i}"]`);
      if (antes) antes.replaceWith(nodoMensaje(m, i));
    } }) : null);
}

// las herramientas que usó el agente, una línea cada una; si son muchas seguidas, tres y «… +N»
function nodoHerramientas(grupo) {
  const clave = `g${grupo[0].i}`;
  const abierto = conv.expandidos.has(clave);
  const visibles = abierto || grupo.length <= 3 ? grupo : grupo.slice(0, 3);
  return el('div', { className: 'tools', 'data-i': String(grupo[0].i) },
    visibles.map(({ m }) => el('div', { className: 'tool' }, g('›'), txt('una', m.texto))),
    grupo.length > 3 ? el('button', { type: 'button', className: 'mas-tools', textContent: abierto ? '  ▴ recoger' : `  … +${grupo.length - 3} más`, onclick: () => {
      conv.expandidos.has(clave) ? conv.expandidos.delete(clave) : conv.expandidos.add(clave);
      const antes = $('conv-lista').querySelector(`.tools[data-i="${grupo[0].i}"]`);
      if (antes) antes.replaceWith(nodoHerramientas(grupo));
    } }) : null);
}

// los mensajes [desde, desde+n) como nodos, con la fecha cuando cambia el día y las herramientas en grupo
function nodosDe(msgs, desde, diaPrevio) {
  const nodos = [];
  let previo = diaPrevio;
  let grupo = [];
  const cerrar = () => { if (grupo.length) { nodos.push(nodoHerramientas(grupo)); grupo = []; } };
  msgs.forEach((m, k) => {
    const d = claveDia(m.hora);
    if (d && d !== previo) { cerrar(); nodos.push(el('div', { className: 'dia', 'data-dia': d }, `── ${dia(m.hora)} ──`)); previo = d; }
    if (m.quien === 'herramienta') grupo.push({ m, i: desde + k });
    else { cerrar(); nodos.push(nodoMensaje(m, desde + k)); }
  });
  cerrar();
  return nodos;
}

function cabeceraConv() {
  const h = conv.hilo || {};
  const dice = h.atencion && NOMBRE_ATENCION[h.atencion] ? NOMBRE_ATENCION[h.atencion] : (h.vivo || h.propio ? 'abierto' : 'sin ventana');
  const sesiones = conv.sesiones.length > 1 ? el('button', { type: 'button', className: 'sesion', onclick: cambiarSesion,
    textContent: `${conv.sesiones.indexOf(conv.sesion) + 1}/${conv.sesiones.length}`, title: 'otra conversación de este hilo' }) : null;
  $('conv-cab').replaceChildren(...[
    el('button', { type: 'button', className: 'volver', onclick: volver }, g('‹'), ' hilos'),
    txt('nombre una', conv.nombre),
    conv.origen ? txt('donde', `en ${conv.origen}`) : null,
    el('span', { className: `estado-conv ${h.atencion || ''}` }, g(GLIFO[h.atencion] || '·', `at ${h.atencion || 'ninguna'}`), ` ${dice}`),
    sesiones].filter(Boolean));
}

// atrás si se llegó navegando dentro de la página (así se vuelve a donde se estaba); si se abrió directo, a la lista de hilos
let navegaciones = 0;
addEventListener('hashchange', () => { navegaciones++; });
function volver() { if (navegaciones > 0) history.back(); else location.hash = '#hilos'; }

function masAntes() {
  if (conv.origen) {  // la otra máquina entrega turnos, no mensajes numerados: se piden más
    if (conv.fuente === 'panel' || conv.turnos >= 50 || conv.totalTurnos <= conv.turnosVistos) return [];
    return [el('button', { type: 'button', className: 'mas antes', textContent: `… ${conv.totalTurnos - conv.turnosVistos} turnos anteriores`, onclick: masTurnos })];
  }
  if (conv.desde <= 0) return [];
  return [el('button', { type: 'button', className: 'mas antes', textContent: `… ${conv.desde} anteriores`, onclick: cargarAnteriores })];
}

async function masTurnos() {
  conv.turnos = Math.min(50, conv.turnos + 10);
  await traerRemoto(true);
}
function pintarMas() { $('conv-mas').replaceChildren(...masAntes()); }

async function cargarAnteriores() {
  if (conv.cargando || conv.desde <= 0) return;
  conv.cargando = true;
  try {
    const r = await pedirConv({ antes: conv.desde, sesion: conv.sesion });
    const alto = document.documentElement.scrollHeight;
    const lista = $('conv-lista');
    const primerDia = lista.firstElementChild && lista.firstElementChild.dataset.dia;
    conv.msgs = [...r.mensajes, ...conv.msgs];
    conv.desde = r.desde;
    const nodos = nodosDe(r.mensajes, r.desde, '');
    const ultimo = r.mensajes.length ? claveDia(r.mensajes[r.mensajes.length - 1].hora) : '';
    if (primerDia && primerDia === ultimo) lista.firstElementChild.remove();  // el mismo día: una sola fecha
    lista.prepend(...nodos);
    pintarMas();
    scrollTo(0, scrollY + document.documentElement.scrollHeight - alto);      // lo que se leía no se mueve
  } catch (e) { $('conv-mas').replaceChildren(el('div', { className: 'falla', textContent: e.message })); }
  conv.cargando = false;
}

function agregar(r) {
  // dos sondeos en vuelo piden desde el mismo punto (el de cada 3 s y los que se disparan al enviar):
  // el que llega segundo trae lo que el primero ya puso, y se descarta en vez de duplicarlo
  if (!r.mensajes.length || r.desde !== conv.total) return;
  const lista = $('conv-lista');
  const estabaAlFinal = pegado();
  const ultimoDia = conv.msgs.length ? claveDia(conv.msgs[conv.msgs.length - 1].hora) : '';
  conv.msgs.push(...r.mensajes);
  conv.total = r.hasta;
  lista.append(...nodosDe(r.mensajes, r.desde, ultimoDia));
  if (estabaAlFinal) { alFinal(); conv.nuevos = 0; } else conv.nuevos += r.mensajes.length;
  pintarNuevos();
}
function pintarNuevos() {
  const b = $('conv-nuevos');
  if (!b) return;
  b.hidden = !conv.nuevos;
  b.textContent = `↓ ${conv.nuevos} nuevo${conv.nuevos === 1 ? '' : 's'}`;
}

// un hilo de otra máquina: se piden sus últimos N turnos y, si algo cambió, se redibuja todo
function dibujarRemoto(r, alPie) {
  conv.msgs = r.mensajes;
  conv.total = r.hasta;
  conv.fuente = r.fuente;
  conv.totalTurnos = r.total_turnos || 0;
  conv.turnosVistos = r.turnos || 0;
  conv.hilo = r.hilo;
  cabeceraConv();
  const lista = $('conv-lista');
  const alto = document.documentElement.scrollHeight;
  lista.replaceChildren(...nodosDe(r.mensajes, 0, ''));
  if (!r.mensajes.length) avisoConv('la conversación todavía no tiene mensajes');
  pintarMas();
  if (alPie) alFinal(); else scrollTo(0, scrollY + document.documentElement.scrollHeight - alto);
}

async function traerRemoto(masViejos = false) {
  if (conv.cargando) return;
  conv.cargando = true;
  try {
    const r = await pedirConv({ turnos: String(conv.turnos) });
    const firma = JSON.stringify(r.mensajes.map((m) => [m.quien, m.hora, m.texto.length]));
    if (firma !== conv.firma || masViejos) {
      const estaba = pegado();
      conv.firma = firma;
      dibujarRemoto(r, estaba && !masViejos);
      if (!estaba && !masViejos) { conv.nuevos += 1; pintarNuevos(); }
    } else { conv.hilo = r.hilo; cabeceraConv(); }
  } catch (e) {
    if ($('conv-lista') && !conv.msgs.length) avisoConv(e.message);
  }
  conv.cargando = false;
}

async function sondear() {
  if (vistaActual() !== 'conversacion' || !conv.nombre) { soltarConversacion(); return; }
  if (document.hidden || conv.cargando) return;
  if (conv.origen) { traerRemoto(); return; }
  try {
    const r = await pedirConv({ despues: conv.total, sesion: conv.sesion });
    if (r.total < conv.total) { abrirConversacion(conv.nombre, '', conv.sesion); return; }  // se reescribió: se vuelve a leer
    conv.hilo = r.hilo;
    cabeceraConv();
    agregar(r);
  } catch (e) { /* sin red un momento: el próximo intento lo dice si sigue */ }
}

function cambiarSesion() {
  const i = (conv.sesiones.indexOf(conv.sesion) + 1) % conv.sesiones.length;
  abrirConversacion(conv.nombre, '', conv.sesiones[i]);
}

// lo que se ve sin conversación que mostrar (hilo remoto, sin archivo…)
function avisoConv(texto) { $('conv-lista').replaceChildren(el('div', { className: 'vacio', textContent: texto })); pintarMas(); }

function puedeConv() {
  return !!(estado.yo.escribir && conv.hilo && (conv.hilo.vivo || conv.hilo.propio) && (!conv.origen || (conv.hilo.en_linea && estado.yo.enlaces.length)));
}

function dockConv() {
  const puede = conv.puede = puedeConv();
  if (!puede) {
    document.documentElement.style.removeProperty('--dock-h');
    return el('div', { id: 'dock', className: 'dock solo' },
      txt('dim', !estado.yo.escribir ? 'solo lectura · `telar web --escribir` para contestar' : 'sin ventana abierta: no se le puede escribir'));
  }
  // en el celular Enter es salto de línea (se manda con el botón); con teclado, Enter manda y Shift+Enter salta
  const tactil = matchMedia('(pointer: coarse)').matches;
  const campo = el('textarea', {
    rows: 1, className: 'campo', autocomplete: 'off', autocapitalize: 'sentences', enterKeyHint: tactil ? 'enter' : 'send', maxLength: 8000,
    oninput: () => crece(),
    placeholder: `escribirle a ${conv.nombre}`, 'aria-label': `escribirle a ${conv.nombre}`,
    onfocus: () => document.body.classList.add('escribiendo'),
    onblur: () => document.body.classList.remove('escribiendo'),
  });
  const crece = () => {  // alto de renglones enteros, hasta el tope que pone el CSS
    campo.style.height = 'auto';
    campo.style.height = `${Math.min(campo.scrollHeight, parseFloat(getComputedStyle(campo).maxHeight))}px`;
  };
  const dijo = el('div', { className: 'dijo', id: 'dock-dijo' });
  const enviar = async () => {
    const texto = campo.value.trim();
    if (!texto) return;
    dijo.className = 'dijo'; dijo.textContent = 'enviando…';
    try {
      const r = await fetch('/api/enviar', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Telar': '1' },
        body: JSON.stringify({ maquina: conv.origen, hilo: conv.nombre, texto, enter: true }) });
      const cuerpo = await r.json().catch(() => ({}));
      if (r.ok && cuerpo.ok) {
        campo.value = ''; crece();
        dijo.className = 'dijo'; dijo.textContent = '';  // lo enviado aparece en la conversación: no hace falta decirlo
        for (const ms of conv.origen ? [1500, 4000, 8000] : [600, 2000, 5000]) setTimeout(sondear, ms);  // aparece en cuanto el agente lo anota
      } else { dijo.className = 'dijo mal'; dijo.textContent = cuerpo.error || `no salió (${r.status})`; }
    } catch (e) { dijo.className = 'dijo mal'; dijo.textContent = 'sin conexión con el servidor'; }
  };
  campo.onkeydown = (e) => {
    if (e.key !== 'Enter' || e.isComposing) return;
    if (e.ctrlKey || e.metaKey || (!tactil && !e.shiftKey)) { e.preventDefault(); enviar(); }
  };
  const dock = el('div', { id: 'dock', className: 'dock' },
    el('div', { className: 'linea-dock' }, g('›', 'prompt'), campo,
      el('button', { type: 'button', className: 'manda', onclick: enviar }, 'enviar')),
    dijo);
  // lo que mide el cuadro se lo dice al resto de la página: la conversación deja ese espacio abajo
  new ResizeObserver(() => document.documentElement.style.setProperty('--dock-h', `${dock.offsetHeight}px`)).observe(dock);
  return dock;
}

function armarConv(nombre, origen) {
  soltarConversacion();
  conv.nombre = nombre;
  conv.origen = origen;
  document.body.classList.add('en-conv');
  $('vista').replaceChildren(el('div', { id: 'conv' },
    el('div', { id: 'conv-cab' }), el('div', { id: 'conv-mas' }), el('div', { id: 'conv-lista' }),
    el('button', { type: 'button', id: 'conv-nuevos', hidden: true, onclick: () => { conv.nuevos = 0; pintarNuevos(); alFinal(); } })));
}

async function abrirConversacion(nombre, origen = '', sesion = '') {
  if (location.hash !== hashConv(nombre, origen)) location.hash = hashConv(nombre, origen);
  armarConv(nombre, origen);
  Object.assign(conv, { sesion, sesiones: [], msgs: [], desde: 0, total: 0, hilo: null, error: '', nuevos: 0, expandidos: new Set(),
                        cargando: true, turnos: 10, totalTurnos: 0, turnosVistos: 0, fuente: '', firma: '' });
  const fuente = origen ? ((estado.espejos.find((e) => e.nombre === origen) || {}).hilos || []) : (estado.hilos && estado.hilos.hilos || []);
  const local = fuente.find((h) => h.nombre === nombre);
  conv.hilo = local ? { nombre, atencion: local.atencion, vivo: local.vivo, propio: local.propio, en_linea: true }
    // recién abierto: la lista del día aún no lo trae, pero tiene sesión propia y se le puede escribir
    : estado.recien === nombre && !origen ? { nombre, atencion: '', vivo: false, propio: true, en_linea: true } : null;
  cabeceraConv();
  $('conv-lista').replaceChildren(el('div', { className: 'vacio', textContent: origen ? `pidiéndole la conversación a ${origen}…` : 'leyendo la conversación…' }));
  try {
    if (origen) {  // otra máquina: sus últimos turnos, y se vuelve a pedir cada 5 s
      const r = await pedirConv({ turnos: String(conv.turnos) });
      conv.firma = JSON.stringify(r.mensajes.map((m) => [m.quien, m.hora, m.texto.length]));
      dibujarRemoto(r, true);
      $('conv').append(dockConv());
      alFinal();
      conv.timer = setInterval(sondear, 5000);
      conv.cargando = false;
      return;
    }
    const r = await pedirConv(sesion ? { sesion } : {});
    Object.assign(conv, { sesion: r.sesion, sesiones: r.sesiones, msgs: r.mensajes, desde: r.desde, total: r.hasta, hilo: r.hilo });
    if (estado.recien === nombre) estado.recien = '';  // ya tiene conversación: deja de ser «recién abierto»
    cabeceraConv();
    $('conv-lista').replaceChildren(...nodosDe(r.mensajes, r.desde, ''));
    if (!r.mensajes.length) avisoConv('la conversación todavía no tiene mensajes');
    pintarMas();
    $('conv').append(dockConv());
    alFinal();
    conv.timer = setInterval(sondear, 3000);
  } catch (e) {
    if (estado.recien === nombre && !origen) {
      // un hilo recién abierto no tiene conversación en disco hasta su primer mensaje: no es un error, se espera sin repintar
      avisoConv('El hilo está abierto. La conversación aparece cuando el agente reciba su primer mensaje; mientras tanto puedes escribirle abajo.');
      $('conv').append(dockConv());
      let intentos = 0;
      conv.timer = setInterval(async () => {
        if (conv.nombre !== nombre || ++intentos > 100) { clearInterval(conv.timer); return; }
        try { await pedirConv({}); abrirConversacion(nombre); } catch (_) { /* todavía no está */ }
      }, 3000);
    } else {
      avisoConv(e.message);
      $('conv').append(dockConv());
    }
  }
  conv.cargando = false;
}

function pintarConversacion() {
  const { nombre, origen } = refConv();
  if (conv.nombre !== nombre || conv.origen !== origen || !$('conv')) { abrirConversacion(nombre, origen); return; }
  if (conv.hilo && !conv.origen) {  // el semáforo del hilo viene del día; se refresca sin tocar los mensajes
    const h = (estado.hilos && estado.hilos.hilos || []).find((x) => x.nombre === conv.nombre);
    if (h) { conv.hilo = { nombre: h.nombre, atencion: h.atencion, vivo: h.vivo, propio: h.propio }; cabeceraConv(); }
  }
  // si la página abrió la conversación antes de saber si puede escribir (recarga directa a ella), el
  // cuadro quedó de solo lectura: se rehace cuando eso cambia, y solo entonces, para no pisar lo que se escribe
  if ($('dock') && !conv.cargando && conv.puede !== puedeConv()) $('dock').replaceWith(dockConv());
}

// ── tema: oscuro por defecto, claro si se elige (la cabecera lo pone antes de pintar) ──
const tema = () => (document.documentElement.dataset.tema === 'claro' ? 'claro' : 'oscuro');
function pintarTema() {
  const claro = tema() === 'claro';
  // el botón dice a qué se pasa, no en cuál se está
  $('icono-tema').textContent = claro ? '☾' : '☀';
  $('texto-tema').textContent = claro ? 'tema oscuro' : 'tema claro';
  document.querySelector('meta[name=color-scheme]').content = claro ? 'light' : 'dark';
  document.querySelector('meta[name=theme-color]').content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
}
function alternarTema() {
  const nuevo = tema() === 'claro' ? 'oscuro' : 'claro';
  if (nuevo === 'claro') document.documentElement.dataset.tema = 'claro'; else delete document.documentElement.dataset.tema;
  guardado('telar.tema', nuevo === 'claro' ? 'claro' : 'oscuro');
  pintarTema();
}
$('tema').onclick = () => { alternarTema(); cerrarMenu(); };

// ── vida de la página ──────────────────────────────────────
addEventListener('hashchange', () => { scrollTo(0, 0); pintar(); });
$('recargar').onclick = () => { cargar(true); cerrarMenu(); };
// el menú de arriba a la derecha: tema y actualizar. Se cierra al elegir, al tocar fuera y con Escape.
function cerrarMenu() { $('menu-panel').hidden = true; $('menu').setAttribute('aria-expanded', 'false'); }
$('menu').onclick = (e) => {
  e.stopPropagation();
  const abrir = $('menu-panel').hidden;
  $('menu-panel').hidden = !abrir;
  $('menu').setAttribute('aria-expanded', String(abrir));
};
document.addEventListener('click', (e) => { if (!$('menu-panel').hidden && !e.target.closest('.der')) cerrarMenu(); });
addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || /input|textarea/i.test(e.target.tagName)) return;
  if (e.key === 'Escape' && !$('menu-panel').hidden) cerrarMenu();
  else if (e.key === 'Escape' && vistaActual() === 'conversacion') volver();
  else if (e.key === '1') location.hash = '#hoy';
  else if (e.key === '2') location.hash = '#hilos';
  else if (e.key === '3' && estado.yo.plan) location.hash = '#plan';
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
