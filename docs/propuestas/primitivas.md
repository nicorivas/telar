# Las primitivas de telar

Estado: **por construir, en pasos**. Hechos: `telar serve` (la API que se queda corriendo), `telar
commit` como orden, y el primer tipo (`tarea`, en [arquitectura](../arquitectura.md), «Los tipos»). Lo que
sigue va encima de la API, no de la CLI suelta.

## Por qué

telar se pensó una orden a la vez (unas 45), y se nota: cuatro formas de dejarle texto a un hilo
(`correo`, `mensaje`, `encargar`, `atajo`), cuatro órdenes sobre las tareas (`pendiente`, `pendientes`,
`tarea`, `cambio`), cinco formas de poner una página en el dashboard (`seccion`, `bloque`, `app`,
`modulos`, `resultado`). Y lo que más duele está al lado: **git**. Muchos escritores (hilos, agentes,
periódicos) sobre un mismo árbol de trabajo por máquina, en una sola rama: choques con archivos sin
commitear, carreras de push, autostash que resucitan lo borrado, el protocolo de commit escrito en
prosa en cinco skills.

La idea es encontrar las pocas piezas de las que todo se arma. Si una orden no se puede expresar con
ellas, falta una pieza; si dos piezas hacen lo mismo, sobra una.

Salió de estudiar otros administradores de agentes (OpenHarness, vibe-kanban, happy, CAO, Agent of
Empires, herdr) y plataformas (Letta, OpenHands, AIOS, Temporal, los SDK de agentes, MCP). Confirman
separar el agente de su ejecución, la conversación del motor como una tercera identidad, mensajes con
estado por destinatario, el turno como unidad y el encargo como objeto durable (la Workflow Execution
de Temporal). Ninguno tiene objetos de dominio con dirección, tipos con acciones aportados por un
proveedor, ni un modelo único de permisos para personas y agentes: eso es lo propio de telar.

## Qué es un agente

Un **agente** es una definición, no algo que corre: **identidad, instrucciones, capacidades y política**.
Es el programa; el hilo es el proceso. Se define en `agente.toml`, al lado de su `CLAUDE.md`.

| campo | qué es | hoy |
|---|---|---|
| `nombre` | la identidad estable | el nombre del hilo residente |
| `para` | cuándo encargarle algo, en una o dos frases | no existe |
| `instrucciones` | su `CLAUDE.md` | la carpeta del residente |
| `memoria` | la carpeta propia, más las compartidas que lee | `memoria/` del residente |
| `capacidades` | skills, herramientas y MCP propios | implícitas |
| `politica` | permisos, herramientas negadas, límites por encargo, qué hace sin preguntar | repartida en `settings.json` y en prosa |
| `modelo` | el modelo por defecto | la configuración global |
| `lugar` | dónde trabaja por defecto y dónde puede | `[agentes]` |
| `residente` | si debe estar siempre vivo (estado deseado del nodo) | implícito |

Lo que va en el hilo, no en el agente: la conversación del motor, la atención, el historial, el lugar
donde corre ahora. Un hilo de proyecto corre el **agente por defecto** (las instrucciones del repo).

## Las piezas

**Datos: qué hay.**

1. **Objeto.** Cualquier cosa con dirección, tipo y estado: una tarea, un correo, un evento, un
   encargo, un hilo, un módulo.
2. **Tipo.** La forma de un objeto y sus **acciones**, con un esquema de argumentos (como una
   herramienta MCP). Lo implementa un proveedor, que puede vivir en otra máquina. **Encargo** es un tipo
   de fábrica: `pedido → aceptado → corriendo → hecho | falló | cancelado`, con quién lo pidió, quién lo
   ejecuta, plazo y resultado.
3. **Cambio.** Lo que le pasó a un objeto, con un número de orden por colección. La atención, «T366 se
   cerró», un correo nuevo y **el turno de un hilo** son cambios. Cualquiera se pone al día pidiendo
   «desde el cambio N», sin sondear.

**Actores: quién hace qué.**

4. **Sujeto.** Una persona o un agente, la misma clase de cosa ante los permisos. Toda acción registra
   **quién la pidió** y **quién la ejecuta**.
5. **Hilo.** Un agente corriendo en un lugar: su conversación (que rota o se bifurca), su atención, sus
   turnos y su ventana. Tiene un solo dueño ([un-dueno-por-hilo.md](un-dueno-por-hilo.md)).
6. **Mensaje.** La única forma de hacer actuar a un sujeto, en cuatro modos: **aviso** (queda en la
   casilla, no despierta), **pedido** (despierta, no espera respuesta), **encargo** (crea un Encargo que
   el destinatario acepta o rechaza, y que se cierra con un resultado) y **consulta** (lee el estado sin
   entrar a la conversación: lo que hoy hacen `ficha` y `hilo leer`). Cada mensaje tiene un estado por
   destinatario (en cola, entregado, falló). El destino es una dirección o una **intención** («trabajar en
   `tarea:T366`»), que una tabla fija resuelve: el hilo vivo del proyecto, si no uno nuevo con su agente,
   si no el agente de lo que no tiene proyecto.
7. **Disparador.** Lo que emite mensajes solo: un reloj (los periódicos), una tecla (los atajos) o un
   cambio («cuando llegue un correo de X», que no existe).

**Sistema: dónde corre y cómo se ve.**

8. **Nodo.** Una máquina con su telar, en el bus. Publica su foto y **reconcilia el estado deseado**
   (residentes, periódicos, módulos).
9. **Lugar.** Dónde trabaja un hilo: nodo, carpeta y rama. Puede ser la carpeta común o un **worktree
   propio**. Se crea, se integra a la rama principal y se descarta.
10. **Vista.** Cómo se presenta un objeto o una colección: una página declarativa o una app aislada.
    Absorbe secciones, bloques, apps y resultados, y declara dónde aparece.
11. **Módulo.** El paquete: un `modulo.toml` que declara tipos, proveedores, vistas, disparadores,
    agentes, skills, órdenes y los **permisos** que pide.

**Dos reglas que las atraviesan.**

- **Dirección.** Una sola forma, `tipo:id` (más el nodo cuando importa): `tarea:T366`,
  `correo:1a13c3f7`, `agente:gestion`, `encargo:e-0412`. Hoy hay seis formas. Con una, un mensaje puede
  decir «revisa `correo:1a13c3f7`» y cualquiera sabe abrirlo.
- **Permiso.** Qué puede hacer un sujeto o un módulo: con qué tipos, qué acciones, en qué nodos, qué
  pide confirmación. Una solicitud de permiso (la «espera» de un hilo) es un objeto con su decisión, que
  se contesta desde cualquier superficie.

## Cómo quedan las órdenes

- **Se funden** (quedan un tiempo como alias): `encargar` y `atajo` en `mensaje` y los disparadores;
  `pendientes`, `pendiente` y `accion` en `tarea`, que se vuelve `objeto`; `seccion`, `bloque`, `app` y
  `resultado` en `vista`.
- **Se van** cuando el bus cruce personas: `correo`, `enlace` y el espejo por ssh (ver
  [telar-para-otros.md](telar-para-otros.md)).
- **`reunion` y `evento`** pasan a ser tipos con sus acciones.
- **Quedan**: `hilos`, `hilo`, `ficha` (como consulta), `vincular`, `ir`, `mirar`, `tejer`, `mensaje`,
  `agente`, `atencion` y `tiempo` (la entrada de los ganchos de agentes y multiplexores ajenos), `hoy`,
  `cambio`, `modulos`, `periodicos`, `proyectos`, `imagen`, `directorio`, `persona`, `equipo`, `config`,
  `perfil`, `doctor`, `init`, `serve`, `commit`, `tipo`.

## Git y los repositorios

1. **El lugar de cada hilo puede ser un worktree propio**, en su rama: nadie toca lo que otro dejó a
   medias, y un choque aparece una vez y en el hilo que lo causó. El perfil del repo lo declara:

   ```toml
   [lugar]
   worktree = true            # cada hilo en su carpeta y su rama
   integrar = "al-cerrar"     # o "a-mano"
   ```

   Conviene en el código y en los proyectos; no en el estado compartido (memoria, tareas, bitácoras),
   que los demás tienen que ver al tiro.
2. **Los archivos calientes tienen un solo escritor** (un nodo); las demás máquinas los cambian por el
   bus, como ya pasa con las tareas.

   ```toml
   [calientes]
   escritor = "telar"
   rutas = ["memory/**", "nico/proyectos/tareas/**", "agentes/*/bitacora.md"]
   ```
3. **`telar commit -m "…" -- rutas`** (hecho como orden): solo esas rutas, incluidas las nuevas; integra
   sin autostash y se detiene si choca; reintenta el push en una carrera; nunca `git add -A`; respeta
   `skip-worktree`. Falta que lo usen las skills y las instrucciones de los agentes, y que mande una ruta
   caliente a su escritor.
4. **Qué es de quién.** El núcleo sabe de hilos, mensajes, objetos, nodos, lugares y git; el perfil de
   cada repo, de sus unidades, campos, áreas, agente para lo que no tiene proyecto, calientes y worktrees;
   los módulos traen lo propio de una vida. Lo que hoy está fijo y debería salir del perfil o la
   configuración: la lista de áreas (`vistas/proyectos.ts`), los clientes propios que no se muestran
   (`vistas/hoy.ts`), el agente «gestion» por nombre, «Nico» en `--de` y en los textos (`[persona]
   nombre`), el formato de tareas en `equipo.py`, `Estado`/`Etapa`/`Cliente` en `ordenes/proyectos.py`.

## Los pasos que faltan

Cada uno deja todo funcionando.

1. **`telar commit` en todas partes**, y `[calientes]` en el perfil.
2. **Direcciones y objetos.** El registro de tipos suma correo, evento, reunión y proyecto, y `telar objeto
   <dirección> [--accion …]`, con `tarea` como alias. Dos preguntas del tipo `tarea` por cerrar: a una
   casilla sin `<!-- id: … -->` (se reconoce por su texto, que cambia), ¿se le pone un id al escribirla
   la primera vez?; y cuando el modelo cambie, ¿un campo `version` en cada archivo o un lector que entienda
   las dos formas?
3. **El agente como definición**: `agente.toml` en cada residente; el hilo guarda su agente, su
   conversación y su lugar por separado.
4. **Mensajes con modos y el Encargo**: `mensaje --modo aviso|pedido|encargo|consulta`, el objeto Encargo
   y la tabla de intenciones. Con eso se le puede encargar a un hilo de proyecto, no solo a un residente.
   Antes, las fallas del bus: los `nats: timeout`, el «Slow Consumer» del laptop, el registro del nodo que
   crece sin tope.
5. **El lugar y los worktrees**: `[lugar]` en el perfil; integrar y descartar como acciones del hilo.
6. **Vistas**: `[vistas]` reemplaza a `[secciones]`, `[bloques]`, `[apps]` y `[resultados]`, que se siguen
   leyendo un tiempo.
7. **Disparadores y estado deseado**: periódicos, teclas y «al cambiar» en `[disparadores]`; el nodo
   reconcilia residentes, periódicos y módulos.
8. **Permisos**: sujetos con permisos, la solicitud de permiso como objeto, los manifiestos con lo que piden.

**Las CLI sueltas** (aparte, junto al paso 2). El repo de vida tiene decenas de CLI propias; seis tocan
el correo y cuatro las tareas. Lo que se centraliza es la entrada y el contrato, no el código: un módulo
declara sus órdenes (`[ordenes]` en `modulo.toml`) y se llaman `telar <modulo> <verbo>`, como git encuentra
`git-lfs`; los adaptadores (`telar-tareas`, `telar-correo`, `telar-retro`) van a un módulo junto a su dato;
lo genérico (un proveedor de Gmail sin nada de nadie) puede vivir en `telar/modulos/`.

## Lo que queda abierto

- **Integrar al cerrar o a mano.** Solo es cómodo, pero mete lo que nadie revisó; a mano deja ramas que se
  alejan.
- **Los calientes por git o por el bus.** Por git sigue legible y es más lento; por el bus es inmediato y
  sale de git. Se parte por git con un escritor.
- **El nombre de la dirección.** `tarea:T366` para escribir, `telar://telar/tarea/T366` para enlazar.
