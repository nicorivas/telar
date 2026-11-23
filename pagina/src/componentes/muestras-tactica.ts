// Los días de mentira de Táctica, para el catálogo (/componentes#tactica) y el ensayo en la página
// (`window.telar.ensayoTactica()`): un día como lo da `telar hoy` (la agenda y las tareas), su plan, lo que espera como
// lo da `telar esperas` y los proyectos como los da `telar proyectos` (para nombrar las cuentas), armados por la vista de
// verdad (vistas/dashboard/tactica.ts: la urgencia, las cuentas, lo que cabe). Inventados: la librería de barrio de las
// muestras de «Contestar» (sus hilos, su boletín, su vitrina), con sus cuentas (la feria, el colegio que compra el plan
// lector, la distribuidora), y el día de la jornada de muestra (componentes/muestras.ts). Nada de aquí es de nadie.
//
// Dos juegos de lo que espera: el que declara lo que piden los agentes (`SENALES`: la vía, el peso, quién espera, la fecha
// dura, las opciones, lo que dejó hecho; urgencia.ts, CAMPOS), el de casi todos los estados; y el de hoy, sin nada declarado (el estado «hoy»: casi todo
// queda sin clasificar).

import type * as cli from '../cli';
import { DIA_EJEMPLO } from './muestras';
import type { Disposicion, Tactica } from './tactica';
import { CAMPOS, type Senales, deEspera, delPlan, ordenar, porque } from '../vistas/dashboard/urgencia';
import { type DatosTactica, type PestanaDeTactica, type ProyectoDeCuenta, armar } from '../vistas/dashboard/tactica';
import type { Dia } from '../vistas/dashboard/dia';
import type { Plan } from '../vistas/dashboard/plan';

/** El día de las muestras: un martes. */
export const FECHA = '2026-11-17';
const a = (hhmm: string) => Date.parse(`${FECHA}T${hhmm}:00`);
/** La fecha de `n` días después del de las muestras (negativo: antes), AAAA-MM-DD en la hora de esta máquina. */
const dia = (n: number) => {
    const d = new Date(`${FECHA}T12:00:00`);
    d.setDate(d.getDate() + n);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const dosCifras = (n: number) => String(n).padStart(2, '0');
/** Una hora del día (en minutos) como «09:30». */
const hhmm = (m: number) => `${dosCifras(Math.floor(m / 60))}:${dosCifras(m % 60)}`;
/** Una hora del día (en minutos) como un instante del día de las muestras. */
const instante = (m: number) => a(hhmm(m));
const hm = (h: number, m = 0) => h * 60 + m;

/** El plan del día de mentira: pone hoy dos tareas en sus tácticos y una en el bloque estratégico; dice qué se decide en
 *  dos reuniones y qué hay que llevar a una; y el foco del día. */
export const PLAN: Plan = {
    tacticos: { hoy: [{ ref: 'T28', texto: 'el boletín' }, { ref: 'T42', texto: 'la vitrina' }] },
    agenda: [
        { inicio: '09:30', fin: '11:00', titulo: 'Foco: el informe', tipo: 'bloque', clase: 'estrategico', tareas: ['T44'] },
        { inicio: '11:30', fin: '12:30', titulo: 'Revisión de diseño', tipo: 'reunion',
            ficha: { decision: 'si la vitrina de diciembre lleva la foto de la feria o un dibujo' } },
        { inicio: '15:00', fin: '16:00', titulo: 'Comité', tipo: 'reunion',
            ficha: { decision: 'el presupuesto de la feria', llevar: ['los tres escenarios del presupuesto'] } },
    ],
    foco: { prioridad: 'el informe del trimestre', paso: 'el índice del informe y sus tres primeras secciones', terminado: 'el índice está aprobado' },
};

/** Los proyectos de la librería, como los da `telar proyectos`: los de un cliente se juntan en su cuenta; los de la casa
 *  (`interno`), cada uno en la suya. */
export const PROYECTOS: ProyectoDeCuenta[] = [
    { ruta: 'casa/feria', nombre: 'Feria del Libro · Stand de diciembre', cliente: 'Feria del Libro' },
    { ruta: 'casa/feria-charlas', nombre: 'Feria del Libro · Ciclo de charlas', cliente: 'Feria del Libro' },
    { ruta: 'casa/colegio', nombre: 'Colegio del Valle · Plan lector 2027', cliente: 'Colegio del Valle' },
    { ruta: 'casa/compras', nombre: 'Distribuidora del Sur · Compras', cliente: 'Distribuidora del Sur' },
    { ruta: 'casa/boletin', nombre: 'Boletín', interno: true },
    { ruta: 'casa/vitrina', nombre: 'Vitrina', interno: true },
    { ruta: 'casa/inventario', nombre: 'Inventario', interno: true },
    { ruta: 'casa/tienda', nombre: 'Tienda', interno: true },
    { ruta: 'casa/caja', nombre: 'Caja', interno: true },
];

/** Un renglón de `telar hoy`: un evento de la agenda o una tarea. */
const fila = (x: Partial<cli.JsonFila> & { texto: string; id: string }): cli.JsonFila => ({
    hecho: false, en_curso: false, origen: 'tareas', ref: x.id, hilo: '', ruta: '', proveedor: '', cuando: null, url: '', ...x,
});
/** La agenda del día de mentira (la de la jornada de muestra): las reuniones con gente y dónde conectarse; el bloque
 *  propio y el almuerzo, sin. */
const AGENDA: cli.JsonFila[] = DIA_EJEMPLO.map((t, i) => fila({
    texto: t.titulo, id: `ev${i}`, clase: 'evento', cuando: `${FECHA}T${hhmm(t.inicio)}:00`, fin: `${FECHA}T${hhmm(t.fin)}:00`,
    ...t.clase === 'reunion' ? { asistentes: ['uno@ejemplo.org', 'dos@ejemplo.org', 'tres@ejemplo.org', 'cuatro@ejemplo.org'],
        url: `https://reunion.ejemplo.org/${i}`, respuesta: 'aceptada' as const } : { asistentes: [] },
}));
/** Las tareas de la persona (y una de otra persona, que no va): las que vencen hoy, las que el plan pone hoy, y otras;
 *  y las que tienen algo de un agente (van a Decidir, o a Hacer si piden hacer: de aquí sale su tamaño). */
const tarea = (id: string, texto: string, mas: Partial<cli.JsonFila> = {}) => fila({ texto, id, ref: id, proveedor: 'tareas', ficha: true,
    direccion: `tarea:${id}`, prioridad: 2, ...mas });
const TAREAS: cli.JsonFila[] = [
    tarea('T40', 'Mandar el pedido de diciembre a la distribuidora', { cuando: FECHA, proyecto: 'casa/compras', tamano: 'rapida' }),
    tarea('T42', 'Armar la vitrina con la foto elegida', { proyecto: 'casa/vitrina', tamano: 'larga' }),
    tarea('T44', 'Llamar a la imprenta por el papel', { proyecto: 'casa/compras', tamano: 'rapida' }),
    tarea('T45', 'Pagar la cuenta de la luz', { cuando: dia(2), proyecto: 'casa/caja', tamano: 'rapida' }),
    tarea('T46', 'Ordenar la bodega', { proyecto: 'casa/tienda', tamano: 'larga' }),
    tarea('T47', 'Pedir presupuesto de los estantes', { cuando: dia(9), proyecto: 'casa/tienda' }),
    tarea('T48', 'Revisar el contrato del local', { cuando: dia(-60), proyecto: 'casa/caja' }),
    tarea('T49', 'Cuadrar la caja de noviembre', { dueno: 'Otra persona', cuando: FECHA, proyecto: 'casa/caja' }),
    tarea('T71', 'Colegio del Valle: firmar la cotización del plan lector', { proyecto: 'casa/colegio', tamano: 'rapida', avance: 'preparado 2026-11-17' }),
    tarea('T74', 'Feria del Libro: pagar la cuota del stand', { proyecto: 'casa/feria', tamano: 'rapida', avance: 'pregunta 2026-11-16' }),
];

/** El día de mentira como lo da `telar hoy`. */
const DIA: Dia = { ahora: `${FECHA}T11:45:00`, fecha: FECHA, nombreDia: 'martes', semana: 47, agenda: AGENDA, pendientes: TAREAS,
    declarados: ['calendario', 'tareas'], fallas: [] };

/** Las pestañas de las fuentes, para el pie: el correo, los mensajes (con su aviso) y las lecturas. */
const PESTANAS: PestanaDeTactica[] = [
    { clave: 'bloque:correo', accion: 'bloque', valor: 'correo', nombre: 'correo', aviso: '' },
    { clave: 'bloque:mensajes', accion: 'bloque', valor: 'mensajes', nombre: 'mensajes', aviso: '3 chats sin leer' },
    { clave: 'pestana:leer', accion: 'pestana', valor: 'leer', nombre: 'leer', aviso: '' },
];

/** Una espera como las de `telar esperas`. */
const espera = (direccion: string, clase: string, desde: string, titulo: string, mas: Partial<cli.JsonEspera> = {}): cli.JsonEspera => ({
    direccion, tipo: direccion.split(':')[0], clase, desde, titulo, resumen: '', enlaces: [], ...mas,
});
/** Lo que un agente dejó en una tarea (`avance:<marca>`): su texto, como la última línea `[avance]`, y su proyecto. */
const avance = (id: string, marca: string, desde: string, titulo: string, texto: string, proyecto = '', campos: Record<string, unknown> = {}): cli.JsonEspera =>
    espera(`tarea:${id}`, `avance:${marca.split(':')[0]}`, desde, titulo, {
        enlaces: proyecto ? [`proyecto:${proyecto}`] : [], resumen: texto,
        campos: { avance: `${marca} ${desde.slice(0, 10)}`, prioridad: 2, version: 'v1', texto, ...campos },
    });

/** Las esperas del día de mentira, de lo que bloquea a lo que no. */
export const ESPERAS: Record<string, cli.JsonEspera> = {
    permiso: espera('permiso:Inventario', 'permiso', `${FECHA}T11:43:00`, 'Permiso para correr el conteo del inventario',
        { enlaces: ['hilo:Inventario', 'proyecto:casa/inventario'], campos: { hilo: 'Inventario', pide: 'Claude needs your permission to use Bash' } }),
    vivo: espera('permiso:Vitrina', 'pregunta', `${FECHA}T11:41:00`, '¿Qué foto va en la vitrina de diciembre?',
        { enlaces: ['hilo:Vitrina', 'proyecto:casa/vitrina'], resumen: 'La del árbol de libros · La de la feria · Ninguna: un dibujo',
            campos: { hilo: 'Vitrina', pregunta: 'p-1', preguntas: [{ pregunta: '¿Qué foto va en la vitrina de diciembre?', encabezado: 'Foto', varias: false,
                opciones: [{ etiqueta: 'La del árbol de libros' }, { etiqueta: 'La de la feria' }, { etiqueta: 'Ninguna: un dibujo' }] }] } }),
    retenido: espera('mensaje:m-7f3a', 'retenido', `${FECHA}T10:10:00`, '«Vitrina» → «Catálogo»',
        { enlaces: ['hilo:Catálogo', 'hilo:Vitrina'], resumen: 'Te paso la lista de los doce libros de la vitrina…',
            campos: { de: 'Vitrina', para: 'Catálogo', modo: 'pedido', motivo: 'cadena de 7 mensajes entre los mismos dos hilos',
                texto: 'Te paso la lista de los doce libros de la vitrina de diciembre, para que revises si están en el catálogo.' } }),
    retenido2: espera('mensaje:m-8b21', 'retenido', `${FECHA}T10:12:00`, '«Catálogo» → «Vitrina»',
        { enlaces: ['hilo:Vitrina', 'hilo:Catálogo'], resumen: 'Revisé la lista: faltan dos…',
            campos: { de: 'Catálogo', para: 'Vitrina', modo: 'respuesta', motivo: 'cadena de 7 mensajes entre los mismos dos hilos', texto: 'Revisé la lista: faltan dos.' } }),
    T70: avance('T70', 'pregunta', `${dia(-1)}T16:40:00`, 'Colegio del Valle: el pedido del plan lector 2027',
        '16-nov 16:40: el colegio pide 300 ejemplares de los ocho títulos del plan lector y un 12% de descuento; con el 12% el margen queda '
        + 'en 9% · falta: ¿aceptamos el 12% ($1,8M en total) o contraofertamos un 8%?', 'casa/colegio', { vence: FECHA }),
    T25: avance('T25', 'preparado', `${dia(-2)}T11:00:00`, 'Feria del Libro: presupuesto del stand',
        '15-nov 11:00: tres escenarios en casa/feria/presupuesto.md; recomiendo el del medio · falta: aprobar el stand doble ($2,4M) antes del Comité',
        'casa/feria', { vence: dia(4) }),
    T31: avance('T31', 'pregunta', `${dia(-1)}T18:20:00`, 'Inventario: partirlo en dos',
        'sigue viva: el conteo de diciembre no cabe en un día · falta: ¿parto el inventario en dos, la bodega y la tienda?', 'casa/inventario', { vence: FECHA }),
    T28: avance('T28', 'preparado', `${FECHA}T08:05:00`, 'Borrador del boletín de diciembre',
        '17-nov 08:00: quedó el borrador en casa/boletin/diciembre.md, con las tres reseñas · falta: el borrador del boletín de diciembre, con las tres reseñas', 'casa/boletin'),
    T19: avance('T19', 'cerrar:caduca', `${dia(-2)}T09:00:00`, 'Renovar el convenio con la distribuidora', 'se renovó solo por un año más',
        'casa/compras', { como: 'caduca', vence: dia(-3) }),
    T12: avance('T12', 'cerrar:hecha', `${dia(-1)}T09:30:00`, 'Pedir las bolsas de papel a la imprenta', 'llegaron ayer: 500 bolsas con el logo nuevo',
        'casa/compras', { como: 'hecha', vence: dia(3), contexto: 'Pedir 500 bolsas a la imprenta del barrio.' }),
    T22: avance('T22', 'cerrar:descartada', `${dia(-6)}T12:00:00`, 'Cotizar estantes nuevos', 'se usan los de la bodega', 'casa/tienda',
        { como: 'descartada', prioridad: 3 }),
    T26: avance('T26', 'pregunta', `${dia(-3)}T10:00:00`, 'Feria del Libro: el ciclo de charlas',
        '14-nov 10:00: la feria ofrece tres horarios para la charla de la librería · falta: ¿quién la da: tú o la encargada de la tienda?', 'casa/feria-charlas'),
    T71: avance('T71', 'preparado', `${FECHA}T09:10:00`, 'Colegio del Valle: firmar la cotización del plan lector',
        '17-nov 09:10: la cotización está en casa/colegio/cotizacion.md con los dos precios; el colegio la pide firmada · falta: firmar la cotización y '
        + 'mandarla escaneada cuando decidas el descuento', 'casa/colegio'),
    T74: avance('T74', 'pregunta', `${dia(-1)}T12:00:00`, 'Feria del Libro: pagar la cuota del stand',
        '16-nov 12:00: el portal de la feria pide tu clave · falta: pagar la cuota del stand ($180 mil) antes del viernes', 'casa/feria',
        { vence: dia(3) }),
    T72: avance('T72', 'pregunta', `${dia(-4)}T15:00:00`, 'Seguro del local: renovarlo',
        '13-nov 15:00: la misma compañía sube la prima un 6% ($38 mil al mes) · falta: ¿renuevo igual o cotizo con otras dos?'),
    T73: avance('T73', 'preparado', `${dia(-2)}T17:00:00`, 'Responder a la vecina por el ruido de la obra',
        '15-nov 17:00: dejé un borrador amable en el correo · falta: la respuesta a la vecina, con el horario de la obra'),
    resena: espera('pregunta:casa/2026-11-14-donde-sale-la-resena', 'decide', `${dia(-3)}T09:30:00`, '¿Dónde sale la reseña de «El libro de la feria»?',
        { enlaces: ['agente:boletin', 'archivo:casa/boletin/preguntas/2026-11-14-donde-sale-la-resena.md'],
            resumen: 'La reseña está lista. Puede salir en el boletín del viernes, o esperar a la página de reseñas.',
            campos: { urgencia: 'alta', vence: dia(7), de: 'agente:boletin', repo: 'casa', recomendada: 'boletin', version: 'a1b2c3',
                opciones: [{ id: 'boletin', texto: 'En el boletín del viernes', accion: '', recomendada: true, marcada: false },
                    { id: 'pagina', texto: 'En la página de reseñas', accion: '', recomendada: false, marcada: false }] } }),
    diaBoletin: espera('pregunta:casa/2026-11-16-que-dia-sale', 'decide', `${dia(-1)}T16:00:00`, '¿Qué día sale el boletín de diciembre?',
        { enlaces: ['agente:boletin', 'archivo:casa/boletin/preguntas/2026-11-16-que-dia-sale.md'], campos: { urgencia: 'media', de: 'agente:boletin', repo: 'casa', version: 'b2',
            opciones: [{ id: 'lunes', texto: 'El lunes 1', accion: '', recomendada: true, marcada: false }, { id: 'viernes', texto: 'El viernes 5', accion: '', recomendada: false, marcada: false }] } }),
    T8: avance('T8', 'pregunta', '2026-10-05T10:00:00', 'Imprenta: seguir con la del barrio',
        '5-oct 10:00: la del barrio subió un 15% · falta: ¿seguimos con ella o cotizamos otra?', 'casa/compras'),
    // vencida hace más de 30 días: es deuda, y no entra
    T3: avance('T3', 'pregunta', '2026-09-20T10:00:00', 'Archivar las facturas de 2024', 'falta: ¿las archivo?', 'casa/caja', { vence: '2026-09-30', prioridad: 1 }),
};

/** Lo que declaran los agentes (urgencia.ts, CAMPOS): va delante del texto de su línea `[avance]`, o en la primera línea
 *  del resumen de una pregunta. */
const c = CAMPOS;
export const SENALES: Record<string, string> = {
    T70: `${c.pide}=decidir · ${c.peso}=alto (el pedido más grande del año) · ${c.persona}=el colegio · ${c.opciones}=aceptar el 12% | contraofertar un 8%* | consultarlo con la contadora`,
    T25: `${c.pide}=aprobar · ${c.peso}=alto (compromete $2,4M) · ${c.dura}=${dia(2)} · ${c.artefacto}=casa/feria/presupuesto.md`,
    T26: `${c.pide}=decidir · ${c.peso}=medio (la feria lo pide esta semana) · ${c.opciones}=la doy yo* | la encargada de la tienda`,
    T31: `${c.pide}=decidir · ${c.peso}=medio (cambia cómo se cuenta diciembre) · ${c.opciones}=en dos días* | en uno, cerrando la tienda`,
    T28: `${c.pide}=aprobar · ${c.peso}=bajo (sale igual el viernes) · ${c.artefacto}=casa/boletin/diciembre.md`,
    T19: `${c.pide}=cerrar · ${c.peso}=bajo`,
    T12: `${c.pide}=cerrar · ${c.peso}=bajo`,
    T22: `${c.pide}=cerrar · ${c.peso}=bajo`,
    T71: `${c.pide}=hacer-tu · ${c.peso}=alto (el colegio la espera firmada) · ${c.persona}=el colegio`,
    T74: `${c.pide}=hacer-tu · ${c.peso}=medio (sin pago no hay stand) · ${c.dura}=${dia(3)}`,
    T72: `${c.pide}=decidir · ${c.peso}=medio ($456 mil al año) · ${c.opciones}=renovar igual | cotizar con otras dos*`,
    T73: `${c.pide}=aprobar · ${c.peso}=bajo`,
    T8: `${c.pide}=decidir · ${c.peso}=bajo (la próxima compra es en enero)`,
    resena: `${c.peso}: medio (la feria es en dos semanas)`,
};

/** Lo contestado que espera al agente, como lo da `telar esperas` (`contestadas`): dos de la mañana de mentira (a una ya
 *  se la encargaste, con «revisar ya») y una de ayer en la tarde, con una instrucción. */
export const CONTESTADAS: cli.JsonContestada[] = [
    { direccion: 'tarea:T15', titulo: 'Pedido de papel de regalo', cuando: `${FECHA}T11:20:00`, respuesta: 'aprobado: envíalo',
        encargada: `${FECHA}T11:42:00`, enlaces: ['proyecto:casa/tienda'] },
    { direccion: 'tarea:T27', titulo: 'Fecha del boletín de diciembre', cuando: `${FECHA}T10:05:00`, respuesta: 'el lunes 1, como siempre', enlaces: ['proyecto:casa/boletin'] },
    { direccion: 'tarea:T33', titulo: 'Saldos de la editorial', cuando: `${dia(-1)}T18:30:00`,
        respuesta: 'quedémonos con los de poesía · instrucción: pregúntale a la editorial si los reponen en enero', enlaces: ['proyecto:casa/compras'] },
];

/** Los periódicos como los da `telar periodicos` desde el servidor de mentira: el que pasa por las tareas, cada hora de 7
 *  a 22 (su próxima corrida, la de después de `m`), y otro que no es la pasada. */
export function periodicosA(m: number): cli.JsonPeriodicos {
    const sig = Array.from({ length: 16 }, (_, i) => hm(7 + i)).find(x => x > m);
    const proxima = sig === undefined ? `${dia(1)}T07:00:00` : `${FECHA}T${hhmm(sig)}:00`;
    const proceso = (nombre: string, cuando: string, mensaje: string, prox: string): cli.JsonPeriodico => ({
        nombre, cuando, tipo: 'mensaje', comando: '', mensaje, hilo: '', max_abiertos: 1, argumentos: [], carpeta: '', descripcion: '', activo: true,
        proxima: prox, ultima: {}, agente: 'avances' });
    return { maquina: 'servidor', archivo: '~/.config/telar/periodicos.toml', zona: '', procesos: [
        proceso('correo', '40 8,12,17 * * 1-5', '/correo', `${FECHA}T12:40:00`), proceso('pulso', '0 7-22 * * *', '/pulso', proxima)] };
}

/** Una espera con lo que declara su agente (SENALES): en una tarea, delante de su texto; en una pregunta, en su resumen. */
function conSenales(k: string, e: cli.JsonEspera): cli.JsonEspera {
    const s = SENALES[k];
    if (!s) return e;
    if (e.clase === 'decide') {
        const resumen = `${s}\n${e.resumen}`;
        return { ...e, resumen, campos: { ...e.campos, secciones: { resumen } } };
    }
    const texto = `${s} · ${String(e.campos?.texto ?? '')}`;
    return { ...e, resumen: texto, campos: { ...e.campos, texto } };
}

/** Más esperas, para el día en que se juntan demasiadas: lo que dejaron preparado o preguntado otros agentes. */
const MAS_TITULOS = ['Ordenar las fotos de la feria', 'Responder a la editorial por los saldos', 'Lista de libros para el club de lectura',
    'Precio de los marcapáginas', 'Horario de diciembre', 'Carta a los socios', 'Reponer los cuentos infantiles', 'Revisar la caja chica',
    'El cartel de la vitrina de enero', 'Inventario de los usados', 'La encuesta del boletín', 'Ofertas para el día del libro'];
const MAS: cli.JsonEspera[] = MAS_TITULOS.map((titulo, i) => avance(`T${60 + i}`, i % 3 ? 'preparado' : 'pregunta',
    `${dia(-1 - (i % 9))}T${String(9 + (i % 8)).padStart(2, '0')}:15:00`, titulo,
    i % 3 ? `${c.pide}=aprobar · ${c.peso}=${i % 2 ? 'bajo' : 'medio'} · quedó listo · falta: «${titulo.toLowerCase()}»`
        : `${c.pide}=decidir · ${c.peso}=bajo · falta: ¿${titulo.toLowerCase()} esta semana o en enero?`,
    ['casa/tienda', 'casa/feria', 'casa/boletin', 'casa/caja', ''][i % 5], i % 5 === 0 ? { vence: dia(2 + (i % 4)) } : {}));

/** Un estado del día de mentira: lo que tendría que decir, y lo que arma la vista con él. */
export interface EstadoTactica {
    clave: string; nombre: string; nota: string;
    /** lo que recibe la vista: el día, el plan, lo que espera, la hora, las pestañas de las fuentes y los proyectos */
    datos: DatosTactica;
    /** Táctica armada, en una disposición y con esas cuentas desplegadas */
    tactica: (d: Disposicion, abiertas?: readonly string[]) => Tactica;
}

const BASE = ['vivo', 'retenido', 'retenido2', 'T70', 'T25', 'T26', 'T31', 'T28', 'T19', 'T12', 'T22', 'T71', 'T74', 'T72', 'T73', 'resena', 'diaBoletin'];
const de = (claves: string[], mas: cli.JsonEspera[] = [], senales = true) =>
    [...claves.map(k => (senales ? conSenales(k, ESPERAS[k]) : ESPERAS[k])), ...mas];

function estado(clave: string, nombre: string, nota: string, m: number, esperas: cli.JsonEspera[], o: { sinPlan?: boolean; contestadas?: boolean } = {}): EstadoTactica {
    const datos: DatosTactica = { dia: { ...DIA, ahora: `${FECHA}T${hhmm(m)}:00` }, plan: o.sinPlan ? undefined : PLAN, esperas, ahora: instante(m),
        pestanas: PESTANAS, proyectos: PROYECTOS, ...o.contestadas ? { contestadas: CONTESTADAS, periodicos: periodicosA(m), agente: 'Avances' } : {} };
    return { clave, nombre, nota, datos, tactica: (d, abiertas) => ({ ...armar({ ...datos, abiertas }).tactica, disposicion: d }) };
}

export const ESTADOS: EstadoTactica[] = [
    estado('reunion', 'en una reunión', 'a las 11:45, en la Revisión de diseño: su ficha arriba, con lo que se decide. Lo que espera, en sus tres '
        + 'vías, cada una por cuenta y por peso (el círculo: alto lleno, medio a medias, bajo un aro): decidir con sus opciones (la recomendada '
        + 'marcada), aprobar con lo que dejó hecho, cerrar con su prueba. Arriba, la pregunta en vivo de un hilo; los dos mensajes retenidos entre '
        + 'hilos, al pie; abajo, lo que contestaste y espera al agente, con su próxima pasada y «revisar ya» (a una ya se la encargaste). '
        + 'El color: el colegio espera hoy, y la fecha dura del stand. '
        + 'En Hacer, primero lo que un agente pide que hagas (la firma, el pago), y después lo de hoy con su tamaño', hm(11, 45), de(BASE), { contestadas: true }),
    estado('hoy', 'sin nada declarado', 'el mismo momento como sería hoy: ningún agente declara qué pide, así que casi todo queda sin clasificar '
        + '(no se adivina por su clase); solo las preguntas del módulo (decidir, con sus opciones) y los cierres propuestos (cerrar) tienen vía',
        hm(11, 45), de(BASE, [], false)),
    estado('libre', 'tiempo libre', 'a las 14:15, libre 45 minutos hasta el Comité: caben las decisiones (≈2 minutos cada una) y la tarea rápida '
        + 'que el plan pone hoy', hm(14, 15), de(['retenido', 'T31', 'T19', 'T12', 'T28'])),
    estado('bloque', 'en un bloque del plan', 'a las 10:10, en el bloque estratégico «Foco: el informe»: el paso y cuándo está terminado, del foco del '
        + 'plan. La Revisión de diseño de las 11:30 tiene algo que preparar: va en Hacer', hm(10, 10), de(['retenido', 'T31', 'T19', 'T12', 'T22', 'T28'])),
    estado('nada', 'nada por decidir', 'ningún agente espera nada: la barra lo dice sin número, las vías lo dicen en una fila, y en lo libre cabe '
        + 'la tarea rápida', hm(14, 15), []),
    estado('muchas', 'muchas cuentas', 'treinta esperas; una venció hace más de 30 días (deuda) y no entra. En cada vía se ven tres cuentas, cada '
        + 'una con la más pesada de las suyas, y «+N cuentas más» lleva al resto; lo sin cuenta va al final', hm(11, 45),
        de([...BASE, 'permiso', 'T8', 'T3'], MAS)),
    estado('sinplan', 'sin plan', 'el día no tiene plan: Hacer es lo que vence hoy (sin la reunión: sin plan no se sabe qué preparar), y lo dice; el '
        + 'borrador del boletín ya no sube por el plan', hm(14, 15), de(['retenido', 'T31', 'T19', 'T12', 'T28']), { sinPlan: true }),
];

/** La espera de una fila: la que abre «Contestar» en el catálogo, como la declara su agente (sin `senales`, como hoy). */
export function esperaDe(direccion: string, senales = true): cli.JsonEspera | undefined {
    const todas = [...Object.entries(ESPERAS).map(([k, e]) => (senales ? conSenales(k, e) : e)), ...MAS];
    return todas.find(e => e.direccion === direccion);
}

/** Lo que muestra la pestaña «la urgencia»: cada espera del día de las muestras con lo que declaran sus agentes, sus
 *  señales y dónde cae. */
export function tablaUrgencia(m = hm(11, 45)): { espera: cli.JsonEspera; senales: Senales; porque: string; nivel: string }[] {
    const ahora = instante(m);
    const plan = delPlan(PLAN);
    const todas = de([...BASE, 'permiso', 'T8', 'T3']);
    const filas = todas.map(e => { const s = deEspera(e, plan, ahora), p = porque(s, ahora); return { espera: e, senales: s, p }; });
    // en su orden; la deuda (sin nivel), al final
    const enOrden = ordenar(filas, f => f.senales);
    return [...enOrden, ...filas.filter(f => !f.p)].map(f => ({ espera: f.espera, senales: f.senales,
        porque: f.p?.texto ?? 'deuda: no entra', nivel: f.p?.nivel ?? '—' }));
}
