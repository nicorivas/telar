# Las primitivas de telar

Propuesta, 16-oct-2026. Estado: **por decidir y construir**. Sale de cuatro estudios hechos en paralelo:
un inventario de qué se usa de verdad (registros, configuración y llamadores en las dos máquinas), el
modelo de datos de seis administradores de agentes (OpenHarness, vibe-kanban, happy, CAO, Agent of
Empires, herdr), el de cinco plataformas conocidas (Letta, OpenHands, AIOS, Temporal, los SDK de agentes
de OpenAI y Claude, MCP) y una auditoría de cómo telar convive con git.

## Por qué

Telar tiene 44 órdenes y unas 25.000 líneas de Python, y se pensó una orden a la vez. El resultado se
ve en el inventario:

- **Cuatro formas de dejarle texto a un hilo** (`correo`, `mensaje`, `encargar`, `atajo`), y `encargar`
  ya es por dentro un `mensaje` de otro tipo.
- **Cuatro órdenes sobre las tareas** (`pendiente`, `pendientes`, `tarea`, `cambio`).
- **Cinco formas de poner una página en el dashboard** (`seccion`, `bloque`, `app`, `modulos`,
  `resultado`), todas «una página o un dato que sale de un comando o una carpeta».
- **Tres caminos entre máquinas** que hacen lo mismo: la puerta (`enlace`), el espejo por ssh y el bus.
  Con bus, la puerta no se usa para enviar desde el 5-oct, y la llamada que la extensión hace cada 30 s
  a `espejo publicar` no hace nada.
- **Peso muerto**: `movil` (seis procesos huérfanos y ningún llamador; lo reemplazó `web`) y el correo
  entre agentes por Maildir (21 correos reales en tres semanas, frente a 314 avisos de cron). Zellij no
  lo usa nadie aquí, pero el README lo ofrece como multiplexor. Las órdenes `tiempo` y `atencion` parecen
  sin uso porque nadie las llama a mano, pero son la entrada pública por la que un multiplexor o un
  agente que no sea Claude Code le avisan a telar, y `doctor` revisa que estén conectadas.

Y lo que más duele no está en telar sino al lado: **git**. Muchos escritores (hilos, agentes, la CLI
de tareas, los periódicos) escriben sobre un mismo árbol de trabajo por máquina, en una sola rama. El
registro de subidas automáticas del laptop tiene 37 choques con archivos sin commitear, y el del
servidor 65 carreras de push. Hay autostash que resucitan archivos borrados, divergencias de cientos de
commits en el repo de trabajo y números de tarea repetidos. El protocolo de commit está escrito a mano,
en prosa, en cinco skills distintas.

Antes de agregar más, hay que encontrar las pocas piezas de las que todo lo demás se arma. Si una
orden de hoy no se puede expresar con ellas, falta una pieza; si dos piezas hacen lo mismo, sobra una.

## Lo que enseñan los demás

**Confirman:**

- **Agente y ejecución separados.** Todos los que lo hacen bien distinguen lo que el agente *es* de lo
  que *corre*. Temporal separa Definition de Execution, OpenHands tiene un agente congelado y sin estado
  frente a una conversación con estado, CAO tiene perfil y terminal, y AoE tiene Agent y Session.
- **Una tercera identidad: la conversación del motor.** OpenHarness, AoE y Letta separan además el id
  de la conversación de Claude o Codex, que rota al compactar, se bifurca y sobrevive a la ventana. En
  telar hoy se confunde con el hilo (`sesiones.json`).
- **Mensajes con estado por destinatario** (en cola, entregado, falló) y un modo **fyi**, que no
  despierta al agente (OpenHarness, CAO).
- **El turno como unidad**, con un id y un único final (terminó, falló, cancelado, espera respuesta).
  Lo tienen OpenHarness, happy, vibe-kanban y AoE.
- **El reloj como disparador** (los Flow de CAO, los cron de Letta) y **el manifiesto con permisos** en
  los módulos (AoE).

**Matizan:**

- **El mensaje solo se queda corto.** Temporal distingue tres operaciones: *query* (leer el estado sin
  perturbarlo), *signal* (escribir sin esperar respuesta) y *update* (escribir y esperar respuesta, con
  validación antes de aceptar). El «encargo» de telar es un update, al que le falta la validación, y la
  consulta pura no existe.
- **El encargo es un objeto durable, no un mensaje.** Tiene estados (aceptado, corriendo, hecho, falló),
  plazo, presupuesto y resultado: es la Workflow Execution de Temporal. Hoy está escondido en el texto de
  un mensaje, y nadie puede preguntar «¿en qué va lo que le pedí a Gestión?».
- **Quién pidió no es quién ejecuta.** Letta (`acting_user_id`) y OpenAI (`run_as`) lo separan. En telar
  importa porque un periódico, un agente o la persona pueden pedir lo mismo.
- **El lugar de trabajo no es del agente.** OpenHands, OpenAI y Letta ponen la carpeta, la máquina y el
  sandbox en la ejecución. El agente declara a lo más un lugar por defecto.

**Nadie tiene** objetos de dominio con dirección (todos usan entidades fijas: sesión, tarea, máquina),
tipos con acciones aportados por un proveedor, ni intenciones resueltas por tabla. Tampoco un nodo que
reconcilia estado deseado sobre un bus compartido, ni un modelo único de permisos para personas y
agentes: en todos, los permisos son de usuario o de dispositivo. Eso es lo propio de telar.

## Qué es un agente

Un **agente** es una definición, no algo que corre: **identidad, instrucciones, capacidades y política**.
Es el programa; el hilo es el proceso. Puede no tener ningún hilo vivo y seguir existiendo, con su
memoria, o tener varios a la vez.

| campo | qué es | hoy |
|---|---|---|
| `nombre`, dirección | la identidad estable | el nombre del hilo residente |
| `para` | cuándo encargarle algo, en una o dos frases: lo que lee la tabla de intenciones y otro agente que busca a quién pedirle | no existe |
| `instrucciones` | su `CLAUDE.md` | la carpeta del residente |
| `memoria` | la carpeta propia (git), más las memorias compartidas que lee por referencia | `memoria/` del residente, más la de la casa |
| `capacidades` | skills, herramientas y servidores MCP **propios** (las de la máquina las pone el lugar) | implícitas |
| `politica` | modo de permisos, herramientas negadas, límites por encargo (turnos, costo), qué puede hacer sin preguntar | repartida en `settings.json` y en prosa |
| `modelo` | el modelo por defecto; un hilo puede cambiarlo | la configuración global |
| `ganchos` | lo que corre al empezar, terminar o recibir algo | globales |
| `lugar` | dónde trabaja por defecto (máquina, carpeta) y dónde puede | `[agentes]` en la configuración |
| `residente` | si debe estar siempre vivo: eso lo vuelve estado deseado del nodo | implícito |

Lo que **no** es del agente y va en el hilo: la conversación del motor, la atención, el historial, el
lugar concreto donde corre ahora y las credenciales que se le dieron a esa ejecución.

Se define en un archivo dentro de su carpeta (`agente.toml`, al lado de su `CLAUDE.md`), igual que los
subagentes de Claude Code y OpenHands se definen en archivos con frontmatter. Un hilo de proyecto común
corre el **agente por defecto** (la definición mínima: las instrucciones del repo y nada más), así que
todo hilo tiene un agente, pero no hace falta escribir uno para cada proyecto.

## Las primitivas

Once piezas en tres familias, más dos reglas que las atraviesan. La propuesta anterior tenía once también.
Los estudios agregaron cinco ideas (el turno, el encargo durable, los modos de mensaje, el lugar y quién
pide frente a quién ejecuta), y casi todas caben dentro de piezas que ya estaban. Solo **Lugar** entra
como pieza nueva. **Dirección**, que antes contaba como pieza, pasa a ser regla.

### Datos: qué hay

1. **Objeto.** Cualquier cosa con dirección, tipo y estado: una tarea, un correo, un proyecto, un evento,
   un encargo, un hilo, un módulo.
2. **Tipo.** La forma de un objeto y sus **acciones**, cada una con un esquema de argumentos (como una
   herramienta MCP), que sirven igual para un clic que para un agente. Lo implementa un **proveedor**, que
   puede vivir en otra máquina (`en = "telar"`, como las tareas hoy). **Proyecto** es un tipo, no una
   primitiva. **Encargo** también es un tipo, que el núcleo trae de fábrica: estados `pedido → aceptado →
   corriendo → hecho | falló | cancelado`, con quién lo pidió, quién lo ejecuta, plazo y resultado.
3. **Cambio.** Lo que le pasó a un objeto, con un número de orden por colección. La atención de un hilo,
   «la tarea T366 se cerró», un correo nuevo y **el turno de un hilo** (empezó, terminó, falló, espera
   respuesta, con su id) son cambios. Cualquiera se pone al día pidiendo «desde el cambio N», sin sondear
   (como `changes` de JMAP o el `seq` de happy).

### Actores: quién hace qué

4. **Sujeto.** Quien puede actuar: una **persona** o un **agente** (definido arriba). Personas y agentes
   son la misma clase de cosa ante los permisos: eso es lo que hace al sistema agent-first. Toda acción
   registra dos sujetos: **quién la pidió** y **quién la ejecuta**.
5. **Hilo.** Un agente corriendo en un lugar: su conversación del motor (que puede rotar o bifurcarse,
   con su linaje), su atención, sus turnos y su ventana. Nace, se archiva, se retoma, se lleva a otra
   máquina y muere. Tiene **un solo dueño**, el nodo donde corre (ver `un-dueno-por-hilo.md`).
6. **Mensaje.** La única forma de hacer actuar a un sujeto, en cuatro modos:
   - **aviso** (fyi): queda en su casilla y no lo despierta;
   - **pedido** (signal): lo despierta y no espera respuesta;
   - **encargo** (update): crea un objeto Encargo, que el destinatario **acepta o rechaza** antes de
     empezar, y que se cierra con un resultado;
   - **consulta** (query): lee el estado de un hilo o un agente sin entrar a su conversación (lo que hoy
     hacen `ficha` y `hilo leer`).

   Cada mensaje tiene un estado por destinatario (en cola, entregado, falló) y una forma de entrega
   (gancho si está trabajando, tecleado si está ocioso, leído a mano). El destinatario es una dirección
   o una **intención** («trabajar en `tarea:T366`»), y una **tabla fija** la resuelve: el hilo vivo del
   proyecto de la tarea, si no un hilo nuevo con el agente de ese proyecto, y si no el agente de lo que
   no tiene proyecto. Si después hace falta que un módulo atienda intenciones, la tabla se abre; por
   ahora, no.
7. **Disparador.** Lo que emite mensajes solo: un **reloj** (los periódicos), una **tecla** (los atajos)
   o un **cambio** («cuando llegue un correo de X»). Hoy son tres mecanismos aparte, y el último no
   existe.

### Sistema: dónde corre y cómo se ve

8. **Nodo.** Una máquina con su proceso telar, unida a las demás por el bus. Publica su foto y
   **reconcilia el estado deseado**, que se declara solo para los agentes residentes, los periódicos y
   los módulos. Los hilos de proyecto los abre y cierra la persona.
9. **Lugar.** Dónde trabaja un hilo: un nodo, una carpeta de un repositorio y la rama en que está.
   Puede ser la carpeta común del repo o un **worktree propio**, según lo que declare el perfil del repo
   (ver «Git y los repositorios»). Tiene su propio ciclo: se crea, se integra a la rama principal y se
   descarta. Un hilo corre en un lugar; varios hilos pueden compartir uno.
10. **Vista.** Cómo se presenta un objeto o una colección: una página declarativa que sale de un
    comando, o una app aislada (un archivo o una URL). Absorbe secciones, bloques, apps, pestañas de
    proveedor y resultados. Declara **dónde** aparece (una pestaña, la barra, una tecla).
11. **Módulo.** El paquete: un manifiesto (`modulo.toml`) que declara tipos y proveedores, vistas,
    disparadores, agentes, skills y los **permisos** que pide. Se instala en uno o más nodos.

### Las dos reglas

- **Dirección.** Todo objeto, sujeto, hilo, lugar y vista tiene una, con una sola forma:
  `tipo:id`, más el nodo cuando importa (`telar:hilo:Gestión`). Ejemplos: `tarea:T366`,
  `correo:1a13c3f7`, `agente:gestion`, `encargo:e-0412`, `vista:correo`. Hoy hay seis formas (un `ref`,
  un id, un nombre de hilo, `@338/marca`, `gmail:<id>`, `proyecto:3`). Con una sola, un mensaje puede
  decir «revisa `correo:1a13c3f7`» y cualquiera sabe abrirlo, verlo o actuar sobre él.
- **Permiso.** Qué puede hacer un sujeto o un módulo: con qué tipos, qué acciones, en qué nodos, y qué
  pide confirmación. Se diseña desde ya, aunque al empezar todo esté permitido para la persona dueña y
  para sus agentes. Una **solicitud de permiso** (la que hoy aparece como «espera» en un hilo) es un
  objeto con su decisión (aprobado, aprobado por esta sesión, negado), que se puede contestar desde
  cualquier superficie.

## Cómo queda cada orden

Las 44 órdenes, en las primitivas. En la columna **destino**, *queda* significa que sigue con otro
fondo, *se funde* que pasa a ser parte de otra orden, y *se va* que se borra.

| orden | uso real | en las primitivas | destino |
|---|---|---|---|
| `hilos`, `hilo`, `ficha`, `vincular`, `ir` | mucho | hilo (`ficha` es una consulta; `vincular` fija el lugar) | quedan; `ficha` pasa a `consulta` |
| `mirar` | por debajo de `ir` y la web | hilo, desde una vista | queda |
| `tejer` | la extensión | nodo (levantar su sesión) | queda |
| `nodo` | siempre corriendo | nodo | queda; suma estado deseado |
| `mensaje` | mucho | mensaje | queda, con modos |
| `encargar` | skills, periódicos | mensaje modo encargo + objeto Encargo | se funde en `mensaje` (alias) |
| `atajo` | la extensión | disparador (tecla) que emite un encargo | se funde en disparadores |
| `reunion` | skills | un tipo (`reunion`) con la acción «preparar», que emite un encargo | queda como tipo |
| `correo` (Maildir) | casi nada | mensaje entre personas | **se va** cuando el bus cruce entre usuarios |
| `enlace` (la puerta) | nada desde el 15-oct | nodo + bus | **se va** |
| `espejo` | lo hace el nodo | nodo (la foto) | se funde; la llamada de la extensión se va |
| `remotos` | la extensión | nodo (los hilos de otro) | queda, por el bus |
| `directorio` | otro usuario | sujeto persona y sus hilos | queda, pasa a sujetos |
| `persona`, `equipo` | casi nada | sujeto persona + permisos + una vista | quedan dormidos hasta los permisos |
| `agente` | los ganchos | hilo (avisos, casilla) + sujeto (skills) | queda |
| `atencion`, `tiempo` | por ganchos | cambio del hilo (la atención, el foco): la entrada para agentes y multiplexores ajenos | quedan |
| `pendientes` | poco | consulta de objetos tarea | se funde en `tarea` |
| `pendiente` | skills | intención «trabajar en» sobre una tarea | se funde en `tarea … --accion trabajar` |
| `tarea` | mucho | objeto + tipo + acciones | queda, y se generaliza a todo objeto |
| `cambio` | una skill | cambio | queda |
| `accion` | poco | acción de un tipo (el perfil) | se funde en las acciones |
| `hoy` | mucho | una vista que junta colecciones | queda |
| `seccion`, `bloque`, `app`, `resultado` | la extensión | vista | se funden en `vista` |
| `modulos` | nadie llama | módulo | queda (instalar, ver) |
| `periodicos` | cron | disparador (reloj) + estado deseado del nodo | queda |
| `evento` | skills | un tipo (`evento`) con la acción «anotar» | queda como tipo |
| `proyectos` | la extensión | colección de objetos proyecto | queda |
| `imagen` | el atajo de tmux | acción del hilo («llevar este archivo a su lugar») | queda |
| `movil` | nada | — | **se va** (lo cubre `web`) |
| `web` | el celular | una superficie del panel | se funde en el panel (`telar serve`) |
| `config`, `perfil`, `doctor`, `init` | instalación | — | quedan |

Todas caben: ninguna orden pide una pieza que no esté. Lo que sale de esta traducción:

- **Trece órdenes se van o se funden** sin perder nada: `enlace`, `movil`, `correo`, `espejo`,
  `pendientes`, `pendiente`, `accion`, `seccion`, `bloque`, `app`, `resultado`, `encargar`, `atajo`. Las
  que se funden quedan un tiempo como alias.
- **`tarea` se vuelve `objeto`.** Ver una cosa por su dirección, correr una de sus acciones y pedir sus
  cambios es lo mismo para una tarea, un correo, un evento, una reunión o un encargo. Es la pieza que
  más órdenes absorbe.
- **Faltaba el encargo como objeto.** Hoy no hay forma de ver en qué va lo que uno encargó.

## Git y los repositorios

La causa común de los choques es la misma: muchos escritores sobre un solo árbol de trabajo por
máquina, en una sola rama, sin dueño por archivo. Las primitivas lo ordenan así:

**1. El lugar de cada hilo puede ser un worktree propio.** Un worktree es otra carpeta del mismo
repositorio, en su propia rama: comparte la historia y los objetos, y no hace falta clonar. Así el
hilo escribe en su carpeta y en su rama, y nadie toca lo que otro dejó a medias. Se acaban el árbol
sucio compartido, el autostash que resucita lo borrado y el commit que se lleva lo ajeno (tres de los
siete modos de falla de la auditoría). Al cerrar el hilo, o cuando lo pida, telar integra su rama a la
principal; si choca, el choque aparece una vez y en el hilo que lo causó. El perfil de cada repo
declara si sus hilos usan worktree:

```toml
[lugar]
worktree = true            # cada hilo en su carpeta y su rama: el código, los proyectos
integrar = "al-cerrar"     # o "a-mano"
```

Conviene en los repos de código y en los proyectos del repo de trabajo. En el estado compartido del repo
de vida (memoria, tareas, ánimo, bitácoras) no conviene, porque los demás tienen que ver al tiro lo que
uno escribe.

**2. Los archivos calientes tienen un solo escritor.** Son los que escriben muchos: el índice de
memoria, las tareas, el ánimo y las bitácoras. El perfil los declara, y se escriben siempre en un solo
nodo (el servidor). Las otras máquinas los cambian por el bus, igual que ya pasa con las tareas desde
el 9-oct. Eso quita la mayoría de las carreras de push del registro.

```toml
[calientes]
escritor = "telar"
rutas = ["memory/**", "nico/proyectos/tareas/**", "agentes/*/bitacora.md"]
```

**3. `telar commit` en el núcleo.** Hoy el protocolo (`git add -- archivo`, `commit -- rutas`,
`pull --rebase --autostash`, `push`) está escrito en prosa en cinco skills y en las instrucciones de los
agentes, y la CLI de tareas tiene su propia versión. Telar lo hace una sola vez y bien:

```
telar commit -m "…" -- rutas      solo esas rutas (incluidas las nuevas)
```

- Integra sin autostash: si lo que llega choca con algo sin commitear, se detiene y lo dice.
- Reintenta el push con espera cuando la falla es una carrera.
- Escribe un registro único.
- Si una ruta es caliente y este nodo no es su escritor, se la manda al escritor por el bus.
- Nunca hace `git add -A` y respeta `skip-worktree`.

Las skills pasan a decir «`telar commit -- rutas`» y nada más.

**4. Qué es de quién.** Hoy telar supone cosas de un repo en particular. La auditoría encontró que el
núcleo en Python respeta bastante bien el límite del perfil. Las filtraciones están en la extensión, en
`equipo.py` y en un par de rutas:

| fijo hoy | dónde | pasa a |
|---|---|---|
| la lista de áreas (`PIA`, `EIC`…) | `vistas/proyectos.ts:45` | el perfil: `areas = […]`, con su orden |
| `brinca` e `interno` como clientes que no se muestran | `vistas/hoy.ts:637` | el perfil: `clientes_propios = […]` |
| el agente «gestion» por nombre | `equipo.ts`, `cli.ts`, `reunion.py`, `webcal.py`, `app.js` | `[agentes] sin_proyecto`, que ya existe |
| «Nico» en `--de` y en los textos | `cli.ts`, `hoy.ts`, `webcal.py`, `web.py` | `[persona] nombre` en la configuración |
| la ruta de las lecturas | `ordenes/web.py:380` | un módulo del repo |
| el formato de la CLI de tareas | `equipo.py` | el proveedor de tareas, con sus acciones |
| el perfil de colega, que lee el correo de un agente fijo | `persona.py:42` | la configuración |
| `Estado`/`Etapa` y la clave `Cliente` | `ordenes/proyectos.py` | el perfil |

La regla queda así: **el núcleo** sabe de hilos, mensajes, objetos, nodos, lugares y git. **El perfil de
cada repo** sabe de sus unidades, sus campos, sus áreas, su agente para lo que no tiene proyecto, quién
opera, sus archivos calientes y si usa worktrees. **Los módulos** traen lo propio de una vida: la CLI de
tareas, la sincronización, las lecturas, la casa de un agente.

## El servidor y la interfaz

El estudio de arquitectura anterior queda igual: un `telar serve` en Python, que se queda corriendo y
habla la misma API que la CLI, porque lo lento hoy es abrir un proceso por cada llamada, no el lenguaje.
El escritorio es web (`npm run panel`). Las primitivas le dan su contrato: **objetos por dirección,
acciones con esquema, cambios desde N y vistas declaradas**. Con ese contrato, una app de un módulo, el
dashboard y un agente usan la misma API.

## Los pasos

Cada paso deja todo funcionando y se puede parar en cualquiera.

0. **Limpiar lo muerto.** Se va la orden `movil` (su librería de ventanas queda: la usa medio telar).
   La puerta (`enlace`) y el correo por Maildir se van cuando el bus cubra a otras personas: hoy solo
   cruza entre hilos de un mismo usuario. Zellij, por decidir: nadie lo usa aquí, pero el README lo
   ofrece.
1. **`telar commit`** y el perfil con `[calientes]`. Las skills y la CLI de tareas pasan a usarlo. Es lo
   que más dolor quita y no depende de lo demás.
2. **Direcciones y objetos.** Un registro de tipos en el núcleo (las tareas primero, después correo,
   evento, reunión, proyecto) y `telar objeto <dirección> [--accion …]`, con `tarea` como alias. Las
   acciones con esquema.
3. **El agente como definición.** `agente.toml` en la carpeta de cada residente. El hilo guarda su
   agente, su conversación del motor y su lugar, cada uno por separado.
4. **Mensajes con modos y el Encargo.** `mensaje --modo aviso|pedido|encargo|consulta`, el objeto
   Encargo con sus estados, y la tabla de intenciones. Se funden `encargar`, `atajo`, `pendiente` y
   `reunion`.
5. **El lugar y los worktrees.** `[lugar]` en el perfil: el hilo nace en su worktree, y se integra y se
   descarta con acciones del hilo.
6. **Vistas.** `[vistas]` reemplaza a `[secciones]`, `[bloques]`, `[apps]` y `[resultados]`, que se
   siguen leyendo un tiempo.
7. **Disparadores y estado deseado.** Periódicos, teclas y «al cambiar» en un solo `[disparadores]`; el
   nodo reconcilia residentes, periódicos y módulos.
8. **Permisos.** Sujetos con permisos, la solicitud de permiso como objeto y los manifiestos de módulo
   con lo que piden.
9. **`telar serve`.** La API que se queda corriendo, con el contrato de arriba.

### Las CLI sueltas

Fuera de telar, el repo de vida tenía unas 40 CLI propias. Seis tocan el correo y cuatro las
tareas, y 17 eran restos del sistema anterior (flow). No es malo tener muchas órdenes chicas; lo
malo es que no haya una puerta para encontrarlas, que dos hagan lo mismo y que la lógica se copie.
Lo que se centraliza es **la entrada y el contrato, no el código**:

- **Órdenes de módulo.** Un módulo declara sus órdenes en `modulo.toml` (`[ordenes]`), y se llaman
  `telar <modulo> <verbo>`, como git encuentra `git-lfs`. `telar --help` las lista con su ayuda,
  así que un agente las descubre solo. El código sigue en la carpeta del módulo.
- **Los adaptadores van con su dato.** `telar-tareas`, `telar-correo` y `telar-retro` traducen datos
  de una vida al contrato de telar: no son de telar (que es genérico) ni del agente en cuya carpeta
  quedaron. Cada uno va a un módulo junto a su dato: las tareas con su CLI, el correo con sus
  clientes de Gmail (las seis en un solo proveedor, con acciones) y la retro con los planes del día.
  La configuración deja de listar rutas a mano: declara módulos, y cada uno dice lo que aporta.
- **Módulos de ejemplo en telar.** Lo genérico, como un proveedor de Gmail sin nada de nadie, puede
  vivir en `telar/modulos/` para que otros lo usen; el módulo propio se apoya en él.

Orden: borrar lo muerto de flow (hecho el 18-oct), las órdenes de módulo, y el correo como
proveedor único (va con el paso 2).

Las fallas del bus que vio el inventario van aparte, antes del paso 4: los `nats: timeout`, el
«Slow Consumer» del laptop y un registro del nodo de 19 MB.

## Lo que queda abierto

- **Integrar al cerrar o a mano.** Integrar solo es cómodo, pero puede meter a la rama principal algo que
  nadie revisó. Integrar a mano deja ramas vivas que se alejan.
- **Los calientes por git o por el bus.** Un solo escritor por git sigue siendo legible (son archivos) y
  más lento (hay que esperar el pull). Por el bus es inmediato, pero sale de git. La propuesta parte por
  git con un escritor.
- **El nombre de la dirección.** `tarea:T366` es corto, y `telar://telar/tarea/T366` es una URL que el
  navegador puede abrir. Se puede tener las dos: la corta para escribir y la larga para enlazar.

## Lo hecho (17-oct-2026)

- **Paso 0, en parte:** se fue la orden `movil` (su librería de ventanas quedó). `tiempo` y `atencion`
  quedan: el inventario las vio sin llamadores, pero son la entrada pública de los ganchos.
- **Paso 1, la orden:** `telar commit` (`src/telar/git.py`, `ordenes/commit.py`), con pruebas sobre
  repositorios de verdad: dos copias que escriben a la vez, lo ajeno sin commitear, `skip-worktree`, el
  rebase que choca y la carrera de push. Falta que las skills, las instrucciones de los agentes y la CLI
  de tareas lo usen en vez de su protocolo propio, y `[calientes]` en el perfil.
