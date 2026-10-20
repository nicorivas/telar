# Un dueño por hilo: cada máquina muestra, solo una manda

Estado: **en parte construida**. Una sesión por máquina, las vistas agrupadas y la dirección marcada de
cada ventana ya son como funciona telar ([arquitectura](../arquitectura.md), «Los hilos y tmux»). Falta
que el registro de un hilo viva en un solo lugar.

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

1. **Cambios al dueño**: un verbo `hilo` por RPC para renombrar, vincular, archivar y cerrar; `telar hilo
   <verbo>` sobre un hilo ajeno lo usa en vez de tocar el estado local.
2. **Reconciliar en cada vuelta**, no solo cuando cambia lo publicado.
3. **Dejar de copiar**: la máquina deja de guardar vínculos, sesiones y archivados de los hilos ajenos;
   la lista y el dashboard los leen del bus.
4. **Quitar las sesiones propias por hilo** del código, cuando no quede ninguna.
