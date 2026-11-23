// Las pruebas del mod de telar (`claude plugin test src/telar/mod`): sin sesión, sin red, sin telar. Cada
// prueba responde en lugar de Claude Code y de telar (`$.process.run`), y mira qué hizo el mod.
import { expect, mock, test } from 'claude-code/testing'

const CASILLA = '/estado/casillas/faro'

type Llamadas = { avisos: string[]; escritos: Record<string, string>; enviados: { text: string; asUser?: boolean }[]; preguntas: number; historia: { path: string; text: string }[]; miradas: number }

// telar, la casilla y la conversación de mentira. `hilo` vacío: una sesión que no es de telar
type Entrada = { name: string; kind: string }

// `dialogo`: el diálogo de una pregunta queda abierto hasta que lo abandonan (como en la terminal, esperando a la
// persona); `leibles`: los archivos que se pueden leer, por ruta
function telarFalso(on: any, opciones: { hilo?: string; aviso?: string; archivos?: Entrada[]; camino?: Entrada[]; dialogo?: boolean; leibles?: Record<string, string> } = {}): Llamadas {
  const hilo = opciones.hilo ?? 'Faro'
  const llamadas: Llamadas = { avisos: [], escritos: {}, enviados: [], preguntas: 0, historia: [], miradas: 0 }
  const leibles = opciones.leibles ?? {}
  on('env.get', () => ({ value: '["/bin/telar"]' }))
  on('session.id', () => ({ value: 'sesion-1' }))
  on('session.start', () => ({ cwd: '/w' }))
  on('process.run', ($: any, e: any) => {
    const argv: string[] = e.argv
    if (argv.includes('mod')) {
      llamadas.preguntas++
      const datos = { hilo, casilla: hilo ? CASILLA : '', aviso: opciones.aviso ?? '' }
      return { value: { exitCode: 0, stdout: JSON.stringify(datos), stderr: '' } }
    }
    // el semáforo: `telar agente evento claude-code --evento …` (el nombre de antes, `agente aviso`, ya no lo cuenta)
    if (argv.includes('evento')) llamadas.avisos.push(argv[argv.indexOf('--evento') + 1])
    return { value: { exitCode: 0, stdout: '', stderr: '' } }
  })
  // la casilla, y su carpeta camino/ (lo que un gancho imprimió y la conversación todavía no muestra)
  on('fs.list', ($: any, e: any) => ({ value: (e.path.endsWith('/camino') ? opciones.camino : opciones.archivos) ?? [] }))
  on('fs.write', ($: any, e: any) => {
    llamadas.escritos[e.path] = e.text
    llamadas.historia.push({ path: e.path, text: e.text })
    return { value: undefined }
  })
  on('fs.exists', ($: any, e: any) => {
    if (e.path === CASILLA + '/mod/respuesta.json') llamadas.miradas++
    return { value: e.path in leibles }
  })
  on('fs.read', ($: any, e: any) => ({ value: leibles[e.path] }))
  on('prompt.submit', ($: any, e: any) => {
    llamadas.enviados.push({ text: e.text, asUser: e.origin?.asUser })
    return { text: e.text }
  })
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('tool.call', ($: any, e: any, next: any) => {
    if (e.tool !== 'AskUserQuestion' || !opciones.dialogo) return { result: 'ok' }
    return new Promise((resolver) => next.signal.addEventListener('abort', () => resolver({ result: 'abandonado' })))
  })
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
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo · de Secretaría' })
  await empezar($)
  await clock.advance(2000)
  expect(ll.enviados).toEqual([{ text: '↯ mensaje nuevo · de Secretaría', asUser: true }])
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

test('en un claude -p no hace nada, aunque herede el hilo', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: 'a.json', kind: 'file' }], aviso: '↯ mensaje nuevo' })
  await $.session.start({ surface: 'terminal', isInteractive: false, cwd: '/w' })
  await $.turn.start({ text: 'hola', turnId: 't1' })
  await clock.advance(5000)
  expect(ll.enviados).toEqual([])
  expect(ll.avisos).toEqual([])
  expect(Object.keys(ll.escritos)).toEqual([])
})

// el 14-nov, con la máquina cargada: los ganchos de UserPromptSubmit tardaban 5 s, el turno no empezaba, y el mod
// encoló el mismo aviso seis veces en dos segundos (salieron todas juntas)
test('no repite el aviso mientras el anterior espera su turno', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo · de Secretaría' })
  await empezar($)
  await clock.advance(10_000) // cinco vueltas sin que empiece el turno del primero
  expect(ll.enviados).toEqual([{ text: '↯ mensaje nuevo · de Secretaría', asUser: true }])
  await $.turn.start({ text: '↯ mensaje nuevo · de Secretaría', turnId: 't1' })
  await terminar($)
  // tuvo su turno y el mensaje sigue esperando (al gancho lo cortaron antes de tomarlo): ahora sí, otra vez
  await clock.advance(2000)
  expect(ll.enviados.length).toBe(2)
})

test('un aviso que nunca tuvo su turno se vuelve a mandar pasado un rato', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo' })
  await empezar($)
  await clock.advance(10_000)
  expect(ll.enviados.length).toBe(1)
  await clock.advance(120_000) // la cola lo soltó: no espera para siempre
  expect(ll.enviados.length).toBe(2)
})

test('lo que está en camino lo hace preguntar, y si volvió a la casilla manda el aviso', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, {
    archivos: [{ name: 'camino', kind: 'dir' }, { name: 'entregados', kind: 'dir' }],
    camino: [{ name: '20261020-ab.json', kind: 'file' }],
    aviso: '↯ mensaje nuevo · de Secretaría',
  })
  await empezar($)
  await clock.advance(2000)
  expect(ll.enviados).toEqual([{ text: '↯ mensaje nuevo · de Secretaría', asUser: true }])
})

test('una carpeta camino vacía no lo hace preguntar', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: 'camino', kind: 'dir' }], camino: [], aviso: '↯ mensaje nuevo' })
  await empezar($)
  const antes = ll.preguntas // la de resolver el hilo al empezar
  await clock.advance(6000)
  expect(ll.preguntas).toBe(antes)
  expect(ll.enviados).toEqual([])
})

test('un prompt de la persona que espera su turno tampoco deja mandar el aviso', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on, { archivos: [{ name: '20261020-ab.json', kind: 'file' }], aviso: '↯ mensaje nuevo' })
  await empezar($)
  await $.prompt.submit({ text: 'revisa lo de ayer' }) // sus ganchos de UserPromptSubmit entregan lo que haya
  await clock.advance(6000)
  expect(ll.enviados.map((x) => x.text)).toEqual(['revisa lo de ayer'])
  await $.turn.start({ text: 'revisa lo de ayer', turnId: 't1' })
  await terminar($)
  await clock.advance(2000) // terminó su turno y el mensaje sigue ahí: ahora sí, el aviso
  expect(ll.enviados.map((x) => x.text)).toEqual(['revisa lo de ayer', '↯ mensaje nuevo'])
})

const PREGUNTAS = [{ question: '¿Qué paleta?', header: 'Colores', multiSelect: false,
  options: [{ label: 'Oscura', description: 'fondo oscuro' }, { label: 'Clara', description: 'fondo claro' }] }]
const PREGUNTA = CASILLA + '/mod/pregunta.json'
const RESPUESTA = CASILLA + '/mod/respuesta.json'
const deLaPregunta = (ll: Llamadas) => ll.historia.filter((x) => x.path === PREGUNTA).map((x) => JSON.parse(x.text))

test('una pregunta abierta se contesta desde afuera: gana la respuesta que deja telar', async ($, on) => {
  const clock = mock.clock(on)
  // una respuesta de otra pregunta no cuenta; la de esta, sí
  const leibles: Record<string, string> = { [RESPUESTA]: JSON.stringify({ id: 'otra', respuestas: { '¿Qué paleta?': 'Clara' } }) }
  const ll = telarFalso(on, { dialogo: true, leibles })
  await empezar($)
  await $.turn.start({ text: 'pregúntame', turnId: 't1' })
  const llamada = $.tool.call({ tool: 'AskUserQuestion', questions: PREGUNTAS } as any)
  await clock.advance(1000)
  expect(ll.miradas).toBeGreaterThan(0) // miró, y la de otra pregunta no la tomó
  expect(deLaPregunta(ll).map((d) => d.estado)).toEqual(['abierta'])
  const id = deLaPregunta(ll)[0].id
  expect(deLaPregunta(ll)[0].preguntas).toEqual(PREGUNTAS)
  leibles[RESPUESTA] = JSON.stringify({ id, respuestas: { '¿Qué paleta?': 'Oscura' } })
  await clock.advance(600)
  const r: any = await llamada
  expect(r.result).toEqual({ questions: PREGUNTAS, answers: { '¿Qué paleta?': 'Oscura' } })
  expect(deLaPregunta(ll).at(-1)).toMatchObject({ id, estado: 'cerrada', por: 'afuera' })
  await terminar($)
  await clock.settle()
  expect(ll.avisos).toEqual(['empieza', 'espera', 'sigue', 'termina'])
})

test('contestada en la terminal, se cierra y deja de mirar afuera', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on)
  await empezar($)
  await $.turn.start({ text: 'pregúntame', turnId: 't1' })
  const r: any = await $.tool.call({ tool: 'AskUserQuestion', questions: PREGUNTAS } as any)
  expect(r.result).toBe('ok')
  expect(deLaPregunta(ll).map((d) => [d.estado, d.por])).toEqual([['abierta', undefined], ['cerrada', 'terminal']])
  const miradas = ll.miradas
  await clock.advance(5000)
  expect(ll.miradas).toBe(miradas)
  expect(ll.historia.filter((x) => x.path === PREGUNTA).length).toBe(2)
})

test('de una pregunta guarda lo preguntado, lo respondido y si espera', async ($, on) => {
  const clock = mock.clock(on)
  const ll = telarFalso(on)
  on('session.messages', () => ({
    value: [
      { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'p1', tool: 'AskUserQuestion', input: { questions: PREGUNTAS },
        result: { questions: PREGUNTAS, answers: { '¿Qué paleta?': 'Clara' } }, text: 'answered' }] },
      { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'p2', tool: 'AskUserQuestion', input: { questions: PREGUNTAS } }] },
    ],
  }))
  await empezar($)
  await $.turn.start({ text: 'hola', turnId: 't1' })
  await terminar($)
  await clock.advance(1500)
  const datos = JSON.parse(ll.escritos[CASILLA + '/mod/conversacion.json'])
  expect(datos.mensajes.map((m: any) => m.tools[0].pregunta)).toEqual([
    { id: 'p1', questions: PREGUNTAS, estado: 'respondida', answers: { '¿Qué paleta?': 'Clara' } },
    { id: 'p2', questions: PREGUNTAS, estado: 'pendiente' },
  ])
})
