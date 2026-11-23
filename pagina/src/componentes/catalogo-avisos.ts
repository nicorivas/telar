// La franja de avisos en el catálogo (/componentes#avisos): sus escenas en cada tema (catalogo.ts las pone en la grilla),
// cómo se ve en la página entera (#avisos/ver/<escena>[/abierta|/plegada|/hilo], también para las capturas) y de dónde
// sale cada aviso: quién lo pone, cuándo se va y dónde se decía antes. Lo que se aprieta aquí no hace nada: dice qué haría.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { item } from './item';
import { franja, punto, type AvisoFranja } from './franja';
import { AVISOS, ESCENAS, escena } from './muestras-avisos';

/** Arriba de la barra, como en la página: la franja y las primeras filas de la barra (para ver dónde va). */
function enLaBarra(html: string): string {
    const filas = item({ variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo: 'dashboard' })
        + item({ variante: 'enlace', activa: true, inicio: [null], titulo: 'táctica', meta: { texto: 'a' } })
        + item({ variante: 'enlace', inicio: [null], titulo: 'calendario', meta: { texto: 'c' } });
    return `<div class="franja-lugar">${html}</div><div class="cat-franja-filas">${filas}</div>`;
}

const CALMA = 'al día · 11:45';
const CALMA_AYUDA = 'sin avisos: la lista de hilos se leyó a las 11:45:02';

/** Las filas de «estados»: cada escena en la barra, la lista abierta, la barra plegada y el punto del teléfono. */
export function filasEstados(): { nombre: string; nota: string; html: string; alto?: boolean }[] {
    const f = (avisos: AvisoFranja[], o: { abierta?: boolean; plegada?: boolean } = {}) =>
        enLaBarra(franja({ avisos, calma: CALMA, calmaAyuda: CALMA_AYUDA, plegable: true, ...o }));
    const varios = escena('varios').avisos;
    const cab = (avisos: AvisoFranja[]) => '<div class="cat-franja-cab"><a class="cab-volver"><span class="i">'
        + `${I.atras}</span><span class="txt"> hilos</span><span class="franja-punto-lugar">${punto(avisos)}</span></a></div>`;
    return [
        ...ESCENAS.map(e => ({ nombre: e.nombre, nota: e.nota, html: f(e.avisos) })),
        { nombre: 'la lista abierta', nota: 'Un clic en la franja: cada aviso con desde cuándo, qué pasó, qué hacer y sus botones; un clic en el aviso va a su lugar. Encima de la barra y de lo de al lado; un clic afuera o ⎋ la cierran.',
            html: f(varios, { abierta: true }), alto: true },
        { nombre: 'la barra plegada', nota: 'Solo el ícono del más grave, en su color; la lista se abre igual, más ancha que la barra. Tranquila, vacía (el lugar queda: su línea calza).',
            html: `<div class="cat-franja-plegadas">${[[AVISOS.conexion], [AVISOS.calendario], varios, []].map(l => `<div>${franja({ avisos: l, plegada: true })}</div>`).join('')}</div>` },
        { nombre: 'el teléfono, viendo un hilo', nota: 'Sin barra a la vista: un punto en el color del más grave junto a «‹ hilos», que lleva a la lista (con la franja arriba). Una nota sola (una máquina apagada) no lo pone. En foco, el mismo punto va en el botón de salir.',
            html: [[AVISOS.conexion], [AVISOS.calendario], [AVISOS.pagina], [AVISOS.maquina]].map(cab).join('') },
    ];
}

/** La página entera: la franja de una escena (abierta o plegada) y el punto del teléfono. `null` si la escena no existe. */
export function enLaPagina(clave: string, extra = ''): { franja: string; punto: string; nombre: string } | null {
    const e = ESCENAS.find(x => x.clave === clave);
    if (!e) return null;
    return {
        franja: `<div class="franja-lugar">${franja({ avisos: e.avisos, calma: CALMA, calmaAyuda: CALMA_AYUDA, abierta: extra === 'abierta', plegada: extra === 'plegada', plegable: true })}</div>`,
        punto: punto(e.avisos), nombre: e.nombre,
    };
}

/** «en la página»: cada escena a pantalla completa (para verla como se vería, y sacar las capturas) y cómo ensayarla en la
 *  página de verdad. */
export function seccionPagina(): string {
    const enlace = (ruta: string, texto: string) => `<a href="#avisos/ver/${ruta}" target="_blank">${esc(texto)}</a>`;
    const filas = ESCENAS.map(e => `<li><b>${esc(e.nombre)}</b>: ${enlace(e.clave, 'laptop o teléfono')} · ${enlace(`${e.clave}/abierta`, 'con la lista abierta')}`
        + ` · ${enlace(`${e.clave}/plegada`, 'con la barra plegada')} · ${enlace(`${e.clave}/hilo`, 'en el teléfono, viendo un hilo')}</li>`);
    return '<section class="cat-tactica">'
        + '<p class="dim">La página entera, con la cabecera, la barra de hilos de mentira con la franja arriba y Táctica a la derecha (sus '
        + 'líneas de abajo calzan). El ancho de la ventana decide si es un laptop o un teléfono (700px o menos): en el teléfono se ve la lista, '
        + 'con la franja arriba si hay algo que decir, o con «/hilo», lo que se ve con un hilo abierto (el punto junto a «‹ hilos»).</p>'
        + `<ul>${filas.join('')}</ul>`
        + '<p class="dim">En la página de verdad, sin que nada falle: <code>window.telar.ensayoAvisos(\'varios\')</code> en la consola (también '
        + '<code>sin-conexion</code>, <code>fuente</code> y <code>ninguno</code>, que los quita; con <code>true</code> de segundo argumento, la lista '
        + 'abierta). Sus botones solo dicen qué harían. Los de verdad siguen: si la página pierde la conexión, se ve el suyo.</p></section>';
}

/** «de dónde sale»: cada aviso, quién lo pone, cuándo se va y dónde se decía antes. */
const FUENTES: readonly [string, string, string, string, string][] = [
    ['sin conexión con telar', 'sin conexión', 'web/vigia.ts, con cada lectura de los hilos: la API no contesta hace 15 s', 'apenas contesta', 'una nota arriba de la lista de hilos; sin ninguna lista, el error en su lugar'],
    ['telar no pudo leer los hilos', 'falla', 'web/vigia.ts: la API contestó, con un error', 'al leerlos', 'la misma nota, como si fuera la conexión'],
    ['la sesión no está viva / tejida', 'falla', 'web/vigia.ts: /hilos dice que la sesión no vive (o por qué no hay multiplexor)', 'al tejerla', 'notas arriba de la lista; sin hilos, en su lugar'],
    ['«X» abierto aquí y en otra máquina', 'falla', 'web/vigia.ts: un hilo vivo aquí y en la foto de otra', 'al cerrar uno', 'un ícono de alerta en su fila'],
    ['la terminal de «X» se cortó', 'falla', 'web/terminal.ts: el WebSocket se cerró y no volvió en 4 s', 'al reconectar', 'una línea escrita en la terminal'],
    ['no se pudo leer el calendario (un proveedor)', 'falla', 'dashboard/dia.ts: /hoy, al consultar los proveedores', 'cuando vuelve a contestar', '«caído · …» arriba de cada pantalla del dashboard'],
    ['«te esperan» sin una fuente', 'falla', 'dashboard/esperas.ts: /esperas trae `fallas` (o no se pudo leer)', 'al leerse entera', 'una línea arriba de «te esperan» y de Táctica'],
    ['no se pudo leer un bloque (el correo…)', 'falla', 'dashboard/bloques.ts: /bloques/<clave> contestó con un error', 'al leerse', 'en rojo, en su pestaña'],
    ['página nueva', 'aviso', 'web/version.ts, con web/recarga.ts: se desplegó otra mientras se mira', 'al recargar', 'arriba a la izquierda, junto a la versión'],
    ['telar 0.x / puerta 0.x', 'aviso', 'web/version.ts: /version, cada 20 minutos', 'al instalarla', 'arriba a la izquierda, junto a la versión'],
    ['retenido: «X» → «Y» / N mensajes retenidos', 'aviso', 'web/detenidos.ts, con lo que lee dashboard/esperas.ts: un mensaje que el freno de cadenas retuvo en las últimas 24 h', 'al soltarlo (o pasadas 24 h: sigue en «te esperan»)', 'solo en «te esperan»: un «listo» retenido dejaba esperando a un hijo y a su padre'],
    ['«X» espera que confíes en una carpeta', 'aviso', 'web/vigia.ts con web/detenidos.ts, de los hilos: telar.confiar (el nodo, cada 30 s) vio en su panel la pregunta de Claude Code de confiar en una carpeta', 'al contestarla en el hilo', 'en ninguna parte: sin ganchos, el hilo no decía nada y esperaba horas'],
    ['lo que dice un archivo de aviso (su línea)', 'problema (mal) o falla (aviso)', 'web/avisos-archivos.ts: GET /avisos, cada minuto; lo dice un JSON que deja un programa (`[avisos.<clave>]`, telar.avisos)', 'cuando dice ok, o pasada una hora sin escribirse', 'en ninguna parte: había que ir a mirar el archivo'],
    ['máquina sin noticias', 'nota', 'web/vigia.ts: la foto de otra máquina no está al día y trae hilos vivos', 'cuando vuelve a publicar', 'solo sus filas apagadas (siguen así)'],
];

export function seccionFuentes(): string {
    const filas = FUENTES.map(([que, nivel, quien, cuando, antes]) =>
        `<div>${esc(que)}</div><div class="dim">${esc(nivel)}</div><div>${esc(quien)}</div><div class="dim">${esc(cuando)}</div><div class="dim">${esc(antes)}</div>`).join('');
    return '<section class="cat-tactica">'
        + '<p class="dim">Lo que pasa aunque nadie apriete nada: el estado del sistema y de los hilos. Quien lo sabe lo pone en '
        + '<code>web/avisos.ts</code> y lo quita apenas deja de pasar; la franja (<code>web/franja.ts</code>) lo dibuja. Una cosa, un lugar: '
        + 'lo que está aquí ya no se dice donde se decía. Lo que espera a la persona (Táctica, «te esperan») no viene: es trabajo, y tiene '
        + 'su lugar. Salvo lo que, sin aviso, se queda callado: un mensaje retenido por el freno de cadenas, que quien lo mandó da por '
        + 'entregado, y un hilo detenido en la pregunta de confiar en una carpeta (<code>web/detenidos.ts</code>). Los toasts de abajo a la derecha siguen siendo para responder a lo que se aprieta.</p>'
        + `<div class="cat-tac-tabla cat-franja-tabla"><b>el aviso</b><b>nivel</b><b>quién lo pone</b><b>se va</b><b>antes</b>${filas}</div></section>`;
}

/** Lo que dice un clic en la franja de mentira. */
export function dice(a: HTMLElement): string {
    const clave = a.dataset.clave ?? '';
    const aviso = Object.values(AVISOS).find(x => x.clave === clave);
    if (a.dataset.accion === 'franja-ir') return `iría a ${aviso?.ir ?? 'su lugar'}`;
    if (a.dataset.accion === 'franja-accion') return `haría «${aviso?.acciones?.find(x => x.id === a.dataset.valor)?.texto ?? a.dataset.valor}»`;
    if (a.dataset.accion === 'franja-plegar') return 'plegaría la barra de hilos (un cambio en el modo puesto)';
    if (a.dataset.accion === 'franja-desplegar') return 'mostraría la barra de hilos';
    return 'abriría (o cerraría) la lista de avisos';
}
