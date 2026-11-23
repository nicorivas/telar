// El día en una línea, en la cabecera de la página (el componente: componentes/jornada.ts). Los datos son los del
// calendario que la página ya lee: la agenda de hoy de `telar hoy` (vistas/dashboard/dia.ts, con su caché: a los
// proveedores se les pregunta cada cinco minutos), cada evento con lo que es (clases.ts: una cita con otras personas es
// una reunión; un bloque propio o la rutina, no) y lo que la persona respondió a la invitación (`respuesta`: lo
// rechazado no cuenta; lo sin responder sí, con su marca; el componente decide cómo se dibuja). Se repinta al cambiar el minuto y al volver a la página. Sin
// calendario declarado, sin reuniones o con el día terminado, el lugar queda vacío y la cabecera no lo muestra
// (marco.css). Un clic lleva al calendario del dashboard. Con un mundo puesto (web/mundo.ts), los eventos de ese mundo y
// los sin clasificar: el día del trabajo no se ve en lo personal.

import { jornada, ocupa, type Clase, type Tramo } from '../componentes/jornada';
import { dia, type Dia } from '../vistas/dashboard/dia';
import { eventosDelDia } from '../vistas/dashboard/eventos';
import { queEs } from '../vistas/dashboard/clases';
import { JORNADA } from '../vistas/dashboard/semana';
import * as mundo from './mundo';

const CLASE: Record<string, Clase> = { cita: 'reunion', bloque: 'bloque', rutina: 'rutina' };

/** Los minutos desde la medianoche de hoy (antes de hoy, negativos; mañana, más de 1440). */
function minutos(ms: number, medianoche: number): number {
    return Math.round((ms - medianoche) / 60000);
}

/** Los tramos de un día: los eventos con hora de su calendario (lo de día completo no ocupa la jornada). */
export function tramosDe(d: Dia, medianoche: number): Tramo[] {
    if (!d.agenda) return [];
    const delMundo = { ...d, agenda: d.agenda.filter(f => mundo.seVe(f.mundo)) };
    return eventosDelDia(delMundo).filter(e => !e.soloPlan).map(e => ({
        inicio: minutos(e.inicio, medianoche), fin: minutos(e.fin, medianoche), titulo: e.titulo, clase: CLASE[queEs(e).tipo] ?? 'bloque',
        respuesta: e.respuesta ?? '',
    }));
}

/** La jornada que abarca la barra: la de la semana del calendario (8:30 a 18:00), estirada a la media hora si una
 *  reunión que ocupa el tiempo (una que no se rechazó) empieza antes o termina después. */
export function abarca(tramos: Tramo[]): { desde: number; hasta: number } {
    const rs = tramos.filter(ocupa);
    const media = 30;
    const desde = Math.min(JORNADA[0] * 60, ...rs.map(t => Math.floor(t.inicio / media) * media));
    const hasta = Math.max(JORNADA[1] * 60, ...rs.map(t => Math.ceil(t.fin / media) * media));
    return { desde: Math.max(0, desde), hasta: Math.min(24 * 60, hasta) };
}

/** Poner el día en su lugar de la cabecera y tenerlo al día. `alClic` lleva al calendario. */
export function montar(lugar: HTMLElement, alClic: () => void): void {
    let ultimo = '';
    const pintar = async () => {
        const d = await dia().catch(() => undefined);
        const ahora = new Date();
        const medianoche = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()).getTime();
        // si la última lectura falló, `dia()` deja la de antes, si es de hoy: sirve igual
        const tramos = d ? tramosDe(d, medianoche) : [];
        const html = tramos.length ? jornada({ ...abarca(tramos), ahora: minutos(ahora.getTime(), medianoche), tramos }) : '';
        if (html === ultimo) return;
        ultimo = html;
        lugar.innerHTML = html;
        lugar.hidden = !html;
    };
    // al cambiar el minuto (y no antes: la barra se mueve de a minutos)
    const cadaMinuto = () => {
        void pintar();
        setTimeout(cadaMinuto, 60000 - (Date.now() % 60000) + 50);
    };
    cadaMinuto();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) void pintar(); });
    mundo.alCambiar(() => void pintar());
    lugar.addEventListener('click', e => { e.preventDefault(); alClic(); });
}
