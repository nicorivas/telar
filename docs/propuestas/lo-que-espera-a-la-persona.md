# Lo que espera a la persona

Estado: **pasos 1 y 2 hechos** (17-nov-2026). El 1, la bandeja de solo lectura: el contrato (`esperando` en cada tipo
de objeto, `[objetos.X] esperando` en un módulo), `telar esperas`, `GET /esperas` y la pestaña «te esperan» del
dashboard, con el número de lo que pregunta en su fila de la barra. El 2, contestar desde ahí: una sola ventana
(`web/contestar.ts`) para el `avance` de una tarea, un retenido, la pregunta en vivo de un hilo y la pregunta de un
módulo (clase `decide`, con su grupo «decisiones que te piden»); dos clics, conversarlo con quien preguntó, y el 409
que relee. La pregunta del repositorio (el 3) salió como módulo, `telar-preguntas`. Lo construido se describe en
[../arquitectura.md](../arquitectura.md), «Lo que espera a la persona, junto», y en [../contratos.md](../contratos.md),
«telar esperas --json». Los pasos 4 (firmas) y 5 (teléfono) siguen por decidir. Los **mundos** (abajo) tienen hecho el contrato y la CLI; la página, en diseño. La poda de lo repetido («La poda que va
con eso»), hecha el 17-nov.

Responde a una pregunta de diseño: cómo le pide un agente a
la persona una decisión que no puede tomar solo (una «consulta»), con el archivo del repositorio como fuente de
verdad. Antes de eso, revisa si telar ya tiene demasiados sistemas de aviso. Lo de aquí está comprobado contra el
código del 17-nov.

## En una línea por pregunta

1. **¿Puede hacerlo un módulo sin tocar el núcleo?** Puede hacer la mitad: el objeto, sus acciones y la respuesta.
   Faltan una lista común de «lo que espera» y un lugar donde declararlo sin romper el perfil.
2. **¿Conviene unificar?** Conviene unificar dónde se ven las cosas y cómo se contestan, pero no dónde viven. Ya hay
   tres maneras de que un agente le pregunte algo a la persona. Una cuarta, aparte de las otras, terminaría igual que
   las tres: sin respuesta.
3. **¿Chocan las restricciones?** La de la firma choca: hoy los agentes commitean con la identidad de la persona y
   nada va firmado. La de los comandos choca con el perfil y con los catálogos de un repositorio compartido. La de
   caducar sin efecto no choca con nada.

## 1. Qué puede un módulo y qué le falta

**Lo que ya puede.** Un módulo declara un tipo (`[objetos.pregunta] ver = …, acciones = […]`, en
[../modulos.md](../modulos.md)). Sus órdenes reciben los repositorios en `TELAR_REPOS`, leen los archivos y devuelven
el objeto: título, estado, resumen en markdown, campos, enlaces y acciones. Una acción puede llevar `opciones` para
un parámetro (`Accion.opciones` en `telar.objetos`). La acción `responder` escribe la respuesta en el archivo y le
manda un `telar mensaje` al agente que preguntó. «Conversarlo en un hilo» ya existe: es la instrucción con el
contexto de una entidad (`telar actuar`).

**Lo que le falta, en el núcleo:**

- **Listar.** Un tipo sabe ver un objeto por su id y aplicarle una acción, pero no listar los suyos. Ni el encargo
  tiene colección. Sin una lista no hay bandeja, y la salida que queda es que el módulo dibuje su propia pestaña:
  una superficie más.
- **Un lugar común.** No hay contrato para que un objeto diga «espero a la persona» y aparezca en la barra, en `hoy`
  o en el teléfono. Un módulo no puede poner un número en la barra.
- **Dónde declararlo.** `.telar/perfil.yaml` es estricto: una clave que telar no conoce es `ErrorDePerfil`, y un
  perfil roto rompe todos los hilos a la vez. Si un repositorio agrega `consultas:` al perfil, se le rompe a todo
  el que tenga un telar anterior, incluido cualquier miembro del equipo que no actualizó. Hay precedente para un
  archivo aparte: `.telar/productos.yaml`, `.telar/fechas.yaml` y `.telar/equipo.yaml` ya existen. Propongo
  `.telar/preguntas.yaml`.
- **El formato.** La lente de registros (`telar.tipos.registro`: frontmatter de `clave: valor`, que reescribe solo
  lo que cambió) no lee listas anidadas como `opciones:` con diccionarios. En vez de hacer más complicada la lente,
  propongo que las opciones sean casillas de una sección `## Opciones`, con su id (abajo). telar ya las escribe sin
  tocar el resto del archivo (`telar.vinetas`), se leen sin telar y se editan a mano.
- **La ventana.** La vista genérica de un objeto (`pagina/src/web/objeto.ts`) pide cada parámetro en un campo de
  texto y no muestra las opciones como botones, ni secciones plegables. La base es el componente `ventana()` que se
  está haciendo en la rama de componentes.
- **Caducar.** Algo tiene que escribir `caducada` al vencer: un disparador diario (`[disparadores]`), no el lector.

**Las tres maneras de modelarla:**

| | a favor | en contra |
|---|---|---|
| **una clase de aviso** (`clase: decide`) | una sola palabra para la persona: «cosas para ti», que informan o preguntan | en telar, «aviso» ya nombra tres cosas y ninguna tiene estado (abajo). Una consulta necesita estado, versión, vencimiento, respuesta y firma: se construiría un tipo nuevo igual y se lo llamaría aviso. Además, un aviso que solo informa no merece un archivo ni un commit |
| **(a) un tipo nuevo** sobre archivos del repo | cumple la premisa (el archivo es la verdad, git, se lee sin telar). Usa lo que ya hay: carpeta con versión (409), escritura atómica e historia | si no absorbe a las otras maneras, es la cuarta |
| **(b) un Encargo** dirigido a la persona | ya tiene el ciclo (estado, historia, versión, plazo) y su cierre ya avisa a quien lo pidió | vive en el estado de una máquina (`<estado>/encargos/objetos/`), no en el repo ni en git, y no se lee sin telar. La persona no es un destino (un encargo va a un hilo). No tiene opciones: su resultado es texto. Al vencer solo dice `vencido`. Y va al revés: un encargo dice «haz esto» y una consulta, «decide esto» |

**Recomendación:** la (a), con los verbos y el ciclo del Encargo (`responder`, `retirar`, `caducar`; quien preguntó
recibe el cierre), para que la persona y los agentes aprendan un solo patrón. Y que no se llame «consulta»: esa
palabra ya tiene dos significados en telar, `--modo consulta` («leer el estado de un hilo») y `consulta = true` en una
orden de módulo («entra JSON, sale JSON»). Propongo **`pregunta`**. Es lo que telar ya llama así en tres lugares, y en
los tres es lo mismo: la pregunta en vivo (`mod/pregunta.json`), la clase `pregunta` de `permiso:` y el `avance:
pregunta` de una tarea.

### El formato propuesto

```markdown
---
de: agente:biblioteca
asunto: ¿Dónde va el informe sobre productividad?
estado: abierta                 # abierta · respondida · caducada · retirada
urgencia: baja                  # baja · media · alta
vence: 2026-11-24               # al vencer, caduca sin efecto
toca: tarea:T84, notas/feed/informe.md
recomendada: papers
---
## Resumen
Qué se pregunta, en tres líneas.
## Por qué
Lo que sabe el agente y por qué recomienda lo que recomienda.
## Detalle
Lo que se expande.
## Opciones
- [ ] En papers, con dos aristas <!-- id: papers -->
- [ ] En artículos, junto a lo parecido <!-- id: articulos -->
- [ ] Cerrar la tarea `tarea:T84 completar` <!-- id: cerrar -->

## Historia
- 2026-11-17 09:30 [creada] agente:biblioteca
```

- «Otra cosa…» (texto libre) y «conversarlo» no se escriben en el archivo: la ventana los ofrece siempre.
- Al responder, telar marca la casilla elegida y escribe `estado`, `respuesta`, `respondio` y `respondida`, el texto
  libre en `## Respuesta` y una línea en la historia. Después le manda un mensaje al agente de `de` con la dirección
  de la pregunta. Si alguien la cambió mientras tanto, la respuesta no se escribe (409) y la ventana se relee.
- El efecto sale de una lista cerrada: el mensaje a quien preguntó (siempre) y, si la opción la nombra entre
  comillas invertidas, una acción de un objeto **de fábrica**, que la persona ve escrita antes de elegir.

## 2. ¿Demasiados sistemas?

**Lo que hay hoy**, comprobado:

| qué | quién espera a quién | dónde vive | cómo se contesta | dónde se ve |
|---|---|---|---|---|
| diálogo de permiso del agente (`permiso:<hilo>`) | agente → persona, bloquea el turno | `esperas.json` y la terminal | solo en la terminal | el semáforo y un objeto de solo lectura |
| pregunta en vivo del agente | agente → persona, bloquea el turno | `mod/pregunta.json` | en la terminal o en la conversación, desde cualquier máquina | la conversación |
| `avance` de una tarea (`proponer`) | agente → persona | el archivo de la tarea, en git | `responder`, o cerrar la tarea | tareas, ahora, día |
| mensaje retenido | freno de cadenas → persona | el registro del bus | `soltar` | ⚙ › agentes |
| concesión de un módulo | módulo → persona | `concesiones.json` | siempre · esta vez · no | un diálogo en la página |
| borrador de un módulo de mensajería | agente → persona | el módulo | aprobarlo | la pestaña del módulo |
| Encargo | hilo → agente | estado de la máquina del destinatario | aceptar, rechazar, cerrar | ≡ en AGENTES, la barra del hilo |
| mensaje `aviso` y `pedido` | hilo → hilo | la casilla | no se contesta | la conversación del que lo recibe |
| `telar aviso` | máquina → persona | nada: dura segundos | no se contesta | una notificación del sistema |
| `telar agente evento` (ganchos; antes `agente aviso`) | agente → telar | `atencion.json` | no se contesta | el semáforo |
| tarea y pendiente | compromisos de la persona | archivos | completar, hecho | tareas, foco, hoy |

Correcciones a la lista con que llegó la pregunta:

- `--modo consulta` no es un mensaje: no viaja, lee la ficha y los últimos turnos. Sobra como modo.
- Los ganchos de Claude Code no son un sistema aparte: son de donde salen el semáforo y `permiso:`.
- Tarea y pendiente no son avisos, son compromisos. Pero el `avance` de una tarea **es** un sistema de consultas, y es
  el que más se usa.
- Faltaban tres: la pregunta en vivo, la concesión de un módulo y el borrador que espera aprobación.

**Lo que está duplicado:** tres maneras de que un agente le pregunte algo a la persona (en vivo, en una tarea y la
consulta propuesta); cuatro puertas de aprobación (permiso, retenido, concesión y borrador), cada una con su
superficie; tres cosas que se llaman «aviso» y dos que se llaman «consulta».

**Lo que dice el uso.** En una instalación de uso diario, hoy hay 29 tareas con una pregunta del agente sin
contestar, y la más vieja tiene seis semanas. En dos meses, de más de 500 propuestas de agentes, dos se contestaron
con `responder`; el resto se resolvió por otro lado o no se resolvió. El cuello de botella no es el formato: es que
nada junta las preguntas frente a la persona y le da una manera rápida de contestarlas. Un sistema de consultas
aparte sería la séptima superficie, y le pasaría lo mismo.

**Unificar todo en un solo modelo de «cosa que espera algo de alguien».**
- A favor: un solo lugar donde mirar y una sola manera de contestar. Las propiedades son las mismas en todos: quién
  espera a quién, desde cuándo, qué opciones hay, cuándo vence y qué pasa al contestar. Hoy cada uno reinventa
  algunas: el encargo tiene plazo pero no caduca, el permiso no se contesta desde fuera, el avance no tiene opciones
  y el retenido no vence.
- En contra: difieren en lo que importa. Un permiso bloquea un turno vivo: contestarlo en dos horas no sirve, y una
  pregunta del repositorio puede esperar días. La verdad vive en lugares distintos por buenas razones: la terminal,
  la máquina, el repositorio, el bus. Un solo modelo, o aplana eso (y pierde el bloqueo del permiso o la versión del
  encargo), o se vuelve una unión de campos opcionales. Migrar rompe contratos (`contratos.md`), skills que escriben
  `avance` y costumbres de los agentes. Y es justo la clase de obra que se come al método.
- Costo: semanas. Migrar las tareas y los encargos, y cambiar los contratos con alias.

**Dejar cada uno como está.**
- A favor: todo funciona, tiene pruebas y contrato, y no cuesta nada.
- En contra: la persona sigue aprendiendo seis lugares, y las preguntas se pudren donde nadie mira (los 29 de arriba).
- Costo: cero ahora; después, cada mecanismo nuevo suma una superficie.

**Lo que recomiendo, en medio: unificar la superficie y el contrato de respuesta, no el almacenamiento.** Que cada
tipo pueda decir cuáles de los suyos esperan a la persona (un método `esperando` en `Tipo`, y para un módulo
`[objetos.X] esperando = "<orden>"`). Que el núcleo los junte en una sola lista (`telar esperas`, `GET /esperas`),
una bandeja en la página, el número en la barra y una sola ventana para contestar cualquiera: resumen, detalle
plegable, opciones como botones, texto libre y «conversarlo». Cada fuente sigue viviendo donde vive, y la pregunta del
repositorio es una fuente más. Costo: unos días de un hijo, por pasos (abajo).

**La poda que va con eso.** Hecha (17-nov-2026):
- `--modo consulta`, retirado: lo dicen `telar ficha` y `telar hilo leer`. Sigue andando como alias que avisa en una
  línea por stderr qué usar; la ayuda ya no lo ofrece, `GET /mensajes/consulta` responde lo mismo fuera de
  `/openapi.json`, y la skill que instala telar ya no lo enseña.
- `telar agente aviso` se llama `telar agente evento`. `aviso` queda como alias callado, porque lo corren los ganchos
  ya instalados; `telar agente instalar` escribe `evento` y reemplaza los de antes sin duplicarlos.
- La regla para lo que venga, en [README.md](README.md) («Cómo se escribe una propuesta») y en
  [../desarrollar.md](../desarrollar.md): cada mecanismo nuevo dice qué reemplaza, o por qué no reemplaza nada.

### ¿Un monolito monstruoso?

No es un monorepo: un monorepo junta varios productos, y telar es uno, con un paquete y una versión. Es un monolito
grande, que creció por acumulación. En dos meses llegó a unas 49 mil líneas de Python en 179 archivos, 21 mil de
TypeScript, 8 mil de CSS, 26 mil de pruebas y 60 órdenes de primer nivel. Eso es mucho para una herramienta
personal, aunque todavía no es monstruoso: cada pieza tiene nombre y contrato, las pruebas la cubren, y el plan de
[primitivas.md](primitivas.md) (objetos con dirección, mensajes con modos, tipos sobre archivos) ya es un esfuerzo de
consolidación. Lo que sí es cierto, y conviene oírlo:

- El núcleo absorbe una manera de trabajar que no es de la herramienta: productos, reuniones, eventos, bloques del
  día, el equipo, los atajos. El sistema de módulos funciona (el Gantt salió como módulo), pero el núcleo no ha
  soltado nada.
- Se agregan mecanismos sin retirar los anteriores: tres «avisos», dos «consultas» y tres maneras de preguntar. El
  peso que se siente no es el código: son las palabras que la persona y los agentes tienen que aprender.

Lo que propongo para eso: la regla de la poda de arriba (ya escrita), y sacar a módulos lo de dominio (productos, reuniones y
eventos, equipo) la próxima vez que se toque cada uno.

## 3. Las tres restricciones

**«Telar no ejecuta comandos escritos en un archivo.»** Para las preguntas no choca: el efecto sale de una lista
cerrada (arriba). Choca con dos cosas que ya existen, si la regla vale en general:
- `.telar/perfil.yaml` declara `acciones` con un `comando` que telar corre cuando la persona aprieta la acción. Sin
  shell en medio, pero sin mostrar el comando, salvo con `confirmar: true`.
- El `.telar/catalogo.toml` de un repositorio de `[repos]` es «del equipo»: sus módulos se instalan con un clic, y
  un módulo corre su `[instalar]`.

En un repositorio compartido, quien edite cualquiera de los dos consigue que se corra un comando en la máquina de la
persona cuando ella apriete una tecla. Propuesta: en un repositorio que no es solo de la persona, mostrar el comando y
pedir confirmación siempre, y avisar cuando cambió desde la última vez que se aprobó, como ya se hace con lo que pide
un módulo al actualizarlo. Las acciones de una pregunta se limitan a los tipos de fábrica, porque las de un módulo
corren código del módulo.

**«En un repositorio compartido, solo se muestra como de un agente lo firmado con su identidad de git.»** Choca, y es
lo más caro de las tres:
- Hoy los agentes commitean con la identidad de la persona, y ningún commit va firmado (`%G?` da `N`). No hay
  identidad de agente en git.
- El autor de un commit no prueba nada: cualquiera escribe el nombre que quiera. Lo que prueba es la firma (SSH, con
  `gpg.format = ssh` y una lista de firmantes permitidos en el repositorio).
- La verificación no puede mirar solo el commit que creó el archivo: tiene que mirar todos los que lo tocaron. Si no,
  alguien del equipo cambia las opciones de una pregunta firmada y sigue viéndose como del agente. Lo que no está
  commiteado se ve «sin verificar».
- Los agentes de una persona comparten su usuario y su disco, así que uno puede leer la llave de otro. La firma prueba
  «de las máquinas de esta persona», no «de este agente». Para un repositorio compartido eso alcanza: separa al
  agente de la persona del resto del equipo. Hay que decirlo así, y no prometer más.
- Una pregunta sin verificar se puede leer y contestar con texto, pero sus acciones no se ofrecen.

**«Una pregunta sin respuesta caduca sin efecto.»** No choca. Es lo que ya se hace en todo lo demás: el plazo de un
encargo solo lo marca `vencido`, un retenido nunca se suelta solo, y la propuesta de permisos deja la decisión en la
terminal si no llega respuesta de fuera. Dos detalles: contestar una pregunta caducada se rechaza (409) y el agente
vuelve a preguntar, y caducar le avisa al agente con un mensaje en modo `aviso`, que no lo despierta.

## Los pasos, si se decide

Cada paso deja todo andando, y el orden pone primero lo que sirve sin inventar nada. El 1, la bandeja de solo lectura
con lo que ya existía, está hecho: su diseño está en [../arquitectura.md](../arquitectura.md), «Lo que espera a la
persona, junto».

2. **Contestar desde ahí**, con una sola ventana sobre `ventana()`: `responder` de tarea, `soltar` de retenido y la
   respuesta a la pregunta en vivo, que ya existen.
3. **La pregunta del repositorio**, como módulo: el tipo, `.telar/preguntas.yaml`, el formato de arriba, `esperando`
   y el disparador que caduca. Así se prueba que un módulo alimenta la bandeja sin tocar el núcleo.
4. **Las firmas**, antes de abrirla en un repositorio compartido: una llave por máquina de la persona, los firmantes
   permitidos en el repositorio y la verificación de cada commit que tocó el archivo.
5. **Al teléfono**, solo la urgencia alta: telar hoy no manda nada al teléfono. El canal está por decidir.

## Mundos

**El problema.** La bandeja junta trabajo y vida personal, y todo se ve igual de urgente: sesenta y tantas cosas en una
lista, donde una pregunta sobre un cliente queda al lado de una sobre una suscripción. La persona siente sobredosis. Lo
que falta no es otra bandeja: es poder mirar una parte de la vida a la vez.

**La idea.** Cada espera y cada tarea dice a qué **mundo** pertenece (trabajo, personal…), y la bandeja se agrupa y se
filtra por él. telar es público: los mundos no van escritos en el código, los declara la configuración
(`[mundos]`, en [../configuracion.md](../configuracion.md)), con dos llaves que ya existen en los datos: el `area` de una
tarea y la carpeta de lo que vive en el repositorio. El mundo se deriva de eso, nunca del título:

| qué | de dónde sale su mundo |
|---|---|
| una tarea | su `area`; si su área no es de ningún mundo, la carpeta de su `proyecto` |
| una casilla de un documento, un proyecto | la carpeta de su documento |
| un hilo, su permiso o su pregunta en vivo | la carpeta de su proyecto; si no calza, la de su agente residente; si tampoco, el hilo del que cuelga |
| un mensaje retenido | el hilo al que iba |
| lo de un módulo | su enlace principal |
| lo demás | ninguno: «sin clasificar», que se ve aparte |

Las dos salidas de un hilo que no estaban en el pedido original cubren lo que la carpeta no alcanza: un hijo con rama
trabaja en un worktree fuera de la raíz (es del mundo de su padre), y un agente residente abre sus hilos en la raíz
misma (es del mundo de su carpeta en `agentes/`). Las dos salen de algo declarado (el padre, el agente), no del nombre.

**Hecho (17-nov):** el campo `mundo` en cada espera, en la tarea (su JSON y el objeto `tarea:`) y en las filas de
`telar pendientes` y `telar hoy`; `mundos` (los declarados, en orden) en la respuesta de `telar esperas` y en `telar
config`; el filtro `--mundo` (y `?mundo=`) en `telar esperas`, `telar tipo tarea lista` y `telar pendientes`, con
`sin-clasificar` para lo que no calza; `telar esperas` en tandas en la terminal. La foto de una máquina lleva el
`agente` de cada hilo, para que las otras sepan su mundo. Los contratos, en [../contratos.md](../contratos.md). Sin
`[mundos]`, nada cambia.

**La página, en pausa** (17-nov): el diseño de las tandas sale del rediseño del dashboard, que separa lo importante de lo secundario. Lo que se probó, en un prototipo que quedó en git: «te esperan» en tandas, una por mundo en el orden de la configuración, cada una con sus
grupos de siempre (hilos que esperan, preguntas, para cerrar, preparado, retenidos) y su número de lo que pregunta; «sin
clasificar» al final, aparte. Arriba, junto al filtro por grupo, uno por mundo, que se recuerda en el navegador. Falta
decidir qué cuenta el número de la barra (todo, el mundo elegido o cada uno por separado) y si la pestaña de tareas
lleva el mismo filtro.

## Conexiones

- [primitivas.md](primitivas.md): objetos, mensajes con modos y permisos. Esto es lo que la persona ve de todos ellos.
- [mensajes-con-modos.md](mensajes-con-modos.md): el Encargo, de donde salen el ciclo y los verbos.
- [permisos.md](permisos.md): `permiso:<hilo>`, la primera solicitud que espera a la persona.
- [componentes.md](componentes.md): `ventana()`, la base de la ventana para contestar.
- [../perfil.md](../perfil.md): por qué el perfil no admite claves nuevas sin romperse.
- [../configuracion.md](../configuracion.md), «`[mundos]`»: cómo se declaran los mundos y de dónde sale el de cada cosa.
