// La sordina: baja el volumen de las herramientas para que lo que dice el modelo quede al frente.
//
// Una edición (Edit, Write, NotebookEdit) se ve como una línea gris con el archivo y cuántas filas agregó y
// sacó, sin el diff. Un comando (Bash) se ve como una línea gris con lo que hace y cuánto imprimió, sin su
// salida. Lo demás queda como lo dibuja Claude Code.
//
// No esconde nada que importe: un error o una interrupción se ven enteros, como siempre, y la vista
// expandida (ctrl+o, --verbose) muestra todo el detalle.
//
// Claude Code dibuja la fila de una herramienta mientras corre y no la vuelve a dibujar al terminar; lo que
// llega al terminar es su resultado. Por eso la fila queda vacía y el resumen va en el lugar del resultado,
// que es donde iban el diff y la salida.

const EDICIONES = new Set(['Edit', 'MultiEdit', 'Write', 'NotebookEdit'])
const ANCHO = 100

// La entrada de cada llamada, guardada por su id cuando se dibuja su fila: el resultado no la trae, y sin
// ella no se sabe qué comando corrió. Solo las últimas, para no crecer sin tope.
const entradas = new Map()
const MAX_ENTRADAS = 200

function recordar(props) {
  entradas.set(props.tool_use_id, props.input || {})
  if (entradas.size > MAX_ENTRADAS) entradas.delete(entradas.keys().next().value)
}

// cuántas filas agregó y sacó una edición, de lo que dice git o de su parche
function filas(output) {
  if (!output || typeof output !== 'object') return null
  if (output.gitDiff && typeof output.gitDiff.additions === 'number') {
    return { mas: output.gitDiff.additions, menos: output.gitDiff.deletions }
  }
  if (Array.isArray(output.structuredPatch)) {
    let mas = 0
    let menos = 0
    for (const h of output.structuredPatch) {
      for (const l of h.lines || []) {
        if (l.startsWith('+')) mas += 1
        else if (l.startsWith('-')) menos += 1
      }
    }
    return { mas, menos }
  }
  return null
}

// el texto en una línea, cortado al ancho con puntos suspensivos
function corto(texto, ancho) {
  const plano = String(texto || '').replace(/\s+/g, ' ').trim()
  if (plano.length <= ancho) return plano
  return plano.slice(0, ancho - 1) + '…'
}

// la ruta, relativa a donde trabaja la sesión si está adentro
function ruta(archivo, cwd) {
  const r = String(archivo || '')
  if (cwd && r.startsWith(cwd + '/')) return r.slice(cwd.length + 1)
  return r
}

// una edición: el archivo y cuántas filas agregó y sacó
function lineaEdicion(input, output, cwd) {
  const archivo = ruta(input.file_path || input.notebook_path || (output && output.filePath), cwd)
  const f = filas(output)
  const nuevo = output && output.type === 'create'
  const cuenta = f ? `  +${f.mas} −${f.menos}` : ''
  const marca = nuevo ? ' (nuevo)' : ''
  return '✎ ' + archivo + marca + cuenta
}

// un comando: lo que hace (la descripción que escribe el modelo, o la primera línea) y cuánto imprimió
function lineaBash(input, output) {
  const que = corto(input.description || String(input.command || '').split('\n')[0], ANCHO)
  const out = output && typeof output === 'object' ? output : {}
  const n = String(out.stdout || '').split('\n').filter((l) => l.trim()).length
  let cola = ''
  if (out.backgroundTaskId) cola = ' · en segundo plano'
  else if (n === 1) cola = ' · 1 línea'
  else if (n > 1) cola = ' · ' + n + ' líneas'
  return '$ ' + que + cola
}

// si la sordina baja esta fila: una edición o un comando, salvo un error, una interrupción o la vista
// expandida, que se dejan como los dibuja Claude Code
function acallado(props) {
  if (!EDICIONES.has(props.tool) && props.tool !== 'Bash') return false
  return !(props.isExpanded || props.isErrored || props.isInterrupted)
}

export function register(on) {
  // la fila: se recuerda su entrada y, si se acalla, queda vacía
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    const p = e.props
    if (p.tool_use_id) recordar(p)
    if (!acallado(p)) return next(e)
    const { Box } = $.ui.resolve(e)
    return Box({ children: [] })
  })

  // el resultado: en lugar del diff o de la salida, una línea gris
  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    const p = e.props
    if (!acallado(p)) return next(e)
    const { Text } = $.ui.resolve(e)
    const input = entradas.get(p.tool_use_id) || {}
    const cwd = await $.session.cwd()
    const texto = EDICIONES.has(p.tool) ? lineaEdicion(input, p.output, cwd) : lineaBash(input, p.output)
    return Text({ dimColor: true, wrap: 'truncate-end', children: [texto] })
  })
}
