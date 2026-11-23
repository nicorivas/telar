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
import type { Hecho, Pendiente } from './web/alcance';

/** Lo que devuelve una orden que no tiene JSON propio: si salió bien, y su salida o su error. */
export interface Salida { ok: boolean; codigo: number; out: string; err: string }

/** Una respuesta de la API: los datos, o el motivo por el que no llegaron (y, con el motivo, lo demás que
 *  traiga la respuesta: la salida de lo que falló). */
/** Lo que respondió la API: los datos, o el error (con el código HTTP en `estado`, si llegó a responder). */
export interface Respuesta<T> { datos?: T; error?: string; cuerpo?: Record<string, unknown>; estado?: number }

// ───────────────────────── la API (`telar serve`) ─────────────────────────

/** Un pedido a la API. Una ruta que la API no tiene (un telar más viejo que la página) se dice así, como
 *  un error: no hay otro camino por el que pedirlo. El cuerpo va como JSON; un FormData, como multipart (el
 *  navegador pone el tipo, con su separador). */
async function aServe<T>(metodo: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', ruta: string, timeout: number, cuerpo?: unknown): Promise<Respuesta<T>> {
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
    return { error: typeof detalle === 'string' ? detalle : `la API respondió ${r.status}`, estado: r.status,
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
    /** su dirección (`hilo:Faro`; `hilo:Faro@telar` si su agente vive en otra máquina) */
    direccion?: string;
    /** si las otras personas del bus lo ven en su directorio (EQUIPO); por defecto, no */
    publico?: boolean;
    /** sus etiquetas («trabajo», «personal»): los modos filtran la lista por ellas (`telar hilo etiquetas`) */
    etiquetas?: string[];
    /** el hilo del que cuelga (`telar hilo padre`, o el que lo abrió, salvo que se haya soltado); "" si de ninguno */
    padre?: string;
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
    /** su rama propia, si es un hijo que trabaja en su worktree (`telar hilo hijo --rama`): la fusiona su padre */
    rama?: { rama: string; base: string; ruta: string } | null;
    /** si espera a la persona, qué pide y de qué clase (`permiso`, `pregunta`, `confiar`: detenido en la pregunta de
     *  Claude Code de confiar en una carpeta, antes de arrancar), si se sabe; null si no */
    espera?: { clase: string; pide: string } | null;
    /** si duerme (telar.dormir): su agente se cerró por estar quieto y su ventana espera; abrirlo lo despierta. `desde`,
     *  hora local ISO («" "» si duerme en otra máquina y no se sabe); null si no duerme */
    dormido?: { desde: string; conversacion: string } | null;
    /** la ventana de aquí de uno de otra máquina (`remoto`) que está fuera de línea (telar.alcance): `false`, y su atención
     *  y si duerme son de antes de que se fuera; sin eso, no viene */
    alcanzable?: boolean;
    /** desde cuándo está fuera de línea su máquina (ISO), con `alcanzable: false` */
    fuera_de_linea_desde?: string;
    /** la parte de la vida a la que pertenece (`[mundos]`): por sus etiquetas, su carpeta, su agente o su padre; "" sin
     *  clasificar. Sin `[mundos]` no viene */
    mundo?: string;
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

/** Lo que la persona respondió a una invitación del calendario; vacío si no aplica (un evento propio, uno que organiza
 *  ella) o si el calendario no dice quién es ella. */
export type RespuestaInvitacion = '' | 'aceptada' | 'rechazada' | 'tentativa' | 'sin_responder';

/** Una fila de `telar pendientes` y de `telar hoy`: un pendiente de un documento, o lo que
 *  aportó un proveedor, ya enrutado al hilo donde se trabaja. `ref` es con lo que se agarra
 *  (`faro:2`, o la referencia estable del proveedor). */
export interface JsonFila {
    texto: string; hecho: boolean; en_curso: boolean; id: string; origen: string;
    ref: string; hilo: string; ruta: string; proveedor: string;
    /** su dirección (`tarea:T84`, `pendiente:c-1a2b3c`), si la tiene: la de su entidad (`telar objeto`) */
    direccion?: string;
    cuando: string | null; url: string;
    /** lo último que dejó un agente que la trabajó solo: «preparado 2026-09-25» */
    avance?: string;
    /** su proveedor da ficha (`telar tarea`): un clic la abre en vez de ir al hilo */
    ficha?: boolean;
    /** a qué parte de la vida pertenece («trabajo», «personal»): las listas filtran por aquí */
    area?: string;
    /** su mundo de `[mundos]` (por su área, su proyecto o la carpeta de su documento); "" sin clasificar; sin `[mundos]`,
     *  no viene. Con un mundo puesto, la página muestra lo suyo y lo sin clasificar (web/mundo.ts) */
    mundo?: string;
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
    /** un evento: lo que la persona respondió a la invitación */
    respuesta?: RespuestaInvitacion;
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
    /** de un proveedor: quién la dejó («ana», «correo»…); en una pestaña de lectura, lo de la persona va primero */
    de?: string;
    /** de un proveedor: de cuándo es (AAAA-MM-DD); en una pestaña de lectura, lo más nuevo arriba */
    fecha?: string;
}

/** Lo que dejó una skill un día (`telar resultado <clave> [día]`), leído de la máquina donde vive. */
export interface JsonResultado {
    ok: boolean; error?: string; aviso?: string; desde?: string;
    clave: string; nombre: string; dia: string; dias: string[];
    formato: 'json' | 'md' | ''; contenido: unknown;
    /** el nombre del archivo que se leyó (`estrategia-2026-11-16.md`), si había */
    archivo?: string;
    /** si la máquina donde vive atiende comentarios sobre un día (`[resultados.<clave>] comentar`) */
    comentable?: boolean;
}
export async function resultado(clave: string, dia = ''): Promise<Respuesta<JsonResultado>> {
    return await deServe<JsonResultado>(`/resultados/${encodeURIComponent(clave)}${dia ? `?dia=${encodeURIComponent(dia)}` : ''}`, 30000);
}

/** Una pasada de un resultado que se llena varias veces al día (`pasadas = "pulso"`, telar.pasadas: docs/contratos.md).
 *  Lo que no nombra el esquema viene igual (`[k: string]: unknown`). Cada cosa trae su `mundo`, el que resolvió telar
 *  (el de su tarea, si tiene dirección; si no, el que dijo el agente; "" sin clasificar). Lo que cambió (las tareas y los
 *  borradores) trae su causa (`JsonCausa`); lo que te espera y las vencidas sin propuesta vienen y no se muestran. */
export interface JsonPasada {
    /** la hora local en que empezó, «2026-11-18T13:00»: única en el día, y su día */
    id: string; termino?: string; modo?: 'dia' | 'noche' | string; pedida?: boolean; seco?: boolean;
    /** con `resumenes`, neutro (las cuentas); sin él (las de antes), puede nombrar lo de cualquier mundo */
    resumen?: string;
    /** el resumen de cada mundo: se muestran los de los mundos que se ven */
    resumenes?: Record<string, string>;
    /** `error`, por qué falló (sin él, o vacío, no falló); `nota`, lo que se dice de ella sin que haya fallado */
    fuentes?: { fuente: string; llegaron: number; archivados: number; error?: string; nota?: string; mundo?: string }[];
    tareas?: { nuevas?: JsonTareaPasada[]; avanzadas?: JsonTareaPasada[]; cerradas?: JsonTareaPasada[] };
    te_esperan?: { id: string; pide: string; linea: string; peso: number; vence: string; mundo?: string }[];
    /** su `enlace` es el del borrador; el de su causa no va */
    borradores?: ({ para: string; asunto: string; enlace: string; tarea: string; mundo?: string } & Omit<JsonCausa, 'enlace'>)[];
    /** las tareas vencidas que nadie ha propuesto cerrar ni mover, por su dirección (`tarea:T405`): pulso solo las nombra */
    vencidas_sin_propuesta?: string[];
    /** el mundo de cada vencida sin propuesta, por su tarea */
    mundos_vencidas?: Record<string, string>;
    /** los mundos de sus cosas ("" lo sin clasificar; [""] si no trae ninguna) */
    mundos?: string[];
    /** los de lo que cambió (tareas y borradores); [] si no cambió nada */
    mundos_cambios?: string[];
    /** los mundos en que tiene algo sin ver ("" lo sin clasificar): con un mundo puesto se ve si trae de ese o "" */
    sin_ver_en?: string[];
    [k: string]: unknown;
}
/** Lo que causó un cambio: `por` («correo de Beto Soto», «minuta del 17-nov»), la clave de su `fuente` (su ícono) y
 *  su `enlace` (una dirección o una web). Una pasada de antes de la causa no lo trae. */
export interface JsonCausa { por?: string; fuente?: string; enlace?: string }
/** Una tarea en una pasada: su dirección (o lo que el agente puso, si todavía no existe), su línea, su causa y, si se cerró,
 *  cómo. */
export interface JsonTareaPasada extends JsonCausa { id: string; linea: string; como?: string; mundo?: string }
/** Hasta cuál vio: su id, su día y cuándo se marcó. */
export interface JsonMarcaVisto { id?: string; dia?: string; cuando?: string }
/** Las pasadas con algo sin ver en algún mundo, la más nueva primero (hasta 40; `total`, cuántas son; `con_cambios`, cuántas
 *  cambiaron algo; `por_mundo`, cuántas con cambios se ven con cada mundo puesto), y hasta cuál vio con ambos (`visto`) y
 *  con cada mundo (`vistos`). */
export interface JsonSinVer {
    ok: boolean; error?: string; desde?: string; clave?: string; nombre?: string; esquema?: string;
    visto?: JsonMarcaVisto; vistos?: Record<string, JsonMarcaVisto>; total?: number; con_cambios?: number; por_mundo?: Record<string, number>;
    pasadas?: JsonPasada[];
}
export interface JsonVisto {
    ok: boolean; error?: string; visto?: JsonMarcaVisto; vistos?: Record<string, JsonMarcaVisto>; movio?: boolean; mundo?: string;
}
/** Las pasadas sin ver de un resultado, leídas donde viven (`telar resultado <clave> --sin-ver`). */
export async function pasadasSinVer(clave: string): Promise<Respuesta<JsonSinVer>> {
    return await deServe<JsonSinVer>(`/resultados/${encodeURIComponent(clave)}/visto`, 20000);
}
/** Marcarlas vistas hasta `id` (vacío: hasta la más nueva), donde viven (`telar resultado <clave> --visto`): con `mundo`,
 *  lo de ese mundo y lo sin clasificar; sin él (ambos), todo. */
export async function marcarVisto(clave: string, id: string, mundo = ''): Promise<Respuesta<JsonVisto>> {
    return await aServe<JsonVisto>('POST', `/resultados/${encodeURIComponent(clave)}/visto`, 20000, mundo ? { id, mundo } : { id });
}

/** Un mensaje que escribe la persona desde otra parte (el panel) a un hilo de cualquier máquina, por
 *  el bus: le llega como suyo (`telar mensaje <hilo> - --tipo persona`). */
export const escribirComoPersona = async (hilo: string, texto: string, de: string) => {
    const r = await aServe<{ ok?: boolean; id?: string; error?: string }>('POST', '/mensajes', 30000, { para: hilo, texto, tipo: 'persona', de });
    return r.error ? { error: r.error } : { ok: true, id: r.datos?.id };
};

/** Las fotos de los hilos de otras máquinas que llegaron aquí (`telar espejo ver`), con lo que espera en cola para cada
 *  una y lo que se hizo de esa cola (telar.alcance). `al_dia`: el nodo de aquí está al día con el bus, así que una foto
 *  vieja quiere decir que su máquina se fue. */
export interface JsonEspejo { nombre: string; en_linea: boolean; edad: number | null; error?: string; hilos: { nombre: string; atencion?: string; vivo?: boolean; relativa?: string; prioridad?: number | null; resumen?: string; remoto?: string; mundo?: string }[]; cola?: Pendiente[]; hechos?: Hecho[] }
export const espejos = async () => await deServe<{ espejos: JsonEspejo[]; al_dia?: boolean }>('/espejos', 15000);

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
    /** su mundo de `[mundos]`, por su carpeta; "" sin clasificar; sin `[mundos]`, no viene */
    mundo?: string;
    /** el cliente, si el nombre lo lleva adelante («Cliente · título»); "" si no */
    cliente?: string;
    /** sin cliente, o con uno que es la casa misma (`internos` del perfil): se muestra el nombre, no el cliente */
    interno?: boolean;
    /** el Estado (o la Etapa) de su tabla de campos, corto; y entero */
    estado?: string; estado_completo?: string;
    /** el área que declara su frontmatter («area: PIA»); "" si no la tiene */
    area?: string;
    /** los campos sueltos de su frontmatter, como texto (`{frontmatter:<clave>}`): con qué se agrupan y se describen las
     *  iniciativas (`agrupar_iniciativas` del modo) */
    frontmatter?: Record<string, string>;
    /** su plazo (`telar fechas`, clase plazo): de cuándo a cuándo, en qué etapa va y lo que no cuadra; null si no tiene */
    plazo?: JsonPlazo | null;
}

/** El plazo de una unidad: el de su fuente de fechas (un gestor de proyectos, su cronograma). */
export interface JsonPlazo {
    inicio: string; fin: string;
    /** pendiente (por partir), en-curso, hecho o cancelado */
    estado: string;
    /** la etapa en palabras («desarrollo»); "" si su fuente no la dice */
    etapa?: string;
    /** cuánto avanzó, de 0 a 1; null si su fuente no lo sabe */
    avance?: number | null;
    /** lo que no cuadra («venció el 22-oct»); "" si nada */
    aviso?: string;
    fuente?: string; enlace?: string;
}

/** El vocabulario de estados de las iniciativas (`[iniciativas]` de la configuración). */
export interface JsonVocabulario {
    estados?: string[]; sinonimos?: Record<string, string>; clases?: Record<string, string>;
    /** lo que dice `estado_fuente` en una ficha → cómo se muestra («sheet» → «Sheet») */
    fuentes?: Record<string, string>;
}

/** Las unidades, y `areas`: el orden en que se muestran las áreas (`areas` del perfil); `fallas`, las fuentes de
 *  fechas que no contestaron al buscar los plazos; `iniciativas`, el vocabulario de sus estados. */
export const proyectos = async () =>
    await deServe<{ raiz: string; proyectos: JsonProyecto[]; areas?: string[]; fallas?: string[]; iniciativas?: JsonVocabulario }>('/proyectos', 30000);

/** `telar proyectos estado`: el estado de una iniciativa, en su ficha (`estado:` y `estado_desde:`), sin commitear.
 *  `cambio`: false si ya estaba en ese estado (contando sus sinónimos), y no se escribió. */
export const estadoIniciativa = async (ruta: string, estado: string) =>
    await aServe<{ ruta: string; archivo: string; estado: string; estado_desde: string; antes: string; cambio: boolean }>(
        'POST', '/proyectos/estado', 15000, { ruta, estado });

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
export interface JsonBloque { clave: string; nombre: string; color: string; tecla?: string; dentro?: string }

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
/** La pantalla de configuración de un módulo (`[configurar]`): una página, casi siempre un lienzo. */
export async function configurarModulo(nombre: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/configurar/${encodeURIComponent(nombre)}`, 90000);
}

export async function bloque(clave: string): Promise<Respuesta<JsonPagina>> {
    return await deServe<JsonPagina>(`/bloques/${encodeURIComponent(clave)}`, 90000);
}

/** Una pestaña de proveedor (un feed): su tecla y cómo se ve su ficha (`vista`: «lectura», o vacío, la de una tarea). */
export interface JsonPestana { nombre: string; tecla: string; vista?: string }
/** La configuración resuelta (`/config`). */
export type JsonConfig = {
    calendario: JsonCalendario; agente: JsonAgenteConfig; hilos: { directorios: string[]; tope: number };
    atajos?: JsonAtajo[]; secciones?: JsonSeccion[]; apps?: JsonApp[];
    /** lo que dejan las skills por día; `pasadas`, el esquema si cada día es una lista de pasadas (la línea del pulso) */
    resultados?: { clave: string; nombre: string; en: string; pasadas: string }[];
    /** las pestañas del dashboard: su orden y las que no se muestran (`[dashboard]`) */
    dashboard?: { orden: string[]; ocultas: string[] };
    /** los módulos instalados (`[modulos]`) y lo que aporta cada uno */
    modulos?: { nombre: string; carpeta: string; descripcion: string; aporta: string[]; configurar?: boolean }[]; remotos?: JsonRemoto[];
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
    /** la instrucción: a quién va de entrada lo que manda una pestaña (`[instruccion] destino`, y `a`, el nombre que lo
     *  elige en la ventana) y `procesar`, la línea que le llega con un contexto libre y nada pedido */
    instruccion?: { destino?: string; a?: string; procesar?: string };
    /** las partes de la vida (`[mundos]`), en su orden: su color ya resuelto, su horario (los días de 0, domingo, a 6;
     *  los minutos del día) y su tema (""; el del modo); `mundos_fuera`, el que rige fuera de todo horario ("" ambos) */
    mundos?: JsonMundo[]; mundos_fuera?: string;
    /** los colores propios de cada tema en esta máquina (`[temas.<tema>]`): tema → {tinta: #rrggbb}; solo los que cambian
     *  algo (un telar de antes no lo manda) */
    temas?: Record<string, Record<string, string>>;
};
export interface JsonMundo {
    nombre: string; areas: string[]; rutas: string[]; etiquetas: string[]; color: string;
    horario: { texto: string; dias: number[]; desde: number; hasta: number }[];
    /** los colores de la página mientras rige (componentes/temas.ts); "" o sin él (un telar de antes), los del modo */
    tema?: string;
    /** los modos que tiene, en su orden (el primero es al que entra la página); vacío o sin él, todos */
    modos?: string[];
    /** el dibujo animado de su tarjeta en la ventana de mundos (componentes/arte.ts); "" o sin él, el que le toca */
    arte?: string;
}
export async function config(): Promise<Respuesta<JsonConfig>> {
    return await deServe<JsonConfig>('/config', 20000);
}

/** `telar encargar <agente> "…"`: pedirle algo a un agente residente, viva donde viva. */
export const encargar = async (agente: string, texto: string) =>
    await aServe<{ hilo?: string; estado?: string; id?: string }>('POST', '/encargos', 30000, { agente, texto });

/** Un grupo propio en la lista de hilos (`[secciones.x]`). `hilos`: nombres exactos, o
 *  prefijos si terminan en `*`. `home`: si declara una página. */
/** `grupo: 'agentes'` es un agente residente: va bajo la cabecera «Agentes», con su home armado por telar. */
export interface JsonSeccion {
    clave: string; nombre: string; hilos: string[]; home: boolean; grupo?: string;
    /** la de un agente: siempre, a-pedido o no (con siempre y a-pedido, lo que le llega por el bus lo abre si está
     *  cerrado y lo despierta si duerme). Un telar de antes no la manda */
    presencia?: 'siempre' | 'a-pedido' | 'no';
    /** la de un agente, con `[mundos]`: su mundo (el de su agente.toml, la etiqueta de su hilo o su carpeta; "" sin
     *  clasificar). Sin `[mundos]`, o un telar de antes, no viene */
    mundo?: string;
    /** la de un agente, con `[mundos]`: qué pasa con él con otro mundo puesto (su agente.toml; sin él, al-final) */
    fuera_de_su_mundo?: FueraDeSuMundo;
    /** la de un agente que vive en otra máquina y cuya carpeta todavía no está en esta (una raíz atrasada): esa máquina,
     *  que lo trae en su foto. Sin casa aquí (`home` false); su hilo se abre allá */
    maquina?: string;
}

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
     *  el mensaje va al hilo donde se trabaja la tarea (el de su proyecto, o el del agente de lo sin proyecto) */
    mensaje?: string; nombre_hilo?: string; al_hilo?: boolean;
    /** solo su ícono (un nombre de web/iconos.ts), en la barra de la ficha, con `ayuda` al pasar el mouse */
    icono?: string; solo_icono?: boolean; ayuda?: string;
}
export interface JsonPagina {
    titulo: string; subtitulo?: string;
    /** la de la entidad que muestra (la ficha de una tarea del tipo: `tarea:T84`) */
    direccion?: string;
    /** la de un bloque: algo nuevo que pide mirarlo («3 chats sin leer»), un punto en su fila del dashboard; "" o sin
     *  el campo, nada. Con el campo (aunque vacío), el bloque se relee solo cada tanto para tenerlo al día */
    aviso?: string;
    /** la versión de lo que muestra (la ficha de una tarea del tipo): se devuelve con una acción, y si la
     *  tarea cambió desde entonces, la acción no se hace */
    version?: string;
    bloques: { titulo?: string; texto?: string; items?: JsonPaginaItem[]; lienzo?: JsonLienzo; marco?: JsonMarco;
               destacado?: boolean; color?: string }[];
    acciones?: JsonAccionPagina[];
    /** la ficha de una lectura (una pestaña con `vista = "lectura"`, vistas/dashboard/leer.ts): sus temas (con `nota`, la
     *  ruta de la nota de ese tema, que se abre al lado), de dónde viene, su fecha y lo que ya se respondió */
    temas?: (string | { nombre: string; nota?: string })[];
    fuente?: string; fecha?: string; estado?: string;
    /** las relaciones que la lectura propone para el grafo (`elegida`: null sin decidir) y el vocabulario de sus tipos */
    conexiones?: { nota: string; titulo?: string; tipo: string; porque?: string; ancla?: string; elegida?: boolean | null }[];
    tipos?: JsonTipoArista[];
    /** desde cuándo se está volviendo a procesar ("" si no): la ficha se relee sola hasta que termina */
    procesando?: string;
}

/** Un tipo de arista del grafo: qué es (`que`), en qué se distingue del más cercano, su grupo y su color. */
export interface JsonTipoArista { tipo: string; que?: string; distingue?: string; grupo?: string; color?: string }

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
/** Correr la acción `n` de la ficha de una tarea; `version`, la de la ficha que se miraba (si cambió, no se hace). Una
 *  que lleva su mensaje a un hilo (`al_hilo`) va al de la tarea; a otro, por la instrucción (web/instruccion.ts). */
export async function accionTarea(id: string, proveedor: string, n: number, texto = '', version = '', conexiones?: string): Promise<Respuesta<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>> {
    return await aServe<{ tipo: string; hecho: string; enlace?: string; salida?: string; hilo?: string }>('POST', `/tareas/${encodeURIComponent(id)}/accion`, 40000,
        { proveedor, n, texto, ...(version ? { version } : {}), ...(conexiones !== undefined ? { conexiones: JSON.parse(conexiones) as unknown } : {}) });
}

/** Una línea de la historia de una tarea (`telar tipo tarea ver --json`): cuándo, de qué clase (creada, nota, avance,
 *  respuesta, mover, edita…) y lo que dice. */
export interface JsonCambio { fecha: string; hora?: string; tipo: string; texto: string }

/** Una tarea entera, como la da `GET /tipos/tarea/<id>` (telar.tipos.tarea): el contexto, la historia, de dónde salió y
 *  dónde se trabaja, con qué se conecta y su proyecto. Lo que falta, no viene o viene vacío. */
export interface JsonTarea {
    id: string; titulo: string; estado: string; direccion?: string; version?: string;
    prioridad?: number; vence?: string; tamano?: string; dueno?: string; espera?: string; avance?: string;
    proyecto?: string; area?: string; etiquetas?: string[]; origen?: string; trabajo?: string; creada?: string;
    /** de qué se trata y en qué va: un párrafo, o vacío */
    contexto?: string;
    /** «- `bloquea` [T276](T276.md) · por qué», tal cual en su archivo */
    conexiones?: string[];
    historia?: JsonCambio[];
}

/** Una tarea entera por su número (sin `tarea:` ni `@máquina`), aquí o en la máquina que las escribe. */
export async function tareaEntera(id: string): Promise<Respuesta<JsonTarea>> {
    return await deServe<JsonTarea>(`/tipos/tarea/${encodeURIComponent(id)}`, 20000);
}

/** Las tareas abiertas de un proyecto (su ruta), enteras. */
export async function tareasDeProyecto(ruta: string): Promise<Respuesta<{ tareas: JsonTarea[]; fallas?: Record<string, string> }>> {
    return await deServe<{ tareas: JsonTarea[]; fallas?: Record<string, string> }>(`/tipos/tarea?proyecto=${encodeURIComponent(ruta)}`, 30000);
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

/** Algo que espera una decisión de la persona (`telar esperas --json`, docs/contratos.md): un permiso o una pregunta de
 *  un hilo, el `avance` de una tarea, un mensaje retenido, lo que declare un módulo. */
export interface JsonEspera {
    direccion: string; tipo: string;
    /** `permiso`, `pregunta`, `avance:<marca>`, `retenido` o la de un módulo */
    clase: string;
    /** fecha y hora (`2026-11-17T09:30:00`) o solo la fecha; vacío si no se sabe */
    desde: string;
    titulo: string; resumen: string;
    /** dónde se ve o se contesta: el primero es el principal (su hilo, su proyecto) */
    enlaces: string[];
    maquina?: string;
    campos?: Record<string, unknown>;
    /** su mundo de `[mundos]`; "" sin clasificar; sin `[mundos]`, no viene */
    mundo?: string;
    /** el agente residente del que es (el de su hilo, el que pregunta, el de la carpeta de su proyecto si declara su
     *  mundo); "" o sin él, de ninguno. Lo de uno que pide esconderse no se nombra fuera de su mundo (web/mundo.ts, `deAgenteAjeno`) */
    agente?: string;
}
/** Una tarea que la persona contestó y que espera al agente (`telar esperas --json`, `contestadas`): su última
 *  `[respuesta]` vino después de la última marca del agente, y no tiene un `avance` pendiente. */
export interface JsonContestada {
    direccion: string; titulo: string;
    /** cuándo contestó (la última `[respuesta]`), como `desde` */
    cuando: string;
    /** lo que contestó, en una línea (sin los avisos de «revisar ya») */
    respuesta: string;
    /** cuándo se le avisó al agente que la atendiera ya (un «prompt: …»: «hazte cargo ya», «revisar ya»); "" si no */
    encargada?: string;
    enlaces: string[];
    mundo?: string;
}
export interface JsonEsperas {
    esperas: JsonEspera[]; fallas?: Record<string, string>; mundos?: string[];
    /** las tareas contestadas que esperan al agente (no esperan a la persona: no son esperas) */
    contestadas?: JsonContestada[];
}

/** Lo que espera a la persona, de lo más viejo a lo más nuevo (`GET /esperas`); con `tipos`, solo los de esos tipos. */
/** Un aviso que viene de un archivo (`[avisos.<clave>]`, telar.avisos), de los que hay que decir: `aviso` o `mal`, de
 *  la última hora. `maquina`, "" si el archivo vive aquí; `informe`, un `.md` para abrir en el visor ("" si no hay);
 *  `problemas`, los ids de lo que está mal (null si el archivo no los trae); `visto`, si la persona ya lo dio por visto
 *  y sigue siendo el mismo. */
export interface JsonAvisoArchivo {
    clave: string; maquina: string; nivel: 'aviso' | 'mal'; linea: string; fecha: string; informe: string;
    sugerencias: number | null; problemas?: string[] | null; visto?: boolean;
}
/** `GET /avisos`: los avisos de los archivos declarados, de esta máquina y de las otras. */
export const avisosDeArchivos = async () =>
    await deServe<{ avisos: JsonAvisoArchivo[]; fallas: Record<string, string> }>('/avisos', 30000);
/** `POST /avisos/visto`: dar por visto el aviso de una fuente, como se vio (su nivel y sus problemas), en la máquina
 *  donde vive su archivo. */
export const avisoVisto = async (clave: string, nivel: string, problemas: string[] | null | undefined) =>
    await aServe<{ ok: boolean; error?: string }>('POST', '/avisos/visto', 20000, { clave, nivel, problemas: problemas ?? null });

export async function esperas(tipos: string[] = []): Promise<Respuesta<JsonEsperas>> {
    return await deServe<JsonEsperas>(`/esperas${tipos.length ? `?${tipos.map(t => `tipo=${encodeURIComponent(t)}`).join('&')}` : ''}`, 30000);
}

/** Una cosa que calza en una búsqueda sobre todo junto (`telar buscar`): su dirección (o lo que la agarra), su título,
 *  dónde vive, cuándo, su estado, si ya pasó y su mundo. */
export interface JsonHallado {
    fuente: string; direccion: string; id: string; titulo: string; donde: string; cuando: string; estado: string;
    pasada: boolean; mundo: string;
    /** el agente residente del que es (un hilo suyo, lo que espera de él, lo de su carpeta si declara su mundo); "" o sin
     *  él, de ninguno. Lo de uno que pide esconderse no sale en ⌘K ni en Todo fuera de su mundo (web/mundo.ts, `deAgenteAjeno`) */
    agente?: string;
    /** de la fila de un bloque: su `bloque`, y su `mensaje` y su `nombre` si los trae; de un objeto de un módulo que es
     *  un documento (`campos.ruta_abs`), su `ruta_abs`: se abre en el visor */
    datos?: Record<string, string>;
}
export interface JsonBusqueda {
    q: string; mundos: string[];
    /** el mundo cuyo contenido va primero en cada fuente, antes del tope ('' ninguno) */
    primero?: string;
    fuentes: {
        clave: string; nombre: string; total: number; hallados: JsonHallado[]; falla: string;
        /** no terminó de leerse a tiempo: trae lo de antes (`leida`) o nada, y sigue leyéndose en telar */
        tarde?: boolean;
        /** cuándo se leyó lo que trae (ISO, hora local); '' si nunca */
        leida?: string;
    }[];
}
/** Buscar sobre todo junto (`GET /buscar`): lo que espera, las tareas, las casillas, los hilos, los proyectos, los
 *  objetos de los tipos de un módulo que los lista (`objeto:<tipo>`) y los bloques. Sin filtrar por mundo: Todo los
 *  ordena, y con `primero` (su mundo puesto) lo de ese mundo entra primero al tope de cada fuente. Contesta en lo que
 *  dura su tope (segundo y medio): la fuente lenta viene `tarde`, y la búsqueda siguiente la trae. `releer`: todas de
 *  nuevo, aunque lo guardado valga. `fuentes`: solo esas (⌘K pide los proyectos, las tareas y los documentos,
 *  `objeto:doc`); sin ninguna, todas. `siHay`: una de `fuentes` que esa máquina no tiene se deja fuera, en vez de ser un
 *  error que tumba a las demás. */
export async function buscar(q: string, limite = 30, releer = false, primero = '', fuentes: readonly string[] = [],
    siHay = false): Promise<Respuesta<JsonBusqueda>> {
    return await deServe<JsonBusqueda>(`/buscar?q=${encodeURIComponent(q)}&limite=${limite}${releer ? '&releer=true' : ''}`
        + (primero ? `&primero=${encodeURIComponent(primero)}` : '')
        + fuentes.map(f => `&fuente=${encodeURIComponent(f)}`).join('') + (siHay ? '&si_hay=true' : ''), 30000);
}

/** Que telar empiece a leer lo que busca (`POST /buscar/preparar`), sin esperar: mientras se escribe, se lee. */
export async function prepararBusqueda(): Promise<Respuesta<{ leyendo: string[] }>> {
    return await aServe<{ leyendo: string[] }>('POST', '/buscar/preparar', 5000);
}

/** Lo que dice telar al contestar la pregunta en vivo de un hilo: si el agente la tomó, o si ya la habían contestado en
 *  su terminal (`por: "terminal"`). */
export interface JsonRespondido { ok?: boolean; tomada?: boolean; por?: string }

/** Contestar la pregunta en vivo de un hilo (`POST /hilos/responder`): `respuestas` es {pregunta: respuesta}. */
export async function responderPregunta(hilo: string, maquina: string, id: string, respuestas: Record<string, string>): Promise<Respuesta<JsonRespondido>> {
    return await aServe<JsonRespondido>('POST', '/hilos/responder', 30000, { hilo, maquina, id, respuestas });
}

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
    /** el agente residente al que se le encarga (con `mensaje`); vacío, un hilo nuevo cada vez */
    agente?: string;
    /** con un hilo nuevo cada vez: el hilo del que cuelga cada uno (el de un agente) */
    padre?: string;
    /** los procesos cuyo resultado usa (declarado), y los que nombra pero no existen */
    despues?: string[]; despues_falta?: string[];
    /** a quién le llega: un agente (deducido de un comando que encarga, si `inferido`), un hilo nuevo o nadie */
    destino?: { tipo: 'agente' | 'hilo' | 'comando'; agente: string; inferido: boolean };
    /** con `calendario`: sus corridas en los días pedidos */
    corridas?: JsonCorrida[];
}
/** Una corrida de un proceso, en la zona de los periódicos: su día y su minuto (así la página no cuenta zonas). */
export interface JsonCorrida {
    dia: string; min: number; en: string;
    estado: 'bien' | 'corrio' | 'fallo' | 'saltado' | 'corriendo' | 'falto' | 'sin-registro' | 'proxima' | 'pausado';
    resultado?: string; hilo?: string;
    /** fuera de su horario: alguien lo corrió a mano */
    manual?: boolean;
}
/** Un agente residente de la máquina de los periódicos: a quién se le puede encargar uno. */
export interface JsonAgentePer { clave: string; nombre: string; carpeta: string; icono: string }
export interface JsonPeriodicos { maquina: string; archivo: string; zona: string; procesos: JsonPeriodico[]; agentes?: JsonAgentePer[] }
/** `telar periodicos calendario`: lo mismo, con las corridas de `dias` días desde `desde`, y la hora de allá. */
export interface JsonCalendarioPer extends JsonPeriodicos { desde: string; dias: number; ahora: string }

/** Un verbo de `telar periodicos`, por la API (que lo pide a la máquina donde viven, por el bus). */
async function periodicosPor<T>(argv: string[], timeout: number): Promise<Respuesta<T>> {
    return await aServe<T>('POST', '/periodicos', timeout, { argv });
}
export const periodicos = async () => await deServe<JsonPeriodicos>('/periodicos', 30000);
export const periodicosCalendario = (desde: string, dias: number) =>
    periodicosPor<JsonCalendarioPer>(['calendario', ...(desde ? ['--desde', desde] : []), '--dias', String(dias)], 30000);
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

/** Despertar un hilo (`POST /despertar`, telar.dormir, telar.alcance): el de aquí en su ventana; el de otra máquina
 *  (`maquina`), pidiéndoselo a ella. `hecho` vacío si no dormía. Con `cola` (un botón), como esté (uno cerrado se retoma)
 *  y, si su máquina está fuera de línea, en cola hasta que vuelva (`en_cola`); `texto`, su primer mensaje. */
export async function despertar(hilo: string, maquina = '', o: { cola?: boolean; texto?: string } = {}):
    Promise<Respuesta<{ hecho: string; en_cola?: boolean; aviso?: string }>> {
    return await aServe<{ hecho: string; en_cola?: boolean; aviso?: string }>('POST', '/despertar', 60000,
        { hilo, maquina, ...(o.cola ? { cola: true } : {}), ...(o.texto ? { texto: o.texto } : {}) });
}

/** Lo que muestra esta página (`POST /mirando`): lo que se mira no se duerme (telar.dormir). */
export async function mirando(pagina: string, hilo: string, maquina = ''): Promise<Respuesta<{ ok: boolean }>> {
    return await aServe<{ ok: boolean }>('POST', '/mirando', 10000, { pagina, hilo, maquina });
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

/** Una instrucción (`telar actuar`, docs/propuestas/instruccion.md): lo que se le pide a un hilo o a un agente, con el
 *  contexto de una entidad. `a` vacío es su hilo; `nuevo`, uno nuevo para ella; sin `direccion` ni `fila`, solo lo
 *  pedido, a quien diga `a`. `fila`: la de un pendiente que la pantalla ya tiene (ahorra buscarlo). */
export interface PedidoInstruccion {
    direccion?: string; a?: string; nuevo?: boolean; skill?: string; nota?: string; escribir?: boolean; fila?: FilaConocida;
    /** sin entidad y con `nuevo`: cómo se llama el hilo nuevo */
    nombre?: string;
    /** un texto que va entero, con sus líneas, debajo de lo pedido (lo que mostraba la pestaña de un módulo) */
    contexto?: ContextoLibre;
}
/** Un contexto que no es una entidad: un texto (un chat), cómo se llama y de dónde viene, en palabras. */
export interface ContextoLibre { texto: string; titulo?: string; origen?: string }
/** La fila de un pendiente, entera o lo que se sepa de ella (su ref, al menos). */
export type FilaConocida = Partial<JsonFila> & { ref: string };
/** `como`: encargado, enviado, escrito (sin mandar), abierto (un hilo nuevo que arrancó con ella) o «por el bus»;
 *  `aviso`, lo que no salió aunque se mandó (no quedó en la historia de la tarea) */
export interface JsonActuado { destino: string; como: string; prompt: string; maquina?: string; aviso?: string }
export async function actuar(p: PedidoInstruccion): Promise<Respuesta<JsonActuado>> {
    return await aServe<JsonActuado>('POST', '/actuar', 90000, p);
}
/** Adónde iría una instrucción sobre una entidad sin elegir a quién (su hilo), y su contexto (`telar actuar --donde`).
 *  `como`: hilo, dormido (se retoma), abrir (no tiene: se le abre uno), agente (se le encarga) o bus (en otra máquina);
 *  vacío, con `falta`, si no tiene hilo propio. */
export interface JsonAdonde {
    destino: string; como: string; maquina: string; carpeta: string; nuevo: boolean; contexto: string; falta: string; titulo: string;
    /** la entidad es un hilo o un agente: a sí mismo no se le manda su contexto */
    propio: boolean;
}
export const adonde = async (direccion: string, fila?: FilaConocida) =>
    await aServe<JsonAdonde>('POST', '/actuar/adonde', 60000, { direccion, ...(fila ? { fila } : {}) });

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
    persona?: string; saltos?: number; estado?: 'enviado' | 'retenido' | 'descartado'; motivo?: string;
    /** si se descartó: cuándo y quién */
    descartado?: string; descartado_por?: string;
}
/** Los últimos mensajes entre hilos, de todas las máquinas. Sin bus, error (y la pestaña no los muestra). */
export const mensajesBus = async (n = 60) => await deServe<{ mensajes: JsonMensajeBus[] }>(`/mensajes?n=${n}`, 30000);
/** `telar mensaje --soltar <id>`: la persona deja pasar un mensaje retenido. */
export const soltarMensaje = async (id: string) =>
    await aServe<{ id: string; para: string }>('POST', `/mensajes/${encodeURIComponent(id)}/soltar`, 30000);
/** `telar mensaje --descartar <id>`: la persona decide que un mensaje retenido no sale. Queda como descartado en el
 *  registro, y a quien lo mandó le llega un aviso (`aviso`, su id; `sin_aviso`, por qué no salió). */
export const descartarMensaje = async (id: string) =>
    await aServe<{ id: string; para: string; de: string; aviso?: string; sin_aviso?: string }>('POST', `/mensajes/${encodeURIComponent(id)}/descartar`, 30000);

/** Un módulo instalado (`GET /modulos`): activo o apagado, su carpeta y de dónde vino. */
export interface JsonModuloInstalado {
    nombre: string; activo: boolean; carpeta: string; descripcion: string; aporta: string[];
    fuente: string; version: string; ref: string; catalogo: string; enlazado: boolean; instalado: string;
    a_mano: boolean; pide: string[]; confianza: string; nueva: string;
    /** si trae pantalla de configuración (`[configurar]`): `configurarModulo` la pide */
    configurar?: boolean;
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
/** Una consulta a un módulo (`GET /modulos/<módulo>/<verbo>`: una orden suya con `consulta = true`), con el JSON que da.
 *  Sin el módulo aquí, `estado` 404. */
export const consultaModulo = async <T>(modulo: string, verbo: string) =>
    await deServe<T>(`/modulos/${encodeURIComponent(modulo)}/${encodeURIComponent(verbo)}`, 60000);
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
    /** el mundo de `[mundos]` que declara su agente.toml ("" o sin él: va por su carpeta) */
    mundo?: string;
    politica?: { permite?: string[]; pregunta?: string[]; niega?: string[] };
}
/** Un encargo, en corto (telar.encargo): su estado va pedido → corriendo → hecho | falló | cancelado. */
export interface JsonEncargoCorto { id: string; estado: string; texto: string; de?: string; creado?: string; actualizado?: string; resultado?: string }
/** Un agente en la vista de agentes (`GET /agentes`): su definición y su estado donde vive. */
export interface JsonEstadoAgente {
    agente: JsonAgente; maquina: string; aqui: boolean; vivo: boolean; atencion: string;
    conversacion: { id: string; peso: number; tope: number } | null; rotacion: string;
    relevo: { cuando: string } | null; encargos: JsonEncargoCorto[]; sin_noticias?: boolean;
    /** su máquina respondió sin él: su carpeta está solo en esta. El texto dice dónde debería vivir y qué hacer */
    solo_aqui?: string;
    /** los hilos que abrió (no los suyos): para verlos, o archivarlos de una vez */
    abrio?: { hilo: string; vivo: boolean; archivado: boolean; cuando: string }[];
    /** su mundo de `[mundos]`, por su carpeta; "" sin clasificar; sin `[mundos]`, no viene */
    mundo?: string;
}
export const agentes = async () => await deServe<{ agentes: JsonEstadoAgente[]; problemas: string[] }>('/agentes', 40000);
/** Rotar ya la conversación de un agente, con relevo (`POST /agentes/rotar`). */
export const rotarAgente = async (hilo: string, maquina = '') =>
    await aServe<{ hecho?: string }>('POST', '/agentes/rotar', 30000, { hilo, maquina });
/** Eliminar a un agente (`POST /agentes/eliminar`), en la máquina donde vive: sus hilos al archivo, su carpeta a
 *  `_eliminados`. Nada se borra: `restaurarAgente` lo trae de vuelta. */
export const eliminarAgente = async (agente: string, maquina = '') =>
    await aServe<{ ok: boolean; clave: string; nombre: string; carpeta: string; archivados: string[]; sin_archivar: string[] }>(
        'POST', '/agentes/eliminar', 120000, { agente, maquina });
/** Abrir el hilo de un agente, retomando su conversación (`POST /agentes/abrir`), donde viva. Si quedó con una shell
 *  (se abrió antes de elegir el motor), la reemplaza. 409 si falta el motor. */
export const abrirAgente = async (agente: string, maquina = '') =>
    await aServe<{ ok: boolean; hilo: string; hecho: string }>('POST', '/agentes/abrir', 60000, { agente, maquina });
/** `telar config`, `[agente] nombre`: con qué se abren los hilos y los agentes (claude-code o ninguno). */
export const motorAgentes = (valor: string) => ajusteConfig('motor', valor);
/** Los agentes eliminados de esta máquina, que se pueden traer de vuelta. */
export const agentesEliminados = async () =>
    await deServe<{ eliminados: { clave: string; nombre: string; carpeta: string }[] }>('/agentes/eliminados', 15000);
export const restaurarAgente = async (agente: string) =>
    await aServe<{ codigo: number; salida: string; error: string }>('POST', '/agentes/restaurar', 30000, { agente });
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

/** Los códigos que nombra un hilo (`GET /codigos`, docs/contratos.md «telar codigos»): los que define su carpeta y
 *  salen de su archivo (`codigos`, por clase), y los que nombra su conversación (`conversacion`, el último primero). */
export interface JsonCodigo {
    codigo: string; clase: string; titulo: string; archivo: string; linea: number; forma: string;
    definiciones: number; nombrado_en: number; resumen?: string; en_conversacion?: number;
}
export interface JsonCodigoNombrado {
    codigo: string; tipo: 'codigo' | 'tarea'; veces: number; ultimo: number; extracto: string;
    titulo?: string; estado?: string; direccion?: string; archivo?: string; linea?: number;
}
export interface JsonClaseCodigos { prefijo: string; nombre: string; archivo: string; cuantos: number }
export interface JsonDefinicion {
    codigo: string; archivo: string; linea: number; forma: string; titulo: string; seccion: string;
    texto?: string; campos?: Record<string, string>;
}
export interface JsonDetalleCodigo {
    codigo: string; tipo: 'codigo' | 'tarea'; definiciones?: JsonDefinicion[];
    nombrado_en?: { archivo: string; lineas: number[] }[];
    conversacion?: { veces: number; ultimo: number; extracto: string };
    direccion?: string; titulo?: string; estado?: string;
}
export interface JsonCodigos {
    hilo: string; maquina: string; carpeta: string; archivos: number; truncado: boolean;
    clases: JsonClaseCodigos[]; codigos: JsonCodigo[]; conversacion: JsonCodigoNombrado[];
    tareas_en: string; aviso: string; detalle?: JsonDetalleCodigo;
    /** las ramas que suman a la carpeta, y los documentos que vienen de una: su clave (`README.md@rama` si la carpeta
     *  también lo tiene) → su ruta, su rama y su archivo */
    ramas?: string[]; de_rama?: Record<string, { ruta: string; rama: string; archivo: string }>;
}
export const codigos = async (hilo: string, maquina = '', codigo = '') =>
    await deServe<JsonCodigos>(`/codigos?hilo=${encodeURIComponent(hilo)}${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`
        + (codigo ? `&codigo=${encodeURIComponent(codigo)}` : ''), 30000);

/** Lo que carga el contexto de un hilo (`GET /contexto`, docs/contratos.md «telar hilo contexto»): cuánto pesa ahora y
 *  desde cuándo, una cuenta por grupo (lo de Claude Code, lo que carga al empezar, al entrar a carpetas, lo que leyó,
 *  lo que se repite, lo de otros hilos y la conversación) y cada cosa con su ruta y su tamaño, en tokens. */
export interface JsonItemCarga {
    grupo: string; clase: string; nombre: string; ruta?: string; veces: number; tokens: number; caracteres?: number;
    primera?: string; ultima?: string;
    /** lo que una compactación ya resumió */
    antes?: { veces: number; tokens: number };
    /** por dónde llegó: Read, Bash, al compactar, cambió afuera */
    vias?: string[];
    /** no está en la conversación como texto: se dedujo de lo medido */
    deducido?: boolean;
}
export interface JsonGrupoCarga { clave: string; nombre: string; para: string; cuantos: number; tokens: number }
export interface JsonCarga {
    hilo: string; maquina: string; agente: string; conversacion: string; carpeta: string; casa: string;
    desde: { que: string; hora: string; como?: string; antes?: number; despues?: number };
    compactaciones: number; total: number; medido: boolean; hora: string; modelo: string; al_empezar: number | null;
    caracteres_por_token: number; grupos: JsonGrupoCarga[]; items: JsonItemCarga[]; truncado: boolean;
}
export const carga = async (hilo: string, maquina = '') =>
    await deServe<JsonCarga>(`/contexto?hilo=${encodeURIComponent(hilo)}${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`, 30000);

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
    modos: { clave: string; nombre: string; valores: Record<string, string | number>; de_fabrica: boolean; cambiado: boolean;
        /** sobre cuál de las cuatro se arma; lo que dice su tabla y a qué vuelve cada uno sin ella */
        base?: string; propios?: string[]; heredados?: Record<string, string | number>; origenes?: Record<string, string> }[];
}
export const modos = async () => await deServe<JsonModos>('/modos', 15000);
/** Crear o cambiar un modo: `[modos.<clave>]` con esos valores (la tabla entera). De uno propio, `base`: sobre cuál de
 *  los cuatro se arma (sin ella, táctica). */
export const guardarModo = async (clave: string, valores: Record<string, string | number>, nombre = '', base = '') =>
    await aServe<{ ok: boolean; modos: JsonModos['modos'] }>('PUT', `/modos/${encodeURIComponent(clave)}`, 15000, { valores, nombre, base });
/** Cambiar solo algunos ajustes de un modo (qué agentes y qué pestañas se ven): esas líneas de `[modos.<clave>]`, lo demás
 *  lo sigue heredando; null quita la línea. */
export const ajustarModo = async (clave: string, valores: Record<string, string | number | null>) =>
    await aServe<{ ok: boolean; modos: JsonModos['modos'] }>('PATCH', `/modos/${encodeURIComponent(clave)}`, 15000, { valores });
/** Un parámetro de los glifos (`GET /glifos`, telar.glifos): un rango (mínimo, máximo, paso) u opciones. */
export interface ParamGlifo { clave: string; grupo: string; nombre: string; base: string | number; ayuda: string;
    opciones?: string[]; minimo?: number; maximo?: number; paso?: number }
/** Los estilos de los glifos, cada uno con todos sus valores, y el catálogo de parámetros. */
export interface JsonGlifos { catalogo: ParamGlifo[]; estilos: Record<string, Record<string, string | number>> }
export const glifos = async () => await deServe<JsonGlifos>('/glifos', 15000);
/** Crear o cambiar un estilo: `[glifos.<estilo>]` con lo que difiere de fábrica. */
export const guardarEstilo = async (estilo: string, valores: Record<string, string | number>) =>
    await aServe<{ ok: boolean; estilos: JsonGlifos['estilos'] }>('PUT', `/glifos/${encodeURIComponent(estilo)}`, 15000, { valores });
/** Quitar `[glifos.<estilo>]`: uno propio desaparece; «base» vuelve a ser el de fábrica. */
export const borrarEstilo = async (estilo: string) =>
    await aServe<{ ok: boolean; estilos: JsonGlifos['estilos'] }>('DELETE', `/glifos/${encodeURIComponent(estilo)}`, 15000, {});
/** Quitar `[modos.<clave>]`: uno propio desaparece; uno de fábrica vuelve a ser el de fábrica. */
export const borrarModo = async (clave: string) =>
    await aServe<{ ok: boolean; modos: JsonModos['modos'] }>('DELETE', `/modos/${encodeURIComponent(clave)}`, 15000, {});

/** De qué mundo es un agente residente y qué lo pone ahí (telar.mundos.por_que_agente): una etiqueta de su hilo que
 *  un mundo declara (`por` «etiqueta») o la ruta declarada que calza con su carpeta (`por` «ruta», `valor` como se
 *  declaró); sin nada, `mundo` vacío: sin clasificar. */
export interface JsonAgenteMundo { clave: string; nombre: string; carpeta: string; mundo: string; por: '' | 'ruta' | 'etiqueta' | 'agente.toml'; valor: string;
    /** qué pasa con él con otro mundo puesto (su agente.toml); sin él, al-final */
    fuera_de_su_mundo?: FueraDeSuMundo }
/** Qué pasa con un agente residente con otro mundo puesto (`fuera_de_su_mundo` en su agente.toml, web/mundo.ts):
 *  al-final (el de fábrica: la barra no lo muestra; ⌘K, la vista de agentes y la instrucción, solo en el modo todo, al
 *  final), esconder (en ninguna parte, ni en todo; solo ⚙ lo nombra) o ver (en todos los mundos, como uno sin
 *  clasificar). */
export type FueraDeSuMundo = 'al-final' | 'esconder' | 'ver';
export const FUERAS: readonly FueraDeSuMundo[] = ['al-final', 'esconder', 'ver'];
/** Lo que muestra ⚙ mundos (`GET /mundos`): cada mundo con lo suyo y el color que declara (`color_propio`, "" si toma
 *  uno por orden), `fuera`, las tintas que puede llevar uno y de qué mundo es cada agente. */
/** Cómo decir la raíz en palabras: el nombre de su carpeta, sacado de uno de sus archivos (`<raiz>/.telar/temas.toml` → el
 *  nombre de `<raiz>`), para que cada persona vea la suya; «la raíz» sin archivo. Lo mismo que telar.temas.nombre_raiz. */
export function nombreRaiz(archivo: string | undefined): string {
    const partes = (archivo ?? '').split(/[\\/]+/).filter(Boolean);
    partes.pop();
    if (partes[partes.length - 1] === '.telar') partes.pop();
    return partes.pop() || 'la raíz';
}

/** Dónde vive algo de un mundo: en la raíz (`<raiz>/.telar/mundos.toml`, todas las máquinas), solo en esta máquina, o en ninguna. */
export type ViveMundo = 'raiz' | 'maquina' | '';
/** Dónde se pisan dos horarios (telar.horario.choques): los mundos, el día (0 domingo) y los minutos. */
export interface JsonChoque { mundos: string[]; dia: number; desde: number; hasta: number }
export interface JsonMundos {
    mundos: (JsonMundo & { color_propio: string; horario_vive?: ViveMundo })[]; fuera: string; tintas: string[]; agentes: JsonAgenteMundo[];
    /** de dónde sale `fuera`; el archivo de la raíz ("" sin raíz), por qué no se lee y lo suyo que esta máquina no aplica (un
     *  telar de antes no los manda) */
    fuera_vive?: ViveMundo;
    raiz?: string;
    error_raiz?: string;
    sobran_raiz?: string[];
    /** dónde se pisan los horarios, como están escritos */
    choques?: JsonChoque[];
    /** los temas que puede llevar uno (un telar de antes no los manda) */
    temas?: string[];
    /** los modos que puede tener uno: los de fábrica y los propios (un telar de antes no los manda) */
    modos?: { clave: string; nombre: string }[];
}
/** Lo que dice un mundo y se cambia desde ⚙ mundos: vacío (o null) quita la línea. */
export type CampoMundo = 'horario' | 'color' | 'tema' | 'arte' | 'modos' | 'etiquetas' | 'areas' | 'rutas';
export const mundos = async () => await deServe<JsonMundos>('/mundos', 15000);
/** Los artes de la raíz (`GET /arte`): cada `<raiz>/.telar/arte/<nombre>.txt`, con su texto tal cual (lo lee
 *  componentes/arte.ts, `leerArteTexto`); `carpeta`, dónde se buscan ("" sin raíz); `errores`, los que no se leyeron. */
export interface JsonArtes { carpeta: string; artes: { nombre: string; texto: string }[]; errores?: Record<string, string> }
export const artesDeLaRaiz = async () => await deServe<JsonArtes>('/arte', 10000);
/** Cambiar solo esos campos de `[mundos.<nombre>]`: lo demás queda como estaba (el horario, en la raíz). 422 con el porqué si
 *  un área, una ruta o una etiqueta ya es de otro mundo, o si el horario no se entiende o se pisa con el de otro. */
export const ajustarMundo = async (nombre: string, valores: Partial<Record<CampoMundo, string | string[] | null>>) =>
    await aServe<JsonMundos & { ok: boolean }>('PATCH', `/mundos/${encodeURIComponent(nombre)}`, 15000, { valores });
/** `[mundos] fuera`: el que rige fuera de todo horario ("" ambos). */
/** Qué pasa con un agente fuera de su mundo (`PUT /mundos/agentes/<clave>`): lo escribe en su agente.toml y lo sube. */
export const fueraDeSuMundo = async (clave: string, valor: FueraDeSuMundo) =>
    await aServe<JsonMundos & { ok: boolean }>('PUT', `/mundos/agentes/${encodeURIComponent(clave)}`, 15000, { fuera_de_su_mundo: valor });
export const fueraMundos = async (fuera: string) =>
    await aServe<JsonMundos & { ok: boolean }>('PATCH', '/mundos', 15000, { fuera });
/** Un mundo nuevo, vacío, después del último. */
export const crearMundo = async (nombre: string) =>
    await aServe<JsonMundos & { ok: boolean }>('PUT', `/mundos/${encodeURIComponent(nombre)}`, 15000, {});
/** Quitar `[mundos.<nombre>]` (y `fuera`, si era él): lo suyo queda sin clasificar. */
export const borrarMundo = async (nombre: string) =>
    await aServe<JsonMundos & { ok: boolean }>('DELETE', `/mundos/${encodeURIComponent(nombre)}`, 15000, {});

/** Lo que muestra ⚙ temas (`GET /temas`): cada tema que se puede elegir (los de fábrica y los propios), con sus colores
 *  propios (`propios`), de qué tema de fábrica parte uno propio (`base`) y si es de fábrica; y los colores que se pueden
 *  cambiar. */
export interface JsonTemas {
    /** `vive`: «raiz» (en `<raiz>/.telar/temas.toml`, todas las máquinas), «maquina» (solo esta), «mixto», "" (de fábrica);
     *  `en_raiz` y `en_maquina`, qué color está dónde (los de la máquina pisan los de la raíz) */
    temas: { clave: string; propios: Record<string, string>; base?: string; de_fabrica?: boolean;
        vive?: '' | 'raiz' | 'maquina' | 'mixto'; en_raiz?: string[]; en_maquina?: string[] }[];
    tintas: string[]; fondos?: string[];
    /** el archivo de la raíz ("" sin raíz: todo en la máquina), la configuración de la máquina, y por qué ese archivo no se lee */
    raiz?: string; maquina?: string; error_raiz?: string;
}
export const temasPropios = async () => await deServe<JsonTemas>('/temas', 15000);
/** Cambiar solo esos colores de `[temas.<tema>]`; null vuelve al de fábrica. 422 si un color no es `#rrggbb`. */
export const ajustarTema = async (tema: string, valores: Record<string, string | null>) =>
    await aServe<JsonTemas & { ok: boolean }>('PATCH', `/temas/${encodeURIComponent(tema)}`, 15000, { valores });
/** Un tema propio nuevo (`PUT /temas/<nombre>`), que parte de `base`. */
export const crearTema = async (nombre: string, base: string) =>
    await aServe<JsonTemas & { ok: boolean }>('PUT', `/temas/${encodeURIComponent(nombre)}`, 15000, { base });
/** Quitar `[temas.<tema>]`: uno de fábrica vuelve al de fábrica; uno propio se borra. */
export const temaDeFabrica = async (tema: string) =>
    await aServe<JsonTemas & { ok: boolean }>('DELETE', `/temas/${encodeURIComponent(tema)}`, 15000, {});

/** Lo que el equipo deja en tu bandeja (`telar equipo sugerencias --json`): subir una prioridad, o una tarea nueva. */
export interface JsonSugerencia {
    id: string; cuando: string; persona: string; tarea: string; titulo: string; prioridad: number | null;
    motivo: string; estado: string; nota: string;
    /** «prioridad»: sugiere subir una tarea · «tarea»: pide una tarea nueva (aceptarla la agrega) */
    tipo?: 'prioridad' | 'tarea'; vence?: string | null;
    /** si alguien (un agente) la está revisando */
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
/** Un hilo hijo de `padre` (`telar hilo hijo`): con su agente, en la carpeta del padre, y el encargo como primer mensaje. */
export async function hiloHijo(padre: string, nombre: string, texto: string, carpeta = ''): Promise<Salida> {
    const r = await aServe<{ codigo: number; salida: string; error: string }>('POST', '/hilo/hijo', 75000,
        { hilo: padre, valor: nombre, texto, carpeta });
    return r.error ? { ok: false, codigo: 1, out: '', err: r.error } : { ok: true, codigo: 0, out: r.datos?.salida ?? '', err: r.datos?.error ?? '' };
}

export async function hilo(verbo: string, hilo: string, valor?: string, extra: string[] = []): Promise<Salida> {
    if (!extra.every(x => x === '--cerrar' || x === '--con-hijos')) return { ok: false, codigo: 1, out: '', err: faltaEnLaApi(`telar hilo ${verbo} ${extra.join(' ')}`) };
    // un verbo sobre un hilo de otra máquina va a su dueño por el bus, que espera hasta 60 s: aquí, un poco más
    const r = await aServe<{ codigo: number; salida: string; error: string }>('POST', `/hilo/${encodeURIComponent(verbo)}`, 75000,
        { hilo, valor: valor ?? '', cerrar: extra.includes('--cerrar'), con_hijos: extra.includes('--con-hijos') });
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

