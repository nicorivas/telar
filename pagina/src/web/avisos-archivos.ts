// Los avisos que vienen de un archivo (`[avisos.<clave>]`, telar.avisos): un programa (un agente, un chequeo que corre
// solo) deja en un JSON cómo está algo, y mientras diga `aviso` o `mal` (y sea de la última hora) la franja de avisos
// (web/avisos.ts) dice su línea, en el color de cuidado (aviso) o de problema (mal), con cuándo se midió. Un clic abre su
// informe en el visor de documentos, en la máquina donde vive. Lo que dice `ok`, lo viejo o lo que no está, nada: se va
// solo.
//
// Abrir el informe, o su ✓ en la lista, lo da por visto (POST /avisos/visto, en la máquina donde vive el archivo: vale
// igual en el laptop y en el teléfono) y deja de salir mientras sea el mismo: telar dice de cada uno si está `visto`, y
// vuelve a salir con un problema nuevo, si empeora o si pasó por ok.
//
// `avisosDeArchivos` arma los avisos sin DOM ni red (lo prueba `npm run prueba:avisos`); `vigilar` los lee (GET /avisos)
// al cargar y cada minuto, si la página se ve.

import * as cli from '../cli';
import * as avisos from './avisos';
import { I } from './iconos';
import * as ui from './ui';

/** Lo que dice el globo del ✓. */
export const AYUDA_VISTO = 'dar por visto: no vuelve a salir hasta que aparezca un problema nuevo, empeore o vuelva después de estar bien';

/** Los avisos de la franja, uno por fuente que hay que decir y que no está vista. `abrir` recibe la ruta del informe (con
 *  «máquina:» delante si vive en otra); `marcar`, el aviso como vino, para darlo por visto (abrir el informe también
 *  lo marca). */
export function avisosDeArchivos(lista: readonly cli.JsonAvisoArchivo[], abrir: (ruta: string) => void,
                                 marcar: (a: cli.JsonAvisoArchivo) => void = () => {}): avisos.Aviso[] {
    return lista.filter(a => (a.nivel === 'aviso' || a.nivel === 'mal') && a.linea && !a.visto).map(a => {
        const desde = Date.parse(a.fecha);
        const medido = Number.isNaN(desde) ? '' : `medido a las ${avisos.hora(desde)}`;
        const informe = a.informe ? (a.maquina ? `${a.maquina}:${a.informe}` : a.informe) : '';
        const sugerencias = a.sugerencias ? `${a.sugerencias} ${a.sugerencias === 1 ? 'sugerencia' : 'sugerencias'} en el informe` : '';
        return {
            clave: `archivo:${a.clave}`, nivel: a.nivel === 'mal' ? 'problema' as const : 'falla' as const, icono: I.campana,
            conConexion: true, cuando: 'hace' as const, desde: Number.isNaN(desde) ? undefined : desde,
            texto: a.linea,
            detalle: [`${a.clave}${a.maquina ? `, en ${a.maquina}` : ''}`, medido, sugerencias].filter(Boolean).join(' · ') + '.',
            hacer: informe ? 'El informe dice qué pasa y qué hacer. Abrirlo lo da por visto.'
                : 'Lo escribe el programa que lo mide: se va solo cuando vuelve a estar bien.',
            ir: informe ? { texto: 'el informe', hacer: () => { abrir(informe); marcar(a); } } : undefined,
            acciones: [{ id: 'visto', texto: '✓ visto', ayuda: AYUDA_VISTO, hacer: () => marcar(a) }],
        };
    });
}

/** Leerlos ahora y cada minuto, mientras la página se vea. Lo que deja de venir se va (`archivo:`), y lo visto también.
 *  Sin respuesta de telar, lo que se sabía sigue (lo dice el aviso de la conexión). */
export function vigilar(): void {
    const leer = async () => {
        const r = await cli.avisosDeArchivos();
        if (!r.datos) return;
        avisos.soloEstos('archivo:', avisosDeArchivos(r.datos.avisos ?? [], ruta => void ui.abrirArchivo(ruta), marcar));
    };
    // se va al tiro; si telar no lo pudo guardar, se dice y vuelve con la lectura siguiente
    const marcar = async (a: cli.JsonAvisoArchivo) => {
        avisos.quitar(`archivo:${a.clave}`);
        const r = await cli.avisoVisto(a.clave, a.nivel, a.problemas);
        if (!r.datos?.ok) ui.estado(`no quedó visto: ${r.datos?.error ?? r.error ?? 'telar no contestó'}`);
        void leer();
    };
    void leer();
    setInterval(() => { if (!document.hidden) void leer(); }, 60 * 1000);
}
