// Lo que mira el estado del sistema y lo deja en los avisos (web/avisos.ts, la franja de arriba de la barra): la conexión
// con telar, la sesión del multiplexor, las otras máquinas, los hilos abiertos en dos a la vez y los detenidos en la
// pregunta de confiar en una carpeta (web/detenidos.ts). Lee lo que ya leen el
// modelo (los hilos, cada pocos segundos) y la página (las fotos de las otras máquinas, `espejos`): no pide nada propio.
//
// Antes, la conexión, la sesión y el aviso del multiplexor eran notas arriba de la lista de hilos, y un hilo abierto en
// dos máquinas, un ícono en su fila. Ahora se dicen solo aquí.

import * as avisos from './avisos';
import { avisoFuera, avisosHechos, type MaquinaAlcance } from './alcance';
import { avisosConfiar } from './detenidos';
import { I } from './iconos';
import { modelo } from '../modelo';
import * as mundo from './mundo';
import * as ui from './ui';

/** Una máquina de las otras, como la trae su foto (`GET /espejos`): si está al día, si se sabe que está fuera de línea
 *  (`fuera`, telar.alcance), lo que le espera en cola y sus hilos. */
export interface Maquina extends MaquinaAlcance { hilos: { nombre: string; vivo?: boolean }[] }

let maquinas: Maquina[] = [];

/** Un error como frase: con su punto. */
const frase = (t: string) => (/[.!?…]$/.test(t.trim()) ? t.trim() : `${t.trim()}.`);

/** La conexión con telar y la sesión, de la última lectura de los hilos. */
function revisarModelo(): void {
    // sin respuesta de telar, pasado un rato (un reinicio dura menos: modelo.caido). Si contestó con un error, no es la
    // conexión: es que no pudo leer los hilos
    if (modelo.caido() && !modelo.errorEstado) {
        avisos.poner({ clave: 'conexion', nivel: 'conexion', icono: I.desconectado, texto: 'sin conexión con telar', desde: modelo.fallaDesde,
            detalle: `La página no recibe respuesta de telar${modelo.leido ? ': lo que se ve es lo último que se supo' : ''} (${modelo.error}).`,
            hacer: `Si se estaba reiniciando (un despliegue, una versión nueva), vuelve sola. Si no, revisa que telar serve corra${modelo.aqui ? ` en ${modelo.aqui}` : ''} y que haya red.`,
            acciones: [{ id: 'reintentar', texto: 'reintentar', hacer: () => void ui.orden('telar.actualizar') }] });
    } else avisos.quitar('conexion');
    if (modelo.caido() && modelo.errorEstado) {
        avisos.poner({ clave: 'hilos', nivel: 'falla', icono: I.alerta, texto: 'telar no pudo leer los hilos', desde: modelo.fallaDesde,
            detalle: `${frase(modelo.error)}${modelo.leido ? ' La lista es la de la última lectura buena.' : ''}`,
            hacer: 'Se vuelve a pedir sola cada pocos segundos. Si sigue, `telar hilos` en un terminal dice lo mismo con más detalle.',
            acciones: [{ id: 'reintentar', texto: 'reintentar', hacer: () => void ui.orden('telar.actualizar') }] });
    } else avisos.quitar('hilos');
    // la sesión del multiplexor: sin ella, la lista es lo que telar recuerda (y nada se abre hasta tejerla)
    if (modelo.leido && !modelo.viva) {
        avisos.poner({ clave: 'sesion', nivel: 'falla', icono: I.alerta, conConexion: true,
            texto: modelo.aviso || `la sesión «${modelo.sesion}» no está ${modelo.hilos.length ? 'viva' : 'tejida'}`,
            detalle: modelo.hilos.length ? 'La lista de hilos es lo que telar recuerda: sus ventanas no están abiertas.' : 'Sin la sesión no hay hilos que mostrar.',
            hacer: 'Tejerla: abre la sesión en un terminal con sus hilos (`telar tejer`).',
            acciones: [{ id: 'tejer', texto: 'tejerla en un terminal', hacer: () => void ui.orden('telar.tejer') }] });
    } else avisos.quitar('sesion');
    // un hilo detenido en la pregunta de confiar en una carpeta: no avisa solo (web/detenidos.ts). La franja está siempre a
    // la vista: uno de un agente que pide esconderse fuera de su mundo no se nombra con otro puesto (web/mundo.ts, `hiloDeAgenteAjeno`)
    avisos.soloEstos('confiar:', avisosConfiar(modelo.hilos.filter(h => !mundo.hiloDeAgenteAjeno(h, modelo.hilos)),
        hilo => void ui.orden('telar.ir', { hilo })));
    revisarDobles();
}

/** Un hilo abierto aquí y vivo en otra máquina: dos conversaciones que se separan (una mudanza a medias). */
function revisarDobles(): void {
    const alla = new Map<string, string>([
        ...maquinas.flatMap(m => m.hilos.filter(x => x.vivo).map(x => [x.nombre, m.nombre] as [string, string])),
        ...modelo.hilos.filter(x => x.remoto && x.remoto !== '?' && x.vivo).map(x => [x.nombre, x.remoto!] as [string, string]),
    ]);
    avisos.soloEstos('dos:', modelo.hilos.filter(h => !h.remoto && h.vivo && alla.has(h.nombre)).map(h => ({
        clave: `dos:${h.nombre}`, nivel: 'falla' as const, icono: I.alerta, conConexion: true, cuando: 'nada' as const,
        texto: `«${h.nombre}» abierto aquí y en ${alla.get(h.nombre)}`,
        detalle: 'Son dos conversaciones del mismo hilo, que se separan.',
        hacer: `Cierra una: la de aquí (archivar o descartar, en su ⋯) o la de ${alla.get(h.nombre)}.`,
        ir: { texto: `el hilo ${h.nombre}`, hacer: () => void ui.orden('telar.ir', { hilo: h.nombre }) },
    })));
}

/** Las otras máquinas (lo que publica cada una): una que se quedó sin noticias, con hilos vivos en su última foto, se
 *  dice como nota (lo normal si está apagada; sus hilos se ven apagados en la barra). Si se sabe que está fuera de línea
 *  (telar.alcance), «laptop fuera de línea desde 14:02», con lo que le espera en cola; y lo que se hizo de esa cola al
 *  volver, en la última media hora. Lo llama la página al leerlas. */
export function espejos(l: Maquina[]): void {
    maquinas = l;
    const ir = { texto: 'máquinas', hacer: () => { location.href = '/maquinas'; } };
    avisos.soloEstos('cola:', l.flatMap(m => avisosHechos(m).map(a => ({ ...a, conConexion: true, cuando: 'hace' as const }))));
    avisos.soloEstos('maquina:', l.filter(m => m.fuera || (!m.en_linea && m.hilos.some(x => x.vivo))).map(m => {
        const fuera = m.fuera ? avisoFuera(m) : null;
        if (fuera) return { ...fuera, conConexion: true, cuando: 'nada' as const, ir };
        if (m.fuera) return null;
        const vivos = m.hilos.filter(x => x.vivo).length;
        return {
            clave: `maquina:${m.nombre}`, nivel: 'nota' as const, icono: I.remoto, conConexion: true, cuando: 'hace' as const,
            desde: m.edad === null ? undefined : Date.now() - m.edad * 1000,
            texto: `${m.nombre} sin noticias`,
            detalle: `Su última foto trae ${vivos} ${vivos === 1 ? 'hilo vivo' : 'hilos vivos'}: se ven como estaban.`,
            hacer: 'Si está apagada o durmiendo, es lo normal; si no, revisa su telar serve y el bus.',
            ir,
        };
    }).filter(a => a !== null));
    revisarDobles();
}

/** Empezar a mirar: con cada lectura de los hilos (y cada medio minuto, por lo que depende de la hora: una caída se dice
 *  pasado un rato). */
export function vigilar(): void {
    modelo.cambio.event(revisarModelo);
    setInterval(revisarModelo, 5000);
    revisarModelo();
}
