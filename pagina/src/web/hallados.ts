// Lo hallado por la búsqueda de telar (`GET /buscar`, cli.buscar), visto desde la página: el ícono y la tinta de cada
// fuente, cómo se abre una cosa hallada donde vive, y las fuentes remotas del buscador ⌘K (los proyectos, las tareas y los
// documentos del grafo). Lo usan las dos búsquedas de la página: Todo (vistas/dashboard/todo.ts), que la pide entera y
// la muestra por fuente, y ⌘K (web/buscador.ts), que mientras se escribe pide solo esas tres, en un solo pedido por cada
// cosa escrita. El pedido es el mismo (cli.buscar) y el orden lo da telar: lo que lo tiene en el título primero, lo que
// ya pasó al final y, con `primero` (el mundo puesto), lo de ese mundo antes que lo de los otros. Aquí no se puntúa nada.
// ⌘K, que se abre en cualquier momento a la vista de quien mire la pantalla, no muestra lo de otro mundo mientras uno
// filtra (`ve`; con ambos o en el modo todo, todo): lo de otro mundo se busca en Todo, donde va al final y dice de cuál es.
// Lo de un agente que pide esconderse fuera de su mundo (`ajeno`: lo de la carpeta de uno que declara su mundo), ni en todo.

import * as cli from '../cli';
import * as ui from './ui';
import * as mundo from './mundo';
import { I } from './iconos';
import type { Fuente, Resultado } from './buscador';

/** La fuente de los documentos de un grafo: el tipo `doc` de un módulo que los lista. */
export const DOCUMENTOS = 'objeto:doc';

/** El ícono y la tinta de cada fuente (de la búsqueda, o de una pestaña): la de su pantalla. Lo demás, tenue. */
const DE: Record<string, [string, string]> = {
    esperas: [I.campana, 'magenta'], tareas: [I.hecha, 'cian'], revisar: [I.hecha, 'cian'], casillas: [I.listado, 'verde'],
    hilos: [I.terminal, 'azul'], proyectos: [I.carpeta, 'verde'], iniciativas: [I.chispa, 'verde'], calendario: [I.fecha, 'azul'],
    tactica: [I.correr, 'amarillo'], ahora: [I.reloj, 'amarillo'],
    [DOCUMENTOS]: [I.documento, 'amarillo'],
};
export const deFuente = (clave: string): [string, string] => DE[clave]
    ?? (clave.startsWith('bloque:') ? [I.ventana, 'violeta'] : clave.startsWith('objeto:') ? [I.ficha, 'blanco'] : [I.lista, 'dim']);

/** Abrir lo hallado donde vive: un objeto que es un documento (los de un grafo: traen su `ruta_abs`), en el visor, que
 *  muestra al lado sus conexiones; lo demás, su dirección; una casilla sin ella, su documento. `false` si no sabe
 *  abrirlo desde aquí (la fila de un bloque: la abre su pestaña, que es de quien la muestra). */
export async function abrirHallado(h: cli.JsonHallado): Promise<boolean> {
    if (h.datos?.ruta_abs) { await ui.abrirArchivo(h.datos.ruta_abs); return true; }
    if (h.direccion) { await ui.abrirDireccion(h.direccion); return true; }
    if (h.fuente === 'casillas' && h.donde) { await ui.abrirArchivo(h.donde); return true; }
    return false;
}

/** «hace 3 d», «vence el 21-nov», corto: lo que va al final de una cosa hallada (en Todo y en ⌘K). */
export function cuandoCorto(iso: string): string {
    if (!iso) return '';
    const hoy = new Date().toISOString().slice(0, 10);
    const d = iso.slice(0, 10);
    if (d === hoy) return iso.length > 10 ? `hoy ${iso.slice(11, 16)}` : 'hoy';
    const [a, m, dd] = d.split('-');
    return a && m && dd ? `${Number(dd)}-${['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][Number(m) - 1] ?? m}` : '';
}

/** Cuántos de cada fuente se le piden a telar por cada cosa escrita en ⌘K (el buscador muestra hasta ocho por grupo). */
export const POR_PEDIDO = 8;

/** Las fuentes de telar que ⌘K muestra, cada una en su grupo: su clave en ⌘K, su fuente en `GET /buscar` y su orden
 *  entre los grupos (después de lo de la página). Los proyectos primero: son pocos y es adonde más se va; los
 *  documentos, que son muchos, al último. */
export const EN_K = [
    { clave: 'proyectos', fuente: 'proyectos', nombre: 'proyectos', orden: 6 },
    { clave: 'tareas', fuente: 'tareas', nombre: 'tareas', orden: 7 },
    { clave: 'documentos', fuente: DOCUMENTOS, nombre: 'documentos', orden: 8 },
] as const;

/** Lo que usan las fuentes de telar en ⌘K; las pruebas lo cambian (pruebas/buscador.mjs). */
export interface DeHallados {
    buscar: typeof cli.buscar;
    /** el mundo cuyo contenido va primero ('' con ambos) */
    primero: () => string;
    /** el nombre de un mundo, para decir de cuál es uno de los otros */
    nombreMundo: (clave: string) => string;
    /** si lo de ese mundo se ve con el puesto (web/mundo.ts, `seVe`): lo de otro mundo no sale en ⌘K, que está a la vista
     *  de quien mira la pantalla; se busca en Todo («buscar en todo», la última fila), que lo pone al final */
    ve: (mundo: string | undefined) => boolean;
    /** si es de un agente que pide esconderse fuera de su mundo, con otro puesto (web/mundo.ts, `deAgenteAjeno`): no sale, ni en el modo todo */
    ajeno: (h: cli.JsonHallado) => boolean;
    preparar: () => unknown;
    /** si telar no alcanzó a leer una fuente (viene `tarde` y sin nada): cuántas veces más preguntar, y cada cuánto */
    reintentos: number;
    pausa: number;
}

/** Una cosa hallada, como fila del buscador: su título y un detalle corto (de una tarea, su número, su proyecto y cuándo
 *  vence, o su estado si ya pasó; de lo demás, dónde vive), y de qué mundo es, si es de otro que el puesto. Abrirla es
 *  lo mismo que en Todo. */
export function resultadoDe(h: cli.JsonHallado, primero: string, nombreMundo: (clave: string) => string = c => c): Resultado {
    const donde = h.donde || h.datos?.ruta_abs || '';
    const otro = !!primero && !!h.mundo && h.mundo !== primero;
    const partes = h.fuente === 'tareas' ? [h.id, donde, h.pasada && h.estado ? h.estado : cuandoCorto(h.cuando)] : [donde];
    return { titulo: h.titulo, icono: deFuente(h.fuente)[0], detalle: [...partes, otro ? nombreMundo(h.mundo) : ''].filter(Boolean).join(' · '),
        abrir: () => abrirHallado(h) };
}

/** Cuánto vale lo que telar contestó para algo escrito (ms): dentro, escribirlo de nuevo no vuelve a preguntar. */
const VIGENCIA = 5000;

/** Una respuesta de telar para lo escrito, con el mundo que se pidió primero. */
interface Ronda { datos: cli.JsonBusqueda; primero: string }

/** El pedido que comparten las fuentes de ⌘K: uno por cada cosa escrita, con las tres fuentes, aunque lo pidan las
 *  tres (el buscador les pregunta a todas a la vez). Si alguna vino `tarde` y sin nada, la ronda siguiente, tras la
 *  pausa, pregunta solo por esas; también una vez para todas. Recuerda las últimas pocas cosas escritas, unos segundos
 *  (lo de una anterior que sigue reintentando no borra lo último), salvo lo que falló. */
class Pedido {
    private readonly rondas = new Map<string, { desde: number; suyas: Promise<Ronda>[] }>();
    constructor(private readonly d: DeHallados) {}

    ronda(q: string, vez: number): Promise<Ronda> {
        let de = this.rondas.get(q);
        // lo de hace rato no vale (al volver a abrir ⌘K, lo de ahora): solo la primera ronda dice desde cuándo
        if (!de || (!vez && Date.now() - de.desde > VIGENCIA)) {
            this.rondas.delete(q);
            this.rondas.set(q, de = { desde: Date.now(), suyas: [] });
            for (const viejo of [...this.rondas.keys()].slice(0, -4)) this.rondas.delete(viejo);
        }
        const { suyas } = de;
        const ya = suyas[vez];
        if (ya) return ya;
        const nueva = suyas[vez] = this.pedir(q, vez, suyas);
        // lo que falló no se recuerda: volver a escribir lo mismo lo vuelve a pedir
        nueva.catch(() => { if (suyas[vez] === nueva) suyas.length = vez; });
        return nueva;
    }

    private async pedir(q: string, vez: number, antes: Promise<Ronda>[]): Promise<Ronda> {
        let fuentes: string[] = EN_K.map(k => k.fuente);
        if (vez) {
            if (!antes[vez - 1]) throw new Error('lo escrito ya venció');   // de una consulta vieja: el buscador la descarta
            const previa = (await antes[vez - 1]).datos;
            fuentes = previa.fuentes.filter(f => f.tarde && !f.hallados.length).map(f => f.clave);
            await new Promise(ok => setTimeout(ok, this.d.pausa));
        }
        const primero = this.d.primero();
        const r = await this.d.buscar(q, POR_PEDIDO, false, primero, fuentes, true);
        if (!r.datos) throw new Error(r.error ?? 'no se pudo buscar');
        return { datos: r.datos, primero };
    }
}

/** Las fuentes remotas de ⌘K que pregunta a telar: los proyectos, las tareas y los documentos del grafo, cada una en su
 *  grupo y en el orden en que vienen (los de los otros mundos, al final, y solo si el puesto los deja ver: `ve`), con un solo `GET /buscar` por cada cosa
 *  escrita (Pedido). Al abrirse la ventana, que telar empiece a leer (como al abrir Todo). Si telar no alcanzó a leer
 *  una, se vuelve a preguntar por ella unas veces; una respuesta que no sirve (falla) es un error, y el buscador no
 *  muestra nada de ella. Una fuente que esa máquina no tiene (sin tareas, o sin módulo que liste documentos) no
 *  muestra nada. */
/** La de un tipo de objeto de un módulo que pide salir en ⌘K (`[objetos.<tipo>] buscador`: los chats de whatsapp), en su
 *  grupo, después de las de telar: un pedido propio por cada cosa escrita, con el mundo puesto primero; lo de otro mundo
 *  (el que dice el objeto, `campos.mundo`) no sale, como en las demás. Abrirlo es abrir su objeto: su vista, con sus
 *  acciones (marcar un chat de foco). */
export function fuenteDeObjetos(tipo: string, plural: string, orden: number, o: Partial<DeHallados> = {}): Fuente {
    const d: DeHallados = {
        buscar: cli.buscar, primero: () => mundo.puesto().mundo, preparar: () => undefined,
        nombreMundo: c => mundo.declarados().find(m => m.clave === c)?.nombre ?? c, ve: mundo.seVe, ajeno: mundo.deAgenteAjeno, reintentos: 3, pausa: 1000, ...o,
    };
    const fuente = `objeto:${tipo}`;
    return {
        clave: fuente, nombre: plural, orden, color: deFuente(fuente)[1], remota: true,
        resultados: async (q: string) => {
            for (let vez = 0; ; vez++) {
                const primero = d.primero();
                const r = await d.buscar(q, POR_PEDIDO, false, primero, [fuente], true);
                if (!r.datos) throw new Error(r.error ?? 'no se pudo buscar');
                const f = r.datos.fuentes.find(x => x.clave === fuente);
                if (!f) return [];
                if (f.tarde && !f.hallados.length && vez < d.reintentos) { await new Promise(ok => setTimeout(ok, d.pausa)); continue; }
                if (f.falla && !f.hallados.length) throw new Error(f.falla);
                return f.hallados.filter(h => d.ve(h.mundo) && !d.ajeno(h)).map(h => resultadoDe(h, primero, d.nombreMundo));
            }
        },
    };
}

export function fuentesDeTelar(o: Partial<DeHallados> = {}): Fuente[] {
    const d: DeHallados = {
        buscar: cli.buscar, primero: () => mundo.puesto().mundo, preparar: () => cli.prepararBusqueda(),
        nombreMundo: c => mundo.declarados().find(m => m.clave === c)?.nombre ?? c, ve: mundo.seVe, ajeno: mundo.deAgenteAjeno, reintentos: 3, pausa: 1000, ...o,
    };
    const pedido = new Pedido(d);
    return EN_K.map((k, i): Fuente => ({
        clave: k.clave, nombre: k.nombre, orden: k.orden, color: deFuente(k.fuente)[1], remota: true,
        // que telar empiece a leer, una vez: lo que lee es lo de todas
        preparar: i ? undefined : d.preparar,
        resultados: async (q: string) => {
            for (let vez = 0; ; vez++) {
                const { datos, primero } = await pedido.ronda(q, vez);
                const f = datos.fuentes.find(x => x.clave === k.fuente);
                if (!f) return [];   // esta máquina no la tiene
                if (f.tarde && !f.hallados.length && vez < d.reintentos) continue;
                if (f.falla && !f.hallados.length) throw new Error(f.falla);
                return f.hallados.filter(h => d.ve(h.mundo) && !d.ajeno(h)).map(h => resultadoDe(h, primero, d.nombreMundo));
            }
        },
    }));
}
