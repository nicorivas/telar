// La franja de avisos en la página: arriba de la barra de hilos (#barra; marco.css la deja fija mientras la lista corre
// debajo), del alto de la barra de la pantalla de al lado. Dibuja lo que guarda web/avisos.ts con el componente
// (componentes/franja.ts), despliega la lista con un clic y atiende sus botones. Tranquila, dice cuándo se leyó la lista
// de hilos por última vez.
//
// Donde no hay barra a la vista, un punto en el color del aviso más grave dentro del botón que la muestra: «‹ hilos» en
// el teléfono viendo un hilo, y el de salir de foco (cabecera y barra ocultas). A la derecha, el ‹ que pliega la barra
// (el modo puesto lo recuerda, web/modos.ts); con la barra plegada, la franja queda con solo el ícono, y la barra se abre
// desde su franja angosta (vistas/hilos.ts).
//
// Para probarla sin que nada falle: `window.telar.ensayoAvisos('<escena>')` en la consola (componentes/muestras-avisos.ts:
// ninguno, sin-conexion, fuente, varios; con `true` de segundo argumento, la lista abierta).

import * as avisos from './avisos';
import { franja, punto } from '../componentes/franja';
import { ESCENAS, escena } from '../componentes/muestras-avisos';
import { modelo } from '../modelo';
import * as modos from './modos';
import * as ui from './ui';

let lugar: HTMLElement | undefined;
let abierta = false;

/** Lo que el modo puesto no muestra: el aviso de versión (y de página nueva), con `aviso_version = oculto` (foco). */
const oculto = (clave: string) => document.body.dataset.aviso_version === 'oculto' && (clave === 'version' || clave === 'pagina-nueva');

/** Sin avisos: cuándo se leyó la lista de hilos por última vez (lo que dice que la página está al día). */
function calma(): { texto: string; ayuda: string } {
    const t = modelo.leidoA;
    if (!t) return { texto: '', ayuda: 'sin avisos' };
    return { texto: `al día · ${avisos.hora(t)}`, ayuda: `sin avisos: la lista de hilos se leyó a las ${new Date(t).toTimeString().slice(0, 8)}` };
}

/** Dibujar la franja y los puntos con lo que hay ahora. */
export function pintar(): void {
    const l = avisos.vigentes(oculto).map(a => avisos.paraDibujar(a));
    if (abierta && !l.length) abierta = false;
    if (lugar) {
        const c = calma();
        const html = franja({ avisos: l, calma: c.texto, calmaAyuda: c.ayuda, abierta, plegada: modos.valor('barra') === 'plegada', plegable: true });
        if (lugar.innerHTML !== html) lugar.innerHTML = html;
    }
    // el punto, dentro de los botones que muestran la barra: siempre al final de lo suyo (salir de foco se rehace al
    // cambiar de modo, y entonces se pone de nuevo)
    const p = punto(l);
    for (const id of ['volver', 'salir-modo']) {
        const b = document.getElementById(id);
        if (!b) continue;
        let s = b.querySelector<HTMLElement>(':scope > .franja-punto-lugar');
        if (!s) { s = document.createElement('span'); s.className = 'franja-punto-lugar'; b.appendChild(s); }
        if (s.innerHTML !== p) s.innerHTML = p;
    }
}

function cerrar(): void {
    if (!abierta) return;
    abierta = false;
    pintar();
}

/** Ponerla arriba de la barra (`barra`: #barra, ya con su lista adentro). */
export function montar(barra: HTMLElement): void {
    lugar = document.createElement('div');
    lugar.id = 'franja';
    lugar.className = 'franja-lugar';
    barra.prepend(lugar);
    lugar.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-accion]');
        if (!a) return;
        e.preventDefault();
        if (a.dataset.accion === 'franja-abrir') { abierta = !abierta; pintar(); return; }
        // plegar la barra: un cambio en el modo puesto, como lo era desde su primera cabecera (alCambiar la redibuja)
        if (a.dataset.accion === 'franja-plegar') { abierta = false; modos.poner('barra', 'plegada'); return; }
        const clave = a.dataset.clave ?? '';
        if (a.dataset.accion === 'franja-ir' || a.dataset.accion === 'franja-accion') {
            abierta = false;
            pintar();
            if (!avisos.hacer(clave, a.dataset.accion === 'franja-accion' ? a.dataset.valor : undefined)) ui.estado('ese aviso ya no está');
        }
    });
    // abierta, un clic afuera o ⎋ la cierran (⎋ no sigue: el dashboard lo tomaría como suyo)
    document.addEventListener('mousedown', e => { if (abierta && !lugar?.contains(e.target as Node)) cerrar(); }, true);
    window.addEventListener('keydown', e => { if (abierta && e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrar(); } }, true);
    avisos.alCambiar(pintar);
    modelo.cambio.event(pintar);
    modos.alCambiar(pintar);
    // desde cuándo («hace 3 min») y la hora de la calma, al día aunque nada cambie
    setInterval(pintar, 30 * 1000);
    pintar();
}

// ── el ensayo: los avisos de mentira del catálogo, en la página de verdad ──

/** Poner los avisos de una escena (componentes/muestras-avisos.ts), sin que nada falle: sus botones solo dicen qué harían.
 *  `ninguno` los quita. Con `abrir`, la lista abierta. Devuelve qué se puso. */
export function ensayo(clave = 'varios', abrir = false): string {
    const e = escena(clave);
    for (const otra of ESCENAS) for (const a of otra.avisos) avisos.quitar(`ensayo:${a.clave}`);
    const ahora = Date.now();
    e.avisos.forEach((a, i) => avisos.poner({
        clave: `ensayo:${a.clave}`, nivel: a.nivel, icono: a.icono, texto: a.texto, detalle: a.detalle, hacer: a.hacer, curso: a.curso,
        desde: ahora - (i + 1) * 4 * 60 * 1000, cuando: a.nivel === 'nota' ? 'hace' : 'desde',
        ir: a.ir ? { texto: a.ir, hacer: () => ui.estado(`(ensayo) iría a ${a.ir}`) } : undefined,
        acciones: a.acciones?.map(x => ({ ...x, hacer: () => ui.estado(`(ensayo) haría «${x.texto}»`) })),
    }));
    abierta = abrir && e.avisos.length > 0;
    pintar();
    return `${e.nombre}: ${e.avisos.length} ${e.avisos.length === 1 ? 'aviso' : 'avisos'} de mentira`;
}
