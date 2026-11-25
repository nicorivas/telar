// Las ventanas que piden los módulos (`[ventanas]` de su modulo.toml; telar.servicios.ventanas): cuando ocurre algo (un
// mensaje a un chat de foco de WhatsApp), sale una ventana en la página, esté donde esté la persona, para responder o
// aplazar. El vigía de aquí le pregunta a telar qué ventanas esperan (`GET /ventanas`, con el mundo puesto) y abre la que
// espera hace más; el contenido y los botones son del módulo (componentes/ventana-modulo.ts los dibuja).
//
// · Cuándo pregunta: al cargar la página, cada CADA (cada CADA_ABIERTA con una abierta, para cerrarla pronto si se
//   atendió en otra parte), al volver a la pestaña, al cambiar de mundo o el silencio, y cuando `/eventos` avisa
//   «ventanas» (un botón en otra pestaña de esta máquina). Con la pestaña escondida, no.
// · El estado no es de esta pestaña: es del módulo (lo que se respondió, lo aplazado). Responder o aplazar en una página
//   la cierra en las demás, aquí y en otras máquinas, cuando vuelven a preguntar; lo que llegó con la página cerrada sale
//   al abrirla, una vez.
// · No robar teclas: si se está escribiendo (una tecla hace menos de QUIETO) o el foco está en un campo (una caja, la
//   terminal, un lienzo), sale quieta (`abrirVentana` con `quieta`: sin fondo y sin tomar el foco), y lo que se escribe
//   sigue yendo adonde iba. Toma el teclado con un clic en ella, o sola cuando el foco sale de los campos y pasan QUIETO
//   sin teclear.
// · ⎋ y un clic fuera hacen lo que la ventana dice (`escape`: aplazar lo más corto), nunca «visto».
// · Los mundos: lo de otro mundo no llega a la página (telar no lo manda). Al cambiar de mundo, lo abierto de otro se
//   cierra al tiro, sin esperar la respuesta.
// · El silencio: «no molestar» a mano (en esta máquina: el ícono de la banda, o ⌘K) y, solo, durante una reunión del
//   calendario. Mientras, no se abre nada (lo abierto se cierra) y se pregunta solo cuántas esperan, sin su contenido;
//   al terminar, sale lo que llegó.
// · Responder: ⌘⏎ (o «enviar») manda lo escrito por la consulta que dice la ventana (WhatsApp: la de la persona en la
//   pestaña, `salida` con `accion = "enviar"`): solo un gesto de la persona lo hace. Se ve «enviando…» y después «enviado»
//   (siguiendo lo que la respuesta diga, `seguir`) o por qué no salió, y lo escrito vuelve a la caja.

import type * as cli from '../cli';
import { ventana } from '../componentes/ventana';
import { juntoHtml, propsVentanaModulo, type Envio } from '../componentes/ventana-modulo';
import { abrirVentana } from './ventana';

export interface Tiempos {
    /** entre preguntas, sin ninguna abierta */
    cada: number;
    /** con una abierta */
    cadaAbierta: number;
    /** sin teclear este tiempo (y sin el foco en un campo) la ventana toma el teclado */
    quieto: number;
    /** después de responder, cada cuánto se mira si salió, y hasta cuándo */
    seguirCada: number;
    seguirHasta: number;
    /** lo que se hizo aquí no vuelve a abrirse antes (lo que se preguntó antes de hacerlo puede llegar después) */
    suprimir: number;
    /** «enviado» se ve este rato antes de cerrarse */
    hecho: number;
}
export const TIEMPOS: Tiempos = { cada: 10000, cadaAbierta: 3000, quieto: 1500, seguirCada: 1500, seguirHasta: 60000, suprimir: 8000, hecho: 1500 };

export interface Dependencias {
    pedir(mundo: string, soloCuantas: boolean): Promise<cli.Respuesta<cli.JsonVentanas>>;
    accion(modulo: string, verbo: string, params: Record<string, unknown>): Promise<cli.Respuesta<Record<string, unknown>>>;
    silenciar(si: boolean): Promise<cli.Respuesta<cli.JsonSilencio>>;
    /** el mundo puesto ("" ambos) */
    mundo(): string;
    /** si una reunión del calendario está en curso: lo que dice el silencio («en reunión»), o "" */
    reunion(): string;
    /** abrir una dirección de la página (`pestana:whatsapp`), en un ítem suyo (el chat) */
    abrir(direccion: string, item: string): unknown;
    /** la ventana de la instrucción con ese contexto: si se mandó */
    instruccion(contexto: { texto: string; titulo: string }, desde: string): Promise<boolean>;
    ahora(): number;
    visible(): boolean;
    /** que cambió lo que se ve del silencio (el ícono de la banda) */
    alCambiar?(): void;
}

/** La clave de una ventana: su módulo y su id. */
export const clave = (v: Pick<cli.JsonVentana, 'modulo' | 'id'>): string => `${v.modulo}\u0000${v.id}`;

/** Lo que es escribir en otra parte: un campo, la terminal (xterm escribe en un textarea), un lienzo (un iframe). */
const CAMPO = 'input, textarea, select, iframe, [contenteditable], [contenteditable] *, .xterm, .xterm *';

/** Si la ventana puede tomar el teclado ya: nadie escribió en los últimos `quieto` ms y el foco no está en un campo. */
export function puedeTomar(activo: Element | null, ultimaTecla: number, ahora: number, quieto = TIEMPOS.quieto, doc: Document = document): boolean {
    if (ahora - ultimaTecla < quieto) return false;
    if (!activo || activo === doc.body || activo === doc.documentElement) return true;
    return !activo.matches(CAMPO);
}

interface Abierta {
    clave: string;
    v: cli.JsonVentana;
    cola: number;
    quieta: boolean;
    ocupada: boolean;
    envio?: Envio;
    falla?: string;
    d?: HTMLDialogElement;
    cerrar: () => void;
}

export class Vigia {
    /** lo que esperaba en la última respuesta (del mundo puesto) */
    pendientes: cli.JsonVentana[] = [];
    cuantas = 0;
    silencio: cli.JsonSilencio = { a_mano: false, desde: '' };
    /** si algún módulo pide ventanas (sin ninguno, la banda no muestra el silencio) */
    hay = false;
    abierta: Abierta | null = null;
    private readonly t: Tiempos;
    /** clave → hasta cuándo no se abre (Infinity: hasta que se suelte) */
    private readonly suprimidas = new Map<string, number>();
    private ultimaTecla = -Infinity;
    private reloj: ReturnType<typeof setTimeout> | undefined;
    private enCurso: Promise<void> | null = null;
    private otraVez = false;
    private montado = false;

    constructor(private readonly d: Dependencias, tiempos: Partial<Tiempos> = {}, private readonly doc: Document = document) {
        this.t = { ...TIEMPOS, ...tiempos };
    }

    /** Escuchar las teclas (para no robarlas), la vuelta a la pestaña, y empezar a preguntar. */
    montar(): void {
        if (this.montado) return;
        this.montado = true;
        this.doc.addEventListener('keydown', () => { this.ultimaTecla = this.d.ahora(); }, true);
        this.doc.addEventListener('visibilitychange', () => { if (this.d.visible()) void this.revisar(); });
        void this.revisar();
    }

    /** Si está en silencio, y por qué («no molestar», «en reunión»); "" si no. */
    enSilencio(): string {
        return this.silencio.a_mano ? 'no molestar' : this.d.reunion() ? this.d.reunion() : '';
    }

    /** Preguntar ahora (lo que se pide mientras ya se pregunta, se pregunta de nuevo al terminar). */
    revisar(): Promise<void> {
        if (this.enCurso) { this.otraVez = true; return this.enCurso; }
        this.enCurso = (async () => {
            try {
                do { this.otraVez = false; await this.una(); } while (this.otraVez);
            } finally {
                this.enCurso = null;
                this.programar();
            }
        })();
        return this.enCurso;
    }

    /** La próxima pregunta: pronto con una abierta, más espaciada sin. */
    programar(ms?: number): void {
        if (this.reloj !== undefined) clearTimeout(this.reloj);
        if (!this.montado) return;
        this.reloj = setTimeout(() => { this.reloj = undefined; void this.revisar(); }, ms ?? (this.abierta ? this.t.cadaAbierta : this.t.cada));
    }

    /** El mundo cambió: lo abierto de otro mundo se cierra ya, sin esperar a telar, y se pregunta de nuevo. */
    alCambiarMundo(): void {
        const a = this.abierta, m = this.d.mundo();
        if (a && m && a.v.mundo && a.v.mundo !== m && !a.ocupada) this.cerrar(a);
        void this.revisar();
    }

    /** «No molestar» a mano: prenderlo o apagarlo. */
    async silenciar(si = !this.silencio.a_mano): Promise<void> {
        const r = await this.d.silenciar(si);
        if (r.datos) this.silencio = r.datos;
        if (this.enSilencio() && this.abierta && !this.abierta.ocupada) this.cerrar(this.abierta);
        this.d.alCambiar?.();
        await this.revisar();
    }

    private suprimida(k: string): boolean {
        const hasta = this.suprimidas.get(k);
        if (hasta === undefined) return false;
        if (hasta > this.d.ahora()) return true;
        this.suprimidas.delete(k);
        return false;
    }

    private async una(): Promise<void> {
        if (!this.d.visible()) return;
        const mundo = this.d.mundo();
        const abierta = this.abierta;
        if (abierta && mundo && abierta.v.mundo && abierta.v.mundo !== mundo && !abierta.ocupada) this.cerrar(abierta);
        const callado = !!this.enSilencio();
        const r = await this.d.pedir(mundo, callado);
        if (!r.datos) return;   // telar no contestó: queda lo de antes
        this.hay = Array.isArray(r.datos.modulos) ? r.datos.modulos.length > 0 : this.hay || !!r.datos.ventanas?.length;
        this.silencio = r.datos.silencio ?? this.silencio;
        this.cuantas = r.datos.cuantas ?? 0;
        this.d.alCambiar?.();
        if (this.enSilencio()) {
            // en silencio no se abre nada, y lo abierto se cierra (una reunión que empieza con la pantalla compartida)
            this.pendientes = [];
            if (this.abierta && !this.abierta.ocupada && !this.abierta.envio) this.cerrar(this.abierta);
            return;
        }
        // salió del silencio (o el mundo cambió mientras se preguntaba): de nuevo, con su contenido
        if (callado || this.d.mundo() !== mundo) { this.otraVez = true; return; }
        this.pendientes = r.datos.ventanas;
        const visibles = this.pendientes.filter(v => !this.suprimida(clave(v)));
        const a = this.abierta;
        if (a) {
            const igual = this.pendientes.find(v => clave(v) === a.clave);
            // la atendieron en otra parte (otra pestaña, otra máquina, el teléfono): se cierra sola
            if (!igual) { if (!a.ocupada && !a.envio) this.cerrar(a); }
            else if (igual.version !== a.v.version || visibles.length !== a.cola) { a.v = igual; a.cola = visibles.length; this.repintar(a); }
        }
        if (!this.abierta && visibles.length) this.abrir(visibles[0], visibles.length);
    }

    /** Abrir una: quieta si se está escribiendo en otra parte. */
    private abrir(v: cli.JsonVentana, cola: number): void {
        const quieta = !puedeTomar(this.doc.activeElement, this.ultimaTecla, this.d.ahora(), this.t.quieto, this.doc);
        const a: Abierta = { clave: clave(v), v, cola, quieta, ocupada: false, cerrar: () => {} };
        this.abierta = a;
        let mirando: ReturnType<typeof setInterval> | undefined;
        void abrirVentana<string>(propsVentanaModulo(v, { cola, quieta, ahora: this.d.ahora() }), {
            clase: 'ventana-modulo-dialogo', quieta, foco: 'textarea.vm-caja',
            // ⎋ y un clic fuera: lo que dice la ventana (aplazar lo más corto), nunca «visto»; mientras algo corre, nada
            puedeCerrar: () => { if (!a.ocupada) void this.escape(a); return false; },
            montar: (d, cerrar) => {
                a.d = d;
                a.cerrar = () => cerrar();
                // ⌘⏎ escribiendo en un borrador lo aprueba a él, no lo de la caja de responder (va antes que las teclas del pie)
                d.addEventListener('keydown', e => {
                    const t = e.target as HTMLElement;
                    if (e.key !== 'Enter' || !(e.metaKey || e.ctrlKey) || e.isComposing || !t.matches?.('textarea.vm-btexto')) return;
                    e.preventDefault(); e.stopImmediatePropagation();
                    const i = (a.v.borradores ?? []).findIndex(x => x.id === t.closest<HTMLElement>('[data-vb]')?.dataset.vb);
                    if (i >= 0 && !e.repeat) void this.hacer(a, `aprobar:${i}`);
                }, true);
                d.addEventListener('click', e => {
                    const b = (e.target as HTMLElement).closest<HTMLElement>('[data-vm]');
                    if (!b || !d.contains(b)) return;
                    e.preventDefault();
                    if (b.matches('[disabled], [aria-disabled="true"]')) return;
                    void this.hacer(a, b.dataset.vm ?? '');
                });
                // un clic la toma (abrirVentana la vuelve modal): sin repintarla, que el clic siga en lo que se apretó
                d.addEventListener('pointerdown', () => { if (a.quieta) { a.quieta = false; this.ayudaAlDia(a); } }, true);
                this.alFondo(d);
                if (quieta) {
                    // toma el teclado sola cuando nadie escribe y el foco salió de los campos
                    mirando = setInterval(() => {
                        if (!a.quieta) { clearInterval(mirando); return; }
                        if (puedeTomar(this.doc.activeElement, this.ultimaTecla, this.d.ahora(), this.t.quieto, this.doc)) {
                            a.quieta = false;
                            d.dispatchEvent(new Event('tomar-foco'));
                            this.ayudaAlDia(a);
                        }
                    }, 250);
                }
                return () => { if (mirando) clearInterval(mirando); };
            },
        }).then(() => {
            if (this.abierta === a) this.abierta = null;
            // la siguiente, si espera otra
            this.programar(this.pendientes.length > 1 ? 300 : undefined);
        });
    }

    private cerrar(a: Abierta): void {
        a.cerrar();
        if (this.abierta === a) this.abierta = null;
    }

    private suprimir(k: string, ms = this.t.suprimir): void {
        this.suprimidas.set(k, ms === Infinity ? Infinity : this.d.ahora() + ms);
    }

    /** Lo de adentro de nuevo (cambió lo que llegó, o lo que se está haciendo), sin perder lo escrito ni el foco. */
    private repintar(a: Abierta): void {
        const d = a.d;
        if (!d) return;
        const caja = d.querySelector<HTMLTextAreaElement>('textarea.vm-caja');
        const texto = caja?.value ?? '', enfocada = !!caja && this.doc.activeElement === caja;
        const sel = caja ? [caja.selectionStart, caja.selectionEnd] : [0, 0];
        // lo editado en un borrador (por su id), y si tenía el foco
        const editados = new Map([...d.querySelectorAll<HTMLTextAreaElement>('[data-vb] textarea.vm-btexto')]
            .map(t => [t.closest<HTMLElement>('[data-vb]')!.dataset.vb ?? '', t.value] as const));
        const enBorrador = (this.doc.activeElement as HTMLElement | null)?.closest?.<HTMLElement>('[data-vb]')?.dataset.vb;
        d.innerHTML = ventana({ ...propsVentanaModulo(a.v, { cola: a.cola, quieta: a.quieta, envio: a.envio, falla: a.falla,
            ocupada: a.ocupada, ahora: this.d.ahora() }), lugar: 'centrada' });
        for (const t of d.querySelectorAll<HTMLTextAreaElement>('[data-vb] textarea.vm-btexto')) {
            const id = t.closest<HTMLElement>('[data-vb]')!.dataset.vb ?? '';
            if (editados.has(id)) t.value = editados.get(id)!;
            if (id === enBorrador) t.focus({ preventScroll: true });
        }
        const nueva = d.querySelector<HTMLTextAreaElement>('textarea.vm-caja');
        if (nueva) {
            nueva.value = texto;
            if (enfocada) { nueva.focus({ preventScroll: true }); try { nueva.setSelectionRange(sel[0] ?? 0, sel[1] ?? 0); } catch { /* sin selección */ } }
        }
        this.alFondo(d);
    }

    /** Lo pegado al título (cuántos nuevos, cuántas más esperan, si está quieta), sin tocar lo demás. */
    private ayudaAlDia(a: Abierta): void {
        const el = a.d?.querySelector<HTMLElement>('.ventana-junto');
        if (el) el.innerHTML = juntoHtml(a.v, { cola: a.cola, quieta: a.quieta });
    }

    /** Lo último a la vista. */
    private alFondo(d: HTMLElement): void {
        const l = d.querySelector<HTMLElement>('.vm-lineas');
        if (l) l.scrollTop = l.scrollHeight;
    }

    private async escape(a: Abierta): Promise<void> {
        const i = a.v.escape;
        if (i !== null && i !== undefined && a.v.acciones[i]) { await this.hacer(a, String(i)); return; }
        // sin un plazo que hacer: se cierra, y no vuelve hasta que llegue algo más
        this.suprimir(a.clave, this.t.cada * 3);
        this.cerrar(a);
    }

    /** Lo que hace un botón (su índice en `acciones`, o «responder»). */
    async hacer(a: Abierta, que: string): Promise<void> {
        if (a.ocupada || this.abierta !== a) return;
        if (que === 'responder') { await this.responder(a); return; }
        if (/^(aprobar|descartar):\d+$/.test(que)) { await this.borrador(a, que); return; }
        const v = a.v, b = v.acciones[Number(que)];
        if (!b) return;
        if (b.abrir) {
            this.suprimir(a.clave);
            if (b.despues) void this.d.accion(v.modulo, b.despues.verbo, b.despues.params);
            this.cerrar(a);
            this.d.abrir(b.abrir, b.item ?? '');
            return;
        }
        a.ocupada = true; a.falla = undefined; this.repintar(a);
        if (b.instruccion) {
            const r = await this.d.accion(v.modulo, b.instruccion.verbo, b.instruccion.params);
            if (!r.datos) { a.ocupada = false; a.falla = `no pude armar el contexto: ${r.error ?? 'falló'}`; this.repintar(a); return; }
            // la ventana de la instrucción, sola: esta se cierra, y no vuelve mientras aquella está abierta
            this.suprimir(a.clave, Infinity);
            this.cerrar(a);
            const mandado = await this.d.instruccion({ texto: String(r.datos.texto ?? ''), titulo: String(r.datos.titulo ?? v.titulo) },
                `la ventana de «${v.titulo}»`).catch(() => false);
            if (mandado && b.despues) await this.d.accion(v.modulo, b.despues.verbo, b.despues.params);
            // si se canceló, vuelve a salir
            this.suprimidas.delete(a.clave);
            if (!mandado) void this.revisar();
            return;
        }
        const r = await this.d.accion(v.modulo, b.verbo ?? '', b.params ?? {});
        if (!r.datos) { a.ocupada = false; a.falla = `no pude: ${r.error ?? 'falló'}`; this.repintar(a); return; }
        if (b.despues) await this.d.accion(v.modulo, b.despues.verbo, b.despues.params);
        this.suprimir(a.clave);
        this.cerrar(a);
    }

    /** Aprobar un borrador (con lo editado: sale como lo dejó quien lo pidió, con su firma y en su horario; es una
     *  respuesta, así que después se da por atendida y se cierra) o descartarlo (la ventana queda, sin él). */
    private async borrador(a: Abierta, que: string): Promise<void> {
        const [verbo, n] = que.split(':');
        const v = a.v, b = v.borradores?.[Number(n)];
        const llamada = verbo === 'aprobar' ? b?.aprobar : b?.descartar;
        if (!b || !llamada) return;
        const caja = a.d?.querySelector<HTMLTextAreaElement>(`[data-vb="${CSS.escape(b.id)}"] textarea.vm-btexto`);
        const texto = caja ? caja.value : b.texto;
        a.ocupada = true; a.falla = undefined;
        if (caja) b.texto = texto;
        this.repintar(a);
        const params = verbo === 'aprobar' && b.aprobar ? { ...llamada.params, [b.aprobar.campo || 'texto']: texto } : llamada.params;
        const r = await this.d.accion(v.modulo, llamada.verbo, params);
        a.ocupada = false;
        if (!r.datos) { a.falla = `no pude ${verbo === 'aprobar' ? 'aprobarlo' : 'descartarlo'}: ${r.error ?? 'falló'}`; this.repintar(a); return; }
        if (verbo === 'aprobar') {
            if (b.aprobar?.despues) await this.d.accion(v.modulo, b.aprobar.despues.verbo, b.aprobar.despues.params);
            this.suprimir(a.clave);
            this.cerrar(a);
            return;
        }
        a.v = { ...v, borradores: (v.borradores ?? []).filter(x => x.id !== b.id) };
        this.repintar(a);
    }

    /** Responder con lo escrito, por la consulta de la ventana; y seguirlo hasta que sale. */
    private async responder(a: Abierta): Promise<void> {
        const v = a.v, r0 = v.responder, d = a.d;
        if (!r0 || !d) return;
        const caja = d.querySelector<HTMLTextAreaElement>('textarea.vm-caja');
        const texto = (caja?.value ?? '').trim();
        if (!texto) { a.falla = 'escribe algo para responder (⌘⏎ lo envía)'; this.repintar(a); caja?.focus(); return; }
        a.ocupada = true; a.falla = undefined; a.envio = { texto, estado: 'enviando' };
        if (caja) caja.value = '';
        this.repintar(a);
        const devolver = (falla: string) => {
            a.ocupada = false; a.envio = undefined; a.falla = falla;
            this.repintar(a);
            const c = a.d?.querySelector<HTMLTextAreaElement>('textarea.vm-caja');
            if (c) { c.value = texto; c.focus({ preventScroll: true }); }
        };
        const r = await this.d.accion(v.modulo, r0.verbo, { ...r0.params, [r0.campo || 'texto']: texto });
        if (!r.datos) { devolver(`no pude enviar: ${r.error ?? 'falló'}`); return; }
        // respondido es atendido: las demás páginas la cierran
        this.suprimir(a.clave, this.t.seguirHasta);
        if (r0.despues) void this.d.accion(v.modulo, r0.despues.verbo, r0.despues.params);
        const seguir = r.datos.seguir as cli.JsonLlamada | undefined;
        const listo = () => {
            a.envio = { texto, estado: 'hecho' };
            this.repintar(a);
            setTimeout(() => { if (this.abierta === a) this.cerrar(a); void this.revisar(); }, this.t.hecho);
        };
        if (!seguir || typeof seguir.verbo !== 'string') { listo(); return; }
        const hasta = this.d.ahora() + this.t.seguirHasta;
        while (this.d.ahora() < hasta && this.abierta === a) {
            await new Promise(r => setTimeout(r, this.t.seguirCada));
            const s = await this.d.accion(v.modulo, seguir.verbo, seguir.params ?? {});
            const e = (s.datos?.seguimiento ?? {}) as { estado?: string; error?: string };
            if (e.estado === 'hecho') { listo(); return; }
            if (e.estado === 'falla') { a.envio = { texto, estado: 'falla', error: e.error ?? '' }; devolver(`no salió: ${e.error || 'falló'}; sigue escrito abajo`); return; }
        }
        // no se supo a tiempo: sigue en la cola (la pestaña dirá si sale)
        if (this.abierta === a) { a.ocupada = false; a.falla = 'sigue en camino: la pestaña dirá si no sale'; this.repintar(a); }
    }
}

// ── el ícono de la banda: «no molestar» ──

const CAMPANA = '\u{eaa2}', SILENCIO = '\u{ec08}';

/** El HTML del silencio en la banda: la campana (tenue, sin silencio) o tachada con por qué y cuántas esperan. */
export function silencioHtml(v: Pick<Vigia, 'enSilencio' | 'cuantas' | 'silencio'>): { html: string; ayuda: string; si: boolean } {
    const por = v.enSilencio();
    if (!por) return { html: `<span class="i">${CAMPANA}</span>`, si: false,
        ayuda: 'las ventanas de los módulos (un chat de foco) salen solas\nclic: no molestar (en esta máquina, hasta que lo apagues)' };
    const n = v.cuantas;
    return { si: true, html: `<span class="i">${SILENCIO}</span><span class="txt"> ${por}${n ? ` · ${n}` : ''}</span>`,
        ayuda: `${por}: ninguna ventana sale${n ? `; ${n} ${n === 1 ? 'espera' : 'esperan'} y salen al terminar` : ''}`
            + (v.silencio.a_mano ? '\nclic: que vuelvan a salir' : '\nmientras dura la reunión del calendario') };
}

/** Poner el ícono en su lugar de la banda y tenerlo al día. */
export function montarSilencio(lugar: HTMLElement, vigia: Vigia): () => void {
    const pintar = () => {
        lugar.hidden = !vigia.hay;
        const s = silencioHtml(vigia);
        lugar.innerHTML = s.html;
        lugar.title = s.ayuda;
        lugar.classList.toggle('si', s.si);
    };
    lugar.addEventListener('click', e => {
        e.preventDefault();
        // en una reunión sin el silencio a mano, el clic lo pone a mano (que dure después de la reunión, si se quiere)
        void vigia.silenciar(!vigia.silencio.a_mano).then(pintar);
    });
    pintar();
    return pintar;
}
