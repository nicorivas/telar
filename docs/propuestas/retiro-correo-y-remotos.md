# Retirar lo que el bus ya reemplazó: el correo entre agentes y los remotos por ssh

Estado: **propuesta** (19-oct-2026). Inventario hecho; nada borrado todavía.

Antes del bus (`docs/propuestas/bus.md`), las máquinas se hablaban por ssh y los agentes por correo:
el espejo se empujaba por ssh, el semáforo y las ventanas de los hilos remotos se traían por ssh cada
pocos segundos, «la puerta» (`[enlaces]`) dejaba al servidor pedirle cosas al laptop, y un correo a
`usuario+hilo@servidor` despertaba al hilo con el `cartero` de Postfix. Con el bus (NATS y `telar nodo`
en cada máquina), casi todo eso tiene un camino nuevo, pero el código viejo sigue: el panel lee por ssh
cientos de cabeceras de correo en cada vuelta lenta, y el texto que leen los agentes al arrancar todavía
les enseña el correo.

## Qué se va, qué se queda

**Se puede retirar** (con bus en las máquinas):

1. `telar remotos atencion` (`remoto.atenciones`): el semáforo de los hilos remotos ya lo publica el nodo.
2. `telar remotos traer` como sondeo (y `remoto.sesiones`): el nodo trae y cierra las ventanas
   (`ventana_de`). Antes hay que cambiar el único llamador que no es sondeo: `servicios/encargos.py`
   (`encargar_y_ir`), que lo corre por el puente para traer la ventana de un agente de otra máquina.
3. El espejo por ssh: `telar espejo publicar` hacia un remoto, `espejo recibir`, `espejo traer` y el
   bucle del panel (`telar.espejo`). El espejo como módulo y `espejo ver` se quedan: los usa el nodo.
4. La puerta en los verbos que el bus ya hace: `enviar`, `leer`, `encargar`, `hilos`, `ping`
   (`ordenes/enlace.py`, buena parte de `enlace.py`, `[enlaces]`, `encargar._por_la_puerta`).
5. Lo que el panel muestra del correo: la insignia ✉, la pestaña «correo» de la ficha, la parte de
   Maildir de la pantalla «correo» (la de los mensajes del bus se queda), `telar correo` (leer),
   `correo leido`, `estado.leidos`, `_aviso_de_correo`, `[remotos.*] correo_archivo`. Y el código sin
   llamadores: `correo.leer_local`, `movil.barra`, `movil.ordenes_grupo`.

**Bloqueado, todavía sin reemplazo:**

- **El correo entre personas** (`telar correo enviar` a otro usuario, el `cartero`, Postfix, la lista de
  permitidos de `telar persona --correo`). El bus no cruza personas: un solo token, temas por persona, y
  el paso de credenciales por persona de `bus.md` sin hacer. Entre hilos de una misma persona, `correo
  enviar` ya va por el bus.
- **El directorio** (`telar directorio`, `<servidor>/directorio/<usuario>.json`): la única forma de ver los
  hilos de otra persona; no tiene sujeto en el bus.
- **`enlace archivo` y `enlace notificar`**: no tienen pedido en el bus. Portarlos al nodo, o aceptar
  perderlos.
- **Desinstalar Postfix**: además, la salida de cron (la de `telar periodicos`) llega por correo; hay que
  poner `MAILTO=""` en el bloque que escribe `telar periodicos`, o mandarla a un log. Ojo: con
  `always_bcc` a una casilla común, esa salida queda donde la lee todo el grupo.

**Núcleo, se queda:** `[remotos.*]` (destino, transporte, raíz, repos, sesión) y lo de `remoto.py` que
abre y lleva hilos (`abrir`, `traer`, `nuevas` —los usa el nodo—, `conversacion_alla`,
`copiar_conversacion`, `nombrar`, `matar`, `vive`, `revisar`, la ventana mosh), `hilo
llevar|mudar|retomar`, `ir --remoto`, `espejo.py` como módulo, `@telar_hilo`. Dos cosas a mover, no a
borrar: `correo.extension()` (la usan `casilla.nombre_de_carpeta` y los temas del bus) va a `casilla.py`, y
`[enlace] no_leer` (lo usa el pedido `leer` del nodo) a `[bus]`, aceptando la clave vieja.

## El orden

1. **Preparar sin romper**: mover `extension()` y `no_leer`; cambiar `encargar_y_ir` para que no corra
   `remotos traer`; decidir `archivo` y `notificar`.
2. **El panel**: fuera los sondeos de atención, traer y espejo (y sus ajustes), y lo que muestra del correo.
3. **Python**: fuera lo retirable de arriba, con sus pruebas y su documentación (`configuracion.md`,
   `contratos.md`, `servidor/README.md`, `bus.md`, `primitivas.md`).
4. **Lo que leen los agentes**: el contexto del arranque (`agente.contexto`) y la skill que instala
   `telar agente instalar` dejan de enseñar el correo y el directorio mientras no haya correo entre
   personas por el bus; después, `telar agente instalar` en cada máquina.
5. **La configuración de cada máquina**: revocar la llave de la puerta, quitar `[enlaces]`,
   `correo_archivo`.
6. **Después, con credenciales y temas por persona en el bus**: el correo entre personas y el directorio
   al bus, y recién entonces el `cartero`, Postfix y la casilla común. Es irreversible y afecta a las otras
   personas del servidor: se decide con ellas.

**Para quien actualice sin bus**: la versión que retire esto deja sin semáforo ni ventanas remotas a quien
use telar con dos máquinas y sin bus. Se anota en el CHANGELOG, con el bus como requisito para dos máquinas.
