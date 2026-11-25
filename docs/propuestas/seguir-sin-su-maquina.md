# Seguir un hilo en otra máquina cuando la suya está apagada

Estado: **se funde en [mudanza-de-hilos.md](mudanza-de-hilos.md)**, que reemplaza sus tres decisiones (24-nov-2026):
el respaldo continuo de su paso 1 no se hace (la persona dijo que no), y «seguir aquí» y la vuelta son la etapa 4 de
aquella, desde la última copia que quedó en cada máquina, **hecha** (telar.seguir; [arquitectura](../arquitectura.md),
«Seguir aquí con la dueña apagada»). Lo de abajo queda como el porqué y el caso. Lo que ya existe
y en qué se apoya: despertar o escribirle a un hilo de una máquina fuera de línea queda en cola y se hace al volver
(telar.alcance, [arquitectura](../arquitectura.md), «Una máquina fuera de línea»); llevar un hilo a otra máquina por
el bus (`telar hilo llevar`, telar.mudanza) necesita que la de origen esté en línea, porque su conversación vive
allá.

## Por qué

El caso: hilo:Catedral@laptop. El laptop quedó apagado o sin red dos horas, y la persona, desde el teléfono, quería que
Catedral siguiera («No tengo acceso a Laptop, ese es el punto»). Hoy se puede ver que el laptop no está, dejarle un
mensaje y pedir que despierte cuando vuelva. Lo que no se puede es **seguir ahora**, en el servidor: su
conversación (`~/.claude/projects/<carpeta>/<id>.jsonl`) está solo en el disco del laptop.

## La idea, en los pasos que faltan

No reemplaza nada: es la mudanza (telar.mudanza) cuando la máquina de origen no está, con la conversación sacada de un
respaldo en vez de pedírsela a ella. El paso 1 deja todo funcionando solo (un respaldo que nadie usa todavía); el 2 y el
3 van juntos, porque seguir en otra máquina sin la vuelta dejaría dos dueños cuando el laptop vuelva.

1. **Un respaldo de la conversación de cada hilo en el servidor, al día por turno.** El nodo de cada máquina, en su
   vuelta (no el gancho `Stop`, que tiene que ser liviano), mira la conversación de sus hilos vivos: si creció desde
   el último respaldo, le manda al servidor solo lo nuevo (`<id>`, desde qué byte, la huella sha256 de lo anterior y
   los bytes que siguen, comprimidos), por un pedido nuevo del bus, `respaldo`. El servidor lo agrega a su copia
   (`<estado>/respaldos/<máquina>/<id>.jsonl`) si la huella calza; si no calza (la conversación se reescribió, una
   compactación, un `/clear` que empezó otra), pide la entera. Con tope: una conversación de más de 25 MB comprimida
   no se respalda (y se dice), y el total por máquina tiene su tope, con lo más viejo afuera primero. Lo que no se
   tocó en 14 días se borra.
2. **«Seguir aquí»**, en el servidor, para un hilo inalcanzable con respaldo: la página lo ofrece en el cuadro de la
   máquina fuera de línea (el botón va junto a «despertar al volver», `panelFuera`, con la forma de la casa) y la
   orden es `telar hilo seguir <hilo>`. Hace lo mismo que la llegada de una mudanza (`mudanza.llegar`): deja la copia
   donde Claude Code la busca, en la carpeta del hilo en el repositorio del servidor, y lo abre retomándola. Antes de
   abrirlo dice lo que no viaja: **lo sin commitear del laptop no está aquí**, ni lo que el laptop hizo después del
   último respaldo (la hora del último, en la misma pregunta), ni lo que corría de fondo allá (Catedral tiene su
   `npm run dev`). El hilo pasa a vivir en el servidor y lo publica él, con una marca: `tomado_de: laptop` y desde
   cuándo.
3. **La vuelta del laptop.** Su nodo, al reconectar, ve que un hilo suyo lo publica otra máquina con `tomado_de` la
   suya: no lo vuelve a publicar (dos dueños se pisarían el estado), duerme a su agente de aquí y deja su ventana
   como vista del de allá, igual que después de `telar hilo llevar`. Su conversación de aquí, si siguió por su lado
   (alguien trabajó en el laptop sin red), queda aparte con su fecha, como hace hoy la llegada de una mudanza, y se
   dice. Nada se borra en el laptop sin su nodo: todo esto lo hace el nodo del laptop, en el laptop.

## Lo que cuesta

- **Construirlo**: el respaldo por partes con su huella, el pedido `respaldo` con trozos (el de `telar.entrega`
  sirve de molde) y los topes, alrededor de un día con sus pruebas. «Seguir aquí» reusa la llegada de una mudanza:
  medio día. La vuelta del laptop es lo delicado: que el nodo ceda un hilo vivo a otra máquina sin que el estado
  parpadee entre las dos, un día más, con pruebas de dos nodos y un tmux de verdad.
- **El bus y la red**: por turno viaja solo lo nuevo (unos KB; un turno con una herramienta que leyó un archivo grande,
  algo más). Por el hotspot del teléfono sigue siendo poco, pero se mide antes de prenderlo para todos.
- **El disco del servidor**: con los topes de arriba, cientos de MB como mucho.
- **La privacidad, que no es técnica.** Una conversación trae todo lo que el agente leyó y escribió: datos de
  clientes, finanzas, lo privado de la memoria. Hoy eso vive solo en el laptop; con esto, también en el servidor (una
  máquina de la persona, en su cuenta, pero en un centro de datos). **Eso lo decide la persona**, y conviene que se
  pueda elegir qué se respalda: por hilo, por etiqueta o por mundo (`[respaldo] mundos = ["trabajo"]`), con nada por
  defecto.

No se construye todavía por dos cosas: la vuelta del laptop toca la regla de un dueño por hilo, y copiar
conversaciones al servidor es una decisión de privacidad que no es de un hilo.

## Lo que falta decidir

1. Si se respalda, y qué: todo, nada por defecto con lista de lo que sí, o por mundo.
2. Si «seguir aquí» se ofrece solo en el servidor o en cualquier máquina en línea (el laptop siguiendo un hilo del
   servidor caído no tiene respaldo de dónde sacarlo: el servidor es quien guarda).
3. Al volver el laptop, si su ventana pasa a mirar el del servidor (como tras una mudanza) o se le pregunta a la
   persona dónde sigue.
