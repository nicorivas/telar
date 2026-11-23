// Las dos fuentes de ⌘K que da la página misma (web/buscador.ts): los hilos (los de aquí y los de las fotos de las otras
// máquinas) y los agentes residentes. Salen de lo que la página ya tiene (el modelo, las fotos de la barra); abrir uno es
// lo de un clic en la barra.
//
// Un agente de otro mundo que el puesto sale solo en el modo todo, al final, como lo demás; uno que pide esconderse fuera
// de su mundo (`fuera_de_su_mundo = "esconder"` en su agente.toml), ni ahí, ni sus hilos (web/mundo.ts, `seVeAgente` y
// `hiloDeAgenteAjeno`): ⌘K se abre en cualquier momento a la vista de quien mire la pantalla (el 23-nov, en todo y en el
// trabajo, nombraba a un agente del mundo personal). Lo prueba `npm run prueba:barra`.

import * as cli from '../cli';
import { modelo } from '../modelo';
import { I } from './iconos';
import * as mundo from './mundo';
import type { Fuente } from './buscador';
import type { HiloDeFoto } from '../vistas/hilos';

/** Lo que las fuentes necesitan de la página: las fotos de las otras máquinas, cómo se muestra un hilo y cómo se manda una
 *  orden (las pruebas lo cambian). */
export interface DeLaPagina {
    otras: () => readonly { nombre: string; hilos: readonly HiloDeFoto[] }[];
    mostrar: (hilo: string) => unknown;
    orden: (orden: string, arg?: unknown) => unknown;
}

const recencia = (iso?: string | null) => {
    const t = iso ? Date.parse(iso) : NaN;
    return Number.isNaN(t) ? 0 : Math.max(0, 100 - (Date.now() - t) / 3600000);   // 100 recién, 0 hace 4 días o más
};

export function fuentes(d: DeLaPagina): Fuente[] {
    return [{
        clave: 'hilos', nombre: 'hilos', orden: 1, color: 'azul',
        resultados: () => {
            // (sin los de un agente, que van en «agentes», y sin una carpeta que desde aquí se ve como «../..»; ni los
            // otros de un agente que pide esconderse fuera de su mundo, ni sus hijos)
            const deAgentes = new Set(modelo.secciones.filter(x => x.grupo === 'agentes').map(x => x.nombre));
            const legible = (r?: string) => (r && !r.startsWith('..') ? r : '');
            const todos = [...modelo.hilos, ...d.otras().flatMap(m => m.hilos)];
            // (uno de un agente de otro mundo, fuera de todo, como siempre; y en todo, el de uno que pide esconderse)
            const ajeno = (h: { nombre: string; agente?: string; padre?: string; mundo?: string }) =>
                (!!h.agente && mundo.fueraDe(h.agente) !== 'ver' && !mundo.seVe(h.mundo)) || mundo.hiloDeAgenteAjeno(h, todos);
            const aqui = modelo.hilos.filter(h => !deAgentes.has(h.nombre) && (!h.agente || cli.nombreVisible(h) !== h.agente) && !ajeno(h)).map(h => ({
                titulo: cli.nombreVisible(h), icono: h.archivado ? I.archivar : h.vivo ? I.lleno : I.vacio,
                detalle: [legible(h.relativa), h.remoto ? `en ${h.remoto}` : '', h.archivado ? 'archivado' : !h.vivo ? 'sin ventana' : ''].filter(Boolean).join(' · '),
                claves: h.nombre, peso: (h.archivado ? 0 : h.vivo ? 50 : 20) + recencia(h.actividad || h.atencion_desde) / 2,
                abrir: () => (h.archivado || !h.vivo ? d.orden('telar.retomar', { hilo: h.nombre }) : d.mostrar(h.nombre)),
            }));
            // los de las otras máquinas, de su foto: se leen y se les escribe por el bus
            const ya = new Set(modelo.hilos.map(h => `${h.remoto ?? ''}|${h.nombre}`));
            const otras = d.otras().flatMap(m => m.hilos.filter(x => x.vivo && !ya.has(`${m.nombre}|${x.nombre}`) && !deAgentes.has(x.nombre) && !ajeno(x)).map(x => ({
                titulo: x.nombre, icono: I.remoto, detalle: [legible(x.relativa), `en ${m.nombre}`].filter(Boolean).join(' · '), peso: 35,
                abrir: () => d.orden('telar.irRemoto', `${m.nombre}|${x.nombre}`),
            })));
            return [...aqui, ...otras];
        },
    }, {
        clave: 'agentes', nombre: 'agentes', orden: 2, color: 'violeta',
        // los del mundo puesto (web/mundo.ts, `agentesQueSeVen`); en todo, también los otros, salvo los que piden esconderse
        resultados: () => mundo.agentesQueSeVen(modelo.secciones.filter(s => s.grupo === 'agentes'), modelo.hilos).map(s => {
            const suyo = modelo.hilos.find(h => h.nombre === s.nombre);
            return {
                titulo: s.nombre, icono: I.agente, detalle: suyo?.vivo ? 'su hilo, abierto' : 'su casa', peso: suyo?.vivo ? 60 : 30,
                abrir: () => (suyo?.vivo ? d.mostrar(s.nombre) : d.orden('telar.seccion', s.clave)),
            };
        }),
    }];
}
