// El dashboard en la página: lo que pasa en el navegador con lo que dibuja panel.ts. Filtra y ordena las listas
// (tareas, proyectos), recuerda lo elegido (modo, búsqueda, orden), atiende los clics y las teclas, y le avisa a
// Dashboard (`enviar`, panel.ts) lo que tiene que hacer él: abrir una tarea, cambiar de pestaña, guardar un formulario.
// Todo queda dentro de su elemento (`.v-dia`); sus estilos, en media/css/dia.css, plan.css (el calendario), proyectos.css y
// ahora.css (con @scope, en `.v-dia`).
//
// Las teclas: el dashboard comparte la página con la barra y las vistas de los hilos, así que sus atajos solo
// valen mientras se ve, y nunca mientras se escribe en un campo de afuera (el buscador de la barra, la terminal).

import * as entidades from '../../web/entidades';
import { I } from '../../web/iconos';
import { circulo } from '../../componentes/circulo';
import { contarFiltro, leerGrupo, marcarFiltros } from '../../componentes/filtros';
import * as ui from '../../web/ui';
import { armarPrompt } from './config/periodicos';
import { esDeuda } from './dia';

/** Lo que la vista le pide al Dashboard (`Dashboard.mensaje`, panel.ts). */
export interface MensajeDia { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string; datos?: string;
    /** dónde se hizo clic: un menú se abre ahí (web/entidades.ts) */
    donde?: { x: number; y: number } }

/** La vista ya montada: el Dashboard le manda lo que hay que dibujar. */
export interface VistaDia {
    /** la pantalla entera: su cuerpo (lo que va dentro de `#dia`) y su barra (componentes/pantalla.ts), arriba */
    pintar(html: string, barra?: string): void;
    /** un pedazo, sin tocar lo escrito en lo demás (el formulario de un periódico, el detalle de un proyecto) */
    parcial(id: string, html: string): void;
    /** cuántos pendientes tiene cada proyecto: llega después de la lista */
    cuentasProyectos(cuentas: Record<string, number>): void;
    /** se ve (es lo que está a la derecha, y la pestaña del navegador está al frente) */
    readonly visible: boolean;
    /** la respuesta a lo que pidió un lienzo (`window.lienzo.pedir`), a ese lienzo y a ningún otro */
    responderLienzo(id: string, respuesta: { ok: boolean; datos?: unknown; error?: string }): void;
    /** dejar puesto un filtro de «tareas» (`deuda`, `vencidas`…), sin lo buscado: para abrirla así desde otra pantalla */
    filtrarTareas(modo: string): void;
}

interface Estado {
    modo: string; q: string; todas: boolean; pq: string; po: string; to: string; area: string; dueno: string;
    pc: boolean; pf: Record<string, string>; px?: boolean; pd?: string; ordenP?: string; ordenC?: string; tm?: string; tq?: string; cq?: Record<string, string>; tmv?: number; pfv?: number;
}

const LLAVE = 'telar.dashboard.estado';

/** Lo que se recordaba: antes en la llave que compartían el marco del dashboard y el de la barra («telar.srcdoc»),
 *  que se pisaban; la primera vez, si lo de ahí es del dashboard, se trae. */
function leerEstado(): Partial<Estado> {
    try {
        const propio = localStorage.getItem(LLAVE);
        if (propio) return JSON.parse(propio) ?? {};
        const viejo = JSON.parse(localStorage.getItem('telar.srcdoc') ?? 'null');
        return viejo && typeof viejo === 'object' && 'modo' in viejo ? viejo : {};
    } catch { return {}; }
}

const norm = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const escribiendoEn = (el: Element | null) => !!el && (el as HTMLElement).isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el?.tagName ?? '');

export function montarDia(raiz: HTMLElement, enviar: (m: MensajeDia) => void): VistaDia {
    raiz.classList.add('v-dia');
    // la barra de la pantalla, quieta arriba mientras el cuerpo corre (dia.css), y el cuerpo
    raiz.innerHTML = '<div id="barra-dia"></div><div id="dia"><div class="aviso">leyendo el día…</div></div>';
    const dia = raiz.querySelector<HTMLElement>('#dia')!;
    const barraDia = raiz.querySelector<HTMLElement>('#barra-dia')!;
    // la barra se rehace solo si cambió: el repintado de cada minuto no le quita el mouse a un botón
    let barraPintada = '';
    const $ = <T extends HTMLElement = HTMLElement>(id: string) => raiz.querySelector<T>(`#${id}`);
    const todos = <T extends HTMLElement = HTMLElement>(sel: string) => [...raiz.querySelectorAll<T>(sel)];
    const visible = () => !raiz.hidden && raiz.isConnected && !document.hidden;

    const estado: Estado = Object.assign({ modo: 'urgentes', q: '', todas: false, pq: '', po: 'fecha', to: 'urgencia', area: '', dueno: '', pc: false, pf: {} }, leerEstado());
    // antes, «area» filtraba por la carpeta de la raíz (trabajo, personal…); ahora es el área del documento
    // «tareas» abre en «esta semana» (8-oct): lo que estaba guardado como «todas» pasa una vez a ese modo
    if (!estado.tmv) { if (!estado.tm || estado.tm === 'todas') estado.tm = 'semana'; estado.tmv = 1; }
    if (!estado.pfv) { estado.pf = { ...(estado.pf || {}) }; if (estado.pf.area) { estado.pf.raiz = estado.pf.area; estado.pf.area = ''; } estado.pfv = 2; }
    const guardar = () => { try { localStorage.setItem(LLAVE, JSON.stringify(estado)); } catch { /* sin almacén */ } };

    // el área y el dueño filtran antes que todo lo demás: lo que queda fuera ni se cuenta
    const pasaArea = (f: HTMLElement, area: string) => !area || f.dataset.area === area;
    const pasaDueno = (f: HTMLElement, dueno: string) => {
        if (dueno === 'mias' && f.dataset.mia === '0') return false;
        if (dueno === 'otros' && (f.dataset.mia !== '0' || f.dataset.sin === '1')) return false;
        if (dueno === 'sin' && f.dataset.sin !== '1') return false;
        return true;
    };
    const pasa = (f: HTMLElement) => pasaArea(f, estado.area) && pasaDueno(f, estado.dueno);
    // código de mayor a menor, con los números como números (T130 antes que T81): lo más nuevo
    // arriba, como el orden «número descendente» de flow. El texto, sin tildes.
    const comparar = (a: HTMLElement, b: HTMLElement) => {
        if (estado.to === 'codigo') return (b.dataset.ref ?? '').localeCompare(a.dataset.ref ?? '', undefined, { numeric: true });
        if (estado.to === 'alfa') return (a.dataset.alfa ?? '').localeCompare(b.dataset.alfa ?? '');
        return Number(a.dataset.orden) - Number(b.dataset.orden);
    };
    const filas = () => { const c = $('tareas'); return c ? [...c.querySelectorAll<HTMLElement>('.tarea')] : []; };
    const visibles = () => filas().filter(f => !f.hidden);
    const conTodas = (partes: string[]) => (f: HTMLElement) => partes.every(p => (f.dataset.texto ?? '').includes(p));

    function aplicar(): void {
        aplicarTareas();   // el área y el responsable filtran también la de «tareas», donde se eligen
        const c = $('tareas'); if (!c) return;
        // el área filtra antes que todo lo demás: lo de otra área ni se cuenta
        const lasDeHoy = filas().filter(pasa);
        for (const f of filas()) if (!lasDeHoy.includes(f)) f.hidden = true;
        const partes = norm(estado.q).split(/\s+/).filter(Boolean);
        let lista = lasDeHoy;
        if (partes.length) lista = lasDeHoy.filter(conTodas(partes));
        else if (estado.modo === 'urgentes') lista = lasDeHoy.filter(f => f.dataset.urgente === '1');
        else if (estado.modo === 'propuestas') lista = lasDeHoy.filter(f => f.dataset.propuesta === '1');
        lista.sort(comparar);
        const limite = partes.length || estado.todas || estado.modo === 'propuestas' ? lista.length : (estado.modo === 'urgentes' ? 8 : 15);
        for (const f of lasDeHoy) f.hidden = true;
        const mas = $('tareas-mas')!;
        lista.forEach((f, i) => { c.insertBefore(f, mas); f.hidden = i >= limite; });
        const resto = lista.length - Math.min(limite, lista.length);
        mas.hidden = resto <= 0;
        mas.textContent = `+ ${resto} más`;
        const vacio = $('tareas-vacio')!;
        vacio.hidden = lista.length > 0;
        vacio.textContent = partes.length ? 'sin resultados' : estado.modo === 'propuestas' ? 'nada que decidir' : 'nada urgente';
        for (const b of todos('[data-orden-t]')) b.classList.toggle('activo', b.dataset.ordenT === estado.to);
        for (const b of todos('[data-modo-tareas]')) b.classList.toggle('activo', !partes.length && b.dataset.modoTareas === estado.modo);
        const cuenta = $('tareas-cuenta');
        if (cuenta) cuenta.textContent = partes.length ? `${lista.length} de ${lasDeHoy.length}` : '';
    }
    // la pestaña «tareas»: todas, filtradas por modo (por revisar, vencidas…), área, dueño y lo buscado
    const enModo = (f: HTMLElement, modo?: string) => {
        const m = modo || estado.tm || 'semana', d = f.dataset.dias ? Number(f.dataset.dias) : null;  // sin fecha, el ítem no lleva data-dias
        if (m === 'revisar') return f.dataset.rev === '1';
        if (m === 'vencidas') return d !== null && d < 0;
        if (m === 'deuda') return esDeuda(d);
        if (m === 'semana') return f.dataset.sem === '1';
        if (m === 'estrella') return f.dataset.estrella === '1';
        if (m === 'encurso') return f.dataset.encurso === '1';
        if (m === 'sinfecha') return d === null;
        return true;
    };
    // el orden de la columna elegida en «tareas»; sin elegir, la urgencia. Lo vacío siempre al final
    const compararColumna = (a: HTMLElement, b: HTMLElement) => {
        const k = estado.ordenC || '';
        if (!k) return Number(a.dataset.orden) - Number(b.dataset.orden);
        const x = a.dataset[k] || '', y = b.dataset[k] || '';
        if (x !== y) {
            if (!x || !y) return x ? -1 : 1;
            if (k === 'dias') return Number(x) - Number(y);
            // el código, de mayor a menor con los números como números (lo más nuevo arriba)
            if (k === 'ref') return y.localeCompare(x, undefined, { numeric: true });
            return x.localeCompare(y);
        }
        return Number(a.dataset.orden) - Number(b.dataset.orden);
    };
    // el buscador de un bloque con muchas filas (la bandeja de correo): esconde las que no tienen todas las palabras
    function aplicarCorreo(): void {
        for (const i of todos<HTMLInputElement>('input.buscar-c')) {
            const sec = i.closest('section'); if (!sec) continue;
            const partes = norm(estado.cq?.[i.dataset.bloque ?? ''] || '').split(/\s+/).filter(Boolean);
            const filas = [...sec.querySelectorAll<HTMLElement>('.cr')];
            let n = 0;
            for (const f of filas) { f.hidden = !conTodas(partes)(f); if (!f.hidden) n += 1; }
            const cuenta = i.parentElement?.querySelector('.buscar-c-cuenta');
            if (cuenta) cuenta.textContent = partes.length ? `${n} de ${filas.length}` : '';
        }
    }
    function aplicarTareas(): void {
        const c = $('tareas-t'); if (!c) return;
        // el área o el responsable que rige y ya no está entre las opciones (no queda ninguna de esa área) se suelta:
        // si no, la lista seguiría filtrada sin que se vea por qué, y sin «todas» no habría cómo soltarlo
        const hay = (g: string, k: string) => !!$('revisar')?.querySelector(`.filtros-op[data-id="${CSS.escape(`${g}:${k}`)}"]`);
        if (estado.area && !hay('area', estado.area)) { estado.area = ''; guardar(); }
        if (estado.dueno && !hay('dueno', estado.dueno)) { estado.dueno = ''; guardar(); }
        const lasDeTodas = [...c.querySelectorAll<HTMLElement>('.tarea')];
        const partes = norm(estado.tq || '').split(/\s+/).filter(Boolean);
        const conTexto = conTodas(partes);
        const vacio = $('tareas-t-vacio')!;
        lasDeTodas.sort(compararColumna);
        for (const s of todos<HTMLElement>('.orden [data-id^="tareas:"]')) {
            const k = (s.dataset.id ?? '').slice(7), si = k === (estado.ordenC || '');
            s.classList.toggle('si', si);
            s.title = s.title.replace(/ \(clic: volver.*\)$/, '') + (si ? ' (clic: volver al orden de telar)' : '');
        }
        let n = 0;
        for (const f of lasDeTodas) {
            c.insertBefore(f, vacio);
            f.hidden = !(pasa(f) && enModo(f) && conTexto(f));
            if (!f.hidden) n += 1;
        }
        vacio.hidden = n > 0 || !lasDeTodas.length;
        vacio.textContent = partes.length ? 'sin resultados' : 'nada aquí';
        // en «esta semana», lo demás queda plegado detrás de «ver todas»: cuántas más hay con los otros filtros
        const mas = $('tareas-t-mas');
        if (mas) {
            const resto = (estado.tm || 'semana') === 'semana' ? lasDeTodas.filter(f => f.hidden && pasa(f) && conTexto(f)).length : 0;
            mas.hidden = resto === 0;
            mas.textContent = `ver todas (${resto} más)`;
            c.appendChild(mas);
        }
        const lista = $('revisar') ?? raiz;
        marcarFiltros(lista, 'modo', estado.tm || 'semana', 'semana');
        marcarFiltros(lista, 'area', estado.area || '');
        marcarFiltros(lista, 'dueno', estado.dueno || '');
        // cada opción dice cuántas quedarían si se la eligiera, con lo demás que está filtrado (la búsqueda y los
        // otros grupos): la de la que rige es lo que se ve
        const cuantas = (cond: (f: HTMLElement) => boolean) => lasDeTodas.filter(f => conTexto(f) && cond(f)).length;
        const deja: Record<string, (f: HTMLElement, k: string) => boolean> = {
            modo: (f, k) => enModo(f, k) && pasaArea(f, estado.area) && pasaDueno(f, estado.dueno),
            area: (f, k) => enModo(f) && pasaArea(f, k) && pasaDueno(f, estado.dueno),
            dueno: (f, k) => enModo(f) && pasaArea(f, estado.area) && pasaDueno(f, k),
        };
        for (const b of lista.querySelectorAll<HTMLElement>('.filtros-op')) {
            const id = b.dataset.id ?? '', i = id.indexOf(':'), cumple = deja[id.slice(0, i)];
            if (cumple) contarFiltro(b, cuantas(f => cumple(f, id.slice(i + 1))));
        }
        for (const b of todos('[data-orden-t]')) b.classList.toggle('activo', b.dataset.ordenT === estado.to);
        const cuenta = $('tareas-t-cuenta');
        if (cuenta) cuenta.textContent = partes.length || (estado.tm || 'semana') !== 'todas' ? `${n} de ${lasDeTodas.length}` : '';
    }
    // un filtro de «tareas»: rige la opción elegida, y si ya regía se suelta. El área y el responsable filtran también
    // la lista de hoy: `aplicar` rehace las dos
    function elegirFiltro(id: string): void {
        const i = id.indexOf(':'), g = id.slice(0, i), k = id.slice(i + 1);
        if (g === 'modo') estado.tm = (estado.tm || 'semana') === k ? 'semana' : k;
        else if (g === 'area') estado.area = estado.area === k ? '' : k;
        else if (g === 'dueno') estado.dueno = estado.dueno === k ? '' : k;
        else return;
        guardar(); aplicar();
    }
    // un grupo plegado (el área, el responsable): sus opciones en un menú bajo él, cada una con su cuenta; la que rige,
    // con ✓ en el acento, y elegirla la suelta
    async function abrirFiltro(g: HTMLElement, donde: { x: number; y: number }): Promise<void> {
        const { nombre, opciones } = leerGrupo(g);
        const elegida = await ui.menu(opciones.map(o => ({
            id: o.id, label: o.nombre, description: [o.cuenta ?? '', o.si ? 'clic: soltarlo' : ''].filter(x => x !== '').join(' · '),
            // las demás, con la celda del ícono en blanco: si no, la que rige queda corrida de las otras
            icono: o.si ? I.hecha : '\u00a0', color: o.si ? 'acento' : undefined,
        })), donde, nombre);
        if (elegida) elegirFiltro(elegida.id);
    }
    // la pantalla de proyectos: las filas llegan en su orden de siempre (`data-orden`), por estado, con la cabecera de
    // cada sección (en ejecución, por partir…) entre ellas. Aquí se filtran por todas las palabras y por el área, los
    // cerrados se esconden salvo que se pidan o se busquen, y se ordenan por la columna elegida: entonces van sin
    // secciones, y lo vacío siempre al final; empatadas, en su orden de siempre
    const proyectosVisibles = () => todos('#proyectos .proy, #iniciativas .proy').filter(f => !f.hidden);
    const COLS_P = ['nombre', 'fase', 'plazo', 'pend'];
    const compararProy = (k: string) => (a: HTMLElement, b: HTMLElement) => {
        const siempre = Number(a.dataset.orden) - Number(b.dataset.orden);
        if (!k) return siempre;
        const x = a.dataset[k] || '', y = b.dataset[k] || '';
        if (x === y) return siempre;
        if (!x || !y) return x ? -1 : 1;
        if (k === 'pend') return Number(y) - Number(x);
        if (k === 'fase') return Number(x) - Number(y);
        return x.localeCompare(y);
    };
    // las iniciativas (proyectos.ts, iniciativas.ts): lo buscado, como en los proyectos; un grupo se ve si le queda alguna,
    // y la que lo encabeza se ve con él aunque no calce (dice de qué programa son). Devuelve [las que se ven, todas]
    const aplicarIniciativas = (partes: string[]): [number, number] => {
        const c = $('iniciativas'); if (!c) return [0, 0];
        const filas = [...c.querySelectorAll<HTMLElement>('.ini')];
        const calza = conTodas(partes);
        const conAlguna = new Set(filas.filter(f => !f.classList.contains('ini-cabeza') && calza(f)).map(f => f.dataset.grupo ?? ''));
        let n = 0;
        for (const f of filas) {
            const cabeza = f.classList.contains('ini-cabeza');
            f.hidden = !calza(f) && !(cabeza && conAlguna.has(f.dataset.grupo ?? ''));
            if (!f.hidden && (calza(f) || !partes.length)) n += 1;
        }
        for (const g of c.querySelectorAll<HTMLElement>('.ini-grupo')) g.hidden = !conAlguna.has(g.dataset.grupo ?? '');
        const cols = c.querySelector<HTMLElement>('.ini-cols'); if (cols) cols.hidden = n === 0;
        const cab = c.querySelector<HTMLElement>('.ini-sec-cab .proy-sec-n'); if (cab) cab.textContent = String(n);
        return [n, filas.length];
    };
    function aplicarProyectos(): void {
        const partes = norm(estado.pq).split(/\s+/).filter(Boolean);
        const [ni, totalI] = aplicarIniciativas(partes);
        const c = $('proyectos');
        if (!c) {
            // solo las iniciativas: lo buscado se cuenta igual
            const cuenta = $('proyectos-cuenta'); if (cuenta) cuenta.textContent = partes.length ? `${ni} de ${totalI}` : '';
            return;
        }
        const area = (estado.pf || {}).area || '';
        const k = COLS_P.includes(estado.ordenP ?? '') ? estado.ordenP! : '';
        const filas = [...c.querySelectorAll<HTMLElement>('.proy, .proy-sec-cab')].sort(compararProy(k));
        const vacio = $('proyectos-vacio');
        for (const f of filas) c.insertBefore(f, vacio);
        for (const s of todos('.proy-cols [data-orden-p]')) s.classList.toggle('activo', s.dataset.ordenP === (k || 'estado'));
        let n = 0, total = 0;
        const porSec = new Map<string, number>();
        for (const f of filas) {
            if (!f.classList.contains('proy')) continue;
            total += 1;
            f.hidden = !conTodas(partes)(f) || (!!area && f.dataset.unidad !== area) || (f.dataset.sec === 'cerrado' && !estado.pc && !partes.length);
            f.classList.toggle('primera', !f.hidden && n === 0 && partes.length > 0);
            if (!f.hidden) { n += 1; porSec.set(f.dataset.sec ?? '', (porSec.get(f.dataset.sec ?? '') ?? 0) + 1); }
        }
        // la cabecera de una sección: solo en el orden de siempre, y si le queda alguna fila
        for (const cab of filas) {
            if (cab.classList.contains('proy')) continue;
            const kk = porSec.get(cab.dataset.sec ?? '') ?? 0;
            cab.hidden = !!k || kk === 0;
            const cuenta = cab.querySelector('.proy-sec-n'); if (cuenta) cuenta.textContent = String(kk);
        }
        if (vacio) { vacio.hidden = n > 0 || ni > 0; vacio.textContent = 'sin resultados'; }
        const cuenta = $('proyectos-cuenta');
        if (cuenta) cuenta.textContent = partes.length ? `${n + ni} de ${total + totalI}` : '';
        $('ver-cerrados')?.classList.toggle('activo', !!estado.pc);
        // la tabla extendida: a lo ancho, sin el detalle, todas las columnas en palabras (proyectos.css)
        c.closest('.proy-dos')?.classList.toggle('extendida', !!estado.px);
        $('ver-extendida')?.classList.toggle('activo', !!estado.px);
        for (const b of todos('[data-pf]')) b.classList.toggle('activo', ((estado.pf || {})[b.dataset.pf ?? ''] || '') === b.dataset.pv);
    }
    // un texto del resumen de un proyecto, cortado a seis líneas sin partir ninguna: al final del último bloque que
    // cabe, o en la última línea entera del que no cabe (un párrafo, un ítem); una tabla que no cabe queda para «más».
    // false si cabe entero
    const cortar = (r: HTMLElement): boolean => {
        const lh = parseFloat(getComputedStyle(r).lineHeight) || 20;
        const tope = 6 * lh;
        r.style.maxHeight = '';
        if (r.scrollHeight <= tope + 2) { r.style.maxHeight = 'none'; return false; }
        const base = r.getBoundingClientRect().top;
        let corte = 0;
        const bajar = (el: Element): boolean => {
            for (const c of el.children) {
                const b = c.getBoundingClientRect(), arriba = b.top - base, abajo = b.bottom - base;
                if (abajo <= tope) { corte = abajo; continue; }
                if (arriba >= tope) return true;
                if (/^(UL|OL|BLOCKQUOTE|DIV)$/.test(c.tagName) && c.children.length && bajar(c)) return true;
                if (/^(P|LI|H\d|DT|DD)$/.test(c.tagName)) {
                    const cs = getComputedStyle(c), lc = parseFloat(cs.lineHeight) || lh, pt = parseFloat(cs.paddingTop) || 0;
                    const n = Math.floor((tope - arriba - pt) / lc);
                    if (n > 0) corte = arriba + pt + n * lc;
                }
                return true;
            }
            return false;
        };
        bajar(r);
        r.style.maxHeight = `${Math.max(corte, lh)}px`;
        return true;
    };
    // el detalle de un proyecto: la pestaña que se ve (la misma al elegir otro), y «más» bajo lo recortado del
    // resumen solo si no cabe (proyectos.ts)
    const aplicarDetalle = () => {
        const det = $('proy-det'); if (!det) return;
        const pest = estado.pd === 'pendientes' || estado.pd === 'documento' ? estado.pd : 'resumen';
        det.dataset.ver = pest;
        for (const a of det.querySelectorAll<HTMLElement>('.det-pest [data-pest]')) a.classList.toggle('sel', a.dataset.pest === pest);
        for (const r of det.querySelectorAll<HTMLElement>(`.det-pane[data-pane="${pest}"] .recorte:not(.entero)`)) {
            const mas = r.nextElementSibling;
            const corto = cortar(r);
            if (mas instanceof HTMLElement && mas.classList.contains('mas')) mas.hidden = !corto;
        }
    };
    // elegir un proyecto: se marca al tiro y se pide su detalle (la derecha la cambia el Dashboard)
    const elegirProy = (f: HTMLElement | undefined) => {
        if (!f) return;
        for (const x of todos('.proy.sel')) x.classList.remove('sel');
        f.classList.add('sel');
        f.scrollIntoView({ block: 'nearest' });
        enviar({ tipo: 'accion', accion: 'proy-sel', valor: f.dataset.valor });
    };
    const moverProy = (paso: number) => {
        const vis = proyectosVisibles(); if (!vis.length) return;
        const i = vis.findIndex(f => f.classList.contains('sel'));
        elegirProy(vis[i < 0 ? 0 : Math.max(0, Math.min(vis.length - 1, i + paso))]);
    };

    // el globo: el texto entero de una tarea al detenerse sobre ella, cuando la fila lo corta. Va dentro del
    // dashboard, que es su contenedor (container-type: size, en dia.css): su posición, relativa a él
    /** lo que pidieron los lienzos y espera respuesta: a qué iframe va, y con qué id suyo */
    const esperanLienzo = new Map<string, { fuente: Window; suyo: string }>();
    const globo = document.createElement('div'); globo.id = 'globo'; globo.hidden = true; raiz.appendChild(globo);
    let globoEspera = 0;
    const esconderGlobo = () => { clearTimeout(globoEspera); globo.hidden = true; };
    raiz.addEventListener('mouseover', e => {
        const f = (e.target as HTMLElement).closest?.<HTMLElement>('[data-completo]');
        if (!f) return esconderGlobo();
        if (!globo.hidden && globo.dataset.de === f.dataset.valor) return;
        esconderGlobo();
        globoEspera = window.setTimeout(() => {
            globo.textContent = f.dataset.completo ?? ''; globo.dataset.de = f.dataset.valor ?? ''; globo.hidden = false;
            const caja = raiz.getBoundingClientRect(), r = f.getBoundingClientRect(), g = globo.getBoundingClientRect();
            const x = Math.max(4, Math.min(r.left - caja.left + 12, caja.width - g.width - 4));
            const abajo = r.bottom + 4 + g.height <= caja.bottom;
            globo.style.left = `${x + raiz.scrollLeft}px`;
            globo.style.top = `${(abajo ? r.bottom + 4 : Math.max(caja.top + 4, r.top - g.height - 4)) - caja.top + raiz.scrollTop}px`;
        }, 350);
    });
    raiz.addEventListener('mouseleave', esconderGlobo);
    raiz.addEventListener('scroll', esconderGlobo, true);

    // un lienzo que pide guardar su memoria: solo se acepta de un iframe de lienzo de este dashboard, y el Dashboard
    // decide el archivo (el que declaró la página), nunca el lienzo
    // un lienzo que pide algo (`window.lienzo.pedir`): igual, solo de un lienzo de aquí; la respuesta vuelve a ese iframe
    window.addEventListener('message', e => {
        const d = e.data as { lienzo?: string; llave?: unknown; datos?: unknown; id?: unknown; orden?: unknown } | null;
        if (!d || typeof d.llave !== 'string' || !todos<HTMLIFrameElement>('iframe.lienzo').some(f => f.contentWindow === e.source)) return;
        if (d.lienzo === 'guardar' && typeof d.datos === 'string') enviar({ tipo: 'lienzo-guardar', valor: d.llave, datos: d.datos });
        if (d.lienzo === 'aviso' && typeof d.datos === 'string') enviar({ tipo: 'lienzo-aviso', valor: d.llave, datos: d.datos.slice(0, 120) });
        if (d.lienzo === 'pedir' && typeof d.id === 'string' && typeof d.orden === 'string') {
            const id = `${d.llave}:${d.id}`;
            esperanLienzo.set(id, { fuente: e.source as Window, suyo: d.id });
            // lo que el lienzo dice en sus coordenadas (dónde se hizo clic, para un menú) pasa a las de la página
            const marco = todos<HTMLIFrameElement>('iframe.lienzo').find(f => f.contentWindow === e.source)?.getBoundingClientRect();
            const datos = d.datos as { x?: unknown; y?: unknown } | undefined;
            const donde = marco && typeof datos?.x === 'number' && typeof datos?.y === 'number'
                ? { x: marco.left + datos.x, y: marco.top + datos.y } : undefined;
            enviar({ tipo: 'lienzo-pedir', valor: d.llave, accion: d.orden, datos: JSON.stringify({ id, datos: d.datos }), donde });
        }
    });

    // ── el formulario de un proceso periódico ──
    let esperaHorario = 0;
    const filtrarSkills = () => {
        const f = $<HTMLInputElement>('per-skill-filtro');
        if (!f) return;
        const q = norm(f.value || '').trim();
        // «sin skill» siempre se ve
        for (const x of todos('#per-skills .skill')) x.hidden = !!q && !!x.dataset.skill && !(x.dataset.texto ?? '').includes(q);
    };
    const formPer = () => {
        const v = (id: string) => $<HTMLInputElement>(id)?.value ?? '';
        const form = $('form-per')!;
        return { nombre: v('per-nombre'), descripcion: v('per-desc'), tipo: form.classList.contains('tipo-comando') ? 'comando' : 'mensaje',
            skill: v('per-skill'), texto: v('per-mensaje'), destino: form.dataset.destino ?? 'hilo',
            comando: v('per-comando'), hilo: v('per-hilo'), max: v('per-max'), args: v('per-args'),
            cuando: v('per-cuando'), carpeta: v('per-carpeta'), activo: !!$<HTMLInputElement>('per-activo')?.checked,
            despues: todos('[data-per-tras].activa').map(x => x.dataset.perTras ?? '').filter(Boolean),
            padre: raiz.querySelector<HTMLElement>('[data-per-padre].activa')?.dataset.perPadre ?? '' };
    };
    /** Lo que le va a llegar al agente: la skill y lo que va después, a la vista mientras se escribe. */
    const decirPrompt = () => {
        const d = $('per-dice');
        if (d) d.textContent = armarPrompt($<HTMLInputElement>('per-skill')?.value ?? '', $<HTMLTextAreaElement>('per-mensaje')?.value ?? '') || '—';
    };
    /** Las skills de quien lo hace: las de la carpeta del agente elegido, o las de la carpeta del hilo nuevo. */
    const pedirSkills = () => {
        const f = $('form-per');
        if (!f) return;
        const destino = f.dataset.destino ?? 'hilo';
        const carpeta = destino === 'hilo' ? ($<HTMLInputElement>('per-carpeta')?.value ?? '').trim()
            : raiz.querySelector<HTMLElement>(`[data-per-destino="${CSS.escape(destino)}"]`)?.dataset.carpeta ?? '';
        enviar({ tipo: 'per-skills', valor: carpeta, accion: destino });
    };
    const guardarPer = () => enviar({ tipo: 'accion', accion: 'per-guardar', valor: JSON.stringify(formPer()) });
    raiz.addEventListener('input', e => {
        const t = e.target as HTMLInputElement;
        if (t.id === 'per-cuando') { clearTimeout(esperaHorario); const c = t.value; esperaHorario = window.setTimeout(() => enviar({ tipo: 'per-horario', valor: c }), 350); return; }
        if (t.id === 'per-skill-filtro') { filtrarSkills(); return; }
        if (t.id === 'per-mensaje') { decirPrompt(); return; }
        if (t.id === 'buscar-p') { estado.pq = t.value; guardar(); aplicarProyectos(); return; }
        if (t.id === 'buscar-t') { estado.tq = t.value; guardar(); aplicarTareas(); return; }
        if (t.classList.contains('buscar-c')) { estado.cq = { ...estado.cq, [t.dataset.bloque ?? '']: t.value }; guardar(); aplicarCorreo(); return; }
        if (t.id !== 'buscar') return;
        estado.q = t.value; estado.todas = false; guardar(); aplicar();
    });
    raiz.addEventListener('change', e => {
        const t = e.target as HTMLInputElement;
        if (t.id === 'per-carpeta' && $('form-per')?.dataset.destino === 'hilo') pedirSkills();
    });
    raiz.addEventListener('click', e => {
        const t = e.target as HTMLElement;
        // guardar lleva lo escrito: se adelanta al manejador general, que mandaría la acción vacía
        if (t.closest('[data-accion="per-guardar"]')) { e.preventDefault(); e.stopPropagation(); guardarPer(); return; }
        const tipo = t.closest<HTMLElement>('[data-per-tipo]');
        if (tipo) {
            const f = $('form-per')!; f.classList.remove('tipo-mensaje', 'tipo-comando'); f.classList.add(`tipo-${tipo.dataset.perTipo}`);
            for (const x of todos('[data-per-tipo]')) x.classList.toggle('activa', x === tipo);
            return;
        }
        // a quién: un agente (sus skills, su casilla) o un hilo nuevo (con su nombre, su carpeta y sus argumentos)
        const destino = t.closest<HTMLElement>('[data-per-destino]');
        if (destino) {
            e.preventDefault();
            const f = $('form-per')!;
            f.dataset.destino = destino.dataset.perDestino ?? 'hilo';
            f.classList.toggle('destino-hilo', f.dataset.destino === 'hilo');
            f.classList.toggle('destino-agente', f.dataset.destino !== 'hilo');
            for (const x of todos('[data-per-destino]')) x.classList.toggle('activa', x === destino);
            pedirSkills();
            return;
        }
        // de quién cuelga cada hilo que abre: uno solo (o nadie)
        const padre = t.closest<HTMLElement>('[data-per-padre]');
        if (padre) { e.preventDefault(); for (const x of todos('[data-per-padre]')) x.classList.toggle('activa', x === padre); return; }
        const tras = t.closest<HTMLElement>('[data-per-tras]');
        if (tras) { e.preventDefault(); tras.classList.toggle('activa'); return; }
        const h = t.closest<HTMLElement>('[data-per-horario]');
        if (h) { const c = $<HTMLInputElement>('per-cuando')!; c.value = h.dataset.perHorario ?? ''; enviar({ tipo: 'per-horario', valor: c.value }); return; }
        const sk = t.closest<HTMLElement>('[data-skill]');
        if (sk && $('form-per')) {
            e.preventDefault();
            const skill = sk.dataset.skill ?? '';
            $<HTMLInputElement>('per-skill')!.value = skill;
            for (const x of todos('#per-skills .skill')) x.classList.toggle('activa', x === sk);
            const hilo = $<HTMLInputElement>('per-hilo'), nombre = $<HTMLInputElement>('per-nombre');
            if (skill && nombre && !nombre.value && !nombre.disabled) nombre.value = skill.replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
            if (skill && hilo && !hilo.value) hilo.placeholder = skill;
            decirPrompt();
            const m = $<HTMLTextAreaElement>('per-mensaje')!;
            m.focus(); m.setSelectionRange(m.value.length, m.value.length);
        }
    }, true);
    // arrastrar una tarjeta (`data-arrastra`, la de «foco») a una casilla (`data-suelta`): la acción de la casilla, con
    // «<casilla>|<tarjeta>» como valor
    let arrastrada = '';
    raiz.addEventListener('dragstart', e => {
        const c = (e.target as HTMLElement).closest<HTMLElement>('[data-arrastra]');
        if (!c) return;
        arrastrada = c.dataset.arrastra ?? '';
        c.classList.add('arrastrando');
        e.dataTransfer?.setData('text/plain', arrastrada);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
    });
    raiz.addEventListener('dragend', e => {
        (e.target as HTMLElement).closest('[data-arrastra]')?.classList.remove('arrastrando');
        for (const x of todos('[data-suelta].encima')) x.classList.remove('encima');
        arrastrada = '';
    });
    raiz.addEventListener('dragover', e => {
        if (!arrastrada) return;
        // donde caería: la casilla de abajo, y ninguna si se salió de ellas
        const z = (e.target as HTMLElement).closest<HTMLElement>('[data-suelta]');
        for (const x of todos('[data-suelta].encima')) if (x !== z) x.classList.remove('encima');
        if (!z) return;
        e.preventDefault();
        z.classList.add('encima');
    });
    raiz.addEventListener('drop', e => {
        const z = (e.target as HTMLElement).closest<HTMLElement>('[data-suelta]');
        for (const x of todos('[data-suelta].encima')) x.classList.remove('encima');
        if (!z || !arrastrada) return;
        e.preventDefault();
        enviar({ tipo: 'accion', accion: z.dataset.accion, valor: `${z.dataset.suelta}|${arrastrada}` });
        arrastrada = '';
    });
    raiz.addEventListener('click', e => {
        const t = e.target as HTMLElement;
        const u = t.closest<HTMLElement>('[data-url]');
        if (u) { e.preventDefault(); e.stopPropagation(); enviar({ tipo: 'url', url: u.dataset.url }); return; }
        const ot = t.closest<HTMLElement>('[data-orden-t]');
        if (ot) { estado.to = ot.dataset.ordenT ?? ''; guardar(); aplicar(); return; }
        // el orden de «tareas» (componentes/orden.ts): la opción que rige, otra vez, vuelve a la urgencia
        const oc = t.closest<HTMLElement>('.orden [data-accion="orden-grupo"][data-id^="tareas:"]');
        if (oc) { const k = (oc.dataset.id ?? '').slice(7); estado.ordenC = estado.ordenC === k ? '' : k; guardar(); aplicarTareas(); return; }
        if (t.closest('#tareas-t-mas')) { estado.tm = 'todas'; guardar(); aplicarTareas(); return; }
        // los filtros de «tareas» (componentes/filtros.ts): uno plegado abre su menú; una opción rige, y otro clic en la
        // que rige la suelta (el modo vuelve a «esta semana»; el área y el responsable, a ninguno)
        const fa = t.closest<HTMLElement>('.filtros [data-accion="filtro-abrir"]');
        if (fa) { void abrirFiltro(fa, entidades.dondeDe(e, fa)); return; }
        const fo = t.closest<HTMLElement>('.filtros [data-accion="filtro"]');
        if (fo) { elegirFiltro(fo.dataset.id ?? ''); return; }
        if (t.closest('#ver-cerrados')) { estado.pc = !estado.pc; guardar(); aplicarProyectos(); return; }
        if (t.closest('#ver-extendida')) { estado.px = !estado.px; guardar(); aplicarProyectos(); return; }
        // una pestaña del detalle de un proyecto (o «los N pendientes» del resumen): se cambia aquí, sin ir y volver
        const pd = t.closest<HTMLElement>('#proy-det [data-pest]');
        if (pd) { estado.pd = pd.dataset.pest; guardar(); aplicarDetalle(); const det = $('proy-det'); if (det) det.scrollTop = 0; return; }
        const mas = t.closest<HTMLElement>('#proy-det .mas');
        if (mas) {
            const r = mas.previousElementSibling;
            if (r instanceof HTMLElement) { r.classList.add('entero'); r.style.maxHeight = ''; }
            mas.hidden = true; return;
        }
        // el nombre de una columna de proyectos: ordena por ella; otra vez, o «estado», vuelve al orden de siempre
        const op = t.closest<HTMLElement>('[data-orden-p]');
        if (op) { const k = op.dataset.ordenP ?? ''; estado.ordenP = k === 'estado' || estado.ordenP === k ? '' : k; guardar(); aplicarProyectos(); return; }
        // un filtro de la lista de proyectos: área y tipo eligen uno; «con hilo» y «con pendientes» se prenden y apagan
        const bf = t.closest<HTMLElement>('[data-pf]');
        if (bf) {
            const pf = { ...(estado.pf || {}) }, k = bf.dataset.pf ?? '';
            pf[k] = pf[k] === bf.dataset.pv && (k === 'hilo' || k === 'pend') ? '' : bf.dataset.pv ?? '';
            estado.pf = pf; guardar(); aplicarProyectos(); return;
        }
        const fp = t.closest<HTMLElement>('.proy[data-accion="proy-sel"]');
        // el ⋯ de una fila, o el estado de una iniciativa que se cambia aquí: la elige y abre su menú (las acciones, o el
        // vocabulario de estados: lo manda el manejador general)
        if (fp && t.closest('.menu-fila, .ini-estado[data-accion]')) elegirProy(fp);
        // en la tabla extendida no se ve el detalle: elegir uno vuelve a la tabla de siempre, con su detalle al lado
        else if (fp) { e.preventDefault(); if (estado.px) { estado.px = false; guardar(); aplicarProyectos(); } elegirProy(fp); return; }
        // un enlace del README: lo abre el Dashboard (un archivo del repositorio o una pestaña)
        const ln = t.closest<HTMLAnchorElement>(':is(.proy-readme, .det-md, .det-datos) a[href]');
        if (ln) {
            e.preventDefault();
            const base = ln.closest<HTMLElement>('[data-base]')?.dataset.base || '';
            enviar({ tipo: 'accion', accion: 'proy-enlace', valor: ln.getAttribute('href') ?? '', datos: base });
            return;
        }
        const m = t.closest<HTMLElement>('[data-modo-tareas]');
        if (m) { estado.modo = m.dataset.modoTareas ?? ''; estado.q = ''; estado.todas = false; guardar(); const b = $<HTMLInputElement>('buscar'); if (b) b.value = ''; aplicar(); return; }
        if (t.closest('#tareas-mas')) { estado.todas = true; guardar(); aplicar(); return; }
        const a = t.closest<HTMLElement>('[data-accion]');
        // el ✓ tacha la fila al tiro, en cualquier lista (la de tareas, Hacer de Táctica, un bloque): hecha, sale cuando el
        // proveedor termina (tareas.ts); si no, vuelve como estaba y se dice por qué
        // (también los ✓ de la columna de acciones: la fila se tacha y el ✓ es un círculo que se llena mientras el
        // proveedor trabaja: componentes/circulo.ts)
        if (a && (a.dataset.accion === 'hecha' || a.dataset.accion === 'hecha-fila' || a.dataset.accion === 'hecha-vineta')) {
            a.closest('.tarea, .item')?.classList.add('marcada');
            if (a.classList.contains('rap') || a.classList.contains('item-accion')) { a.classList.add('girando'); a.innerHTML = circulo({ mov: 'llena' }); }
        }
        // un botón que manda lo escrito en un campo (el de escribirle al agente sobre una reunión)
        const campo = a?.dataset.campo ? $<HTMLTextAreaElement>(a.dataset.campo) : null;
        if (campo && !campo.value.trim()) { campo.focus(); return; }
        if (a) enviar({ tipo: 'accion', accion: a.dataset.accion, valor: a.dataset.valor, nuevo: e.metaKey || e.ctrlKey, datos: campo ? campo.value : undefined,
            donde: entidades.dondeDe(e, a) });
        if (campo) campo.value = '';
    });

    // el clic derecho sobre una fila que tiene menú (su ⋯: un proyecto, una tarea, un pendiente) lo abre ahí mismo
    raiz.addEventListener('contextmenu', e => {
        const fila = (e.target as HTMLElement).closest('.proy, .tarea, .fila, .est-u');
        const menu = fila?.querySelector<HTMLElement>('.menu-fila[data-accion], .item-menu[data-accion]');
        if (!menu?.dataset.accion) return;
        e.preventDefault();
        if (fila?.classList.contains('proy')) elegirProy(fila as HTMLElement);
        enviar({ tipo: 'accion', accion: menu.dataset.accion, valor: menu.dataset.valor, donde: entidades.dondeDe(e) });
    });

    // las teclas: solo mientras el dashboard se ve, y no si se escribe en un campo de afuera (la barra, una terminal)
    // ni hay un diálogo abierto (un campo, un menú: web/interfaz.ts), que se queda con las suyas
    window.addEventListener('keydown', e => {
        if (!visible() || document.querySelector('dialog[open]')) return;
        const activo = document.activeElement;
        if (activo && activo !== document.body && !raiz.contains(activo) && escribiendoEn(activo)) return;
        tecla(e, activo);
    });
    function tecla(e: KeyboardEvent, activo: Element | null): void {
        // escribiéndole al agente sobre una reunión: las letras son del campo; ⌘⏎ envía, ⎋ sale del campo
        if (activo?.id === 'ev-texto') {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); $('ev-enviar')?.click(); return; }
            if (e.key === 'Escape') { e.preventDefault(); (activo as HTMLElement).blur(); }
            return;
        }
        // escribiendo en el formulario de un periódico: las letras son del campo, no atajos
        if ($('form-per')) {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); guardarPer(); return; }
            const escribiendo = escribiendoEn(activo);
            if (e.key === 'Escape') { e.preventDefault(); if (escribiendo) { (activo as HTMLElement).blur(); return; } enviar({ tipo: 'accion', accion: 'per-cancelar' }); return; }
            if (escribiendo) return;
        }
        const bp = $<HTMLInputElement>('buscar-p');
        if (bp && activo === bp) {         // en proyectos: ⏎ abre el primero que calza
            if (e.key === 'Escape') { e.preventDefault(); if (bp.value) { bp.value = ''; estado.pq = ''; guardar(); aplicarProyectos(); } else enviar({ tipo: 'accion', accion: 'dia' }); }
            else if (e.key === 'Enter') { e.preventDefault(); const vis = proyectosVisibles(); const f = vis.find(x => x.classList.contains('sel')) || vis[0]; if (f) enviar({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); }
            else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); moverProy(e.key === 'ArrowDown' ? 1 : -1); }
            return;
        }
        if (bp && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'j' || e.key === 'k')) { e.preventDefault(); moverProy(e.key === 'ArrowDown' || e.key === 'j' ? 1 : -1); return; }
        if (bp && e.key === 'Enter') { const f = raiz.querySelector<HTMLElement>('.proy.sel'); if (f && !f.hidden) { e.preventDefault(); enviar({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); return; } }
        if (bp && e.key === 'Escape') { e.preventDefault(); enviar({ tipo: 'accion', accion: 'dia' }); return; }
        if (bp && e.key === '/') { e.preventDefault(); bp.focus(); return; }
        const b = $<HTMLInputElement>('buscar');
        if (b && activo === b) {           // escribiendo: las letras son de la búsqueda
            if (e.key === 'Escape') { e.preventDefault(); if (b.value) { b.value = ''; estado.q = ''; guardar(); aplicar(); } else b.blur(); }
            else if (e.key === 'Enter') { e.preventDefault(); const f = visibles()[0]; if (f) enviar({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor, nuevo: e.metaKey || e.ctrlKey }); }
            return;
        }
        // la ficha de una tarea: ⏎ la acción principal, ← → la propuesta anterior o siguiente, ⎋ vuelve a hoy
        // escribiendo en la ficha (el porqué de una lectura): las teclas son del campo, y ⎋ sale de él
        if ($('ficha-tarea') && escribiendoEn(activo) && raiz.contains(activo)) {
            if (e.key === 'Escape') { e.preventDefault(); (activo as HTMLElement).blur(); }
            return;
        }
        if ($('ficha-tarea') && !e.metaKey && !e.ctrlKey && !e.altKey) {
            const acc = ({ Enter: 'tarea-principal', ArrowRight: 'tarea-siguiente', ArrowLeft: 'tarea-anterior', Escape: 'volver-ficha' } as Record<string, string>)[e.key];
            if (acc) { e.preventDefault(); enviar({ tipo: 'accion', accion: acc }); return; }
        }
        // en la ficha de un proceso periódico: ⏎ lo corre ahora, ⎋ vuelve a la lista
        if ($('ficha-per') && !e.metaKey && !e.ctrlKey && !e.altKey) {
            if (e.key === 'Enter') { e.preventDefault(); enviar({ tipo: 'tecla', k: '⏎' }); return; }
            if (e.key === 'Escape') { e.preventDefault(); enviar({ tipo: 'accion', accion: 'periodicos' }); return; }
        }
        // en el calendario, ← → cambian de día
        if ($('cal-dia') && !e.metaKey && !e.ctrlKey && !e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
            e.preventDefault(); enviar({ tipo: 'accion', accion: 'cal-dia', valor: e.key === 'ArrowLeft' ? '-1' : '1' }); return;
        }
        // en «tareas»: escribir en la búsqueda; ⏎ abre la primera que se ve; / va a buscar
        // el buscador de la bandeja: ⎋ lo vacía, y otra vez lo suelta; / lo enfoca
        const bc = raiz.querySelector<HTMLInputElement>('input.buscar-c');
        if (bc && activo instanceof HTMLInputElement && activo.classList.contains('buscar-c')) {
            if (e.key === 'Escape') {
                e.preventDefault();
                if (activo.value) { activo.value = ''; estado.cq = { ...estado.cq, [activo.dataset.bloque ?? '']: '' }; guardar(); aplicarCorreo(); } else activo.blur();
            }
            return;
        }
        if (bc && e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey && !escribiendoEn(activo)) { e.preventDefault(); bc.focus(); return; }
        const bt = $<HTMLInputElement>('buscar-t');
        if (bt && activo === bt) {
            if (e.key === 'Escape') { e.preventDefault(); if (bt.value) { bt.value = ''; estado.tq = ''; guardar(); aplicarTareas(); } else bt.blur(); return; }
            if (e.key !== 'Enter') return;
        }
        if (bt && e.key === '/') { e.preventDefault(); bt.focus(); return; }
        if ($('revisar') && e.key === 'Enter') {
            const f = raiz.querySelector<HTMLElement>('#revisar .tarea:not([hidden])');
            if (f) { e.preventDefault(); enviar({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor }); return; }
        }
        if (e.metaKey || e.ctrlKey || e.altKey) return;    // los atajos con modificador son del navegador
        // lo que queda (una letra, ⎋) es un atajo del dashboard: no si se está escribiendo en otro campo suyo
        if (escribiendoEn(activo)) return;
        if (e.key === '/') { e.preventDefault(); b?.focus(); return; }
        // un correo abierto al lado de la lista: ⎋ lo cierra y deja la lista
        if (e.key === 'Escape' && raiz.querySelector('.dividido')) { enviar({ tipo: 'accion', accion: 'item-volver' }); return; }
        if (e.key === 'Escape') { enviar({ tipo: 'accion', accion: 'volver' }); return; }
        if (e.key.length === 1) { e.preventDefault(); enviar({ tipo: 'tecla', k: e.key }); }
    }

    const vista: VistaDia = {
        get visible() { return visible(); },
        responderLienzo(id, respuesta) {
            const quien = esperanLienzo.get(id);
            if (!quien) return;
            esperanLienzo.delete(id);
            quien.fuente.postMessage({ lienzo: 'respuesta', id: quien.suyo, ...respuesta }, '*');
        },
        pintar(html, barra = '') {
            esconderGlobo();
            if (barra !== barraPintada) { barraDia.innerHTML = barra; barraPintada = barra; }
            const activo = document.activeElement as HTMLInputElement | null;
            // el foco se recupera solo si estaba en el dashboard: si no, es de la barra o de un hilo
            const adentro = !!activo && raiz.contains(activo);
            const id = adentro ? activo!.id : '';
            const enCorreo = adentro && activo!.classList.contains('buscar-c') ? activo!.dataset.bloque ?? '' : undefined;
            const pos = id === 'buscar' || id === 'buscar-p' || id === 'buscar-t' || enCorreo !== undefined ? activo!.selectionStart ?? 0 : 0;
            // lo que se está escribiendo sobre una reunión sobrevive al repintado de cada minuto
            const ta = $<HTMLTextAreaElement>('ev-texto');
            const previo = ta ? { ev: ta.dataset.evento, v: ta.value, foco: (activo as Element | null) === ta, s: ta.selectionStart } : null;
            dia.innerHTML = html;
            const nt = $<HTMLTextAreaElement>('ev-texto');
            if (previo && nt && nt.dataset.evento === previo.ev) { nt.value = previo.v; if (previo.foco) { nt.focus(); nt.setSelectionRange(previo.s, previo.s); } }
            const nb = $<HTMLInputElement>('buscar');
            if (nb) { nb.value = estado.q; if (id === 'buscar') { nb.focus(); nb.setSelectionRange(pos, pos); } }
            const nt2 = $<HTMLInputElement>('buscar-t');
            if (nt2) { nt2.value = estado.tq || ''; if (id === 'buscar-t') { nt2.focus(); nt2.setSelectionRange(pos, pos); } }
            const np = $<HTMLInputElement>('buscar-p');
            // en proyectos, el buscador toma el foco al llegar (si nadie más lo tiene: la barra, un hilo)
            const libre = adentro || !activo || activo === document.body;
            if (np) { np.value = estado.pq; if (libre && (id === 'buscar-p' || id !== 'buscar') && visible()) { np.focus(); np.setSelectionRange(pos || np.value.length, pos || np.value.length); } }
            for (const i of todos<HTMLInputElement>('input.buscar-c')) {
                i.value = estado.cq?.[i.dataset.bloque ?? ''] ?? '';
                if (enCorreo !== undefined && i.dataset.bloque === enCorreo) { i.focus(); i.setSelectionRange(pos, pos); }
            }
            aplicar(); aplicarProyectos(); aplicarCorreo(); aplicarDetalle();
        },
        parcial(id, html) {
            const el = $(id);
            if (!el) return;
            // el mismo proyecto que se repinta (llegaron sus pendientes, su README): queda abierto lo que estaba abierto,
            // y donde se estaba leyendo; otro proyecto parte de arriba
            const mismo = el.querySelector<HTMLElement>('[data-mismo]')?.dataset.mismo;
            const abiertos = [...el.querySelectorAll<HTMLElement>('details[open][data-k], .entero[data-k]')].map(x => x.dataset.k ?? '');
            const arriba = el.scrollTop;
            el.innerHTML = html; filtrarSkills();
            if (mismo && el.querySelector<HTMLElement>('[data-mismo]')?.dataset.mismo === mismo) {
                for (const k of abiertos) {
                    const x = el.querySelector<HTMLElement>(`[data-k="${CSS.escape(k)}"]`);
                    if (x instanceof HTMLDetailsElement) x.open = true; else if (x) { x.classList.add('entero'); x.style.maxHeight = ''; }
                }
                el.scrollTop = arriba;
            } else el.scrollTop = 0;
            if (id === 'proy-det') aplicarDetalle();
        },
        filtrarTareas(modo) {
            estado.tm = modo;
            estado.tq = '';
            guardar();
        },
        cuentasProyectos(cuentas) {
            // cuántos pendientes tiene cada proyecto: llegan después de la lista, a su columna
            for (const f of todos('.proy')) {
                const k = cuentas[f.dataset.valor ?? ''] || 0;
                f.dataset.pend = k ? String(k) : '';
                const celda = f.querySelector('.tareas-p'); if (celda) celda.textContent = k ? String(k) : '';
            }
            aplicarProyectos();
        },
    };
    return vista;
}
