// Lo que en VS Code son comandos de la extensión (el menú de un hilo, ir a uno, retomarlo, abrir una
// sección…), para el anfitrión que no es VS Code: el dashboard en el navegador (src/navegador), que da lo
// suyo: su interfaz, cómo avisar y qué mostrar a la derecha.

import type { Anfitrion, Opcion } from '../anfitrion';
import * as cli from '../cli';
import { modelo } from '../modelo';
import { elegirEntrada } from '../vistas/equipo';
import type { BarraHilos } from '../vistas/hilos';
import type { PanelHoy } from '../vistas/hoy';

export interface Casa {
    hoy: PanelHoy;
    barra: BarraHilos;
    anfitrion: Anfitrion;
    /** un aviso a quien mira: `{ __aviso, nivel, ms }` */
    avisar(m: { __aviso: string; nivel?: string; ms?: number }): void;
    /** a la derecha: «dashboard», un hilo, «doc:<hilo>» o «rem:<máquina>:<hilo>» */
    mostrar(que: string): void;
}

export function crearOrdenes(c: Casa): Record<string, (...args: any[]) => unknown> {
    const hiloDe = (a: unknown): string => typeof a === 'string' ? a : (a as { hilo?: string } | undefined)?.hilo ?? '';

    /** Por qué un nombre no sirve para un hilo nuevo, o undefined: `telar ir --crear` con el nombre de uno que
     *  ya existe va a ese (o lo retoma), no abre otro. */
    function yaEsta(nombre: string): string | undefined {
        const igual = nombre ? modelo.hilos.find(h => h.nombre === nombre) : undefined;
        if (!igual) return undefined;
        return igual.archivado || !igual.vivo ? `ya hay un hilo «${nombre}», cerrado: retómalo desde la lista, o elige otro nombre`
            : `ya hay un hilo «${nombre}»: elige otro nombre`;
    }

    /** `telar hilo <verbo>` sobre un hilo, y la lista al día. */
    async function sobreHilo(a: unknown, verbo: string, extra: string[] = [], valor?: string): Promise<boolean> {
        const hilo = hiloDe(a);
        if (!hilo) return false;
        const r = await cli.hilo(verbo, hilo, valor, extra);
        if (!r.ok) { c.avisar({ __aviso: `telar: ${r.err.trim().split('\n').pop() || `«telar hilo ${verbo}» falló`}`, nivel: 'falla' }); return false; }
        modelo.invalidar();
        await modelo.sondear();
        return true;
    }

    /** El menú de un hilo, que en VS Code es su menú contextual: lo que se puede hacer con él, según esté
     *  vivo, archivado o vinculado. Cada acción es una orden `telar hilo …`. */
    async function menuHilo(a: unknown): Promise<void> {
        const hilo = hiloDe(a);
        const h = modelo.porNombre(hilo);
        if (!hilo || !h) return;
        type Fila = Opcion & { hacer?: () => Promise<unknown> };
        const prioridad = (n: string, nombre: string): Fila => ({ label: `prioridad ${nombre}`, description: String(h.prioridad ?? '') === n ? 'la que tiene' : '',
            hacer: () => sobreHilo(hilo, 'prioridad', [], n) });
        const filas: Fila[] = [
            { label: h.archivado || !h.vivo ? 'retomar' : 'ver', description: h.archivado || !h.vivo ? 'reabre su tab con su conversación' : '',
                hacer: async () => { if (h.archivado || !h.vivo) { if (await sobreHilo(hilo, 'retomar')) c.mostrar(hilo); } else c.mostrar(hilo); } },
            { label: 'renombrar', description: 'se mueve con él lo que telar sabía', hacer: async () => {
                const nombre = await c.anfitrion.campo({ title: `Nombre nuevo para «${hilo}»`, value: hilo });
                if (nombre && nombre !== hilo) await sobreHilo(hilo, 'renombrar', [], nombre);
            } },
            ...(h.vinculado ? [{ label: 'ver su carpeta y documento', description: h.relativa || h.ruta, hacer: async () => c.mostrar(`doc:${hilo}`) }] : []),
            { label: 'vincular a un proyecto', description: h.relativa ? `hoy: ${h.relativa}` : 'sin carpeta', hacer: () => vincularWeb(hilo) },
            ...(h.vinculado ? [{ label: 'desvincular', description: 'soltar su carpeta', hacer: () => sobreHilo(hilo, 'desvincular') }] : []),
            { label: 'prioridad', separador: true },
            prioridad('1', 'alta'), prioridad('2', 'media'), prioridad('3', 'baja'), prioridad('ninguna', 'ninguna'),
            { label: 'guardar o cerrar', separador: true },
            ...(h.archivado ? [{ label: 'desarchivar', description: 'volver a la lista sin abrirlo', hacer: () => sobreHilo(hilo, 'desarchivar') }]
                : [{ label: 'archivar', description: 'cierra el tab y guarda su conversación', hacer: () => sobreHilo(hilo, 'archivar', ['--cerrar']) }]),
            ...(h.vivo ? [{ label: 'cerrar', description: 'cierra el tab y lo saca de la lista', hacer: () => sobreHilo(hilo, 'cerrar') }] : []),
            ...(!h.remoto ? [{ label: 'llevar a otra máquina', description: 'su conversación viaja; los archivos no', hacer: () => llevarWeb(hilo) }] : []),
            { label: 'olvidar', description: 'telar pierde su carpeta, su prioridad y su atención', hacer: async () => {
                const si = await c.anfitrion.aviso(`¿Que telar olvide «${hilo}»? Pierde su carpeta, su prioridad y su atención.`, { modal: true }, 'Olvidar');
                if (si === 'Olvidar') await sobreHilo(hilo, 'olvidar');
            } },
        ];
        const elegida = await c.anfitrion.elegir(filas, { title: hilo });
        await elegida?.hacer?.();
    }

    /** Vincular desde la web: se elige entre los proyectos del perfil, o se escribe una ruta. */
    async function vincularWeb(hilo: string): Promise<void> {
        const r = await cli.proyectos();
        const otra = { label: 'otra carpeta…', description: 'escribir su ruta', ruta: '' };
        const filas = [...(r.datos?.proyectos ?? []).map(p => ({ label: p.nombre, description: p.ruta, ruta: String(p.ruta) })), otra];
        const elegida = await c.anfitrion.elegir(filas, { title: `Vincular «${hilo}» a…`, placeHolder: 'filtrar' });
        if (!elegida) return;
        const ruta = elegida.ruta || await c.anfitrion.campo({ title: `La carpeta de «${hilo}»`, prompt: 'relativa a la raíz del repositorio, o absoluta' });
        if (ruta) await sobreHilo(hilo, 'vincular', [], ruta);
    }

    /** Llevar un hilo a otra máquina de [remotos]: si aquí hay trabajo sin subir, se pregunta antes. */
    async function llevarWeb(hilo: string): Promise<void> {
        const remotos = (await cli.config()).datos?.remotos ?? [];
        if (!remotos.length) { c.avisar({ __aviso: 'telar: no hay máquinas en [remotos]', nivel: 'aviso' }); return; }
        const elegida = remotos.length === 1 ? remotos[0]
            : (await c.anfitrion.elegir(remotos.map(x => ({ label: x.nombre, description: x.destino, x })), { title: `¿A qué máquina llevo «${hilo}»?` }))?.x;
        if (!elegida) return;
        c.avisar({ __aviso: `llevando «${hilo}» a ${elegida.nombre}…`, nivel: 'info', ms: 4000 });
        let r = await cli.hilo('llevar', hilo, elegida.nombre);
        if (!r.ok && /sin subir/.test(r.err)) {
            const lista = r.out.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
            const si = await c.anfitrion.aviso(`La conversación de «${hilo}» viaja, los archivos no. Aquí hay trabajo que allá no va a estar:\n${lista}`, { modal: true }, 'Llevar igual');
            if (si !== 'Llevar igual') return;
            r = await cli.hilo('llevar', hilo, elegida.nombre, ['--si']);
        }
        if (!r.ok) { c.avisar({ __aviso: `telar: ${r.err.trim().split('\n').pop() || 'no se llevó'}`, nivel: 'falla' }); return; }
        modelo.invalidar();
        await modelo.sondear();
    }

    return {
        'telar.menuHilo': a => menuHilo(a),
        // un hilo de otra máquina: se lee como conversación y se le escribe por el bus (aquí no hay su terminal)
        'telar.irRemoto': (id?: string) => { const [maq, ...resto] = String(id ?? '').split('|'); if (maq && resto.length) c.mostrar(`rem:${maq}:${resto.join('|')}`); },
        // en la web, ir a un hilo es mostrar su terminal a la derecha (no mover la ventana de tmux de nadie)
        'telar.ir': a => c.mostrar(hiloDe(a)),
        'telar.retomar': async a => { if (await sobreHilo(a, 'retomar')) c.mostrar(hiloDe(a)); },
        'telar.archivar': a => sobreHilo(a, 'archivar', ['--cerrar']),
        'telar.cerrar': a => sobreHilo(a, 'cerrar'),
        'telar.archivo': () => c.barra.alternarArchivo(),
        // sin id (el aviso de «2 cosas esperan»), a elegir; con una sola, esa (como en VS Code)
        'telar.equipoVer': async (id?: string) => { const e = await elegirEntrada(id); if (e) { c.mostrar('dashboard'); await c.hoy.abrirEquipo(e); } },
        'telar.equipo': async () => { const e = await elegirEntrada(); if (e) { c.mostrar('dashboard'); await c.hoy.abrirEquipo(e); } },
        // conectar el calendario: la dirección privada iCal (se escribe sin mostrarla: es secreta)
        'telar.conectarCalendario': async () => {
            const valor = await c.anfitrion.campo({
                title: 'Conectar calendario', password: true, ignoreFocusOut: true,
                prompt: 'La dirección privada de tu calendario en formato iCal. En Google Calendar: '
                    + 'Configuración › tu calendario › «Dirección secreta en formato iCal».',
                placeHolder: 'https://calendar.google.com/calendar/ical/…/basic.ics',
                validateInput: t => !t.trim() || /^https?:\/\/\S+$/.test(t.trim()) ? undefined : 'tiene que ser una dirección https://…',
            });
            if (!valor?.trim()) return;
            const r = await cli.elegirCalendario(valor.trim());
            if (!r.ok) { c.avisar({ __aviso: `telar: ${r.err.trim().split('\n').pop() || 'no pude conectar el calendario'}`, nivel: 'falla' }); return; }
            c.avisar({ __aviso: 'Calendario conectado.', nivel: 'info' });
            await c.hoy.actualizar(true);
        },
        'telar.seccion': (clave?: string) => { if (clave) { c.mostrar('dashboard'); return c.hoy.abrirSeccion(clave); } },
        'telar.app': (clave?: string) => { if (clave) { c.mostrar('dashboard'); return c.hoy.abrirApp(clave); } },
        'telar.tarea': (valor?: string) => valor ? c.hoy.abrirTarea(valor) : undefined,
        'telar.hoy': () => c.mostrar('dashboard'),
        'telar.actualizar': () => modelo.sondear(true),
        'telar.tejer': async () => { await cli.tejer(); await modelo.sondear(); },
        'telar.nuevo': async () => {
            const nombre = (await c.anfitrion.campo({
                title: 'Hilo nuevo', placeHolder: 'faro',
                prompt: 'Un tab con su agente. Después se vincula a un proyecto con ⋯.',
                validateInput: t => yaEsta(t.trim()),
            }))?.trim();
            if (!nombre) return;
            const remotos = (await cli.config()).datos?.remotos ?? [];
            let remoto = '';
            if (remotos.length) {
                const e = await c.anfitrion.elegir([{ label: 'Local', description: 'en esta máquina', remoto: '' },
                    ...remotos.map(r => ({ label: `Remoto: ${r.nombre}`, description: r.destino, remoto: r.nombre }))],
                    { placeHolder: `¿Dónde vive el agente de «${nombre}»?` });
                if (!e) return;
                remoto = e.remoto;
            }
            await c.anfitrion.irAHilo(nombre, true, remoto);
        },
        // la lista de tareas de la barra lateral es de VS Code: aquí las tareas están en el dashboard
        'telar.tareas': () => undefined,
        'telar.tareasActualizar': () => undefined,
    };
}
