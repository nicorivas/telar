// Lo poco de VS Code que usa su eco predictivo (eco/prediccion.ts), escrito de nuevo y en chico: eventos,
// cosas que se desechan, un temporizador, un color y dos ayudantes. Lo demás de VS Code no hace falta.

export interface IDisposable { dispose(): void }

export function toDisposable(f: () => void): IDisposable { return { dispose: f }; }

export class DisposableStore implements IDisposable {
    private readonly cosas = new Set<IDisposable>();
    private desechado = false;
    add<T extends IDisposable>(t: T): T {
        if (this.desechado) t.dispose(); else this.cosas.add(t);
        return t;
    }
    dispose(): void {
        this.desechado = true;
        for (const c of this.cosas) { try { c.dispose(); } catch { /* que siga con los demás */ } }
        this.cosas.clear();
    }
}

export abstract class Disposable implements IDisposable {
    protected readonly _store = new DisposableStore();
    protected _register<T extends IDisposable>(t: T): T { return this._store.add(t); }
    dispose(): void { this._store.dispose(); }
}

export type Event<T> = (escucha: (e: T) => unknown) => IDisposable;

export class Emitter<T> implements IDisposable {
    private readonly escuchas = new Set<(e: T) => unknown>();
    readonly event: Event<T> = escucha => {
        this.escuchas.add(escucha);
        return toDisposable(() => this.escuchas.delete(escucha));
    };
    fire(e: T): void { for (const f of [...this.escuchas]) f(e); }
    dispose(): void { this.escuchas.clear(); }
}

export function disposableTimeout(f: () => void, ms: number, store?: DisposableStore): IDisposable {
    const t = setTimeout(() => { d.dispose(); f(); }, ms);
    const d = toDisposable(() => clearTimeout(t));
    store?.add(d);
    return d;
}

/** Una función que corre recién cuando dejaron de llamarla por `ms` (lo que en VS Code es `@debounce`). */
export function debounced<A extends unknown[]>(f: (...a: A) => void, ms: number): (...a: A) => void {
    let t: ReturnType<typeof setTimeout> | undefined;
    return (...a: A) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); };
}

export const escapeRegExpCharacters = (t: string): string => t.replace(/[\\{}*+?|^$.[\]()]/g, '\\$&');

export const isNumber = (x: unknown): x is number => typeof x === 'number' && !isNaN(x);

export type SingleOrMany<T> = T | T[];

/** Un color #rrggbb, para un estilo de eco que no sea uno de los con nombre. */
export class RGBA { constructor(readonly r: number, readonly g: number, readonly b: number, readonly a = 1) { } }
export class Color {
    constructor(readonly rgba: RGBA) { }
    static fromHex(hex: string): Color {
        const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
        if (!m) throw new Error(`no es un color: ${hex}`);
        return new Color(new RGBA(parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)));
    }
}

/** Lo de adentro de xterm que usa el eco: los atributos con que está escribiendo ahora. */
export interface XtermAttributes {
    isInverse(): number; isBold(): number; isUnderline(): number; isBlink(): number; isInvisible(): number;
    isItalic(): number; isDim(): number; isStrikethrough(): number; isOverline?(): number;
    getFgColorMode(): number; getBgColorMode(): number; getFgColor(): number; getBgColor(): number;
    isFgRGB(): boolean; isBgRGB(): boolean; isFgPalette(): boolean; isBgPalette(): boolean;
    isFgDefault(): boolean; isBgDefault(): boolean; isAttributeDefault(): boolean;
    clone?(): XtermAttributes;
}
export interface IXtermCore { _inputHandler: { _curAttrData: XtermAttributes } }

/** Lo que llega del servidor, antes de dibujarse: el eco lo corrige (quita lo que ya predijo). */
export interface IBeforeProcessDataEvent { data: string }
export interface ITerminalProcessManager { onBeforeProcessData: Event<IBeforeProcessDataEvent> }

export interface ITerminalTypeAheadConfiguration {
    localEchoLatencyThreshold: number;
    localEchoExcludePrograms: ReadonlyArray<string>;
    localEchoEnabled: 'auto' | 'on' | 'off';
    localEchoStyle: 'bold' | 'dim' | 'italic' | 'underlined' | 'inverted' | string;
}
/** Todas las terminales de aquí son de tmux: no se excluye (VS Code sí, por defecto). */
export const DEFAULT_LOCAL_ECHO_EXCLUDE: ReadonlyArray<string> = ['vim', 'vi', 'nano'];
