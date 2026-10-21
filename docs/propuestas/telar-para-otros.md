# telar para otros: primero un equipo, después cualquiera

Estado: **propuesta, por empezar**. Es el plan maestro: el orden está al final. Decidido: la extensión de VS
Code se depreca (20-oct-2026).

Hoy telar funciona bien para una persona con dos máquinas (un laptop y un servidor) unidas por un bus y
por Tailscale, y con la configuración armada a mano por esa misma persona. Esta propuesta dice qué falta para
que lo use un equipo de trabajo, después cualquiera, y qué queda de las versiones anteriores que conviene
retirar en el camino.

## Lo que bloquea a un equipo: la seguridad entre personas

Cada persona ya tiene su cuenta en el bus, que el servidor hace cumplir ([arquitectura](../arquitectura.md),
«Entre máquinas: el bus»). Lo que falta para que las personas se hablen:

1. **Retirar el correo del servidor.** El correo y el directorio entre personas ya van por el bus
   ([arquitectura](../arquitectura.md), «Entre máquinas: el bus»), con el correo del servidor de respaldo
   para quien no tenga nodo. Para retirarlo (el `cartero`, Postfix, la casilla común, `telar directorio`
   por carpeta y la lista de permitidos de `telar persona --correo`), cada persona del servidor necesita su
   cuenta en el bus (`telar bus persona`) y su nodo (`telar instalar --bus`). Antes de desinstalar Postfix:
   la salida de cron de `telar periodicos` llega por correo (poner `MAILTO=""` o mandarla a un log; con
   `always_bcc` a una casilla común, la lee todo el grupo). `enlace archivo` y `enlace notificar` no tienen
   pedido en el bus: portarlos al nodo o aceptar perderlos. Es irreversible y afecta a las otras personas
   del servidor: se decide con ellas.
2. **Más de una máquina siempre prendida**, en clúster (NATS de tres), si el equipo crece: hoy el servidor es
   un punto único de falla.

## Lo que falta para que alguien lo instale solo

- **Un día que funcione con la configuración de fábrica.** El dashboard rinde con los proveedores de quien lo
  armó (sus tareas, su calendario). Una persona nueva necesita un proveedor de tareas por defecto (una
  carpeta de markdown, que el tipo `tarea` ya sabe leer y escribir) y una guía de su primera hora. Los
  ejemplos de la documentación y de algunos docstrings todavía traen rutas de la configuración del autor.

## Un mod de Claude Code dentro de telar

Desde Claude Code 2.1.287, un *mod* es un plugin con un módulo en JavaScript que corre adentro de Claude Code:
reacciona a eventos (empieza o termina un turno, una herramienta está por correr, llega un mensaje), puede
cambiar prompts y decidir sobre herramientas, dibuja paneles o una franja sobre el prompt, y registra comandos
que corren sin gastar un turno ([referencia](https://code.claude.com/docs/en/plugins/mods/reference)).

El mod ya existe (`src/telar/mod/`, viaja en el paquete) y `telar agente instalar` lo deja cargado en cada
sesión por `CLAUDE_CODE_PLUGIN_DIRS` ([arquitectura](../arquitectura.md), «Cómo llega un mensaje»). Hoy
avisa de los mensajes de la casilla sin teclear en la terminal, lleva el semáforo de cada hilo desde
sus propios eventos ([agentes.md](../agentes.md)) y deja la conversación ya estructurada para la lectura.
Tiene sus pruebas (`claude plugin test src/telar/mod`) y el CI las corre. Por ahora no le falta nada:
la franja sobre el prompt se descartó (20-oct-2026), porque la página ya muestra quién espera.

Es JavaScript en un proyecto de Python, y el mod tiene los mismos poderes que telar (archivos, procesos,
red).

## Vestigios de versiones anteriores

- **El correo entre personas y los remotos por ssh y mosh** (`remoto.py`, `movil.py`, `correo.py`,
  `espejo.py`, el `cartero`; unas mil líneas): se van cuando el bus cruce personas (el punto 3 de arriba).
  Quien use dos máquinas sin bus queda sin semáforo ni ventanas remotas: el CHANGELOG lo dice, con el bus
  como requisito para dos máquinas.
- **El puente `en_proceso`**: algunas órdenes (`hilo llevar`, las acciones del perfil) todavía corren la CLI
  por dentro y leen su salida, en vez de ser servicios.
- **Claves viejas que se aceptan sin usarse** en `config.py` (`[enlace] no_leer`, `correo_archivo`): avisar
  primero y retirarlas en una versión.

## Funcionalidades que faltan para cualquiera

- **Registrarse en el bus desde la CLI** (decidido el 20-oct-2026 como el camino, para cuando telar salga de
  Brinca). La persona corre `telar instalar --unirse <servidor>`: su secreto se genera en su máquina y al
  servidor viaja solo su hash; quien administra el bus aprueba (`telar bus pedidos`, `telar bus aprobar`, o
  un aviso en el dashboard, quizás automático por dominio) y el bus suma la cuenta y se recarga solo. Quién
  pide se sabe de dos maneras, que pueden convivir:
  - **dentro de una red de Tailscale** (lo de hoy, y lo de Brinca): `tailscale whois` de la máquina que
    pide; la red ya cifra y ya deja entrar solo a quien se invitó (compartirle el servidor);
  - **con el bus en internet**, para quien solo quiere el bus y no la red: NATS con TLS (un dominio y un
    certificado) y un código de invitación de un solo uso (`telar bus invitar <persona>`). Sin TLS no: hoy
    las claves viajan en claro y las cifra Tailscale.
  Lo que sigue pidiendo una red privada es ver la página o las terminales de una máquina detrás de un router,
  pero eso es entre las máquinas de una misma persona.
- **Otros asistentes, en serio.** Hoy todo supone Claude Code (sus hooks, su registro, ahora el mod). Hace
  falta una interfaz de adaptador por asistente —su estado, sus mensajes, su conversación— y que Claude Code
  sea un adaptador más. El registro de vistas de un hilo (`pagina/src/web/vistas-hilo.ts`) y los
  renderizadores de la lectura ya van por ahí.
- **Varias personas en una máquina**, cada una con su acceso: hoy la página tiene una llave por máquina; falta
  entrar como persona y poder rotar la llave.
- **Inglés**: la CLI y casi toda la documentación están en español (el README, en inglés).
- **Pruebas de la página**: el CI prueba el Python; de la página solo está la prueba del eco
  (`npm run prueba:eco`).

## El orden

1. Darles cuenta y nodo en el bus a las otras personas del servidor, y retirar el correo del servidor (con ellas).
2. Para cualquiera: inglés, la configuración de fábrica, otros asistentes.
