# Los agentes

Adentro de un hilo casi siempre hay un agente de línea de comandos trabajando. telar
**no lo lanza ni lo pilota**: lo reconoce, se entera de en qué anda, y recuerda qué
conversación vive en qué tab para poder volver a abrirla mañana.

Este documento dice qué tiene que hacer un agente —cualquiera— para integrarse.

## Los seis eventos

Todo el contrato cabe en seis palabras. Un agente avisa; telar anota.

| Evento | Cuándo lo manda | Qué deja escrito |
|---|---|---|
| `abre` | arrancó una conversación | este hilo tiene esta conversación, en este panel |
| `empieza` | se puso a trabajar | atención: `trabajando` |
| `espera` | necesita a la persona | atención: `espera` |
| `sigue` | dio señales de vida (corrió una herramienta) | desmiente un `espera` anterior; nada más |
| `termina` | acabó la respuesta | atención: `termino` |
| `cierra` | la sesión se acabó | atención: `ninguna` |

Los cuatro del medio son exactamente lo que escribe `telar atencion set`: el evento es
la forma automática de lo mismo que se puede decir a mano. `abre` y `cierra` no hablan
de atención sino del **registro de conversación por panel**.

Tres reglas que están en el código y no se negocian:

* **`sigue` no afirma, desmiente.** Una herramienta ejecutada no significa «empecé»;
  significa «si te dije que te esperaba, ya no». Cualquier otra lectura pisa un
  `espera` legítimo que todavía nadie resolvió.
* **Lo que no cambia no se escribe.** Del otro lado hay una barra vigilando el
  archivo: reescribir `trabajando` sobre `trabajando` la despierta para nada.
* **Al `cierra` no se borra la conversación.** Se apaga el semáforo y se deja anotada:
  es exactamente la que se va a querer retomar mañana. Quien quiera olvidarla del todo
  lo pide (`telar agente aviso --olvidar`).

## El camino corto: un comando por evento

Un agente que sepa correr un comando ya puede integrarse, sin escribir una línea de
Python y en cualquier lenguaje:

```sh
telar agente aviso --evento abre --sesion "$ID_DE_LA_CONVERSACION"
telar agente aviso --evento empieza
telar agente aviso --evento espera
telar agente aviso --evento sigue
telar agente aviso --evento termina
telar agente aviso --evento cierra --sesion "$ID_DE_LA_CONVERSACION"
```

Para los cuatro del medio, `telar atencion set trabajando|espera|termino|ninguna` hace
lo mismo y se lee mejor. `abre` es el que de verdad conviene mandar: es lo que después
permite `telar agente retomar`.

### Cómo sabe telar en qué hilo pasó

En este orden, y **nunca por el foco**:

1. `--hilo`, si se dijo;
2. `$TELAR_HILO`, que el multiplexor exportó al abrir el tab y el agente heredó;
3. al **abrir**, el panel donde corre el agente (`$TELAR_PANEL`, o `$ZELLIJ_PANE_ID` /
   `$TMUX_PANE`): una conversación que se retoma en otro tab tiene que mudarse con él,
   y el panel es lo único que lo dice;
4. la conversación ya anotada, que para todo lo demás es exacta y no cuesta nada;
5. el panel otra vez, como último recurso.

El foco no está en la lista a propósito. La persona se va a otro tab mientras el agente
trabaja, y ese es justamente el momento en que se dispara un evento: anotar «el que
tiene el foco» le pone la atención —o peor, la conversación— al hilo equivocado.

Lo barato es que el multiplexor exporte `TELAR_HILO` al crear el tab. Con eso, ningún
evento necesita preguntarle nada a nadie.

### Las reglas del gancho

Quien enganche `telar agente aviso` en su agente hereda tres cuidados que ya están
resueltos de este lado, pero conviene saber por qué:

* **callado**: no imprime nada salvo que se le pida `--json`. Hay agentes que meten la
  salida de sus ganchos en su propio contexto, y un gancho charlatán le habla al agente;
* **siempre sale con 0**: un gancho que falla no puede frenar a quien lo llamó. Una
  carga rota, un disco lleno o un hilo que no se puede resolver terminan todos en el
  mismo lugar: no hacer nada;
* **no levanta el multiplexor si no hace falta**: preguntarle cuesta subprocesos y hay
  eventos que se disparan a cada herramienta.

## El camino completo: un adaptador

Vale la pena cuando el agente ya manda una carga con todo adentro (como los *hooks* de
Claude Code) o cuando además se quiere `retomar`, `nuevo` e instalador.

Un adaptador es un módulo que hereda de `telar.agente.base.AgenteBase` y se registra:

```python
from telar.agente import registrar
from telar.agente.base import AgenteBase, Aviso, Evento

class MiAgente(AgenteBase):
    nombre = "mi-agente"
    comandos = ("mi-agente",)          # lo que delata al proceso en el panel

    def leer_aviso(self, crudo, *, evento=None):
        return Aviso(
            evento=evento or MOMENTOS[crudo["tipo"]],
            agente=self.nombre,
            sesion=str(crudo.get("id", "")),
        )

    def retomar(self, conversacion):   # devuelve el comando, NO lo corre
        return ["mi-agente", "--continuar", conversacion.id]

    def nuevo(self, ruta=None):
        return ["mi-agente"]

registrar("mi-agente", lambda config: MiAgente(config))
```

Eso es todo lo obligatorio. De `AgenteBase` vienen hechos `corriendo`,
`conversaciones`, `anotar` y `atencion`, y de `telar.agente.base` la traducción entera
(`atencion_de`, `resolver_hilo`, `aplicar`), que es la misma para todos.

Opcional, y recomendado en este orden:

| Método | Para qué |
|---|---|
| `archivo_de(conversacion)` | dónde quedó el registro de esa conversación en disco |
| `ganchos()` | qué eventos nativos hay que enganchar (`Gancho`) |
| `ruta_ajustes()` | dónde vive la configuración del agente en esta máquina |
| `instalar()` / `desinstalar()` | escribir y sacar los ganchos por el usuario |

Si el adaptador viene con telar, se agrega a `telar.agente.INCLUIDOS` (nombre → módulo)
y se importa solo al pedirlo. Uno de afuera no necesita estar ahí: le basta con que
algo lo importe para que su `registrar` corra.

### Cuatro cosas que conviene no improvisar

* **Reconocer al agente se hace por el proceso, nunca por el título del panel.** Un
  título miente en cuanto alguien lo renombra. `AgenteBase.corriendo` mira el comando
  palabra por palabra, porque muchos agentes se distribuyen como un script que arranca
  otra cosa (`node …/claude`).
* **`retomar` y `nuevo` devuelven el comando y no lo corren.** Quién lo corre y en qué
  panel es de quien tenga el foco puesto ahí.
* **El vínculo se anota cuando el agente arranca, no cuando se necesita.** Al resucitar
  una sesión el multiplexor relanza el comando y el agente abre una conversación
  *nueva*; si nadie anotó nada al arrancar, veinte hilos en la misma carpeta son
  indistinguibles.
* **Un panel corre una conversación a la vez.** Por eso `abre` manda el panel: es lo
  único que permite darse cuenta de que la anterior murió (un `/clear`, o salir y
  volver a entrar) y sacarla del hilo. Sin eso, un hilo acumula conversaciones muertas
  y `retomar` abre la equivocada.

## El adaptador incluido: Claude Code

Es el único que viene de fábrica. Traduce así:

| Momento de Claude Code | Evento |
|---|---|
| `SessionStart` | `abre` |
| `UserPromptSubmit` | `empieza` |
| `Notification` | `espera` |
| `PostToolUse` | `sigue` |
| `SubagentStop` | `sigue` |
| `Stop` | `termina` |
| `SessionEnd` | `cierra` |

Son siete momentos y **seis** ganchos: `SubagentStop` se entiende si llega, pero no se
engancha —un subagente que termina no cambia en qué está la conversación—, así que en tu
`settings.json` vas a contar seis. Los seis apuntan al **mismo** comando —`telar agente aviso
claude-code`— y cuál fue viene en el JSON que Claude Code le manda por la entrada
estándar (`hook_event_name`). Una sola línea que mantener.

```sh
telar agente instalar              # los escribe en ~/.claude/settings.json
telar agente instalar --seco       # muestra cómo quedaría el archivo, sin tocarlo
telar agente instalar --ajustes ./settings.json
telar agente desinstalar           # saca los de telar, deja los ajenos
telar agente ver                   # qué hay puesto, y qué sabe telar de este hilo
```

Además de los seis, `instalar` pone un **segundo `SessionStart`** que llama a `telar agente
contexto claude-code`. Su salida entra al contexto del agente al empezar (y tras `/clear` y
al retomar): cinco líneas sobre quién es, cómo le escriben y cómo escribirles a los otros
hilos. El aviso no puede hacer eso porque su regla es no imprimir nada. Sin `$TELAR_HILO` no
dice nada, y se apaga con `[agente] contexto = false`. Y deja la skill **`/hilos`** en
`~/.claude/skills/hilos/`, lo largo de lo mismo, que el agente abre cuando le hace falta;
una `/hilos` que no sea de telar no se toca. `desinstalar` quita las dos cosas.

El instalador **se mete en casa ajena y se porta como tal**: mezcla con los ganchos que
ya estaban y solo reemplaza los suyos (se reconocen por su comando), deja un respaldo
`settings.json.telar.bak` antes de tocar nada, escribe a un temporal que después
renombra, y ante un JSON que no entiende se niega a escribir en vez de pisarlo. Los
ganchos recién puestos los lee Claude Code al arrancar de nuevo.

Ese respaldo **no se pisa nunca**: si el nombre ya está ocupado —un segundo `instalar`, o
el `desinstalar` que viene después—, el nuevo sale fechado
(`settings.json.telar.20260919-142530.bak`). Así el retrato del archivo *antes* de telar
sobrevive justo a la orden que deshace telar. Y la copia hereda los permisos del
original: una configuración que era privada sigue siéndolo.

Dos detalles de Claude Code que se pagan si no se saben: la carpeta de configuración es
`~/.claude` salvo que `$CLAUDE_CONFIG_DIR` diga otra, y las conversaciones se guardan en
`projects/<carpeta con la ruta aplanada>/<id>.jsonl`. Cómo se aplana esa ruta es cosa
suya y cambia sin avisar, así que telar no la reconstruye: busca el archivo por su
nombre, que es el id.

## Qué NO hace telar con el agente

* no lo lanza ni lo mata: abrir un panel y correr algo ahí es del multiplexor;
* no lee sus conversaciones —sabe dónde están, y nada más—;
* no le manda nada por la red, ni le cuenta a nadie qué se hizo;
* no le escribe en la entrada sin que se lo pidan: `escribir` deja el texto puesto y la
  última palabra es siempre de la persona.
