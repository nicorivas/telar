// Las pruebas de la sordina (`claude plugin test src/telar/sordina`): dibuja las filas de herramientas y mira
// qué quedó.
import { expect, test } from 'claude-code/testing'

const BASE = { plugin: 'sordina', surface: 'terminal', viewport: { columns: 120, rows: 40 } } as const

function fila(component: 'ToolUse' | 'ToolResult', props: Record<string, unknown>) {
  return { ...BASE, component, requestId: 'u1', props: { tool_use_id: 'u1', isErrored: false, isInterrupted: false, isRunning: false, ...props } }
}

// lo que dibujaría Claude Code donde la sordina lo deja pasar
function claudeCode(on: any) {
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['dibujo de Claude Code'] }))
  on('session.cwd', () => ({ value: '/repo' }))
}

const EDIT = {
  tool: 'Edit',
  input: { file_path: '/repo/src/a.py', old_string: 'x', new_string: 'y' },
  output: { filePath: '/repo/src/a.py', structuredPatch: [{ lines: [' ctx', '-viejo', '+nuevo', '+otro'] }] },
}

// se dibuja la fila (que recuerda la entrada) y después el resultado, como en Claude Code
async function dibujar($: any, props: Record<string, unknown>) {
  const filaUi = await $.ui.mount(fila('ToolUse', props))
  const resultado = await $.ui.mount(fila('ToolResult', props))
  return { filaUi, resultado }
}

test('una edición es una línea gris con el archivo y sus filas, sin diff', async ($, on) => {
  claudeCode(on)
  const { filaUi, resultado } = await dibujar($, EDIT)
  expect(await filaUi.find({ type: 'Text', text: 'dibujo de Claude Code' })).toBeUndefined()
  const t = await resultado.find({ type: 'Text', text: '\u270e src/a.py  +2 \u22121' })
  expect(t).toBeDefined()
  expect(t!.props.dimColor).toBe(true)
})

test('un archivo nuevo lo dice', async ($, on) => {
  claudeCode(on)
  const { resultado } = await dibujar($, {
    tool: 'Write', input: { file_path: '/repo/n.md' },
    output: { type: 'create', filePath: '/repo/n.md', structuredPatch: [], gitDiff: { additions: 7, deletions: 0 } },
  })
  expect(await resultado.find({ type: 'Text', text: '\u270e n.md (nuevo)  +7 \u22120' })).toBeDefined()
})

test('un comando es una línea gris con lo que hace y cuánto imprimió, sin su salida', async ($, on) => {
  claudeCode(on)
  const { resultado } = await dibujar($, {
    tool: 'Bash', input: { command: 'git status', description: 'Ver el árbol' },
    output: { stdout: 'a\nb\n\nc\n', stderr: '', interrupted: false },
  })
  expect(await resultado.find({ type: 'Text', text: '$ Ver el árbol · 3 líneas' })).toBeDefined()
})

test('sin descripción, la primera línea del comando', async ($, on) => {
  claudeCode(on)
  const { resultado } = await dibujar($, { tool: 'Bash', input: { command: 'make\n  test' }, output: { stdout: '', stderr: '' } })
  expect(await resultado.find({ type: 'Text', text: '$ make' })).toBeDefined()
})

test('un error, una interrupción o la vista expandida se ven enteros', async ($, on) => {
  claudeCode(on)
  for (const extra of [{ isErrored: true }, { isInterrupted: true }, { isExpanded: true }]) {
    for (const sitio of ['ToolUse', 'ToolResult'] as const) {
      const ui = await $.ui.mount(fila(sitio, { ...EDIT, ...extra }))
      expect(await ui.find({ type: 'Text', text: 'dibujo de Claude Code' })).toBeDefined()
      await ui.unmount()
    }
  }
})

test('las demás herramientas quedan como las dibuja Claude Code', async ($, on) => {
  claudeCode(on)
  const ui = await $.ui.mount(fila('ToolUse', { tool: 'Read', input: { file_path: '/repo/a.py' } }))
  expect(await ui.find({ type: 'Text', text: 'dibujo de Claude Code' })).toBeDefined()
})
