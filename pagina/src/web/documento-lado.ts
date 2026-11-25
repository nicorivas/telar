// La barra de la derecha del visor de un documento (web/carpeta.ts): lo que acompaña al texto sin meterse en él. Tiene
// hasta tres hojas, cada una en su pestaña con su cuenta: los **comentarios** (web/comentarios.ts: la lista en el orden del
// documento, cada uno con su número, que es el mismo que lleva su tramo en el texto; ahí se responde, se resuelve y se
// escribe uno nuevo), las **conexiones** del grafo (lo que sale y lo que llega) y los **datos** del frontmatter de un .md
// (web/frontmatter.ts: cada clave con su valor), que solo aparece si el documento tiene uno.
//
// Se pliega como la ficha de la derecha de un hilo (web/lado.ts): la flecha › al final de las pestañas la pliega y queda
// una franja angosta con ‹ arriba y el nombre de cada hoja en vertical, con su cuenta (un clic abre esa hoja). Se
// arrastra su línea, como las barras de la página (web/anchos.ts): el ancho se recuerda por pantalla, y el doble clic
// vuelve al de fábrica. Ni una ni otra tienen tecla, así que esta tampoco.
//
// Con qué abre: si el documento tiene comentarios abiertos, en comentarios; si no, como se dejó la última vez (plegada, de
// fábrica; abierta, en la hoja que se eligió). Lo que se elige a mano se recuerda en este navegador.
//
// En el teléfono (`body.angosto`) no hay columna al lado: la barra es una hoja que sube desde abajo. Plegada, una franja
// abajo con sus pestañas y sus cuentas; un toque en una (o en un tramo comentado, o «comentar») la sube hasta un poco
// más de la mitad, y la flecha ⌄ la baja. Ahí empieza siempre plegada, y lo que se haga no se recuerda: es de paso.

import { esc } from '../estilo';
import * as anchos from './anchos';
import { I } from './iconos';
import { pestanas } from '../componentes/pestanas';
import { acomodar } from './pestanas';

export type Hoja = 'comentarios' | 'conexiones' | 'datos';
const HOJAS: Hoja[] = ['comentarios', 'conexiones', 'datos'];
/** las que no están siempre: aparecen solo si el documento las tiene */
const A_VECES: Hoja[] = ['datos'];

/** lo que se recuerda: si se dejó plegada y en qué hoja (el ancho va con los de la página, web/anchos.ts) */
export const CLAVE = 'telar.visor.lado';
/** el ancho de fábrica, en px; y los topes */
export const ANCHO = 320;
export const MINIMO = 240;
/** ni más que esta parte de la ventana del visor */
export const FRACCION = 0.5;

export interface Recordado { plegada: boolean; hoja: Hoja }
export const DE_FABRICA: Recordado = { plegada: true, hoja: 'conexiones' };

export function leerRecordado(almacen: Pick<Storage, 'getItem'> | null): Recordado {
    try {
        const v = JSON.parse(almacen?.getItem(CLAVE) ?? 'null') as Partial<Recordado> | null;
        if (!v || typeof v !== 'object') return { ...DE_FABRICA };
        return { plegada: typeof v.plegada === 'boolean' ? v.plegada : DE_FABRICA.plegada,
            hoja: HOJAS.includes(v.hoja as Hoja) ? v.hoja as Hoja : DE_FABRICA.hoja };
    } catch { return { ...DE_FABRICA }; }
}

/** Con qué abre un documento: con comentarios abiertos, en ellos; si no, lo recordado. En el teléfono, siempre plegada. */
export function inicial(abiertos: number, r: Recordado, telefono: boolean): Recordado {
    if (telefono) return { plegada: true, hoja: abiertos > 0 ? 'comentarios' : r.hoja };
    return abiertos > 0 ? { plegada: false, hoja: 'comentarios' } : r;
}

/** La cuenta de una hoja: cuántos, y si se dice en la tinta de lo que espera algo (los comentarios abiertos). */
export interface Cuenta { n: number | null; tinta?: boolean; ayuda?: string }

/** Lo de la página que usa la barra (en la prueba, de mentira). */
export interface EntornoLado {
    body: HTMLElement;
    almacen: Pick<Storage, 'getItem' | 'setItem'> | null;
    pantalla: () => { width: number; height: number };
}

const NOMBRE: Record<Hoja, string> = { comentarios: 'comentarios', conexiones: 'conexiones', datos: 'datos' };
const ICONO: Record<Hoja, string> = { comentarios: I.escribir, conexiones: I.enlace, datos: I.etiqueta };
const SIN_CUENTAS = (): Record<Hoja, Cuenta> => ({ comentarios: { n: null }, conexiones: { n: null }, datos: { n: null } });

export class Lado {
    hoja: Hoja = DE_FABRICA.hoja;
    plegada = true;
    private cuentas: Record<Hoja, Cuenta> = SIN_CUENTAS();
    /** las hojas de `A_VECES` que tiene el documento que se muestra */
    private tiene = new Set<Hoja>();
    /** si ya se decidió con qué abre el documento que se muestra (lo decide el primero que sabe: sus comentarios) */
    private decidido = false;
    private readonly barra: HTMLElement;
    private readonly hojas: Record<Hoja, HTMLElement>;

    constructor(readonly el: HTMLElement, private readonly e: EntornoLado, private readonly visor: HTMLElement) {
        el.classList.add('doc-lado');
        el.innerHTML = '<div class="tirador doc-tirador" title="arrastrar: el ancho de la barra · doble clic: el de fábrica"></div>'
            + '<div class="doc-lado-barra"></div>'
            + HOJAS.map(h => `<div class="doc-lado-hoja" data-hoja="${h}" hidden></div>`).join('');
        this.barra = el.querySelector<HTMLElement>('.doc-lado-barra')!;
        this.hojas = Object.fromEntries(HOJAS.map(h => [h, el.querySelector<HTMLElement>(`[data-hoja="${h}"]`)!])) as Record<Hoja, HTMLElement>;
        el.addEventListener('click', ev => {
            const a = (ev.target as HTMLElement).closest<HTMLElement>('[data-doc-lado]');
            if (!a || !el.contains(a)) return;
            ev.preventDefault();
            ev.stopPropagation();
            const que = a.dataset.docLado;
            if (que === 'plegar') this.plegar(true, true);
            else if (que === 'abrir') this.mostrar((a.dataset.hoja as Hoja | undefined) ?? this.vista, true);
            else if (que === 'hoja') this.mostrar(a.dataset.hoja as Hoja, true);
        });
        this.ponerAncho(this.anchoRecordado());
        this.tirador();
        this.pintar();
    }

    private get telefono(): boolean { return this.e.body.classList.contains('angosto'); }

    /** La hoja de una pestaña: donde la llena quien sabe de ella (la capa de comentarios, las conexiones). */
    lugar(h: Hoja): HTMLElement { return this.hojas[h]; }

    /** Un documento nuevo: las hojas, leyendo; las cuentas, sin saber; y con qué abre, por decidir. */
    empezar(): void {
        this.decidido = false;
        this.cuentas = SIN_CUENTAS();
        this.tiene.clear();
        for (const h of HOJAS) this.hojas[h].innerHTML = '<p class="nada">leyendo…</p>';
        this.mostrarse(true);
        // mientras se decide, como se dejó (sin esperar a los comentarios para dibujar la página)
        const r = inicial(0, leerRecordado(this.e.almacen), this.telefono);
        this.hoja = r.hoja; this.plegada = r.plegada;
        this.pintar();
    }

    /** Sin barra: una carpeta, los candidatos, un error. */
    ocultar(): void { this.mostrarse(false); }

    private mostrarse(si: boolean): void {
        this.el.hidden = !si;
        for (const x of this.lugares()) x.classList.toggle('con-lado', si);
    }

    /** Con qué abre, ahora que se sabe cuántos comentarios abiertos tiene (una vez por documento). */
    decidir(abiertos: number): void {
        if (this.decidido) return;
        this.decidido = true;
        const r = inicial(abiertos, leerRecordado(this.e.almacen), this.telefono);
        this.hoja = r.hoja; this.plegada = r.plegada;
        this.pintar();
    }

    /** Si el documento tiene la hoja `h` (una de las que no están siempre: los datos). Sin ella, su pestaña no aparece, y
     *  si estaba abierta en ella, se abre en las conexiones. */
    tener(h: Hoja, si: boolean): void {
        if (si) this.tiene.add(h); else this.tiene.delete(h);
        this.pintar();
    }

    /** Las hojas que tiene el documento que se muestra, en su orden. */
    private get visibles(): Hoja[] { return HOJAS.filter(h => !A_VECES.includes(h) || this.tiene.has(h)); }

    /** La hoja que se ve: la elegida, si el documento la tiene; si no, las conexiones (sin cambiar lo recordado). */
    private get vista(): Hoja { return this.visibles.includes(this.hoja) ? this.hoja : 'conexiones'; }

    cuenta(h: Hoja, c: Cuenta): void {
        this.cuentas[h] = c;
        this.pintarBarra();
    }

    /** Abre la barra en la hoja `h`. `aMano`: lo eligió la persona (se recuerda). */
    mostrar(h: Hoja, aMano = false): void {
        this.decidido = true;
        this.hoja = h;
        this.plegada = false;
        if (aMano) this.recordar();
        this.pintar();
    }

    plegar(si: boolean, aMano = false): void {
        this.decidido = true;
        this.plegada = si;
        if (aMano) this.recordar();
        this.pintar();
    }

    private recordar(): void {
        if (this.telefono) return;
        try { this.e.almacen?.setItem(CLAVE, JSON.stringify({ plegada: this.plegada, hoja: this.hoja })); } catch { /* sin almacén */ }
    }

    /** El visor y su ventana: llevan las clases de la barra (el ancho de la ventana y dónde va el texto dependen de ella). */
    private lugares(): HTMLElement[] {
        const v = this.visor.closest<HTMLElement>('.ventana');
        return v ? [this.visor, v] : [this.visor];
    }

    private pintar(): void {
        this.el.classList.toggle('plegada', this.plegada);
        for (const x of this.lugares()) x.classList.toggle('lado-plegado', this.plegada);
        for (const h of HOJAS) this.hojas[h].hidden = this.plegada || h !== this.vista;
        this.pintarBarra();
    }

    private numero(h: Hoja): string {
        const c = this.cuentas[h];
        if (c.n === null) return '';
        return `<span class="doc-lado-n${c.tinta ? ' tinta' : ''}">${c.n}</span>`;
    }

    private ayuda(h: Hoja): string { return this.cuentas[h].ayuda ?? NOMBRE[h]; }

    /** Las pestañas y la flecha; plegada, la franja (‹ y cada hoja en vertical; en el teléfono, una fila abajo). */
    private pintarBarra(): void {
        if (this.plegada) {
            const hojas = this.visibles.map(h => `<a class="doc-lado-vertical${this.telefono ? '' : ' v'}" data-doc-lado="abrir" data-hoja="${h}" title="${esc(this.ayuda(h))}">`
                + `<span class="i">${ICONO[h]}</span><span class="doc-lado-nombre">${NOMBRE[h]}</span>${this.numero(h)}</a>`).join('');
            this.barra.classList.remove('con-pestanas');
            this.barra.innerHTML = this.telefono
                ? `${hojas}<a class="doc-lado-pliegue i" data-doc-lado="abrir" title="mostrar la barra">${I.subir}</a>`
                : `<a class="doc-lado-pliegue i" data-doc-lado="abrir" title="mostrar la barra">${I.atras}</a>${hojas}`;
            return;
        }
        // abierta: las pestañas de la casa (componentes/pestanas.ts), con la flecha de plegar en su extremo; si no caben (tres
        // en una barra angosta), las que no caben van al «⋯» (web/pestanas.ts, `acomodar`)
        this.barra.classList.add('con-pestanas');
        this.barra.innerHTML = pestanas({ nombre: 'barra del documento', dato: 'doc-lado', accion: 'hoja', activa: this.vista, clases: ['doc-lado-pestanas'],
            fin: `<a class="doc-lado-pliegue i" data-doc-lado="plegar" title="plegar la barra">${this.telefono ? I.abierto : I.plegado}</a>`,
            pestanas: this.visibles.map(h => {
                const c = this.cuentas[h];
                return { valor: h, nombre: NOMBRE[h], icono: ICONO[h], datos: { hoja: h }, ayuda: c.ayuda && c.ayuda !== NOMBRE[h] ? c.ayuda : undefined,
                    ...(c.n === null ? {} : { cuenta: c.n, cuentaAtencion: !!c.tinta }) };
            }) });
        const fila = this.barra.querySelector('.pestanas');
        if (fila) acomodar(fila);
    }

    // ── el ancho ──

    private anchoRecordado(): number {
        const v = anchos.leer(this.e.almacen)[anchos.clavePantalla(this.e.pantalla())]?.documento;
        return typeof v === 'number' && Number.isFinite(v) ? v : ANCHO;
    }

    /** Los topes con una ventana del navegador de `ventana` px: de `MINIMO` a la mitad. */
    static topes(ventana: number): anchos.Topes { return { min: MINIMO, max: Math.max(MINIMO, Math.floor(ventana * FRACCION)) }; }

    private ponerAncho(px: number | undefined): void {
        for (const x of this.lugares()) {
            if (px === undefined) x.style.removeProperty('--doc-lado-ancho');
            else x.style.setProperty('--doc-lado-ancho', `${px}px`);
        }
    }

    /** La franja de su línea: arrastrarla cambia el ancho (la ventana crece o se achica con ella, así que el ancho se
     *  calcula en cada movimiento con dónde está el borde derecho ahora), y al soltar se recuerda para esta pantalla. */
    private tirador(): void {
        const f = this.el.querySelector<HTMLElement>('.doc-tirador')!;
        let desde = 0, ancho = 0;
        const caja = () => (this.visor.closest('.ventana') ?? this.visor).getBoundingClientRect();
        anchos.agarre(f, 'documento', this.e.body, {
            puede: () => !this.plegada && !this.telefono && !this.el.hidden,
            empezar: () => { desde = f.getBoundingClientRect().left + 3; ancho = this.el.getBoundingClientRect().width; },
            mover: dx => {
                const x = desde + dx, c = caja();
                ancho = anchos.acotar(c.right - x, Lado.topes(window.innerWidth));
                this.ponerAncho(ancho);
            },
            soltar: movida => { if (movida) anchos.recordar(this.e.almacen, anchos.clavePantalla(this.e.pantalla()), 'documento', ancho); },
            fabrica: () => { anchos.recordar(this.e.almacen, anchos.clavePantalla(this.e.pantalla()), 'documento', undefined); this.ponerAncho(ANCHO); },
        });
    }
}
