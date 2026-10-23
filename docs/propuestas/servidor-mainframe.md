# El servidor como mainframe: lo que falta

Estado: **construida, sin probar en el servidor real** (23-oct-2026). Cómo es —el pedido por el bus, el ayudante de
root, el secreto, los puertos— está en [../arquitectura.md](../arquitectura.md), «El servidor como mainframe». Las
pruebas cubren el protocolo, los permisos y el plan del ayudante en seco (`pruebas/test_alojamiento.py`); lo que no se
pudo ejercitar sin crear un usuario de verdad es el script de instalación de `servidor/telar-alojar`.

Nació de que Pablo Ferreiro quiere hilos en el servidor: hasta ahora darle un lugar era a mano (`telar persona
crear`, una llave ssh, un guion con sudo) y fuera del bus, así que no veía sus hilos del servidor desde su laptop como
los de cualquier otra máquina suya.

## Lo que no hace

- **Iniciar sesión en Claude.** Es de la persona, con su cuenta: la primera vez que abre un hilo en el servidor,
  Claude se lo pide en esa misma terminal.
- **Sus repositorios.** El lugar nace vacío; clonar el de su equipo lo hace ella (`telar instalar --unirse`, o git).
- **Abrir el puerto 22 en Tailscale**, si la red lo restringe, y los puertos 8781+ para su página: es de quien
  administra la red.
- **Crecer.** Con 8 GB (CX33), tres o cuatro alojados con tope de 2,5 GB se pelean la memoria; subir a CX43 antes.
  El tope por persona está en `alojamiento.MEMORIA` y `CPU`, y todavía no se elige al aprobar.
- **El flujo viejo** (`telar persona crear`, correo por cartero, remotos por ssh) sigue: es para quien no tiene bus.
  Cuando todos tengan nodo, se retira ([telar-para-otros.md](telar-para-otros.md)).
- **Un botón en la página.** Hoy es la CLI (`telar servidor`); falta la sección en ⚙ junto a «personas», y el aviso
  al dueño cuando llega un pedido.

## Puesta en marcha

Instalar el ayudante de root, una vez, como en [`servidor/README.md`](../../servidor/README.md) («Alojar a otras
personas»); reiniciar el nodo del servidor y recargar el bus. Pablo ya tiene cuenta en el bus (`pabloferreiro`), así
que ese es su usuario Linux allá (el viejo `pablo` de la prueba de septiembre es otra cosa y no se toca). Desde su
laptop: `telar servidor pedir --llave ~/.ssh/id_ed25519.pub`; en el servidor, `telar servidor aprobar pabloferreiro`;
`telar servidor pedidos` dice cuándo termina, y en su laptop aparece la máquina `telar` en su cuenta. Su
`[bus] administra` tiene que ser `nico` (lo escribe `telar instalar --unirse`; si entró de otra forma, a mano).

## Lo que falta

1. Probarlo de punta a punta con un alojado real (Pablo), y ajustar el script de instalación a lo que salga: es lo
   único que no se pudo ejercitar sin crear un usuario de verdad.
2. La sección en la página, el aviso de pedido nuevo, y elegir los topes al aprobar.
3. `telar doctor`: que el servidor diga si el ayudante está instalado y su carpeta de pedidos bien puesta.
4. Un alojado que quiera migrar sus hilos de otra máquina: hoy nace de cero.
