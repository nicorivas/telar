# Permisos

Estado: **primer paso hecho** (22-oct-2026), sin cambiar nada de lo que se permite hoy: un módulo declara en su
`modulo.toml` lo que pide (`[permisos]`: rutas que lee y escribe, red, órdenes de telar) y `telar modulos
instalar` lo muestra antes de preguntar, sin hacerlo cumplir; y lo que un hilo espera de la persona es un objeto
de solo lectura, `permiso:<hilo>` (qué hilo, desde cuándo y qué pide, si su agente lo dijo). **Por decidir**: las
preguntas de abajo, sobre todo quién contesta una solicitud y si telar hace cumplir lo que un módulo pide. Es el
paso 8 de [primitivas.md](primitivas.md).

## Por qué

Hoy los permisos están repartidos en lugares que no se conocen entre sí:

| qué | dónde vive hoy | quién lo decide |
|---|---|---|
| lo que puede hacer el agente de un hilo | el `settings.json` del motor (Claude Code), más los flags de `[agentes.<carpeta>] argumentos` y lo que dice la prosa de cada `CLAUDE.md` | la persona, a mano, en cada máquina |
| lo que un agente corre sin preguntar para hablar con otros hilos | `PERMISOS` de `telar.agente.claude_code`, que `telar agente instalar` agrega a `permissions.allow` | telar, fijo |
| lo que alcanza una persona en el bus | su cuenta de NATS (`telar bus persona`): un espacio aparte que el servidor hace cumplir | quien administra el bus |
| quién administra el bus | su rol (dueño, admin, miembro: telar.personas): la gestión solo la alcanzan las cuentas admin, porque el servidor solo a ellas les exporta el servicio | el dueño o un admin (⚙ personas, `telar bus rol`) |
| lo que ve y pide alguien del equipo | `telar serve --equipo`: su llave y lo que la página del equipo deja | la persona, al dar la llave |
| lo que hace un módulo | nada: corre con los permisos de quien lo instaló | nadie |

Y la **espera** de un hilo (el diálogo de permiso que el agente le abre a la persona) es solo un color en el
semáforo: se ve en la lista, pero no se sabe qué pide sin ir a la terminal, ni se contesta desde otro lado.

primitivas.md junta esto en una regla que atraviesa todas las piezas: un **permiso** dice qué puede hacer un
**sujeto** (una persona o un agente) o un **módulo**: con qué tipos, qué acciones, en qué nodos, y qué pide
confirmación. Una **solicitud de permiso** es un objeto con su decisión, que se contesta desde cualquier
superficie (la terminal, la página, el celular).

## Qué es

- **Sujeto.** Quien pide o ejecuta una acción: una persona (`[persona]`, su cuenta en el bus) o un agente (su
  `agente.toml`, [agente-como-definicion.md](agente-como-definicion.md)). Ante los permisos son la misma clase de
  cosa: toda acción registra quién la pidió y quién la ejecuta (hoy lo hace a medias: `de` en un mensaje, `quien`
  en la historia de un encargo).
- **Permiso.** Lo que un sujeto o un módulo puede hacer, en el vocabulario de los objetos: tipos y acciones
  (`tarea:* completar`, `hilo:* mensaje`), rutas, red, nodos. Lo que no está permitido ni negado, se pregunta.
- **Solicitud.** Lo que pasa cuando algo pide lo que no tiene: un objeto `permiso:` con quién lo pide, qué, desde
  cuándo, y su decisión (`pendiente → concedido | negado | vencido`), que cualquier superficie con derecho a
  contestar puede tomar. La espera de un hilo es la primera: la que abre el motor del agente.
- **Manifiesto.** Lo que un módulo dice que pide, en su `modulo.toml`. Quien lo instala lo ve antes; más
  adelante, telar lo hace cumplir y pregunta por lo que pida de más.

## Cómo se declara

**Un módulo**, en su `modulo.toml` (hecho):

```toml
[permisos]
leer = ["~/datos/oceano"]            # rutas que lee fuera de su carpeta
escribir = ["~/.local/state/nino34"] # rutas que escribe
red = ["psl.noaa.gov"]               # los sitios a los que se conecta; true: cualquiera; false o nada: ninguno
ordenes = ["mensaje", "tipo tarea"]  # las órdenes de telar que corre («telar mensaje» vale igual)
```

Su carpeta no se declara: es suya. Sin la tabla, el módulo «no dice qué pide», que no es lo mismo que no pedir
nada (la tabla vacía).

**Lo que se le concede** (hecho, 28-oct-2026, para las órdenes que pide la página de un módulo): la primera vez que
su lienzo pide una orden declarada (`window.lienzo.pedir`), la página le pregunta a la persona (siempre, solo esta
vez, no), y lo decidido queda en `telar.concesiones` (`<estado>/concesiones.json`), que telar hace cumplir en `POST
/lienzo/pedir`. `telar modulos permisos [módulo] [--quitar orden]` lo lista y lo revoca. Es la primera concesión que
telar hace cumplir; las demás puertas (las órdenes que corre un módulo desde su propio proceso, las rutas, la red)
pueden usar el mismo registro.

**Un sujeto** (por construir). Un agente, en la `politica` de su `agente.toml`; una persona, en la configuración
de quien la deja entrar. La forma que se propone es la misma para los dos:

```toml
# agente.toml de un residente
[politica]
permite = ["tarea:* completar", "hilo:* mensaje", "archivo:notas/**"]
pregunta = ["tarea:* borrar"]
niega = ["archivo:~/.ssh/**"]
```

**Una solicitud** no se declara: la crea quien pide (hoy, el motor del agente al abrir su diálogo).

## Qué reemplaza

| hoy | después |
|---|---|
| el color «espera» del semáforo | la solicitud `permiso:<hilo>`, que dice qué pide y (después) se contesta desde la página o el celular |
| `PERMISOS` fijo en el adaptador de Claude Code | lo que permite la `politica` del agente (el adaptador la traduce a `permissions.allow`) |
| los flags de permiso en `[agentes.<carpeta>] argumentos`, y la prosa | la `politica` del `agente.toml` |
| un módulo que corre con todo | un módulo que pide lo suyo, y telar que lo hace cumplir donde puede |

Las cuentas del bus no se reemplazan: son el piso (lo que una persona no alcanza de otra) y lo hace cumplir el
servidor. Los permisos van encima, dentro de lo que una persona ya alcanza.

## Cómo convive con lo de hoy

- `[permisos]` es una sección nueva y opcional del manifiesto. Un módulo sin ella se instala y corre como
  siempre. Una clave que esta versión no entiende se muestra como no entendida, no rompe la instalación. Un
  telar anterior no conoce la sección y no lee el módulo que la trae (como con cualquier sección nueva).
- La espera sigue siendo la atención `espera`, escrita por los mismos ganchos y el mod. Lo nuevo es que el gancho
  `Notification` guarda además el texto de lo que pide en `<estado>/esperas.json`, y que `permiso:<hilo>` lo
  junta. Nada lee `esperas.json` más que ese tipo: si falta o está roto, la solicitud sale sin el texto, y renombrar u
  olvidar un hilo no se cortan por él (cuenta como vacío y la siguiente anotación lo rehace). Sin `desde` en la
  atención (un `atencion.json` viejo) tampoco sale el texto: no hay cómo saber si es de esta espera.
- Nadie contesta nada todavía: la solicitud no tiene acciones, y el diálogo de la terminal es el de siempre.

## El primer paso (hecho)

1. **Lo que pide un módulo.** `telar.modulos` lee y valida `[permisos]` (`Modulo.permisos`, y `Modulo.pide` en
   palabras). `telar modulos instalar` dice «pide: …» antes de preguntar, y que telar todavía no lo hace cumplir;
   `telar modulos` lo lista (y `--json`, en `permisos`); `actualizar` dice si cambió desde lo que se vio al instalarlo (anotado en `modulos.toml`), después de
   correr el `[instalar]` de la versión nueva, como siempre: decir antes y preguntar es lo que queda (abajo).
   No lo hace cumplir.
2. **La espera como objeto.** El tipo `permiso` de fábrica en `telar.objetos`: `permiso:<hilo>` existe mientras su
   atención es `espera`, con `hilo`, `desde`, `pide` y `clase` (`permiso` o `pregunta`), y enlaza a su hilo y a su
   proyecto; el hilo que espera enlaza a él. Lo que pide sale del `message` de la notificación de Claude Code, o de
   `telar agente aviso --evento espera --pide "…"` para cualquier otro agente. Es de solo lectura.

El contrato está en [contratos.md](../contratos.md) (`telar objeto`, `telar agente aviso`) y la declaración en
[configuracion.md](../configuracion.md) («Lo que pide un módulo»).

## Las decisiones abiertas

Cada una con la opción que se tomó por ahora y por qué.

1. **¿Quién puede contestar una solicitud?** Por ahora: nadie fuera de la terminal (solo lectura). Cuando se
   pueda, la propuesta es que solo la persona dueña del hilo, desde cualquier superficie suya; un agente nunca
   contesta la solicitud de otro. Es lo más conservador: hoy solo la persona frente a la terminal decide.
2. **¿Telar hace cumplir lo que un módulo pide?** Por ahora no, y lo dice al instalar. Hacerlo de verdad pide
   un arenero por sistema (`sandbox-exec` en macOS, bubblewrap o landlock en Linux), que es mucho y frágil. Lo
   barato y útil primero: que las órdenes de telar que corre un módulo (`TELAR_MODULO` en su entorno) se
   rechacen si no las declaró, y que `actualizar` pregunte cuando pide más. Falta decidir si basta con eso.
3. **¿Un módulo sin `[permisos]` se puede instalar?** Por ahora sí, como siempre, y se muestra «no dice qué
   pide». Exigirlo rompería todos los módulos de hoy. Cuando telar lo haga cumplir, uno sin la tabla podría
   instalarse solo con `--si` o con un aviso más fuerte.
4. **¿Qué tan fina es la red?** Por ahora `true`, `false` o una lista de sitios, solo para mostrar. Si se hace
   cumplir, la lista de sitios es lo que vale la pena; el puerto o el método, no todavía.
5. **¿Una clave desconocida en `[permisos]` es un error?** Por ahora no: se muestra como no entendida y el
   módulo se instala. Un error haría que un módulo escrito para un telar más nuevo no se instale en uno más
   viejo; callarla escondería lo que pide. Mostrarla es el medio.
6. **¿Qué id tiene una solicitud?** Por ahora el del hilo (`permiso:Faro`): un hilo espera una cosa a la vez, y
   la versión es desde cuándo espera. Cuando se contesten, cada solicitud tendrá su id (`permiso:p-1a2b3c4d`)
   y su historia, y `permiso:<hilo>` seguirá siendo «la que espera ahora».
7. **¿Cómo se contesta desde fuera?** La propuesta es la de [lo-que-hacen-los-otros.md](lo-que-hacen-los-otros.md)
   (punto 3): el gancho `PermissionRequest` de Claude Code (o `tool.check` en el mod) publica la solicitud en el
   bus y espera hasta ~120 s una decisión; si no llega, queda el diálogo de siempre en la terminal. Falta
   decidir ese plazo y si lo que no se contesta a tiempo se niega o se deja al diálogo (por ahora: al diálogo,
   que es lo de hoy).
8. **¿Dónde vive la política de cada sujeto?** La propuesta: la de un agente, en su `agente.toml`; la de una
   persona, en la configuración de quien la deja entrar (junto a `[equipo]`). Falta decidir si se unen en un solo
   archivo.
9. **¿Lo que pide un hilo sale de su máquina?** Por ahora no: `esperas.json` es local y el bus solo lleva la
   atención (`espera` y desde cuándo). El texto de un diálogo de permiso puede nombrar rutas o comandos; antes de
   publicarlo conviene decidir quién lo ve (la persona dueña, en sus máquinas, parece suficiente).

## Lo que queda

- Contestar una solicitud: el gancho `PermissionRequest` (que trae la herramienta y su entrada, y puede devolver
  la decisión), acciones `conceder` y `negar` en `permiso:`, y la página y el celular mostrándolas.
- Una solicitud con su propio id, su historia y quién la contestó.
- La `politica` de los agentes (`agente.toml`) y su traducción a `permissions.allow`, en lugar de `PERMISOS` fijo
  y de los flags de `argumentos`.
- Hacer cumplir lo que un módulo pide, empezando por las órdenes de telar que corre; que `actualizar` pregunte
  cuando pide más; `telar doctor` avisando de un módulo instalado sin `[permisos]`.
- `permisos` en `telar config --json` y en ⚙ configuración de la página.
- Registrar en cada acción quién la pidió y quién la ejecuta (el sujeto), de punta a punta.
- La página: ver `permiso:<hilo>` al lado del hilo que espera.
