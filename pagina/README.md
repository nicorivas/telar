# pagina/ — el código de la página de telar

Aquí vive la página que sirve `telar serve --web`: la barra de hilos, el dashboard y cada hilo (terminal,
lectura, conversación, carpeta). Se escribe en TypeScript y se empaqueta con esbuild en `src/telar/web/`, que
es lo que viaja en el paquete de Python. Cómo es la página: `docs/arquitectura.md`, «La página».

Hasta el 20-oct-2026 la carpeta se llamó `vscode/`: empezó como la extensión de VS Code «telar — threads of
work» (`nicorivas.telar-hilos`), deprecada ese día. La página hace todo lo que hacía; la extensión ya no se
publica ni se mantiene. Si la tienes instalada, sigue funcionando con la versión que tengas, pero no recibe
cambios: desinstálala y usa la página.

```
npm ci                    # una vez
npm run tipos             # que los tipos cierren
npm run navegador         # compilar a src/telar/web/ (lo que se commitea)
npm run navegador:watch   # y de nuevo con cada cambio; scripts/dev.py lo usa (docs/desarrollar.md)
npm run prueba:eco        # la prueba del eco de la terminal
npm run prueba:enlaces    # la de las rutas y direcciones de la terminal, también las partidas en filas
npm run prueba:arrastre   # la de lo que se lee de un archivo arrastrado (sus rutas, citarlas, su tamaño)
npm run lint:css
```

- `src/navegador/` — la entrada de la página (`app.ts`) y el eco de la terminal.
- `src/vistas/` — la barra de hilos (`hilos.ts`) y el dashboard (`dashboard/`). En el dashboard, `panel.ts` es el
  núcleo: lee la configuración y el día, lleva las pestañas y las teclas, y le pasa cada acción a la pantalla que
  la declara. Cada pantalla (`ahora.ts`, `tareas.ts`, `bloques.ts`, `proyectos.ts`, `plan.ts`, `secciones.ts`,
  `equipo.ts`) tiene su estado, su HTML y sus acciones, y recibe del núcleo lo que dice `pantalla.ts`. Todo se
  pinta en `vista.ts`; la configuración (⚙) está en `config/`.
- `src/web/` — las vistas de un hilo, su carpeta, «compartir», la interfaz (`ui.ts`, `interfaz.ts`) y las órdenes.
  `rutas-agente.ts` vuelve enlaces al visor las rutas de archivo que escribe un agente (en la terminal, la
  lectura y la conversación), en la máquina de su hilo, y abre en una pestaña nueva las direcciones web.
  Dónde están en lo que muestra la terminal (también las que llegan partidas en varias filas) lo dice `enlaces.ts`,
  que reconoce además las direcciones de objetos (`tarea:T366`); `objeto.ts` es la vista de uno sin vista propia.
  Un archivo arrastrado a la terminal deja su ruta en el chat (`terminal.ts`, que lo sube o lo copia a la máquina
  del hilo cuando hace falta); qué rutas trae un arrastre, cómo se citan y el tamaño legible, en `arrastre.ts`.
- `media/css/` — los estilos, sobre los tokens de `tokens.css`; cada pantalla con su `@scope`, y las piezas que
  comparten (el recuadro con borde, la fila de volver) en `componentes.css`, sin `@scope`.
- `scripts/navegador.mjs` — el empaquetado.
