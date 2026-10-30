// La frontera con telar. Todo lo que la página sabe del mundo entra por aquí: la API de `telar serve`
// (`/api`, detrás de la llave de la página).
//
// Regla dura: los datos salen de la API y de ningún otro lado. No se lee un archivo de estado, no se
// llama al multiplexor, no se adivina una ruta. Si telar no lo sabe decir, la vista lo dice vacío y
// explica por qué. Así la página no se entera de dónde vive el estado ni de qué multiplexor hay debajo,
// y no se rompe cuando eso cambie.
//
// Las formas del JSON de abajo son las de `docs/contratos.md`; lo que no esté declarado
// ahí se lee como opcional, para que una versión más nueva de telar no tire la vista.

import { esAbsoluta, unir } from './rutas';

/** Lo que devuelve una orden que no tiene JSON propio: si salió bien, y su salida o su error. */
export interface Salida { ok: boolean; codigo: number; out: string; err: string }

/** Una respuesta de la API: los datos, o el motivo por el que no llegaron (y, con el motivo, lo demás que
 *  traiga la respuesta: la salida de lo que falló). */
export interface Respuesta<T> { datos?: T; error?: string; cuerpo?: Record<string, unknown> }

// ───────────────────────── la API (`telar serve`) ─────────────────────────

/** Un pedido a la API. Una ruta que la API no tiene (un telar más viejo que la página) se dice así, como
 *  un error: no hay otro camino por el que pedirlo. El cuerpo va como JSON; un FormData, como multipart (el
 *  navegador pone el tipo, con su separador). */
async function aServe<T>(metodo: 'GET' | 'POST' | 'PUT' | 'DELETE', ruta: string, timeout: number, cuerpo?: unknown): Promise<Respuesta<T>> {
    let r: Response;
    const formulario = cuerpo instanceof FormData;
    try {
        r = await fetch(`/api${ruta}`, {
            method: metodo, cache: 'no-store', signal: AbortSignal.timeout(timeout),
            headers: cuerpo === undefined || formulario ? {} : { 'Content-Type': 'application/json' },
            body: cuerpo === undefined ? undefined : formulario ? cuerpo : JSON.stringify(cuerpo),
        });
    } catch (e) {
        return { error: `la API no respondió: ${(e as Error).message}` };
    }
    let json: unknown;
    try { json = await r.json(); } catch { json = undefined; }
    const detalle = (json as { detail?: unknown } | undefined)?.detail;
    if (r.ok && json !== undefined) return { datos: json as T };
    if (r.status === 404 && detalle === 'Not Found') return { error: faltaEnLaApi(`${metodo} ${ruta.split('?')[0]}`) };
    return { error: typeof detalle === 'string' ? detalle : `la API respondió ${r.status}`,
        ...(json && typeof json === 'object' ? { cuerpo: json as Record<string, unknown> } : {}) };
}

/** Lo que la página pide y la API de este telar no tiene. */
const faltaEnLaApi = (que: string) => `falta en la API: ${que} (¿un telar más viejo que la página?)`;
const deServe = <T>(ruta: string, timeout: number) => aServe<T>('GET', ruta, timeout);

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
    /** si las otras personas del bus lo ven en su directorio (EQUIPO); por defecto, no */
    publico?: boolean;
    /** el agente residente del que es (su carpeta) y su ícono; "" si no es de ninguno */
    agente?: string; icono?: string;
    /** quién lo abrió, si no fue la persona: el hilo (o el periódico) que lo abrió, y su agente y su ícono si era de uno */
    abierto_por?: { por: string; agente?: string; icono?: string; cuando?: string } | null;
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
    /** cuánto toma: «rapida» (media hora o menos) o «larga» (horas o días); vacío sin decir */
    tamano?: string;
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
    /** su prioridad, de 0 (P0, la más alta) a 3; null si el proveedor no la dice */
    prioridad?: number | null;
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
    return await deServe<JsonResultado>(`/resultados/${encodeURIComponent(clave)}${dia ? `?dia=${encodeURIComponent(dia)}` : ''}`, 30000);
}

/** Un comentario sobre el resultado de un día: lo atiende la máquina donde vive, y dice qué abrió
 *  (`telar resultado <clave> <día> --comentar`, con el texto por la entrada estándar). */
export async function comentarResultado(clave: string, dia: string, texto: string): Promise<{ ok: boolean; abrio?: string; error?: string }> {
    const r = await aServe<{ ok: boolean; abrio?: string; error?: string }>('POST', `/resultados/${encodeURIComponent(clave)}/comentario`, 90000, { dia, texto });
    return r.datos ?? { ok: false, error: r.error };
}

/** Un mensaje que escribe la persona desde otra parte (el panel) a un hilo de cualquier máquina, por
 *  el bus: le llega como suyo (`telar mensaje <hilo> - --tipo persona`). */
export const escribirComoPersona = async (hilo: string, texto: string, de: string) => {
    const r = await aServe<{ ok?: boolean; id?: string; error?: string }>('POST', '/mensajes', 30000, { para: hilo, texto, tipo: 'persona', de });
    return r.error ? { error: r.error } : { ok: true, id: r.datos?.id };
};

/** Las fotos de los hilos de otras máquinas que llegaron aquí (`telar espejo ver`). */
export interface JsonEspejo { nombre: string; en_linea: boolean; edad: number | null; error?: string; hilos: { nombre: string; atencion?: string; vivo?: boolean; relativa?: string; prioridad?: number | null; resumen?: string; remoto?: string }[] }
export const espejos = async () => await deServe<{ espejos: JsonEspejo[] }>('/espejos', 15000);

/** Una nota sobre un evento del día (`telar evento`). */
export interface JsonNota { de: string; texto: string; creado: string }
export interface JsonNotas {
    ok: boolean; error?: string; aviso?: string; dia: string;
    eventos: Record<string, { titulo: string; inicio: string; notas: JsonNota[] }>;
}
export const notasEventos = async (dia = '') => await deServe<JsonNotas>(`/notas${dia ? `?dia=${encodeURIComponent(dia)}` : ''}`, 30000);
/** `de`: quién la escribe, la persona de esta máquina (`yo.persona` del dashboard). */
export const notaEvento = async (evento: string, texto: string, titulo: string, inicio: string, dia = '', de = '') =>
    await aServe<{ ok: boolean; error?: string }>('POST', '/notas', 30000, { evento, texto, de, titulo, inicio, dia });

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
/** Preparar o hacer la minuta de una reunión (`telar reunion`). Con `preguntar`, si no se sabe de qué
 *  proyecto es, no hace nada y devuelve los candidatos (`hecho: "preguntar"`); `proyecto` es la elección. */
export const reunion = (titulo: string, hora: string, enlace = '', evento = '',
    opciones: { asistentes?: string[]; proyecto?: string; preguntar?: boolean; donde?: boolean } = {}) =>
    aServe<JsonReunion>('POST', '/reunion', 60000, { titulo, hora, enlace, evento, asistentes: opciones.asistentes ?? [],
        proyecto: opciones.proyecto ?? '', preguntar: !!opciones.preguntar, donde: !!opciones.donde });

/** Dónde quedó un archivo arrastrado a un hilo: su ruta en la máquina del hilo ('' es la de aquí). */
export interface JsonEntrada { ruta: string; maquina: string; bytes: number }
/** Un archivo arrastrado a un hilo, en la carpeta de entrada de su máquina (servicios/archivos.py, `POST
 *  /archivos/entrada`): uno de esta máquina nombrado por su ruta (se copia por ssh a la del hilo), o uno que se
 *  sube entero. Con tiempo: puede ser grande y la red, lenta. */
export const entradaPorRuta = (hilo: string, maquina: string, ruta: string) =>
    aServe<JsonEntrada>('POST', '/archivos/entrada', 10 * 60 * 1000, { hilo, maquina, ruta });
export function entradaSubida(hilo: string, maquina: string, archivo: File): Promise<Respuesta<JsonEntrada>> {
    const f = new FormData();
    f.append('hilo', hilo); f.append('maquina', maquina); f.append('archivo', archivo, archivo.name);
    return aServe<JsonEntrada>('POST', '/archivos/entrada', 10 * 60 * 1000, f);
}

/** Una unidad del perfil, tenga hilo o no (`telar proyectos --json`). */
export interface JsonProyecto {
    ruta: string; nombre: string; arquetipo: string; modificado: string | null; hilo: string; vivo: boolean;
    /** el cliente, si el nombre lo lleva adelante («Cliente · título»); "" si no */
    cliente?: string;
    /** sin cliente, o con uno que es la casa misma (`internos` del perfil): se muestra el nombre, no el cliente */
    interno?: boolean;
    /** el Estado (o la Etapa) de su tabla de campos, corto; y entero */
    estado?: string; estado_completo?: string;
    /** el área que declara su frontmatter («area: PIA»); "" si no la tiene */
    area?: string;
}

/** Las unidades, y `areas`: el orden en que se muestran las áreas (`areas` del perfil). */
export const proyectos = async () => await deServe<{ raiz: string; proyectos: JsonProyecto[]; areas?: string[] }>('/proyectos', 30000);

/** Los pendientes de los documentos de todas las unidades, tengan hilo o no (sin proveedores: rápido). */
export const pendientesRepo = async () => await deServe<{ pendientes: JsonFila[] }>('/pendientes?repo=true', 30000);

/** `telar proyectos abrir`: un hilo vinculado a esa unidad con el agente cargándola, o ir al que ya hay. */
export const abrirProyecto = async (ruta: string) =>
    await aServe<{ hilo: string; ruta: string; mensaje: string; hecho: string }>('POST', '/proyectos/abrir', 30000, { ruta });

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
/** `en`: arriba de otra pestaña («plan»); `dentro`: una subpestaña de una de las fijas («proyectos») */
export interface JsonBloque { clave: string; nombre: string; color: string; en?: string; tecla?: string; dentro?: string }

/** `telar bloque <clave> --item <id>`: el detalle de un ítem (el cuerpo de un correo), al abrirlo. */
export async function bloqueItem(clave: string, id: string): Promise<Respuesta<{ texto: string }>> {
    return await deServe<{ texto: string }>(`/bloques/${encodeURIComponent(clave)}/items/${encodeURIComponent(id)}`, 70000);
}

/** `window.lienzo.pedir`: lo que la página de un módulo pide que telar haga por ella (telar.servicios.lienzos). Sin la
 *  concesión, un error con `cuerpo.permiso` (qué preguntarle a la persona). */
export async function lienzoPedir(origen: string, orden: string, datos: unknown): Promise<Respuesta<{ orden: string; datos: unknown }>> {
    return await aServe<{ orden: string; datos: unknown }>('POST', '/lienzo/pedir', 60000, { origen, orden, datos });
}

/** Anotar lo que la persona decidió sobre lo que pide un módulo (telar.concesiones). */
export async function conceder(modulo: string, orden: string, decision: 'concedido' | 'negado' | 'olvidar'): Promise<Respuesta<unknown>> {
    return await aServe<unknown>('POST', '/permisos', 15000, { modulo, orden, decision });
}

/** `telar bloque <clave>`: la página que imprime su comando. */
export async function bloque(clave: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/bloques/${encodeURIComponent(clave)}`, 90000);
}

export interface JsonPestana { nombre: string; tecla: string }
/** La configuración resuelta (`/config`). */
export type JsonConfig = {
    calendario: JsonCalendario; agente: JsonAgenteConfig; hilos: { directorios: string[]; tope: number };
    atajos?: JsonAtajo[]; secciones?: JsonSeccion[]; apps?: JsonApp[];
    /** las pestañas del dashboard: su orden y las que no se muestran (`[dashboard]`) */
    dashboard?: { orden: string[]; ocultas: string[] };
    /** los módulos instalados (`[modulos]`) y lo que aporta cada uno */
    modulos?: { nombre: string; carpeta: string; descripcion: string; aporta: string[] }[]; remotos?: JsonRemoto[];
    /** el bus de esta persona: url, persona y máquina; vacío sin bus */
    bus?: { url?: string; persona?: string; maquina?: string }; bloques?: JsonBloque[];
    pestanas?: JsonPestana[];
    /** el agente que recibe lo que no tiene proyecto (`[agentes] sin_proyecto`); vacío si no hay */
    agente_general?: { clave?: string; nombre?: string };
    /** quién es la persona de esta máquina: una tarea sin dueño es suya */
    persona?: string; persona_nombres?: string[];
    /** la carpeta del estado de telar en esta máquina */
    estado?: string;
    /** dónde vive la bandeja del equipo, vista desde aquí: «aqui», otra máquina, o vacío */
    equipo?: string;
};
export async function config(): Promise<Respuesta<JsonConfig>> {
    return await deServe<JsonConfig>('/config', 20000);
}

/** `telar encargar <agente> "…"`: pedirle algo a un agente residente, viva donde viva. */
export const encargar = async (agente: string, texto: string) =>
    await aServe<{ hilo?: string; estado?: string; id?: string }>('POST', '/encargos', 30000, { agente, texto });

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
    /** más texto para el buscador del bloque, que no se muestra (las direcciones y los nombres de un correo) */
    busca?: string;
    /** su id en el bloque: con él, el dashboard pide su detalle (el cuerpo de un correo) al abrirlo */
    id?: string;
    /** con `enlace`: un texto que identifica una pestaña ya abierta del navegador (su título o su
     *  dirección lo contiene, p. ej. la cuenta de Gmail). Lo usaba la extensión de VS Code, en macOS; una
     *  página no puede mover otra pestaña, así que el enlace se abre en una nueva */
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

export const seccion = async (clave: string) => await deServe<JsonPagina>(`/secciones/${encodeURIComponent(clave)}`, 40000);
export const app = async (clave: string) => await deServe<JsonPagina>(`/apps/${encodeURIComponent(clave)}`, 40000);
/** Guardar el orden de las pestañas del dashboard: «ahora,revisar,-plan» (con «-», oculta). */
export const configPestanas = async (valor: string) =>
    await aServe<{ dashboard: { orden: string[]; ocultas: string[] } }>('PUT', '/config/pestanas', 20000, { valor });
/** La ficha de una tarea (`telar tarea`) y correr una de sus acciones, por su número. */
export async function tarea(id: string, proveedor: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/tareas/${encodeURIComponent(id)}?proveedor=${encodeURIComponent(proveedor)}`, 40000);
}
/** Correr la acción de una tarea por su `rol` (hecha…): un solo viaje, sin leer la ficha antes. */
export async function accionPorRol(id: string, proveedor: string, rol: string, texto = ''): Promise<Respuesta<{ tipo: string; hecho: string; salida?: string; hilo?: string }>> {
    return await aServe<{ tipo: string; hecho: string; salida?: string; hilo?: string }>('POST', `/tareas/${encodeURIComponent(id)}/accion`, 40000, { proveedor, rol, ...(texto ? { texto } : {}) });
}
/** `hilo`: con una acción que lleva su mensaje a un hilo (`al_hilo`), a cuál; sin él, al de la tarea. */
export async function accionTarea(id: string, proveedor: string, n: number, texto = '', version = '', hilo = ''): Promise<Respuesta<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>> {
    return await aServe<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>('POST', `/tareas/${encodeURIComponent(id)}/accion`, 40000, { proveedor, n, texto, ...(version ? { version } : {}), ...(hilo ? { hilo } : {}) });
}

/** Un objeto de telar por su dirección (`tipo:id[@máquina]`, GET /objetos/<dirección>): lo que muestra la vista
 *  de un objeto (web/objeto.ts). */
export interface JsonObjeto {
    direccion: string; tipo: string; id: string; titulo: string; estado?: string; resumen?: string;
    campos?: Record<string, unknown>; enlaces?: string[];
    acciones?: { nombre: string; descripcion?: string; params?: Record<string, string>;
        /** los valores de un parámetro para elegir en vez de escribir (los productos, los estados) */
        opciones?: Record<string, { valor: string; nombre: string }[]> }[];
    version?: string; maquina?: string;
}

/** Una dirección en la ruta de la API: con sus `:`, `/` y `@` a la vista, lo demás escapado. */
const enRuta = (direccion: string) => encodeURIComponent(direccion).replace(/%3A/gi, ':').replace(/%2F/gi, '/').replace(/%40/g, '@');

export async function objeto(direccion: string): Promise<Respuesta<JsonObjeto>> {
    return await deServe<JsonObjeto>(`/objetos/${enRuta(direccion)}`, 20000);
}

/** Correr una acción de un objeto con sus parámetros, sobre la versión que se está mirando (si cambió, 409). */
/** Una tarea nueva (`telar tipo tarea crear`): `titulo` y lo que acepta su `nueva` (vence, proyecto, tamano…). */
export async function crearTarea(params: Record<string, string>): Promise<Respuesta<{ id: string; titulo: string }>> {
    return await aServe<{ id: string; titulo: string }>('POST', '/tipos/tarea', 40000, { params });
}

export async function accionObjeto(direccion: string, accion: string, params: Record<string, string>, version = ''): Promise<Respuesta<{ objeto?: JsonObjeto | null; resultado?: unknown }>> {
    return await aServe<{ objeto?: JsonObjeto | null; resultado?: unknown }>('POST', `/objetos/${enRuta(direccion)}/acciones/${encodeURIComponent(accion)}`,
        40000, { params, ...(version ? { version } : {}) });
}

/** Los procesos periódicos (`telar periodicos`), de esta máquina o de `[periodicos] en`. */
export interface JsonPeriodico {
    nombre: string; cuando: string; tipo: 'comando' | 'mensaje'; comando: string; mensaje: string; hilo: string;
    max_abiertos: number; argumentos: string[]; carpeta: string; descripcion: string; activo: boolean;
    proxima: string;
    ultima: { inicio?: string; fin?: string; codigo?: number; resultado?: string; corriendo?: boolean; hilo?: string };
    /** el módulo que lo trae, o si lo declara un `[disparadores.x]`: no se cambia desde aquí, sino allá */
    modulo?: string; disparador?: boolean;
}
export interface JsonPeriodicos { maquina: string; archivo: string; zona: string; procesos: JsonPeriodico[] }

/** Un verbo de `telar periodicos`, por la API (que lo pide a la máquina donde viven, por el bus). */
async function periodicosPor<T>(argv: string[], timeout: number): Promise<Respuesta<T>> {
    return await aServe<T>('POST', '/periodicos', timeout, { argv });
}
export const periodicos = async () => await deServe<JsonPeriodicos>('/periodicos', 30000);
export const periodicosLog = (nombre: string) => periodicosPor<{ nombre: string; log: string }>(['log', nombre, '--lineas', '200'], 30000);
export const periodicosHorario = (cuando: string) =>
    periodicosPor<{ valido: boolean; cuando: string; proximas: string[]; error: string }>(['horario', cuando, '--n', '3'], 30000);
export interface JsonSkill { nombre: string; descripcion: string; origen: string }
export const periodicosSkills = (carpeta: string) =>
    periodicosPor<{ carpeta: string; skills: JsonSkill[] }>(['skills', ...(carpeta ? ['--carpeta', carpeta] : [])], 30000);
/** Cambiar uno: `nuevo`, `editar`, `pausar`, `activar`, `borrar`, `ahora`, con sus banderas. */
export const periodicosOrden = (args: string[]) => periodicosPor<{ ok: boolean; hecho: string }>(args, 60000);

/** Una conversación del agente, entera, para leerla. */
export interface JsonConversacion {
    conversacion: string; archivo: string; hilo: string;
    mensajes: { quien: 'usuario' | 'agente' | 'herramienta'; hora: string; texto: string }[];
}

export const conversacion = async (id: string) => await deServe<JsonConversacion>(`/conversaciones/${encodeURIComponent(id)}`, 20000);

/** `telar atajo <tecla>`: un hilo nuevo con el agente y el mensaje de ese atajo. */
export async function abrirItem(clave: string, mensaje: string, nombre: string): Promise<Respuesta<{ hilo: string; mensaje: string }>> {
    return await aServe<{ hilo: string; mensaje: string }>('POST', `/bloques/${encodeURIComponent(clave)}/abrir`, 30000, { mensaje, nombre });
}
export const atajo = async (tecla: string) =>
    await aServe<{ hilo: string; mensaje: string }>('POST', `/atajos/${encodeURIComponent(tecla)}`, 30000);


/** `telar config --directorios a,b`: de qué carpetas salen los hilos. Vacío: las del perfil. */
export const directoriosHilos = (carpetas: string) => ajusteConfig('directorios', carpetas);

/** `telar config --reunion`: qué decirle al agente al preparar una reunión. Vacío: el de fábrica. */
export const plantillaReunion = (texto: string) => ajusteConfig('reunion', texto);

/** `telar config --proyecto`: qué decirle al agente al abrir un proyecto. Vacío: el de fábrica. */
export const plantillaProyecto = (texto: string) => ajusteConfig('proyecto', texto);

/** `telar config --calendario gws|ninguno|<dirección>`: elegir de dónde sale la agenda. */
export const elegirCalendario = (valor: string) => ajusteConfig('calendario', valor);

/** Un ajuste de la configuración (`PUT /config/<ajuste>`). */
async function ajusteConfig(ajuste: string, valor: string): Promise<Salida> {
    const r = await aServe<{ archivo: string }>('PUT', `/config/${ajuste}`, 20000, { valor });
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: r.datos?.archivo ?? '', err: '' };
}

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
    if (!raiz || !esAbsoluta(raiz)) return h;
    const ruta = h.ruta && !esAbsoluta(h.ruta) && h.relativa ? unir(raiz, h.relativa) : h.ruta;
    const f = h.ficha;
    const ficha = f && f.documento && !esAbsoluta(f.documento) && f.relativo
        ? { ...f, documento: unir(raiz, f.relativo) }
        : f;
    return ruta === h.ruta && ficha === f ? h : { ...h, ruta, ficha };
}

// ───────────────────────── las órdenes que usa la vista ─────────────────────────

export async function hilos(conFicha: boolean, orden: string): Promise<Respuesta<JsonHilos>> {
    const q = new URLSearchParams({ orden, ...(conFicha ? {} : { ficha: 'false' }) }).toString();
    return await deServe<JsonHilos>(`/hilos?${q}`, conFicha ? 30000 : 8000);
}

export const ficha = async (hilo: string) => await deServe<JsonFichaOrden>(`/ficha?hilo=${encodeURIComponent(hilo)}`, 30000);

/** Sin `local`, se consulta a los proveedores declarados y puede tardar lo que tarden. */
export async function hoy(local: boolean, dia = ''): Promise<Respuesta<JsonHoy>> {
    const q = new URLSearchParams({ ...(local ? { local: 'true' } : {}), ...(dia ? { dia } : {}) }).toString();
    return await deServe<JsonHoy>(`/hoy${q ? `?${q}` : ''}`, local ? 20000 : 60000);
}

export async function ir(hilo: string, crear = false, remoto = ''): Promise<Salida> {
    const r = await aServe<{ hilo: string; hecho: string }>('POST', '/ir', remoto ? 60000 : 20000, { hilo, crear, remoto });
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: `→ «${r.datos?.hilo ?? hilo}»`, err: '' };
}

/** Una skill que el agente de un hilo tiene a mano (`telar agente skills`). */
export interface JsonSkill {
    nombre: string; descripcion: string; origen: string; alcance: string; ruta: string;
    /** cuántas veces se usó en la conversación del hilo */
    usada: number;
}
type JsonSkills = { hilo: string; conversacion: string; remoto: boolean; skills: JsonSkill[] };
export const skills = async (hilo: string, carpeta = '') => await deServe<JsonSkills>(
    `/skills?hilo=${encodeURIComponent(hilo)}${carpeta ? `&carpeta=${encodeURIComponent(carpeta)}` : ''}`, 30000);

/** `telar actuar`: mandarle a un hilo o a un agente un prompt sobre una entidad (docs/propuestas/acciones.md). */
export interface JsonActuado { destino: string; como: string; prompt: string; maquina?: string }
export async function actuar(direccion: string, a: string, skill: string, nota: string, escribir: boolean): Promise<Respuesta<JsonActuado>> {
    return await aServe<JsonActuado>('POST', '/actuar', 60000, { direccion, a, skill, nota, escribir });
}

/** Lo último de un hilo (`telar hilo leer`), de esta máquina o de otra por el bus: el JSON tal cual. */
export async function leerHilo(hilo: string, ultimos: string, maquina = ''): Promise<Salida> {
    const q = new URLSearchParams({ hilo, ultimos, ...(maquina ? { maquina } : {}) }).toString();
    const r = await deServe<unknown>(`/hilos/leer?${q}`, 35000);
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: JSON.stringify(r.datos), err: '' };
}

/** `telar compartir`: a dónde se puede llevar algo compartido, y llevarlo. El JSON tal cual. */
export async function compartirDestinos(): Promise<Salida> {
    const r = await deServe<unknown>('/compartir/destinos', 15000);
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: JSON.stringify(r.datos), err: '' };
}
export async function compartir(a: string, url: string, texto: string, titulo: string): Promise<Salida> {
    const r = await aServe<unknown>('POST', '/compartir', 40000, { a, url, texto, titulo });
    return r.error ? { ok: false, codigo: 1, out: JSON.stringify({ ok: false, error: r.error }), err: r.error } : { ok: true, codigo: 0, out: JSON.stringify(r.datos), err: '' };
}

/** Un mensaje entre hilos por el bus, como lo guarda su registro (`telar mensaje --registro`). */
export interface JsonMensajeBus {
    id: string; de: string; para: string; tipo: string; texto: string; creado: string;
    persona?: string; saltos?: number; estado?: 'enviado' | 'retenido'; motivo?: string;
}
/** Los últimos mensajes entre hilos, de todas las máquinas. Sin bus, error (y la pestaña no los muestra). */
export const mensajesBus = async (n = 60) => await deServe<{ mensajes: JsonMensajeBus[] }>(`/mensajes?n=${n}`, 30000);
/** `telar mensaje --soltar <id>`: la persona deja pasar un mensaje retenido. */
export const soltarMensaje = async (id: string) =>
    await aServe<{ id: string; para: string }>('POST', `/mensajes/${encodeURIComponent(id)}/soltar`, 30000);

/** Un módulo instalado (`GET /modulos`): activo o apagado, su carpeta y de dónde vino. */
export interface JsonModuloInstalado {
    nombre: string; activo: boolean; carpeta: string; descripcion: string; aporta: string[];
    fuente: string; version: string; ref: string; catalogo: string; enlazado: boolean; instalado: string;
    a_mano: boolean; pide: string[]; confianza: string; nueva: string;
}
/** Uno de un catálogo (`GET /modulos/catalogo`): `confianza` es oficial, equipo o sin revisar. */
export interface JsonModuloDisponible {
    nombre: string; descripcion: string; fuente: string; version: string; autor: string; etiquetas: string[];
    telar: string; permisos: Record<string, unknown> | null; catalogo: string; confianza: string;
    instalado: boolean; le_sirve: boolean;
}
export const modulosInstalados = async () => await deServe<{ modulos: JsonModuloInstalado[] }>('/modulos', 30000);
export const modulosCatalogo = async (forzar = false) =>
    await deServe<{ disponibles: JsonModuloDisponible[]; problemas: string[] }>(`/modulos/catalogo${forzar ? '?forzar=true' : ''}`, 30000);
export const modulosAccion = async (accion: string, nombre: string) =>
    await aServe<{ salida: string }>('POST', `/modulos/${encodeURIComponent(accion)}`, 600000, { nombre });

/** Un agente residente, como lo da `telar agentes --json` (docs/contratos.md). */
export interface JsonAgente {
    clave: string; nombre: string; direccion: string; carpeta: string; definicion: string; para: string; modelo: string;
    residente: boolean; hilos: string[]; en: string; problemas: string[];
    /** siempre (lo mantiene abierto el nodo), a-pedido (se abre cuando le llega algo) o no */
    presencia?: 'siempre' | 'a-pedido' | 'no';
    publico?: boolean;
    /** uno o dos caracteres que la lista pone junto a cada hilo suyo */
    icono?: string;
    politica?: { permite?: string[]; pregunta?: string[]; niega?: string[] };
}
/** Un encargo, en corto (telar.encargo): su estado va pedido → corriendo → hecho | falló | cancelado. */
export interface JsonEncargoCorto { id: string; estado: string; texto: string; de?: string; creado?: string; actualizado?: string; resultado?: string }
/** Un agente en la vista de agentes (`GET /agentes`): su definición y su estado donde vive. */
export interface JsonEstadoAgente {
    agente: JsonAgente; maquina: string; aqui: boolean; vivo: boolean; atencion: string;
    conversacion: { id: string; peso: number; tope: number } | null; rotacion: string;
    relevo: { cuando: string } | null; encargos: JsonEncargoCorto[]; sin_noticias?: boolean;
    /** los hilos que abrió (no los suyos): para verlos, o archivarlos de una vez */
    abrio?: { hilo: string; vivo: boolean; archivado: boolean; cuando: string }[];
}
export const agentes = async () => await deServe<{ agentes: JsonEstadoAgente[]; problemas: string[] }>('/agentes', 40000);
/** Rotar ya la conversación de un agente, con relevo (`POST /agentes/rotar`). */
export const rotarAgente = async (hilo: string, maquina = '') =>
    await aServe<{ hecho?: string }>('POST', '/agentes/rotar', 30000, { hilo, maquina });
/** Un agente residente nuevo en esta máquina (`POST /agentes/nuevo`): su carpeta, y `[agentes] carpeta` si faltaba. */
export const nuevoAgente = async (nombre: string, para = '') =>
    await aServe<{ clave: string; nombre: string; carpeta: string; configurado: boolean }>('POST', '/agentes/nuevo', 30000, { nombre, para });
/** La ficha de un agente para la barra de la derecha (`GET /agentes/del-hilo`): su definición, su CLAUDE.md, su
 *  último relevo y el peso de su conversación (`aqui`: si vive en esta máquina; si no, esas dos no se saben). */
export interface JsonFichaAgente {
    agente: JsonAgente; claude_md: string; definicion_texto: string; aqui: boolean;
    encargos?: JsonEncargoCorto[];
    relevo: { texto: string; ruta: string; cuando: string } | null;
    conversacion: { id: string; peso: number; tope: number } | null;
    rotacion: string;
}
export const fichaAgente = async (hilo: string, maquina = '') =>
    await deServe<JsonFichaAgente>(`/agentes/del-hilo?hilo=${encodeURIComponent(hilo)}${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`, 15000);

/** La versión de telar (`GET /version`): la que corre, la última en PyPI y si un clic la instala (`puede`: solo
 *  una instalación de `uv tool`); `a_mano`, qué hacer si no; `progreso`, la actualización en curso o la última. */
export interface JsonVersion {
    corre: string; ultima: string; hay_nueva: boolean; como: 'uv' | 'repo' | 'otro'; puede: boolean;
    consultado?: number | null; notas?: string; error?: string; a_mano?: string; progreso?: JsonProgreso;
    /** en un servidor con puerta, a quien la administra: su versión, si va atrás de telar y la orden para ponerla al día */
    puerta?: { version: string; atras: boolean; telar: string; url: string; actualizar?: string };
}
export interface JsonProgreso { version?: string; estado?: 'corriendo' | 'listo' | 'fallo'; desde?: number; hasta?: number; error?: string; log?: string }
export const version = async (forzar = false) => await deServe<JsonVersion>(`/version${forzar ? '?forzar=true' : ''}`, 20000);
export const actualizar = async (v: string) => await aServe<JsonProgreso>('POST', '/actualizar', 30000, { version: v });
export const progresoActualizar = async () => await deServe<JsonProgreso>('/actualizar', 10000);
/** La versión que contesta el servicio ahora (`/salud`): cambia cuando la actualización lo reinició. */
export const versionCorriendo = async () => (await deServe<{ version?: string }>('/salud', 5000)).datos?.version ?? '';

/** Un hilo de otra persona, como lo publica su nodo (telar.entre_personas): nunca su conversación. */
export interface JsonHiloColega { nombre: string; ext: string; vivo: boolean; carpeta: string; resumen: string }
/** Los hilos de las otras personas del bus (`GET /directorio`), por persona y máquina; `al_dia`: si su nodo
 *  publicó hace poco (si no, la lista puede estar vieja). */
export interface JsonDirectorio {
    yo: string;
    personas: { persona: string; maquinas: { maquina: string; publicado: string; visto: string; al_dia: boolean; hilos: JsonHiloColega[] }[] }[];
}
export const directorio = async () => await deServe<JsonDirectorio>('/directorio', 20000);
/** Un mensaje a la casilla de un hilo de otra persona (`telar correo enviar persona+hilo@…`). */
export const escribirColega = async (persona: string, hilo: string, texto: string) =>
    await aServe<{ id: string; persona: string; hilo: string }>('POST', '/directorio/escribir', 40000, { persona, hilo, texto });

/** Una cuenta del bus y su rol (`telar bus personas`, telar.personas). */
export interface JsonCuenta { nombre: string; rol: 'dueño' | 'admin' | 'miembro' }
/** Un pedido de entrada al bus (`telar instalar --unirse`): pendiente, o decidido hace poco (`por`, quién). */
export interface JsonPedidoEntrada {
    id: string; persona: string; estado: 'pendiente' | 'aprobado' | 'rechazado'; cuando: number;
    decidido?: number | null; por?: string; tailscale: string; desde: string; maquina?: string; equipo?: string;
}
/** La gestión de personas del bus (`GET /personas`): quién la pide (`quien`, `rol`), las cuentas y los pedidos;
 *  después de una acción, `hecho` y `falta` (si el bus no se pudo recargar). */
export interface JsonPersonas {
    dueno: string; quien: string; rol: string; personas: JsonCuenta[]; pedidos: JsonPedidoEntrada[];
    hecho?: string; falta?: string;
}
export const personas = async () => await deServe<JsonPersonas>('/personas', 40000);
/** Aprobar o rechazar un pedido (`pedido`, y el `rol` con que entra), quitar una cuenta o cambiarle el rol (`nombre`, `rol`). */
export const personasAccion = async (accion: 'aprobar' | 'rechazar' | 'quitar' | 'rol', datos: { pedido?: string; nombre?: string; rol?: string }) =>
    await aServe<JsonPersonas>('POST', `/personas/${accion}`, 40000, datos);

/** Un lugar en el servidor (telar.alojamiento), como lo ve quien lo administra. */
export interface JsonAlojado {
    persona: string; estado: string; maquina?: string; cuando?: number; listo?: number; error?: string | null;
    memoria?: string; cpu?: string;
    /** la versión de su telar (la que dijo el ayudante al crearlo o actualizarlo); `actualizando`, a cuál va */
    version?: string | null; actualizando?: string | null;
}
export interface JsonAlojamiento {
    dueno: string; quien: string; administra: boolean; servidor: string; alojamientos: JsonAlojado[];
    /** la versión del telar del servidor: a la que se actualiza un alojado */
    telar?: string;
    topes?: { memoria: string; cpu: string }; hecho?: string;
}
/** Los alojados del servidor y los topes de los nuevos (`GET /alojamiento`): solo para quien lo administra. */
export const alojamiento = async () => await deServe<JsonAlojamiento>('/alojamiento', 40000);
/** Cambiar los topes de un alojado (se aplican ya) o, con `persona` vacía, los de los nuevos. */
export const alojamientoTopes = async (persona: string, memoria: string, cpu: string) =>
    await aServe<JsonAlojamiento>('POST', '/alojamiento/topes', 60000, { persona, memoria, cpu });

/** Actualizar el telar de un alojado a la versión del servidor (corre aparte; `alojamiento()` dice cuándo terminó). */
export const alojamientoActualizar = async (persona: string) =>
    await aServe<JsonAlojamiento>('POST', '/alojamiento/actualizar', 60000, { persona });

/** Los fondos que se pueden elegir para la terminal, y cómo se ve ahora (`GET /terminal/fondos`). */
export interface JsonFondos {
    fondos: { valor: string; nombre: string; descripcion: string; tipo: 'propio' | 'modulo' }[];
    actual: { columnas: number; posicion: 'izquierda' | 'centro' | 'derecha'; fondo: string };
}
export const fondosTerminal = async () => await deServe<JsonFondos>('/terminal/fondos', 15000);
/** Cambiar un ajuste de `[terminal]`: columnas (0: todo), posicion o fondo. */
export const ajusteTerminal = async (clave: 'columnas' | 'posicion' | 'fondo', valor: string | number) =>
    await aServe<{ ok: boolean; clave: string; valor: string | number }>('PUT', `/config/terminal/${clave}`, 15000, { valor });

/** Los modos de la página y el catálogo de ajustes (`GET /modos`, telar.modos). */
export interface JsonModos {
    catalogo: { clave: string; grupo: string; nombre: string; opciones: string[]; ayuda: string }[];
    modos: { clave: string; nombre: string; valores: Record<string, string | number>; de_fabrica: boolean; cambiado: boolean }[];
}
export const modos = async () => await deServe<JsonModos>('/modos', 15000);
/** Crear o cambiar un modo: `[modos.<clave>]` con esos valores. */
export const guardarModo = async (clave: string, valores: Record<string, string | number>, nombre = '') =>
    await aServe<{ ok: boolean; modos: JsonModos['modos'] }>('PUT', `/modos/${encodeURIComponent(clave)}`, 15000, { valores, nombre });
/** Quitar `[modos.<clave>]`: uno propio desaparece; uno de fábrica vuelve a ser el de fábrica. */
export const borrarModo = async (clave: string) =>
    await aServe<{ ok: boolean; modos: JsonModos['modos'] }>('DELETE', `/modos/${encodeURIComponent(clave)}`, 15000, {});

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
// la API la pide por el bus a la máquina donde vive
export const equipoPendientes = async (remoto: string) =>
    await deServe<{ sugerencias: JsonSugerencia[] }>(`/equipo/bandeja?maquina=${encodeURIComponent(remoto)}`, 30000);
export const equipoRevisando = async (remoto: string, id: string, quien = 'gestion') =>
    await aServe<{ sugerencia: JsonSugerencia }>('POST', `/equipo/${encodeURIComponent(id)}/revisando?quien=${encodeURIComponent(quien)}`, 30000, { maquina: remoto });
export const equipoResolver = async (remoto: string, verbo: 'aceptar' | 'rechazar' | 'existe', id: string, nota = '', tarea = '') =>
    await aServe<{ sugerencia: JsonSugerencia }>('POST', `/equipo/${encodeURIComponent(id)}/${verbo}`, 40000, { nota, tarea, maquina: remoto });

/** Una máquina de `[remotos]` donde pueden vivir hilos. */
export interface JsonRemoto { nombre: string; destino: string; transporte: string; raiz: string }

/** `telar hilo <verbo> [valor] --hilo <hilo>`: vincular, renombrar, prioridad, archivar… */
export async function hilo(verbo: string, hilo: string, valor?: string, extra: string[] = []): Promise<Salida> {
    if (!extra.every(x => x === '--cerrar')) return { ok: false, codigo: 1, out: '', err: faltaEnLaApi(`telar hilo ${verbo} ${extra.join(' ')}`) };
    // un verbo sobre un hilo de otra máquina va a su dueño por el bus, que espera hasta 60 s: aquí, un poco más
    const r = await aServe<{ codigo: number; salida: string; error: string }>('POST', `/hilo/${encodeURIComponent(verbo)}`, 75000,
        { hilo, valor: valor ?? '', cerrar: extra.includes('--cerrar') });
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: r.datos?.salida ?? '', err: r.datos?.error ?? '' };
}

/** Lo que dice `POST /hilo/llevar`: si sigue copiando (`en_curso`), su salida queda en `registro`. */
export interface JsonLlevado { codigo: number; salida: string; error: string; en_curso: boolean; registro: string }
/** Llevar un hilo a otra máquina de `[remotos]` (`telar hilo llevar`). Copia la conversación por ssh y abre el
 *  hilo allá: con una conversación grande tarda minutos, así que la API responde a los 20 s que sigue en curso.
 *  Con trabajo sin subir aquí, falla (409, con la lista en `cuerpo.salida`) hasta que `si`. */
export const llevar = (hilo: string, maquina: string, si = false) =>
    aServe<JsonLlevado>('POST', '/hilo/llevar', 60000, { hilo, maquina, si });
/** En qué va la mudanza de un hilo (telar.mudanza.progreso): {} si no hay ninguna. */
export interface JsonMudanza { hilo?: string; paso?: string; maquina?: string; bytes?: number; error?: string;
    avisos?: string[]; aviso?: string; carpeta?: string; hora?: number }
export const mudanza = (hilo: string) => deServe<JsonMudanza>(`/mudanza?hilo=${encodeURIComponent(hilo)}`, 5000);
/** Traer a esta máquina un hilo que vive en `maquina` (otra tuya): esa lo lleva aquí por el bus. Espera a que termine. */
export const traer = (hilo: string, maquina: string, si = false) =>
    aServe<JsonLlevado>('POST', '/hilo/traer', 620000, { hilo, maquina, si });

/** Lleva un pendiente al hilo donde se trabaja y se lo deja escrito al agente, sin enviar:
 *  apretar Enter le toca a la persona, y esa decisión no se automatiza desde una barra. */
/** `proveedor`, si se sabe, evita preguntarles a todos (el calendario se baja entero): de 5 s a menos de 1. */
/** `fila`: la de `telar pendientes` que ya se tiene (foco): telar no la vuelve a buscar (unos 2 s menos). */
export const pendiente = async (ref: string, nuevo = false, proveedor = '', texto = '', enviar = false, fila?: JsonFila) =>
    await aServe<JsonPendienteIdo>('POST', '/pendiente/llevar', 90000, { ref, nuevo, proveedor, texto, enviar, ...(fila ? { fila } : {}) });

/** Una casilla en su documento: `--hecho`, `--responsable NOMBRE` o `--linea`. `esperado` es el texto
 *  que se vio: si el documento cambió y ya no dice eso, telar no toca nada. */
export interface JsonVineta { ref: string; archivo: string; relativa: string; linea: number; hecho: string }
export async function vineta(ref: string, esperado: string, opciones: string[]): Promise<Respuesta<JsonVineta>> {
    const i = opciones.indexOf('--responsable');
    const cuerpo = { ref, esperado, hecho: opciones.includes('--hecho'), linea: opciones.includes('--linea'),
        ...(i >= 0 ? { responsable: opciones[i + 1] ?? '' } : {}) };
    return await aServe<JsonVineta>('POST', '/pendiente/casilla', 60000, cuerpo);
}

export async function tejer(sumar = false): Promise<Salida> {
    const r = await aServe<{ codigo: number; salida: string; error: string }>('POST', '/tejer', sumar ? 60000 : 20000, { sumar });
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: r.datos?.salida ?? '', err: r.datos?.error ?? '' };
}

/** Cómo se llama un hilo en pantalla: la etiqueta de su ficha, o su nombre. El nombre sigue
 *  siendo la llave (la del multiplexor y la del estado): esto solo cambia lo que se lee. */
export function nombreVisible(h: JsonHilo): string {
    return h.ficha?.etiqueta?.trim() || h.nombre;
}

