// A qué máquinas se puede llevar un hilo desde su menú (el ⋯ de su fila, web/ordenes.ts), y qué dice cada fila. Desde
// cualquier máquina, a cualquier otra de la persona: las de `[remotos]` (por ssh) y las que se ven en el bus (su foto,
// GET /espejos). Una fila por máquina, con su nombre: «llevar a laptop», no «llevar a otra máquina» (que no decía
// adónde y se perdía al final del menú). Una que no contesta se ve apagada y dice por qué; nunca desaparece.
//
// Un hilo que vive aquí se lleva (`telar hilo llevar`). Uno que vive en otra máquina se trae aquí, o esa lo lleva a una
// tercera (`POST /hilo/traer` con `a`): las dos que no son esta tienen que estar en línea. Con la suya apagada y una
// copia de su conversación aquí, «traer» no puede, pero se puede **seguir aquí** desde esa copia (telar.seguir, la etapa
// 4 de la mudanza): quien arma el menú le pregunta antes a telar (`GET /hilo/seguir`) y lo pasa en `seguir`.
//
// Solo arma datos y textos: quien los pone en el menú (web/ordenes.ts) atiende el clic. Lo prueba pruebas/llevar.mjs,
// en Node: npm run prueba:llevar.

import { fueraDeLinea, type MaquinaAlcance } from './alcance';

/** Una máquina a la que llevarlo, con lo que dice su fila. `apagado`: por qué no se puede ahora ("" si se puede). */
export interface FilaLlevar {
    /** `llevar`: el hilo vive aquí. `traer`: vive en `desde` y viene aquí. `llevar-desde`: vive en `desde` y va a `a`.
     *  `seguir`: vive en `desde`, que está apagada, y se sigue aquí desde la copia de aquí */
    modo: 'llevar' | 'traer' | 'llevar-desde' | 'seguir';
    /** adónde va */
    a: string;
    /** dónde vive ("" si aquí) */
    desde: string;
    /** por ssh (de `[remotos]`) o por el bus */
    por: 'ssh' | 'bus';
    label: string;
    description: string;
    apagado: string;
}

export interface Contexto {
    /** esta máquina (la que sirve la página) */
    aqui: string;
    /** dónde vive el hilo: "" o igual a `aqui` si aquí; '?' si no se sabe */
    vive: string;
    /** las de `[remotos]` */
    remotos: { nombre: string; destino?: string }[];
    /** las otras máquinas del bus, de sus fotos */
    otras: MaquinaAlcance[];
    ahora?: number;
    /** con la máquina del hilo apagada, si se puede seguir aquí (lo que dijo `GET /hilo/seguir`); sin esto, no se sabe */
    seguir?: { puede: boolean; por_que_no?: string; aqui?: { bytes: number; fecha: string } | null;
        alla?: { bytes: number | null } | null };
}

/** «1,2 MB». */
const mb = (n: number): string => `${(n / 1e6).toFixed(1).replace('.', ',')} MB`;

/** «el 23-nov 07:14», corto, de una fecha ISO. */
function fechaCorta(iso: string, ahora: number): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const hh = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    const hoy = new Date(ahora);
    if (d.toDateString() === hoy.toDateString()) return `de hoy ${hh}`;
    const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    return `del ${d.getDate()}-${MESES[d.getMonth()]} ${hh}`;
}

/** La fila de seguir aquí, si se puede: «seguir aquí» con de cuándo es la copia de aquí y cuánto falta. */
function filaSeguir(o: Contexto, vive: string, suya: string, ahora: number): FilaLlevar | undefined {
    const s = o.seguir;
    if (!s?.puede || !s.aqui) return undefined;
    const copia = `la copia de aquí, ${fechaCorta(s.aqui.fecha, ahora)} (${mb(s.aqui.bytes)})`;
    const alla = s.alla?.bytes;
    const falta = alla === null || alla === undefined ? `no se sabe cuánto pesaba en ${vive}`
        : alla > s.aqui.bytes ? `faltan unos ${mb(alla - s.aqui.bytes)}` : 'no debería faltar nada';
    return { modo: 'seguir', a: o.aqui, desde: vive, por: 'bus', label: 'seguir aquí, desde la copia de aquí',
        description: `${suya}: ${copia}; ${falta}`, apagado: '' };
}

/** Hace cuánto, corto: «3 min», «2 h», «4 d». */
const hace = (s: number): string => s < 90 ? `${Math.max(1, Math.round(s))} s` : s < 5400 ? `${Math.round(s / 60)} min`
    : s < 129600 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`;

/** Por qué no se puede contar con `nombre` ahora ("" si se puede, o si no se sabe). Por el bus hace falta su nodo: una
 *  foto vieja basta para apagarla. Por ssh (`ssh`), solo si se sabe que está fuera de línea: una de [remotos] sin foto
 *  en el bus, o con su nodo caído, se intenta igual y, si no contesta, lo dice la mudanza. */
export function porQueNo(nombre: string, otras: readonly MaquinaAlcance[], ahora = Date.now(), ssh = false): string {
    const m = otras.find(x => x.nombre === nombre);
    if (!m || m.en_linea) return '';
    if (m.fuera) return fueraDeLinea(m, ahora);
    if (ssh) return '';
    return m.edad !== null && m.edad !== undefined ? `${nombre} no da noticias hace ${hace(m.edad)}` : `${nombre} no da noticias`;
}

/** Las máquinas que no son esta, en orden: primero las de [remotos], después las del bus. Sin repetir. Una de [remotos]
 *  que también está en el bus va por el bus (telar.dueno: por ssh ya no se mudan hilos si hay bus). */
export function maquinas(o: Pick<Contexto, 'aqui' | 'remotos' | 'otras'>): { nombre: string; por: 'ssh' | 'bus' }[] {
    const vistas = new Set<string>([o.aqui]);
    const salida: { nombre: string; por: 'ssh' | 'bus' }[] = [];
    const delBus = new Set(o.otras.map(m => m.nombre));
    for (const r of o.remotos) if (r.nombre && !vistas.has(r.nombre)) {
        vistas.add(r.nombre);
        salida.push({ nombre: r.nombre, por: delBus.has(r.nombre) ? 'bus' : 'ssh' });
    }
    for (const m of o.otras) if (m.nombre && !vistas.has(m.nombre)) { vistas.add(m.nombre); salida.push({ nombre: m.nombre, por: 'bus' }); }
    return salida;
}

/** Las filas del menú de un hilo para llevarlo: una por máquina, encendida o apagada con su porqué. */
export function filasLlevar(o: Contexto): FilaLlevar[] {
    const ahora = o.ahora ?? Date.now();
    const aqui = o.aqui || 'esta máquina';
    const vive = o.vive && o.vive !== o.aqui ? o.vive : '';
    const todas = maquinas(o);
    const viaja = 'su conversación viaja; los archivos no';
    if (!vive) {
        return todas.map(m => {
            const apagado = porQueNo(m.nombre, o.otras, ahora, m.por === 'ssh');
            return { modo: 'llevar', a: m.nombre, desde: '', por: m.por, label: `llevar a ${m.nombre}`,
                description: apagado ? `${apagado}: no tiene dónde recibirlo` : `${viaja} · ${m.por === 'ssh' ? 'por ssh' : 'por el bus'}`,
                apagado: apagado ? `${apagado}: no tiene dónde recibirlo` : '' };
        });
    }
    if (vive === '?') return [];
    // vive en otra: traerlo aquí, o que esa lo lleve a una tercera. Lo hace su máquina: tiene que contestar. Con ella
    // apagada, seguir aquí desde la copia de aquí, si la hay (y si no, por qué no, en la de traer)
    const suya = porQueNo(vive, o.otras, ahora);
    const seguir = suya ? filaSeguir(o, vive, suya, ahora) : undefined;
    const sinTraer = suya && o.seguir?.por_que_no && !seguir ? o.seguir.por_que_no : `${suya}: su conversación vive allá`;
    const filas: FilaLlevar[] = seguir ? [seguir] : [{
        modo: 'traer', a: o.aqui, desde: vive, por: 'bus', label: `traer a ${aqui} (esta máquina)`,
        description: suya ? sinTraer : `vive en ${vive}: ${viaja}`,
        apagado: suya ? sinTraer : '',
    }];
    for (const m of todas) {
        if (m.nombre === vive) continue;
        const destino = porQueNo(m.nombre, o.otras, ahora);
        const apagado = suya ? `${suya}: su conversación vive allá` : destino ? `${destino}: no tiene dónde recibirlo` : '';
        filas.push({ modo: 'llevar-desde', a: m.nombre, desde: vive, por: 'bus', label: `llevar a ${m.nombre}`,
            description: apagado || `vive en ${vive}: ${vive} lo lleva; ${viaja}`, apagado });
    }
    return filas;
}
