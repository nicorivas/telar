# Correo entre agentes y telar en el celular

Propuesta, 24-sep-2026. Estado: **implementada en telar** el mismo día, salvo lo que se dice
al final; lo del servidor (el cartero) queda de quien lo administra. Continúa [hilos-remotos.md](hilos-remotos.md).

Dos partes que se tocan: los agentes de distintas personas ya se escriben por correo en el
servidor, y telar tiene que mostrarlo; y desde el celular hoy se entra a un hilo pero no se
puede volver.

## Lo que ya existe en el servidor (no es de telar)

Un servidor compartido donde cada persona es un usuario Linux, con sus propios agentes. Los
mensajes nativos entre sesiones de Claude Code no cruzan entre usuarios (registro, socket en
`/run/user/<uid>/cc-socks/` y llave son por usuario), así que se montó correo:

- **Postfix solo local.** Escucha en loopback, entrega solo a usuarios de la máquina; lo
  demás rebota. Cada usuario recibe en `~/Maildir`.
- **El cartero** (`/usr/local/bin/cartero`, activado por `~/.forward`, corre como el
  destinatario). Al llegar un correo lo entrega a una sesión interactiva de Claude Code de
  ese usuario con `SendMessage`, desde un `claude -p` que no tiene otras herramientas. La
  sesión lo recibe como mensaje de un par —no como orden de su humano— y **se despierta si
  estaba ociosa**. Ese era el requisito: que el receptor no tenga que ir a revisar nada.
- **Capas**: remitente = el uid que Postfix anotó («from userid N»), no el `From`; lista de
  permitidos por usuario (`~/.cartero-permitidos`); tope de 20 entregas por remitente y
  hora; cuerpo ≤ 20 KB. Todo queda en `~/.cartero.log` con una línea por evento:
  `ENTREGADO de=… a=<sesión> asunto=…`, `RETENIDO <motivo>`, `SIN SESIÓN …`.
- **Direcciones**: `usuario@servidor` va a la sesión activa más reciente de ese usuario;
  `usuario+extension@servidor` a la sesión cuyo nombre o sesión tmux contiene la extensión.
- **Enviar**: `mail -s "asunto" usuario@servidor` (mailutils).

**Decisión**: el correo entre agentes es **público dentro del servidor**. Los agentes
conversan a la vista de todos; lo privado queda entre humanos. Falta el archivo común (ver
§1.3); del lado del servidor lo monta quien lo administra, no telar.

## 1. Correo en telar

### 1.1 Una dirección por hilo

Un hilo remoto debería recibir correo en su propia dirección: `usuario+pizza@servidor` le
llega al hilo «Pizza», no a cualquier sesión de esa persona.

- Al crear un hilo remoto (y al renombrarlo), telar escribe en la **sesión tmux remota** la
  opción `@telar_hilo <nombre>` (`tmux set-option -t telar-1a2b3c4d @telar_hilo Pizza`).
- La extensión de la dirección es el nombre del hilo en minúsculas y sin espacios ni
  acentos (`T42 Faro Norte` → `t42-faro-norte`). Definir la función una vez y exponerla
  en `telar ficha --json` como `correo: "usuario+t42-faro-norte@servidor"`.
- El cartero busca la sesión por esa opción (lo ajusta quien administra el servidor; ya
  encuentra por nombre de sesión, falta leer `@telar_hilo`).
- La misma opción la usa el menú del celular (§2) para mostrar nombres en vez de
  `telar-1a2b3c4d`.

### 1.2 Pendientes por hilo (✉ N)

Un correo **pendiente** es uno que llegó y no alcanzó a ningún agente: `SIN SESIÓN`
(la sesión del hilo no estaba viva) o `RETENIDO`. Los entregados no son pendientes: el
agente ya los tiene.

- telar lee, por ssh en el refresco lento, `~/.cartero.log` y `~/Maildir` del remoto y
  cuenta los pendientes de cada hilo (por la extensión de la dirección).
- La lista de hilos muestra **✉ N** junto al nombre; la ficha, los asuntos.
- **Retomar** un hilo con pendientes se los entrega: al abrirse, el primer mensaje al agente
  es «Tienes N correos que llegaron mientras estabas cerrado:» y los correos (misma
  plantilla que el cartero).

### 1.3 La vista «conversaciones de agentes»

Una pantalla del dashboard (y de la vista del celular, §2) con los correos entre agentes:

- Agrupados por **hilo de correo** (`Message-ID` / `In-Reply-To` / `References`), el más
  reciente arriba; cada fila: participantes, asunto, cuántos mensajes, estado (entregado,
  retenido, sin sesión).
- Al abrir una conversación: los mensajes en orden, con remitente verificado y hora.
- Filtros: los míos · todos · retenidos.

**Fuente**: por ser públicos, el servidor guarda copia de todo en un archivo común legible
por el grupo de usuarios (Postfix `always_bcc` a una casilla de archivo; los permisos de la
Maildir se resuelven del lado del servidor). telar la lee con `[remotos.<n>] correo_archivo
= "/ruta/al/archivo"`; si no está declarada, la vista muestra solo la Maildir propia.

## 2. telar en el celular

**Problema.** Desde el celular se entra con `mosh usuario@servidor -- hilos`, un menú que
lista las sesiones tmux y hace `tmux attach` a la elegida. Una vez adentro, Claude Code
ocupa toda la pantalla y **no hay forma de volver**: el tmux del servidor tiene `status off`
y `prefix None` para ser invisible cuando se lo mira desde el tmux del laptop (hilos
remotos anidados). Lo que sirve al laptop deja al celular encerrado.

**Propuesta: `telar movil`**, una vista para pantalla chica que reemplaza al menú `hilos`,
más una barra de telar arriba de cada hilo abierto desde el celular.

### 2.1 La vista

Pensada para ~40 columnas y dedos:

- La lista de hilos (remotos de esta máquina) con prioridad, atención y **✉ N**.
- Las conversaciones de agentes (§1.3).
- Tocar/elegir un hilo lo abre (2.2). Al salir del hilo, se vuelve a esta vista.

Corre **en el servidor** (`telar movil` allá, con el estado que haga falta leído de ahí), para
que el celular solo necesite `mosh usuario@servidor -- telar movil`.

### 2.2 Abrir un hilo sin quedar encerrado

La clave: el celular **no se engancha a la sesión del hilo, sino a una sesión agrupada**
con ella (`tmux new-session -t telar-1a2b3c4d -s movil-1a2b3c4d`). Una sesión agrupada
comparte las ventanas —el mismo Claude, lo mismo en pantalla— pero **tiene sus propias
opciones**. Así el celular tiene barra y teclas sin que el laptop, enganchado a la sesión
original, las vea:

- `status on`, `status-position top`, una línea: `◀ telar · ✉ 2 · Pizza`.
- `mouse on` y rangos clicables en la barra (`#[range=user|volver]…`, con
  `bind -n MouseDown1Status` que mira `#{mouse_status_range}`): tocar «◀ telar» hace
  `detach-client` y se vuelve a la vista; tocar «✉ 2» abre los correos del hilo.
- Una tecla sin prefijo como respaldo (p. ej. `bind -n F12 detach-client`), que se puede
  poner en la fila de teclas extra de Termux (`~/.termux/termux.properties`, `extra-keys`).
  Documentarlo.
- Al volver, telar mata la sesión agrupada (`movil-…`); la del hilo sigue intacta.

Verificar en tmux 3.4 (el del servidor) que los rangos `user` y `mouse_status_range` se
comportan como se espera en Termux; si el toque en la barra no llega, queda la tecla.

### 2.3 Remote Control

Aparte de la terminal, cada hilo remoto puede abrirse con `claude --remote-control <nombre>`
para que aparezca por su nombre en la app de Claude (dictado por voz). Opción en
`[remotos.<n>]`: `remote_control = true`.

## Pruebas

- Nombre → extensión de correo: acentos, espacios, mayúsculas, choques.
- Lectura del log del cartero: cada tipo de línea; pendientes por hilo.
- Agrupar correos por `References` con hilos incompletos.
- Sesión agrupada: se crea con las opciones propias, la original no cambia de opciones,
  volver mata solo la agrupada.
- Sin `[remotos]` o sin correo en el servidor: nada de esto aparece.

Antes de publicar: ejemplos con `casa`, `usuario@servidor`; sin nombres propios.

## Lo que cambió al implementarla

- **Pendientes: el cartero tiene que anotar el `Message-Id`.** Su registro de hoy dice
  ENTREGADO/RETENIDO/SIN SESIÓN con el asunto, que no identifica un correo. telar cruza la
  Maildir con `id=<Message-Id>` en cada línea; sin eso, no cuenta pendientes y lo dice.
  Anotar también `ext=<extensión>` ayudaría a leer el registro, pero telar reparte por la
  dirección a la que llegó el correo (`X-Original-To`), que ya está en la Maildir.
- **Retomar no copia los correos en el primer mensaje.** Ese mensaje llega al agente con la
  voz de su humano; copiar ahí un correo ajeno le daría a quien lo escribió la voz del
  dueño, que es justo lo que el cartero evita al entregarlos como mensajes de un par.
  Retomar avisa cuántos hay y dónde, y pide leerlos antes de actuar.
- **`@telar_hilo` lo pone la sesión de allá sobre sí misma**, como lo primero que corre
  (`tmux set-option @telar_hilo <nombre>`). Encadenarlo con `;` en la línea de tmux
  funcionaba por ssh y no por mosh. Al renombrar, se actualiza por ssh.
- **Las teclas del celular van en una tabla propia (`key-table telar-movil`)**, no en
  `bind -n`: las tablas son del servidor tmux entero, y un F12 en `root` también lo habría
  recibido el laptop a través de mosh.
- **Remote Control (§2.3) no está**: queda para cuando se sepa cómo lo expone Claude Code.
- Probado contra el servidor: dirección y lectura del buzón real; crear un hilo remoto con
  «Ñ» deja `@telar_hilo`; renombrar lo actualiza; la sesión agrupada tiene barra arriba,
  mouse y su tabla, y la del hilo no cambia; `telar movil --lista` ve los hilos por
  `@telar_hilo`. No se probó tocar la pantalla de un celular.

