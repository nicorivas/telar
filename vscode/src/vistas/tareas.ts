// Las acciones sobre una tarea —llevarla a su hilo, marcarla hecha, reagendarla, asignarla,
// la estrella, compartirla— que usa el dashboard. Lo que piden a la interfaz va a la página (web/ui.ts).

import * as ui from '../web/ui';
import type { Opcion } from '../web/ui';
import * as cli from '../cli';
import { modelo } from '../modelo';
import { olvidarDia } from './dia';

/** `texto` y `enviar`: lo que se le dice al agente del hilo, y mandarlo (no solo escribirlo). */
export async function llevarPendiente(ref: string, nuevo: boolean, proveedor = '', texto = '', enviar = false): Promise<void> {
    // buscar el hilo, retomarlo o encargárselo a un agente del servidor toma unos segundos:
    // una notificación lo dice mientras tanto, para que el Enter no parezca perdido
    const r = await ui.progreso({ titulo: `telar: llevando ${ref} a su hilo…` },
        () => cli.pendiente(ref, nuevo, proveedor, texto, enviar));
    if (!r.datos) {
        void ui.aviso(`telar: ${r.error ?? `no pude llevar «${ref}»`}`);
        return;
    }
    await modelo.sondear();
    void ui.mostrarTerminal();
}

/** El ✓ de la lista: corre la acción que el proveedor declara con `rol: "hecha"`, sin abrir
 *  la ficha ni preguntar (se deshace reabriéndola). Si el proveedor no declara una, lo dice. */
/** Una fecha nueva para una tarea: las de siempre a un clic, u otra escrita a mano. Devuelve
 *  AAAA-MM-DD (o +Nd, que el proveedor cuenta desde su fecha), o undefined si se cancela. */
export async function elegirFecha(titulo: string): Promise<string | undefined> {
    const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const desde = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d; };
    const dias = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const hoy = new Date();
    const lunes = desde(((8 - hoy.getDay()) % 7) || 7);
    const finDeMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);
    const opciones: (Opcion & { valor: string })[] = [
        { label: 'mañana', description: `${dias[desde(1).getDay()]} ${iso(desde(1))}`, valor: iso(desde(1)) },
        { label: 'pasado mañana', description: `${dias[desde(2).getDay()]} ${iso(desde(2))}`, valor: iso(desde(2)) },
        { label: 'el próximo lunes', description: iso(lunes), valor: iso(lunes) },
        { label: 'en una semana', description: `${dias[desde(7).getDay()]} ${iso(desde(7))}`, valor: iso(desde(7)) },
        { label: 'fin de mes', description: `${dias[finDeMes.getDay()]} ${iso(finDeMes)}`, valor: iso(finDeMes) },
        { label: 'otra fecha…', description: 'AAAA-MM-DD, 15-10, 15-oct o +10d', valor: '' },
    ];
    const elegida = await ui.elegir(opciones, { titulo: `Nueva fecha · ${titulo}`, placeholder: 'para cuándo queda' });
    if (!elegida) return undefined;
    if (elegida.valor) return elegida.valor;
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const leer = (t: string): string => {
        t = t.trim().toLowerCase();
        if (/^\+\d+d$/.test(t) || /^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
        const m = t.match(/^(\d{1,2})[-/ ](\d{1,2}|[a-zé]{3,})$/);
        if (!m) return '';
        const mes = /^\d+$/.test(m[2]) ? Number(m[2]) : meses.indexOf(m[2].slice(0, 3)) + 1;
        if (mes < 1 || mes > 12) return '';
        let d = new Date(hoy.getFullYear(), mes - 1, Number(m[1]));
        if (d.getDate() !== Number(m[1])) return '';  // un día que ese mes no tiene (31-feb)
        if (d < new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())) d = new Date(hoy.getFullYear() + 1, mes - 1, Number(m[1]));
        return iso(d);
    };
    const escrita = await ui.campo({ titulo: `Nueva fecha · ${titulo}`, ayuda: 'AAAA-MM-DD, 15-10, 15-oct o +10d',
        validar: t => (t.trim() && !leer(t) ? 'no entiendo esa fecha' : undefined) });
    return escrita?.trim() ? leer(escrita) || undefined : undefined;
}

/** Reagendar una tarea desde la lista: la acción con rol «fecha» de su proveedor, con la fecha elegida. */
export async function reagendar(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'fecha') ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar la fecha`}`);
        return false;
    }
    const fecha = await elegirFecha(`${id} ${ficha.datos?.titulo ?? ''}`.trim());
    if (!fecha) return false;
    const r = await cli.accionTarea(id, proveedor, k, fecha);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude mover ${id}`}`); return false; }
    ui.estado(`${id} → ${fecha}`, 5000);
    return true;
}

/** Elegir quién hace una tarea: la persona (que es lo de siempre, sin asignar), ella misma asignada a
 *  propósito, el equipo que ofrece el proveedor, u otro nombre escrito. Devuelve el texto para la
 *  acción («none» para dejarla sin asignar), o undefined si se cancela. */
export async function elegirDueno(titulo: string, actual: string, opciones: string[], persona: string,
    vineta = false): Promise<string | undefined> {
    type Item = Opcion & { valor?: string };
    const yo = persona ? persona[0].toUpperCase() + persona.slice(1) : 'yo';
    const items: Item[] = [
        // una viñeta de un documento sin responsable no es de nadie; una tarea sin dueño es de la persona
        vineta ? { label: 'Sin responsable', description: 'la viñeta no dice quién la hace', valor: 'none' }
            : { label: `${yo} (sin asignar)`, description: 'lo de siempre: una tarea sin dueño es tuya', valor: 'none' },
        { label: yo, description: 'asignada a ti a propósito', valor: yo },
        { label: '', separador: true },
        ...opciones.filter(o => o.toLowerCase() !== yo.toLowerCase()).map(o => ({ label: o, valor: o })),
        { label: '', separador: true },
        { label: 'otra persona…', valor: '' },
    ];
    for (const it of items) if (it.valor !== undefined && it.valor && (it.valor === actual || (it.valor === 'none' && !actual))) it.description = `${it.description ?? ''} ← ahora`.trim();
    const e = await ui.elegir(items, { titulo: titulo, placeholder: 'quién hace esta tarea' });
    if (!e) return undefined;
    if (e.valor) return e.valor;
    const escrito = await ui.campo({ titulo: titulo, ayuda: 'el nombre de quien la hace' });
    return escrito?.trim() || undefined;
}

/** El responsable de una tarea, desde su fila: la acción del proveedor con `rol: dueno`. */
export async function asignar(valor: string, actual: string, persona: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const acciones = ficha.datos?.acciones ?? [];
    const k = acciones.findIndex(a => a.rol === 'dueno');
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar el responsable`}`);
        return false;
    }
    const quien = await elegirDueno(`${id} ${ficha.datos?.titulo ?? ''}`.trim(), actual, acciones[k].opciones ?? [], persona);
    if (!quien) return false;
    const r = await cli.accionTarea(id, proveedor, k, quien);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude asignar ${id}`}`); return false; }
    ui.estado(`${id} → ${quien === 'none' ? 'sin asignar' : quien}`, 5000);
    return true;
}

/** Correr la acción de una tarea que tiene ese `rol` (estrella, equipo…) sin abrir su ficha. */
async function alternarPorRol(valor: string, rol: string, queEs: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === rol) ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece ${queEs}`}`);
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k, '');
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude cambiar ${queEs} de ${id}`}`); return false; }
    ui.estado(`${id}: ${ficha.datos?.acciones?.[k].nombre ?? queEs}`, 4000);
    return true;
}

/** Poner o quitar la estrella de una tarea: la acción del proveedor con `rol: estrella`. */
export const alternarEstrella = (valor: string) => alternarPorRol(valor, 'estrella', 'la estrella');

/** Compartir una tarea con el equipo, o dejar de hacerlo: la acción con `rol: equipo` (`telar equipo`). */
export async function alternarEquipo(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // la acción dice qué hará: «○ compartir…» la comparte, «◉ dejar de compartir…» la deja
    const antes = (await cli.tarea(id, proveedor)).datos?.acciones?.find(a => a.rol === 'equipo')?.nombre ?? '';
    if (!await alternarPorRol(valor, 'equipo', 'compartir con el equipo')) return false;
    const compartida = antes.startsWith('○');
    void ui.info(compartida
        ? `telar: ${id} ahora la ve el equipo (título, estado, prioridad y fecha); pueden sugerir subirla.`
        : `telar: ${id} dejó de compartirse con el equipo.`);
    return true;
}

export async function marcarHecha(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // un viaje: la acción por su rol. Un telar de antes (el de otra máquina sin actualizar) no
    // conoce --rol: entonces, como siempre, la ficha primero para saber su número
    const directo = await ui.progreso({ discreto: true, titulo: `✓ ${id}…` },
        () => cli.accionPorRol(id, proveedor, 'hecha'));
    if (directo.datos) {
        olvidarDia();
        ui.estado(`✓ ${id} hecha`, 5000);
        return true;
    }
    if (!/--rol|unrecognized|argumentos/i.test(directo.error ?? '')) {
        void ui.aviso(`telar: ${directo.error ?? `no pude marcar ${id}`}`);
        olvidarDia();
        return false;
    }
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'hecha') ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id} no se puede marcar hecha desde la lista: ábrela`}`);
        olvidarDia();
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude marcar ${id}`}`); return false; }
    ui.estado(`✓ ${id} hecha`, 5000);
    return true;
}
