// El mod de telar para Claude Code. Lo carga cada sesión de Claude Code con CLAUDE_CODE_PLUGIN_DIRS (lo pone
// `telar agente instalar`); en una sesión que no es un hilo de telar no hace nada.
//
// Hace tres cosas, y mientras vive toca un archivo en la casilla (.mod) para que telar sepa que está:
//
// 1. La casilla. Cuando llegan mensajes y la sesión está ociosa, manda la línea de aviso («↯ mensaje
//    nuevo · …») como un mensaje, y el gancho UserPromptSubmit de siempre le agrega el contenido. Antes ese
//    aviso lo tecleaba el nodo en la terminal, y podía caer sobre lo que la persona estaba escribiendo. Si
//    la sesión trabaja, nada: el gancho Stop entrega los mensajes al terminar el turno. Un aviso mandado no
//    se repite mientras no haya tenido su turno: `$.prompt.submit` resuelve al encolarlo, y el turno empieza
//    recién cuando terminan los ganchos de UserPromptSubmit (con la máquina cargada, segundos). Lo que un
//    gancho imprimió y la conversación todavía no muestra (casilla/camino/) también lo hace preguntar: si
//    al gancho lo mataron, `telar agente mod` lo devuelve a la casilla y el aviso sale de nuevo.
// 2. El semáforo. Dice en qué anda la sesión (`telar agente evento --evento …`) desde sus propios eventos:
//    empieza y termina con el turno (también uno interrumpido con Esc, que el gancho Stop no ve), espera
//    cuando aparece un diálogo de permiso o una pregunta, y sigue cuando se contesta. Con el mod vivo, los
//    ganchos clásicos de esos cuatro eventos no avisan (telar agente evento los descarta), para no avisar dos
//    veces.
// 3. La conversación. Mientras la sesión avanza, deja sus últimos mensajes ya estructurados en la casilla
//    (mod/conversacion.json, aparte de los mensajes pendientes): lo que escribió la persona, lo que
//    contestó el agente y cada herramienta con lo que la distingue. Con eso telar lee el hilo (el modo
//    lectura de la página, `telar hilo leer`) sin descifrar el registro de Claude Code, que cambia de forma
//    sin avisar. De una pregunta del agente (AskUserQuestion) guarda además las preguntas, sus opciones y lo
//    respondido.
// 4. Las preguntas, desde afuera. Mientras el diálogo de una pregunta está abierto en la terminal, la deja en
//    mod/pregunta.json y mira mod/respuesta.json, donde telar deja lo que la persona contestó en la página
//    (`POST /hilos/responder`, también desde otra máquina por el bus). Lo que llegue primero gana: la
//    respuesta de afuera cierra el diálogo y el agente la recibe como si la hubiera elegido ahí; si contestan
//    en la terminal, sigue como siempre. Al cerrarse, mod/pregunta.json dice que se cerró y por dónde.

const CADA_MS = 2000        // cada cuánto mira la casilla
const VIDA_MS = 10_000      // cada cuánto toca la señal de vida (el nodo la da por muerta a los 30 s)
const RESOLVER_MS = 60_000  // cada cuánto vuelve a preguntar el hilo (pudo cambiar de nombre)
const TURNO_MS = 120_000    // cuánto espera un aviso mandado a que empiece su turno; después se da por perdido

let hilo = ''          // el hilo de esta sesión; '' si no es de telar
let casilla = ''       // su carpeta de mensajes
let trabajando = false
let enviando = false
let avisado = null     // cuándo salió un prompt (el aviso, o uno de la persona) que todavía no tuvo su turno
let vida = 0
let resuelto = 0
let guardando = false  // ya hay una escritura de la conversación en camino
const MENSAJES = 300   // cuántos mensajes de la conversación se guardan, los últimos
const TEXTO = 8000     // caracteres por mensaje
const DETALLE = ['description', 'command', 'file_path', 'pattern', 'url', 'query', 'prompt']
const PREGUNTA_MS = 500 // cada cuánto mira si llegó la respuesta de afuera, mientras hay una pregunta abierta
let semaforo = ''      // el último evento avisado: no se repite el mismo
let cola = Promise.resolve()  // los avisos salen de a uno y en orden

async function ejecutable($) {
  // TELAR_EJECUTABLE: con qué se llama a telar, como una lista JSON (lo pone `telar agente instalar`)
  try {
    const crudo = await $.env.get('TELAR_EJECUTABLE')
    if (crudo) return JSON.parse(crudo)
  } catch {
    // no es JSON: telar del PATH
  }
  return ['telar']
}

// el semáforo: encola el aviso sin esperar, para no frenar el turno
function avisar($, evento) {
  if (!hilo || evento === semaforo) return
  semaforo = evento
  cola = cola.then(() => correrAviso($, evento)).catch(() => {})
}

async function correrAviso($, evento) {
  const telar = await ejecutable($)
  const argv = [...telar, 'agente', 'evento', 'claude-code', '--evento', evento, '--hilo', hilo, '--sesion', await $.session.id()]
  await $.process.run(argv, { timeoutMs: 15_000 })
}

// `telar agente mod`: el hilo, la casilla y, si hay mensajes, el aviso. Nunca falla: {} si algo sale mal
async function preguntar($, sesion) {
  const telar = await ejecutable($)
  try {
    const r = await $.process.run([...telar, 'agente', 'mod', '--sesion', sesion], { timeoutMs: 15_000 })
    return r.exitCode === 0 ? JSON.parse(r.stdout || '{}') : {}
  } catch {
    return {}
  }
}

async function resolver($) {
  const d = await preguntar($, await $.session.id())
  hilo = d.hilo || ''
  casilla = d.casilla || ''
  resuelto = await $.clock.now()
  return d
}

// la conversación, ya estructurada, en la casilla: se junta lo que pase en el próximo segundo y se escribe una vez
function guardarPronto($) {
  if (!hilo || !casilla || guardando) return
  guardando = true
  $.clock.after(1000, () => guardar($))
}

function recortar(texto) {
  return texto.length > TEXTO ? texto.slice(0, TEXTO) + ' […]' : texto
}

async function guardar($) {
  guardando = false
  const todos = await $.session.messages()
  const mensajes = todos.slice(-MENSAJES).map((m) => ({
    role: m.role,
    text: recortar(m.text || ''),
    // de cada herramienta, lo que la distingue de otra llamada igual (telar arma la línea)
    tools: (m.toolUses || []).map((u) => {
      const input = {}
      for (const k of DETALLE) {
        const v = u.input ? u.input[k] : undefined
        if (typeof v === 'string' && v.trim()) input[k] = v.slice(0, 300)
      }
      return u.tool === 'AskUserQuestion' ? { tool: u.tool, input, pregunta: resumenPregunta(u) } : { tool: u.tool, input }
    }),
  }))
  const datos = { sesion: await $.session.id(), hora: await $.clock.now(), total: todos.length, mensajes }
  await $.fs.write(casilla + '/mod/conversacion.json', JSON.stringify(datos))
}

const corto = (v, n) => (typeof v === 'string' ? v.slice(0, n) : '')

// una pregunta del agente: lo preguntado (sin las vistas previas), lo respondido y en qué está. `pendiente`
// mientras corre (Claude Code todavía no guarda su resultado); `cancelada` si se cerró sin respuesta
function resumenPregunta(u) {
  const qs = u.input && Array.isArray(u.input.questions) ? u.input.questions : []
  const questions = qs.slice(0, 8).map((q) => ({
    question: corto(q && q.question, 1000),
    header: corto(q && q.header, 60),
    multiSelect: !!(q && q.multiSelect),
    options: (q && Array.isArray(q.options) ? q.options : []).slice(0, 8)
      .map((o) => ({ label: corto(o && o.label, 200), description: corto(o && o.description, 500) })),
  }))
  const r = u.result && typeof u.result === 'object' ? u.result : null
  const answers = r && r.answers && typeof r.answers === 'object' ? r.answers : null
  const estado = u.text === undefined ? 'pendiente' : u.isError || !answers ? 'cancelada' : 'respondida'
  return { id: u.tool_use_id, questions, estado, ...(answers ? { answers } : {}) }
}

async function escribirPregunta($, datos) {
  try {
    await $.fs.write(casilla + '/mod/pregunta.json', JSON.stringify(datos))
  } catch {
    // sin la casilla, la pregunta se contesta solo en la terminal
  }
}

// lo que la persona contestó afuera (mod/respuesta.json, lo deja telar): solo si es de esta pregunta
async function respuestaDeAfuera($, id) {
  try {
    const ruta = casilla + '/mod/respuesta.json'
    if (!(await $.fs.exists(ruta))) return null
    const d = JSON.parse(await $.fs.read(ruta))
    if (d && d.id === id && d.respuestas && typeof d.respuestas === 'object') return d.respuestas
  } catch {
    // a medio escribir, o roto: en la próxima vuelta
  }
  return null
}

// el diálogo de la terminal y la respuesta de afuera, a la vez: gana la primera. La de afuera se devuelve como el
// resultado de la herramienta (el diálogo, abandonado, se cierra solo)
async function abrirPregunta($, e, next) {
  const id = e.tool_use_id
  await escribirPregunta($, { id, estado: 'abierta', desde: await $.clock.now(), preguntas: e.questions })
  let reloj = null
  const deAfuera = new Promise((resolver) => {
    reloj = $.clock.every(PREGUNTA_MS, async () => {
      const r = await respuestaDeAfuera($, id)
      if (r) resolver(r)
    })
  })
  const dialogo = next(e)
  let por = 'terminal'
  try {
    const gano = await Promise.race([dialogo.then((r) => ({ r })), deAfuera.then((respuestas) => ({ respuestas }))])
    if (!gano.respuestas) return gano.r
    por = 'afuera'
    dialogo.catch(() => {})
    return { result: { questions: e.questions, answers: gano.respuestas } }
  } finally {
    // nada de aquí puede fallar hacia afuera: el .catch del gancho volvería a correr la herramienta (otro diálogo)
    try {
      if (reloj) reloj.cancel()
      await escribirPregunta($, { id, estado: 'cerrada', por, hora: await $.clock.now() })
      guardarPronto($)
    } catch {
      // la pregunta queda «abierta» en la casilla; telar la da por cerrada cuando la conversación muestra su resultado
    }
  }
}

const esMensaje = (f) => f.kind === 'file' && f.name.endsWith('.json')

async function hayMensajes($) {
  try {
    const entradas = await $.fs.list(casilla)
    if (entradas.some(esMensaje)) return true
    // lo que un gancho imprimió y la conversación todavía no muestra: `telar agente mod` lo revisa
    if (!entradas.some((f) => f.kind === 'dir' && f.name === 'camino')) return false
    return (await $.fs.list(casilla + '/camino')).some(esMensaje)
  } catch {
    return false
  }
}

async function vuelta($) {
  const ahora = await $.clock.now()
  if (ahora - resuelto > RESOLVER_MS) await resolver($)
  if (!hilo || !casilla) return
  if (ahora - vida > VIDA_MS) {
    vida = ahora
    await $.fs.write(casilla + '/.mod', String(ahora))
  }
  if (trabajando || enviando) return
  // el aviso anterior espera su turno (los ganchos de UserPromptSubmit corren antes): otro sería el mismo aviso
  // encolado dos veces, y el gancho del primero ya entrega todo lo que haya. Si nunca empieza, se da por perdido
  if (avisado !== null && ahora - avisado < TURNO_MS) return
  if (!(await hayMensajes($))) return
  const d = await preguntar($, await $.session.id())
  if (!d.aviso) return
  enviando = true
  avisado = await $.clock.now()
  try {
    // asUser: el gancho UserPromptSubmit reconoce el aviso por su comienzo («↯») y agrega los mensajes; con
    // otro remitente delante no lo reconocería y cortaría la cadena de mensajes entre hilos
    await $.prompt.submit({ text: d.aviso, asUser: true })
  } catch {
    // la persona interrumpió o la cola lo soltó: no espera turno, en la próxima vuelta se intenta de nuevo
    avisado = null
  } finally {
    enviando = false
  }
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    if (e.isInteractive === false) return next(e)  // un claude -p: no es un hilo, aunque herede TELAR_HILO
    await resolver($)
    $.clock.every(CADA_MS, () => vuelta($))
    return next(e)
  })

  // solo el turno principal: los de un subagente traen agentId
  on('turn.start', async ($, e, next) => {
    if (!e.agentId) {
      trabajando = true
      avisado = null  // el prompt que esperaba (si había) ya tiene su turno
      avisar($, 'empieza')
    }
    return next(e)
  })

  // un prompt de la persona (o el aviso mismo) que espera su turno: sus ganchos de UserPromptSubmit van a entregar lo
  // que haya en la casilla, así que un aviso ahora sería otro turno de más. Un comando (/clear) no trae turno, y uno
  // escrito mientras el turno corre (turnId) puede entrar en ese mismo turno sin abrir otro: esos no cuentan
  on('prompt.submit', async ($, e, next) => {
    if (!e.command && !e.turnId) avisado = await $.clock.now()
    return next(e)
  }).catch(async ($, e, next) => next(e))

  // también al interrumpirlo con Esc o al caer por un error de la API
  on('turn.complete', async ($, e, next) => {
    if (!e.agentId) {
      trabajando = false
      avisar($, 'termina')
      guardarPronto($)
    }
    return next(e)
  })

  // cada fila que la conversación guarda (un mensaje, una respuesta, un resultado): la lectura la ve al tiro
  on('session.append', async ($, e, next) => {
    guardarPronto($)
    return next(e)
  })

  // un diálogo de permiso a la vista: lo dispara Claude Code solo cuando de verdad le pregunta a la persona
  // (en modo automático, un `ask` de tool.check lo decide el clasificador y no llega aquí)
  on('classic.PermissionRequest', async ($, e, next) => {
    avisar($, 'espera')
    return next(e)
  }).catch(async ($, e, next) => next(e))

  // un servidor MCP que le pide algo a la persona
  on('classic.Notification', async ($, e, next) => {
    if (e.notification_type === 'permission_prompt' || e.notification_type === 'elicitation_dialog') avisar($, 'espera')
    return next(e)
  }).catch(async ($, e, next) => next(e))

  // una pregunta del agente espera respuesta mientras corre, en la terminal o desde afuera (abrirPregunta); cualquier
  // herramienta que termina de correr después de una espera quiere decir que la persona contestó
  on('tool.call', async ($, e, next) => {
    const pregunta = e.tool === 'AskUserQuestion'
    if (pregunta) avisar($, 'espera')
    const r = pregunta && hilo && casilla && e.tool_use_id ? await abrirPregunta($, e, next) : await next(e)
    if (semaforo === 'espera' && trabajando) avisar($, 'sigue')
    return r
  }).catch(async ($, e, next) => next(e)) // si este gancho falla, la herramienta corre igual
}
