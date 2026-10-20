// Las pruebas del mod de telar (`claude plugin test src/telar/mod`): sin sesión, sin red, sin telar. Cada
// prueba responde en lugar de Claude Code y de telar (`$.process.run`), y mira qué hizo el mod.
import { expect, mock, test } from 'claude-code/testing'

const CASILLA = '/estado/casillas/faro'

type Llamadas = { avisos: string[]; escritos: Record<string, string>; enviados: { text: string; asUser?: boolean }[] }

// telar, la casilla y la conversación de mentira. `hilo` vacío: una sesión que no es de telar
function telarFalso(on: any, opciones: { hilo?: string; aviso?: string; archivos?: { name: string; kind: string }[] } = {}): Llamadas {
  const hilo = opciones.hilo ?? 'Faro'
  const llamadas: Llamadas = { avisos: [], escritos: {}, enviados: [] }
  on('env.get', () => ({ value: '["/bin/telar"]' }))
  on('session.id', () => ({ value: 'sesion-1' }))
  on('session.start', () => ({ cwd: '/w' }))
  on('process.run', ($: any, e: any) => {
    const argv: string[] = e.argv
    if (argv.includes('mod')) {
      const datos = { hilo, casilla: hilo ? CASILLA : '', aviso: opciones.aviso ?? '' }
      return { value: { exitCode: 0, stdout: JSON.stringify(datos), stderr: '' } }
    }
    if (argv.includes('aviso')) llamadas.avisos.push(argv[argv.indexOf('--evento') + 1])
    return { value: { exitCode: 0, stdout: '', stderr: '' } }
  })
  on('fs.list', () => ({ value: opciones.archivos ?? [] }))
  on('fs.write', ($: any, e: any) => {
    llamadas.escritos[e.path] = e.text
    return { value: undefined }
  })
  on('prompt.submit', ($: any, e: any) => {
    llamadas.enviados.push({ text: e.text, asUser: e.origin?.asUser })
    return { text: e.text }
  })
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('tool.call', () => ({ result: 'ok' }))
  return llamadas
}

async function empezar($: any) {
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/w' })
}

const terminar = ($: any) => $.turn.complete({ turnId: 't1', answer: '', durationMs: 1, isAborted: false, usage: null })

test('en una sesión que no es de telar no hace nada', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { hilo: '', archivos: [{ name: 'a.json', kind: 'file' }], aviso: '↯ mensaje nuevo' })
  await empezar($)
  await $.turn.start({ text: 'hola', turnId: 't1' })
  await clock.advance(5000)
  expect(ll.enviados).toEqual([])
  expect(ll.avisos).toEqual([])
  expect(Object.keys(ll.escritos)).toEqual([])
})

test('toca su señal de vida en la casilla', async ($, on) => {
  const clock = mock.clock(on, { now: 100_000 })
  const ll = telarFalso(on)
  await empezar($)
  await clock.advance(2000)
  expect(Object.keys(ll.escritos)).toContain(CASILLA + '/.mod')
})

test('con mensajes y la sesión ociosa, manda el aviso como si lo escribiera la persona', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo · de Gestión' })
  await empezar($)
  await clock.advance(2000)
  expect(ll.enviados).toEqual([{ text: '↯ mensaje nuevo · de Gestión', asUser: true }])
})

test('mientras trabaja no manda nada: los entrega el gancho Stop', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo' })
  await empezar($)
  await $.turn.start({ text: 'trabaja', turnId: 't1' })
  await clock.advance(6000)
  expect(ll.enviados).toEqual([])
})

test('lo suyo en la casilla (la señal, la conversación) no cuenta como un mensaje', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, {
    archivos: [{ name: '.mod', kind: 'file' }, { name: 'mod', kind: 'dir' }, { name: 'entregados', kind: 'dir' }],
    aviso: '↯ mensaje nuevo',
  })
  await empezar($)
  await clock.advance(6000)
  expect(ll.enviados).toEqual([])
})

test('el semáforo: empieza y termina con el turno, sin repetir', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on)
  await empezar($)
  await $.turn.start({ text: 'hola', turnId: 't1' })
  await terminar($)
  await terminar($) // un segundo final no se avisa dos veces
  await clock.settle()
  expect(ll.avisos).toEqual(['empieza', 'termina'])
})

test('una pregunta a la persona es espera, y contestarla es sigue', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on)
  await empezar($)
  await $.turn.start({ text: 'pregúntame', turnId: 't1' })
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] })
  await terminar($)
  await clock.settle()
  expect(ll.avisos).toEqual(['empieza', 'espera', 'sigue', 'termina'])
})

test('deja la conversación ya estructurada, aparte de los mensajes pendientes', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on)
  on('session.messages', () => ({
    value: [
      { role: 'user', text: '¿cómo va?', toolUses: [] },
      { role: 'assistant', text: 'Miro.', toolUses: [{ tool_use_id: 'u1', tool: 'Bash', input: { command: 'git status', timeout: 5 } }] },
    ],
  }))
  await empezar($)
  await $.turn.start({ text: '¿cómo va?', turnId: 't1' })
  await terminar($)
  await clock.advance(1500)
  const escrito = ll.escritos[CASILLA + '/mod/conversacion.json']
  expect(escrito).toBeDefined()
  const datos = JSON.parse(escrito)
  expect(datos.sesion).toBe('sesion-1')
  expect(datos.mensajes).toEqual([
    { role: 'user', text: '¿cómo va?', tools: [] },
    { role: 'assistant', text: 'Miro.', tools: [{ tool: 'Bash', input: { command: 'git status' } }] },
  ])
})
