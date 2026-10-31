// Las órdenes `telar.*` de la página (el menú de un hilo, ir a uno, retomarlo, abrir uno nuevo, abrir una
// sección…): las piden la barra y el dashboard (`ui.orden`), y las cumple esta página, con su interfaz
// (web/ui.ts) y lo que muestra a la derecha (src/navegador/app.ts).

import { PRIORIDAD } from '../estilo';
import { C, I } from './iconos';
import * as entidades from './entidades';
import * as ui from './ui';
import type { Opcion } from './ui';
import * as cli from '../cli';
import { modelo } from '../modelo';
import * as modos from './modos';
import { avisar } from './interfaz';
import { elegirEntrada } from '../vistas/dashboard/equipo';
import type { BarraHilos } from '../vistas/hilos';
import type { Dashboard } from '../vistas/dashboard/panel';

export interface Casa {
    hoy: Dashboard;
    barra: BarraHilos;
    /** a la derecha: «dashboard», un hilo, «doc:<hilo>» o «rem:<máquina>:<hilo>» */
    mostrar(que: string): void;
    /** cierra la terminal de un hilo que ya no tiene (lo archivaron o lo cerraron): no queda reconectando escondida */
    soltar(hilo: string): void;
    /** releer ya las fotos de las otras máquinas (lo que cambió allá llega en segundos) */
    releerOtras(): Promise<void>;
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
        if (!r.ok) { avisar(`telar: ${r.err.trim().split('\n').pop() || `«telar hilo ${verbo}» falló`}`, 'falla'); return false; }
        modelo.invalidar();
        await modelo.sondear();
        return true;
    }

    /** Archivar o descartar un hilo desde su fila: la fila lo dice mientras va (en otra máquina va por el bus y tarda), y
     *  si es el que se estaba mirando, al terminar se muestra lo que queda: archivado, su conversación; descartado, el
     *  dashboard (su terminal ya no existe). Descartar es `telar hilo cerrar`: lo termina y sale de la lista (la
     *  conversación queda en disco, sin botón para volver a ella). */
    async function sacar(a: unknown, verbo: 'archivar' | 'cerrar' | 'olvidar', haciendo: string): Promise<void> {
        const hilo = hiloDe(a);
        if (!hilo || modelo.ocupados.has(hilo)) return;
        modelo.ocupados.set(hilo, `${haciendo}…`);
        modelo.cambio.fire();
        // desde ya y hasta que deje de verse: «cerrando…», con el nombre apagado (allá tarda unos segundos)
        modelo.saliendo.set(hilo, { texto: verbo === 'archivar' ? 'archivando' : 'cerrando', hasta: Date.now() + 90_000 });
        try {
            const ok = await sobreHilo(a, verbo, verbo === 'archivar' ? ['--cerrar'] : []);
            if (!ok) modelo.saliendo.delete(hilo);
            // lo de la otra máquina (su foto) se relee seguido hasta que el hilo ya no aparece, a lo más un minuto
            else void (async () => {
                for (let i = 0; i < 30 && modelo.saliendo.has(hilo); i++) {
                    await c.releerOtras();
                    await modelo.sondear().catch(() => undefined);
                    await new Promise(r => setTimeout(r, 2000));
                }
            })();
            // descartar uno archivado o dormido: deja de estar en la lista; si se lo miraba, vuelve al dashboard
            if (ok) c.soltar(hilo);
            if (ok && c.barra.mostrado === hilo) c.mostrar(verbo === 'archivar' ? hilo : 'dashboard');
            if (ok) ui.estado(`«${hilo}» ${verbo === 'archivar' ? 'archivado' : 'descartado'}`, 4000);
        } finally {
            modelo.ocupados.delete(hilo);
            modelo.cambio.fire();
        }
    }

    /** Descartar un hilo: vivo, se termina y sale de la lista; archivado o dormido, sale del archivo (telar olvida su
     *  carpeta, su prioridad y su atención), después de preguntar: no hay cómo volver a él desde la lista. */
    async function descartar(hilo: string): Promise<void> {
        const h = modelo.porNombre(hilo);
        if (!h) return;
        if (h.vivo && !h.archivado) { await sacar(hilo, 'cerrar', 'descartándolo'); return; }
        const si = await ui.aviso(`¿Descartar «${hilo}»? Sale del archivo y telar olvida su carpeta, su prioridad y su atención (su conversación queda en disco).`, 'Descartar');
        if (si === 'Descartar') await sacar(hilo, 'olvidar', 'descartándolo');
    }

    /** El menú de un hilo (el ⋯ de su fila): lo que se puede hacer con él, según esté
     *  vivo, archivado o vinculado. Cada acción es una orden `telar hilo …`. */
    async function menuHilo(a: unknown): Promise<void> {
        await entidades.menuDe(`hilo:${hiloDe(a)}`, (a as { donde?: { x: number; y: number } } | undefined)?.donde);
    }

    // lo que se puede hacer con un hilo, para su menú (web/entidades.ts): según esté vivo, archivado o vinculado
    entidades.registrar('hilo', async hilo => {
        const h = modelo.porNombre(hilo);
        if (!hilo || !h) return undefined;
        type Fila = entidades.AccionEntidad;
        const prioridad = (n: string, nombre: string): Fila => ({ label: `prioridad ${nombre}`, description: String(h.prioridad ?? '') === n ? 'la que tiene' : '',
            icono: PRIORIDAD[Number(n) || 0], color: C.cambiar,
            hacer: () => sobreHilo(hilo, 'prioridad', [], n) });
        const filas: Fila[] = [
            { label: h.archivado || !h.vivo ? 'retomar' : 'ver', icono: h.archivado || !h.vivo ? I.retomar : I.ver, color: C.ir, description: h.archivado || !h.vivo ? 'reabre su tab con su conversación' : '',
                hacer: async () => { if (h.archivado || !h.vivo) { if (await sobreHilo(hilo, 'retomar')) c.mostrar(hilo); } else c.mostrar(hilo); } },
            { label: 'renombrar', icono: I.renombrar, color: C.cambiar, description: 'se mueve con él lo que telar sabía', hacer: async () => {
                const nombre = await ui.campo({ titulo: `Nombre nuevo para «${hilo}»`, valor: hilo });
                if (nombre && nombre !== hilo) await sobreHilo(hilo, 'renombrar', [], nombre);
            } },
            ...(h.vinculado ? [{ label: 'ver su carpeta y documento', icono: I.carpeta, color: C.ir, description: h.relativa || h.ruta, hacer: async () => c.mostrar(`doc:${hilo}`) }] : []),
            { label: 'vincular a un proyecto', icono: I.vincular, color: C.cambiar, description: h.relativa ? `hoy: ${h.relativa}` : 'sin carpeta', hacer: () => vincularWeb(hilo) },
            ...(h.vinculado ? [{ label: 'desvincular', icono: I.desvincular, color: C.cambiar, description: 'soltar su carpeta', hacer: () => sobreHilo(hilo, 'desvincular') }] : []),
            { label: 'etiquetas…', icono: I.etiqueta, color: C.cambiar,
                description: h.etiquetas?.length ? `hoy: ${h.etiquetas.join(', ')}` : 'trabajo, personal…: los modos filtran la lista por ellas',
                hacer: () => etiquetarWeb(hilo, h.etiquetas ?? []) },
            ...(modelo.hayBus ? [h.publico
                ? { label: 'hacer privado', icono: I.privado, color: C.cambiar, description: 'hoy es público: las otras personas lo ven en EQUIPO; deja de salir', hacer: () => sobreHilo(hilo, 'privar') }
                : { label: 'hacer público', icono: I.publico, color: C.cambiar, description: 'que las otras personas del bus lo vean en EQUIPO y le escriban (su nombre y carpeta; nunca la conversación)',
                    hacer: () => sobreHilo(hilo, 'publicar') }] : []),
            { label: 'prioridad', separador: true },
            prioridad('1', 'alta'), prioridad('2', 'media'), prioridad('3', 'baja'), prioridad('ninguna', 'ninguna'),
            { label: 'archivar o descartar', separador: true },
            ...(h.archivado ? [{ label: 'desarchivar', icono: I.desarchivar, color: C.ir, description: 'volver a la lista sin abrirlo', hacer: () => sobreHilo(hilo, 'desarchivar') }]
                : [{ label: 'archivar', icono: I.archivar, color: C.cambiar, description: 'lo guarda en ARCHIVO con su conversación, para retomarlo', hacer: () => sacar(hilo, 'archivar', 'archivándolo') }]),
            // descartar: vivo, se termina y sale de la lista; dormido o archivado, telar lo olvida (carpeta, prioridad)
            h.vivo && !h.archivado
                ? { label: 'descartar', icono: I.descartar, color: C.quitar, description: 'lo termina y lo saca de la lista, sin guardarlo', hacer: () => sacar(hilo, 'cerrar', 'descartándolo') }
                : { label: 'descartar', icono: I.descartar, color: C.quitar, description: 'sale del archivo: telar olvida su carpeta, su prioridad y su atención', hacer: () => descartar(hilo) },
            ...(!h.remoto ? [{ label: 'llevar a otra máquina', icono: I.llevar, color: C.otro, description: 'su conversación viaja; los archivos no', hacer: () => llevarWeb(hilo) }]
                : [{ label: 'traer a esta máquina', icono: I.traer, color: C.otro, description: `vive en ${h.remoto}: su conversación viaja aquí; los archivos no`, hacer: () => traerWeb(hilo, h.remoto ?? '') }]),
        ];
        return { titulo: hilo, acciones: filas };
    });

    /** Las etiquetas de un hilo: se escriben todas (separadas por coma); vacío las quita. Se sugieren las que ya se
     *  usan y las de los modos. */
    async function etiquetarWeb(hilo: string, actuales: string[]): Promise<void> {
        const usadas = new Set(modelo.hilos.flatMap(x => x.etiquetas ?? []));
        for (const m of modos.lista()) for (const e of String(m.valores.etiquetas ?? '').split(',')) if (e) usadas.add(e);
        const texto = await ui.campo({
            titulo: `Etiquetas de «${hilo}»`, valor: actuales.join(', '), placeholder: 'trabajo, personal',
            ayuda: `separadas por coma; vacío las quita${usadas.size ? ` · en uso: ${[...usadas].sort().join(', ')}` : ''}`,
            validar: t => t.split(/[,\s]+/).every(e => !e || /^#?[a-z0-9áéíóúüñ][a-z0-9áéíóúüñ-]{0,23}$/i.test(e)) ? undefined
                : 'minúsculas, números y guiones; hasta 24 letras cada una',
        });
        if (texto === undefined) return;
        await sobreHilo(hilo, 'etiquetas', [], texto.trim() || 'ninguna');
    }

    /** Vincular desde la web: se elige entre los proyectos del perfil, o se escribe una ruta. */
    async function vincularWeb(hilo: string): Promise<void> {
        const r = await cli.proyectos();
        const otra = { label: 'otra carpeta…', description: 'escribir su ruta', ruta: '' };
        const filas = [...(r.datos?.proyectos ?? []).map(p => ({ label: p.nombre, description: p.ruta, ruta: String(p.ruta) })), otra];
        const elegida = await ui.elegir(filas, { titulo: `Vincular «${hilo}» a…`, placeholder: 'filtrar' });
        if (!elegida) return;
        const ruta = elegida.ruta || await ui.campo({ titulo: `La carpeta de «${hilo}»`, ayuda: 'relativa a la raíz del repositorio, o absoluta' });
        if (ruta) await sobreHilo(hilo, 'vincular', [], ruta);
    }

    /** Llevar un hilo a otra máquina de [remotos]: si aquí hay trabajo sin subir, se pregunta antes. */
    /** Traer a esta máquina un hilo que vive en otra tuya: aquella lo lleva por el bus (telar.mudanza). Con trabajo
     *  sin subir allá, se pregunta, como al llevar. */
    async function traerWeb(hilo: string, maquina: string): Promise<void> {
        if (!hilo || !maquina) return;
        avisar(`trayendo «${hilo}» desde ${maquina}… (una conversación larga tarda)`, 'info', 6000);
        let r = await cli.traer(hilo, maquina);
        if (r.error && /sin subir/.test(r.error)) {
            const salida = String(r.cuerpo?.salida ?? '');
            const lista = salida.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
            const si = await ui.aviso(`La conversación de «${hilo}» viaja, los archivos no. En ${maquina} hay trabajo que aquí no va a estar:\n${lista}`, 'Traer igual');
            if (si !== 'Traer igual') return;
            r = await cli.traer(hilo, maquina, true);
        }
        if (r.error) { avisar(`telar: ${r.error}`, 'falla'); return; }
        avisar(`«${hilo}» ya está aquí`, 'info', 5000);
        modelo.invalidar();
        await modelo.sondear();
    }

    async function llevarWeb(hilo: string): Promise<void> {
        // las de [remotos] (por ssh) y las otras tuyas que se ven en el bus, en línea (por el bus: telar.mudanza)
        const remotos = ((await cli.config()).datos?.remotos ?? []).map(x => ({ nombre: x.nombre, destino: `${x.destino} · por ssh` }));
        const delBus = ((await cli.espejos()).datos?.espejos ?? [])
            .filter(e => e.en_linea && !e.error && !remotos.some(r => r.nombre === e.nombre))
            .map(e => ({ nombre: e.nombre, destino: 'tuya, por el bus' }));
        const destinos = [...remotos, ...delBus];
        if (!destinos.length) { avisar('telar: no hay otra máquina: ni en [remotos] ni en línea en el bus', 'aviso'); return; }
        const elegida = destinos.length === 1 ? destinos[0]
            : (await ui.elegir(destinos.map(x => ({ label: x.nombre, description: x.destino, x })), { titulo: `¿A qué máquina llevo «${hilo}»?` }))?.x;
        if (!elegida) return;
        // la transición a la vista (web/mudanza.ts): letras grandes, barra, pasos; al llegar, a su terminal allá
        const { llevar } = await import('./mudanza');
        // al llegar: el hilo de una máquina del bus se mira desde aquí (su terminal allá); uno de [remotos] sigue en su tab
        const porElBus = delBus.some(x => x.nombre === elegida.nombre);
        await llevar(hilo, elegida.nombre, () => { c.mostrar(porElBus ? `rem:${elegida.nombre}:${hilo}` : hilo); });
    }


    return {
        'telar.menuHilo': a => menuHilo(a),
        // un hilo de otra máquina: se lee como conversación y se le escribe por el bus (aquí no hay su terminal)
        // el ⋯ de un hilo de otra máquina (de su foto): verlo, o traerlo a esta
        'telar.menuRemoto': async (id?: string) => {
            const [maq, ...resto] = String(id ?? '').split('|');
            const hilo = resto.join('|');
            if (!maq || !hilo) return;
            const e = await ui.elegir([
                { label: 'ver', description: 'su conversación, y escribirle por el bus', id: 'ver' },
                { label: 'traer a esta máquina', description: `vive en ${maq}: su conversación viaja aquí; los archivos no`, id: 'traer' },
            ], { titulo: `${hilo} · en ${maq}` });
            if (e?.id === 'ver') c.mostrar(`rem:${maq}:${hilo}`);
            else if (e?.id === 'traer') await traerWeb(hilo, maq);
        },
        'telar.irRemoto': (id?: string) => { const [maq, ...resto] = String(id ?? '').split('|'); if (maq && resto.length) c.mostrar(`rem:${maq}:${resto.join('|')}`); },
        // en la web, ir a un hilo es mostrar su terminal a la derecha (no mover la ventana de tmux de nadie)
        'telar.ir': a => c.mostrar(hiloDe(a)),
        // una pestaña del dashboard (el grupo DASHBOARD de la barra, el ⚙ de la cabecera)
        'telar.pestana': (accion: string, valor = '') => c.hoy.irAPestana(accion, valor),
        'telar.retomar': async a => { if (await sobreHilo(a, 'retomar')) c.mostrar(hiloDe(a)); },
        // mostrarlo sin abrir nada: uno archivado o cerrado se ve en su conversación, con «retomar»
        'telar.ver': a => { const h = hiloDe(a); if (h) c.mostrar(h); },
        'telar.archivar': a => sacar(a, 'archivar', 'archivándolo'),
        'telar.cerrar': a => sacar(a, 'cerrar', 'descartándolo'),
        'telar.descartar': a => descartar(hiloDe(a)),
        'telar.archivo': () => c.barra.alternarArchivo(),
        // sin id (el aviso de «2 cosas esperan»), a elegir; con una sola, esa
        'telar.equipoVer': async (id?: string) => { const e = await elegirEntrada(id); if (e) { c.mostrar('dashboard'); await c.hoy.abrirEquipo(e); } },
        // escribirle a un hilo de otra persona (la sección EQUIPO de la barra): a su casilla, por el bus
        'telar.escribirColega': async (id?: string) => {
            const [persona, ext, nombre] = JSON.parse(String(id ?? '[]')) as string[];
            if (!persona || !ext) return;
            const escrito = await ui.escribir({ titulo: `a ${persona} · ${nombre ?? ext}`,
                ayuda: `le llega a la casilla de ese hilo, como un correo tuyo (${persona}+${ext}). ⌘⏎ envía.`,
                placeholder: '¿qué le dices?' });
            if (!escrito?.texto.trim()) return;
            const r = await cli.escribirColega(persona, ext, escrito.texto);
            if (!r.datos) void ui.falla(`telar: no le llegó a ${persona}: ${r.error ?? 'sin respuesta'}`);
            else void ui.estado(`telar: en la casilla de «${nombre ?? ext}», de ${persona}`, 5000);
        },
        'telar.agentesVer': async () => { c.mostrar('dashboard'); await c.hoy.abrirAgentes(); },
        // un agente residente nuevo: su carpeta con CLAUDE.md y agente.toml (lo mismo que `telar agentes nuevo`)
        'telar.agenteNuevo': async () => {
            const nombre = (await ui.campo({
                titulo: 'Agente nuevo', placeholder: 'Faro',
                ayuda: 'Un agente residente: vive en su carpeta, con su memoria y su bitácora, y le encargas cosas.',
            }))?.trim();
            if (!nombre) return;
            const para = (await ui.campo({
                titulo: `Para qué es «${nombre}»`, placeholder: 'Revisar cómo van los proyectos y avisar lo que se atrasó.',
                ayuda: 'En una o dos frases: cuándo encargarle algo. Se puede dejar vacío y escribirlo después en su agente.toml.',
            }))?.trim() ?? '';
            const r = await cli.nuevoAgente(nombre, para);
            if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
            avisar(`Agente ${r.datos.nombre} en ${r.datos.carpeta}. Escribe en su CLAUDE.md qué hace.`, 'info');
            await modelo.sondear(true);
        },
        'telar.equipo': async () => { const e = await elegirEntrada(); if (e) { c.mostrar('dashboard'); await c.hoy.abrirEquipo(e); } },
        // conectar el calendario: la dirección privada iCal (se escribe sin mostrarla: es secreta)
        'telar.conectarCalendario': async () => {
            const valor = await ui.campo({
                titulo: 'Conectar calendario', password: true,
                ayuda: 'La dirección privada de tu calendario en formato iCal. En Google Calendar: '
                    + 'Configuración › tu calendario › «Dirección secreta en formato iCal».',
                placeholder: 'https://calendar.google.com/calendar/ical/…/basic.ics',
                validar: t => !t.trim() || /^https?:\/\/\S+$/.test(t.trim()) ? undefined : 'tiene que ser una dirección https://…',
            });
            if (!valor?.trim()) return;
            const r = await cli.elegirCalendario(valor.trim());
            if (!r.ok) { avisar(`telar: ${r.err.trim().split('\n').pop() || 'no pude conectar el calendario'}`, 'falla'); return; }
            avisar('Calendario conectado.', 'info');
            await c.hoy.actualizar(true);
        },
        'telar.seccion': (clave?: string) => { if (clave) { c.mostrar('dashboard'); return c.hoy.abrirSeccion(clave); } },
        'telar.app': (clave?: string) => { if (clave) { c.mostrar('dashboard'); return c.hoy.abrirApp(clave); } },
        'telar.tarea': (valor?: string) => valor ? c.hoy.abrirTarea(valor) : undefined,
        'telar.hoy': () => c.mostrar('dashboard'),
        'telar.actualizar': () => modelo.sondear(true),
        'telar.tejer': async () => { await cli.tejer(); await modelo.sondear(); },
        'telar.nuevo': async () => {
            const nombre = (await ui.campo({
                titulo: 'Hilo nuevo', placeholder: 'faro',
                ayuda: 'Un tab con su agente. Después se vincula a un proyecto con ⋯.',
                validar: t => yaEsta(t.trim()),
            }))?.trim();
            if (!nombre) return;
            const remotos = (await cli.config()).datos?.remotos ?? [];
            let remoto = '';
            if (remotos.length) {
                const e = await ui.elegir([{ label: 'Local', description: 'en esta máquina', remoto: '' },
                    ...remotos.map(r => ({ label: `Remoto: ${r.nombre}`, description: r.destino, remoto: r.nombre }))],
                    { placeholder: `¿Dónde vive el agente de «${nombre}»?` });
                if (!e) return;
                remoto = e.remoto;
            }
            await ui.irAHilo(nombre, true, remoto);
        },
    };
}
