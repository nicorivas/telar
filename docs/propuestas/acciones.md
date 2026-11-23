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
3. **«instrucción…»**, arriba, para todo tipo ([instruccion.md](instruccion.md)).

Lo usan la barra de hilos, la lista de proyectos, las tareas, y el Gantt (el lienzo de un módulo pide el menú de
una entidad con `window.lienzo.pedir("menu", {direccion})`, que no pide permiso porque solo muestra: lo que se
elige, se elige en la página). Para abrirla, sin menú, `window.lienzo.pedir("abrir", {direccion})`: lo mismo que un
clic en un enlace a esa dirección, y tampoco pide permiso.

## «instrucción…»

Lo que era «Acción…»: mandarle a un hilo o a un agente algo sobre la entidad, con su contexto. Desde el 13-nov-2026 es
la ventana «instrucción», la misma de foco, de la ficha de una tarea y de encargarle a un agente; su diseño y lo que
falta están en [instruccion.md](instruccion.md).

## Los pasos

1. **Lo demás:** actuar sobre lo que se encuentra con ⌘K. Lo de la instrucción (la plantilla del prompt, recordar la
   última skill y el último destino), en [instruccion.md](instruccion.md).
