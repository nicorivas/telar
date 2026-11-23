// El mundo puesto: la parte de la vida que se mira (`[mundos]`: trabajo, personal…) o ambos. Es el segundo eje de la
// página, aparte del modo (docs/propuestas/orden-por-modos.md, paso 2): filtra la página entera (la barra, el número,
// las listas, el día) y se ve en la banda de la cabecera, su nombre en su color. Si declara un tema, la página lo lleva
// mientras rige (lo pone web/modos.ts, que escucha `alCambiar`).
//
// Cambia solo con el horario de cada mundo (lo declara la configuración; `telar config` lo entrega leído) y a mano. Lo
// elegido a mano dura hasta el próximo cambio del horario y después vuelve solo: así no se queda puesto sin querer. Lo
// que se eligió a mano es de este navegador, como el modo. El cálculo es puro (componentes/modos-mundos.ts,
// `mundoAhora`, con su prueba); aquí, el estado, el reloj y los oyentes.
//
// Lo sin clasificar (una cosa cuyo `mundo` es "") se ve en todos los mundos: esconderlo sería perder lo que espera sin
// que se note. Sin `[mundos]`, nada se filtra y la cabecera no muestra nada.

import * as cli from '../cli';
import { modelo } from '../modelo';
import { modosDelMundo, mundoAhora, type Mundo, type MundoPuesto } from '../componentes/modos-mundos';

const CLAVE = 'telar.mundo.a-mano';
const leerLocal = (): { mundo: string; desde: number } | null => {
    try {
        const v = JSON.parse(localStorage.getItem(CLAVE) ?? 'null') as { mundo?: unknown; desde?: unknown } | null;
        return v && typeof v.mundo === 'string' && typeof v.desde === 'number' ? { mundo: v.mundo, desde: v.desde } : null;
    } catch { return null; }
};
const guardarLocal = (v: { mundo: string; desde: number } | null) => {
    try { if (v) localStorage.setItem(CLAVE, JSON.stringify(v)); else localStorage.removeItem(CLAVE); } catch { /* sin almacén */ }
};

let mundos: Mundo[] = [];
/** si ya llegaron de la API (antes, no se sabe cuál rige: el tema espera) */
let recibidos = false;
let fuera = '';
let aMano = leerLocal();
let actual: MundoPuesto = { mundo: '', por: 'sin-horario' };
/** en todo, el mundo ordena y no esconde (lo pone web/modos.ts) */
let soloOrdena = false;
const oyentes = new Set<() => void>();

/** Si ya se sabe qué mundos hay (llegaron de la API, aunque sean ninguno). */
export const conocidos = (): boolean => recibidos;
/** Los mundos declarados, en su orden (vacío sin `[mundos]`). */
export const declarados = (): readonly Mundo[] => mundos;
/** El mundo que rige fuera de todo horario ("" ambos). */
export const deFuera = (): string => fuera;
/** Los modos que tiene el mundo puesto (con ambos, los de todos juntos); null: todos, o los mundos no se saben todavía. */
export const modos = (): string[] | null => (recibidos ? modosDelMundo(mundos, actual.mundo) : null);
/** El puesto ahora, y por qué (`mundo` vacío: ambos). */
export const puesto = (): MundoPuesto => actual;
/** El mundo puesto como objeto, o undefined con ambos. */
export const mundo = (): Mundo | undefined => mundos.find(m => m.clave === actual.mundo);

/** Si una cosa de ese mundo se ve con el puesto: lo suyo y lo sin clasificar (undefined o ""); con ambos, todo; y en
 *  todo (el modo), todo: ahí el mundo ordena y no esconde. */
export function seVe(de: string | undefined): boolean {
    return soloOrdena || enElPuesto(de);
}

/** Lo mismo, también en todo: lo que se ve sin buscarlo, la barra de hilos, obedece al mundo puesto en todos los modos
 *  (en todo, lo de otro mundo va a la fila plegada del final, «de personal 7»: ordenado al final, sin quedar a la vista
 *  de una pantalla compartida). */
export function enElPuesto(de: string | undefined): boolean {
    return !mundos.length || !actual.mundo || !de || de === actual.mundo;
}

/** Qué pasa con un agente residente con otro mundo puesto (`fuera_de_su_mundo` en su agente.toml, cli.FueraDeSuMundo):
 *  lo que trae `GET /mundos` (lo último escrito desde ⚙ mundos) y, si no, su sección de `telar config`; sin saberlo,
 *  al-final (el de fábrica). `clave`: la de su carpeta, con o sin `agente:`. */
export function fueraDe(clave: string | undefined): cli.FueraDeSuMundo {
    if (!clave) return 'al-final';
    const suya = clave.startsWith('agente:') ? clave : `agente:${clave}`;
    return delAgente(suya)?.fuera_de_su_mundo ?? modelo.secciones.find(s => s.clave === suya)?.fuera_de_su_mundo ?? 'al-final';
}

/** Si es de un agente residente (`agente`: su hilo o un hijo suyo, lo que espera de él, lo que vive en su carpeta si su
 *  agente.toml declara su mundo) que pide esconderse fuera de su mundo (`fuera_de_su_mundo = "esconder"`), con otro
 *  mundo puesto: eso no se nombra en ninguna parte (⌘K, Todo, «te esperan», Táctica, la instrucción, la franja), tampoco
 *  en el modo todo, donde lo demás de otro mundo va al final. Solo ⚙ (modos, mundos) lo nombra, para configurarlo. El
 *  caso: el Jardín (personal) con el trabajo puesto y la pantalla compartida. Con al-final o ver, lo suyo va como
 *  lo demás, por su mundo. */
export const deAgenteAjeno = (x: { agente?: string; mundo?: string }): boolean => !!x.agente && escondido(x.agente, x.mundo);

/** Si ese agente pide esconderse fuera de su mundo y lo suyo, de ese mundo, no es del puesto (también en todo). */
const escondido = (agente: string, de: string | undefined): boolean => fueraDe(agente) === 'esconder' && !enElPuesto(de);

/** Lo mismo para un hilo: el de un agente que pide esconderse, o un hijo suyo (cuelga de él, `padre`, aunque no trabaje
 *  en su carpeta), por su mundo. `hilos`: dónde buscar a sus padres (los de aquí y los de las fotos de las otras máquinas). */
export function hiloDeAgenteAjeno(h: { nombre: string; agente?: string; padre?: string; mundo?: string },
    hilos: readonly { nombre: string; agente?: string; padre?: string }[]): boolean {
    if (enElPuesto(h.mundo)) return false;
    const vistos = new Set<string>();
    for (let x: typeof hilos[number] | undefined = h; x && !vistos.has(x.nombre); x = x.padre ? hilos.find(y => y.nombre === x!.padre) : undefined) {
        if (x.agente) return escondido(x.agente, h.mundo);
        vistos.add(x.nombre);
    }
    return false;
}

/** El mundo que filtra ahora: el puesto, salvo con ambos o en todo (ahí no filtra ninguno: ""). */
export const filtrando = (): string => (soloOrdena || !mundos.length ? '' : actual.mundo);

/** Si el mundo filtra (lo de siempre) o solo ordena (en todo): lo pone el modo. Avisa si cambió. */
export function ordenarSolo(si: boolean): void {
    if (si === soloOrdena) return;
    soloOrdena = si;
    for (const f of oyentes) f();
}

export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => oyentes.delete(f);
}

/** Vuelve a calcular el puesto (con la hora de ahora) y avisa si cambió; con `siempre`, avisa igual. Lo de a mano que
 *  ya venció se olvida. */
function aplicar(siempre = false): void {
    const antes = JSON.stringify(actual);
    actual = mundos.length
        ? mundoAhora(mundos, new Date(), { fuera, aMano: aMano ? { mundo: aMano.mundo, desde: new Date(aMano.desde) } : undefined })
        : { mundo: '', por: 'sin-horario' };
    if (aMano && actual.por !== 'a-mano') { aMano = null; guardarLocal(null); }
    if (!siempre && JSON.stringify(actual) === antes) return;
    for (const f of oyentes) f();
}

/** Elegir uno a mano (`""`: ambos): dura hasta el próximo cambio del horario. */
export function poner(clave: string): void {
    if (clave && !mundos.some(m => m.clave === clave)) return;
    aMano = { mundo: clave, desde: Date.now() };
    guardarLocal(aMano);
    aplicar(true);
}

/** Soltar lo de a mano: rige el horario. */
export function volverAlHorario(): void {
    aMano = null;
    guardarLocal(null);
    aplicar(true);
}

/** El siguiente (⌥⇧0): cada mundo, después ambos, y de vuelta al horario. */
export function siguiente(): void {
    if (!mundos.length) return;
    const ciclo = [...mundos.map(m => m.clave), ''];
    if (actual.por === 'a-mano' && actual.mundo === '') { volverAlHorario(); return; }
    poner(ciclo[(ciclo.indexOf(actual.mundo) + 1) % ciclo.length]);
}

/** Los mundos de la configuración, como los da `telar config` (con su color y su horario ya leídos). */
export function recibir(cfg: Pick<cli.JsonConfig, 'mundos' | 'mundos_fuera'> | undefined): void {
    mundos = (cfg?.mundos ?? []).map(m => ({ clave: m.nombre, nombre: m.nombre, color: m.color, tema: m.tema ?? '',
        horario: (m.horario ?? []).map(t => ({ dias: t.dias, desde: t.desde, hasta: t.hasta })), modos: m.modos ?? [],
        arte: m.arte ?? '' }));
    fuera = cfg?.mundos_fuera ?? '';
    recibidos = true;
    // lo elegido a mano de un mundo que ya no se declara, no vale
    if (aMano?.mundo && !mundos.some(m => m.clave === aMano!.mundo)) { aMano = null; guardarLocal(null); }
    aplicar(true);
}

// ── lo que dice cada mundo, para verlo y cambiarlo (⚙ mundos, y el cruce de la grilla de ⚙ modos) ──

/** lo que dio `GET /mundos` la última vez: cada mundo con lo suyo, `fuera` y de qué mundo es cada agente */
let detalle: cli.JsonMundos | undefined;

/** Lo que dice cada mundo y de qué mundo es cada agente, si ya se leyó (`leerDetalle`). */
export const detalles = (): cli.JsonMundos | undefined => detalle;

/** El mundo de un agente residente (su carpeta o su dirección) y por qué; undefined si no se sabe. */
export const delAgente = (clave: string): cli.JsonAgenteMundo | undefined =>
    detalle?.agentes.find(a => a.clave === clave.replace(/^agente:/, ''));

/** Si un agente residente se ve con el mundo puesto: con hilos suyos abiertos (`deSusHilos`, el mundo de cada uno), si
 *  alguno se ve; sin ninguno, por el suyo (el de su agente.toml, la etiqueta de su hilo o su carpeta: el que trae su
 *  sección de `telar config` y, si no, `GET /mundos`; sin saberlo, se ve). Lo usan la barra, ⌘K, la instrucción y la
 *  vista de agentes. `ve`: con qué se mira cada mundo (`seVe`: en el modo todo, todo; la barra pasa `enElPuesto`, que
 *  obedece al mundo también en todo). Lo que diga el agente (`fueraDe`) manda: con «esconder», `enElPuesto` en todas
 *  (no sale ni en todo); con «ver», se ve en todos los mundos; con «al-final» (el de fábrica), `ve`. */
export function seVeAgente(a: { clave: string; mundo?: string }, deSusHilos: readonly (string | undefined)[] = [],
    ve: (de: string | undefined) => boolean = seVe): boolean {
    const fuera = fueraDe(a.clave);
    if (fuera === 'ver') return true;
    const mirar = fuera === 'esconder' ? enElPuesto : ve;
    if (deSusHilos.length) return deSusHilos.some(m => mirar(m));
    return mirar(a.mundo ?? delAgente(a.clave)?.mundo);
}

/** Los agentes residentes (sus secciones) que se nombran con el mundo puesto, por `seVeAgente` con sus hilos vivos: ⌘K
 *  (web/buscador-hilos.ts) y los destinos de la instrucción (web/instruccion.ts). En el modo todo, también los de otro
 *  mundo, salvo los que piden esconderse. */
export function agentesQueSeVen<T extends { clave: string; nombre: string; mundo?: string }>(agentes: readonly T[],
    hilos: readonly { nombre: string; vivo: boolean; archivado: boolean; mundo?: string }[]): T[] {
    return agentes.filter(a => seVeAgente(a, hilos.filter(h => h.nombre === a.nombre && h.vivo && !h.archivado).map(h => h.mundo)));
}

/** Lo que devolvió la API (`GET /mundos`, o una escritura): lo guarda y lo aplica (el color, el horario y `fuera`
 *  cambian el puesto al tiro). */
export function recibirDetalle(d: cli.JsonMundos): void {
    detalle = d;
    recibir({ mundos: d.mundos, mundos_fuera: d.fuera });
}

/** Leer lo que dice cada mundo (`GET /mundos`). Devuelve el error, o "". */
export async function leerDetalle(): Promise<string> {
    const r = await cli.mundos();
    if (!r.datos) return r.error ?? 'no se pudo';
    recibirDetalle(r.datos);
    return '';
}

/** Lo que devuelve una escritura: si salió, se toma y ""; si no, el porqué, y se vuelve a leer lo que dice el archivo
 *  (lo que no se escribió pudo chocar con algo cambiado por otro lado). */
async function escrito(p: Promise<cli.Respuesta<cli.JsonMundos>>): Promise<string> {
    const r = await p;
    if (!r.datos) { void leerDetalle(); return r.error ?? 'no se pudo'; }
    recibirDetalle(r.datos);
    return '';
}

/** Cambiar algunos campos de un mundo, en la configuración (solo esas líneas). */
export const ajustar = (nombre: string, valores: Partial<Record<cli.CampoMundo, string | string[] | null>>) =>
    escrito(cli.ajustarMundo(nombre, valores));
/** Qué pasa con un agente fuera de su mundo: lo escribe en su agente.toml (y lo sube); lo que vuelve se aplica al tiro. */
export const ponerFueraDeSuMundo = (clave: string, valor: cli.FueraDeSuMundo) => escrito(cli.fueraDeSuMundo(clave.replace(/^agente:/, ''), valor));
/** `[mundos] fuera`: el que rige fuera de todo horario ("" ambos). */
export const ponerFuera = (valor: string) => escrito(cli.fueraMundos(valor));
/** Un mundo nuevo, vacío. */
export const crear = (nombre: string) => escrito(cli.crearMundo(nombre));
/** Quitar un mundo de la configuración. */
export const borrar = (nombre: string) => escrito(cli.borrarMundo(nombre));

/** Arrancar: leer los mundos y mirar el reloj (cada medio minuto: el horario cambia al minuto). */
export function montar(): void {
    // lo de cada mundo y de qué mundo es cada agente (la barra esconde así a uno sin hilo de otro mundo); un telar más
    // viejo, sin `GET /mundos`, da los mundos en `GET /config`
    void leerDetalle().then(e => { if (e) void cli.config().then(r => { if (r.datos) recibir(r.datos); }); });
    setInterval(() => aplicar(), 30_000);
    // al volver a la pestaña después de un rato (el portátil dormido), al tiro
    document.addEventListener('visibilitychange', () => { if (!document.hidden) aplicar(); });
}
