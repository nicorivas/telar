// La ventana de mundos en el catálogo (/componentes#mundos): sus estados en cada tema, cada arte animado, y un lugar
// para probar uno nuevo escrito como en un archivo de la raíz. Con mundos de mentira: nada de lo que se aprieta aquí
// pone un mundo, dice qué haría. Lo vivo (animar el arte) es web/arte-vivo.ts, el mismo de la página.

import { esc } from '../estilo';
import { ALTO, ANCHO, artes, leerArteTexto, registrarArte, olvidarArte, type Arte } from './arte';
import './arte/index';
import { tarjetaMundo, tarjetasDeMundos, ventanaMundos, type TarjetaMundo } from './mundos-ventana';
import type { Mundo, MundoPuesto } from './modos-mundos';
import { animar, type Vivo } from '../web/arte-vivo';

/** una muestra del catálogo, con el tema y la densidad de su columna (catalogo.ts, `celda`) */
type Celda<C> = (c: C, html: string, clase?: string) => string;

const T = (dias: number[], desde: number, hasta: number) => ({ dias, desde: desde * 60, hasta: hasta * 60 });
/** los mundos de mentira, un lunes a las 10 */
const MUNDOS: Mundo[] = [
    { clave: 'trabajo', nombre: 'trabajo', color: 'cian', horario: [T([1, 2, 3, 4, 5], 9, 19)] },
    { clave: 'personal', nombre: 'personal', color: 'magenta', horario: [] },
];
const MAS: Mundo[] = [...MUNDOS,
    { clave: 'estudio', nombre: 'estudio', color: 'amarillo', horario: [T([6], 9, 13)] },
    { clave: 'huerta', nombre: 'huerta', color: 'verde', horario: [T([0], 8, 12)] }];
const AHORA = new Date(2026, 10, 23, 10, 0);
const HASTA = new Date(2026, 10, 23, 19, 0);

const ESTADOS: { nombre: string; nota: string; html: () => string }[] = [
    { nombre: 'quieta', nota: 'trabajo rige por su horario: su arte entero, los demás tenues; el foco en la de ahora (⏎ la deja)',
        html: () => ventanaMundos(tarjetasDeMundos({ mundo: 'trabajo', por: 'horario', hasta: HASTA, luego: 'personal' }, MUNDOS, AHORA, 'personal'),
            { aMano: false, estados: { 0: 'foco' } }) },
    { nombre: 'encima de personal', nota: 'el mouse (o el foco) encima: se ilumina en su color, el arte se enciende, se acelera y se inclina; un barrido la cruza',
        html: () => ventanaMundos(tarjetasDeMundos({ mundo: 'trabajo', por: 'horario', hasta: HASTA, luego: 'personal' }, MUNDOS, AHORA, 'personal'),
            { aMano: false, estados: { 1: 'hover' } }) },
    { nombre: 'ambos, a mano', nota: 'elegido a mano: dura hasta el próximo cambio del horario; «volver al horario» (h) lo suelta',
        html: () => ventanaMundos(tarjetasDeMundos({ mundo: '', por: 'a-mano', hasta: HASTA, luego: 'personal' }, MUNDOS, AHORA, 'personal'),
            { aMano: true }) },
    { nombre: 'cuatro mundos', nota: 'más de cuatro tarjetas: en filas parejas, y la última de una fila corta se estira hasta el borde',
        html: () => ventanaMundos(tarjetasDeMundos({ mundo: 'estudio', por: 'a-mano', hasta: HASTA, luego: 'trabajo' } as MundoPuesto, MAS, AHORA, 'personal'),
            { aMano: true }) },
];

/** «estados»: la ventana en cada estado, en cada tema elegido; «probar» la abre de verdad, con estos mundos de mentira. */
export function seccionEstados<C>(columnas: C[], celda: Celda<C>, nombreColumna: (c: C) => string): string {
    const h = ['<section class="cat-mundos">',
        '<p class="dim">Para cambiar de mundo (<code>componentes/mundos-ventana.ts</code>, <code>media/css/mundos.css</code>; lo vivo, '
        + '<code>web/mundos-ventana.ts</code>): la abren ⌘M, un clic en el mundo de la banda y «cambiar de mundo» en ⌘K. Una tarjeta por mundo y '
        + 'ambos al final: arriba su arte (<a href="#mundos/artes">los artes</a>), abajo su nombre en su color, su horario y si es el de ahora. '
        + 'Las líneas van de borde a borde; ninguna esquina redondeada; lo que distingue cada una es su color y su dibujo. Teclas: ← → ↑ ↓, 1…n, '
        + '⏎, h (volver al horario), e (editar), ⎋. Con «reducir movimiento», el arte quieto. En el teléfono, una bajo otra.</p>',
        '<p><a data-probar-mundos>probar</a><span class="dim"> · la abre de verdad con estos mundos de mentira: no pone ninguno, dice qué haría</span></p>'];
    for (const e of ESTADOS) {
        h.push(`<h3 class="cat-mundos-estado">${esc(e.nombre)}<span class="dim"> · ${esc(e.nota)}</span></h3><div class="cat-mundos-fila">`);
        for (const c of columnas) h.push(`<div class="cat-mundos-celda"><div class="cat-tema">${esc(nombreColumna(c))}</div>${celda(c, e.html())}</div>`);
        h.push('</div>');
    }
    h.push('</section>');
    return h.join('');
}

/** Un arte como tarjeta: su nombre, qué es y su ritmo (de fábrica o de la raíz, y a qué mundos va). */
const tarjetaDeArte = (a: Arte, i: number): TarjetaMundo => ({
    clave: `arte-${a.clave}`, nombre: a.nombre, arte: a.clave, puesto: false, tecla: undefined,
    color: ['cian', 'magenta', 'verde', 'amarillo', 'azul', 'violeta'][i % 6],
    horario: a.que || '—',
    estado: [`${a.clave}`, `${a.fps} fps, ${a.alHover.cuadros ? 'otra escena' : `${a.alHover.fps}`} encima`,
        a.origen === 'archivo' ? 'de la raíz' : 'de fábrica', a.para.length ? `para ${a.para.join(', ')}` : ''].filter(Boolean).join(' · '),
});

/** «los artes»: cada uno animado, en una tarjeta como la de la ventana (el mouse encima lo acelera), con el tema de la
 *  primera columna. */
export function seccionArtes<C>(columna: C, celda: Celda<C>): string {
    const lista = artes();
    const grilla = `<div class="ventana ventana-mundos centrada"><div class="mt-grilla cols-3" style="--mt-cols: 3">`
        + lista.map((a, i) => tarjetaMundo(tarjetaDeArte(a, i), { span: i === lista.length - 1 && lista.length % 3 ? 3 - (lista.length % 3) + 1 : undefined })).join('')
        + '</div></div>';
    return '<section class="cat-mundos">'
        + `<p class="dim">Cada arte es un módulo aparte (<code>componentes/arte.ts</code>): los de fábrica, en <code>componentes/arte/</code>; los de la raíz, `
        + `en <code>&lt;raiz&gt;/.telar/arte/&lt;clave&gt;.txt</code>, que telar entrega solo (<code>GET /arte</code>). Un mundo elige el suyo con `
        + `<code>[mundos.&lt;n&gt;] arte = "&lt;clave&gt;"</code> (o en ⚙ mundos); sin decirlo, el que se llama como él, uno que lo sugiere, o la órbita. `
        + `El lienzo mide ${ANCHO} × ${ALTO} letras. Cómo hacer uno: <code>docs/arte.md</code>, y <a href="#mundos/probar">probar uno</a>.</p>`
        + celda(columna, grilla, 'cat-mundos-artes') + '</section>';
}

const EJEMPLO = `nombre: faro
que: un faro que barre la noche
fps: 3
hover: 9
---
      *
     /|\\
    |▒|  ·      ·
   _|_|_ ~~~ ~~
---
   ·  *
     /|\\ ─ ─ ─
    |▒|  ·
   _|_|_  ~~~ ~~
---
      *
 ─ ─ /|\\
    |▒|     ·
   _|_|_ ~~ ~~~
`;

/** «probar uno»: escribir un arte como en un archivo de la raíz y verlo al tiro, en una tarjeta, animado. */
export function seccionProbar<C>(columna: C, celda: Celda<C>): string {
    return '<section class="cat-mundos cat-probar-arte">'
        + '<p class="dim">Escribe un arte como en un archivo de la raíz: los cuadros separados por una línea <code>---</code>; desde una '
        + '<code>--- hover</code>, la escena de cuando el mouse está encima; arriba, si quieres, <code>fps</code>, <code>hover</code> (fps encima), '
        + '<code>nombre</code>, <code>que</code> y <code>para</code> (los mundos que lo llevan sin decir <code>arte</code>). Se ve al lado, '
        + 'animado. Para usarlo: guárdalo en <code>&lt;raiz&gt;/.telar/arte/&lt;clave&gt;.txt</code> y ponlo en un mundo '
        + '(<code>[mundos.&lt;n&gt;] arte = "&lt;clave&gt;"</code>, o ⚙ mundos). Uno con código (una función del tiempo): '
        + '<code>docs/arte.md</code>.</p>'
        + '<div class="cat-probar-fila">'
        + `<textarea class="cat-probar-texto" spellcheck="false" rows="${ALTO + 14}">${esc(EJEMPLO)}</textarea>`
        + `<div class="cat-probar-lado">${celda(columna, `<div class="ventana ventana-mundos centrada cat-probar-ventana"><div class="mt-grilla cols-1" style="--mt-cols: 1">`
            + `${tarjetaMundo({ clave: 'prueba', nombre: 'prueba', color: 'cian', arte: 'prueba', horario: '', estado: '', puesto: false })}</div></div>`)}`
        + '<div class="cat-probar-dice dim"></div></div></div></section>';
}

let vivo: Vivo | undefined;

/** Después de pintar el catálogo: animar el arte que haya (y dejar de animar el de antes), y en «probar», leer lo
 *  escrito. */
export function despuesDePintar(raiz: HTMLElement): void {
    vivo?.parar();
    vivo = undefined;
    const texto = raiz.querySelector<HTMLTextAreaElement>('.cat-probar-texto');
    if (texto) {
        // la tarjeta de la prueba lleva el arte «prueba», aunque al dibujarse todavía no existiera
        const lienzo = raiz.querySelector<HTMLElement>('.cat-probar-ventana [data-arte]');
        if (lienzo) lienzo.dataset.arte = 'prueba';
        const leer = () => {
            const dice = raiz.querySelector<HTMLElement>('.cat-probar-dice');
            try {
                const { def, avisos } = leerArteTexto(texto.value);
                const a = registrarArte('prueba', { ...def, origen: 'archivo' });
                const tarjeta = raiz.querySelector<HTMLElement>('.cat-probar-ventana .mt-tarjeta');
                if (tarjeta) {
                    tarjeta.querySelector('.mt-nombre')!.textContent = a.nombre;
                    tarjeta.querySelector('.mt-horario')!.textContent = a.que || ' ';
                    tarjeta.querySelector('.mt-estado')!.textContent = `${Array.isArray(def.cuadros) ? def.cuadros.length : 0} cuadros · ${a.fps} fps`
                        + ` · ${a.alHover.cuadros ? `otra escena encima (${a.alHover.cuadros.length})` : `${a.alHover.fps} fps encima`}`;
                }
                if (dice) dice.textContent = avisos.length ? avisos.join(' · ') : 'se lee bien';
            } catch (e) {
                olvidarArte('prueba');
                if (dice) dice.textContent = (e as Error).message;
            }
        };
        texto.addEventListener('input', leer);
        leer();
    }
    if (raiz.querySelector('[data-arte]')) vivo = animar(raiz, { caja: '.mt-tarjeta' });
}

/** Un clic en el catálogo que es de esta página: una tarjeta o un botón de una ventana de muestra dicen qué harían;
 *  «probar» la abre de verdad. Devuelve si lo atendió. */
export function atender(t: HTMLElement, avisar: (texto: string) => void): boolean {
    if (t.closest('[data-probar-mundos]')) {
        void probar(avisar);
        return true;
    }
    const tarjeta = t.closest<HTMLElement>('.mt-tarjeta');
    if (tarjeta?.closest('.muestra')) {
        const m = tarjeta.dataset.mundo ?? '';
        avisar(m.startsWith('arte-') ? `el arte «${m.slice(5)}»` : `pondría ${m || 'ambos'}`);
        return true;
    }
    const b = t.closest<HTMLElement>('.ventana-mundos .boton');
    if (b?.closest('.muestra')) {
        avisar(b.dataset.accion === 'horario' ? 'volvería al horario' : b.dataset.accion === 'editar' ? 'iría a ⚙ mundos' : 'la cerraría');
        return true;
    }
    return false;
}

/** La ventana de verdad (web/mundos-ventana.ts) con los mundos de mentira: dice qué se eligió y no lo pone. */
async function probar(avisar: (texto: string) => void): Promise<void> {
    const W = await import('../web/mundos-ventana');
    const r = await W.abrir({ fuente: () => ({ puesto: { mundo: 'trabajo', por: 'horario', hasta: HASTA, luego: 'personal' }, mundos: MUNDOS, fuera: 'personal', ahora: AHORA }),
        elegir: x => avisar(x.horario ? 'volvería al horario' : `pondría ${x.mundo || 'ambos'}`), editar: () => avisar('iría a ⚙ mundos') });
    if (!r) avisar('se cerró sin elegir');
}
