# Un dueño por hilo: cada máquina muestra, solo una manda

Estado: **casi construida**. Una sesión por máquina, las vistas agrupadas y la dirección marcada de
cada ventana ya son como funciona telar ([arquitectura](../arquitectura.md), «Los hilos y tmux»), y el
registro de un hilo (vínculo, archivo, conversación) vive en su dueño y las otras máquinas lo leen del
bus. Las sesiones propias de antes ya no existen en el código (paso 2, 22-oct-2026).

## Por qué

Con dos máquinas, la que no tiene el hilo guarda una copia de su registro (`remotos.json`, vínculos,
sesiones, archivados) y la mantiene al día reaccionando a eventos del bus («nació», «murió», «se
renombró»). Un evento perdido o fuera de orden deja la copia distinta hasta que alguien la arregla a
mano: un vínculo que no llegó, una ventana traída con el nombre equivocado.

## La idea

**Cada hilo tiene un solo dueño: la máquina donde corre.** Las demás lo muestran; ninguna lo copia.

- **El registro completo vive en el bus** (`TELAR_HILOS`): nombre, dirección, vínculo, atención,
  archivado, conversación. Cada máquina publica los suyos, y solo esos.
- **Lo que una máquina muestra** es la unión de sus hilos y los del bus, sin registro propio de un hilo
  ajeno.
- **Los cambios van al dueño.** Renombrar, vincular, archivar o cerrar un hilo de otra máquina es un
  pedido (`rpc.<persona>.<maquina>.hilo`) que el dueño aplica y vuelve a publicar.
- **Las ventanas se reconcilian, no se reaccionan.** En cada vuelta del nodo, los hilos vivos de otras
  máquinas contra las ventanas abiertas aquí: se abre lo que falta, se cierra lo que sobra.

Con el laptop apagado, sus hilos siguen en el bus como inalcanzables: se ven, no se abren, y los
mensajes esperan en la casilla. Lo que tiene que seguir corriendo va en el servidor.

No resuelve los archivos: un vínculo a una carpeta que la otra máquina todavía no tiene sigue sin ficha
hasta el próximo pull. El registro puede decirlo («la carpeta no está aquí») en vez de fallar.

## Los pasos que faltan

Hechos: los cambios a un hilo ajeno los aplica su dueño (`telar hilo` se los pide por el bus, pedido `hilo`
a su nodo, y solo si allá sale bien ajusta lo de aquí), y el nodo concilia en cada vuelta de la foto (30 s)
las ventanas de aquí contra el estado de los hilos de las otras máquinas.

1. ~~**Dejar de copiar**~~ (hecho): la máquina deja de guardar vínculos, sesiones y archivados de los hilos
   ajenos; la lista y el dashboard los leen del bus.

   Cómo quedó:

   - El dueño publica en `TELAR_HILOS`, además de la conversación que ya iba, `vinculo` (relativo a la
     raíz, "" sin carpeta) y `archivado`. Un hilo ya publicado como muerto se vuelve a publicar si se
     archiva o se vincula después, salvo que otra máquina ya lo publique (se mudó).
   - El nodo de cada máquina deja lo último que publicó cada hilo de las otras en `ajenos.json`, entero
     y reemplazado en cada cambio: es la foto del bus en disco, no una copia que se parcha con eventos.
     Guarda solo lo que se lee de ahí (máquina, conversación, vínculo, archivado), así que un cambio de
     atención no lo reescribe, y lo escribe recién cuando el bus terminó de entregarle lo que había al
     arrancar: antes quedaría con una parte de los hilos. Mientras vigila el bus lo refresca cada 30 s; si
     pasan dos minutos sin que lo toque (el nodo apagado, sin `[bus]`), caduca y no se lee.
   - `Estado.vinculos()`, `archivados()` y `sesiones()` toman de ahí lo de un hilo ajeno, así que la
     lista, la página, `telar proyectos`, `retomar` y el nodo leen lo del dueño sin cambiar nada más. La
     conversación del dueño va primera en `sesiones`, y las anteriores que se sabían aquí siguen detrás. Un
     vínculo que sube con `..` no se toma.
     Ajeno es el hilo que tiene ventana o dirección aquí (`remotos.json`) **y** cuyo dueño, según el bus,
     es otra máquina: un hilo de aquí que se llama igual que uno de allá no toma lo de aquel.
   - `telar hilo vincular|desvincular|archivar|desarchivar` de un hilo ajeno se lo pide al dueño. Si allá
     sale bien, anota el cambio en `ajenos.json` (lo que el nodo recoja después lo reemplaza), para que la
     respuesta y la página lo muestren ya, y escribe también la copia de aquí. `retomar` le pide
     `desarchivar` si estaba archivado. `conciliar` usa el `archivado` del dueño, y «revivir» también,
     salvo para un hilo que aquí se llama distinto («Faro · 2»), que no cruza con lo que publica y sigue con
     su copia.
   - Compatibilidad: mientras el dueño no publique un campo (un telar de antes allá, sin bus, o con el nodo
     de aquí apagado y `ajenos.json` caducado), vale la copia de aquí; en cuanto lo publica, gana el dueño.
     Por eso la copia se sigue escribiendo cuando el dueño acepta un cambio: no se lee mientras él publica,
     y es lo que vale cuando deja de publicar, o cuando el hilo vuelve a esta máquina (lo que se cambió
     allá directamente, sin pasar por aquí, no llega a esta copia, como antes). Sin bus, todo funciona como
     antes (los hilos remotos por ssh siguen guardando su registro aquí).

   Lo que sigue copiándose, a propósito: la **prioridad** (no estaba en este paso; va al dueño y se anota
   aquí, y la foto del espejo la trae), la **atención** (el nodo la anota al instante para el semáforo), y
   la conversación que se anota al abrir un hilo nuevo allá desde aquí (`telar ir --remoto`), que sirve de
   respaldo hasta que el dueño la publique y entonces queda sin uso. `desarchivar` de un hilo ajeno desde
   otros caminos (llevarle un pendiente) toca solo la copia de aquí: si allá estaba archivado, se
   desarchiva cuando su agente vuelve a trabajar, como cualquier hilo.

2. ~~**Quitar las sesiones propias por hilo**~~ (hecho, 22-oct-2026): telar ya no abre, lista, mira ni
   escribe a una sesión tmux propia por hilo (`telar-…` con `@telar_hilo`); todo hilo es una ventana de la
   sesión del telar con su dirección `@ventana/marca`. Se fueron `movil.propios`, `hilo_de_panel`,
   `ordenes_nuevo`, `escribir` y la rama sin `principal` de `movil.crear`; `Telar.propios`/`propio` (y el campo
   `propio` del JSON de un hilo); `_cerrar_sesion`; `sesion_tmux` en lo que publica el nodo; `remoto.sesion_nueva`
   y las ramas de `remoto.comando`, `vive`, `matar` y `nombrar` para direcciones sin `@`; y la revisión
   `sesiones` de `telar doctor`, que fue la que dijo cuándo era seguro: dio `ok` en las dos máquinas, después de
   dejar sin dirección los tres hilos que el laptop todavía anotaba con una de antes. Una dirección que no es
   `@ventana/marca` (vacía, o una de antes en un `remotos.json` viejo) cuenta como hilo muerto allá: abrirlo
   abre una ventana nueva.
