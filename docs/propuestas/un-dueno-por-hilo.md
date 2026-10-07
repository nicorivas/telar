# Un dueño por hilo: cada máquina muestra, solo una manda

Propuesta, 7-oct-2026. Estado: **en parte construida**: una sesión por máquina y las vistas agrupadas
están hechas (ver «Hecho» al final); lo demás, por hacer.

## Por qué

Con dos máquinas (un laptop que se duerme y un servidor que no), cada hilo existe dos veces. La máquina
donde corre tiene su registro: nombre, vínculo, conversación, archivado, su ventana. La otra guarda una
copia de ese registro (`remotos.json`, vínculos, sesiones, archivados) y una ventana que es un cliente
conectado a la de allá. Cada cambio tiene que repetirse en el otro lado, y el que no se repite deja las
dos copias distintas.

Las fallas de una sola semana salen todas de esa forma:

1. **Dos copias que nada obliga a coincidir.** El laptop se entera por eventos («nació», «murió», «se
   renombró») y reacciona a cada uno. Un evento perdido, o que llega en mal orden, deja la copia
   distinta hasta que alguien la arregla a mano: un vínculo que no llegó, una ventana traída con el
   nombre de la sesión porque el nombre se puso tres segundos después.
2. **El hilo se identifica por su nombre, y el nombre cambia.** Un renombre se veía como un hilo que
   muere y otro que nace: el laptop cerró ventanas de hilos vivos.
3. **Dos clases de hilo en una misma máquina.** En el servidor, los que tenían sesión tmux propia se
   podían traer desde otra máquina; los tabs de la sesión del telar no. Lo que abría un agente
   (`telar pendiente`) nacía como tab y no aparecía en ninguna otra parte.
4. **La ventana local puede desviarse.** Es un cliente tmux enganchado allá; si termina mirando otra
   cosa, nadie se entera y la persona lee una conversación que no es.
5. **Los archivos los sincroniza git, a su ritmo.** Un vínculo apunta a una carpeta que en la otra
   máquina todavía no existe.

## La idea

**Cada hilo tiene un solo dueño: la máquina donde corre, sea el laptop o el servidor.** Las demás lo
muestran; ninguna lo copia.

### Una sesión por máquina; mirar es agruparse

En cada máquina, todo hilo es una ventana de **una sola sesión**, la del telar (`sesion` en la
configuración). Nada abre sesiones propias por hilo: ni los agentes, ni los periódicos, ni el celular,
ni la web, ni el laptop cuando abre un hilo en el servidor. Así hay una sola clase de hilo, y todo lo
que telar sabe de tabs (listar, renombrar, escribir, cerrar) vale en las dos máquinas.

Mirar un hilo desde afuera es engancharse a una **sesión agrupada** con la del telar, fija en su
ventana (`ver-<id>-<máquina>`; el celular, `movil-<id>`). Una agrupada comparte las ventanas pero elige
la suya: el laptop y el celular miran hilos distintos sin moverse uno al otro, que es lo que obligaba a
tener una sesión por hilo. Tres cosas la hacen confiable, todas probadas contra tmux 3.4 y 3.7:

- **No se mueve sola.** El tmux del servidor va sin prefijo ni barra: quien mira no puede cambiar de
  ventana con el teclado. telar apunta siempre a las ventanas con su sesión delante (`=telar:@3`): un
  `@3` a secas puede resolver a la sesión de quien mira y moverle la pantalla. Y no mueve al cliente
  de una vista (`switch-client`) aunque sea «el cliente actual».
- **Si algo la mueve, suelta.** Un gancho (`session-window-changed`) suelta a quien mira si su ventana
  deja de ser la actual; pasa sobre todo cuando la ventana muere. Mirar otro hilo creyendo que es el
  propio es peor que no mirar: la ventana local se cierra y el nodo la reabre si el hilo sigue vivo.
- **Una marca, no solo el `@N`.** Cada ventana-hilo lleva `@telar_id`; la dirección que se guarda es
  `@338/1a2b3c4d`. tmux reusa los `@N` al reiniciarse; con la marca, un `@N` reusado no se mira ni se
  cierra. `destroy-unattached` borra la vista cuando nadie la mira (puesto en el mismo `attach`: puesto
  antes, tmux la borra en el acto).

### El registro, en el bus

- **El registro completo vive en el bus**, en `TELAR_HILOS`: nombre, dirección, vínculo, atención,
  archivado, conversación. Cada máquina publica sus propios hilos, y solo esos.
- **Lo que una máquina muestra** es la unión de sus hilos (leídos aquí) y los de las demás, leídos del
  bus. No guarda registro propio de un hilo ajeno: ni vínculo, ni sesiones, ni archivado.
- **Los cambios van al dueño.** Renombrar, vincular, archivar o cerrar un hilo de otra máquina es un
  pedido por el bus (`rpc.<persona>.<maquina>.hilo`) que el dueño aplica y vuelve a publicar.
- **Las ventanas se reconcilian, no se reaccionan.** En cada vuelta del nodo: los hilos vivos de otras
  máquinas contra las ventanas abiertas aquí, por dirección. Se abre lo que falta, se cierra lo que
  sobra. Un evento perdido se corrige en la vuelta siguiente.

### La asimetría que queda

El servidor está siempre encendido; el laptop duerme. Con el laptop apagado sus hilos siguen en el bus,
marcados como inalcanzables: se ven, no se abren ni reciben en el momento (los mensajes esperan en la
casilla, como hoy). Lo que tiene que seguir corriendo —agentes residentes, periódicos— va en el
servidor. Es una regla de dónde poner las cosas, no del diseño. Mirar desde el servidor un hilo del
laptop también se podría (la misma vista agrupada, al revés), pero el laptop no siempre está para
recibir la conexión.

### Lo que no resuelve

Los archivos. Un vínculo a una carpeta que la otra máquina todavía no tiene seguirá sin ficha allá hasta
el próximo `git pull`. El registro puede decirlo («la carpeta no está aquí») en vez de fallar, pero
sincronizar el repositorio sigue siendo de git.

## Hecho (7-oct-2026)

- Todo hilo nuevo es una ventana de la sesión del telar (`movil.crear` con la sesión), marcada con
  `@telar_id`: encargos a un agente, periódicos, el celular, la web, y el laptop al abrir o retomar un
  hilo en el servidor (`remoto.crear_alla`, por ssh, que devuelve la dirección).
- La ventana local de un hilo remoto mira por una vista agrupada fija (`remoto.guion_ver`); el celular
  también (`movil.ordenes_grupo` con `ventana`).
- El nodo publica la dirección de cada ventana (`ventana`) y el de la otra máquina la sigue: trae lo
  que nace, sigue a un hilo que cambió de dirección (de sesión propia a ventana, o reabierto) en vez de
  traerlo como «· 2», y sigue un renombre hecho allá.
- `[agente] max_vivos` cuenta y cierra ventanas donde nadie mira la sesión del telar directo (un
  servidor); en el laptop no toca los tabs.
- `[remotos.<x>] sesion`: la sesión del telar allá, si se llama distinto que aquí.
- Las sesiones propias de antes se siguen viendo y mirando mientras existan.

## Por hacer

1. **Cambios al dueño.** Un verbo `hilo` por RPC para renombrar, vincular, archivar y cerrar; `telar
   hilo <verbo>` sobre un hilo ajeno lo usa en vez de tocar el estado local.
2. **Reconciliar en cada vuelta**, no solo cuando cambia lo publicado: hoy el nodo reacciona a cada
   cambio del bus; una ventana que se cerró sin cambio allá espera al próximo.
3. **Dejar de copiar.** Con 1 y 2 andando, el laptop deja de guardar vínculos, sesiones y archivados de
   los hilos ajenos; la lista y el dashboard los leen del bus.
4. **Quitar las sesiones propias** del código cuando no quede ninguna.
