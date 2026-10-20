// El mod de telar para Claude Code. Lo carga cada sesión de Claude Code con CLAUDE_CODE_PLUGIN_DIRS (lo pone
// `telar agente instalar`); en una sesión que no es un hilo de telar no hace nada.
//
// Hace una cosa: cuando llegan mensajes a la casilla del hilo y la sesión está ociosa, manda la línea de
// aviso («↯ mensaje nuevo · …») como un mensaje, y el gancho UserPromptSubmit de siempre le agrega el
// contenido. Antes ese aviso lo tecleaba el nodo en la terminal, y podía caer sobre lo que la persona estaba
// escribiendo. Mientras el mod vive, toca un archivo en la casilla (.mod) y el nodo deja de teclear.
// Si la sesión está trabajando no hace nada: el gancho Stop entrega los mensajes al terminar el turno.

const CADA_MS = 2000        // cada cuánto mira la casilla
const VIDA_MS = 10_000      // cada cuánto toca la señal de vida (el nodo la da por muerta a los 30 s)
const RESOLVER_MS = 60_000  // cada cuánto vuelve a preguntar el hilo (pudo cambiar de nombre)

let hilo = ''          // el hilo de esta sesión; '' si no es de telar
let casilla = ''       // su carpeta de mensajes
let trabajando = false
let enviando = false
let vida = 0
let resuelto = 0

// `telar agente mod`: el hilo, la casilla y, si hay mensajes, el aviso. Nunca falla: {} si algo sale mal
async function preguntar($, sesion) {
  // TELAR_EJECUTABLE: con qué se llama a telar, como una lista JSON (lo pone `telar agente instalar`)
  let telar = ['telar']
  try {
    const crudo = await $.env.get('TELAR_EJECUTABLE')
    if (crudo) telar = JSON.parse(crudo)
  } catch {
    // no es JSON: telar del PATH
  }
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

async function hayMensajes($) {
  try {
    const entradas = await $.fs.list(casilla)
    return entradas.some((f) => f.kind === 'file' && f.name.endsWith('.json'))
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
  if (trabajando || enviando || !(await hayMensajes($))) return
  const d = await preguntar($, await $.session.id())
  if (!d.aviso) return
  enviando = true
  try {
    // asUser: el gancho UserPromptSubmit reconoce el aviso por su comienzo («↯») y agrega los mensajes; con
    // otro remitente delante no lo reconocería y cortaría la cadena de mensajes entre hilos
    await $.prompt.submit({ text: d.aviso, asUser: true })
  } catch {
    // la persona interrumpió o la cola lo soltó: en la próxima vuelta se intenta de nuevo
  } finally {
    enviando = false
  }
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await resolver($)
    $.clock.every(CADA_MS, () => vuelta($))
    return next(e)
  })

  // solo el turno principal: los de un subagente traen agentId
  on('turn.start', async ($, e, next) => {
    if (!e.agentId) trabajando = true
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (!e.agentId) trabajando = false
    return next(e)
  })
}
