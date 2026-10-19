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
import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';

// ───────────────────────── configuración de la extensión ─────────────────────────

/** Los ajustes `telar.*` (en VS Code, su configuración; en la web, los de su servidor). */
let leerAjuste: <T>(clave: string, porDefecto: T) => T = (_c, d) => d;
export function usarAjustes(f: <T>(clave: string, porDefecto: T) => T): void { leerAjuste = f; }

export function ajuste<T>(clave: string, porDefecto: T): T {
    return leerAjuste(clave, porDefecto);
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

// ───────────────────────── la API (`telar serve`) ─────────────────────────

/** El socket de `telar serve` en esta máquina (`<estado>/serve/telar.sock`). */
function socketServe(): string {
    const base = process.env.XDG_STATE_HOME || path.join(os.homedir(), '.local', 'state');
    return path.join(base, 'telar', 'serve', 'telar.sock');
}

/** Un pedido a la API de telar por su socket. `undefined` solo si no hay API que conteste: no corre, o
 *  todavía no tiene esa ruta (un servidor más viejo). Entonces quien llama usa la CLI, que da lo mismo
 *  (las dos son cáscaras de la misma función, `telar.servicios`). Si la API contesta con un error, ese
 *  es el error: una acción no se reintenta por la CLI, porque se correría dos veces. */
function aServe<T>(metodo: 'GET' | 'POST' | 'PUT' | 'DELETE', ruta: string, timeout: number, cuerpo?: unknown): Promise<Respuesta<T> | undefined> {
    const sock = socketServe();
    if (!fs.existsSync(sock)) return Promise.resolve(undefined);
    const datos = cuerpo === undefined ? undefined : JSON.stringify(cuerpo);
    return new Promise(listo => {
        const pedido = http.request({
            socketPath: sock, path: ruta, method: metodo, timeout,
            headers: datos === undefined ? {} : { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(datos) },
        }, res => {
            let texto = '';
            res.setEncoding('utf8');
            res.on('data', d => { texto += d; });
            res.on('end', () => {
                let json: unknown;
                try { json = JSON.parse(texto); } catch { json = undefined; }
                const detalle = (json as { detail?: unknown } | undefined)?.detail;
                if (res.statusCode === 200 && json !== undefined) { listo({ datos: json as T }); return; }
                // la ruta no existe en esa API: como si no hubiera API
                if (res.statusCode === 404 && detalle === 'Not Found') { listo(undefined); return; }
                registrar(`telar serve ${metodo} ${ruta} → ${res.statusCode}: ${texto.slice(0, 200)}`);
                listo({ error: typeof detalle === 'string' ? detalle : `la API respondió ${res.statusCode}` });
            });
        });
        pedido.on('timeout', () => { pedido.destroy(); registrar(`telar serve ${ruta}: no respondió en ${timeout} ms`); listo({ error: 'telar serve no respondió a tiempo' }); });
        // sin conexión (el socket quedó de una vuelta anterior): como si no hubiera API
        pedido.on('error', () => listo(undefined));
        if (datos !== undefined) pedido.write(datos);
        pedido.end();
    });
}
const deServe = <T>(ruta: string, timeout: number) => aServe<T>('GET', ruta, timeout);

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
    /** el nombre para mostrar, según la `etiqueta` del perfil; vacío si no hay */
    etiqueta?: string;
    pendientes: JsonPendiente[]; secciones: Record<string, unknown>;
    leida: string | null; nota: string; vacia: boolean;
}

export interface JsonHilo {
    id: string; nombre: string; vivo: boolean; activo: boolean; archivado: boolean;
    /** vive en una sesión tmux propia de esta máquina (no es un tab): está vivo aunque `vivo` no lo cuente */
    propio?: boolean;
    vinculado: boolean; ruta: string; relativa: string; arquetipo: string;
    prioridad: number | null; atencion: string; visto: string | null; tiempo: number;
    /** desde cuándo está en ese semáforo: lo último que hizo su agente */
    atencion_desde?: string | null;
    /** la última vez que se le pidió algo a su agente (un prompt, un encargo): su «última modificación» */
    actividad?: string | null;
    /** terminó y la persona no lo ha mirado desde entonces: te espera, como «espera» */
    sin_ver?: boolean;
    sesiones: string[]; ficha?: JsonFicha | null;
    /** dónde vive su agente: "" aquí, el nombre de un [remotos], o "?" si es remoto sin saber adónde */
    remoto?: string;
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
    /** lo último que dejó un agente que la trabajó solo: «preparado 2026-09-25» */
    avance?: string;
    /** su proveedor da ficha (`telar tarea`): un clic la abre en vez de ir al hilo */
    ficha?: boolean;
    /** a qué parte de la vida pertenece («trabajo», «personal»): las listas filtran por aquí */
    area?: string;
    /** quién la hace, si no es la persona; vacío es suya */
    dueno?: string;
    /** el color de la palabra de `avance` (verde, rojo…) */
    color?: string;
    /** si su proveedor tiene pestaña propia (un feed): no es un pendiente, va a esa pestaña */
    pestana?: string;
    /** un evento: cuándo termina, dónde, y si es de día completo */
    fin?: string; lugar?: string; todo_el_dia?: boolean; asistentes?: string[];
    /** «evento» o «tarea», si la trajo un proveedor */
    clase?: string;
    /** el proveedor la destaca (la más alta prioridad, o con estrella): va siempre en «esta semana» */
    destacada?: boolean;
    /** la persona la marcó con estrella */
    estrella?: boolean;
    /** las etiquetas de la tarea; «equipo» es la que la comparte con el equipo (`telar equipo`) */
    etiquetas?: string[];
    /** de un proveedor: la carpeta que la tarea dice que es su proyecto, haya o no hilo ahí */
    proyecto?: string;
}

/** Lo que dejó una skill un día (`telar resultado <clave> [día]`), leído de la máquina donde vive. */
export interface JsonResultado {
    ok: boolean; error?: string; aviso?: string; desde?: string;
    clave: string; nombre: string; dia: string; dias: string[];
    formato: 'json' | 'md' | ''; contenido: unknown;
    /** si la máquina donde vive atiende comentarios sobre un día (`[resultados.<clave>] comentar`) */
    comentable?: boolean;
}
export async function resultado(clave: string, dia = ''): Promise<Respuesta<JsonResultado>> {
    return await deServe<JsonResultado>(`/resultados/${encodeURIComponent(clave)}${dia ? `?dia=${encodeURIComponent(dia)}` : ''}`, 30000)
        ?? telarJson<JsonResultado>(['resultado', clave, ...(dia ? [dia] : [])], 30000);
}

/** Un comentario sobre el resultado de un día: lo atiende la máquina donde vive, y dice qué abrió
 *  (`telar resultado <clave> <día> --comentar`, con el texto por la entrada estándar). */
export async function comentarResultado(clave: string, dia: string, texto: string): Promise<{ ok: boolean; abrio?: string; error?: string }> {
    const r = await aServe<{ ok: boolean; abrio?: string; error?: string }>('POST', `/resultados/${encodeURIComponent(clave)}/comentario`, 90000, { dia, texto });
    if (r) return r.datos ?? { ok: false, error: r.error };
    return conEntrada<{ ok: boolean; abrio?: string; error?: string }>(['resultado', clave, dia, '--comentar', '--json'], texto);
}

/** Un mensaje que escribe la persona desde otra parte (el panel) a un hilo de cualquier máquina, por
 *  el bus: le llega como suyo (`telar mensaje <hilo> - --tipo persona`). */
export const escribirComoPersona = async (hilo: string, texto: string, de: string) => {
    const r = await aServe<{ ok?: boolean; id?: string; error?: string }>('POST', '/mensajes', 30000, { para: hilo, texto, tipo: 'persona', de });
    if (r) return r.error ? { error: r.error } : { ok: true, id: r.datos?.id };
    return conEntrada<{ ok?: boolean; id?: string; error?: string }>(['mensaje', hilo, '-', '--tipo', 'persona', '--de', de, '--json'], texto);
};

/** Las fotos de los hilos de otras máquinas que llegaron aquí (`telar espejo ver`). */
export interface JsonEspejo { nombre: string; en_linea: boolean; edad: number | null; error?: string; hilos: { nombre: string; atencion?: string; vivo?: boolean; relativa?: string; prioridad?: number | null; resumen?: string; remoto?: string }[] }
export const espejos = async () => await deServe<{ espejos: JsonEspejo[] }>('/espejos', 15000)
    ?? telarJson<{ espejos: JsonEspejo[] }>(['espejo', 'ver', '--json'], 15000);

/** Una orden de telar con un texto por su entrada estándar, y su JSON. */
function conEntrada<T>(args: string[], texto: string): Promise<T & { ok?: boolean; error?: string }> {
    return new Promise(listo => {
        const p = cp.spawn(programa(), [...banderas(), ...args], { env: ambiente() });
        let out = '', err = '';
        const tope = setTimeout(() => { p.kill(); }, 90000);
        p.stdout.on('data', d => { out += d; });
        p.stderr.on('data', d => { err += d; });
        p.on('error', e => { clearTimeout(tope); listo({ ok: false, error: e.message } as T & { ok?: boolean; error?: string }); });
        p.on('close', () => {
            clearTimeout(tope);
            try { listo(JSON.parse(out)); } catch { listo({ ok: false, error: ultimaLinea(err) || 'no respondió' } as T & { ok?: boolean; error?: string }); }
        });
        p.stdin.end(texto);
    });
}

/** Una nota sobre un evento del día (`telar evento`). */
export interface JsonNota { de: string; texto: string; creado: string }
export interface JsonNotas {
    ok: boolean; error?: string; aviso?: string; dia: string;
    eventos: Record<string, { titulo: string; inicio: string; notas: JsonNota[] }>;
}
export const notasEventos = async (dia = '') => await deServe<JsonNotas>(`/notas${dia ? `?dia=${encodeURIComponent(dia)}` : ''}`, 30000)
    ?? telarJson<JsonNotas>(['evento', 'notas', ...(dia ? [dia] : [])], 30000);
export const notaEvento = async (evento: string, texto: string, titulo: string, inicio: string, dia = '') =>
    await aServe<{ ok: boolean; error?: string }>('POST', '/notas', 30000, { evento, texto, de: 'Nico', titulo, inicio, dia })
    ?? telarJson<{ ok: boolean; error?: string }>(['evento', 'nota', evento, texto, '--de', 'Nico', '--titulo', titulo,
        '--inicio', inicio, ...(dia ? ['--dia', dia] : [])], 30000);

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
/** Un proyecto del que podría ser una reunión, con por qué (`telar reunion --preguntar`). */
export interface JsonCandidato { ruta: string; nombre: string; puntaje: number; motivos: string[] }
export interface JsonReunion {
    hilo: string; proyecto: string; mensaje: string; hecho: string;
    candidatos?: JsonCandidato[]; gestion?: string; destino?: string; recordado?: boolean;
}
/** Preparar o hacer la minuta de una reunión. Con `preguntar`, si no se sabe de qué proyecto es,
 *  no hace nada y devuelve los candidatos (`hecho: "preguntar"`); `proyecto` es la elección. */
export const reunion = (titulo: string, hora: string, enlace = '', evento = '',
    opciones: { asistentes?: string[]; proyecto?: string; preguntar?: boolean; donde?: boolean } = {}) =>
    telarJson<JsonReunion>(
        ['reunion', titulo, hora, ...(enlace ? ['--enlace', enlace] : []), ...(evento ? ['--evento', evento] : []),
            ...(opciones.asistentes?.length ? ['--asistentes', opciones.asistentes.join(',')] : []),
            ...(opciones.proyecto ? ['--proyecto', opciones.proyecto] : []),
            ...(opciones.preguntar ? ['--preguntar'] : []), ...(opciones.donde ? ['--donde'] : []), '--json'], 40000);

/** Una unidad del perfil, tenga hilo o no (`telar proyectos --json`). */
export interface JsonProyecto {
    ruta: string; nombre: string; arquetipo: string; modificado: string | null; hilo: string; vivo: boolean;
    /** el cliente, si el nombre lo lleva adelante («Cliente · título»); "" si no */
    cliente?: string;
    /** el Estado (o la Etapa) de su tabla de campos, corto; y entero */
    estado?: string; estado_completo?: string;
    /** el área que declara su frontmatter («area: PIA»); "" si no la tiene */
    area?: string;
}

export const proyectos = async () => await deServe<{ raiz: string; proyectos: JsonProyecto[] }>('/proyectos', 30000)
    ?? telarJson<{ raiz: string; proyectos: JsonProyecto[] }>(['proyectos', '--json'], 30000);

/** Los pendientes de los documentos de todas las unidades, tengan hilo o no (sin proveedores: rápido). */
export const pendientesRepo = async () => await deServe<{ pendientes: JsonFila[] }>('/pendientes?repo=true', 30000)
    ?? telarJson<{ pendientes: JsonFila[] }>(['pendientes', '--json', '--repo'], 30000);

/** `telar proyectos abrir`: un hilo vinculado a esa unidad con el agente cargándola, o ir al que ya hay. */
export const abrirProyecto = (ruta: string) =>
    telarJson<{ hilo: string; ruta: string; mensaje: string; hecho: string }>(['proyectos', 'abrir', ruta, '--json'], 30000);

/** De dónde sale la agenda, según `telar config --json`. La dirección iCal viene tapada. */
export interface JsonCalendario {
    tipo: string; fuente: string; publica: boolean;
    gws: boolean; gws_cuenta: string; gws_conectado: boolean;
}

/** Lo que el dashboard muestra de `[agente]`. */
export interface JsonAgenteConfig {
    nombre: string; carpeta: string; reunion: string; reunion_por_defecto: string;
    proyecto: string; proyecto_por_defecto: string;
}

/** Una tecla del dashboard que abre un hilo con el agente haciendo algo (`[atajos.m]`). */
export interface JsonAtajo { tecla: string; nombre: string; mensaje: string; descripcion: string; en?: string }

/** Una sección del día que llena un comando (`[bloques.<clave>]`). */
/** `en`: "" es una pestaña propia del dashboard; «plan», arriba del plan. `tecla`: la de su pestaña. */
export interface JsonBloque { clave: string; nombre: string; color: string; en?: string; tecla?: string }

/** `telar bloque <clave> --item <id>`: el detalle de un ítem (el cuerpo de un correo), al abrirlo. */
export async function bloqueItem(clave: string, id: string): Promise<Respuesta<{ texto: string }>> {
    return await deServe<{ texto: string }>(`/bloques/${encodeURIComponent(clave)}/items/${encodeURIComponent(id)}`, 70000)
        ?? telarJson<{ texto: string }>(['bloque', clave, '--item', id, '--json'], 70000);
}

/** `telar bloque <clave>`: la página que imprime su comando. */
export async function bloque(clave: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/bloques/${encodeURIComponent(clave)}`, 90000) ?? telarJson<JsonPagina>(['bloque', clave], 90000);
}

export interface JsonPestana { nombre: string; tecla: string }
/** La configuración resuelta: primero la API (`/config`), sin ella la CLI. */
export type JsonConfig = {
    calendario: JsonCalendario; agente: JsonAgenteConfig; hilos: { directorios: string[]; tope: number };
    atajos?: JsonAtajo[]; secciones?: JsonSeccion[]; apps?: JsonApp[];
    /** las pestañas del dashboard: su orden y las que no se muestran (`[dashboard]`) */
    dashboard?: { orden: string[]; ocultas: string[] };
    /** los módulos instalados (`[modulos]`) y lo que aporta cada uno */
    modulos?: { nombre: string; carpeta: string; descripcion: string; aporta: string[] }[]; remotos?: JsonRemoto[]; bloques?: JsonBloque[];
    pestanas?: JsonPestana[];
    /** el agente que recibe lo que no tiene proyecto (`[agentes] sin_proyecto`); vacío si no hay */
    agente_general?: { clave?: string; nombre?: string };
    /** quién es la persona de esta máquina: una tarea sin dueño es suya */
    persona?: string; persona_nombres?: string[];
    /** la carpeta del estado de telar en esta máquina */
    estado?: string;
};
export async function config(): Promise<Respuesta<JsonConfig>> {
    return await deServe<JsonConfig>('/config', 20000) ?? telarJson<JsonConfig>(['config', '--json'], 20000);
}

/** `telar encargar <agente> "…"`: pedirle algo a un agente residente, viva donde viva. */
export const encargar = (agente: string, texto: string) =>
    telarJson<{ hilo?: string; estado?: string; id?: string }>(['encargar', agente, texto], 30000);

/** Un grupo propio en la lista de hilos (`[secciones.x]`). `hilos`: nombres exactos, o
 *  prefijos si terminan en `*`. `home`: si declara una página. */
/** `grupo: 'agentes'` es un agente residente: va bajo la cabecera «Agentes», con su home armado por telar. */
export interface JsonSeccion { clave: string; nombre: string; hilos: string[]; home: boolean; grupo?: string }

export function enSeccion(s: JsonSeccion, hilo: string): boolean {
    return s.hilos.some(p => p.endsWith('*') ? hilo.startsWith(p.slice(0, -1)) : hilo === p);
}

/** Lo que se abre en el panel y no es un hilo (`[apps.x]`): su página la da `telar app <clave>`.
 *  `url`, si la app es una página servida: el panel la deja entrar en su CSP. */
export interface JsonApp { clave: string; nombre: string; descripcion?: string; fuente: 'pagina' | 'archivo' | 'url'; url?: string }

/** La página de una sección, tal como la devuelve su comando `home` (docs/contratos.md). */
export interface JsonPaginaItem {
    titulo: string; fecha?: string; texto?: string; conversacion?: string; hilo?: string;
    /** un glifo corto antes del título (● sin procesar, ✓ hecho); `destacado` lo resalta */
    marca?: string; destacado?: boolean;
    /** con `mensaje`, un clic abre un hilo nuevo con el agente y ese primer prompt; `nombre` es el del hilo */
    mensaje?: string; nombre?: string;
    /** un clic lo abre: una URL en el navegador, una ruta en el editor */
    enlace?: string;
    /** las tareas que nacieron de este ítem (un correo): un clic en el ítem las muestra, y cada una abre su ficha */
    tareas?: { proveedor: string; id: string; estado?: string }[];
    /** los ítems con el mismo `grupo` (los correos de una conversación) van anidados bajo el más reciente */
    grupo?: string;
    /** su id en el bloque: con él, el dashboard pide su detalle (el cuerpo de un correo) al abrirlo */
    id?: string;
    /** con `enlace`: un texto que identifica una pestaña ya abierta del navegador (su título o su
     *  dirección lo contiene, p. ej. la cuenta de Gmail); el enlace se abre en ella en vez de en una nueva */
    reusar?: string;
}
/** Un botón de una página (la ficha de una tarea): lo corre `telar tarea --accion N`. */
export interface JsonAccionPagina {
    nombre: string; tipo?: 'comando' | 'hilo' | 'abrir'; comando?: string[]; enlace?: string;
    /** pide un texto antes de correr (reemplaza `{texto}`); `confirmar` pregunta primero */
    pide?: string; principal?: boolean; confirmar?: boolean;
    /** qué es, para quien la corre sin abrir la ficha: `hecha` es el ✓ de la lista de tareas, `fecha`
     *  cambia la fecha, `dueno` quién la hace */
    rol?: string;
    /** con `rol: dueno`, las personas para elegir */
    opciones?: string[];
    /** después del comando, un hilo nuevo con el agente y este mensaje (`nombre_hilo`); con `al_hilo`,
     *  el mensaje va al hilo donde se trabaja la tarea (el de su proyecto, o Gestión) */
    mensaje?: string; nombre_hilo?: string; al_hilo?: boolean;
}
export interface JsonPagina {
    titulo: string; subtitulo?: string;
    /** la versión de lo que muestra (la ficha de una tarea del tipo): se devuelve con una acción, y si la
     *  tarea cambió desde entonces, la acción no se hace */
    version?: string;
    bloques: { titulo?: string; texto?: string; items?: JsonPaginaItem[]; lienzo?: JsonLienzo; marco?: JsonMarco;
               destacado?: boolean; color?: string }[];
    acciones?: JsonAccionPagina[];
}

/** Una página HTML local que la sección muestra en un iframe: animaciones, dibujos. */
export interface JsonLienzo { archivo: string; alto?: number | 'lleno'; params?: Record<string, string | number>; memoria?: string }
/** Una página servida (http o https) en un iframe del panel: lo que muestra una app con `url`. */
export interface JsonMarco { url: string; alto?: number | 'lleno' }

export const seccion = async (clave: string) => await deServe<JsonPagina>(`/secciones/${encodeURIComponent(clave)}`, 40000)
    ?? telarJson<JsonPagina>(['seccion', clave, '--json'], 40000);
export const app = async (clave: string) => await deServe<JsonPagina>(`/apps/${encodeURIComponent(clave)}`, 40000)
    ?? telarJson<JsonPagina>(['app', clave, '--json'], 40000);
/** Guardar el orden de las pestañas del dashboard: «ahora,revisar,-plan» (con «-», oculta). */
export const configPestanas = async (valor: string) =>
    await aServe<{ dashboard: { orden: string[]; ocultas: string[] } }>('PUT', '/config/pestanas', 20000, { valor })
    ?? telarJson<{ dashboard: { orden: string[]; ocultas: string[] } }>(['config', '--pestanas', valor, '--json'], 20000);
/** La ficha de una tarea (`telar tarea`) y correr una de sus acciones, por su número. */
export async function tarea(id: string, proveedor: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/tareas/${encodeURIComponent(id)}?proveedor=${encodeURIComponent(proveedor)}`, 40000)
        ?? telarJson<JsonPagina>(['tarea', id, '--proveedor', proveedor, '--json'], 40000);
}
/** Correr la acción de una tarea por su `rol` (hecha…): un solo viaje, sin leer la ficha antes. */
export async function accionPorRol(id: string, proveedor: string, rol: string): Promise<Respuesta<{ tipo: string; hecho: string; salida?: string; hilo?: string }>> {
    return await aServe<{ tipo: string; hecho: string; salida?: string; hilo?: string }>('POST', `/tareas/${encodeURIComponent(id)}/accion`, 40000, { proveedor, rol })
        ?? telarJson(['tarea', id, '--proveedor', proveedor, '--rol', rol, '--json'], 40000);
}
export async function accionTarea(id: string, proveedor: string, n: number, texto = '', version = ''): Promise<Respuesta<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>> {
    return await aServe<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>('POST', `/tareas/${encodeURIComponent(id)}/accion`, 40000, { proveedor, n, texto, ...(version ? { version } : {}) })
        ?? telarJson(['tarea', id, '--proveedor', proveedor, '--accion', String(n), ...(texto ? ['--texto', texto] : []), ...(version ? ['--version', version] : []), '--json'], 40000);
}

/** Los procesos periódicos (`telar periodicos`), de esta máquina o de `[periodicos] en`. */
export interface JsonPeriodico {
    nombre: string; cuando: string; tipo: 'comando' | 'mensaje'; comando: string; mensaje: string; hilo: string;
    max_abiertos: number; argumentos: string[]; carpeta: string; descripcion: string; activo: boolean;
    proxima: string;
    ultima: { inicio?: string; fin?: string; codigo?: number; resultado?: string; corriendo?: boolean; hilo?: string };
}
export interface JsonPeriodicos { maquina: string; archivo: string; zona: string; procesos: JsonPeriodico[] }

export const periodicos = () => telarJson<JsonPeriodicos>(['periodicos', 'ver'], 30000);
export const periodicosLog = (nombre: string) => telarJson<{ nombre: string; log: string }>(['periodicos', 'log', nombre, '--lineas', '200'], 30000);
export const periodicosHorario = (cuando: string) =>
    telarJson<{ valido: boolean; cuando: string; proximas: string[]; error: string }>(['periodicos', 'horario', cuando, '--n', '3'], 30000);
export interface JsonSkill { nombre: string; descripcion: string; origen: string }
export const periodicosSkills = (carpeta: string) =>
    telarJson<{ carpeta: string; skills: JsonSkill[] }>(['periodicos', 'skills', ...(carpeta ? ['--carpeta', carpeta] : [])], 30000);
/** Cambiar uno: `nuevo`, `editar`, `pausar`, `activar`, `borrar`, `ahora`, con sus banderas. */
export const periodicosOrden = (args: string[]) => telarJson<{ ok: boolean; hecho: string }>(['periodicos', ...args], 60000);

/** Una conversación del agente, entera, para leerla. */
export interface JsonConversacion {
    conversacion: string; archivo: string; hilo: string;
    mensajes: { quien: 'usuario' | 'agente' | 'herramienta'; hora: string; texto: string }[];
}

export const conversacion = async (id: string) => await deServe<JsonConversacion>(`/conversaciones/${encodeURIComponent(id)}`, 20000)
    ?? telarJson<JsonConversacion>(['agente', 'conversacion', id, '--json'], 20000);

/** `telar atajo <tecla>`: un hilo nuevo con el agente y el mensaje de ese atajo. */
/** Abre aquí los hilos que nacieron en una máquina remota (un reloj allá, el celular). Es el sondeo
 *  de cada tres minutos: con bus no hace nada, porque `telar nodo` los trae al instante. */
/** Copia aquí el semáforo de los hilos remotos (sus ganchos corren allá). */
export const atencionRemotos = () =>
    telarJson<{ cambios: { hilo: string; atencion: string }[]; errores: string[]; por?: string }>(['remotos', 'atencion', '--json'], 30000);
export const traerRemotos = () =>
    telarJson<{ traidos: { remoto: string; sesion: string; hilo: string }[]; por?: string }>(['remotos', 'traer', '--sondeo', '--json'], 60000);
export async function abrirItem(clave: string, mensaje: string, nombre: string): Promise<Respuesta<{ hilo: string; mensaje: string }>> {
    return await aServe<{ hilo: string; mensaje: string }>('POST', `/bloques/${encodeURIComponent(clave)}/abrir`, 30000, { mensaje, nombre })
        ?? telarJson(['bloque', clave, '--abrir', mensaje, '--nombre', nombre, '--json'], 30000);
}
export const atajo = (tecla: string) => telarJson<{ hilo: string; mensaje: string }>(['atajo', tecla, '--json'], 30000);

/** Empuja al servidor una foto de los hilos de este laptop (`telar espejo publicar`), para verlos
 *  desde allá y desde la web del celular. `remoto` es una máquina de `[remotos]`; vacío, la única. */
export const publicarEspejo = (remoto: string) =>
    telarJson<{ publicado: boolean; maquina: string; remoto: string; error: string }>(
        ['espejo', 'publicar', ...(remoto ? ['--a', remoto] : [])], 40000);

/** `telar config --directorios a,b`: de qué carpetas salen los hilos. Vacío: las del perfil. */
export const directoriosHilos = (carpetas: string) => telar(['config', '--directorios', carpetas], 20000);

/** `telar config --reunion`: qué decirle al agente al preparar una reunión. Vacío: el de fábrica. */
export const plantillaReunion = (texto: string) => telar(['config', '--reunion', texto], 20000);

/** `telar config --proyecto`: qué decirle al agente al abrir un proyecto. Vacío: el de fábrica. */
export const plantillaProyecto = (texto: string) => telar(['config', '--proyecto', texto], 20000);

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

export async function hilos(conFicha: boolean, orden: string): Promise<Respuesta<JsonHilos>> {
    const q = new URLSearchParams({ orden, ...(conFicha ? {} : { ficha: 'false' }) }).toString();
    return await deServe<JsonHilos>(`/hilos?${q}`, conFicha ? 30000 : 8000)
        ?? telarJson<JsonHilos>(['hilos', ...(conFicha ? [] : ['--sin-ficha']), '--orden', orden], conFicha ? 30000 : 8000);
}

export const ficha = async (hilo: string) => await deServe<JsonFichaOrden>(`/ficha?hilo=${encodeURIComponent(hilo)}`, 30000)
    ?? telarJson<JsonFichaOrden>(['ficha', hilo], 30000);

/** Sin `local`, se consulta a los proveedores declarados y puede tardar lo que tarden. */
export async function hoy(local: boolean, dia = ''): Promise<Respuesta<JsonHoy>> {
    // primero la API (rápida: el calendario ya bajado, la configuración en memoria); sin ella, la CLI
    const q = new URLSearchParams({ ...(local ? { local: 'true' } : {}), ...(dia ? { dia } : {}) }).toString();
    return await deServe<JsonHoy>(`/hoy${q ? `?${q}` : ''}`, local ? 20000 : 60000)
        ?? telarJson<JsonHoy>(['hoy', ...(local ? ['--local'] : []), ...(dia ? ['--dia', dia] : [])], local ? 20000 : 120000);
}

export const ir = (hilo: string, crear = false, remoto = '') =>
    telar(['ir', hilo, ...(crear ? ['--crear'] : []), ...(remoto ? ['--remoto', remoto] : [])], remoto ? 60000 : 20000);

/** Un correo entre agentes, como lo da `telar correo --json`. */
export interface JsonCorreo {
    id: string; de: string; para: string; asunto: string; fecha: string; estado: string; nuevo: boolean;
    cuerpo?: string; leido?: boolean;
}
export interface JsonConversacionCorreo {
    id: string; asunto: string; participantes: string[]; mensajes: number; ultima: string; estado: string; correos: JsonCorreo[];
}
export interface JsonBuzon {
    remoto: string; usuario: string; error: string; sabe_pendientes: boolean; archivo_comun: boolean; cartero?: boolean;
    hilos: Record<string, JsonCorreoHilo>;
    conversaciones: JsonConversacionCorreo[];
}

/** El correo de un hilo con casilla: su dirección, lo sin entregar, su bandeja y cuánto no se vio. */
export interface JsonCorreoHilo { direccion: string; pendientes: JsonCorreo[]; correos?: JsonCorreo[]; no_leidos?: number }

/** `telar correo leido <hilo>`: marcar vista su bandeja (o esos ids). */
/** Una skill que el agente de un hilo tiene a mano (`telar agente skills`). */
export interface JsonSkill {
    nombre: string; descripcion: string; origen: string; alcance: string; ruta: string;
    /** cuántas veces se usó en la conversación del hilo */
    usada: number;
}
export const skills = (hilo: string) => telarJson<{
    hilo: string; conversacion: string; remoto: boolean; skills: JsonSkill[];
}>(['agente', 'skills', '--hilo', hilo, '--json'], 30000);

export const correoLeido = (hilo: string, ids: string[] = []) =>
    telar(['correo', 'leido', hilo, ...(ids.length ? ['--ids', ...ids] : [])], 40000);

/** Un mensaje entre hilos por el bus, como lo guarda su registro (`telar mensaje --registro`). */
export interface JsonMensajeBus {
    id: string; de: string; para: string; tipo: string; texto: string; creado: string;
    persona?: string; saltos?: number; estado?: 'enviado' | 'retenido'; motivo?: string;
}
/** Los últimos mensajes entre hilos, de todas las máquinas. Sin bus, error (y la pestaña no los muestra). */
export const mensajesBus = async (n = 60) => await deServe<{ mensajes: JsonMensajeBus[] }>(`/mensajes?n=${n}`, 30000)
    ?? telarJson<{ mensajes: JsonMensajeBus[] }>(['mensaje', '--registro', String(n)], 30000);
/** `telar mensaje --soltar <id>`: la persona deja pasar un mensaje retenido. */
export const soltarMensaje = async (id: string) =>
    await aServe<{ id: string; para: string }>('POST', `/mensajes/${encodeURIComponent(id)}/soltar`, 30000)
    ?? telarJson<{ id: string; para: string }>(['mensaje', '--soltar', id], 30000);

/** Lo que el equipo deja en tu bandeja (`telar equipo sugerencias --json`): subir una prioridad, o una tarea nueva. */
export interface JsonSugerencia {
    id: string; cuando: string; persona: string; tarea: string; titulo: string; prioridad: number | null;
    motivo: string; estado: string; nota: string;
    /** «prioridad»: sugiere subir una tarea · «tarea»: pide una tarea nueva (aceptarla la agrega) */
    tipo?: 'prioridad' | 'tarea'; vence?: string | null;
    /** si alguien (Gestión) la está revisando */
    revisando?: { quien: string; desde: string };
    /** de un pedido: tareas tuyas que parecen lo mismo (solo las ves tú) */
    similares?: { id: string; titulo: string; estado: string; prioridad: number | null; vence: string | null; avance: string | null; compartida: boolean }[];
}
const remotoEquipo = (remoto: string) => (remoto && remoto !== 'local' ? ['--remoto', remoto] : []);
export const equipoPendientes = (remoto: string) =>
    telarJson<{ sugerencias: JsonSugerencia[] }>(['equipo', 'sugerencias', ...remotoEquipo(remoto)], 30000);
export const equipoRevisando = (remoto: string, id: string, quien = 'gestion') =>
    telarJson<{ sugerencia: JsonSugerencia }>(['equipo', 'revisando', id, '--quien', quien, ...remotoEquipo(remoto)], 30000);
export const equipoResolver = (remoto: string, verbo: 'aceptar' | 'rechazar' | 'existe', id: string, nota = '', tarea = '') =>
    telarJson<{ sugerencia: JsonSugerencia }>(['equipo', verbo, id, ...(nota ? ['--nota', nota] : []), ...(tarea ? ['--tarea', tarea] : []),
        ...remotoEquipo(remoto)], 40000);

export const correo = (cuerpos = false) =>
    telarJson<{ remotos: JsonBuzon[] }>(['correo', ...(cuerpos ? ['--cuerpos'] : [])], 40000);

/** Una máquina de `[remotos]` donde pueden vivir hilos. */
export interface JsonRemoto { nombre: string; destino: string; transporte: string; raiz: string }

/** `telar hilo <verbo> [valor] --hilo <hilo>`: vincular, renombrar, prioridad, archivar… */
export const hilo = (verbo: string, hilo: string, valor?: string, extra: string[] = []) =>
    // llevar copia una conversación por ssh y abre el hilo allá: puede tardar más
    // llevar copia la conversación por ssh y abre el hilo allá: una conversación grande con la subida de un
    // laptop tarda minutos (4 con 12 MB, el 9-oct). Con 2 la extensión daba por fallado lo que seguía andando
    telar(['hilo', verbo, ...(valor ? [valor] : []), '--hilo', hilo, ...extra], verbo === 'llevar' ? 15 * 60000 : 30000);

/** Lleva un pendiente al hilo donde se trabaja y se lo deja escrito al agente, sin enviar:
 *  apretar Enter le toca a la persona, y esa decisión no se automatiza desde una barra. */
/** `proveedor`, si se sabe, evita preguntarles a todos (el calendario se baja entero): de 5 s a menos de 1. */
export const pendiente = (ref: string, nuevo = false, proveedor = '', texto = '', enviar = false) =>
    telarJson<JsonPendienteIdo>(['pendiente', ref, ...(nuevo ? ['--nuevo'] : []), ...(proveedor ? ['--proveedor', proveedor] : []),
        ...(texto ? ['--texto', texto] : []), ...(enviar ? ['--enviar'] : [])], 90000);

/** Una casilla en su documento: `--hecho`, `--responsable NOMBRE` o `--linea`. `esperado` es el texto
 *  que se vio: si el documento cambió y ya no dice eso, telar no toca nada. */
export interface JsonVineta { ref: string; archivo: string; relativa: string; linea: number; hecho: string }
export const vineta = (ref: string, esperado: string, opciones: string[]) =>
    telarJson<JsonVineta>(['pendiente', ref, ...opciones, '--esperado', esperado, '--json'], 60000);

/** `--si` porque la confirmación ya la dio la persona en un diálogo: sin eso, una acción que
 *  pide confirmar falla aquí, donde no hay una terminal que pueda preguntar. */
export const accion = (nombre: string, hilo: string) =>
    telar(['accion', nombre, '--hilo', hilo, '--si'], 120000);

export const tejer = () => telar(['tejer'], 20000);

/** Cómo se llama un hilo en pantalla: la etiqueta de su ficha, o su nombre. El nombre sigue
 *  siendo la llave (la del multiplexor y la del estado): esto solo cambia lo que se lee. */
export function nombreVisible(h: JsonHilo): string {
    return h.ficha?.etiqueta?.trim() || h.nombre;
}

