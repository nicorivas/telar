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
npm run lint:css
```

- `src/navegador/` — la entrada de la página (`app.ts`) y el eco de la terminal.
- `src/vistas/` — la barra de hilos (`hilos.ts`) y el dashboard (`dashboard/`: `panel.ts` decide qué mostrar y lo
  pinta en `vista.ts`; cada pantalla, en su módulo).
- `src/web/` — las vistas de un hilo, su carpeta, «compartir», la interfaz (`ui.ts`, `interfaz.ts`) y las órdenes.
- `media/css/` — los estilos, sobre los tokens de `tokens.css`; cada pantalla con su `@scope`.
- `scripts/navegador.mjs` — el empaquetado.
