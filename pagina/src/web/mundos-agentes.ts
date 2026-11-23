// Los mundos vistos desde la configuración (⚙ mundos y el cruce en la grilla de ⚙ modos): de qué mundo es cada agente
// residente y por qué, qué sale con un mundo elegido, y lo que se revisa antes de escribir un mundo (lo mismo que dice
// la configuración al leer `[mundos]`: un área, una ruta o una etiqueta en dos mundos es un error). Sin DOM ni red: la
// prueba es `npm run prueba:mundos`.
//
// El mundo de un agente lo dice el servidor (`GET /mundos`, telar.mundos.por_que_agente), como el de su hilo: el que
// declara su agente.toml (`mundo = "personal"`), que le gana a todo; si no, una etiqueta del hilo que un mundo declara
// y, si no, la ruta declarada que calza con su carpeta. Sin ninguna, queda sin
// clasificar y se ve en todos los mundos (esconderlo sería perderlo sin que se note).

import { leerTramo } from '../componentes/modos-mundos';

/** Un agente y su mundo, como los da `GET /mundos` (cli.JsonAgenteMundo). */
export interface AgenteMundo { clave: string; carpeta?: string; mundo: string; por: '' | 'ruta' | 'etiqueta' | 'agente.toml'; valor: string }

/** Si un agente de ese mundo ("" sin clasificar) sale con el mundo elegido ("" ambos): lo suyo y lo sin clasificar;
 *  con ambos, todos. `soloOrdena`: en el modo todo, el mundo ordena y no esconde nada. */
export const seVeEn = (deAgente: string, elegido: string, soloOrdena = false): boolean =>
    soloOrdena || !elegido || !deAgente || deAgente === elegido;

/** Por qué un agente es de su mundo, en una frase: lo que declara su agente.toml, la etiqueta de su hilo o la ruta que
 *  calza con su carpeta. */
export function porQue(a: AgenteMundo | undefined): string {
    const carpeta = a?.carpeta ? ` (${a.carpeta})` : '';
    if (!a?.mundo) return `sin clasificar: ninguna ruta de un mundo calza con su carpeta${carpeta}; se ve en todos`;
    if (a.por === 'agente.toml') return `de ${a.mundo}: lo declara su agente.toml (${a.valor}), y le gana a su carpeta y a sus etiquetas`;
    if (a.por === 'etiqueta') return `de ${a.mundo} por la etiqueta «${a.valor}» de su hilo`;
    return `de ${a.mundo} por su carpeta${carpeta}: calza con la ruta «${a.valor}»`;
}

/** Una lista escrita en un campo: separada por coma, sin espacios a los lados ni repetidos. */
export const leerLista = (texto: string): string[] => [...new Set(texto.split(',').map(x => x.trim()).filter(Boolean))];

/** El horario escrito en un campo: sus tramos separados por «;» (un tramo lleva comas: «lun,mié 9-13»). Si uno no se
 *  entiende, el error dice cuál (como al leer la configuración). */
export function leerHorarioEscrito(texto: string): string[] {
    const tramos = [...new Set(texto.split(';').map(x => x.trim()).filter(Boolean))];
    for (const t of tramos) leerTramo(t);
    return tramos;
}

/** Lo que dice cada mundo, para ver si algo ya es de otro. */
export interface Declarado { nombre: string; areas: string[]; rutas: string[]; etiquetas: string[] }

/** Lo primero de `valores` que no se puede escribir en `campo` de ese mundo: lo que ya es de otro («empresa/» ya es de
 *  «trabajo»; las rutas, con o sin la barra final, son la misma) o una ruta que sube con «..». "" si todo sirve. */
export function choque(mundos: readonly Declarado[], nombre: string, campo: 'areas' | 'rutas' | 'etiquetas', valores: readonly string[]): string {
    const clave = (v: string) => (campo === 'rutas' ? `${v.trim().replace(/\/+$/, '')}/` : v.trim());
    for (const v of valores) {
        if (campo === 'rutas' && v.split('/').includes('..')) return `«${v}» no puede subir con «..»: relativa a la raíz, o absoluta`;
        const otro = mundos.find(m => m.nombre !== nombre && m[campo].some(x => clave(x) === clave(v)));
        if (otro) return `«${v}» ya es de «${otro.nombre}»`;
    }
    return '';
}

/** Lo que un mundo nuevo no puede llamarse: "" si sirve. Una palabra sin espacios ni signos, que no sea otro. */
export function nombreNuevo(nombre: string, hay: readonly string[]): string {
    if (!/^[^\s,:/."'[\]#=]+$/.test(nombre)) return 'una palabra, sin espacios ni signos («,», «:», «/», «.»…)';
    if (nombre === 'sin-clasificar' || nombre === 'fuera') return `«${nombre}» no: es de telar`;
    if (hay.includes(nombre)) return `ya hay un mundo «${nombre}»`;
    return '';
}
