# El agente como definición: `agente.toml`

Estado: **hecho en lo principal** (23-oct-2026, telar 0.5). El `agente.toml` dice `nombre`, `para`, `modelo`,
`residente` (siempre, a-pedido o no; `true` y `false` siguen valiendo), `hilos`, `lugar`, `publico`, `icono` y una
`[politica]` (permite, pregunta, niega) que telar le pasa a su sesión como permisos del motor (`--settings`). La
máquina pisa lo suyo: su `en` gana sobre `lugar`, y sus `hilos` y `argumentos` se suman. El hilo anota de qué agente
es (`de_agente.json`). Quedan sin uso `instrucciones`, `memoria` y `capacidades`.

## Por qué

Hoy un agente residente es una carpeta con un `CLAUDE.md`, y todo lo demás está implícito o repartido: su
nombre sale del título del README, para qué sirve no lo dice ninguna parte que telar lea, el modelo es el de
la configuración global, los permisos están en `[agentes.<carpeta>] argumentos` de cada máquina y en prosa.
Otro hilo que quiere encargarle algo tiene que adivinar a quién; el nodo abre a cualquiera que reciba un
mensaje, quiera estar vivo o no.

La idea de primitivas.md: un agente es **una definición, no algo que corre** (el programa; el hilo es el
proceso). La definición vive en el repositorio, junto a sus instrucciones, y vale igual en todas las máquinas.

## Qué es y cómo se declara

Un `agente.toml` en la carpeta del residente, al lado de su `CLAUDE.md`. Todos los campos son opcionales: un
archivo vacío vale lo mismo que no tenerlo.

```toml
# agentes/faro/agente.toml
nombre = "Faro"                       # su identidad: el nombre de su hilo (por defecto, el título del README)
para = "La lámpara y el turno de noche: encárgale lo que tenga que ver con la luz."
modelo = "opus"                       # el modelo por defecto, si el lanzador sabe elegirlo
residente = true                      # false: el nodo no le abre la sesión solo cuando le llega algo

# se leen y se muestran; todavía no cambian nada (abajo, «Lo que queda»)
instrucciones = "CLAUDE.md"
[memoria]
[capacidades]
[politica]
[lugar]
```

| campo | qué hace hoy (primer paso) |
|---|---|
| `nombre` | pisa el título del README: es el nombre del hilo, de la sección y el que acepta `telar encargar` |
| `para` | una o dos frases de cuándo encargarle algo: `telar agentes`, su home, `agente:<carpeta>`; el contexto de arranque de los demás dice que existe |
| `modelo` | al abrir su sesión (un encargo, un periódico, su hilo al tejer) el lanzador lo pasa al motor: `--model` en Claude Code; un motor que no sabe elegir modelo lo ignora |
| `residente` | `true` (por defecto) es lo de hoy; con `false` el nodo no lo publica como residente y un mensaje que le llega espera en su casilla hasta que alguien lo abra. Un encargo (`telar encargar`, un periódico) lo sigue abriendo, con bus o sin él: es pedirlo explícito |
| `instrucciones`, `memoria`, `capacidades`, `politica`, `lugar` | se aceptan y se muestran como «declarado, sin uso todavía» |

## Qué reemplaza y cómo convive con lo de hoy

- **Sin `agente.toml` todo es igual**: el nombre del README, el modelo global, residente siempre. Ningún
  campo nuevo cambia una salida que ya existía; las salidas suman campos.
- **El título del README** sigue valiendo cuando el archivo no dice `nombre`.
- **`[agentes.<carpeta>]` de la configuración** (`hilos`, `home`, `argumentos`, `en`) se sigue leyendo igual.
  Es lo de cada máquina; el `agente.toml` es lo del agente en todas. Donde se pisan gana la máquina: si
  `argumentos` ya trae `--model`, el `modelo` del archivo no se agrega.
- **Un archivo con errores no apaga al agente.** Un TOML que no se lee se ignora entero; un campo con un tipo
  equivocado se ignora solo, y los demás valen. Una clave desconocida es un aviso (puede ser de un telar más
  nuevo). Todo eso queda en `problemas`, que muestran `telar agentes` y la revisión `agentes` de
  `telar doctor`.
- **Dos agentes con el mismo `nombre`**: el segundo (por orden de carpeta) se queda con el de antes, y se avisa.
  Se comparan como los ve el bus (`bus.ficha`: sin mayúsculas, acentos ni símbolos), porque «FARO» y «Faro»
  serían la misma casilla. Un nombre o un modelo con caracteres de control se ignora con aviso.
- **Cambiar el nombre** cambia el nombre de su hilo y de su casilla. Su conversación está anotada con el nombre
  viejo: doctor avisa si el nombre declarado no tiene conversación y el de antes sí (`telar hilo renombrar` la
  lleva), y si ya hay conversaciones con los dos (llegó algo antes de correr doctor: `telar hilo adoptar`). El
  nodo sigue recogiendo la casilla del nombre de antes y la pasa a la nueva (lo que mandó una máquina que todavía
  no tiene el `agente.toml` nuevo), salvo que un hilo vivo siga con ese nombre; doctor avisa de lo que espera ahí.
  Al revés (manda una máquina con el archivo nuevo y la del agente todavía no lo tiene) espera en la casilla
  nueva hasta que esa máquina se ponga al día.
- **Un nombre que ya es de un hilo de proyecto** (vinculado a otra carpeta): doctor avisa, porque un encargo
  caería en la ventana de ese hilo.

## Las decisiones abiertas

Cada una con lo que elegí por ahora y por qué; todas se pueden cambiar sin romper un archivo escrito hoy.

1. **Dónde gana cada uno, archivo o máquina.** Elegí: la configuración de la máquina pisa al archivo donde
   se cruzan (hoy, solo `--model` en `argumentos`). Porque es lo que ya se escribió a mano y nadie espera que
   un archivo del repo lo deshaga. ¿Se mudan `hilos`, `home` y `argumentos` al `agente.toml`? Por ahora no:
   `argumentos` lleva permisos, y los permisos son de `politica`, que está por decidir.
2. **Qué significa `residente = false`.** Elegí lo único que existe hoy: el nodo no le abre la sesión solo.
   Cuando llegue el estado deseado (paso 7), `true` querrá decir «siempre vivo», que es más que lo de hoy
   («se abre cuando le llega algo»). Puede que haga falta un tercer valor (`"a pedido"`); si es así, `true`
   de hoy debería leerse como ese.
3. **Errores blandos o duros.** Elegí blandos (se ignora lo que está mal y se avisa), porque `descubrir` corre
   dentro del nodo y una coma de más callaría al agente en todas las máquinas. La alternativa es negarse a
   cargarlo, como hace la configuración.
4. **El `modelo`, libre o de una lista.** Elegí texto libre que pasa tal cual al motor: los nombres de los
   modelos cambian más rápido que telar. Se aplica también al retomar su conversación.
5. **`para` en el contexto de arranque.** Elegí no ponerlo entero (son líneas que cada sesión carga): la
   línea de los residentes dice que `telar agentes` cuenta para qué es cada uno. ¿Basta, o se quiere el `para`
   de cada uno ahí, recortado?
6. **El nombre de la orden.** Elegí `telar agentes` (plural, como `hilos` y `proyectos`); `telar agente` ya es
   del motor que corre en un hilo. Un módulo que se llamara `agentes` queda tapado, como uno que trajera
   `[objetos.agente]`: doctor avisa de los dos.
7. **La forma de `memoria`, `capacidades`, `politica` y `lugar`.** No la elegí: se aceptan como tablas (o
   texto, `instrucciones`) sin mirar adentro. Propuesta para discutir:
   - `memoria`: `propia = "memoria"`, `lee = ["../../memory"]` (las compartidas).
   - `capacidades`: `skills`, `herramientas`, `mcp`, listas de nombres.
   - `politica`: `permisos` (el modo del motor), `negadas`, `sin_preguntar`, `max_por_encargo`. Es la que
     reemplazaría a `argumentos`, y la que más conviene pensar junto con el paso 8 (permisos).
   - `lugar`: `por_defecto` y `puede` (carpetas); reemplazaría a `[agentes.<carpeta>] en` para la máquina.

## Lo que queda

- **El hilo guarda su agente** (la otra mitad del paso 3): hoy un hilo es de un agente si lleva su nombre o
  está vinculado a su casa. Que el registro del hilo diga `agente = "faro"`, aparte de su conversación y su
  lugar, para que un hilo de proyecto pueda correr otro agente que el por defecto.
- **Usar los campos que hoy solo se muestran**: `politica` en vez de `argumentos`, `capacidades` para armar
  las skills y MCP de su sesión, `memoria` para su home y para las compartidas que lee, `lugar` para dónde se abre.
- **`argumentos` al tejer**: hoy van solo al abrir su sesión por un encargo; el `modelo` va también al abrir su
  hilo con `telar tejer`/`abrir`. Igualar los dos cuando `politica` los reemplace.
- **La página**: mostrar `para` y lo declarado en el home del agente ya está (sale de `agentes.pagina`); una
  vista de todos los agentes en la página, no.
- **`GET /agentes`**: por ahora la API los da por `/objetos/agente:<carpeta>`.
