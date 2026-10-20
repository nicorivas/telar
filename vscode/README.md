# vscode/ — el código de la página de telar

Aquí vive la página que sirve `telar serve --web`: la barra de hilos, el dashboard y cada hilo (terminal,
lectura, conversación). Se escribe en TypeScript y se empaqueta con esbuild en `src/telar/web/`, que es lo
que viaja en el paquete de Python. Cómo es la página: `docs/arquitectura.md`, «La página».

La carpeta se llama `vscode/` porque empezó como la extensión de VS Code «telar — threads of work»
(`nicorivas.telar-hilos`), **deprecada el 20-oct-2026**: la página hace todo lo que hacía. La extensión ya no
se publica ni se mantiene, y su código propio se borró. Si la tienes instalada, sigue funcionando con la
versión que tengas, pero no recibe cambios: desinstálala y usa la página.

```
npm ci                    # una vez
npm run tipos             # que los tipos cierren
npm run navegador         # compilar a src/telar/web/ (lo que se commitea)
npm run navegador:watch   # y de nuevo con cada cambio; scripts/dev.py lo usa (docs/desarrollar.md)
npm run prueba:eco        # la prueba del eco de la terminal
npm run lint:css
```

- `src/navegador/` — la entrada de la página (`app.ts`), el eco de la terminal y la lectura.
- `src/vistas/`, `src/web/` — el dashboard, la barra de hilos y las páginas de cada vista.
- `media/css/` — los estilos, sobre los tokens de `tokens.css`.
- `scripts/navegador.mjs` — el empaquetado.
