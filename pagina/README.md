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
npm run prueba:semana     # la de la semana del calendario: qué es cada evento, cómo se cuenta la jornada y qué toca en «ahora»
npm run prueba:arrastre   # la de lo que se lee de un archivo arrastrado (sus rutas, citarlas, su tamaño)
npm run prueba:componentes # la del ítem: sus tres secciones, lo que se escapa, dónde va cada acción
npm run prueba:buscador   # la del buscador: sus partes, su barra, el ✕, que cada buscador lo use, y lo que ⌘K pregunta afuera
npm run prueba:readme     # la del README de un proyecto partido para su detalle: secciones, vacías, resumen
npm run prueba:nota       # la de lo que dice una nota en «conexiones» de una lectura, y el documento de una carpeta
npm run prueba:temas      # la de los temas: el contraste y la luz azul de los de la noche, el tema de un mundo, los
                          # colores propios (fondos, líneas, tintas), los temas propios y dónde vive cada uno
                          # (en la raíz, para todas las máquinas, o solo en esta)
npm run lint:css
```

- `src/navegador/` — la entrada de la página (`app.ts`) y el eco de la terminal.
- `src/vistas/` — la barra de hilos (`hilos.ts`; quién se ve en ella y cómo se anida, en `hilos-familia.ts`) y el
  dashboard (`dashboard/`). En el dashboard, `panel.ts` es el
  núcleo: lee la configuración y el día, lleva las pestañas y las teclas, y le pasa cada acción a la pantalla que
  la declara. Cada pantalla (`ahora.ts`, `tareas.ts`, `bloques.ts`, `proyectos.ts`, `plan.ts` (el calendario), `secciones.ts`,
  `equipo.ts`) tiene su estado, su HTML y sus acciones, y recibe del núcleo lo que dice `pantalla.ts`. Todo se
  pinta en `vista.ts`; la configuración (⚙) está en `config/`. El calendario (en `plan.ts`) tiene el día y la
  semana (`semana.ts`); los eventos de un día cruzados con su plan están en `eventos.ts`, y qué es cada uno (una
  cita, un bloque propio de qué clase, la rutina) en `clases.ts`. El detalle de un proyecto parte su README con
  `readme.ts`. La ficha de un ítem de una pestaña de lectura (`vista = "lectura"`) la dibuja `leer.ts`, con sus
  estilos en `media/css/leer.css`; sus conexiones, las tarjetas del margen, `relaciones.ts`, y lo que dice cada nota,
  `nota.ts`.
- `src/componentes/` — las piezas que se arman igual en cualquier vista, y el catálogo que las muestra
  (`/componentes`, docs/desarrollar.md). `item.ts` es la fila de una lista (la barra de hilos): inicio con ranuras
  de íconos, texto, y fin con aviso, meta y acciones; `circulo.ts`, el círculo con que se dice un estado y lo que
  está en curso; `buscador.ts`, el buscador de toda la página (la lupa, en qué se busca, la cuenta, la tecla y el ✕;
  como fila propia, en su barra: `barraBuscar`), cuyo ✕ atiende `web/buscadores.ts`, y lo suyo en el catálogo en
  `catalogo-buscador.ts`; `anatomia.ts`, lo que nombra la lámina de sus partes; `gramatica.ts`, la gramática visual (qué
  quiere decir cada forma); `senales.ts`, las señales de estado que salen de ella y que piden las vistas;
  `temas.ts` y `densidades.ts`, los temas y las densidades y cómo se pone uno (el tema, del modo o del mundo, y las
  cuentas de su contraste; de los colores propios de un tema, la paleta, los avisos y la hoja; y los temas propios, cómo
  se conocen y cómo se copia su base); `franja.ts`, la franja de avisos de arriba de la barra (el estado del sistema y de
  los hilos); `boton.ts`, el botón con texto, «la tecla en el pie»: el pie de una ventana
  como una banda de celdas, cada una con su tecla y su palabra, a una línea del contenido (sus teclas las atiende
  `web/botonera.ts`; en el catálogo, `catalogo-botones.ts`, con qué confirmaciones destruyen); `catalogo.ts` y `muestras.ts`, el
  catálogo (empaquetado aparte, en `componentes.js`) y lo que muestra.
- `src/web/` — las vistas de un hilo, su carpeta, «compartir», la interfaz (`ui.ts`, `interfaz.ts`) y las órdenes.
  `rutas-agente.ts` vuelve enlaces al visor las rutas de archivo que escribe un agente (en la terminal, la
  lectura y la conversación), en la máquina de su hilo, y abre en una pestaña nueva las direcciones web.
  Dónde están en lo que muestra la terminal (también las que llegan partidas en varias filas) lo dice `enlaces.ts`,
  que reconoce además las direcciones de objetos (`tarea:T366`); `objeto.ts` es la vista de uno sin vista propia.
  Un archivo arrastrado a la terminal deja su ruta en el chat (`terminal.ts`, que lo sube o lo copia a la máquina
  del hilo cuando hace falta); qué rutas trae un arrastre, cómo se citan y el tamaño legible, en `arrastre.ts`.
  Los avisos de estado (sin conexión, una fuente que falla, una terminal que se cortó, una versión nueva) los guarda
  `avisos.ts`, quien los sabe los pone y los quita (`vigia.ts` mira la conexión, la sesión y las otras máquinas), y
  `franja.ts` los dibuja arriba de la barra; los toasts de `interfaz.ts` quedan para responder a lo que se aprieta.
  El buscador ⌘K es `buscador.ts`: filtra lo que le dan sus fuentes de la página y le pregunta con lo escrito a las
  remotas; lo hallado por la búsqueda de telar (`GET /buscar`), cómo se abre y la fuente «documentos» de ⌘K, en
  `hallados.ts`, que comparte con Todo.
  Los colores propios de cada tema y los temas propios (`[temas.<tema>]`, ⚙ temas) los pone `colores.ts`, con una hoja
  encima de `temas.css` (la de uno propio, con las reglas de su base copiadas con su nombre).
  El ancho de la barra de hilos y de la ficha de un hilo, arrastrando su línea (con doble clic, el de fábrica; recordado
  por pantalla), lo pone `anchos.ts`; mientras se arrastra, la terminal no se mide, y al soltar se mide una vez.
- `media/css/` — los estilos, sobre los tokens de `tokens.css` (primitivos, semánticos y de cada componente), los
  temas de `temas.css` (colores) y las densidades de `densidades.css` (medidas); cada pantalla con su `@scope`, y las piezas que comparten (el recuadro con borde, la fila de
  volver en `componentes.css`; el ítem en `item.css`), sin `@scope`.
- `scripts/navegador.mjs` — el empaquetado: `app.js` (la página), `componentes.js` (el catálogo) y `marco.css`.
