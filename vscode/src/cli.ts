// La frontera con la CLI. Todo lo que esta extensión sabe del mundo entra por aquí.
//
// Regla dura: los datos salen de `telar … --json` y de ningún otro lado. No se lee un
// archivo de estado, no se llama al multiplexor, no se adivina una ruta. Si telar no lo
// sabe decir, la vista lo dice vacío y explica por qué. Así la extensión no se entera de
// dónde vive el estado ni de qué multiplexor hay debajo, y no se rompe cuando eso cambie.
//
// Las formas del JSON de abajo son las de `docs/contratos.md`; lo que no esté declarado
// ahí se lee como opcional, para que una versión más nueva de telar no tire la vista.

import * as cp from 'child_process';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

// ───────────────────────── configuración de la extensión ─────────────────────────

export function ajuste<T>(clave: string, porDefecto: T): T {
    return vscode.workspace.getConfiguration('telar').get<T>(clave) ?? porDefecto;
}

/** El programa. Se busca en el PATH: aquí no se escribe ninguna ruta de nadie. */
export const programa = (): string => (ajuste('cli', 'telar') || 'telar').trim();

/** Las banderas globales que la configuración quiera añadir (`-c`, `-r`). */
function banderas(): string[] {
    const b: string[] = [];
    const conf = String(ajuste('config', '')).trim();
    const raiz = String(ajuste('raiz', '')).trim();
    if (conf) b.push('--config', path.resolve(expandir(conf)));
    // resuelta a propósito: el host de extensiones no tiene el directorio de trabajo de
    // nadie, y una raíz relativa apuntaría a un lugar que la persona no eligió
    if (raiz) b.push('--raiz', path.resolve(expandir(raiz)));
    return b;
}

/** `~` es del usuario, no de esta extensión: lo resuelve el sistema, no una constante. */
export function expandir(ruta: string): string {
    if (ruta === '~') return os.homedir();
    return ruta.startsWith('~/') ? path.join(os.homedir(), ruta.slice(2)) : ruta;
}

// ───────────────────────── el PATH y los procesos ─────────────────────────

/** El host de extensiones no hereda el PATH de un shell de login: se lo pedimos a uno. */
let PATH_RESUELTO = process.env.PATH ?? '';

let registrar: (linea: string) => void = () => { /* hasta que la extensión ponga el suyo */ };
export function conBitacora(f: (linea: string) => void): void { registrar = f; }

export interface Salida { ok: boolean; codigo: number; out: string; err: string }

function correr(cmd: string, args: string[], timeout: number, entorno?: NodeJS.ProcessEnv): Promise<Salida> {
    return new Promise(listo => {
        cp.execFile(cmd, args, { env: entorno ?? ambiente(), timeout, encoding: 'utf8', maxBuffer: 8 << 20 },
            (e, out, err) => {
                const codigo = e && typeof (e as { code?: unknown }).code === 'number' ? (e as unknown as { code: number }).code : e ? -1 : 0;
                listo({ ok: !e, codigo, out: out ?? '', err: (err ?? '') + (e && !err ? `\n${e.message}` : '') });
            });
    });
}

/** El entorno de los hijos: el PATH resuelto y nada más nuestro.
 *
 *  `TELAR_HILO` se quita a propósito. Si VS Code se abrió desde dentro de un hilo, lo
 *  heredaríamos y toda orden sin `--hilo` actuaría sobre ese, no sobre el que se tocó en
 *  la barra. Aquí siempre se dice a cuál, y quitarlo evita el malentendido callado. */
function ambiente(): NodeJS.ProcessEnv {
    const env: NodeJS.ProcessEnv = { ...process.env, PATH: PATH_RESUELTO };
    delete env.TELAR_HILO;
    return env;
}

export async function resolverPath(): Promise<void> {
    if (process.platform === 'win32') return;
    const shell = process.env.SHELL || '/bin/sh';
    const r = await correr(shell, ['-ilc', 'printf "%s" "$PATH"'], 6000, process.env);
    const salida = r.out.trim().split('\n').pop() ?? '';
    if (r.ok && salida.includes('/')) PATH_RESUELTO = salida;
    // Los sitios donde suele quedar un programa instalado por el usuario y que un shell
    // no interactivo puede no traer. Salen de `os.homedir()`: ninguna ruta fija de nadie.
    const extras = [path.join(os.homedir(), '.local', 'bin'), '/usr/local/bin', '/opt/homebrew/bin'];
    const partes = PATH_RESUELTO.split(path.delimiter);
    for (const extra of extras) if (!partes.includes(extra)) PATH_RESUELTO += path.delimiter + extra;
}

export const pathResuelto = (): string => PATH_RESUELTO;

// ───────────────────────── hablar con telar ─────────────────────────

/** Una orden de telar. Devuelve la salida cruda; quien llama decide qué hacer con el error. */
export async function telar(args: string[], timeout = 15000): Promise<Salida> {
    const r = await correr(programa(), [...banderas(), ...args], timeout);
    if (!r.ok) registrar(`telar ${args.join(' ')} → ${r.codigo}: ${ultimaLinea(r.err)}`);
    return r;
}

/** Una orden con `--json`. `undefined` si falló, y el motivo queda en `error`. */
export interface Respuesta<T> { datos?: T; error?: string }

export async function telarJson<T>(args: string[], timeout = 15000): Promise<Respuesta<T>> {
    const r = await telar([...args, '--json'], timeout);
    if (!r.ok) return { error: motivo(r, args) };
    try {
        return { datos: JSON.parse(r.out) as T };
    } catch (e) {
        registrar(`telar ${args.join(' ')} --json: salida ilegible (${e})`);
        return { error: `«telar ${args.join(' ')}» no devolvió JSON` };
    }
}

/** El error, en una frase que se pueda mostrar sin asustar. */
function motivo(r: Salida, args: string[]): string {
    const linea = ultimaLinea(r.err) || ultimaLinea(r.out);
    if (/ENOENT|not found|no encontr/i.test(linea) && r.codigo !== 2) {
        return `no encontré «${programa()}» en el PATH (ajusta telar.cli)`;
    }
    return linea || `«telar ${args.join(' ')}» falló (código ${r.codigo})`;
}

/** La última línea con algo: una queja de telar termina con lo que hay que leer. */
function ultimaLinea(texto: string): string {
    return texto.split('\n').map(l => l.trim()).filter(Boolean).pop() ?? '';
}

// ───────────────────────── las formas del JSON (docs/contratos.md) ─────────────────────────

export interface JsonPendiente {
    texto: string; hecho: boolean; en_curso: boolean; id: string; origen: string;
    ref?: string; hilo?: string;
}

export interface JsonFicha {
    documento: string; relativo: string; titulo: string; estado: string;
    pendientes: JsonPendiente[]; secciones: Record<string, unknown>;
    leida: string | null; nota: string; vacia: boolean;
}

export interface JsonHilo {
    id: string; nombre: string; vivo: boolean; activo: boolean; archivado: boolean;
    vinculado: boolean; ruta: string; relativa: string; arquetipo: string;
    prioridad: number | null; atencion: string; visto: string | null; tiempo: number;
    sesiones: string[]; ficha?: JsonFicha | null;
}

export interface JsonHilos {
    sesion: string; viva: boolean; raiz: string; multiplexor: string;
    aviso: string; orden: string; hilos: JsonHilo[];
    /** los pids de las terminales que muestran la sesión (vacío si no se sabe) */
    clientes?: number[];
}

export interface JsonAccion {
    nombre: string; descripcion: string; tecla: string; donde: string; confirmar: boolean;
}

export interface JsonFichaOrden {
    hilo: JsonHilo; seguro: boolean; acciones: JsonAccion[]; perfil: string;
}

/** Una fila de `telar pendientes` y de `telar hoy`: un pendiente de un documento, o lo que
 *  aportó un proveedor, ya enrutado al hilo donde se trabaja. `ref` es con lo que se agarra
 *  (`faro:2`, o la referencia estable del proveedor). */
export interface JsonFila {
    texto: string; hecho: boolean; en_curso: boolean; id: string; origen: string;
    ref: string; hilo: string; ruta: string; proveedor: string;
    cuando: string | null; url: string;
}

/** El día. La agenda es `null` cuando no se consultó a nadie (`--local`) o cuando no hay
 *  ningún proveedor declarado: son dos silencios distintos, y los dos se dicen. */
export interface JsonHoy {
    ahora: string; dia: string; fecha: string; semana: number; local: boolean;
    agenda: JsonFila[] | null;
    atencion: JsonHilo[];
    pendientes: JsonFila[];
    tiempo: { total: number; hilos: Record<string, number> };
    proveedores: { declarados: string[]; fallas: string[] };
}

/** `telar reunion`: un hilo con el agente preparando esa reunión (o ir a él, si ya existe). */
export const reunion = (titulo: string, hora: string, enlace = '') =>
    telarJson<{ hilo: string; proyecto: string; mensaje: string; hecho: string }>(
        ['reunion', titulo, hora, ...(enlace ? ['--enlace', enlace] : []), '--json'], 30000);

/** De dónde sale la agenda, según `telar config --json`. La dirección iCal viene tapada. */
export interface JsonCalendario {
    tipo: string; fuente: string; publica: boolean;
    gws: boolean; gws_cuenta: string; gws_conectado: boolean;
}

/** Lo que el dashboard muestra de `[agente]`. */
export interface JsonAgenteConfig { nombre: string; carpeta: string; reunion: string; reunion_por_defecto: string }

export const config = () => telarJson<{
    calendario: JsonCalendario; agente: JsonAgenteConfig; hilos: { directorios: string[]; tope: number };
}>(['config', '--json'], 20000);

/** `telar config --directorios a,b`: de qué carpetas salen los hilos. Vacío: las del perfil. */
export const directoriosHilos = (carpetas: string) => telar(['config', '--directorios', carpetas], 20000);

/** `telar config --reunion`: qué decirle al agente al preparar una reunión. Vacío: el de fábrica. */
export const plantillaReunion = (texto: string) => telar(['config', '--reunion', texto], 20000);

/** `telar config --calendario gws|ninguno|<dirección>`: elegir de dónde sale la agenda. */
export const elegirCalendario = (valor: string) => telar(['config', '--calendario', valor], 20000);

/** Lo que devuelve `telar pendiente <ref> --json`: adónde fue y qué se le escribió. */
export interface JsonPendienteIdo {
    ref: string; texto: string; destino: string; creado?: boolean; enviado?: boolean;
}

/** Las rutas absolutas, que es lo único que sirve para abrir un archivo desde aquí.
 *
 *  telar devuelve `ruta` y `documento` tal como los tenga, y si la raíz que le dieron era
 *  relativa, lo son. El par `relativa`/`relativo` sí es siempre relativo a la raíz: con una
 *  raíz absoluta, pegarlos da la ruta buena. Con una raíz relativa no se toca nada, porque
 *  adivinar el directorio de trabajo de otro proceso es peor que no abrir el archivo. */
export function conRutasAbsolutas(h: JsonHilo, raiz: string): JsonHilo {
    if (!raiz || !path.isAbsolute(raiz)) return h;
    const ruta = h.ruta && !path.isAbsolute(h.ruta) && h.relativa ? path.join(raiz, h.relativa) : h.ruta;
    const f = h.ficha;
    const ficha = f && f.documento && !path.isAbsolute(f.documento) && f.relativo
        ? { ...f, documento: path.join(raiz, f.relativo) }
        : f;
    return ruta === h.ruta && ficha === f ? h : { ...h, ruta, ficha };
}

// ───────────────────────── las órdenes que usa la vista ─────────────────────────

export const hilos = (conFicha: boolean, orden: string) =>
    telarJson<JsonHilos>(['hilos', ...(conFicha ? [] : ['--sin-ficha']), '--orden', orden], conFicha ? 30000 : 8000);

export const ficha = (hilo: string) => telarJson<JsonFichaOrden>(['ficha', hilo], 30000);

/** Sin `local`, se consulta a los proveedores declarados y puede tardar lo que tarden. */
export const hoy = (local: boolean) =>
    telarJson<JsonHoy>(['hoy', ...(local ? ['--local'] : [])], local ? 20000 : 120000);

export const ir = (hilo: string, crear = false) => telar(['ir', hilo, ...(crear ? ['--crear'] : [])], 20000);

/** `telar hilo <verbo> [valor] --hilo <hilo>`: vincular, renombrar, prioridad, archivar… */
export const hilo = (verbo: string, hilo: string, valor?: string, extra: string[] = []) =>
    telar(['hilo', verbo, ...(valor ? [valor] : []), '--hilo', hilo, ...extra], 30000);

/** Lleva un pendiente al hilo donde se trabaja y se lo deja escrito al agente, sin enviar:
 *  apretar Enter le toca a la persona, y esa decisión no se automatiza desde una barra. */
export const pendiente = (ref: string, nuevo = false) =>
    telarJson<JsonPendienteIdo>(['pendiente', ref, ...(nuevo ? ['--nuevo'] : [])], 60000);

/** `--si` porque la confirmación ya la dio la persona en un diálogo: sin eso, una acción que
 *  pide confirmar falla aquí, donde no hay una terminal que pueda preguntar. */
export const accion = (nombre: string, hilo: string) =>
    telar(['accion', nombre, '--hilo', hilo, '--si'], 120000);

export const tejer = () => telar(['tejer'], 20000);
