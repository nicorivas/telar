# Un bus para telar: mensajes y estado entre varias máquinas

*Estado: construido (octubre de 2026): bus, demonio, casillas, entrega por ganchos, `telar mensaje`, y por el bus `encargar`, `enlace enviar`, la web, el correo de una misma persona, el espejo y las ventanas de los remotos. Lo que falta, al final de «Cómo llegar».*

## Por qué

telar empezó en una máquina y creció hacia dos (un laptop que se duerme, un servidor que no) a punta
de mecanismos sueltos, cada uno con sus reglas:

| camino | entre | cómo entrega |
|---|---|---|
| mensaje nativo del agente | misma máquina y persona | lo del agente (`SendMessage`) |
| correo entre agentes | hacia el servidor | Postfix, y un **agente lanzado solo para reenviar** el texto |
| la puerta (`telar enlace`) | servidor → laptop | ssh atado a un comando, que **teclea el texto en el panel** |
| encargos (`telar encargar`) | a un agente residente | teclea, o cola y gancho `Stop` |
| la carpeta de entrada | cualquiera | un archivo, y alguien que avise |
| sondeos | laptop ↔ servidor | atención cada 20 s, espejo cada 30 s, traer cada 3 min |

Las fallas que eso trae no son de un mecanismo sino de la forma:

1. **Entregar es teclear en una terminal.** Un texto largo pegado en el prompt de un agente pierde el
   comienzo; no hay confirmación de que llegó; se mezcla con lo que la persona escribe.
2. **Un modelo como enrutador.** El correo levanta un agente por mensaje (10–30 s, tokens, memoria) y a
   veces no entrega.
3. **No hay casilla durable por hilo.** Un mensaje a un hilo dormido u ocupado se pierde o depende del
   camino.
4. **El estado está repartido y se reconcilia por sondeo**: ventanas fantasma, hilos duplicados.

## La idea

Separar tres cosas que hoy van mezcladas:

- **transporte**: que un mensaje o un evento cruce de una máquina a otra, aunque el destino duerma;
- **estado**: qué hilos hay, dónde vive cada uno ahora, en qué anda;
- **entrega**: que el mensaje entre a la conversación del agente.

### Direcciones que no dependen de la máquina

Cada hilo tiene una identidad estable (`persona/hilo`, con un id detrás). En qué máquina vive es estado,
no parte de la dirección: mudar un hilo cambia un dato y los mensajes siguen llegando.

### Un bus con memoria en la máquina que no se apaga

NATS con JetStream, sobre la red privada (Tailscale o la que haya):

- **colas durables por hilo** (`casilla.<persona>.<hilo>`): lo que llega a un destino desconectado espera,
  y llega en orden, con confirmación;
- **estado clave-valor con avisos** (`hilos.<persona>.<hilo>` → máquina, atención, conversación): quien
  quiera se suscribe y se entera al instante, sin sondeo;
- **pedidos con respuesta** (`rpc.<persona>.<maquina>.<verbo>`): abrir, retomar, leer; lo que hoy son
  verbos de la puerta y ssh reenviados, con permisos por persona;
- **objetos** para lo grande: el mensaje lleva solo la referencia (*claim check*).

### Un demonio por máquina

`telar nodo` (launchd o systemd) mantiene una conexión **saliente** al bus: así una máquina que no
acepta conexiones (un laptop detrás de cualquier red) recibe lo suyo igual. Publica el estado de sus
hilos (los ganchos del agente se lo dan por un socket local), se suscribe a las casillas de los hilos que
aloja y atiende los pedidos que le tocan.

### Entrega por los ganchos del agente, nunca tecleando contenido

El demonio deja el mensaje en la casilla local del hilo.

- Si el agente está trabajando, el gancho `Stop` le entrega el mensaje al terminar el turno
  (`decision: block` con el mensaje como motivo): sigue trabajando con él, entero.
- Si está inactivo, se teclea **una línea fija y corta** («↯ mensaje nuevo») y el gancho
  `UserPromptSubmit` agrega el contenido como contexto.

La casilla confirma la entrega al inyectarlo. Cada mensaje lleva id: entregar dos veces no duplica.

### Git sigue siendo para el contenido

Repositorios, tareas, memoria: git. El bus lleva mensajes y eventos, no reemplaza el control de versiones.

### Seguridad

La red privada como perímetro, credenciales del bus por persona y permisos por tema (una persona no
lee las casillas de otra), y lo que llega de otro sigue siendo un mensaje, no una orden.

## Qué se va y qué queda

- **Se va**: Postfix y el agente reenviador, los verbos de la puerta y los ssh reenviados, los sondeos
  (atención, espejo, traer), la carpeta de entrada como buzón, teclear contenido en paneles.
- **Queda**: tmux como lugar de los procesos, los ganchos del agente, git, y la CLI, la extensión y la web
  como clientes.

El bus es **opcional**: telar en una sola máquina sigue funcionando con archivos, como hoy.

## Prueba de concepto (octubre de 2026)

**Entrega por ganchos**, con Claude Code real:

| prueba | resultado |
|---|---|
| `Stop` con `decision: block` entrega un mensaje de ~3.000 caracteres después de que el agente terminó | lo recibió entero (citó la primera y la última palabra) y siguió trabajando con él |
| `UserPromptSubmit` con `additionalContext`, disparado por «↯ mensaje nuevo» | el agente respondió con el contenido, tildes incluidas |
| agente **interactivo e inactivo** en tmux: se teclea solo «↯», el contenido (1.401 caracteres) va por el gancho | respondió al contenido y contó bien sus 181 palabras |

**NATS 2.15** en el servidor, cliente `nats-py` en el laptop, 220 ms de ida y vuelta entre ambos (distancia):

| prueba | resultado |
|---|---|
| tres mensajes publicados con el destino desconectado | al conectarse los recibió los tres, en orden, con tildes |
| reenvío de un mensaje con el mismo id | el servidor lo marcó duplicado y no lo guardó dos veces |
| un mensaje sin confirmar | se reentregó al vencer el plazo (al menos una vez) |
| cambio de estado de un hilo | el aviso llegó al suscriptor en 232 ms (un viaje de red) |
| pedido con respuesta | 440 ms con quien responde en el mismo laptop (dos viajes); un ssh solo para conectar cuesta lo mismo, y uno con un comando de telar, 550 ms |
| el servidor | 14 MB de memoria, arranca en menos de 1 ms |

La ganancia no es velocidad bruta (la manda la distancia) sino conexión permanente, avisos sin sondeo y
mensajes que esperan en vez de perderse.

## Cómo quedó (octubre de 2026)

- `[bus]` en la configuración; `telar[bus]` trae el cliente (nats-py). Sin `[bus] url`, nada cambia.
- `telar nodo` (servicios en `servidor/telar-nodo.service` y `telar-nodo.plist`) y el bus como servicio
  (`servidor/telar-bus.service`).
- `telar mensaje <hilo|agente> "…"`; `telar encargar` publica en la casilla del agente si hay bus.
- Los ganchos `Stop` y `UserPromptSubmit` (`telar agente casilla`) entregan la casilla; se instalan con
  `telar agente instalar`. Un agente abierto antes de instalarlos los lee recién al reiniciarse.
- También por el bus: `telar enlace enviar` (a la casilla del hilo), lo que se escribe desde la web a un
  hilo de otra máquina (mensaje `persona`: lo escribe la persona, no otro hilo), la lectura desde la web
  de una conversación de otra máquina (pedido `leer` a su nodo, con `[enlace] no_leer`), el correo entre
  hilos de una misma persona y el espejo (cada nodo publica su foto cada 30 s en `TELAR_ESPEJO` y guarda
  las de los demás). El nodo publica `vivo: false` cuando un hilo deja de vivir en su máquina, con su
  sesión tmux si tiene una propia: la otra máquina trae la ventana de lo que nace allá y cierra la de lo
  que muere, al instante. `remotos traer` queda para llamarlo a mano; el sondeo de la extensión (`--sondeo`) no hace nada si hay bus.
- Probado de punta a punta entre un laptop y un servidor: un mensaje a un agente cerrado lo abre
  retomando su conversación y le entrega el contenido; a uno abierto e inactivo se le teclea solo «↯»;
  la atención de un hilo de la otra máquina llega en uno o dos segundos.

## Cómo llegar

1. Bus, demonio y casillas en el servidor; los agentes residentes como primeros usuarios.
2. El laptop como nodo; `encargar`, `enlace enviar` y el correo entre agentes pasan al bus. *Hecho.*
3. El estado por suscripción; se apagan los sondeos y se retira el reenviador. *Hecho: la atención, el
   espejo y las ventanas de los remotos; el correo de una misma persona ya no pasa por el reenviador.
   Falta: el correo entre personas.*
4. Varias personas: credenciales y permisos por persona; varias máquinas siempre prendidas, en clúster.

## Riesgos

- **La entrega por ganchos depende de cómo el agente trate esos ganchos.** Funciona hoy (probado), pero
  es un uso nuestro y no un patrón establecido: hay que cubrirlo con pruebas que corran contra el agente.
- **Un punto único de falla** mientras haya un solo servidor (como hoy). Clúster de tres si crece.
- **Una dependencia más** (`nats-server`) y un demonio por máquina. La alternativa sin dependencia es la
  misma forma hecha a mano: el servidor como centro, una API HTTP, SQLite como casilla y avisos en vivo
  (SSE); menos piezas, pero reconexión, orden y confirmaciones quedan por construir y mantener.
