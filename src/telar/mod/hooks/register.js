// El mod de telar para Claude Code. Lo carga cada sesión de Claude Code con CLAUDE_CODE_PLUGIN_DIRS (lo pone
// `telar agente instalar`); en una sesión que no es un hilo de telar no hace nada.
//
// Hace tres cosas, y mientras vive toca un archivo en la casilla (.mod) para que telar sepa que está:
//
// 1. La casilla. Cuando llegan mensajes y la sesión está ociosa, manda la línea de aviso («↯ mensaje
//    nuevo · …») como un mensaje, y el gancho UserPromptSubmit de siempre le agrega el contenido. Antes ese
//    aviso lo tecleaba el nodo en la terminal, y podía caer sobre lo que la persona estaba escribiendo. Si
//    la sesión trabaja, nada: el gancho Stop entrega los mensajes al terminar el turno.
// 2. El semáforo. Dice en qué anda la sesión (`telar agente aviso --evento …`) desde sus propios eventos:
//    empieza y termina con el turno (también uno interrumpido con Esc, que el gancho Stop no ve), espera
//    cuando aparece un diálogo de permiso o una pregunta, y sigue cuando se contesta. Con el mod vivo, los
//    ganchos clásicos de esos cuatro eventos no avisan (telar agente aviso los descarta), para no avisar dos
//    veces.
// 3. La conversación. Mientras la sesión avanza, deja sus últimos mensajes ya estructurados en la casilla
//    (mod/conversacion.json, aparte de los mensajes pendientes): lo que escribió la persona, lo que
//    contestó el agente y cada herramienta con lo que la distingue. Con eso telar lee el hilo (el modo
//    lectura de la página, `telar hilo leer`) sin descifrar el registro de Claude Code, que cambia de forma
//    sin avisar.

const CADA_MS = 2000        // cada cuánto mira la casilla
const VIDA_MS = 10_000      // cada cuánto toca la señal de vida (el nodo la da por muerta a los 30 s)
const RESOLVER_MS = 60_000  // cada cuánto vuelve a preguntar el hilo (pudo cambiar de nombre)

let hilo = ''          // el hilo de esta sesión; '' si no es de telar
let casilla = ''       // su carpeta de mensajes
let trabajando = false
let enviando = false
let vida = 0
let resuelto = 0
let guardando = false  // ya hay una escritura de la conversación en camino
const MENSAJES = 300   // cuántos mensajes de la conversación se guardan, los últimos
const TEXTO = 8000     // caracteres por mensaje
const DETALLE = ['description', 'command', 'file_path', 'pattern', 'url', 'query', 'prompt']
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
  const argv = [...telar, 'agente', 'aviso', 'claude-code', '--evento', evento, '--hilo', hilo, '--sesion', await $.session.id()]
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
      return { tool: u.tool, input }
    }),
  }))
  const datos = { sesion: await $.session.id(), hora: await $.clock.now(), total: todos.length, mensajes }
  await $.fs.write(casilla + '/mod/conversacion.json', JSON.stringify(datos))
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
    if (!e.agentId) {
      trabajando = true
      avisar($, 'empieza')
    }
    return next(e)
  })

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

  // una pregunta del agente espera respuesta mientras corre; cualquier herramienta que termina de correr
  // después de una espera quiere decir que la persona contestó
  on('tool.call', async ($, e, next) => {
    if (e.tool === 'AskUserQuestion') avisar($, 'espera')
    const r = await next(e)
    if (semaforo === 'espera' && trabajando) avisar($, 'sigue')
    return r
  }).catch(async ($, e, next) => next(e)) // si este gancho falla, la herramienta corre igual
}
