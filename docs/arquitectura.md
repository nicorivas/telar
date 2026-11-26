# Cómo está hecho telar

telar junta en un solo lugar los hilos de trabajo de una persona: cada hilo es una terminal con
un agente (Claude Code, por ejemplo) trabajando en una carpeta. Alrededor de los hilos, telar
muestra lo que hay que hacer (tareas, agenda, correo) y deja que los agentes se hablen entre sí,
en una máquina o en varias.

Este documento describe cómo es telar hoy: las piezas, cómo se conectan y por dónde se enchufa lo
propio. Las claves de cada pieza están en [configuracion.md](configuracion.md); lo que falta, en
[propuestas/](propuestas/README.md).

## El dibujo

```
 lo que ves                  un proceso por máquina                 lo que hay debajo
 ──────────                  ──────────────────────                 ─────────────────

 ┌───────────────┐  HTTP    ┌──────────────────────────────┐  tmux  ┌──────────────────────┐
 │ la página     │  WS      │ telar serve (Python)         │───────▶│ una sesión de tmux   │
 │ · barra de    │─────────▶│  · la API (telar.servicios)  │        │ por máquina; cada    │
 │   hilos       │ Tailscale│  · la página                 │        │ hilo es una ventana  │
 │ · dashboard   │          │  · las terminales (PTY)      │◀───────│ con su agente        │
 │ · el hilo:    │          │  · el nodo del bus           │ ganchos└──────────────────────┘
 │   terminal,   │          │  · la página del equipo      │ del agente
 │   lectura…    │          └──┬────────────┬──────────┬───┘
 └───────────────┘             │            │          │ NATS   ┌──────────────────────┐
  navegador o celular          │            │          └───────▶│ las otras máquinas,  │
                               │            │                   │ con su telar serve   │
 ┌───────────────┐  socket     │            │                   └──────────────────────┘
 │ la CLI telar, │─────────────┤            │
 │ agentes,      │             ▼            ▼
 │ scripts       │  ┌───────────────────┐ ┌──────────────────────────────┐
 └───────────────┘  │ tu repositorio    │ │ lo tuyo, enchufado           │
                    │ + .telar/perfil   │ │ · proveedores (tareas,       │
                    │ (qué es un        │ │   calendario, lo que sea)    │
                    │ proyecto)         │ │ · tipos (objetos en archivos)│
                    └───────────────────┘ │ · módulos (modulo.toml)      │
                                          └──────────────────────────────┘
```

Tres reglas sostienen el dibujo:

1. **La lógica vive una vez.** Cada orden de la CLI y cada ruta de la API son cáscaras de una misma
   función de `telar.servicios`, que devuelve un modelo (Pydantic): el modelo es el contrato
   ([contratos.md](contratos.md)). La página no tiene lógica de datos propia: pide a la API y dibuja.
   Cualquier cosa que telar muestra, un script o un agente la puede pedir igual (`telar … --json`).
2. **telar no sabe qué es un proyecto, ni cómo son tus tareas.** Lo dice tu repositorio
   (`.telar/perfil.yaml`) y lo traen tus proveedores. telar sabe de hilos, de mensajes y de máquinas.
3. **Nada se hace a escondidas.** Los comandos son listas de palabras (sin shell), los proveedores
   no salen a la red salvo que se les pida, y una acción solo corre si el proveedor la ofreció.

## Las piezas

| pieza | qué es | dónde vive |
|---|---|---|
| **hilo** | una ventana de tmux con un agente, vinculada a una carpeta. telar recuerda su conversación, su atención y su prioridad | la sesión de tmux; el estado en `~/.local/state/telar/` ([estado.md](estado.md)) |
| **agente** | el programa que corre dentro del hilo. telar no lo pilota: lo reconoce por sus ganchos | [agentes.md](agentes.md) |
| **agente residente** | un hilo que siempre existe, con su carpeta, su memoria y su casilla; recibe encargos | `[agentes] carpeta` |
| **perfil** | lo que tu repositorio dice de sí mismo: qué carpetas son unidades de trabajo, qué archivo es su cara, qué secciones se leen | `.telar/perfil.yaml`, en la raíz del repo ([perfil.md](perfil.md)) |
| **configuración** | lo de esta máquina: dónde está el repo, qué proveedores hay, qué se muestra | `~/.config/telar/config.toml` |
| **proveedor** | un programa que le trae a telar datos de afuera, en un JSON conocido: tareas, agenda, cualquier lista | `[proveedores.*]` |
| **tipo** | objetos guardados como archivos de texto, con un modelo y acciones; telar los lee y los escribe él mismo. Hoy hay uno: `tarea` | `telar.tipos`, `[tipos.*]` |
| **módulo** | una carpeta con un `modulo.toml` que aporta de una vez una pestaña, una app, un proceso periódico o un resultado | `[modulos]` |
| **mensaje** | texto para un hilo o un agente, en cualquier máquina; llega aunque el hilo esté cerrado | `telar mensaje`; viaja por el bus |
| **periódico** | algo que corre solo cada cierto tiempo, a veces abriendo un hilo con un agente | `telar periodicos` (cron) |
| **disparador** | lo que corre un comando o manda un mensaje solo: por un reloj (un periódico), una tecla (un atajo) o un cambio (`telar cambio`) | `[disparadores]`; el de cambio lo corre el nodo |
| **nodo** | la parte de `telar serve` que habla con el bus: recibe los mensajes, avisa a los hilos, publica qué hay vivo | `telar serve --nodo` |
| **la página** | lo que se ve: la barra de hilos, el dashboard y cada hilo; también es la app del celular | `telar serve --web`; su código, en `pagina/` |

## Un proceso por máquina

Cada máquina corre un solo `telar serve`, como servicio (systemd de usuario en Linux, launchd en
macOS), con el mismo código en todas. `telar instalar` deja una máquina andando: la configuración, la
llave de la página, el `[bus]`, el servicio y los ganchos del agente, y al final `telar doctor`. Lo que cambia entre máquinas es la
configuración: el servidor tiene el calendario, las tareas, los periódicos y la página del equipo;
el laptop, sus hilos y lo que solo él puede hacer (un navegador, archivos locales).

- **La API** escucha en un socket Unix (`~/.local/state/telar/serve/telar.sock`, en una carpeta solo
  para su dueño). La CLI, si la encuentra, le pide a ella; si no, hace el trabajo sola.
- **Lo pesado que solo lee** (la lista de proyectos, los pendientes de todo el repositorio) se calcula en un proceso
  aparte, uno solo, que el servicio levanta la primera vez (`telar.aparte`): la API atiende cada pedido en un hilo del
  mismo proceso y Python corre uno a la vez (el GIL), así que unos pocos pedidos pesados tapaban la lista de hilos y la
  configuración. Lo que dan los proveedores (el calendario, las tareas, que pueden vivir en otra máquina) se guarda 30 s
  para todos los que lo piden a la vez, y cualquier pedido a la API que cambia algo lo olvida (`telar.alla`, `MEMORIA`).
  El proceso aparte sale solo cuando el servicio ya no está (uno que se apaga por una señal no alcanza a terminarlo).
- **Si un pedazo se cae, sale el proceso entero**: la API, la página, la del equipo y el nodo corren en el mismo bucle,
  y uno que termina sin que se lo pidan (un error, o uno que vuelve sin más) va al registro con su traza, apaga los
  demás y el proceso sale con 1, para que el servicio lo levante. Cada servidor espera a lo más `PLAZO_APAGAR` (5 s) a
  las conexiones abiertas, los avisos a la página (`/eventos`) terminan solos al apagarse, y si con todo no alcanzó a
  salir en `PLAZO_SALIR` (20 s), sale igual (`telar.ordenes.serve`). El 26-nov-2026 el nodo se cayó al preparar el bus
  (un corte justo después de conectar) y la página, que ya no escuchaba, esperaba para siempre a que se cerraran sus
  eventos: el proceso quedó vivo y sordo, sin una línea en el registro. El nodo ya no se cae por eso: lo intenta de
  nuevo hasta que el bus conteste.
- **La página** (`--web`) se sirve en la dirección de Tailscale de la máquina (puerto 8780; en el
  servidor, `tailscale serve` le pone HTTPS). Se entra con una llave por máquina
  (`~/.config/telar/panel.llave`), que deja una cookie; además, cada pedido tiene que venir del mismo
  origen.
- **Las terminales**: `/pty` es un WebSocket que corre `telar mirar <hilo> --enlaces` en un PTY. Con
  `?maquina=<otra>` reenvía a la de esa máquina: la dirección sale de la foto del espejo y se entra
  con el secreto del bus de la persona. `--enlaces` engancha el cliente de tmux con `-T hyperlinks`: dentro de un
  tmux 3.4 o más nuevo, Claude Code escribe un enlace de markdown (`[Doc](https://…)`) como un hipervínculo OSC 8,
  con solo «Doc» a la vista, y tmux se lo pasa a una terminal solo si ella declara entenderlos; la de la página se
  presenta como xterm-256color, que no lo declara, y sin esto llegaba «Doc» sin su dirección. Eso no alcanza para un
  hilo de otra máquina mirado por su ventana de aquí: mosh bota los OSC 8 enteros, y el tmux de allá no se los pasa a
  mosh-server. Por eso cada agente que telar arranca lleva `FORCE_HYPERLINK=0` (`telar.entorno.DEL_AGENTE`): Claude
  Code escribe «Doc (https://…)», con la dirección a la vista, y la página la encuentra por donde llegue. El PTY es la terminal
  de control de `mirar` (`terminal.con_terminal`, TIOCSCTTY): el tamaño que manda la página se le pone al PTY y el
  núcleo se lo avisa al cliente de tmux con SIGWINCH; sin eso, la ventana del hilo quedaba del tamaño con que se abrió.
- **Las máquinas**: `/maquinas` lista las del bus que sirven su página; se pasa a otra con un boleto
  firmado que vence en un minuto y sirve una vez.
- **La página del equipo** (`--equipo`) es otra app, en su propio puerto: alguien de confianza ve tus
  tareas y te sugiere prioridades, sin alcanzar nada de tu API.
- **Las tareas de fondo**: refrescar el calendario (una copia que vale 10 minutos), la foto del
  estado.

Algunas órdenes todavía corren la CLI por dentro y leen su salida (`telar.servicios.en_proceso`): los
verbos de `telar hilo` y `telar tejer`. `hilo llevar` y las acciones del perfil quedan en la CLI a
propósito (tardan minutos o heredan la terminal).

## Los hilos y tmux

En cada máquina, todo hilo es una ventana de **una sola sesión** de tmux, la del telar (`sesion` en la
configuración), marcada con `@telar_id`. Los agentes, los periódicos, la página y el laptop cuando
abre un hilo en el servidor abren ventanas en esa sesión, nunca sesiones propias.

Mirar un hilo es engancharse a una **sesión agrupada** con la del telar, fija en su ventana
(`ver-<id>-<máquina>`). Comparte las ventanas pero elige la suya, así que dos pantallas miran hilos
distintos sin moverse una a la otra. Para que sea confiable:

- telar apunta siempre a las ventanas con su sesión delante (`=telar:@3`), nunca un `@3` a secas;
- un gancho (`session-window-changed`) suelta a quien mira si su ventana deja de ser la actual;
- la dirección guardada lleva la marca (`@338/1a2b3c4d`): tmux reusa los `@N` al reiniciarse;
- `destroy-unattached` borra la vista cuando nadie la mira.

La página dimensiona la ventana (`window-size latest`). El tmux de una máquina que se mira desde
otra va sin prefijo ni barra. Pide tmux 3.5 o más: la 3.4 tiene un segfault que se lleva todos los hilos.

Si tmux se cae, el nodo sabe quién estaba vivo (lo anota cada 30 s) y `telar hilo caidos` los reabre
con su conversación.

Un hilo quieto se **duerme** (`telar.dormir`, `[hilos] dormir_tras`): el nodo cierra su agente y deja en su ventana
una línea que espera, así que el hilo sigue en su lugar de la lista con un aro tenue. Abrirlo (la página, `telar
mirar`, `ir`, `retomar`) o escribirle (un mensaje del bus, un encargo, lo que otro hilo le teclea) lo despierta: su
panel se reemplaza por el agente retomando su conversación, en la misma ventana. Lo que se mira no se duerme: una
terminal enganchada a su ventana, lo que muestra una página (que lo dice cada 30 s, `POST /mirando`) o lo que se mira
desde otra máquina (su foto lo dice, `mirando`).

## Entre máquinas: el bus

Las máquinas se unen por un servidor NATS con JetStream (`servidor/telar-bus.service`) en la que no se
apaga. Cada nodo abre una conexión saliente hacia él. Sin `[bus] url`, nada de esto corre y telar
funciona en una sola máquina.

Por el bus viajan:

| qué | dónde | para qué |
|---|---|---|
| los mensajes | stream `TELAR_CASILLAS`, tema `casilla.<persona>.<ficha>` | esperan hasta que los recoja la máquina donde vive el hilo; el mismo id no se guarda dos veces |
| el estado | almacén `TELAR_HILOS`, clave `<persona>.<ficha>` | dónde vive cada hilo, en qué anda, su conversación, su vínculo y si está archivado; cada máquina publica los suyos y se entera de los demás al instante |
| la foto | almacén `TELAR_ESPEJO`, cada 30 s | los hilos de cada máquina y la dirección de su página |
| los pedidos | `rpc.<persona>.<maquina>.<verbo>` | leer una conversación, las tareas de otra máquina, los periódicos, la bandeja del equipo, un encargo que vive allá |
| el registro | `TELAR_REGISTRO`, dos semanas | quién le dijo qué a quién, y los mensajes retenidos |
| los cambios | `cambio.<persona>.<tema>`, sin guardar | `telar cambio <tema>`: que el dashboard de cada máquina relea, y los disparadores «al cambiar» |

La respuesta a un pedido que pasa de lo que acepta el servidor de NATS en un mensaje (`max_payload`, 1 MB si no se
cambió: todas las tareas de una máquina, con su texto) viaja comprimida con gzip, y quien pidió la reconoce por sus
dos primeros bytes (`telar.bus.empacar` y `desempacar`). La que ni así cabe vuelve como un error que lo dice: antes
no salía, y el que pidió esperaba hasta su plazo.

**Entrar al bus de un equipo.** Una persona nueva corre `telar instalar --unirse` desde el clon del repositorio
del equipo, que lo declara en `.telar/equipo.yaml` (el bus, quién aprueba, los módulos, los programas que hacen
falta: telar.unirse). Su secreto se genera en su máquina y a la máquina del bus viaja solo su hash, a la
**puerta**: `POST /unirse` en la página de esa máquina, lo único que telar recibe sin la llave. La puerta atiende
solo en la máquina que tiene las cuentas del bus, solo desde la red de Tailscale, sabe quién pide por `tailscale
whois` y acepta pocos pedidos por hora de una misma dirección. Un pedido no da acceso: queda pendiente hasta que
quien administra lo aprueba (`telar bus pedidos`, `telar bus aprobar <id>`; le llega un aviso a sus otras
máquinas). Al aprobar, el hash entra a las cuentas y el bus se recarga; el nodo de la persona, que mientras
tanto intentaba conectarse, entra solo.

Las direcciones no dependen de la máquina: mudar un hilo cambia su estado, no su casilla. Cuando un
hilo nace o muere en una máquina, la otra trae o cierra su ventana al instante.

La `<ficha>` es el nombre del hilo en forma normalizada (`secretaria` por «Secretaría»), porque un tema no admite
espacios ni puntos. Esa forma junta a los nombres que solo difieren en mayúsculas, tildes o espacios, así que
dos hilos así compartirían casilla, tema y clave: lo de uno lo recibiría el otro. Por eso uno se queda con la
forma (el que la lee: vivo y, entre esos, el que la tenía desde antes) y los demás se apartan (`faro_3f9a1c`, un
sufijo que sale de su nombre exacto, el mismo en cualquier máquina; telar.casilla), y su nodo publica su estado con
esa clave: quien le escribe por su nombre exacto o por su id la encuentra ahí antes de publicar. `telar hilo hijo` y
`telar hilo renombrar` no aceptan un nombre que choca.

El nodo publica muerto un hilo de aquí que falta dos vueltas seguidas, también si murió con el nodo
apagado (la máquina se cayó, `telar serve` se reinició justo entonces): al arrancar parte de lo que el
bus da vivo en esta máquina, no de cero. Lo que el bus dice de otra máquina no lo toca, y un hilo que
otra máquina ya publica (se mudó) no lo publica muerto desde aquí. Del otro lado, la ventana de un hilo
ajeno que se cierra sola se reabre mientras el bus lo dé por vivo, pero no más de tres veces en cinco
minutos: a la cuarta, el registro dice «allá no contesta: no la reabro más», y la cuenta vuelve a cero
cuando el hilo cambia de dirección o publica otra cosa. Un estado viejo en el bus, venga de donde venga,
no se vuelve una ventana que parpadea.

**Un hilo tiene un solo dueño**, la máquina donde corre ([propuesta](propuestas/un-dueno-por-hilo.md)).
Su vínculo, su archivo y su conversación los guarda él y los publica en `TELAR_HILOS`; el nodo de las
otras máquinas deja lo último que publicó en `ajenos.json` (en la carpeta del estado, entero y
reemplazado cada vez, y caducado si el nodo deja de refrescarlo), y la lista y la página de allá lo
leen de ahí. Vincular o archivar un hilo ajeno se le pide a su dueño, y lo que se lee cambia cuando él
lo vuelve a publicar. La copia de allá (`vinculos.json`, `archivados.json`, `sesiones.json`) se sigue
escribiendo cuando el dueño acepta un cambio, pero solo se lee mientras el dueño no publique ese campo
(sin bus, con el nodo apagado, o un telar de antes allá).

**El dueño está escrito, con su época** (telar.dueno). El registro de cada hilo en `TELAR_HILOS` dice `dueno` (la
máquina) y `epoca` (sube con cada traspaso), y el nodo lo escribe condicionado a la revisión que leyó: si otro escribió
entre medio, lee de nuevo y decide otra vez. Un nodo no publica un hilo cuyo registro es de otra máquina (antes se
pisaban, y un hilo que se fue podía volver a figurar aquí); solo toma el de un hilo muerto allá si aquí se abrió otro
con su nombre (otra conversación). El traspaso son tres escrituras condicionadas: el dueño lo cede (`cede`), la que
recibe lo toma (`dueno`, `epoca + 1`), o el dueño se echa atrás (`epoca + 1`). Una de las dos gana siempre: nunca dos
dueños, aunque una máquina vuelva de dormir sin saber nada. La lista de una máquina no muestra como un cerrado suyo a
un hilo que el bus dice de otra (`ajenos.json`): no se retoma por error con su copia vieja. La página sigue al dueño
(`GET /hilo/registro`), también un traspaso en curso, desde cualquier máquina y el teléfono.

**Cómo llega un mensaje.** El nodo de la máquina del hilo lo deja en su casilla local
(`telar.casilla`). Los ganchos `Stop` y `UserPromptSubmit` del agente (`telar agente casilla`) se lo
entregan entero al terminar el turno. Si el agente está ocioso, hay que despertarlo con una línea de
aviso («↯ mensaje nuevo · …», nunca el contenido), y el gancho `UserPromptSubmit` le agrega los mensajes:

- con **el mod de telar** (`src/telar/mod/`, un mod de Claude Code que cada sesión carga por
  `CLAUDE_CODE_PLUGIN_DIRS`), el aviso lo manda el mod como un mensaje (`$.prompt.submit`) en cuanto la
  sesión queda ociosa, sin pasar por el teclado: no cae sobre lo que la persona está escribiendo. Mientras
  vive, el mod toca un archivo en la casilla (`.mod`) cada pocos segundos;
- sin el mod (o con esa señal vieja de más de 30 s), el nodo teclea el aviso en la terminal del hilo.

Un hilo cerrado se abre retomando su conversación.

**Entregado es que entró, no que se imprimió.** Claude Code mata a un gancho que se pasa de su plazo y descarta
lo que imprimió: con la máquina cargada, un gancho que alcanzó a marcar el mensaje antes de morir lo perdía. Por
eso el gancho de la casilla no lo marca entregado: lo deja **en camino** (`<casilla>/camino/`), con la conversación
del gancho (`transcript_path`), hasta dónde iba, su pid y cuántas veces se intentó. La corrida siguiente de un
gancho de la casilla, y la pregunta del mod (`telar agente mod`, cada 2 s mientras haya algo en camino), lo
revisan (`casilla.revisar`): si la cabecera del mensaje (`, id <mid>]`, que lleva todo lo que entrega la casilla,
también lo de tu persona) aparece en lo que la conversación escribió desde entonces, pasa a `entregados/`; si no
aparece, y el gancho que lo llevaba ya no corre y pasó la gracia (15 s), vuelve a esperar y sale en esa misma
corrida, marcado «otra vez» (`, id <mid>, otra vez]`) para que el agente no repita lo que ya hizo. Un encargo
queda corriendo cuando se ve entrar, y uno que se cerró entretanto no vuelve. Se busca en la cola del archivo, no
en la conversación entera, y sin descifrar sus registros: la cabecera es nuestra y un gancho cancelado no deja su
salida. Así un gancho cancelado puede hacer que un mensaje llegue dos veces, nunca cero; tras cinco intentos sin
verlo entrar se da por entregado (`sin_confirmar`). Sin `transcript_path` (otro agente), se entrega al imprimir.

Para que no los maten, los ganchos son livianos y tienen plazo holgado. Los que no pueden fallar (la casilla y el
contexto de `SessionStart`) tienen 30 s (`casilla.PLAZO_GANCHO`); los del semáforo siguen cortos. Lo que corre en
cada turno importa solo lo que usa: ni pydantic (`telar.objetos`), ni asyncio (`telar.bus`), ni `tempfile`; lo
pesado va adentro de la función que lo necesita (`pruebas/test_casilla_en_camino.py` lo vigila). Y el mod no
repite el aviso: `$.prompt.submit` resuelve al encolar, y el turno empieza recién cuando terminan los ganchos de
`UserPromptSubmit`; mientras un prompt (el aviso, o uno de la persona) espera su turno, no manda otro (si en 2
minutos no empieza, lo da por perdido). Al agente que le llegó solo la línea del aviso, `telar agente casilla
--leer` le muestra lo pendiente entero y lo da por entregado: esa salida sí la vio.

**El modo de un mensaje** (`telar mensaje --modo`, docs/propuestas/mensajes-con-modos.md) dice qué espera
quien lo manda. Sin modo es un `pedido`: lo de arriba. Un `aviso` espera aparte (`<casilla>/avisos/`): el
nodo no lo avisa, el mod no lo ve y el gancho `Stop` no alarga el turno por él; entra con el próximo turno
del hilo, junto a lo que llegue. Un `encargo` despierta como un pedido y, al dejarlo en la casilla, crea su
**Encargo** (`telar.encargo`, `<estado>/encargos/objetos/<id>.json`): un objeto `encargo:<id>` con estado
(`pedido → aceptado → hecho | falló | cancelado`), quién lo pidió, plazo y resultado, que el hilo acepta y
cierra (`telar objeto encargo:<id> cerrar`); al cerrarlo, a quien lo pidió le llega un mensaje con el
resultado. Quien lo manda guarda una nota (`<estado>/encargos/enviados/<id>.json`) para abrirlo después desde
su máquina, con el pedido `encargo` al nodo de allá. En qué anda un hilo no es un mensaje: lo dicen `telar ficha` y
`telar hilo leer` (`--modo consulta`, que los juntaba, se retiró). `telar encargar` sigue aparte, con su cola
(`telar.encargos`).

**Los disparadores** (`[disparadores.x]`, `telar.disparadores`, docs/propuestas/disparadores.md) juntan lo que
pasa solo. El de reloj se suma a los procesos de `telar periodicos` y corre desde el crontab; el de tecla se suma
a `[atajos]`. El de cambio (`al = "cambio:<tema>"`) lo corre el nodo de la máquina de los periódicos cuando le
llega ese tema, igual que un periódico (`telar.periodicos.correr`), en dos hilos propios para no quitarle hilos a
las vueltas, y con freno: uno a la vez por disparador, una sola corrida pendiente por ráfaga, 30 s entre corridas
y 12 por hora. Cada 30 s el nodo mira además el **estado deseado** (`telar.deseado`): los residentes de aquí sin
sesión van a su registro (una línea cuando cambia) y a `<estado>/deseado.json`, que lee `telar doctor`. Solo
avisa: un residente se abre cuando le llega algo, y `[agente] max_vivos` cierra a los ociosos.

**Entre hilos de una misma persona no hay aprobación.** El mensaje de un hilo propio llega como pedido
de un colega; el de otra persona, como mensaje. En lugar de la aprobación hay frenos: cada mensaje
lleva `persona` y `saltos` (la cadena se corta cuando la persona habla), y pasado el tope de saltos (6)
o de mensajes por hora de un hilo (30) se retiene en el registro hasta que la persona lo suelte o lo descarte
(`telar mensaje --descartar`: no sale nunca, queda en el registro como `descartado` con quién y cuándo, y a quien lo
mandó le llega un aviso de telar que no lo despierta ni corta su cadena). La
conversación entre un padre y su hijo directo lleva su cuenta aparte (`familia`, `telar.casilla.cadena_familia`):
no suma a la cadena de ninguno (el «listo» de un hijo no se retenía por lo que su padre habló con otros), y
vuelve a empezar con un commit en la carpeta del hijo o cuando la persona le habla a uno de los dos; el tope
frena ahí lo mismo, dos agentes que se contestan sin hacer nada. Lo retenido de las últimas 24 h se dice
además en la franja de avisos de la página (`web/detenidos.ts`): quien lo mandó lo da por entregado.

**Una cuenta por persona.** El servidor NATS tiene una cuenta por persona (`telar bus persona`,
`telar.cuentas`): su usuario es su nombre en el bus y su clave, el secreto de `[bus] token`, el mismo en
todas sus máquinas. Una cuenta es un espacio aparte: sus casillas, el estado de sus hilos, la foto de sus
máquinas y los pedidos a sus nodos no los ve otra persona, porque el servidor no lo deja. El mismo secreto
abre la terminal de otra máquina suya (`/pty?maquina=`) y firma los boletos de `/maquinas`, así que una
máquina solo acepta a otra de la misma persona. El servidor guarda solo el hash de cada clave (bcrypt).
Entre cuentas cruza solo lo que cada una exporta (`telar.entre_personas`): `correo.<persona>`, un
servicio con el que otra persona le deja un mensaje a un hilo suyo (su nodo lo guarda en la casilla del
hilo y responde; el servidor dice de qué cuenta vino, así que nadie escribe a nombre de otro), y
`directorio.<persona>`, la lista de sus hilos que publica su nodo cada 30 s. `telar correo enviar
persona+hilo@…` va por ahí si esa persona tiene nodo en el bus; si no, por el correo del servidor (el
`cartero`, en [servidor/](../servidor/README.md)), que sigue mientras otras personas lo usen.

**Cuando el bus falla.** La conexión del nodo no se rinde: reconecta cada 2 s mientras haga falta, y
cada falla que cuenta nats-py (un `nats: timeout`, una conexión rechazada, una «slow consumer») queda en el
registro de `telar serve` en una línea, la misma una vez cada diez minutos con cuántas hubo en medio
(`telar.bus.Avisador`); el corte y la vuelta también, y una vuelta breve tras un corte callado se cuenta
con el siguiente. Un cierre ordenado (al apagar el nodo) no se anota como corte. Una vuelta del nodo que
falla (con el bus caído, todas) es una línea cada diez minutos de la misma forma. Bajo launchd ese
registro es un archivo (`~/Library/Logs/telar-serve.log`) que nadie rota: `telar serve` lo deja en su
última mitad al pasar de 4 MB (`telar.salida.recortar_registro`) al arrancar y cada 30 s, aunque las
vueltas fallen; con systemd va a journald, que tiene su propio tope. Los pedidos con respuesta se
atienden cada uno en su tarea, para que uno lento no deje esperando a lo que llega detrás, con turnos
por verbo, como cuando cada suscripción iba por su cuenta: cuatro a la vez de cada uno, y los lentos de
un verbo no dejan sin turno a los de otro. Los que solo leen, varios del mismo verbo juntos; los que
escriben (y el correo de otra persona), de a uno por verbo y en orden, como antes. Con 64 de un verbo en
curso o esperando, el nodo le contesta a ese verbo al tiro que está ocupado, `{"ok": false, "ocupada": true,
"error": "<máquina> está ocupada: …"}`, en vez de dejar que quien pidió espere hasta su plazo; quien pide lo
toma como cualquier `ok: false` y puede volver a probar en un rato. Las suscripciones de pedidos y
avisos tienen tope de lo que espera (2000 mensajes, 32 MB); las dos de `kv.watch` (el vigía del estado
y el del espejo) las arma nats-py con sus límites de fábrica, que telar no puede cambiar, y por eso los
dos solo reciben: guardan lo último de cada hilo o máquina, y anotar la atención, mirar la ventana o
guardar la foto lo hace otra tarea, una vez por ráfaga. En cada vuelta, las casillas de los hilos de
aquí se piden todas a la vez (hasta 1 s) y cada mensaje se deja en su archivo fuera del bucle. Lo que se
lee del bus, y el envío de un mensaje (que lleva id, también su copia en el registro, y la del correo de
otra persona), se repite una vez si un pedido no volvió a tiempo con el bus ya conectado, dentro del
mismo plazo de antes: el reintento usa lo que quedó, si queda al menos un segundo. Si no conectó, o el
plazo se cumplió entero, no se insiste.

**Una máquina fuera de línea** (telar.alcance). Lo que el bus guarda de los hilos de una máquina es lo último que
publicó: un laptop que se apaga no alcanza a decir nada, y su estado se queda «vivo» o «dormido». Por eso lo que se
sabe de una máquina sale de su foto: está en línea mientras su foto tenga menos de `VIGENTE` (120 s), y si no, se da
por fuera de línea desde la hora de la última, siempre que el nodo de aquí esté al día con el bus (deja una marca cada
30 s mientras está conectado: sin ella, la que no tiene noticias es esta). Entonces sus hilos son **inalcanzables**:
la lista, la barra, la franja y `telar hilos --red` dicen «laptop fuera de línea desde 14:02» y no los muestran vivos
ni dormidos (lo que hacían cuando se fue va en la ayuda). Lo que se les pide no se pierde ni deja a nadie esperando el
plazo del bus:

- un **mensaje** espera en su casilla del bus (es durable) y su nodo lo recoge al volver;
- **despertarlo** (`telar hilo despertar --maquina`, el botón «despertar al volver» de la página), o retomarlo para que
  lea un mensaje si no estaba abierto, queda **en cola** en la máquina que lo pidió (`<estado>/cola/<máquina>.json`,
  uno por hilo: lo que se pide de nuevo se suma). El nodo de esa máquina lo hace cuando la foto de la otra vuelve a
  llegar, una vez por foto nueva y hasta tres veces sin respuesta; lo hecho queda anotado un día con su resultado, que
  la página dice en la franja, y al hilo que lo pidió le llega un aviso.

Con la máquina en línea, despertar va al nodo del dueño (`hilo-despertar`), que despierta al dormido en su ventana,
retoma al cerrado con su conversación y deja como está al despierto (y su foco, también). Un pedido sin respuesta dice
lo que se sabe por la foto: fuera de línea desde cuándo, o que está en línea y su telar es más viejo y no atiende ese
verbo (`telar.bus.pedir`).

**Seguir aquí con la dueña apagada** (telar.seguir; la etapa 4 de [mudanza-de-hilos](propuestas/mudanza-de-hilos.md)).
Sin réplica continua, con la máquina de un hilo apagada no hay una copia al día de su conversación en ninguna parte:
solo la que quedó en cada máquina la última vez que el hilo vivió en ella. «Seguir aquí» la retoma, y antes dice lo que
falta. Se ofrece solo donde hay copia y solo con la dueña apagada (su foto vencida y su nodo sin contestar); con ella
en línea es «traer». Para decir cuánto falta sin copiar nada, la foto de cada máquina lleva el largo de la
conversación de cada hilo suyo y cuándo creció (`conv_bytes`, `conv_crecio`). Lo toma con la época que leyó
(`tomado_de`, `hasta` en el registro) y lo abre. Cuando la dueña vuelve, cede sola, en la primera vuelta de su nodo:
cierra a su agente, deja aparte su copia si creció después de la con que se siguió (`<sid>.de-<máquina>-<fecha>.jsonl.bak`:
se puede leer, no seguir) y lo avisa en la franja de su página, con un informe. Entre que su agente despierta y que su
nodo ve el registro (unos segundos, lo que tarda en reconectarse) hay dos agentes con la misma conversación; lo que el
de la que vuelve alcance a escribir queda en lo apartado.

**Los archivados de otra máquina.** Uno archivado aquí que el registro dice de otra (aquí sin conversación, o con la
misma) se ve en el archivo de aquí como de allá (`dueno` en `telar hilos --json`; en la página, con su máquina), y
retomarlo lo abre allá, por su nodo, no la copia de aquí. Con esa máquina apagada, dice si se puede seguir aquí. Uno
que aquí tiene otra conversación es otro hilo con el mismo nombre, y es de aquí.

**Llevar un hilo a otra máquina** (`telar hilo llevar`, telar.mudanza; «traer aquí» se lo pide a su dueño). Por el
bus, también hacia una de `[remotos]` que esté en él: por ssh solo se muda sin bus (no hay dueño que compartir). Antes
de copiar se espera siempre a que el agente termine su turno (su atención deja de ser «trabajando» y su conversación
lleva 4 s sin crecer), la pida quien la pida: la página, «traer», la CLI desde otra ventana o el agente mismo, que
sigue en un proceso aparte. Después **se detiene primero y se pasa después**: el registro dice que se cede, su agente se
detiene (su panel espera como el de uno dormido, y no despierta mientras viaja), y lo que viaja es la conversación final.
Allá lo toman con la época que se cedió y lo abren; aquí su ventana se cierra, y nada se archiva. Si algo falla antes
de que lo tomen, aquí se echa atrás y su agente despierta; si ya lo tomaron, vive allá (y si no alcanzaron a abrirlo,
lo abre su nodo). Si el proceso de la mudanza muere a mitad (la tapa del laptop), el nodo de aquí se echa atrás solo,
al minuto. La conversación viaja de a pedazos por el bus (telar.replica), en las dos direcciones y sin ssh:

- **Solo lo que allá falta.** Una conversación de Claude Code solo crece al final, y junto a ella vive su carpeta
  `<sid>/` (`tool-results/`, `subagents/`, `workflows/`), que viaja con ella. Allá se dice, de cada archivo, su largo
  y la huella (sha256 de los 64 KB anteriores) de cada lugar donde su copia podría cortarse para ser un comienzo de la
  de aquí: su largo entero y, en una conversación, antes de lo que Claude anota al cerrarse. Donde una calza, se manda
  desde ahí; si ninguna, entera, y al llegar la de allá queda aparte (`<sid>.antes-<fecha>.jsonl.bak`).
- **Sin tope y retomable.** Pedazos de bytes crudos de hasta 896 KB (una línea JSON con lo que identifica al pedazo,
  y sus bytes, comprimidos con zlib si eso los achica), seis en camino a la vez por una sola conexión, leídos del
  disco de a poco. Allá se juntan en `<estado>/llegadas/<sid>/`, cada uno al final del anterior: repetido no duplica,
  y si la copia se corta (la red, la tapa del laptop, el proceso), el siguiente intento sigue desde lo juntado. Lo
  juntado y abandonado se borra a los tres días.
- **Verificada antes de tocar nada.** Al final se compara el largo y el sha256 de cada archivo; recién entonces pasa
  a la carpeta de proyecto donde lo busca el agente que arranca allá (telar.rutas calcula esa carpeta en un solo
  lugar: `/Users/ana/vida` es `-Users-ana-vida`, `/home/ana/vida`, `-home-ana-vida`). Lo de allá que aquí no está no se
  borra.

Lo que no es la conversación (telar.sin_subir; telar.mudanza, `registro_de` y `casilla_de`):

- **Lo sin subir, solo lo del hilo.** Se mira el repositorio de su carpeta (el de la raíz, si no tiene) y los
  repositorios donde escribió su conversación: lo sin commitear que su conversación escribió (Edit, Write, MultiEdit,
  NotebookEdit, también sus subagentes) es suyo; lo demás sin commitear de su carpeta puede ser de otro y no se sube;
  los commits sin subir de la rama, sí. El resto del repositorio no se mira (antes el aviso sonaba siempre). Si hay
  algo, el panel de la mudanza lo muestra por repositorio y se elige: «subir y llevar» (después de su turno, commitea
  solo lo suyo, por sus rutas, y sube con telar.git) o «llevar igual». Si nada dice que algo es suyo, no se ofrece
  subir. Sin nada pendiente, ni se ve.
- **Allá, al día.** La otra máquina dice si tiene el último commit de cada repositorio del hilo; al llegar, el que va
  atrás se pone al día con su rama de arriba antes de abrir (fetch y rebase, apartando lo sin commitear de allá y
  devolviéndolo). Si lo que llega toca algo sin commitear de allá, no se toca y se dice; si aquí quedaron commits sin
  subir, también.
- **Los hijos con rama no se mudan**: su rama y su worktree existen solo aquí. Su padre se lleva solo, con el aviso de
  que sus hijos se fusionan desde aquí.
- **Su registro y su casilla viajan con él**: del que cuelga, sus etiquetas, su prioridad, el esfuerzo de su agente y
  si es público quedan allá como estaban aquí; lo que esperaba en su casilla local se deja allá cuando abrió, y sale de
  aquí.

Medido entre un laptop y su servidor por Tailscale (24-nov-2026, `scripts/probar_mudanza.py transporte`): 115 MB la
primera vez, 19 s del laptop al servidor y 10 s de vuelta; con 1 MB más, 3 s y 1 s; igual, un segundo. Una máquina que
no atiende `replica-estado` (su nodo no está, o un telar de antes) no recibe hilos. El progreso de la mudanza queda en
la máquina que la corre (`<estado>/llevar/<hilo>.json`); la que pidió traer un hilo lo lee de allá
(`mudanza-progreso`), y su página muestra los mismos pasos; el paso grueso (cediendo, copiando, abriendo) está también
en el registro del bus.

Lo que no se puede arreglar desde aquí sin probar contra el bus real:

- **La «slow consumer» del servidor.** La que cuenta `nats-server` en su registro (`Slow Consumer
  Detected`) es suya: no alcanzó a escribirle al laptop dentro de su `write_deadline` (por defecto, 10 s) y
  le cortó la conexión. Pasa cuando el laptop duerme o la red se traba (un hotspot) mientras el servidor
  le sigue mandando el estado de cada hilo y las fotos de cada máquina cada 30 s. El nodo reconecta
  solo; para que pase menos, habría que subir `write_deadline` en el servidor o mandar menos (la foto
  solo si cambió, sin perder que la página la usa para saber si la máquina está en línea), y medirlo con
  `nats-server` delante.
- **Un laptop dormido no responde, pero sigue suscrito.** Hasta que el servidor da su conexión por
  muerta (`ping_interval`, 2 min por defecto, y dos pings sin respuesta), un pedido a esa máquina se
  queda sin respuesta hasta su plazo en vez de volver al tiro con «nadie atiende». Por eso los pedidos
  (`telar.bus.pedir`) no se reintentan: repetirlo duplicaría la espera sin llegar a nadie. Bajar el
  `ping_interval` del servidor lo acortaría; hay que probarlo con el bus real.
- **El consumidor del vigía se rehace después de cada corte** (`recreate_consumer`); mientras no hay red
  falla, y esas fallas ahora son una línea cada diez minutos, pero siguen pasando.

Git sigue siendo para el contenido: los archivos se sincronizan con `pull` y `push`, a su ritmo, y un
hilo vinculado a una carpeta que la otra máquina todavía no tiene se ve sin ficha hasta el próximo pull.

## El servidor como mainframe

Además de ser la máquina de quien lo corre y alojar el bus, un servidor puede **alojar a otras personas**
([propuesta](propuestas/servidor-mainframe.md): lo que falta). Alguien que ya tiene cuenta en el bus pide un lugar
(`telar servidor pedir`), quien administra lo aprueba (`telar servidor aprobar`), y el servidor le arma lo que una
persona necesita para tener una máquina propia: un usuario Linux sin grupos extra y con tope de memoria y CPU, su
uv, su Claude Code y su telar, y **su propio nodo** (`telar serve --nodo`) conectado a **su cuenta** del bus,
con su secreto, y su página detrás de la puerta del servidor (abajo). Desde ahí el servidor es una máquina más *de esa persona*: sus hilos viven
aquí, y los ve, los abre y les escribe desde su laptop por el bus como a los de cualquier otra máquina suya. No hay
un tipo nuevo de hilo, ni sesiones compartidas: lo de cada persona lo separan el sistema (usuarios, permisos) y el
bus (una cuenta por persona), y cada hilo sigue teniendo un solo dueño.

El pedido va por el bus al servicio `alojar.<dueño>` (`telar.alojamiento`): la cuenta del dueño lo exporta a todas
y todas lo importan (`telar.cuentas`); el servidor NATS dice de qué cuenta viene (`Nats-Request-Info`), así que
nadie pide a nombre de otro. Lo atiende el nodo de la máquina del bus. `pedir` y `estado` son de cualquiera del bus,
sobre lo suyo; `ver`, `aprobar`, `rechazar` y `quitar`, del dueño y de los admin (los roles de `telar.personas`).
Un alojamiento pasa `pendiente → preparando → activo`, o `falló` (se reintenta aprobando de nuevo), `rechazado` o
`quitado`, y se guarda en `~/.config/telar/bus/alojamientos.json`, privado. Un servidor sin puerta (abajo) le da a
cada alojado el siguiente puerto de página libre desde el 8781 (`telar instalar --web-puerto`); con puerta, ninguno.

**La puerta: una dirección para todos** (`telar.puerta`, desde la 0.7.0). Cada persona tiene su propio `telar serve`,
que corre con sus permisos; lo que no tiene es un puerto propio en la red. Todos entran por la dirección del
servidor, `https://<máquina>.<red>.ts.net`, como a un servidor web normal: `tailscale serve` le pasa cada pedido a la
puerta por un socket (`/run/telar/puerta/puerta.sock`) al que solo llega él, y la puerta sabe de quién es por
Tailscale: `tailscale whois` de la dirección que `tailscale serve` pone en `X-Forwarded-For` (y que pisa, como el
`X-Forwarded-Host`, así que el navegador no la inventa). La cuenta se busca en su tabla (`/etc/telar/puerta.toml`, la
de quien administra, y la cuenta de cada alojado en `/etc/telar/alojados.d/`, que anota el ayudante de root con la
que usó al unirse al bus) y el pedido, HTTP o la terminal por WebSocket, sigue al socket de esa persona,
`/run/telar/<usuario>/web.sock`. Ahí su telar sirve la página sin llave (`telar serve --web-socket`): la carpeta del
socket (2750, de la persona y del grupo `telar-puerta`) deja pasar solo a ella y a la puerta. Un pedido que viene del
servidor mismo no entra: llegaría desde la dirección del servidor, que `whois` da como la de quien administra. Sin
llave ni puerto por persona, ni prefijo en la dirección: la página es la misma y la dirección también; cambia quién
la pide. La puerta corre como el usuario de sistema `telar-puerta`, con su telar en `/opt/telar-puerta`, y se
instala con `servidor/telar-puerta-instalar`. Quien administra conserva además su página directa (`--web`, en el
8780 y con llave), que es la que usan sus otras máquinas.

**En la página**, la vista de máquinas (`/maquinas`) lista debajo de las tuyas los servidores mainframe que ofrece el
bus (`GET /alojamiento.json`, que pregunta `estado` al servicio `alojar.<dueño>`; si nadie atiende, la lista va vacía)
con cómo va tu pedido, y «pedir un lugar» (con una llave ssh opcional) lo manda por `POST /alojamiento/pedir`. El
secreto del bus lo pone la máquina que sirve la página, nunca el navegador. Quien administra ve ahí mismo los pedidos
de todos y los aprueba, rechaza o quita.

**Lo que necesita root, sin darle root al nodo.** El nodo corre sin privilegios y con `NoNewPrivileges`: no hay
sudo. Deja un pedido en una carpeta de buzón (`/var/spool/telar-alojar/pendientes/`), que `telar-alojar.path` vigila
y despierta a `telar-alojar.service` (root, una vez por vez); éste deja el resultado en `resultados/` y el nodo lo
lee. `servidor/telar-alojar` solo usa la biblioteca estándar y no se fía del pedido: cada campo pasa por una
expresión estricta, el archivo tiene que ser común, del dueño de la carpeta y chico, no toca usuarios que no creó él
(`/etc/telar/alojados.d/`), y lo que escribe en la carpeta de la persona (su secreto, su llave) lo escribe *como
ella*, con entorno limpio, para que un enlace simbólico suyo no lo lleve a escribir en otro lado.

**El secreto viaja una vez.** El telar de una persona usa el mismo secreto en todas sus máquinas (con él se abren las
terminales de una máquina a otra y se firman los boletos), así que el servidor necesita el suyo para su nodo. Va
dentro del pedido, por el bus; el nodo comprueba contra el hash de la cuenta que es el verdadero, lo guarda en un
archivo privado hasta aprobar, y lo borra al dejarlo en el `bus.token` del usuario nuevo. No sale en ninguna
respuesta.

## Los agentes residentes

No hay dos clases de hilo. Un hilo es siempre una conversación con una casa (una carpeta), y puede
ser de paso (se abre para algo y se archiva) o **residente**: siempre existe, recibe encargos y rota
su conversación cuando pesa. Un residente vive en una carpeta bajo `[agentes] carpeta`, con su
`CLAUDE.md`, `README.md`, `memoria/` y `bitacora.md`.

Su **definición** es un `agente.toml` al lado de su `CLAUDE.md`, opcional: un agente es el programa y el
hilo, el proceso. Hoy telar usa de ahí `nombre`, `para`, `modelo` y `residente`, y muestra el resto
(`telar agentes`, `agente:<carpeta>`). La definición es del repositorio y vale en todas las máquinas; la
configuración de cada una (`[agentes.<carpeta>]`) gana donde se cruzan. Un archivo con errores se lee en
blando: lo que está mal se ignora y se avisa, porque `telar.agentes.descubrir` corre dentro del nodo y un
error no puede callar al agente. El diseño y lo que falta: [agente-como-definicion.md](propuestas/agente-como-definicion.md).

Cada agente arranca en su carpeta, para que Claude Code cargue su `CLAUDE.md` desde el comienzo: Claude
lee los `CLAUDE.md` desde la carpeta de arranque hasta la raíz del repositorio, así que lo común a
todos los agentes va en el `CLAUDE.md` de la carpeta que los contiene. Un `@import` fuera de la carpeta
de arranque se ignora sin aviso, y `$CLAUDE_PROJECT_DIR` es la carpeta de arranque, no la raíz: los
ganchos se escriben con ruta fija.

`telar encargar <agente> "…"` (o un periódico con `agente = "…"`):

- sesión viva y libre: se le escribe el encargo;
- viva y trabajando: va a la cola, y el gancho `Stop` le entrega el siguiente al terminar su turno;
- sin sesión: se abre retomando su última conversación, o una nueva —que empieza leyendo su último relevo— si
  pasó de `[agentes] rotar_mb`. Una viva que pasa del tope rota con relevo al terminar un turno
  (telar.rotacion: le pide el relevo, `/clear`, y que lo lea).

Telar anota de qué agente es cada hilo que abre para uno (`de_agente.json`): un hilo renombrado sigue siendo
suyo.

El resultado se deja en el registro (la tarea, el estado del proyecto, la bitácora), no en la
conversación. `[agente] max_vivos` limita los hilos vivos de una máquina: antes de abrir otro, telar
cierra los ociosos que nadie mira, los residentes al final. Cerrar no pierde nada.

Cada hilo arranca sabiendo de los demás: el gancho `SessionStart` le da su nombre, su casilla y cómo
escribir a otros, y `telar agente instalar` le pone la skill `/hilos`.

## Los tipos: objetos sobre archivos

Un **tipo** es la forma de unos objetos que viven como archivos de texto (`telar.tipos`): un modelo,
sus **acciones** y sus **formatos** (lentes que leen el texto y lo editan al mínimo). El primero es
`tarea`, con dos formatos:

- **el archivo propio**: una tarea por archivo, con líneas `clave: valor`, el contexto,
  `## Conexiones` y `## Historia`;
- **la casilla**: una línea `- [ ]` de un documento, en sus dos dialectos (`@owner(…)`, `@deadline(…)`;
  y `vence:`, `!alta`, `#etiqueta`).

Leer y escribir sin cambios da los mismos bytes; una acción toca solo sus líneas.

- **Las acciones** (`completar`, `cerrar`, `reabrir`, `algun_dia`, `esperar`, `reagendar`, `asignar`,
  `anotar`, `proponer`, `responder`, `editar`, `secuela`, `conectar`) son funciones sobre el modelo,
  cada una con su precondición y su línea en la historia.
- **La carpeta** (`Carpeta`) lee un objeto con su versión (la huella del archivo) y le aplica una
  acción. Con una versión vieja, la acción se rechaza. Hay un escritor a la vez (un candado), la
  escritura es atómica, y lo escrito tiene que releerse igual a lo que se quiso escribir o no se
  escribe. Al crear, el número lo elige quien escribe, con el candado tomado.
- **El índice** (`telar.tipos.indice`) tiene los objetos en la memoria de `telar serve` y se pone al
  día por la fecha y el tamaño de cada archivo: con 300 tareas, mirar si algo cambió cuesta 1 ms. Nadie
  escribe en él: la acción escribe el archivo y el índice lo relee.

Hay dos cáscaras: `telar tipo tarea <verbo>` y las rutas `/tipos/tarea` (una versión vieja es un 409).
Desde una máquina con `[tipos.tarea] en`, la orden va por el bus a la que las tiene: hay un solo
escritor. Quien escribe commitea y sube el archivo (`telar commit`). El proveedor `tipo = "tipo"` le
da esas tareas a `telar hoy` y al dashboard, con su ficha y sus botones.

**Cuando el modelo cambie, ningún archivo lleva un campo `version`: el lector entiende la forma vieja y la
nueva**, y las dos dan la misma tarea. (La versión de la carpeta, de arriba, es otra cosa: la huella del
archivo al leerlo, que nadie escribe en él.) Un campo `version` obligaría a reescribir cientos de archivos (o a
dejarlos a medias), haría que una tarea escrita a mano o por otra herramienta sin el campo no supiera qué es, y
pondría una línea que nadie lee en cada diff. Leer las dos formas no cuesta eso: el archivo de antes sigue
siendo válido tal como está, y se reescribe solo lo que una acción toca. Así ya se lee hoy:

- un campo que el archivo no dice vale su valor por defecto, que es lo que significaba no decirlo (`estado:
  activa`, `prioridad: 2`, `area: personal`): un campo nuevo entra así;
- una línea de la historia, con hora o sin ella;
- la casilla, en sus dos dialectos y con los sinónimos de cada clave (`@owner`, `@dueño`, `@responsable`,
  `@para` o «@Ana:» al comienzo);
- el archivo propio, con los sinónimos de sus claves (`dueno`, sin ñ, es `dueño`) y la clave escrita con la
  tilde aparte.

Una clave que cambie de nombre se agrega como sinónimo, en los dos formatos, y una línea se reescribe en el
nombre que ya tenía. Una clave que el formato no conoce (`version: 2`, la de otra herramienta) no entra al
modelo y queda tal cual: leer y escribir no la tocan. Un BOM al comienzo o los finales CRLF tampoco cambian
lo que se lee, y al escribir se conservan. Lo fijan las pruebas de `pruebas/test_tarea_dos_formas.py`.

### Las casillas de los documentos

Un pendiente de un documento (una casilla `- [ ] …` de la sección `pendientes` del perfil) no es una tarea
del tipo: vive en su documento, y telar solo le cambia la marca o el responsable (`telar pendiente
--hecho/--responsable`, `telar.vinetas`). Nace sin id, y su referencia (`faro:2`) es su lugar, que cambia
cuando el documento cambia. Mientras no tenga id se la busca por su texto, y se toca solo si hay una.

La primera vez que telar la **escribe** le agrega un id al final de la línea, `<!-- id: c-1a2b3c -->`: `c-` y
seis cifras hexadecimales, único en ese documento, con una forma que no se confunde con la de una tarea
(`T84`). Desde ahí se la busca por ese id, su referencia pasa a nombrarlo (`faro:c-1a2b3c`, en vez de su
lugar; la de lugar de antes la sigue encontrando, en el lugar donde esté) y su dirección es
`pendiente:c-1a2b3c` (`telar objeto`, que la
ve con su texto, su estado, su documento, su línea y su responsable, y le aplica `hecho` y `responsable`).
La lectura (`telar.lectura`) reconoce el id y no lo muestra en el texto. Mirar o llevar una casilla a su hilo
no le pone id: solo escribirla.

Las reglas de esa escritura: un id que ya está (de telar, de una tarea, o puesto a mano) no se reescribe;
solo cuenta como id el comentario que cierra la línea, fuera de un `código` (una casilla que habla de la
sintaxis no lo toma por suyo). Se cambia una línea y el resto del archivo queda byte a byte (`\r\n`, unicode,
el final sin salto, los espacios del final de esa línea); se escribe a un temporal y se renombra, así que si no
se puede escribir el documento queda como estaba, y un archivo de solo lectura no se toca aunque la carpeta
se pueda escribir. Un documento con otro nombre (un enlace duro) se escribe en su lugar, sin temporal, para
no separarlo del otro nombre. La casilla es lo que ve la lectura: si la línea tiene un U+2028 o un salto de
página, la casilla llega hasta ahí, y el id va antes de ese carácter.

Dos casillas con el mismo id no se adivinan: en un documento, se dice, y alguien le borra el id a la copia; en
dos documentos (una línea copiada a otro proyecto, un README de plantilla), la dirección es un 409 que dice
dónde está cada una, y cada una se sigue alcanzando por su `ref`. El id solo, sin `pendiente:`, nombra una
casilla si tiene la forma de telar (`c-1a2b3c`); uno puesto a mano (`T84`) no le gana a la tarea T84 de un
proveedor: se lo nombra con su dirección, `pendiente:T84`. Dos casillas iguales sin id son dos filas en `telar
pendientes`: la lectura dice cuál es cada una entre las que dicen lo mismo (la primera o la segunda de dos, en
el orden del documento; `repetida` en la fila), y se le escribe a esa, que recibe su propio id. Si entretanto
cambió cuántas casillas dicen eso (alguien agregó o borró una igual), no se adivina: un 409, y nada cambia.

### Lo que un hilo espera

Cuando el agente de un hilo necesita a la persona (un diálogo de permiso, la pregunta de un MCP), su atención
pasa a `espera`, y eso es todo lo que telar sabía. Ahora la espera es además un objeto, `permiso:<hilo>`, de
solo lectura: qué hilo espera, desde cuándo y, si su agente lo dijo, qué pide. El texto lo trae el gancho
`Notification` de Claude Code (su `message`) o `telar agente evento --evento espera --pide "…"`, y queda en
`<estado>/esperas.json`, uno por hilo. Vale para la espera que empezó cerca de cuando se anotó (unos segundos:
el gancho y el mod de telar avisan casi a la vez y en cualquier orden); uno de una espera anterior no se
muestra. Por eso lo anota también el gancho clásico cuando el mod está vivo, aunque ahí la atención la escriba
el mod. De un hilo de otra máquina se sabe que espera y desde cuándo (lo publica su dueño), no qué pide.

Un permiso no se contesta desde aquí: eso es lo que sigue ([propuestas/permisos.md](propuestas/permisos.md)). Lo
que el agente pregunta con opciones (AskUserQuestion), sí: el mod de telar deja la pregunta abierta en la casilla
(`mod/pregunta.json`) y, mientras el diálogo espera en la terminal, mira si telar le dejó la respuesta
(`mod/respuesta.json`, de `POST /hilos/responder`); la primera que llega gana, y la de afuera cierra el diálogo como si
la hubieran elegido ahí. La vista conversación la muestra en el lugar de la caja y la contesta así, también a un hilo de
otra máquina (pedido `responder` por el bus). El contrato, en [contratos.md](contratos.md), «telar hilo leer».

### Lo que espera a la persona, junto

Hay varias maneras de que algo espere una decisión de la persona, y cada una vive donde vive: el permiso o la pregunta
en vivo de un hilo (la terminal, `esperas.json`, `mod/pregunta.json`), lo que un agente dejó para decidir en una tarea
(su `avance`, en el archivo de la tarea), un mensaje que el freno de cadenas retuvo (el registro del bus). `telar
esperas` (y `GET /esperas`) las junta en una sola lista, sin mover ninguna de su lugar
([propuestas/lo-que-espera-a-la-persona.md](propuestas/lo-que-espera-a-la-persona.md)):

- **El contrato es de cada tipo de objeto.** `Tipo.esperando(ctx)` (`telar.objetos`) da los suyos que esperan, una
  `Espera` cada uno: su dirección, una clase (`permiso`, `pregunta`, `avance:<marca>`, `retenido`), desde cuándo, un
  título, un resumen corto, sus enlaces (el hilo o el proyecto) y lo propio en `campos`. Lo saben `permiso` (los hilos
  vivos en espera; de otra máquina, según la foto que publica, si sigue en línea), `tarea` (las abiertas con `avance`,
  pedidas a la máquina donde viven) y `mensaje` (un tipo de solo lectura sobre el registro del bus: `mensaje:<id>`).
  Un módulo suma los suyos con `[objetos.X] esperando = "<orden>"`, una consulta suya.
- **El servicio las junta** (`telar.servicios.esperas`): pide a la vez a cada tipo que sabe esperar (dos esperan al
  bus), ordena de la más vieja a la más nueva, y lo que no pudo leer de una fuente lo dice en `fallas` sin tirar las
  demás. Es de solo lectura: nada de aquí contesta, suelta ni toca el `avance` de una tarea. Cada cosa se contesta
  donde vive, por su dirección (`telar objeto`).
- **Lo que cuesta, preguntado seguido.** El número de la barra la pide cada tanto, y dos fuentes cruzan la red. El
  registro del bus se lee por partes (`bus.registro_al_dia`): `telar serve` recuerda, por secuencia del stream, lo que
  ya leyó; al bus le pregunta hasta dónde va y le pide solo lo nuevo, sin `asegurar` los streams (unos 4 s la primera
  vez desde el laptop; después, 1 s, casi todo conectar). Las tareas que viven en otra máquina se reusan si se leyeron
  hace menos de 30 s (`Tarea.RECIENTE`), porque allá cada pedido corre `telar tipo tarea lista` entero.

- **En la página**, es la pestaña «te esperan» del dashboard (`vistas/dashboard/esperas.ts`): los grupos por clase,
  con los hilos que esperan ahora siempre arriba (un agente detenido en su turno) y después las decisiones que te
  piden (la clase `decide`: las preguntas que un agente deja en un repositorio, del módulo preguntas), cada uno de lo
  más viejo a lo más nuevo, con buscador y filtros por grupo. Su fila en DASHBOARD lleva el número de lo que pregunta
  (los hilos que esperan, las decisiones y las preguntas en las tareas), que la pantalla relee cada minuto y medio
  mientras la página se ve (`PestanaDashboard.cuenta`, en `vistas/hilos.ts`).
- **También en «táctica»** (`vistas/dashboard/tactica.ts`, la vista de partida del orden por modos; por ahora una pestaña
  más, la primera de DASHBOARD): su bloque Decidir son las mismas esperas en el orden de la urgencia
  (`vistas/dashboard/urgencia.ts`: alguien espera > vence hoy > el plan la puso hoy > vence esta semana > antigüedad, sin
  la marca de un agente; la deuda no entra), hasta siete filas, en lotes: las preguntas `decide` de un mismo agente, los
  retenidos todos juntos y, de lo demás, lo de una misma clase y un mismo proyecto. Su barra lleva cuántas decisiones
  esperan (todas, no solo las que preguntan). Un lote se contesta en la misma ventana, una tras otra. Las filas de
  tareas (las de las vías y las de Hacer) llevan al pasar el mouse el ícono de fecha de la lista de tareas: mover la fecha
  no contesta lo que espera, que sigue en su vía.
- **Y la deuda, en el filtro «deuda» de tareas**: lo vencido hace más de 30 días. El modo estrategia (mirar con calma) no
  tiene pantalla propia: abre en proyectos, con el tablero y las decisiones (módulos tablero y registro) como sus
  otras pestañas. La pantalla «estrategia», que juntaba esas fuentes en un recorrido, se sacó el 19-nov-2026
  (`telar.config.PESTANAS_RETIRADAS`).
- **Se contesta en una sola ventana** (`web/contestar.ts`, que dibuja `componentes/contestar.ts` sobre `ventana()` y abre
  `abrirVentana`, `web/ventana.ts`): un clic en la fila. Arriba el resumen, las opciones como filas que se eligen,
  «Otra cosa…» (texto libre) y abajo «conversarlo» (la instrucción con la espera
  como contexto; la de una pregunta de un agente va de entrada a quien preguntó) o «ir al hilo». Dos clics: uno elige y
  el otro hace lo elegido, por el camino que ya existía: el `avance` de una tarea, `responder` (no le avisa al agente:
  queda en su historia) o, si propone cerrarla, `cerrar` como propone; un retenido, `soltar` o `descartar` (que pregunta
  antes, con el foco en «cancelar»); la pregunta en vivo de un
  hilo, `POST /hilos/responder`, como la vista conversación; la de un módulo (`decide`), su acción `responder` con
  `opcion` o con `texto`. Todo sobre la versión que se leyó: si cambió (409), la ventana relee la espera y lo dice, sin
  mandar nada. Un permiso de la terminal no se contesta ahí: la ventana lo muestra y ofrece ir al hilo. Al pasar el
  mouse por la fila, abrirla donde vive (su objeto, la tarea en su ficha) o ir a su hilo; de un retenido, además,
  soltarlo (abre la ventana con «Soltarlo» elegido) o descartarlo (pregunta y lo hace), y con varios, la cabecera de su
  grupo los descarta todos (la pregunta dice cuántos).
- **Lo que hace recordar, a la izquierda** (`componentes/ficha-contestar.ts`): de una tarea o de una pregunta de un
  módulo, la ventana crece y responde sin abrir otra cosa de qué se trata (el contexto entero), cómo se llegó aquí (la
  historia, con quién: tú, el agente, lo que aplicó, una reunión; la creación y las últimas cuatro a la vista, lo del
  medio plegado), qué está en juego (el peso, quién espera, la fecha y si es dura, lo que bloquea) y qué hay
  relacionado (de dónde salió, dónde se trabaja, el proyecto con su estado y las otras tareas abiertas, como enlaces que
  se abren en la página). La tarea entera se lee al abrirla (`GET /tipos/tarea/<id>`), y su proyecto (`GET /proyectos`,
  una vez por página) y las otras del proyecto (`GET /tipos/tarea?proyecto=…`) después; lo que todavía no llega, se
  dice. De una pregunta de un módulo, su resumen, su porqué, su detalle y su archivo. Lo que se pide y las opciones,
  enteras, a la derecha; en el teléfono, una pantalla con las dos una debajo de la otra.
- **La barra de la tarea, en el encabezado** (`vistas/dashboard/barra-tarea.ts`): la misma de su ficha en la vista
  tareas, con sus íconos, colores y globos: la estrella y compartir delante del título, y al final la fecha, esperar a,
  la prioridad, quién la hace, el tamaño, hecha y descartar, menos lo que la ventana ya hace a su manera (al cerrar, hecha
  y descartar son sus opciones; en lo que pide hacer, hecha es «Hecho»; la instrucción es «conversarlo»). Llega con la
  ficha de su proveedor (`GET /tareas/<id>`), y cada una corre como en la ficha (`tareas.ts`, `correrAccion`: la fecha
  con elegirFecha), sin cerrar la ventana: la tarea se relee y lo que se conteste va sobre su versión de ahora. Mover la
  fecha, la prioridad o el tamaño no contesta la propuesta; esperar a alguien, hecha o descartar sí, y la ventana se
  cierra con lo hecho. Sin teclas, para no pisar las de la ventana.

La forma, en [contratos.md](contratos.md), «telar esperas --json».

## La página

Se escribe en TypeScript (`pagina/src/`) y se empaqueta con esbuild (`pagina/scripts/navegador.mjs`)
en `src/telar/web/`: `app.js` y `marco.css` (los estilos de `pagina/media/css/`). xterm.js va aparte, en
`src/telar/web/xterm/`, y se carga la primera vez que se abre una terminal. Cómo desarrollarla con recarga
sola: [desarrollar.md](desarrollar.md).

Todo vive en un solo documento, sin marcos: cada pantalla se dibuja en un elemento de la página, y su CSS va
con `@scope` (`#barra`, `.v-dia`, `.v-terminal`…), para que sus nombres sean solo suyos. Solo van en un iframe
los lienzos y las apps del dashboard, que son páginas de afuera (aisladas con `sandbox`).

- **La barra de hilos**: los de esta máquina y los de las demás en una sola lista, con la máquina en
  una columna (⇄). Un hilo de otra máquina se nombra `máquina:hilo`. «+ nuevo», en la cabecera de HILOS,
  abre uno (`POST /ir` con `crear`). Está en `pagina/src/vistas/hilos.ts`. Quién se ve y cómo se anida, aparte y
  sin la página (`vistas/hilos-familia.ts`): lo que el modo y el mundo puestos dejan ver, y lo que el mundo deja afuera
  en una fila plegada al final de HILOS («de personal»), cada hijo bajo su padre en las dos. El hilo que se mira se ve
  siempre, con su familia: sus padres (para quedar anidado) y sus descendientes, de esta máquina y de las otras; si es
  el hijo de un agente, el agente. Un hilo va sangrado y con «↳» solo bajo su padre, y solo si el padre se ve en la
  misma sección; si el padre es un agente, va bajo el agente, en AGENTES, con los suyos debajo. Si el padre no se ve
  (archivado, de otro mundo, en otra máquina sin ventana aquí), va suelto, y de quién cuelga lo dice su ayuda. Dos con
  el mismo título (el de la ficha de su carpeta) van cada uno con su nombre.
  ARCHIVO, al final de HILOS, lista los archivados de esta máquina y, después, los de las otras, de su foto
  (`archivados`), con su máquina en la columna de dónde vive: un clic muestra su conversación, y «retomar en M» lo
  abre allá. Uno de allá que aquí ya está, o que vive en alguna máquina, no se repite; el mundo los filtra como a todos.
- **El dashboard**: las pestañas del día (tareas, agenda, correo, lo que traigan los proveedores y
  los módulos), que son las filas del grupo DASHBOARD de la barra. La configuración es el ⚙ de la cabecera:
  un menú vertical de secciones (pestañas, calendario, hilos, modos, mundos, temas, glifos, agente, periódicos, agentes, módulos), cada una
  en su archivo de `vistas/dashboard/config/` y nombrada en su registro (`configuracion.ts`): una sección nueva
  es un archivo más.
  `vistas/dashboard/panel.ts` es el núcleo: lee la configuración y el día, lleva las pestañas y las teclas, y le
  pasa cada acción a la pantalla que la declara. Cada pantalla (táctica, ahora, tareas, los bloques, proyectos,
  el calendario, las secciones, el equipo, «te esperan») vive en su archivo con su estado, su HTML y sus acciones, y recibe del
  núcleo lo que dice `vistas/dashboard/pantalla.ts`: una pantalla nueva es un archivo más. Todo se pinta en
  `vistas/dashboard/vista.ts`, que filtra, ordena y atiende los clics y las teclas. Sus atajos valen solo mientras se ve, y nunca mientras se escribe en un campo
  de afuera (el buscador de la barra, una terminal). El calendario tiene dos vistas, el día y la semana de lunes a
  viernes (`vistas/dashboard/semana.ts`), con el mismo dibujo: una cita (con otras personas) va llena, un bloque
  propio va rayado y del color de su clase, la rutina es una línea, y lo que se cruza se marca. Qué es cada
  evento lo decide `clases.ts`, con lo que dice el plan del día o, si no hay, con sus invitados y su título. La
  semana dice además en qué se va su jornada: las horas por clase, lo libre y lo estratégico bloque por bloque.
- **Un hilo** tiene vistas, en un registro (`pagina/src/web/vistas-hilo.ts`): la terminal (⌥T), la lectura (⌥L,
  solo la respuesta final del agente, con un renderizador por fuente; la conversación la deja el mod de telar en
  la casilla, y sin él se lee del registro del agente) y la conversación (⌥C). A su derecha, su barra (`web/lado.ts`), con
  una pestaña por hoja: la ficha de su agente, sus notas (`web/borradores.ts`, ⌥B: los próximos prompts, que guarda
  telar), sus códigos y su contexto. Una vista nueva es una entrada del
  registro, con su `montar`: se dibuja en un elemento de la página y se cierra cuando ya no hace falta (de las
  terminales quedan abiertas las ocho últimas). «Compartir» se dibuja igual (`web/compartir.ts`). En las tres vistas,
  las rutas de archivo que escribe el agente son enlaces al visor de documentos (`web/rutas-agente.ts`), en la máquina
  del hilo. El visor (`web/carpeta.ts`) no es una vista: es una ventana (`abrirVentana`) encima de lo que se mira,
  que se cierra con su ✕ o ⎋ y deja todo como estaba, con el foco donde estaba; `navegador/app.ts` abre ahí `arch:<ruta>`
  y `doc:<hilo>` (la carpeta del hilo y su documento), y venga de donde venga (un enlace, ⌘K, Todo, un aviso, una
  dirección, un nombre suelto que tiene varios candidatos) es el mismo. Una relativa es de donde arrancó
  el agente, que según `[agente] carpeta` es la carpeta del hilo o la raíz: se prueba primero la del hilo y
  después la raíz, y se abre la que existe. El visor lee una lista cerrada (`telar.servicios.archivos`): la raíz,
  `[repos]`, lo que declaran las apps y la carpeta de un hilo de esa máquina aunque esté fuera de la raíz (su
  vínculo, o el worktree de un hijo con rama), resuelta, sin un enlace que escape; y recorre la carpeta que
  contiene el archivo sin salirse de ella. Una de otra máquina va como `máquina:ruta` (la carpeta del hilo,
  relativa a la raíz de allá, con `../` si está fuera): el backend se la pide a esa máquina por el bus
  (`archivo-leer`, con `documento`), que la arma con sus límites, y las rutas vuelven con la máquina delante para
  seguir recorriendo allá. Una dirección web (texto, un enlace, o un hipervínculo OSC 8 de la terminal) abre una pestaña
  nueva en el navegador de la persona. En la terminal, una ruta o una dirección que llegó partida en varias filas
  se encuentra entera (`web/enlaces.ts`): Claude Code corta él sus líneas al ancho de su caja, con saltos de
  verdad, así que una fila que llega al borde derecho sigue en la de abajo si lo que cruza el corte es más largo
  que una fila. La dirección de un objeto (`tipo:id[@máquina]`: `tarea:T366`, `hilo:Telar`, y los tipos de los
  módulos, que dice `/api/objetos/tipos`) también es un enlace: `navegador/app.ts` abre una tarea en su ficha, un
  archivo o un proyecto en el visor y un hilo como la barra, y cualquier otra en la vista del objeto
  (`web/objeto.ts`: `/api/objetos/<dirección>`, con sus enlaces y sus acciones). Un `.html` el visor lo muestra
  dibujado, en un iframe aislado (`/api/archivos/ver`, con `sandbox`: sus scripts no ven la llave ni la API de la
  página), con su código a un clic. Al final del archivo, sus conexiones en el grafo (`/api/modulos/grafo/vecinos`,
  si la máquina del archivo tiene el módulo): se piden después de mostrarlo, porque el grafo lee el repositorio
  entero, y la barra dice cuántas hay. La primera fila del visor es la barra de una pantalla con el nombre del
  archivo; un enlace a otro archivo lo abre ahí mismo, y «‹» delante del nombre (o ⌫) vuelve al anterior. Un .md o un
  texto se **comenta**: se selecciona texto y la tecla c (o el botón que aparece) abre la barra de la derecha con la caja para escribir; el
  comentario va al archivo de al lado, `.<nombre>.marginalia.json` (`/api/comentarios`, telar.comentarios; el formato,
  en docs/contratos.md), anclado a la cita de la fuente (`web/fuente.ts` lleva lo seleccionado sobre el markdown
  dibujado al texto fuente: las líneas de cada bloque, que markdown-it da, acotan la búsqueda, y la búsqueda por letras
  y números calza la cita a través de los `**` y los enlaces). Los comentarios que hay se marcan sobre el texto apenas,
  con su número al final del tramo, y van en la **barra de la derecha** del visor (`web/documento-lado.ts`, plegable y
  de ancho arrastrable como las de la página): una pestaña para los comentarios, en el orden del documento y con el mismo
  número (estado, lo respondido, responder, resolver, editar, borrar: `web/comentarios.ts`), y otra para las conexiones
  del grafo; en el teléfono, una hoja que sube desde abajo. Su
  **modo lectura** (el modo revisión: de entrada en el modo foco, o con su ícono o la tecla l) dibuja el .md en la
  prosa (`media/css/prosa.css`: la letra con serifa, el ancho de lectura y los estilos del markdown, los mismos de la
  lectura de un hilo, que los comparte), en una columna al medio de una ventana más grande, con la barra a la derecha sin correrla si cabe. Un archivo arrastrado a la terminal deja su ruta en el chat: en la
  caja de abajo, donde está el cursor; sobre la terminal, pegada sin ⏎. Si el arrastre trae la ruta (VS Code, una
  terminal, Safari con el Finder), se usa; si trae solo el archivo (Chrome con el Finder, Windows), la página
  pregunta y lo sube. Para un hilo de otra máquina, o para lo subido, el archivo va antes a la carpeta de entrada
  de la máquina del hilo (`POST /api/archivos/entrada`: a otra máquina, por ssh como `telar imagen`; hasta 200 MB, sin pisar nada)
  y se escribe la ruta de allá. Lo que se lee del arrastre está en `web/arrastre.ts`; nunca se navega al archivo.
- **La barra de la derecha** (`web/lado.ts`) acompaña a todo hilo, con hasta tres hojas: la ficha de un agente residente
  (`/api/agentes/del-hilo`) y los **códigos** que nombra el hilo (`web/codigos.ts`, `/api/codigos`: `H3`, `PEN-07`,
  `T84`). Los códigos los calcula `telar.codigos` en la máquina del hilo (otra, por el verbo `codigos` del bus):
  reconoce las tres formas en que un documento de la carpeta vinculada define uno (un título, una fila con el
  código en la primera columna, una viñeta en negrita), se queda con los que se nombran fuera de su archivo o en
  la conversación, los agrupa por prefijo con el nombre de su sección, y relee un archivo solo si cambió. La hoja
  los muestra con una caja para buscar y el detalle de cada uno (su definición, el archivo y dónde más se nombra);
  una tarea, con lo que da `/api/objetos`. Los códigos que la hoja conoce son además enlaces en la terminal, la
  lectura y la conversación del hilo (`web/enlaces.ts`, `web/rutas-agente.ts`): un clic (en la terminal, ⌘-clic)
  abre la barra en esa hoja, con el código abierto; cuando llegan códigos nuevos (`telar:codigos`), las vistas enlazan lo que ya dibujaron. Por
  qué y lo que queda: [propuestas/codigos.md](propuestas/codigos.md).
  La tercera, **contexto** (`web/carga.ts`, `/api/contexto`), está en todo hilo: cuánto pesa ahora el contexto de su
  conversación, desde cuándo (que empezó, el último /clear o la última compactación) y de qué está hecho, en siete
  grupos (lo de Claude Code, lo que carga al empezar, al entrar a carpetas, lo que leyó, lo que se repite, lo de otros
  hilos y la conversación), con las partes del total en una franja (`componentes/partes.ts`) y, al abrir un grupo, cada
  cosa con su ruta, su tamaño y cuántas veces entró. Sirve para ver cuánto pesan los archivos generales contra lo que
  el hilo leyó. La lee `telar.conversacion.carga`, el mismo lector de la conversación, de a poco (guarda hasta dónde
  leyó y sigue de ahí cuando el archivo crece); qué registro dice qué lo sabe el adaptador del agente
  (`telar.agente.carga_claude`, que junta en `telar.agente.carga`). De otra máquina, por el verbo `contexto` del bus.
- **La terminal** es xterm.js sobre `/pty`, con un eco predictivo propio (`pagina/src/navegador/eco/`): dibuja
  al tiro lo que se escribe y lo confirma con lo que llega. Se reconecta sola si se corta. Lo que un programa de
  la terminal manda al portapapeles (OSC 52) pasa al de la persona: así se copia de un hilo de otra máquina, donde
  el mouse lo tiene el tmux de allá. Nada de la terminal puede leer el portapapeles.
- **Los avisos y diálogos** (un aviso que se va solo, un campo para escribir, un texto largo con a quién va, un
  menú para elegir, un aviso con botones) los pone la página misma, encima de todo (`pagina/src/web/interfaz.ts`):
  se ven mire uno lo que mire, también la lista en el celular. El dashboard, la barra y las órdenes `telar.*` los
  piden a `web/ui.ts`, que también sabe abrir un enlace, mostrar un hilo o una carpeta, y correr una orden.
- **En el celular** es una app instalable (manifiesto y service worker en `web/app/`), y la hoja
  «compartir» del teléfono lleva un enlace o un texto a un hilo (`/compartir`).

## Cómo se mueve una cosa

**Un hilo pide atención.** El agente termina y espera respuesta. El mod de telar (o, sin él, el gancho
clásico; los dos llaman a `telar agente evento`) anota «te espera» en el estado; el nodo lo publica en el bus y la barra de cada máquina lo pinta.
«Terminó» y no lo viste cuenta como «te espera».

**Un agente le pide algo a otro.** El hilo A corre `telar mensaje B "…"`. El mensaje va al bus, el
nodo de la máquina de B lo deja en su casilla, y el gancho de B se lo entrega al terminar su turno.

**Una tarea se trabaja.** El dashboard pide las tareas (`/hoy`, que consulta al proveedor). Con ▶,
telar busca el hilo de la tarea: el que lleva su id en el nombre, el que tiene su carpeta en el texto
o el que calza con una etiqueta. Si no hay ninguno, abre uno nuevo con el agente y le da la tarea como
primer mensaje. Con ✓, corre la acción «hecha» que el proveedor ofreció.

## Por dónde se enchufa lo propio

| quiero… | se hace con | sin escribir código |
|---|---|---|
| que telar entienda mis proyectos | el perfil (`.telar/perfil.yaml`) | sí |
| ver mis tareas | `[proveedores.tareas]`: `markdown`, `tipo` o `comando` | sí, con `markdown` o `tipo` |
| ver mi agenda | `[proveedores.calendario]`: iCal o `gws` | sí |
| una pestaña propia en el dashboard | `[vistas.x]` con `aparece = "pestana"`: un comando que imprime una página (antes `[bloques]`, que se sigue leyendo) | no: un script |
| una app (un juego, un visor) | `[vistas.x]`: una página, un archivo o una URL (antes `[apps]`) | depende |
| algo que corra solo | `[disparadores.x]`: un reloj (`cuando`), una tecla o un cambio; o `telar periodicos crear …` | sí |
| un agente residente | su carpeta con `CLAUDE.md` y, si se quiere, un `agente.toml` (nombre, para qué, modelo) | sí |
| empaquetar todo lo anterior | un módulo con `modulo.toml` | — |
| que otro agente o script use telar | la CLI con `--json` o la API ([contratos.md](contratos.md)) | — |
| integrar otro agente | sus ganchos, con los seis eventos ([agentes.md](agentes.md)) | casi |

## Conectar un sistema de tareas

Hay cuatro niveles. Cada uno agrega algo al anterior, y se puede parar en cualquiera.

### Nivel 1: casillas en tus documentos (sin código)

Si tus tareas ya son casillas de markdown en los README de tus proyectos, basta con decirle a telar
dónde mirar:

```toml
# ~/.config/telar/config.toml
[proveedores.tareas]
tipo  = "markdown"
rutas = ["proyectos/*/README.md"]
encabezado = '^##\s+Pendientes'     # opcional: solo esa sección
```

Cada casilla es una tarea, y entiende unas pocas marcas:

```markdown
## Pendientes
- [ ] Medir el alcance real  vence:2026-06-30  !alta  #faro
- [>] Ajustar el giro  espera:@electricista
- [x] Montar la lámpara
```

`[>]` es «en curso», `espera:` saca la tarea de lo urgente (depende de otro), y como la tarea vive en
la carpeta de un proyecto, telar ya sabe a qué hilo va.

### Nivel 2: una carpeta de tareas, que telar escribe (sin código)

Si quieres una tarea por archivo, con su historia, y que telar las cambie él mismo (✓, reagendar,
anotar), usa el tipo `tarea`:

```toml
[tipos.tarea]
carpeta = "~/notas/tareas"     # un T84.md por tarea

[proveedores.tareas]
tipo    = "tipo"
carpeta = "~/notas/tareas"     # la misma
```

La ficha y sus botones salen de las acciones del tipo; desde la terminal, `telar tipo tarea …`.

### Nivel 3: tu propio gestor, por un puente (un script)

Si tus tareas viven en otra parte (un `todo.txt`, Todoist, una base de datos, una CLI propia),
escribes un **puente**: un programa que las imprime en el JSON que telar espera.

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
```

El programa imprime una lista. Solo `texto` es obligatorio:

```json
[{"id": "T84", "texto": "Medir el alcance", "prioridad": "alta", "vence": "2026-06-30",
  "etiquetas": ["faro"], "espera": "", "en_curso": false, "area": "trabajo"}]
```

Un puente completo para un `todo.txt` (el formato de [todotxt.org](http://todotxt.org)):

```python
#!/usr/bin/env python3
"""Las tareas de ~/todo.txt, en el JSON de telar."""
import json, re
from pathlib import Path

PRIORIDAD = {"A": "alta", "B": "media", "C": "baja"}
tareas = []
for n, linea in enumerate(Path("~/todo.txt").expanduser().read_text().splitlines(), 1):
    if not linea.strip() or linea.startswith("x "):          # vacía o hecha
        continue
    pri = re.match(r"\(([A-Z])\) ", linea)
    vence = re.search(r"\bdue:(\d{4}-\d{2}-\d{2})", linea)
    texto = re.sub(r"^\([A-Z]\) |\s*\bdue:\S+|\s*[+@]\S+", "", linea).strip()
    tareas.append({"id": str(n), "texto": texto,
                   "prioridad": PRIORIDAD.get(pri.group(1)) if pri else None,
                   "vence": vence.group(1) if vence else None,
                   "etiquetas": re.findall(r"\+(\S+)", linea)})   # +faro → el hilo «faro»
print(json.dumps(tareas, ensure_ascii=False))
```

Con eso, tus tareas aparecen en el dashboard ordenadas por urgencia (prioridad y fecha), cada una al
lado del hilo donde se trabaja, y ▶ la lleva a un agente.

### Nivel 4: la ficha y las acciones del puente

Para poder **hacer cosas** sobre una tarea desde telar (marcarla hecha, cambiarle la fecha,
contestarle algo), el puente ofrece además su **ficha**:

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
detalle = ["/ruta/a/mis-tareas", "--ver", "{id}"]
```

`--ver T84` imprime una página con la tarea y sus botones:

```json
{ "titulo": "T84 · Medir el alcance", "subtitulo": "alta · vence 2026-06-30",
  "bloques": [{"titulo": "notas", "texto": "falta la cota del lado norte"}],
  "acciones": [
    {"nombre": "✓ hecha", "rol": "hecha", "principal": true, "comando": ["mis-tareas", "hecha", "T84"]},
    {"nombre": "cambiar fecha", "rol": "fecha", "comando": ["mis-tareas", "fecha", "T84", "{texto}"]},
    {"nombre": "anotar", "pide": "qué", "comando": ["mis-tareas", "nota", "T84", "{texto}"]},
    {"nombre": "trabajar en un hilo", "tipo": "hilo"} ] }
```

- El **rol** dice qué es cada acción para quien la corre sin abrir la ficha. `hecha` es la que
  corre el ✓ de la lista, y `fecha` la que corre el selector de fecha al hacer clic en un atraso.
- Una acción solo corre si el proveedor la ofreció: telar vuelve a pedir la ficha y toma el
  comando de ahí, nunca de quien hace clic.
- Un agente usa lo mismo: `telar tarea T84 --json` lee la ficha, y
  `telar tarea T84 --accion 0` corre la primera acción.

### Si tus tareas viven en otra máquina

Si el gestor corre en un servidor (para que el laptop y el servidor vean lo mismo, sin esperar a que
se sincronice una copia), se dice dónde:

```toml
[proveedores.tareas]
tipo = "comando"
en   = "servidor"          # la máquina, por el bus: se leen allá y sus acciones corren allá
comando = ["/ruta/allá/mis-tareas"]
```
