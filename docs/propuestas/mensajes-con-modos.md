# Mensajes con modos y el Encargo

Estado: **primer paso hecho** (22-oct-2026): `telar mensaje --modo aviso|pedido|encargo|consulta`, el aviso que
espera en la casilla sin despertar, y el Encargo como objeto (`encargo:e-1a2b3c4d`), guardado en la máquina de
quien lo hace, con sus acciones `aceptar`, `rechazar` y `cerrar`. **Por decidir**: las preguntas de abajo, la
tabla de intenciones y cómo se funde `telar encargar`. Es el paso 4 de [primitivas.md](primitivas.md).

## Por qué

Hoy un mensaje entre hilos hace siempre lo mismo: llega a la casilla y despierta al que lo recibe. No hay
manera de decir «para que lo sepas» sin interrumpir a un agente que está en otra cosa, ni de pedir algo y
saber después si se hizo. Quien encarga queda mirando la conversación del otro (`telar hilo leer`) para
adivinar si terminó, y lo que terminó no deja nada que se pueda abrir: el resultado queda en la prosa de un
turno.

primitivas.md lo resuelve con una sola pieza, el **mensaje**, en cuatro modos, y un tipo de fábrica, el
**Encargo**: un pedido durable con estado, quién lo pidió, quién lo hace, plazo y resultado, como la Workflow
Execution de Temporal.

## Qué es y cómo se declara

El modo dice qué espera quien manda. Es un campo más del mensaje (`modo`), y sin él vale `pedido`, lo de
siempre.

| modo | qué hace | cómo llega |
|---|---|---|
| `aviso` | queda en la casilla, **no despierta** | entra a la conversación la próxima vez que el hilo tenga turno: cuando su persona le escriba, o junto con un mensaje que sí despierta. A un residente sin sesión no se le abre |
| `pedido` | despierta, no espera respuesta | como hoy: el «↯ mensaje nuevo», el gancho `Stop` o el mod |
| `encargo` | despierta y crea un **Encargo** que el destinatario acepta o rechaza y cierra con un resultado | como un pedido, con la dirección del encargo y cómo contestarlo |
| `consulta` | **no entra a la conversación**: lee el estado del hilo | no viaja: es la ficha del hilo (`hilo:<nombre>`) y sus últimos turnos (`telar hilo leer`) |

```
telar mensaje Faro "la luz del muelle ya está" --modo aviso
telar mensaje Faro "¿quedó la nota en T84?"                  (pedido, como siempre)
telar mensaje Faro "revisa tarea:T84 y dime qué falta" --modo encargo --plazo 2026-10-24
telar mensaje Faro --modo consulta
telar objeto encargo:e-1a2b3c4d                              en qué va: estado, resultado, historia
telar objeto encargo:e-1a2b3c4d aceptar
telar objeto encargo:e-1a2b3c4d cerrar --params '{"resultado": "faltan dos casillas"}'
```

**El Encargo.** Un objeto con dirección `encargo:<id>` (`e-` y ocho cifras hex, que elige quien lo manda para
poder nombrarlo antes de que llegue). Su estado va `pedido → aceptado → corriendo → hecho | falló | cancelado`.
Guarda `texto`, `de` (quién lo pidió), `para` (el hilo que lo hace), `responder_a` (el hilo al que se le
avisa al cerrarlo, si lo pidió un hilo), `plazo`, `resultado` y una `historia` (cada cambio con su hora y
quién lo hizo).

- **Dónde vive.** En la máquina del destinatario, en `<estado>/encargos/objetos/<id>.json`. Lo crea la
  casilla al recibir el mensaje (`telar.casilla.dejar`): llegue por donde llegue, existe una vez, y el mismo
  mensaje repetido no lo crea dos veces. Quien lo manda guarda en su máquina una nota corta
  (`<estado>/encargos/enviados/<id>.json`: para quién y en qué máquina) para encontrarlo después.
- **Cómo se abre desde otra máquina.** `telar objeto encargo:e-…` lo busca aquí; si no está, en la máquina
  de su nota (o la que diga `@máquina`), con un pedido nuevo del nodo, `encargo`. Mientras el nodo de allá
  todavía no lo recoge, se ve la nota de aquí, en estado `pedido` y `en_camino`.
- **Las acciones.** `aceptar` (de `pedido` a `aceptado`); `rechazar` (`{"motivo": …}`, a `cancelado`, con el
  motivo como resultado); `cerrar` (`{"resultado": …, "estado": "hecho" | "falló"}`). Cada una lleva la
  versión que se leyó (`--version`), y con una vieja no se hace (409). Rechazar o cerrar le avisa a
  `responder_a` con un mensaje (modo `pedido`) que nombra el encargo y su resultado.

## Qué reemplaza y cómo convive con lo de hoy

- **`--tipo` sigue igual.** Es otra cosa: dice de quién es (`persona`) y si es un encargo explícito a un
  agente (`encargo`, el de `telar encargar` y los periódicos, que abre aunque el agente no sea residente). El
  modo dice qué espera quien manda. Un mensaje `--modo encargo` también abre a un agente no residente: es
  pedirlo explícito.
- **Un mensaje sin `modo` es un `pedido`.** Lo que mandan los telar de antes, el panel, `telar encargar`, los
  periódicos y los atajos llega igual que hoy. El campo `modo` va en el mensaje solo cuando no es `pedido`:
  el registro y la casilla de un pedido quedan byte a byte como antes.
- **Un nodo de antes** no sabe de modos: un aviso le llega como pedido (despierta) y un encargo, como un
  mensaje sin objeto (el texto dice la dirección, pero allá no existe y el pedido `encargo` no tiene quién
  lo atienda: `telar objeto` dice que esa máquina no atiende «encargo»). Nada se pierde; se pierde el modo.
- **El aviso espera aparte**, en `<casilla>/avisos/<id>.json`: el nodo no teclea el «↯», el mod no lo ve como
  mensaje nuevo (no sondea por él) y el gancho `Stop` no impide que el turno termine por un aviso solo. Lo
  entregado va a `entregados/`, como todo.
- **`telar encargar` no cambia.** Sigue escribiéndole al agente en su hilo de siempre (o en su cola, o
  abriendo su sesión), sin bus o por el bus con `--tipo encargo`. No crea un Encargo.
- **`ficha` y `hilo leer` no cambian.** La consulta los junta; no los reemplaza.

**Cómo se funde `telar encargar` después.** Cuando el Encargo pese poco, `telar encargar faro "…"` pasa a ser
`telar mensaje agente:faro "…" --modo encargo`: el objeto reemplaza a la cola de `<estado>/encargos/<agente>.jsonl`
(un encargo que espera es uno en `pedido`; `repartir` entrega el siguiente en `pedido` cuando el agente
termina su turno), y lo que hoy anota `encargos.log` queda en la historia de cada uno. `telar encargar` queda
como alias, y `--tipo encargo` como «ábrelo aunque no sea residente». Un periódico con `agente = "…"` manda un
encargo, y su resultado (lo que hoy deja `telar resultado`) se cierra en él.

## Las decisiones abiertas

Cada una con lo que elegí por ahora y por qué; todas se pueden cambiar sin romper un mensaje ni un encargo
guardado hoy.

1. **Modo y tipo, dos campos.** Elegí no tocar `tipo` y agregar `modo`: `tipo` ya viaja en el bus y lo leen
   nodos de antes, y mezclar «de quién» con «qué espera» obligaría a valores como `persona-aviso`. ¿Se
   funden algún día (`tipo` solo para `persona`)?
2. **Cuándo entra un aviso.** Elegí: con el próximo turno del hilo (su persona le escribe, o llega algo que
   despierta), nunca solo. La alternativa es entregarlo en el próximo `Stop` aunque sea el único, que no
   despierta a un hilo ocioso pero sí alarga el turno de uno que trabaja. Un aviso puede esperar días en un
   hilo que nadie abre; ¿se le pone fecha de caducidad?
3. **Rechazar es `cancelado`.** Elegí quedarme con los estados de primitivas.md: rechazar lo deja
   `cancelado`, con `rechazado: true` y el motivo como resultado. La alternativa es un estado `rechazado`
   aparte, que se lee más claro pero agrega uno a la lista.
4. **`corriendo` no lo pone nadie todavía.** Elegí no inventarlo: llegará cuando el turno de un hilo sea un
   cambio (paso 7, el turno como unidad), y el encargo pase a `corriendo` cuando empiece el turno que lo
   atiende. Por ahora `aceptar` lo deja `aceptado`.
5. **Cerrar sin aceptar.** Elegí permitirlo (un agente que lo hace de una vez no tiene por qué aceptarlo
   antes); la historia lo dice. La alternativa es exigir `aceptar`, que solo agrega un paso.
6. **El resultado vuelve como pedido.** Elegí que rechazar o cerrar despierte a quien lo pidió (si lo pidió
   un hilo): delegó y probablemente espera. Pasa por los frenos de siempre (saltos y tope por hora), así que
   una cadena de encargos se corta igual que una de mensajes. La alternativa es un aviso, que no despierta.
   Aceptar no avisa: se ve con una consulta.
7. **Quién puede hacer cada acción.** Por ahora cualquiera en la máquina del destinatario (o por el bus, con
   el pedido `encargo`): todavía no hay permisos (paso 8). La propuesta: aceptar, rechazar y cerrar, el que lo
   hace; cancelar, quien lo pidió (una acción que no hay todavía).
8. **El plazo.** Elegí una fecha (`2026-10-24`) o fecha y hora en ISO, validada al mandar; el objeto dice
   `vencido` cuando pasó y no está cerrado, y nada más: no se avisa ni se cancela solo. ¿Se le avisa a alguien
   al vencer (un disparador, paso 7)?
9. **La consulta no lleva texto.** Elegí rechazar un texto con `--modo consulta` (no se manda nada, y un
   texto haría creer que sí). Más adelante podría ser una pregunta que contesta un agente barato sin entrar a
   la conversación del hilo.
10. **El id lo elige quien manda.** Elegí `e-` y ocho cifras hex al azar, para que quien manda lo pueda nombrar
    al tiro, antes de que llegue. Un choque es improbable; si pasa, el que llega segundo no pisa al primero
    (no se crea).

## Lo que queda

- **La tabla de intenciones**: el destino como intención («trabajar en `tarea:T84`») que se resuelve al hilo
  vivo del proyecto, si no a uno nuevo con su agente, si no al agente de lo que no tiene proyecto. Con eso se
  le puede encargar a un hilo de proyecto que no está abierto.
- **El estado por destinatario** de cada mensaje (en cola, entregado, falló), que hoy solo sabe la casilla
  de la máquina del hilo.
- **Fundir `telar encargar`** (arriba), y que los periódicos manden encargos.
- **`corriendo`** con el turno como cambio, **cancelar** desde quien lo pidió, y los permisos de cada acción.
- **Listar los encargos** (`telar encargos`, o una colección en `GET /objetos/encargo`), y una vista en la
  página: los que hice, los que me pidieron, los vencidos.
- **La página**: mandar con modo desde el panel y abrir un `encargo:` como cualquier objeto.
