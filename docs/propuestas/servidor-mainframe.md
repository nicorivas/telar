# El servidor como mainframe: lo que falta

Estado: **en uso** (26-oct-2026). Pablo Ferreiro tiene su lugar en el servidor y entra, como todos, por la puerta
(`https://telar.tail22505a.ts.net`). Cómo es —el pedido por el bus, el ayudante de root, el secreto, la puerta— está
en [../arquitectura.md](../arquitectura.md), «El servidor como mainframe». Las pruebas cubren el protocolo, los
permisos, el plan del ayudante en seco (`pruebas/test_alojamiento.py`) y la puerta (`pruebas/test_puerta.py`). Falta
que Pablo la pruebe desde su laptop.

Nació de que Pablo Ferreiro quiere hilos en el servidor: hasta ahora darle un lugar era a mano (`telar persona
crear`, una llave ssh, un guion con sudo) y fuera del bus, así que no veía sus hilos del servidor desde su laptop como
los de cualquier otra máquina suya.

## Lo que no hace

- **Iniciar sesión en Claude.** Es de la persona, con su cuenta: la primera vez que abre un hilo en el servidor,
  Claude se lo pide en esa misma terminal.
- **Sus repositorios.** El lugar nace vacío; clonar el de su equipo lo hace ella (`telar instalar --unirse`, o git).
- **Abrir el puerto 22 en Tailscale**, si la red lo restringe: es de quien administra la red. La página ya no pide
  puertos: con la puerta (`telar.puerta`, desde la 0.7.0) todos entran por la dirección del servidor.
- **Crecer.** Con 8 GB (CX33), tres o cuatro alojados con tope de 2,5 GB se pelean la memoria; subir a CX43 antes.
  El tope por persona está en `alojamiento.MEMORIA` y `CPU`, y todavía no se elige al aprobar.
- **El flujo viejo** (`telar persona crear`, correo por cartero, remotos por ssh) sigue: es para quien no tiene bus.
  Cuando todos tengan nodo, se retira ([telar-para-otros.md](telar-para-otros.md)).
- **El aviso al dueño** cuando llega un pedido (la lista de máquinas lo muestra, pero nadie se entera sin mirar).

## Puesta en marcha

Instalar el ayudante de root, una vez, como en [`servidor/README.md`](../../servidor/README.md) («Alojar a otras
personas»); reiniciar el nodo del servidor y recargar el bus. Pablo ya tiene cuenta en el bus (`pabloferreiro`), así
que ese es su usuario Linux allá (el viejo `pablo` de la prueba de septiembre es otra cosa y no se toca). Desde su
laptop: `telar servidor pedir --llave ~/.ssh/id_ed25519.pub`; en el servidor, `telar servidor aprobar pabloferreiro`;
`telar servidor pedidos` dice cuándo termina, y en su laptop aparece la máquina `telar` en su cuenta. Su
`[bus] administra` tiene que ser `nico` (lo escribe `telar instalar --unirse`; si entró de otra forma, a mano).

## Lo que falta

1. Que Pablo pruebe la puerta desde su laptop: su página, no la de Nico, y la terminal. Lo demás de punta a punta ya
   se hizo con él (su usuario, su nodo en el bus, su telar detrás de la puerta).
2. El aviso de pedido nuevo, y elegir los topes al aprobar.
3. `telar doctor` en el servidor: que diga si el ayudante y la puerta están instalados, si la versión de la puerta
   va atrás de la de telar (se actualiza a mano: `servidor/telar-puerta-instalar`), y si cada alojado tiene su
   socket.
4. Un alojado que quiera migrar sus hilos de otra máquina: hoy nace de cero.
