// La línea del pulso en la página: debajo de la franja de avisos (web/franja.ts), la última pasada de pulso que la
// persona no ha visto, y un clic abre la ventana con todas las sin ver (componentes/pulso.ts dibuja). Al cerrarla, quedan
// vistas hasta la más nueva que mostró: lo lleva telar en la máquina donde viven las pasadas (POST /resultados/<clave>/visto),
// así que vale igual en el laptop y en el teléfono. Una que llegó mientras se miraba no queda vista: sigue en la línea.
//
// Lee la configuración una vez: el resultado con `pasadas = "pulso"` (el primero, si hubiera dos). Sin uno, no pide nada y
// no hay línea. Relee lo sin ver cada dos minutos mientras la página se mira, y al volver a ella. Si no se pudo leer, lo dice
// la franja (`fuente:pulso`) y la línea queda como estaba.
//
// Lo de un mundo solo se ve con ese mundo puesto (web/mundo.ts, `filtrando`): la línea y la ventana muestran lo de ese mundo
// y lo sin clasificar (componentes/pulso.ts, `delMundo`), y se vuelven a dibujar al cambiar de mundo, sin leer de nuevo.
// Cerrar la ventana marca visto con el mundo que tenía al abrirse: lo de ese mundo y lo sin clasificar; lo de otro mundo
// de esas pasadas sigue sin ver hasta mirarlo con él. Con ambos (o en el modo todo, donde el mundo no esconde), todo.
//
// Lo que hace cada cosa llega en `Hacer`: el de verdad es `HACER` (la API); la prueba (pruebas/pulso.mjs) le pasa uno con un
// fetch de mentira, y el ensayo (`window.telar.ensayoPulso()`), uno que no toca nada.

import * as cli from '../cli';
import { conVisto, delMundo, hayCambios, hoyLocal, linea, ventanaPulso } from '../componentes/pulso';
import { pasadasDeMuestra } from '../componentes/muestras-pulso';
import * as avisos from './avisos';
import { I } from './iconos';
import * as mundos from './mundo';

/** Lo que la línea y la ventana le piden al mundo. */
export interface Hacer {
    leer(clave: string): Promise<cli.Respuesta<cli.JsonSinVer>>;
    /** marcar vistas hasta `id` con `mundo` puesto ("" ambos) */
    marcar(clave: string, id: string, mundo: string): Promise<cli.Respuesta<cli.JsonVisto>>;
    /** abrir una dirección (`tarea:T580`) o una web */
    ir(direccion: string): void;
    web(url: string): void;
    /** decir algo al pasar (un toast) */
    decir(texto: string): void;
    /** el mundo que filtra ahora ("" ambos, o el modo todo); sin esto, ambos */
    mundo?(): string;
    /** la tinta de cada mundo, para su nombre */
    colores?(): Record<string, string>;
}

/** Lo que es de una página: la línea y lo que sabe de las pasadas sin ver. Sin DOM: lo prueba Node. */
export class Pulso {
    datos?: cli.JsonSinVer;
    error = '';
    /** con la ventana abierta, lo que se relee no cambia lo que se muestra (ni lo que se marcará visto) */
    abierta = false;
    /** el mundo con que se abrió la ventana: al cerrarla, se marca con ese aunque el mundo haya cambiado mientras */
    private mundoAbierto?: string;

    constructor(readonly hacer: Hacer, readonly clave: string, readonly nombre = clave) {}

    /** El mundo que filtra: el de la ventana abierta, o el de ahora. */
    get mundo(): string { return this.mundoAbierto ?? this.hacer.mundo?.() ?? ''; }

    /** Lo que se ve con el mundo de ahora: las pasadas, cuántas son y hasta cuál vio. */
    vista(mundo = this.mundo) { return delMundo(this.datos, mundo); }

    /** Releer lo sin ver. Devuelve si cambió lo que se muestra. */
    async leer(): Promise<boolean> {
        const r = await this.hacer.leer(this.clave);
        if (!r.datos?.ok) {
            this.error = r.datos?.error || r.error || 'no se pudo leer';
            return false;
        }
        this.error = '';
        if (this.abierta) return false;
        const huella = (d?: cli.JsonSinVer) => JSON.stringify([d?.pasadas?.map(p => [p.id, p.sin_ver_en]) ?? [], d?.total ?? 0, d?.por_mundo ?? {}]);
        const antes = huella(this.datos);
        this.datos = r.datos;
        return huella(r.datos) !== antes;
    }

    /** La línea, o '' si no hay nada que cambió sin ver con el mundo puesto. */
    linea(hoy = hoyLocal()): string {
        const v = this.vista();
        return linea({ ...v, nombre: this.nombre, hoy, mundo: this.mundo, colores: this.hacer.colores?.() });
    }

    /** La más nueva que se muestra (con cambios o sin ellos): hasta esa quedan vistas al cerrar. */
    get masNueva(): string { return this.vista().pasadas[0]?.id ?? ''; }

    /** Si hay algo que cambió sin ver, con el mundo puesto: solo entonces hay línea y se abre la ventana. */
    get conCambios(): boolean { return this.vista().pasadas.some(hayCambios); }

    /** Abrir la ventana: desde aquí, lo que se relee no cambia lo que se muestra, y el mundo queda el de ahora. */
    abrir(): void {
        this.abierta = true;
        this.mundoAbierto = this.hacer.mundo?.() ?? '';
    }

    ventana(hoy = hoyLocal()) {
        const v = this.vista();
        return ventanaPulso({ ...v, nombre: this.nombre, hoy, mundo: this.mundo, colores: this.hacer.colores?.() });
    }

    /** La ventana se cerró: vistas hasta la más nueva que mostró, con el mundo que tenía (lo de ese mundo y lo sin
     *  clasificar; con ambos, todo). Si sale, la línea se va (hasta que llegue otra); lo de otro mundo queda para cuando se
     *  mire con él. Si no sale, se dice y queda. */
    async cerrada(): Promise<boolean> {
        const mundo = this.mundo;
        const id = this.masNueva;
        this.abierta = false;
        this.mundoAbierto = undefined;
        if (!id) return true;
        const r = await this.hacer.marcar(this.clave, id, mundo);
        if (!r.datos?.ok) {
            this.hacer.decir(`no quedaron vistas: ${r.datos?.error || r.error || 'no respondió'}`);
            return false;
        }
        // lo que llegó después de la más nueva que se mostró sigue sin ver: se sabrá al releer
        this.datos = conVisto(this.datos ?? { ok: true }, id, mundo, r.datos);
        return true;
    }
}

export const HACER: Hacer = {
    leer: clave => cli.pasadasSinVer(clave),
    marcar: (clave, id, mundo) => cli.marcarVisto(clave, id, mundo),
    ir: direccion => { void import('./ui').then(ui => ui.abrirDireccion(direccion)); },
    web: url => { void import('./ui').then(ui => ui.abrirExterno(url)); },
    decir: texto => { void import('./ui').then(ui => ui.estado(texto)); },
    mundo: () => mundos.filtrando(),
    colores: () => Object.fromEntries(mundos.declarados().map(m => [m.clave, m.color])),
};

// ── en la página ────────────────────────────────────────────────────────────

let pulso: Pulso | undefined;
let lugar: HTMLElement | undefined;
const CADA = 2 * 60 * 1000;

function pintar(): void {
    if (!lugar || !pulso) return;
    const html = pulso.linea();
    if (lugar.innerHTML !== html) lugar.innerHTML = html;
}

/** Lo que no se pudo leer, en la franja (sin conexión, lo dice el aviso de la conexión). */
function avisar(p: Pulso): void {
    if (!p.error) { avisos.quitar('fuente:pulso'); return; }
    avisos.poner({ clave: 'fuente:pulso', nivel: 'falla', icono: I.alerta, conConexion: true, texto: `no se pudo leer ${p.nombre}`,
        detalle: `${p.error.replace(/[.]?$/, '.')} La línea del pulso es la de la última vez.`,
        hacer: 'Se vuelve a leer sola cada dos minutos; si sigue, `telar resultado pulso --sin-ver` en un terminal dice lo mismo.' });
}

async function releer(): Promise<void> {
    if (!pulso || document.hidden) return;
    await pulso.leer();
    if (pulso.hacer === HACER) avisar(pulso);
    pintar();
}

/** Abrir la ventana con las sin ver (releídas antes, si se puede). Al cerrarla, quedan vistas. */
export async function abrir(p = pulso): Promise<void> {
    if (!p || p.abierta) return;
    await p.leer();
    pintar();
    if (!p.conCambios) return;
    p.abrir();
    const { abrirVentana } = await import('./ventana');
    const { enlazar } = await import('./rutas-agente');
    let ir: { direccion?: string; web?: string } = {};
    await abrirVentana<string>(p.ventana(), {
        clase: 'pulso-dialogo',
        montar: (d, cerrar) => {
            // las direcciones que van dentro de una línea («ver tarea:T470»), como enlaces, igual que en la terminal
            const cuerpo = d.querySelector<HTMLElement>('.ventana-cuerpo');
            if (cuerpo) enlazar(cuerpo, false);
            d.addEventListener('click', e => {
                const a = (e.target as HTMLElement).closest<HTMLElement>('[data-direccion], [data-web]');
                if (!a || !d.contains(a)) return;
                e.preventDefault();
                ir = a.dataset.direccion ? { direccion: a.dataset.direccion } : { web: a.dataset.web };
                cerrar('ir');
            });
        },
    });
    await p.cerrada();
    pintar();
    if (ir.direccion) p.hacer.ir(ir.direccion);
    else if (ir.web) p.hacer.web(ir.web);
    // y lo que haya llegado mientras
    if (p === pulso) void releer();
}

/** Ponerla debajo de la franja (`barra`: #barra, con la franja ya montada) y empezar a leer, si hay un pulso declarado. */
export async function montar(barra: HTMLElement): Promise<void> {
    lugar = document.createElement('div');
    lugar.id = 'pulso';
    lugar.className = 'pulso-lugar';
    const franja = barra.querySelector('#franja');
    if (franja) franja.after(lugar); else barra.prepend(lugar);
    lugar.addEventListener('click', e => {
        if ((e.target as HTMLElement).closest('[data-accion="pulso-abrir"]')) { e.preventDefault(); void abrir(); }
    });
    // otro mundo (o el modo todo): lo mismo leído, mirado con él
    mundos.alCambiar(pintar);
    const c = await cli.config();
    const r = c.datos?.resultados?.find(x => x.pasadas === 'pulso');
    if (!r) return;
    pulso = new Pulso(HACER, r.clave, r.nombre || r.clave);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) void releer(); });
    setInterval(() => void releer(), CADA);
    // «13:00» pasa a ser «ayer 13:00» a la medianoche
    setInterval(pintar, 60 * 1000);
    await releer();
}

// ── el ensayo: pasadas de mentira en la página de verdad ──

/** La línea y, con `abrir`, la ventana, con pasadas de mentira (componentes/muestras-pulso.ts; de trabajo, personales y
 *  sin clasificar), vistas con el mundo puesto, sin leer ni marcar nada: cerrarla dice qué haría. Mientras, la línea de
 *  verdad deja de releerse; ↻ (recargar) la vuelve. */
export async function ensayo(abrirla = true): Promise<string> {
    const muestra = pasadasDeMuestra();
    const falso: Hacer = {
        leer: async () => ({ datos: muestra }),
        marcar: async (_c, id, mundo) => {
            falso.decir(`(ensayo) quedarían vistas hasta ${id}${mundo ? ` en ${mundo}` : ''}`);
            return { datos: { ok: true, visto: mundo ? muestra.visto : { id }, vistos: mundo ? { ...muestra.vistos, [mundo]: { id }, '': { id } } : {} } };
        },
        ir: d => falso.decir(`(ensayo) abriría ${d}`),
        web: u => falso.decir(`(ensayo) abriría ${u}`),
        decir: t => { void import('./ui').then(ui => ui.estado(t)); },
        mundo: HACER.mundo,
        colores: HACER.colores,
    };
    pulso = new Pulso(falso, 'pulso', 'pulso');
    await pulso.leer();
    pintar();
    if (abrirla) void abrir(pulso);
    return `${muestra.total} pasadas de mentira`;
}
