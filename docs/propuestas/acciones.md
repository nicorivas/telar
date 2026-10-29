# Acciones sobre una entidad: un menú, y «Acción…»

Estado: **el menú y «Acción…», hechos** (28-oct-2026, sin publicar): el menú junto al puntero para hilos, proyectos,
tareas y pendientes, con clic derecho y con su ⋯ (`menu` en `web/interfaz.ts`, y `web/entidades.ts`), y desde un
lienzo (`window.lienzo.pedir("menu")`: el Gantt). Decidido: un solo menú para toda entidad, abierto
con clic derecho (o su ⋯) donde está; «Acción…» manda a un hilo un prompt con el contexto de la entidad, con una
skill o sin ella; se manda solo a otro hilo o a un agente, y se deja escrito si el destino es el hilo que se está
mirando; las secciones van en el orden contexto, skill, hilo, con el destino ya elegido.

## Por qué

Hoy hay tres menús que hacen lo mismo de tres maneras: el de un hilo (el ⋯ de su fila en la barra), el de un
proyecto (el ⋯ de su fila en «proyectos») y el de una tarea (el ⋯ de su fila en «tareas»). Los tres abren una caja
con un buscador en el centro de la pantalla, lejos de donde se hizo clic, y cada uno arma sus acciones a mano. Y no
hay una manera de decir «haz esto con esta cosa» a un agente sin escribir a mano de qué cosa se habla.

Toda entidad ya tiene una dirección (`proyecto:operacion/faro`, `hilo:Faro`, `tarea:T84`) y `telar objeto` ya
lista lo que se puede hacer con cada tipo. El menú es eso, en la pantalla, donde está la entidad.

## El menú

Un solo componente (`web/menu.ts`): un menú junto al puntero (clic derecho) o bajo el ⋯ que se apretó, con
↑ ↓ ⏎ ⎋ y escribir para filtrar. Recibe una dirección y arma sus ítems en tres capas:

1. **Lo de la página** para ese tipo: abrir, ir a su hilo, copiar la dirección… (`web/entidades.ts`: cada tipo
   registra las suyas).
2. **Las acciones del tipo** que da el servidor (`GET /objetos/<dirección>`): las de un tipo de un módulo llegan
   solas.
3. **«Acción…»**, arriba, para todo tipo (paso 2).

Lo usan la barra de hilos, la lista de proyectos, las tareas, y el Gantt (el lienzo de un módulo pide el menú de
una entidad con `window.lienzo.pedir("menu", {direccion})`, que no pide permiso porque solo muestra: lo que se
elige, se elige en la página).

## «Acción…»

Un panel con tres secciones, de arriba abajo:

1. **Contexto**: lo que `telar objeto` sabe de la entidad (título, estado, campos, su documento, su hilo), y una
   caja para escribir qué se quiere.
2. **Skill** (opcional): un buscador de las skills del agente del destino (`GET /skills`); primero las que más se han
   usado con ese tipo. Sin skill, va el prompt solo.
3. **Agente o hilo**: un buscador, con una lista ya armada: el hilo de la entidad (si tiene), «un hilo nuevo para
   ella», los agentes residentes y los hilos recientes. Viene elegido el de la entidad, para que la lista de skills
   sea la correcta desde el comienzo; cambiarlo la actualiza.

**Ejecutar** arma el prompt (la skill si hay, el contexto como la dirección de la entidad y lo que se escribió) y lo
manda: a un agente con `telar encargar`, a un hilo nuevo con `telar proyectos abrir`, a otro hilo por su casilla. Si
el destino es el hilo que se está mirando, se deja escrito en su entrada y no se manda. La orden es
`telar actuar <dirección> [--skill X] [--a <hilo|agente>] [--nota …] [--escribir]` (y `POST /actuar`), para que un agente también
pueda; la plantilla del prompt se puede cambiar en la configuración.

## Los pasos

1. **Lo demás:** la plantilla del prompt en la configuración; detectar que el destino es el hilo que se está mirando
   (hoy, «dejarlo escrito, sin mandar» es una casilla); recordar la última skill y el último destino por tipo; agentes y archivos; actuar sobre lo que se
   encuentra con ⌘K.
