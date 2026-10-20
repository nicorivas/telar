# Desarrollar telar

Cómo ver un cambio al tiro mientras se trabaja, y cómo llevarlo a las máquinas cuando está listo.

## La página, mientras se trabaja: `scripts/dev.py`

```
python3 scripts/dev.py                 # http://<ip de tailscale>:18780, con la llave de siempre
```

Corre dos cosas hasta ⌃C:

- **esbuild mirando** `vscode/src` y `vscode/media/css` (`npm run navegador:watch`): rehace
  `src/telar/web/app.js` y `marco.css` en menos de un segundo, con el mismo resultado que `npm run navegador`
  (minificado), así que lo que queda en git es lo que se commitea.
- **un `telar serve --web --dev` aparte**, en el puerto 18780 y su propio socket: el `serve` de siempre (el
  bus, el nodo, la página en 8780) no se toca. Se reinicia solo cuando cambia un `.py` de `src/telar`.

Con `--dev`, la página se recarga sola cuando cambian sus archivos (`/dev/cambios`, server-sent events) y
cuando el servidor vuelve de reiniciarse. Sin `--dev` esa ruta no existe y la página no la busca de nuevo.

Usa la configuración y los datos de verdad: solo cambia el código. Lo que se aprieta ahí (cerrar una tarea,
escribirle a un hilo, un atajo), pasa. Para probar sin tocar nada, una configuración aparte con
`TELAR_CONFIG` y `XDG_CONFIG_HOME` (su propia llave) y sin `[atajos]`.

Para probar la terminal con la latencia de una red lejana sin depender de ella:
`localStorage['telar.latencia'] = '500'` en la consola de la página (y recargar) la simula, la mitad a la ida y
la mitad a la vuelta; en la consola de la terminal, `__eco.estado()` dice si el eco se está mostrando y la
latencia que mide. El eco tiene su prueba, contra un Claude Code falso: `npm run prueba:eco` en `vscode/`.

Necesita telar instalado editable (`uv tool install --editable '.[serve,bus]'`): así `telar` corre el
código del repositorio. Un cambio en la extensión de VS Code (lo que no es la página) se ve con
`npm run compile` en `vscode/` y recargando la ventana de VS Code.

## Llevarlo a las máquinas: `servidor/desplegar.sh`

```
servidor/desplegar.sh                  # al servidor y a esta máquina
servidor/desplegar.sh --solo-servidor
```

Despliega lo que ya está en el remoto de git (si hay commits sin subir, se detiene). En el servidor (el
`destino` del primer `[remotos]`, o `TELAR_SERVIDOR`): `git pull`; reinstala telar si cambió
`pyproject.toml`, `npm ci` si cambiaron las dependencias de `vscode/`, compila la extensión si cambió
`vscode/`; reinicia `telar-serve` y comprueba que la API contesta y que no se perdió ninguna ventana de tmux
(los hilos). En esta máquina: compila la extensión y reinicia su `serve`. Reiniciar `serve` corta las
terminales abiertas en el navegador: se recarga la página.
