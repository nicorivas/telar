// Los avisos de mentira de la franja (componentes/franja.ts): los del catálogo (/componentes#avisos) y los del ensayo de
// la página (`window.telar.ensayoAvisos('<estado>')`, web/franja.ts). Cada estado es una escena: ninguno, sin conexión,
// una fuente que falla, varios a la vez. Los nombres son inventados (los hilos de la barra de mentira: componentes/muestras.ts).

import { I } from '../web/iconos';
import { AYUDA_VISTO } from '../web/avisos-archivos';
import type { AvisoFranja } from './franja';

/** Los avisos de las escenas, uno por clase: lo que dice cada uno y sus botones, como los pone la página. */
// el ✓ de un aviso de archivo (web/avisos-archivos.ts): lo da por visto hasta que cambie
const VISTO = { id: 'visto', texto: '✓ visto', ayuda: AYUDA_VISTO };

export const AVISOS: Record<string, AvisoFranja> = {
    conexion: {
        clave: 'conexion', nivel: 'conexion', icono: I.desconectado, texto: 'sin conexión con telar', cuando: 'desde las 11:32',
        detalle: 'La página no recibe respuesta de telar: lo que se ve es lo último que se supo.',
        hacer: 'Si se estaba reiniciando (un despliegue, una versión nueva), vuelve sola. Si no, revisa que telar serve corra en laptop y que haya red.',
        acciones: [{ id: 'reintentar', texto: 'reintentar' }],
    },
    calendario: {
        clave: 'fuente:calendario', nivel: 'falla', icono: I.fecha, texto: 'no se pudo leer el calendario', cuando: 'desde las 11:40',
        detalle: 'calendario: la consulta tardó más de 20 s. La agenda es la de la última vez.',
        hacer: 'Se vuelve a pedir sola; si sigue, revisa de dónde sale la agenda.', ir: '⚙ calendario',
    },
    correo: {
        clave: 'fuente:bloque:correo', nivel: 'falla', icono: I.correo, texto: 'no se pudo leer el correo', cuando: 'desde las 11:41',
        detalle: 'correo: la cuenta pidió entrar de nuevo.', hacer: 'Se vuelve a pedir solo; si sigue, revisa su módulo en ⚙ módulos.',
        ir: 'la pestaña correo', acciones: [{ id: 'releer', texto: 'leerlo de nuevo' }],
    },
    terminal: {
        clave: 'terminal:faro', nivel: 'falla', icono: I.desconectado, texto: 'la terminal de «faro» se cortó', cuando: 'hace 1 min',
        detalle: 'Se reconecta sola, cada vez más espaciado (hasta cada 15 s).',
        ir: 'el hilo faro', acciones: [{ id: 'reconectar', texto: 'reconectar ahora' }],
    },
    dos: {
        clave: 'dos:Telar', nivel: 'falla', icono: I.alerta, texto: '«Telar» abierto aquí y en servidor',
        detalle: 'Son dos conversaciones del mismo hilo, que se separan.', hacer: 'Cierra una (archivar o descartar, en su ⋯).', ir: 'el hilo Telar',
    },
    pagina: {
        clave: 'pagina-nueva', nivel: 'aviso', icono: I.releer, texto: 'página nueva', cuando: 'desde las 11:20',
        detalle: 'Se desplegó después de abrir esta.', hacer: 'Recargarla: lo escrito y lo que miras se quedan.',
        acciones: [{ id: 'recargar', texto: 'recargar' }],
    },
    version: {
        clave: 'version', nivel: 'aviso', icono: I.actualizar, texto: 'telar 0.13.1', cuando: 'desde las 9:05',
        detalle: 'Hay una versión nueva de telar (corre la 0.13.0).',
        hacer: 'Se instala y se reinicia el servicio: la página vuelve sola y los hilos no se cortan.',
        acciones: [{ id: 'instalar', texto: 'instalar' }], ir: '⚙ versión',
    },
    retenido: {
        clave: 'retenidos', nivel: 'aviso', icono: I.pausa, texto: 'retenido: «Vitrina» → «Catálogo»', cuando: 'hace 20 min',
        detalle: 'El freno de cadenas retuvo el mensaje de «Vitrina» → «Catálogo» (cadena de 7 mensajes entre hilos sin que hablara la persona (tope 6)). No llegó, y quien lo mandó cree que sí.',
        hacer: 'Míralo en «te esperan» y suéltalo si está bien (o `telar mensaje --soltar <id>`); si no, cuéntale al hilo que lo mandó.',
        ir: 'te esperan',
    },
    confiar: {
        clave: 'confiar:Catálogo', nivel: 'aviso', icono: I.carpeta, texto: '«Catálogo» espera que confíes en una carpeta', cuando: 'hace 4 min',
        detalle: 'Claude Code pregunta si confías en ~/worktrees/vitrina-catalogo (--add-dir) antes de arrancar: contéstalo en el hilo (telar no lo contesta). Mientras nadie la conteste, el hilo no hace nada.',
        hacer: 'Ve al hilo y contesta la pregunta de Claude Code (si es el worktree de su rama, «Yes, add it»). telar no la contesta: es tuya.',
        ir: 'el hilo Catálogo',
    },
    archivo: {
        clave: 'archivo:equipo', nivel: 'falla', icono: I.campana, texto: 'el disco está al 92%', cuando: 'hace 12 min',
        detalle: 'equipo · medido a las 11:33 · 3 sugerencias en el informe.', hacer: 'El informe dice qué pasa y qué hacer. Abrirlo lo da por visto.',
        ir: 'el informe', acciones: [VISTO],
    },
    archivoMal: {
        clave: 'archivo:respaldo', nivel: 'problema', icono: I.campana, texto: 'el respaldo de anoche no corrió', cuando: 'hace 40 min',
        detalle: 'respaldo, en servidor · medido a las 11:05.', hacer: 'El informe dice qué pasa y qué hacer. Abrirlo lo da por visto.',
        ir: 'el informe', acciones: [VISTO],
    },
    maquina: {
        clave: 'maquina:servidor', nivel: 'nota', icono: I.remoto, texto: 'servidor sin noticias', cuando: 'hace 3 h',
        detalle: 'Su última foto es de hace 3 h: sus hilos se ven como estaban.',
        hacer: 'Si está apagada o durmiendo, es lo normal; si no, revisa su telar serve y el bus.', ir: 'máquinas',
    },
};

/** Las escenas: qué avisos hay en cada una, y cómo se llama. */
export const ESCENAS: readonly { clave: string; nombre: string; nota: string; avisos: AvisoFranja[] }[] = [
    { clave: 'ninguno', nombre: 'sin avisos', avisos: [],
        nota: 'Tranquila: dice en tenue cuándo se leyó la lista por última vez. El lugar queda (su línea calza con la de la pantalla de al lado). En el teléfono, sin avisos, no está.' },
    { clave: 'sin-conexion', nombre: 'sin conexión', avisos: [AVISOS.conexion],
        nota: 'La API no contesta hace más de 15 s (un reinicio, que dura menos, no se dice). Rojo, y solo ella. Lo que necesita a telar (una fuente, una terminal) se calla mientras tanto: la falla es la misma. Vuelve sola.' },
    { clave: 'fuente', nombre: 'una fuente que falla', avisos: [AVISOS.calendario],
        nota: 'El calendario no contestó: el resto del día sí. Antes se decía arriba de cada pantalla del dashboard («caído · calendario»); ahora, aquí. Un clic en el aviso lleva a ⚙ calendario.' },
    { clave: 'varios', nombre: 'varios avisos', avisos: [AVISOS.maquina, AVISOS.version, AVISOS.calendario, AVISOS.terminal, AVISOS.dos, AVISOS.pagina, AVISOS.retenido, AVISOS.confiar, AVISOS.archivo, AVISOS.archivoMal],
        nota: 'Lo más grave a la vista, con «+9»; un clic abre la lista entera, de lo más grave a lo menos, cada uno con qué hacer y adónde lleva. Un hilo abierto aquí y en otra máquina, que antes era un ícono en su fila, también va aquí.' },
];

export const escena = (clave: string) => ESCENAS.find(e => e.clave === clave) ?? ESCENAS[0];
