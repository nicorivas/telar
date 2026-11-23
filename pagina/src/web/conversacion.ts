// Un hilo leído como conversación (la vista del celular): los últimos turnos (`/api/hilos/leer`, releídos cada
// pocos segundos), una caja para escribirle y las teclas para contestarle una pregunta (⏎, ⎋, 1-3, ↑↓). A un
// hilo de aquí, lo escrito va por el mismo canal que la terminal (`/pty`, una vista de `telar mirar`): es teclear
// en el hilo, con la misma llave. A uno de otra máquina, como mensaje de la persona (`/api/mensajes`, por el bus).
// Lo que el agente pregunta con opciones (AskUserQuestion) se contesta en el pie, en el lugar de la caja
// (web/pregunta.ts), y la respuesta va a su diálogo por `/api/hilos/responder`.
// Lo escrito en la caja (y en «otra respuesta» de una pregunta) se guarda mientras se escribe: recargar la página no lo
// pierde (web/guardado.ts, web/recarga.ts). Se dibuja en un elemento de la página; sus estilos, en
// media/css/conversacion.css (con @scope, en `.v-conversacion`).

import MarkdownIt from 'markdown-it';
import { modelo } from '../modelo';
import { C, I } from './iconos';
import { circulo, type Circulo } from '../componentes/circulo';
import * as ui from './ui';
import { skillsDe } from './instruccion';
import { atenderClics, enlazar } from './rutas-agente';
import type { RutasVista, Vista } from './vistas-hilo';
import { formulario, registro, type Formulario, type Pregunta } from './pregunta';
import * as guardado from './guardado';
import * as recarga from './recarga';
import * as cli from '../cli';
import { fueraDe, panelFuera } from './alcance';
import { abreAlEscribir } from './dormidos';

interface Mensaje { quien: string; texto?: string; pregunta?: Pregunta }
interface Leido { error?: string; fuente?: string; texto?: string; turnos?: Mensaje[][]; total_turnos?: number; recortado?: boolean }

/** el markdown del agente (el HTML que traiga se escapa) */
const md = new MarkdownIt({ html: false, linkify: true });

/** lo que de la API de dictado del navegador se usa */
interface DictadoEvento { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }
interface Dictador {
    lang: string; continuous: boolean; interimResults: boolean;
    onresult: ((e: DictadoEvento) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null;
    start(): void; abort(): void;
}

const QUIEN: Record<string, string> = { usuario: 'tú', agente: 'agente', herramienta: '·' };

/** De quién es un mensaje, como un círculo leve en la ranura de su izquierda (gramática visual: el color de un círculo
 *  dice de quién es). La persona, en el acento; el agente, en el de los agentes; lo que llegó de otro hilo o agente por el
 *  bus, la figura «viene de afuera» (un satélite). El nombre queda en su ayuda. */
const MARCA: Record<string, Circulo> = { usuario: { tam: 'chico' }, agente: { tam: 'chico' }, bus: { figura: 'satelite' }, espera: { tam: 'chico', lleno: 0 } };
function marca(clase: 'usuario' | 'agente' | 'bus' | 'espera', ayuda: string): HTMLElement {
    const m = el('span', `marca ${clase}`);
    m.innerHTML = circulo(MARCA[clase]);
    m.title = ayuda;
    return m;
}

/** Un turno «tuyo» que no escribió la persona: lo que tecleó el nodo para que entrara un mensaje del bus («↯ mensaje
 *  nuevo · mensaje de Mobile: …», telar.casilla `aviso`). Su etiqueta dice de quién vino; null si es de la persona (o
 *  «tu persona: …», lo que ella mandó desde otra parte). */
function delBus(texto: string): string | null {
    if (!texto.startsWith('↯ mensaje nuevo')) return null;
    const m = /^↯ mensaje nuevo · (?:(?:mensaje|encargo) de (.+?)|(tu persona)): /.exec(texto);
    if (m?.[2]) return null;
    return m?.[1] ? `↯ ${m[1]}` : '↯ mensaje';
}
/** Las teclas de abajo, para lo que el agente pregunta con opciones: lo que muestran (un ícono de la letra o el número),
 *  lo que envían, su ayuda y si es un ícono. */
const TECLAS: [string, string, string, boolean][] = [[I.hecha, '\r', 'enter: acepta lo marcado', true], [I.cerrar, '\u001b', 'escape: cancela o interrumpe', true],
    ['1', '1', 'la opción 1', false], ['2', '2', 'la opción 2', false], ['3', '3', 'la opción 3', false],
    [I.subir, '\u001b[A', 'subir', true], [I.abierto, '\u001b[B', 'bajar', true]];

/** Lo que se le escribió y todavía no aparece en la conversación: su texto y en qué va. */
interface Pendiente { texto: string; desde: number }
/** Para reconocer lo escrito en la conversación: sin espacios de más y sin el aviso del bus. */
/** Cuánto se espera a ver lo enviado en la conversación antes de decir que quedó en su casilla. */
const ESPERA_CASILLA = 5000;
const comparable = (t: string) => t.replace(/\s+/g, ' ').trim().slice(0, 60);

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

/** La dirección de un WebSocket de esta página (`/pty?…`). */
function enchufe(ruta: string): string {
    const u = new URL(ruta, location.href);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.href;
}

export function montar(raiz: HTMLElement, { hilo, maquina }: RutasVista): Vista {
    const h = maquina ? undefined : modelo.porNombre(hilo);
    // el hilo de un agente residente, cerrado: escribirle lo abre (`abreAlEscribir`)
    const loAbre = abreAlEscribir(h, modelo.secciones, modelo.hayBus);
    // un hilo de otra máquina se lee por la API y se le escribe como mensaje (por el bus): sin terminal, no hay
    // teclas que apretar. Lo mismo un agente cerrado: su nodo lo abre al llegarle
    const porMensaje = !!maquina || loAbre;
    raiz.classList.add('v-conversacion');
    raiz.innerHTML = '<main class="turnos"><p class="nada">leyendo…</p></main><footer><div class="teclas"></div>'
        + `<form class="escribir"><span class="dijo" role="status"></span><textarea rows="1"></textarea>`
        + `<button type="submit" class="enviar" title="enviar (⏎)"><span class="i">${I.enviar}</span></button></form>`
        + '</footer>';
    const $ = <T extends HTMLElement>(s: string) => raiz.querySelector<T>(s)!;
    const turnos = $('.turnos'), texto = $<HTMLTextAreaElement>('textarea'), dijo = $('.dijo'), form = $<HTMLFormElement>('.escribir');
    const boton = $<HTMLButtonElement>('button.enviar');
    // la caja crece con lo escrito, hasta ocho líneas; vacía, una
    const crecer = () => { texto.style.height = 'auto'; texto.style.height = `${Math.min(texto.scrollHeight, 8 * parseFloat(getComputedStyle(texto).lineHeight || '20') + 16)}px`; };
    texto.addEventListener('input', () => { crecer(); boton.classList.toggle('listo', !!texto.value.trim()); });
    // lo escrito y no enviado, de antes de recargar la página (y guardado mientras se escribe)
    const escrito = guardado.caja(texto, `conv:${maquina}|${hilo}`);
    if (texto.value) { boton.classList.add('listo'); requestAnimationFrame(crecer); }

    /** En qué va lo último que se envió, a la izquierda de la caja: solo un círculo (gramática visual: el círculo dice
     *  cómo está algo). Gira mientras va, es un aro mientras falta que lo lea (en su casilla), es lleno y quieto al llegar (completo: un estado, no un movimiento) y es
     *  un aro rojo si falló. Lo que dice con palabras queda en su ayuda. */
    const FORMA: Record<'enviando' | 'llego' | 'cola' | 'error', Circulo> = {
        enviando: { mov: 'gira' }, cola: { lleno: 0 }, llego: { lleno: 1 }, error: { lleno: 0 },
    };
    const decir = (estado: '' | 'enviando' | 'llego' | 'cola' | 'error', que = '') => {
        dijo.className = `dijo ${estado}`;
        dijo.innerHTML = estado ? circulo(FORMA[estado]) : '';
        dijo.title = que;
        dijo.setAttribute('aria-label', que);
    };
    let pendiente: Pendiente | null = null;
    /** Lo enviado, al final de la conversación y tenue, hasta que aparece de verdad en ella. */
    const ponerPendiente = () => {
        turnos.querySelector('.msj.pendiente')?.remove();
        if (!pendiente) return;
        const f = el('div', 'msj usuario pendiente');
        f.append(marca('usuario', 'tú · enviando'), el('div', 'cuerpo', pendiente.texto));
        turnos.appendChild(f);
    };
    const teclas = $('.teclas');
    teclas.hidden = porMensaje;
    const pie = $('footer');
    // la pregunta pendiente: su formulario se guarda entre repintadas (lo elegido no se pierde con cada lectura)
    let abierta: Formulario | null = null;
    let dormido = false;

    // archivado o cerrado: no hay agente que lea, así que no hay caja para escribirle; en su lugar, retomarlo. Salvo un
    // agente residente (`loAbre`): la caja queda, y lo que se le escriba lo abre
    if (h && (!h.vivo || h.archivado)) {
        dormido = !loAbre;
        form.hidden = dormido;
        teclas.hidden = true;
        const aviso = document.createElement('div');
        aviso.className = 'dormido';
        const que = document.createElement('span');
        que.textContent = loAbre ? `${h.archivado ? 'archivado' : 'cerrado'}: escribirle lo abre con esta conversación, y lo lee al tiro`
            : `${h.archivado ? 'archivado' : 'cerrado'}: esto es lo que conversó, sin el agente abierto`;
        const retomar = document.createElement('a');
        retomar.style.setProperty('--c', `var(--${C.hecho})`);
        const ic = document.createElement('span'); ic.className = 'i'; ic.textContent = I.retomar;
        retomar.append(ic, document.createTextNode(' retomar'));
        retomar.title = 'abre el agente con esta conversación, en su terminal';
        retomar.addEventListener('click', () => void ui.orden('telar.retomar', { hilo }));
        aviso.append(que, retomar);
        form.before(aviso);
    }

    /** Lo que el agente pregunta con opciones y espera respuesta (web/pregunta.ts): en el pie, en el lugar de la caja y
     *  las teclas (mientras su diálogo está abierto, lo que se tecleara en su terminal iría a él, no al agente); en la
     *  conversación, una línea que dice que te pregunta. Se contesta ahí si el mod de telar tiene el diálogo
     *  (`contestable`, también en otra máquina); si no, en un hilo de aquí con una sola pregunta de una opción, con el
     *  número de la opción en su terminal; y si tampoco, se muestra y dice dónde contestarla. Sin pregunta, la caja de
     *  siempre. `cerrada`: la que se acaba de contestar desde aquí, que no vuelve aunque una lectura atrasada la traiga. */
    let cerrada = '';
    const ponerPregunta = (p: Pregunta | null) => {
        if (p && p.id === cerrada) p = null;
        if (!p || dormido) {
            abierta?.el.remove();
            abierta = null;
            turnos.querySelector('.msj.pregunta.espera')?.remove();
            pie.classList.remove('preguntando');
            form.hidden = dormido;
            teclas.hidden = porMensaje || dormido;
            return;
        }
        const una = p.preguntas.length === 1 && !p.preguntas[0].varias;
        const como = p.contestable ? 'mod' : !porMensaje && una ? 'teclas' : '';
        if (!abierta || abierta.id !== p.id || abierta.el.dataset.como !== como) {
            abierta?.el.remove();
            const q = p, clave = `pregunta:${maquina}|${hilo}|${q.id}`;
            abierta = formulario(q, como === 'mod' ? { responder: r => void responder(q, r),
                otras: guardado.leer<string[]>(clave), alEscribir: otras => guardado.guardar(clave, otras) }
                : como === 'teclas' ? { teclas: j => { teclear(String(j + 1)); setTimeout(() => void leer(), 800); },
                    nota: 'sin telar en su diálogo: tocar una opción teclea su número en la terminal' }
                : { nota: porMensaje ? `contéstala en la terminal del hilo, en ${maquina} (su telar no la recibe desde aquí)`
                    : 'contéstala en su terminal (⌥T), o con las teclas de abajo' });
            abierta.el.dataset.como = como;
        }
        pie.classList.add('preguntando');
        if (abierta.el.parentElement !== pie) pie.prepend(abierta.el);
        form.hidden = true;
        // sin el mod y con varias preguntas, las teclas son la forma de contestarla desde aquí
        teclas.hidden = porMensaje || !!como;
        const aviso = el('div', 'msj agente pregunta espera');
        aviso.append(marca('espera', 'el agente te pregunta: contesta abajo'), el('div', 'cuerpo', 'te pregunta: contesta abajo'));
        (turnos.querySelector('.turno:last-of-type') ?? turnos).appendChild(aviso);
    };
    /** Mandar la respuesta al diálogo del agente: por telar, que se la pasa al mod (aquí, o en la máquina del hilo). */
    const responder = async (p: Pregunta, respuestas: Record<string, string>) => {
        const f = abierta;
        f?.ocupado(true, 'enviando la respuesta…');
        const fallo = (que: string) => { f?.ocupado(false); ui.estado(que, 6000); };
        try {
            const r = await fetch('/api/hilos/responder', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hilo, maquina, id: p.id, respuestas }),
            });
            const d = await r.json() as { detail?: string; tomada?: boolean; por?: string };
            if (!r.ok) { fallo(`no se envió: ${d.detail || `telar respondió ${r.status}`}`); return; }
            if (d.por === 'terminal') ui.estado('ya la habían contestado en la terminal', 6000);
            else if (!d.tomada) { fallo('quedó en camino: el agente todavía no la toma (si sigue abierta, vuelve a responder)'); return; }
            cerrada = p.id;
            guardado.guardar(`pregunta:${maquina}|${hilo}|${p.id}`, undefined);
            ponerPregunta(null);
            pronto = Date.now() + 20000;
            setTimeout(() => void leer(), 600);
        } catch {
            fallo('sin conexión con telar: no se envió');
        }
    };

    atenderClics(turnos, { hilo, maquina });
    const abajo = () => turnos.scrollHeight - turnos.scrollTop - turnos.clientHeight < 40;
    let ultimo = '', leido = false;
    let apagarVoz: () => void = () => { /* lo pone el modo de voz, si lo hay */ };
    let alPintar: (d: Leido) => void = () => { /* lo pone el modo de voz, si lo hay */ };
    /** Su máquina está fuera de línea (web/alcance.ts): qué pasa, lo que le espera en cola y «despertar al volver»; la caja
     *  de abajo le escribe igual. Sin la foto que lo diga, el error tal cual. */
    const ponerFuera = async (error: string) => {
        const r = await cli.espejos().catch(() => undefined);
        const m = fueraDe(maquina, (r?.datos?.espejos ?? []).map(e => ({ ...e, fuera: !e.en_linea && !!r?.datos?.al_dia })));
        turnos.textContent = '';
        if (!m) { turnos.appendChild(el('p', 'nada', error)); return; }
        const cuadro = el('div', 'fuera-de-linea');
        cuadro.innerHTML = panelFuera(hilo, m, Date.now(), { conversacion: true });
        cuadro.querySelector<HTMLButtonElement>('button[data-accion="despertar"]')?.addEventListener('click', async e => {
            const b = e.currentTarget as HTMLButtonElement;
            if (b.disabled) return;
            b.disabled = true;
            const d = await cli.despertar(hilo, maquina, { cola: true });
            ui.estado(d.datos?.hecho || d.error || 'no se pudo', 8000);
            void ponerFuera(error);
        });
        turnos.appendChild(cuadro);
    };
    const pintar = (d: Leido) => {
        alPintar(d);
        // lo enviado: si ya aparece entre lo que dijo la persona, llegó; si no, a los pocos segundos pasa a «en su casilla» (aro:
        // falta que lo lea) y sigue abajo, tenue. Va antes de la salida de abajo: con la conversación sin cambios también corre
        if (pendiente) {
            const buscado = comparable(pendiente.texto);
            const llego = (d.turnos ?? []).some(t => t.some(m => m.quien === 'usuario' && comparable(m.texto ?? '').includes(buscado)));
            if (llego) { pendiente = null; decir('llego', 'llegó: está en la conversación'); }
            else if (Date.now() - pendiente.desde > ESPERA_CASILLA) decir('cola', 'en su casilla; todavía no aparece (si el agente está trabajando, lo lee al terminar)');
        }
        const firma = JSON.stringify(d);
        if (firma === ultimo) return;
        ultimo = firma;
        const seguir = abajo() || !leido;
        turnos.textContent = '';
        if (d.error) {
            const sinConversacion = /no tiene conversación/.test(d.error);
            // su máquina fuera de línea (telar.alcance): su conversación vive allá; escribirle igual sirve, y despertarlo
            // queda en cola para cuando vuelva
            const fuera = maquina && /^.+ fuera de línea desde [^:]+:/.test(d.error);
            if (fuera) { void ponerFuera(d.error); return; }
            turnos.appendChild(el('p', 'nada', sinConversacion
                ? 'este hilo no dejó una conversación en esta máquina (se cerró sin mensajes, o la tuvo en otra)' : d.error));
            return;
        }
        if (d.fuente === 'panel') { turnos.appendChild(el('pre', 'panel', d.texto ?? '')); ponerPregunta(null); }
        else {
            if (d.recortado || (d.total_turnos ?? 0) > (d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'turnos anteriores sin mostrar'));
            // Los pasos del agente (herramientas) no se muestran: en el celular no importan. Solo, si lo último que hay en la
            // conversación es uno, una línea gris con ese paso: está trabajando.
            const turnosD = d.turnos ?? [];
            const ultimoMsj = turnosD.at(-1)?.at(-1);
            // lo que el agente pregunta con opciones: la que espera, para contestarla; las cerradas, en el historial
            const pendiente = [...turnosD].reverse().flat().find(m => m.pregunta?.estado === 'pendiente')?.pregunta ?? null;
            const trabajando = ultimoMsj?.quien === 'herramienta' && !ultimoMsj.pregunta ? ultimoMsj : null;
            for (const turno of turnosD) {
                const t = el('section', 'turno');
                for (const m of turno) {
                    if (m.pregunta && m.pregunta.estado !== 'pendiente') { t.append(...registro(m.pregunta, marca)); continue; }
                    if (m.quien === 'herramienta') continue;
                    const bus = m.quien === 'usuario' ? delBus(m.texto ?? '') : null;
                    const f = el('div', `msj ${bus ? 'bus' : m.quien}`);
                    f.appendChild(marca(bus ? 'bus' : m.quien === 'agente' ? 'agente' : 'usuario', bus ?? QUIEN[m.quien] ?? m.quien));
                    const cuerpo = el('div', m.quien === 'agente' ? 'cuerpo md' : 'cuerpo', m.quien === 'agente' ? undefined : m.texto ?? '');
                    if (m.quien === 'agente') cuerpo.innerHTML = md.render(m.texto ?? '');
                    f.appendChild(cuerpo);
                    t.appendChild(f);
                }
                if (t.childElementCount) turnos.appendChild(t);
            }
            if (trabajando) {
                const f = el('div', 'msj herramienta');
                f.append(el('span', 'marca', '·'), el('div', 'cuerpo', (trabajando.texto ?? '').split('\n')[0]));
                turnos.appendChild(f);
            }
            ponerPregunta(pendiente);
            if (!(d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'todavía no hay conversación'));
        }
        ponerPendiente();
        // las rutas que escribió el agente, como enlaces al visor
        enlazar(turnos, true, hilo);
        leido = true;
        if (seguir || pendiente) turnos.scrollTop = turnos.scrollHeight;
    };

    let leyendo = false, pronto = 0;
    const leer = async () => {
        if (leyendo) return;
        leyendo = true;
        try {
            const r = await fetch(`/api/hilos/leer?hilo=${encodeURIComponent(hilo)}&ultimos=8${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`, { cache: 'no-store' });
            const d = await r.json() as Leido & { detail?: string };
            pintar(r.ok ? d : { error: d.detail || `la API respondió ${r.status}` });
        } catch { /* sin conexión: se reintenta en la vuelta */ }
        leyendo = false;
    };
    // cada 4 s mientras se mira (1,5 justo después de escribirle); escondida, cada 20
    let espera = 0;
    const vuelta = () => {
        void leer();
        espera = window.setTimeout(vuelta, Date.now() < pronto ? 1500 : (document.hidden || raiz.hidden ? 20000 : 4000));
    };
    vuelta();

    // escribir: una vista de la terminal del hilo, abierta la primera vez que hace falta
    let ws: WebSocket | null = null;
    const cola: string[] = [];
    let enviando = false;
    // lo que recargar la página perdería (web/recarga.ts): lo que espera a que abra su terminal, un mensaje por el bus
    // en camino, lo recién enviado mientras puede faltarle el ⏎ de repuesto (abajo, a los 6 s), y una pregunta con
    // opciones marcadas (lo marcado no se guarda; lo escrito sí) o enviándose
    let vozActiva = false;
    const soltarUso = recarga.enUso(() => vozActiva || cola.length > 0 || enviando || (!!pendiente && Date.now() - pendiente.desde < 8000)
        || !!abierta?.el.matches('.ocupado') || !!abierta?.el.querySelector('[aria-pressed="true"]'));
    const canal = () => {
        if (ws && ws.readyState <= 1) return ws;
        const nuevo = new WebSocket(enchufe(`/pty?hilo=${encodeURIComponent(hilo)}&cols=100&rows=30`));
        let abrio = false;
        nuevo.onopen = () => { abrio = true; for (const d of cola.splice(0)) nuevo.send(JSON.stringify({ d })); };
        nuevo.onclose = () => {
            if (ws === nuevo) ws = null;
            // se cerró sin haber abierto: lo que esperaba en la cola no salió
            if (!abrio && cola.length) {
                cola.length = 0;
                if (pendiente) { texto.value ||= pendiente.texto; escrito.anotar(); crecer(); pendiente = null; ponerPendiente(); }
                decir('error', 'no se pudo abrir su terminal: no se envió (quedó en la caja)');
            }
        };
        ws = nuevo;
        return nuevo;
    };
    // al volver a primer plano (o recuperar la red) el socket puede estar muerto sin haberlo dicho: se descarta y el
    // próximo envío abre uno nuevo
    const refrescar = () => { if (!document.hidden && ws) { const v = ws; ws = null; v.onclose = null; v.close(); } };
    document.addEventListener('visibilitychange', refrescar);
    window.addEventListener('online', refrescar);
    const teclear = (d: string) => {
        const c = canal();
        if (c.readyState === 1) c.send(JSON.stringify({ d })); else cola.push(d);
        pronto = Date.now() + 20000;
    };
    // ⏎ envía; ⇧⏎ es una línea nueva (y mientras se compone una letra con acento, ⏎ es de la composición)
    texto.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener('submit', async e => {
        e.preventDefault();
        const t = texto.value.replace(/\s+$/, '');
        if (!t) return;
        pendiente = { texto: t, desde: Date.now() };
        texto.value = ''; escrito.anotar(); crecer(); boton.classList.remove('listo');
        decir('enviando', 'enviando…');
        ponerPendiente();
        turnos.scrollTop = turnos.scrollHeight;
        if (porMensaje) {
            // por el bus, como la persona; le llega al hilo al terminar su turno (o al tiro si espera)
            enviando = true;
            try {
                const r = await fetch('/api/mensajes', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ para: hilo, texto: t, tipo: 'persona', de: 'el panel' }),
                });
                const d = await r.json() as { detail?: string; despertado?: string; sin_despertar?: string; en_cola?: string; cola?: boolean };
                // ya se está abriendo: el aviso de cerrado sobra
                if (r.ok && loAbre) raiz.querySelector('.dormido')?.remove();
                if (r.ok) { decir('cola', loAbre ? 'en su casilla: telar lo abre con su conversación, y lo lee ahora'
                    : d.despertado ? `estaba ${d.despertado}: lo retomé con su conversación, y lo lee ahora`
                    : d.en_cola ? `${d.en_cola}: espera en el bus y le llega cuando vuelva${d.cola ? ' (allá no estaba abierto: retomarlo quedó en cola)' : ''}`
                    : d.sin_despertar ? `en su casilla; no está abierto y no pude retomarlo (${d.sin_despertar}): le llega cuando lo retomes`
                    : 'en su casilla: le llega al terminar su turno, o al tiro si te espera'); pronto = Date.now() + 30000; setTimeout(() => void leer(), 3000); }
                else { texto.value = t; escrito.anotar(); crecer(); pendiente = null; ponerPendiente(); decir('error', `no se envió: ${d.detail || `telar respondió ${r.status}`}`); }
            } catch {
                texto.value = t; escrito.anotar(); crecer(); pendiente = null; ponerPendiente();
                decir('error', 'sin conexión con telar: no se envió (quedó en la caja)');
            } finally { enviando = false; }
            return;
        }
        // como un pegado (para que un salto de línea no envíe antes de tiempo), y después ⏎
        // el ⏎ va después, con holgura: pegado y ⏎ casi juntos, el agente toma el ⏎ como parte del pegado y no envía
        const mio = pendiente;
        teclear(`\u001b[200~${t}\u001b[201~`);
        setTimeout(() => teclear('\r'), 400);
        setTimeout(() => void leer(), 1500);
        // si a los 6 s no aparece en la conversación, el ⏎ se perdió o no se tomó: una vez más (en una caja vacía no hace nada)
        setTimeout(async () => {
            if (pendiente !== mio) return;
            await leer();
            if (pendiente === mio) { teclear('\r'); setTimeout(() => void leer(), 1500); }
        }, 6000);
    });
    for (const [nombre, envia, ayuda, icono] of TECLAS) {
        const b = el('button', '');
        if (icono) b.append(el('span', 'i', nombre)); else b.textContent = nombre;
        b.type = 'button';
        b.title = ayuda;
        b.addEventListener('click', () => { teclear(envia); setTimeout(() => void leer(), 800); });
        teclas.appendChild(b);
    }

    // las skills del agente: un botón al final de las teclas abre una lista con buscador (las de la ventana
    // «instrucción», web/instruccion.ts) y la elegida queda escrita en la caja como «/nombre », lista para agregarle lo
    // que haga falta y enviar. Es teclear en la
    // terminal del hilo, así que solo en los de esta máquina (a uno de otra, lo escrito llega como mensaje del bus y
    // un «/skill» no se ejecutaría)
    if (!porMensaje) {
        const b = el('button', 'skills');
        b.type = 'button';
        b.title = 'skills: elegir una para mandársela';
        b.append(el('span', 'i', I.accion));
        b.addEventListener('click', async () => {
            ui.estado('leyendo sus skills…', 1500);
            const lista = await skillsDe(hilo, '');
            if (!lista.length) { ui.estado('este hilo no tiene skills a mano'); return; }
            const op = await ui.elegir(lista.map(x => ({
                label: `/${x.nombre}`, description: (x.usada ? `${x.usada}× · ` : '') + (x.descripcion ?? ''),
                icono: I.accion, color: C.agente, nombre: x.nombre,
            })), { titulo: 'skills', placeholder: 'skills' });
            if (!op) return;
            // un «/algo» al empezar cambia de skill; lo demás escrito se queda, detrás
            const pre = `/${op.nombre} `;
            texto.value = pre + texto.value.replace(/^\/\S*\s*/, '');
            escrito.anotar();
            crecer();
            boton.classList.add('listo');
            texto.focus();
            texto.setSelectionRange(pre.length, pre.length);
        });
        teclas.appendChild(b);
    }

    // manos libres: hablarle con el micrófono (el navegador dicta, en español) y que el agente conteste en voz alta,
    // para ir caminando con audífonos. Lo dictado va a la caja y sale solo tras una pausa; lo que el agente dice al
    // terminar un turno se lee en voz alta (sin código ni enlaces). Mientras habla, el micrófono sigue abierto: si le hablas, se calla (pensado para audífonos). Pide que la
    // pantalla no se apague (si el teléfono la bloquea, el navegador corta el micrófono). Tocar el botón mientras habla
    // lo calla; tocarlo en silencio apaga el modo.
    const Dictado = (window as unknown as { SpeechRecognition?: new () => Dictador; webkitSpeechRecognition?: new () => Dictador })
        .SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: new () => Dictador }).webkitSpeechRecognition;
    if (Dictado && !dormido && 'speechSynthesis' in window) {
        const bv = el('button', 'voz');
        bv.type = 'button';
        bv.textContent = 'voz';
        bv.title = 'manos libres: hablas y el agente te contesta en voz alta';
        let activo = false, oyendo: Dictador | null = null, hablando = false, parar = false;
        let leidoFirma = '', candidata = '', pausa = 0, tardanza = 0, luz: { release(): Promise<void> } | null = null;
        const ultimaDelAgente = (d: Leido): string => {
            const m = (d.turnos ?? []).at(-1)?.at(-1);
            return m?.quien === 'agente' ? (m.texto ?? '').trim() : '';
        };
        /** Lo que se lee de un mensaje: sin código, sin enlaces ni signos del markdown, y no más de lo que se aguanta oír. */
        const paraOir = (t: string): string => {
            let x = t.replace(/```[\s\S]*?```/g, ' (código en pantalla) ').replace(/`([^`]*)`/g, '$1')
                .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/https?:\/\/\S+/g, 'un enlace')
                .replace(/^\s*[#>*\-+|]+\s*/gm, '').replace(/[*_~|]/g, '').replace(/\n{2,}/g, '. ').replace(/\s+/g, ' ').trim();
            if (x.length > 450) {
                const corte = x.slice(0, 450), fin = Math.max(corte.lastIndexOf('. '), corte.lastIndexOf('? '));
                x = `${corte.slice(0, fin > 200 ? fin + 1 : 450)} … el resto está en pantalla.`;
            }
            return x;
        };
        const escuchar = () => {
            if (!activo || oyendo) return;
            const r = new Dictado();
            r.lang = 'es-CL'; r.continuous = true; r.interimResults = true;
            const prefijo = texto.value ? texto.value.replace(/\s+$/, '') + ' ' : '';
            r.onresult = (e: DictadoEvento) => {
                const dicho = Array.from(e.results).map(x => x[0].transcript).join('').trim();
                // hablarle mientras lee lo calla (con audífonos el micrófono no oye la voz del agente)
                if (hablando && dicho) callar();
                texto.value = prefijo + dicho; escrito.anotar(); crecer(); boton.classList.toggle('listo', !!texto.value.trim());
                clearTimeout(pausa);
                // el dictado se cierra solo tras una pausa tras lo último dicho: sale lo que hay
                if (e.results[e.results.length - 1].isFinal) pausa = window.setTimeout(() => {
                    if (!texto.value.trim()) return;
                    form.requestSubmit();
                    r.abort();
                }, 1800);
            };
            r.onerror = (e: { error: string }) => {
                if (e.error === 'not-allowed' || e.error === 'service-not-allowed') { apagar(); ui.estado('sin permiso para el micrófono: se da en los ajustes del sitio', 6000); }
            };
            r.onend = () => { if (oyendo === r) oyendo = null; if (activo) setTimeout(escuchar, 300); };
            oyendo = r;
            try { r.start(); } catch { oyendo = null; }
        };
        const callar = () => { parar = true; speechSynthesis.cancel(); };
        const leerEnVoz = (t: string) => {
            const frases = paraOir(t).match(/[^.!?…]+[.!?…]*\s*/g) ?? [];
            if (!frases.length) return;
            hablando = true; parar = false;
            escuchar();   // sigue oyendo mientras habla: si le hablas, se calla
            const voces = speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('es'));
            const voz = voces.find(v => v.lang.toLowerCase().includes('cl')) ?? voces.find(v => v.localService) ?? voces[0];
            // en trozos de unas pocas frases: el navegador corta las lecturas largas
            const trozos: string[] = [];
            for (const f of frases) { const u = trozos.length - 1; if (u >= 0 && trozos[u].length + f.length < 220) trozos[u] += f; else trozos.push(f); }
            const siguiente = (i: number) => {
                if (parar || i >= trozos.length) { hablando = false; bv.classList.remove('habla'); escuchar(); return; }
                const u = new SpeechSynthesisUtterance(trozos[i]);
                u.lang = voz?.lang ?? 'es-CL'; if (voz) u.voice = voz; u.rate = 1.05;
                u.onend = () => siguiente(i + 1);
                u.onerror = () => { hablando = false; bv.classList.remove('habla'); escuchar(); };
                speechSynthesis.speak(u);
            };
            bv.classList.add('habla');
            siguiente(0);
        };
        alPintar = (d: Leido) => {
            if (!activo) return;
            const t = ultimaDelAgente(d);
            if (!t || t === leidoFirma || t === candidata) return;
            // lo último que dijo, si de verdad es lo último (sigue igual tras unos segundos: el agente no está en medio de su turno)
            candidata = t;
            clearTimeout(tardanza);
            tardanza = window.setTimeout(() => {
                if (!activo || candidata !== t) return;
                leidoFirma = t; leerEnVoz(t);
            }, 2500);
        };
        const pedirPantalla = async () => {
            try { luz = await (navigator as unknown as { wakeLock: { request(k: string): Promise<{ release(): Promise<void> }> } }).wakeLock.request('screen'); } catch { luz = null; }
        };
        const alVolver = () => { if (activo && !document.hidden) void pedirPantalla(); };
        document.addEventListener('visibilitychange', alVolver);
        const apagar = () => {
            activo = false; vozActiva = false; clearTimeout(pausa); clearTimeout(tardanza); callar(); oyendo?.abort(); oyendo = null;
            void luz?.release(); luz = null; bv.classList.remove('activa', 'habla');
        };
        bv.addEventListener('click', async () => {
            if (activo && hablando) { callar(); return; }
            if (activo) { apagar(); ui.estado('manos libres apagado'); return; }
            // lo que ya estaba dicho no se lee: solo lo que venga
            try {
                const r = await fetch(`/api/hilos/leer?hilo=${encodeURIComponent(hilo)}&ultimos=2${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`, { cache: 'no-store' });
                leidoFirma = ultimaDelAgente(await r.json() as Leido);
            } catch { leidoFirma = ''; }
            activo = true; vozActiva = true; candidata = leidoFirma;
            bv.classList.add('activa');
            void pedirPantalla();
            speechSynthesis.getVoices();   // las voces se cargan a la primera
            // leer algo corto ahora, dentro del toque: el navegador solo deja hablar tras un gesto
            const hola = new SpeechSynthesisUtterance('Te escucho.'); hola.lang = 'es-CL';
            hola.onend = () => escuchar();
            speechSynthesis.speak(hola);
            ui.estado('manos libres: habla; el agente te contesta en voz alta. Toca «voz» para callarlo o apagarlo', 6000);
        });
        teclas.appendChild(bv);
        apagarVoz = apagar;
    }

    return {
        mostrada: () => void leer(),
        cerrar: () => {
            clearTimeout(espera); document.removeEventListener('visibilitychange', refrescar); window.removeEventListener('online', refrescar);
            apagarVoz(); ws?.close(); ws = null; escrito.soltar(); soltarUso();
        },
    };
}
