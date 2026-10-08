# Contratos

Las formas que telar se pasa entre piezas, escritas para que alguien de afuera las
pueda cumplir. Si un programa devuelve esto, telar lo teje sin saber nada de él.

Hay dos: el **estado de un hilo**, que es lo que telar espera de quien sepa leer un
documento, y **[lo que la CLI imprime con `--json`](#la-cli)**, que es lo que telar
le promete a quien lo consuma.

## El estado de un hilo

Un hilo es una unidad de trabajo viva, y su documento —normalmente un `README.md`—
dice cómo va. Quien sepa decirlo es un *proveedor de estado*
(`telar.proveedores.estado`), y todos devuelven el mismo objeto:

```json
{
  "titulo":  "Faro",
  "resumen": "La lámpara nueva llegó y está montada; falta el ajuste del giro.",
  "campos":  { "Encargo": "Municipalidad de la costa", "Entrega": "2026-06-30" },
  "pendientes": [
    { "texto": "Desmontar la lámpara vieja", "hecho": true,  "en_curso": false, "id": "", "origen": "pendientes" },
    { "texto": "Ajustar la velocidad de giro", "hecho": false, "en_curso": true, "id": "", "origen": "pendientes" }
  ],
  "esperando": [
    { "texto": "El electricista confirma si el motor viejo sirve", "cuando": null, "origen": "esperando" }
  ],
  "hitos":   [ { "que": "Entrega", "cuando": "2026-06-30", "origen": "campos" } ],
  "enlaces": [ { "texto": "el informe", "destino": "informes/2026-06.pdf", "origen": "" } ],

  "documento": "proyectos/faro/README.md",
  "leido":     "2026-06-01T09:12:44",
  "nota":      "",
  "faltan":    []
}
```

### Los siete campos

| Campo | Forma | Qué es |
|---|---|---|
| `titulo` | texto | cómo se llama el hilo. Vacío se permite; telar usa entonces el nombre del tab. |
| `resumen` | texto | **una** línea: cómo va la cosa. Es lo que se ve bajo cada hilo en la barra. |
| `campos` | objeto texto → texto | la ficha: cliente, etapa, precio, lo que el repositorio lleve. telar no interpreta las claves. |
| `pendientes` | lista | lo que queda por hacer, en orden del documento. |
| `esperando` | lista | lo que el hilo no puede mover porque depende de otro. |
| `hitos` | lista | fechas con nombre, de la más próxima a la más lejana. |
| `enlaces` | lista | adónde lleva el documento, sin repetir destinos. |

Un `pendiente` lleva `texto`, `hecho`, `en_curso`, `id` (estable, si vino de un
gestor de tareas; vacío si salió del texto) y `origen` (de qué sección). Una espera
lleva `texto`, `cuando` (`AAAA-MM-DD` o `null`) y `origen`. Un hito lleva `que`,
`cuando` y `origen`. Un enlace lleva `texto`, `destino` y `origen`.

Todos los campos son opcionales: lo que no esté vale por su vacío. Lo que **sí**
esté tiene que tener esta forma, o telar se queja en vez de adivinar. Una clave que
no esté en esta página se ignora, para que un programa pueda llevar cosas suyas.

### Los cuatro de procedencia

No son parte del contrato —un proveedor externo puede no ponerlos— pero telar los
llena cuando lee él:

| Campo | Qué es |
|---|---|
| `documento` | de qué archivo salió |
| `leido` | cuándo, en ISO, para saber si el estado está rancio |
| `nota` | por qué salió flaco, en una frase legible |
| `faltan` | las secciones que el arquetipo declaraba `requerida` y no estaban |

Un documento que no existe no es una falla: es un hilo sin cara. Vuelve un estado
vacío con la razón en `nota`, y el telar sigue.

## El proveedor `documento`

Lee el markdown del hilo. Es el de siempre, y no hace falta declararlo: leer un
archivo del repositorio que el usuario ya señaló no es salir al mundo.

**No sabe dónde está nada.** Qué sección es el estado, cuál trae los pendientes, qué
tabla son los campos: todo sale del [perfil del repositorio](perfil.md). Lo único
que da por sabido es el markdown.

El trabajo se reparte en dos: `telar.lectura` cumple lo que el perfil declaró y
devuelve cada sección con su tipo; este proveedor decide qué significa cada sección
para el estado de un hilo. Por eso una sección se ancla en un **encabezado** y no en
cualquier línea: eso lo fija el perfil, no esta página.

### La cascada

Cada campo del contrato tiene una lista de **orígenes** y se toma el primero que dé
algo. Un origen es el nombre de una sección del perfil, o `campo:Clave` para una fila
de la tabla de campos.

Así se lee igual un README que pone el estado en un párrafo, otro que lo pone en una
fila (`| Etapa | Descubrimiento |`) y otro que no lo pone en ninguna parte:

```toml
[ficha]
cascada.resumen = ["estado", "situacion", "campo:Etapa", "campo:Fase"]
cascada.pendientes = ["pendientes", "proximos_pasos"]
```

`[ficha]` es su propia sección, no una fila de `[proveedores.*]`: aquellos traen ítems
del día (agenda, tareas) y este responde por un documento. `proveedor` elige cuál —
`documento` por defecto, `comando` para salir afuera — y el resto de las claves son sus
opciones.

Los campos singulares (`titulo`, `resumen`) se quedan con el primer origen que dé
algo; los plurales (`campos`, `pendientes`, `esperando`, `hitos`) suman todos sus
orígenes, en orden, sin repetir. `enlaces` no se gobierna por cascada: un enlace no
tiene sección, sale del documento entero.

Sin `cascada` declarada, se arma sola con lo que el arquetipo declaró:

| Campo | De dónde sale por defecto |
|---|---|
| `titulo` | la sección `titulo`; si no hay, el nombre de la carpeta (o del archivo) |
| `resumen` | la sección `estado`; después las demás de tipo `parrafo`, `linea` o `texto` |
| `campos` | todas las secciones de tipo `tabla`, y después el front matter |
| `pendientes` | la sección `pendientes`; después las demás de tipo `casillas` y `lista` |
| `esperando` | la sección llamada `esperando`, si el perfil la declara |
| `hitos` | la sección llamada `hitos`, más los `campos` cuyo valor trae fecha |

Los tres primeros nombres son [los que telar entiende](perfil.md#los-tres-nombres-que-telar-entiende).
Que `esperando` y `hitos` signifiquen algo es la única licencia que se toma este
proveedor, y la configuración la puede desarmar entera nombrando otras secciones.

### Las marcas

`hecho` y `en_curso` salen de la casilla, con lo que el perfil ya define para el tipo
`casillas`: `[x]` hecha, `[>]` en curso. Un repositorio que **además** marque en el
texto lo declara:

```toml
[proveedores.estado]
marcas.hecho = ["✅"]
marcas.en_curso = ["⏳", "▶"]
```

Lo declarado se suma a la casilla, no la reemplaza, y se saca del texto: `- [ ] ⏳
Ajustar el giro` queda en curso y se llama «Ajustar el giro». Sin declararlo, ese
emoji es texto y nada más. Como prefijo solo valen las marcas que no son ASCII: si
valiera la `x`, una viñeta que empieza con «xilófonos» quedaría hecha.

Lo marcado como hecho sale de `pendientes` con su bandera, pero **no** entra a
`esperando` ni a `hitos`: una espera cumplida ya no es una espera.

### Las fechas

`AAAA-MM-DD`, `DD-MM-AAAA` y `DD-mes` con el mes en tres letras (`meses` en las
opciones cambia el idioma). Un `DD-mes` sin año se resuelve con el año en curso, que
es una suposición: en diciembre, un «5-ene» quiere decir el próximo y esto va a
decir que es el de este año.

### Las otras opciones

| Opción | Por defecto | Qué hace |
|---|---|---|
| `cascada` | la de arriba | mapa campo → orígenes; pisa entero el campo que nombre |
| `marcas` | `[x]`, `[>]` | qué más cuenta como hecho o en curso |
| `maximo` | `0` (sin tope) | tope de elementos por campo |
| `meses` | es/en | mapa de tres letras → número |

## El proveedor `comando`

Corre un programa y lee de su salida estándar el JSON de arriba. Es la puerta para
todo lo que telar no sabe leer: un gestor de tareas, una base de datos, un documento
que no es markdown.

```toml
[ficha]
proveedor = "comando"
comando = ["scripts/estado.py", "{documento}"]
tiempo = 10
```

* `comando` es una **lista de palabras**, nunca una línea de shell. Si de verdad
  hace falta una, se pide explícita: `["sh", "-c", "…"]`, a la vista. Igual que las
  acciones del perfil, y por lo mismo.
* Marcadores que se reemplazan en cada palabra: `{documento}`, `{ruta}` (la carpeta
  del hilo), `{hilo}` (su nombre), `{arquetipo}`.
* Corre con la carpeta del hilo por `cwd`, sin shell.
* Salir con algo que no es cero, no responder en `tiempo` segundos o imprimir algo
  que no es el JSON del contrato son `ErrorDeProveedor`, con lo último que haya
  dicho el programa. El telar sigue sin ese hilo; no se cae.
* Lo que imprima por el error estándar no se interpreta: solo se cita si falla.

Un programa mínimo que cumple el contrato:

```python
#!/usr/bin/env python3
import json, sys
print(json.dumps({
    "titulo": "Faro",
    "resumen": "montada la lámpara, falta el giro",
    "pendientes": [{"texto": "Ajustar la velocidad de giro", "en_curso": True}],
}))
```

## En Python

```python
from telar.proveedores import estado

e = estado.leer(documento, arquetipo)   # el proveedor `documento`, sin configurar
e.a_dict()                              # la forma JSON de esta página
e.a_ficha()                             # la misma cosa en el vocabulario de telar.modelo
estado.Estado.desde_dict(crudo)         # de vuelta, validando

estado.obtener(cfg)                     # el proveedor que la configuración declare
estado.Documento().desde_texto(texto, arquetipo)   # sin volver al disco
```

`a_ficha()` existe porque el resto de telar habla de `telar.modelo.Ficha`: el
`resumen` pasa a ser el `estado` de la ficha, y lo que no tiene lugar propio ahí
—campos, esperas, hitos, enlaces— viaja en `secciones`, ya en JSON, para que quien
dibuje no tenga que conocer estas clases.

# La CLI

Cada orden con `--json` imprime **una sola línea** de JSON en la salida estándar y
nada más: ni color, ni avisos, ni una línea de cortesía. Es lo que consume una
barra de estado, una vista de editor u otro agente, y por eso está escrito aquí y
no en el `--help` de cada una.

Las reglas valen para todas:

* **Una línea, un objeto.** Siempre un objeto en la raíz, nunca una lista suelta:
  así se le pueden agregar claves sin romper a nadie.
* **Los errores no salen por ahí.** Van al error estándar, en prosa, y la orden
  sale con 2. Una salida vacía y un 2 significan «no hay JSON que darte».
* **Agregar claves es normal; cambiar las de aquí, no.** Un consumidor debe
  ignorar lo que no conozca.
* **Rutas**: `ruta` es absoluta (sirve para `cd`), `relativa` es relativa a la raíz
  del repositorio (sirve para mostrar). Vacío, no `null`, cuando no hay.
* **Tiempos**: siempre **segundos** (número), nunca minutos ni «1h20».
* **Fechas**: ISO de la máquina, sin zona (`2026-09-18T09:12:44`), porque son un
  registro local. `null` cuando no se sabe.
* **Atención**: una de `ninguna`, `trabajando`, `espera`, `termino`.
* **Prioridad**: `1` alta, `2`, `3` baja, o `null` si no tiene.
* **Codificación**: los caracteres van tal cual mientras la salida los admita. Si
  no (una consola en cp1252, un `PYTHONIOENCODING` ajeno), la misma línea sale con
  escapes `\uXXXX`: es JSON válido y, al decodificarlo, el texto es idéntico. El
  JSON nunca se translitera; lo que telar dibuja para una persona, sí.

## Las piezas que se repiten

### `hilo`

```json
{
  "id": "@3", "nombre": "faro", "vivo": true, "propio": false, "activo": false,
  "archivado": false, "vinculado": true,
  "ruta": "/casa/trabajo/proyectos/faro", "relativa": "proyectos/faro",
  "arquetipo": "proyecto", "prioridad": 2, "atencion": "espera",
  "visto": "2026-09-18T09:12:44", "tiempo": 4320.0,
  "sesiones": ["a1b2c3d4"], "remoto": "",
  "ficha": { … }
}
```

`id` es la llave del multiplexor (`@3` en tmux y el id del tab en zellij, estables mientras la sesión viva) y es lo
que reciben las órdenes. `nombre` es lo que se muestra **y la llave del estado**:
el id se corre cuando alguien abre un tab al principio, el nombre no. `vivo` dice
si el multiplexor lo está mostrando ahora; un hilo archivado, o uno de una sesión
que todavía no se levanta, aparece con `vivo: false` en vez de desaparecer. `propio` es `true`
para un hilo que no es tab del multiplexor pero vive en una sesión tmux propia de esta máquina (los
que abre el celular con `telar movil` y los periódicos): `vivo` sigue siendo `false` —`ir`, `cerrar`
y el resto operan sobre tabs—, pero se le puede escribir con `enviar`.
`tiempo` son los segundos con el foco **en el día en curso**. `ficha` puede ser
`null` (con `--sin-ficha`) o faltar. `remoto` dice dónde vive el agente del hilo: `""`
es aquí, un nombre es una máquina de `[remotos]`, y `"?"` es una ventana que corre mosh,
ssh o et sin que telar la haya armado (se sabe que es remota, no adónde).

### `ficha`

```json
{
  "documento": "/casa/trabajo/proyectos/faro/README.md",
  "relativo": "proyectos/faro/README.md",
  "titulo": "Faro", "etiqueta": "Puerto Norte · Faro",
  "estado": "La lámpara nueva llegó y está montada; …",
  "pendientes": [ { "texto": "Ajustar el giro", "hecho": false, "en_curso": true, "id": "", "origen": "pendientes" } ],
  "secciones": { "esperando": [ … ], "campos": { … } },
  "leida": "2026-09-18T09:12:44", "nota": "", "vacia": false
}
```

`etiqueta` es el nombre para mostrar, armado con la `etiqueta` del arquetipo
(docs/perfil.md); vacío si no hay con qué armarlo, y entonces se muestra el nombre del
hilo. El nombre del hilo sigue siendo la llave: la etiqueta solo cambia lo que se lee.
`secciones` lleva lo que el perfil declaró y telar no interpreta; su contenido
depende del repositorio, así que un consumidor lo dibuja o lo ignora, pero no
supone. `nota` dice en una frase por qué la ficha salió flaca (el documento no
existe, falta una sección requerida). Ver [el estado de un hilo](#el-estado-de-un-hilo).

### `pendiente`

```json
{
  "ref": "faro:2", "texto": "Ajustar la velocidad de giro",
  "hecho": false, "en_curso": true, "id": "", "origen": "pendientes", "dueno": "Ana Pérez",
  "hilo": "faro", "ruta": "proyectos/faro",
  "proveedor": "", "clase": "", "cuando": null, "url": ""
}
```

`clase` la pone el proveedor que lo trajo: `"evento"` si ocupa una hora del día y
`"tarea"` si pide hacerse; vacío en los pendientes que salen de un documento. Es lo que
separa la agenda del resto: tener fecha no alcanza, porque una tarea vence un día y no
por eso es una reunión.

`ref` es la llave con que `telar pendiente <ref>` lo agarra: `<hilo>:<n>` si el
pendiente salió del documento de un hilo, `<ruta>:<n>` si salió de una unidad sin
hilo abierto, y el id del proveedor si vino de afuera. La `n` es la posición en el
documento, y **cambia si el documento cambia**: sirve para el minuto siguiente, no
para guardarla. `hilo` puede ser `""` (nadie lo está trabajando todavía).

`dueno` es quién lo hace: en una viñeta, lo que dice `@owner(Ana Pérez)` (en cualquier parte) o
`@Ana Pérez:` (al comienzo), y `""` si no dice nadie («sin responsable»); `@deadline(AAAA-MM-DD)` llega
como `cuando`. Esas marcas, y `@prioridad(…)`, no quedan en `texto`. En una tarea de proveedor, `dueno`
vacío es de la persona.

Lo que viene de un proveedor trae además `proyecto`: la carpeta que la tarea dice que es suya
(su `origen`, si es una ruta del repositorio), haya o no un hilo ahí; `ruta` es la del hilo al
que se la llevaría. La vista de proyectos del dashboard junta por `proyecto`.

## Orden por orden

### `telar hilos --json`

```json
{ "sesion": "telar", "viva": true, "raiz": "/casa/trabajo",
  "multiplexor": "tmux", "aviso": "", "orden": "mux", "clientes": [ 85579 ],
  "hilos": [ hilo, … ] }
```

`clientes` son los pids de las terminales enganchadas a la sesión: los procesos del
multiplexor que la están mostrando. Sirven para encontrar desde afuera cuál terminal
mira la sesión (la extensión de VS Code busca aquel terminal cuya shell es antepasado de
uno de ellos, y le da el foco). Vacío si la sesión no está viva o el multiplexor no lo
dice; zellij, hoy, no lo dice.

`aviso` trae, en prosa, por qué no se pudo hablar con el multiplexor (no está
instalado, no responde); con `aviso` no vacío, `viva` es `false` y los hilos son
los que telar recuerda. `orden` es el criterio pedido: `mux`, `alfa`, `reciente` o
`prioridad`. Con `--vivos` no vienen los que el multiplexor no muestra; con
`--sin-ficha`, los hilos no traen la clave `ficha`.

### `telar ficha [hilo] --json`

```json
{ "hilo": hilo, "seguro": true, "acciones": [ … ], "perfil": "taller" }
```

`seguro` dice si el hilo se supo por `$TELAR_HILO` (la variable que el multiplexor
exporta al abrirlo) o si hubo que adivinarlo por el foco. Adivinar por el foco es
legítimo para mirar y peligroso para actuar: el foco lo mueve la persona mientras
el agente trabaja en otro hilo. Cada acción trae `nombre`, `descripcion`, `tecla`,
`donde` (`hilo` o `raiz`) y `confirmar`.

### `telar hilo <verbo> --json`

```json
{ "hilo": hilo, "codigo": 0 }
```

El hilo **después** del cambio, releído. `hilo` es `null` si el verbo lo hizo
desaparecer de la lista (`olvidar`).

### `telar pendientes --json`

```json
{ "dia": "2026-09-18", "raiz": "/casa/trabajo",
  "pendientes": [ pendiente, … ], "fallas": [ "agenda: no respondió" ] }
```

Los hechos no vienen salvo `--hechos`; las unidades sin hilo, solo con `--repo`;
los proveedores, solo con `--proveedores` (y ahí `fallas` dice cuál se cayó, sin
tumbar el resto).

### `telar pendiente <ref> --json`

Con `--donde`, la decisión sin tocar nada:

```json
{ "ref": "faro:2", "texto": "Ajustar el giro", "destino": "faro",
  "vivo": true, "ruta": "proyectos/faro", "nuevo": false }
```

Sin `--donde`, lo que pasó:

```json
{ "ref": "faro:2", "texto": "Ajustar el giro", "destino": "faro",
  "creado": false, "enviado": false }
```

`enviado` es `false` salvo que se pida `--enviar`: telar **escribe** la frase en la
entrada del agente y no la manda. Apretar Enter es de la persona.

### `telar hoy --json`

Con `--dia AAAA-MM-DD`, la agenda (y `fecha`, `dia`, `semana`) es la de ese día; el resto no cambia.

```json
{ "ahora": "2026-09-18T09:12:44", "dia": "viernes", "fecha": "2026-09-18",
  "semana": 38, "local": false,
  "agenda": [ pendiente con "cuando", … ],
  "atencion": [ hilo sin ficha, … ],
  "pendientes": [ pendiente, … ],
  "tiempo": { "total": 7200.0, "hilos": { "faro": 4320.0 } },
  "proveedores": { "declarados": ["agenda"], "fallas": [] } }
```

`agenda` es `null` —no `[]`— cuando no se consultó: con `--local`, o sin ningún
proveedor declarado. Vacío significa «no hay nada hoy»; `null`, «no se preguntó», y
una vista que guarde lo anterior sabe entonces que no debe borrarlo. `atencion`
trae solo los hilos que dijeron algo, ordenados por lo que piden: primero los que
esperan, después los que terminaron, al final los que trabajan.

### `telar proyectos --json`

```json
{ "raiz": "/…/trabajo",
  "proyectos": [
    { "ruta": "proyectos/faro", "nombre": "Faro", "arquetipo": "proyecto",
      "modificado": "2026-09-18T12:04:31+00:00", "hilo": "faro", "vivo": true } ] }
```

Todas las unidades del perfil, tengan hilo o no, ordenadas por `nombre`. `modificado` es
el archivo más reciente de la carpeta sin contar las ocultas (`null` si no hay ninguno).
`hilo` es el que está vinculado a esa unidad, o `""`; `vivo`, si ese hilo tiene tab.

`telar proyectos abrir <ruta> --json` devuelve `{ "hilo", "ruta", "mensaje", "hecho" }`:
`hecho` es `"abierto"` o `"ya estaba"`, y `mensaje` lo que se le dijo al agente (`""` si
no hay agente o si el hilo ya estaba).

### `telar seccion <clave> --json`

Lo que imprime el comando `home` de una sección, tal cual, después de comprobar su forma:

```json
{ "titulo": "Diario", "subtitulo": "opcional",
  "bloques": [
    { "titulo": "opcional", "texto": "markdown simple, opcional",
      "items": [ { "titulo": "…", "fecha": "2026-09-23T11:43", "texto": "…",
                   "conversacion": "id de una conversación del agente", "hilo": "…" } ] } ] }
```

Un bloque puede traer además un **lienzo**, una página HTML local que se muestra en un
`<iframe>` al comienzo del bloque, a todo el ancho:

```json
{ "lienzo": { "archivo": "/ruta/absoluta/dibujo.html", "alto": 240,
              "params": { "animo": "jugando", "nota": "…" } } }
```

`archivo` es obligatorio (absoluto, `.html`, tiene que existir); `alto` en píxeles, de 40
a 2000 (240 si falta); `params` va como query string (`?animo=jugando&nota=…`) y es la
forma de pasarle datos. El iframe lleva `sandbox="allow-scripts"` sin `allow-same-origin`:
el lienzo corre sus scripts pero no alcanza el panel ni la extensión. Cada vez que se pide
la página el iframe se vuelve a crear.

El lienzo entra como `srcdoc` (su contenido, no su ruta): un iframe hacia un recurso local
del webview queda en blanco. Eso trae tres consecuencias para quien lo escribe:

- tiene que ser **autocontenido**: sus rutas relativas no resuelven, y no hay red;
- hereda el CSP del panel; telar le pone el nonce del panel a cada `<script>`, así que el
  script en línea corre, pero un `<script src>` externo o un `eval` no;
- los params llegan por `location.search` (telar reescribe la URL a `about:srcdoc?…` antes
  de que corra nada) y también en `window.lienzo.params`. Un bloque puede ser solo un lienzo, o lienzo con título,
texto e ítems.

El sandbox deja al lienzo sin almacenamiento propio (`localStorage` lanza un error). Si lo
necesita —un juego que recuerda, un dibujo que se sigue—, la página declara `memoria`, la ruta
absoluta de un `.json` que puede no existir todavía:

```json
{ "lienzo": { "archivo": "/ruta/juego.html", "alto": 640, "memoria": "/ruta/estado/juego.json" } }
```

El lienzo recibe lo último guardado en `window.lienzo.memoria` (`null` la primera vez o si el
archivo no es JSON) y guarda con `window.lienzo.guardar(objeto)`, que reemplaza el archivo
entero. El lienzo nunca nombra la ruta: el panel le da una llave al pintarlo y escribe solo el
archivo que declaró la página, hasta 4 MB.

Todo es opcional salvo `titulo` en la página y en cada ítem. `texto` admite párrafos,
`**negrita**`, `*cursiva*`, `` `código` `` y listas con `- `; lo demás se muestra como
texto, nunca como HTML. Un ítem con `conversacion` se abre como conversación; uno con
`hilo` y sin conversación lleva a ese hilo. Si el comando falla, tarda más de 30 s o
devuelve otra forma, la orden sale con 2 y dice por qué.

### `telar bloque <clave> --json`

Lo que imprime el comando de `[bloques.<clave>]`, con el mismo contrato que la página de una
sección y las mismas reglas (sale con 2 si falla, tarda o viene con otra forma). El dashboard
toma los ítems de todos sus bloques y usa dos campos más de cada ítem, que en una sección se
ignoran:

| campo | qué es |
| --- | --- |
| `marca` | un carácter al comienzo de la fila (`●` sin procesar, `✓` hecho) |
| `destacado` | `true` resalta la fila con el color del bloque |
| `mensaje` | un clic en la fila abre un hilo nuevo con el agente y este primer prompt (`telar bloque <clave> --abrir <mensaje>`) |
| `nombre` | el nombre de ese hilo; el `titulo` si falta |

`mensaje` llega al agente tal cual: quien escribe el comando decide qué lleva. Si la fila
muestra algo que escribió otra persona (un asunto de correo), conviene que el mensaje
lleve solo un identificador y que el agente lea el resto.

`fecha` da la hora de la fila; `texto`, quién o de dónde (la columna que se esconde cuando
el panel es angosto); `titulo`, qué.

### `telar tarea <id> --json`

La ficha de una tarea: lo que imprime el `detalle` del proveedor (`{id}` reemplazado), con
el contrato de una página de sección y tres cosas más. Un bloque puede ser `destacado`
(con `color`: azul, amarillo, verde, rojo, magenta, cian o violeta), un ítem puede traer
`enlace` (una URL o una ruta absoluta, que se abre con un clic) y la página trae
`acciones`, hasta nueve:

```json
{ "titulo": "T203 · Mandar el alcance al cliente", "subtitulo": "activa · P0 · vence 2026-09-22",
  "bloques": [ { "titulo": "el agente · cerrar (caducó)", "texto": "…", "destacado": true, "color": "cian" } ],
  "acciones": [
    { "nombre": "✓ de acuerdo: caducó", "principal": true, "comando": ["todo", "caduco", "T203"] },
    { "nombre": "no, sigue viva", "pide": "por qué", "comando": ["todo", "responder", "T203", "no: {texto}"] },
    { "nombre": "trabajar en un hilo", "tipo": "hilo" },
    { "nombre": "abrir lo preparado", "tipo": "abrir", "enlace": "/ruta/borrador.md" },
    { "nombre": "descartar", "comando": ["todo", "descarta", "T203"], "confirmar": true } ] }
```

| campo | qué es |
| --- | --- |
| `tipo` | `comando` (de fábrica), `hilo` (llevar la tarea a su hilo) o `abrir` (`enlace`) |
| `comando` | lista de palabras, sin shell; `{texto}` se reemplaza por lo escrito |
| `pide` | antes de correr se pide un texto, con esto de ayuda |
| `confirmar` | antes de correr se pregunta |
| `principal` | la de ⏎; una como mucho. Las demás van numeradas y el número es su tecla |
| `mensaje` | después del comando, abre un hilo nuevo con el agente y este primer prompt (`nombre_hilo`: su nombre); un `{texto}` en él también se reemplaza |
| `rol` | qué es, para quien la corre sin abrir la ficha: `hecha` es la que corre el ✓ de la lista de tareas de VS Code, sin preguntar aunque tenga `confirmar`; `fecha` cambia la fecha de la tarea, y recibe en `{texto}` la fecha nueva (`AAAA-MM-DD`, o `+Nd`) que el dashboard pide con un selector al hacer clic en el atraso; `dueno` cambia quién la hace, y recibe en `{texto}` el nombre (o `none`, sin asignar) que el dashboard pide al hacer clic en el responsable, ofreciendo `opciones` |
| `opciones` | con `rol: dueno`, las personas para elegir (una lista de nombres); se puede escribir otra |

`telar tarea <id> --accion N [--texto T]` corre la acción `N`. telar vuelve a pedir la ficha
y toma el comando de ahí, nunca de quien lo pide: desde el dashboard solo se puede correr
lo que el proveedor ofreció. Las de tipo `hilo` y `abrir` las hace quien dibuja.

La lista de tareas del proveedor `comando` acepta además `avance`: lo último que dejó un
agente que la trabajó solo, `<estado>[:<cómo>] <fecha>` (`preparado 2026-09-25`,
`cerrar:caduca 2026-09-25`). telar no lo interpreta: el dashboard lo muestra y ordena por él.
`color` (azul, amarillo, verde, rojo, magenta, cian, violeta) pinta la palabra de `avance`.
Y `area`: a qué parte de la vida pertenece la tarea (`trabajo`, `personal`, lo que el
proveedor use). Con más de un área, las listas de tareas ofrecen un filtro por ella.

### `telar agente conversacion <id> --json`

```json
{ "conversacion": "4f21c0de-…", "archivo": "/…/4f21c0de-….jsonl", "hilo": "faro",
  "mensajes": [ { "quien": "usuario", "hora": "2026-09-23T14:41:02Z", "texto": "/revisar" },
                { "quien": "herramienta", "hora": "…", "texto": "Bash · listar la carpeta" },
                { "quien": "agente", "hora": "…", "texto": "Listo." } ] }
```

`quien` es `usuario`, `agente` o `herramienta`. Una herramienta es una línea (su nombre y
su `description`, `command` o `file_path`), no su salida. El razonamiento y los resultados
de herramientas se omiten. `hilo` es el hilo donde telar anotó esa conversación, o `""`.

### `telar correo --json`

```json
{ "remotos": [ {
    "remoto": "casa", "usuario": "usuario", "error": "", "sabe_pendientes": true, "cartero": true,
    "archivo_comun": false,
    "hilos": { "Pizza": { "direccion": "usuario+pizza@servidor", "pendientes": [ correo, … ],
                          "correos": [ correo + "leido", … ], "no_leidos": 1 } },
    "conversaciones": [ { "id": "<…>", "asunto": "…", "participantes": ["otro", "usuario"],
                          "mensajes": 3, "ultima": "Thu, 24 Sep 2026 12:19:03 -0300",
                          "estado": "entregado", "correos": [ correo, … ] } ] } ] }
```

`correo` es `{id, de, para, asunto, fecha, estado, nuevo}`, y con `--cuerpos` también
`cuerpo`. `de` es el usuario que lo mandó según el uid que anotó el servidor de correo, no
el campo `From`. `estado` es `entregado`, `retenido`, `sin sesión` o `""` si el cartero no
anota ids (entonces `sabe_pendientes` es `false` y `pendientes` va vacío). Un `error` no
vacío dice por qué no se pudo leer esa máquina; las otras siguen.

### `telar directorio --json`

```json
{ "remotos": [ { "remoto": "casa", "error": "",
    "personas": [ { "usuario": "ana", "maquina": "casa", "actualizado": "2026-09-24T17:42:00",
                    "hilos": [ { "nombre": "Faro", "direccion": "ana+faro@casa",
                                 "vinculo": "proyectos/faro", "resumen": "Faro" } ] },
                  { "usuario": "otra", "error": "el archivo es de ana: se descarta" } ] } ] }
```

Una persona con `error` no se pudo leer o no es quien dice ser. `telar directorio publicar
--json` devuelve `{"publicado": {"casa": ""}}`, con el error de cada máquina o `""`.
`telar correo enviar … --json` devuelve `{"enviado": true, "a": "…", "via": "usuario@casa"}`.

### `telar atencion get --json`

Con un hilo:

```json
{ "hilo": "faro", "atencion": "espera", "desde": "2026-09-18T09:12:44" }
```

Sin hilo, todos los anotados:

```json
{ "hilos": { "faro": { "atencion": "espera", "desde": "2026-09-18T09:12:44" } } }
```

`telar atencion set <atencion> --json` devuelve `{"hilo": …, "atencion": …}`.

### `telar tiempo --json`

```json
{ "desde": "2026-09-18", "hasta": "2026-09-18", "tope": 3600.0,
  "unidad": "segundos", "agrupado": "hilo", "total": 7200.0,
  "hilos": { "faro": 4320.0 },
  "dias": { "2026-09-18": { "faro": 4320.0 } } }
```

`tope` es el recorte de un intervalo sin cambio de foco, en segundos: nadie avisa
cuando se va del computador. `agrupado` es `hilo` o `carpeta` (`--por-carpeta`
suma los hilos que miran la misma). Un intervalo cuenta entero en el día en que
**empezó**. `telar tiempo marcar --json` devuelve `{"hilo": …, "anotado": bool}`,
donde `anotado` es `false` si el foco ya estaba ahí y no había nada que anotar.

### `telar doctor --json`

```json
{ "ok": false,
  "revisiones": [ { "nombre": "multiplexor", "estado": "ok",
                    "dice": "tmux", "arreglo": "" } ] }
```

`estado` es `ok`, `aviso` o `falla`. `arreglo` es la frase que dice qué hacer, y
viene vacía cuando no hay nada que hacer. La orden sale con **1** si hay alguna
falla, con 0 si no: un aviso no es una falla, telar funciona sin perfil, sin
proveedores y sin ganchos, solo hace menos.

### `telar config --json` y `telar perfil --json`

`config` devuelve la configuración resuelta, con `origen` (de qué archivo salió,
vacío si son puros valores por defecto) y `entorno` (qué clave pisó cada variable
`TELAR_*`). `perfil` devuelve lo que el repositorio declara: `minimo` dice si rige
la convención mínima, y cada arquetipo trae sus `secciones` y los `documentos` que
alcanza hoy, relativos a la raíz.

### `telar init --json` y `telar tejer --json`

```json
{ "escrito": { "config": "/casa/.config/telar/config.toml" },
  "multiplexor": "tmux", "sesion": "telar", "raiz": "/casa/trabajo",
  "avisos": [ "ya había configuración …; --forzar la reescribe" ] }
```

En `escrito` solo aparece lo que se escribió de verdad: lo que ya estaba y no se
pisó sale en `avisos`. `tejer` devuelve
`{"sesion": …, "multiplexor": …, "ya_estaba": bool, "hilos": n}`.

## `telar agente --json`

Cuatro formas, una por orden. Todas son de una línea, como el resto.

`aviso` — lo que el gancho le cuenta a telar, y qué hizo telar con eso:

```json
{"aplicado": true, "hilo": "faro", "atencion": "trabajando", "sesion": "0f3a…"}
```

Cuando el aviso no se pudo aplicar, la línea es `{"aplicado": false, "problema": "…"}` y
nada más. Un gancho nunca falla por esto: devuelve 0 igual, porque del otro lado hay un
agente esperando y un semáforo que miente un rato es el problema menor.

`instalar`, `desinstalar` y `--seco` — qué archivo se tocó y con qué:

```json
{
  "ruta": "/casa/.claude/settings.json",
  "ganchos": ["SessionStart", "UserPromptSubmit", "Notification", "PostToolUse", "Stop", "SessionEnd"],
  "reemplazados": [], "escrito": true,
  "respaldo": "/casa/.claude/settings.json.telar.bak",
  "comando": ["/usr/local/bin/telar", "agente", "aviso", "claude-code"]
}
```

Con `--seco`, `escrito` es `false` y no se tocó nada. `--json` implica `--si`: del otro
lado no hay a quién preguntarle.

`ver` — cómo está el agente en este hilo:

```json
{
  "agente": "claude-code", "hilo": "faro", "atencion": "espera",
  "ganchos": ["SessionStart", "Stop"], "ajustes": "/casa/.claude/settings.json",
  "conversaciones": [{"id": "0f3a…", "cuando": "2026-09-18T09:12", "titulo": "…"}]
}
```

`ganchos` son los que están puestos **hoy** en la configuración del agente, no los que
telar instalaría.

## `telar espejo` — los hilos de otra máquina

`telar espejo publicar` (en el laptop) arma esta foto y la manda por ssh a `telar espejo recibir
--de <nombre>` (en el servidor), que la valida, le pone la hora de llegada —la de **ese** reloj, no
la de la foto— y la guarda en `<estado>/espejos/<nombre>.json` con permisos 600. `<nombre>` es
`a-z0-9_-`, hasta 32 caracteres; lo que no cabe en eso se rechaza.

La foto (versión 1):

```json
{
  "version": 1, "maquina": "macbook-nico", "telar": "0.1.9",
  "publicado": "2026-09-30T10:20:00-03:00", "sesion": "faro",
  "hilos": [
    {"nombre": "Faro", "atencion": "espera", "vivo": true, "activo": false, "prioridad": 1,
     "tiempo": 5400.0, "visto": null, "relativa": "proyectos/faro", "arquetipo": "proyecto",
     "remoto": "", "resumen": "Cliente · Faro"}
  ]
}
```

Los archivados no viajan. No viajan tampoco la ruta absoluta, las sesiones ni el estado del
proyecto: lo que se lee desde afuera es lo que sirve para mirar. `resumen` es el título del
documento del hilo. Una foto de otra versión, sin lista de hilos o con más de 2 MB se rechaza.

`telar espejo ver --json` (y `/api/espejos` de `telar web`) lee lo guardado:

```json
{"vigente": 120.0,
 "espejos": [{"nombre": "macbook-nico", "en_linea": true, "edad": 12.3, "recibido": 1790000000.1,
              "publicado": "2026-09-30T10:20:00-03:00", "telar": "0.1.9", "sesion": "faro",
              "hilos": []},
             {"nombre": "roto", "error": "no se pudo leer: …", "en_linea": false, "edad": null, "hilos": []}]}
```

`en_linea` es `edad < vigente`. Un archivo que no se puede leer aparece con `error`, no se esconde.
`telar espejo publicar --json` dice `{"publicado": true|false, "maquina", "remoto", "error"}` y sale
con 1 si falló.

## `telar enlace` — la puerta entre dos máquinas

El cliente (`telar enlace <verbo>`, o `telar.enlace.llamar`) corre por ssh, con la llave de la puerta:

```
ssh -i <llave> -o BatchMode=yes <destino> '<verbo> [argumentos citados]'   < contenido
```

sshd ignora esa línea como orden y ejecuta el comando forzado `telar enlace servir`, entregándola en
`SSH_ORIGINAL_COMMAND`; el **contenido** (un archivo, un texto) va por la entrada estándar. `servir`
imprime una sola línea JSON y sale con 0 si `ok`, con 1 si no. Toda respuesta trae `ok` y `verbo`; un fallo
trae `error` y nada más. Los verbos y sus topes:

| verbo | argumentos | entrada | respuesta |
| --- | --- | --- | --- |
| `ping` | — | ninguna | `maquina`, `telar`, `hora`, `verbos` |
| `hilos` | — | ninguna | `foto`: la del espejo (ver `telar espejo`) |
| `archivo` | `<nombre>` | el archivo, hasta 100 MB | `ruta`, `bytes`, `sha256` |
| `enviar` | `<hilo> [enter]` | el texto, UTF-8, hasta 8000 caracteres | `hilo`, `caracteres`, `enviado` |
| `notificar` | `[titulo]` (hasta 60) | el texto, hasta 500 caracteres | `titulo`, `caracteres` |
| `leer` | `<hilo> [N]` (1 a 50, 5 si no se dice) | ninguna | `historia`: la de `telar hilo leer --json` |

Reglas que la puerta impone (y `pruebas/test_enlace.py` comprueba):

- Un verbo que no está en la tabla —o que `[enlace] verbos` apagó— se rechaza; no hay forma de correr otra cosa.
- `archivo`: el nombre se reduce a `[A-Za-z0-9._ -]` sin carpetas ni puntos delante, y el archivo nunca pisa a
  otro (agrega `-1`, `-2`…). Queda con permisos 600 en una carpeta 700.
- `enviar`: solo a un hilo que existe **y** está vivo (con tab, o `propio`); un texto con saltos de línea exige `enter`, porque el
  salto es un ↩.
- `notificar`: el texto llega por variables de entorno, nunca dentro de un script.
- `leer`: apagado si `[enlace] verbos` no lo nombra; solo un hilo por su nombre exacto, y uno que `no_leer`
  veta responde lo mismo que uno que no existe.
- Lo que pesa más que el tope del verbo se rechaza antes de leerse o hacerse nada.

## `telar periodicos --json` — los procesos periódicos

```json
{"maquina": "servidor", "archivo": "/home/ana/.config/telar/periodicos.toml", "zona": "America/Santiago",
 "procesos": [{"nombre": "correo", "cuando": "0 9-19/2 * * *", "tipo": "mensaje", "comando": "", "mensaje": "/correo",
   "hilo": "✉ correo", "max_abiertos": 2, "argumentos": [], "carpeta": "", "descripcion": "", "activo": true,
   "proxima": "2026-10-02T11:00-03:00",
   "ultima": {"inicio": "2026-10-02T09:00:01-03:00", "fin": "…", "codigo": 0, "resultado": "abrí «✉ correo 10/02 09:00»",
              "tipo": "mensaje", "segundos": 0.8, "hilo": "✉ correo 10/02 09:00"}}]}
```

`proxima` va vacía si está pausado. `ultima` está vacía si nunca corrió, y trae `corriendo: true` mientras
corre. `codigo` distinto de 0 es que falló (un comando que salió mal, un hilo que no se pudo abrir); un
`mensaje` saltado por `max_abiertos` es 0 con `resultado` «saltado: …». Las órdenes que cambian algo
responden `{"ok": true, "hecho": "…"}`; `log` responde `{"nombre", "log"}`.

## `telar hilo leer --json` — lo último de un hilo

```json
{"hilo": "Faro", "fuente": "conversacion", "conversacion": "<id>", "total_turnos": 12, "recortado": false,
 "turnos": [[{"quien": "usuario", "hora": "2026-10-01T12:00:00Z", "texto": "…"},
             {"quien": "herramienta", "hora": "…", "texto": "Bash · qué hace"},
             {"quien": "agente", "hora": "…", "texto": "…"}]]}
```

Un turno empieza con un mensaje de `usuario`. `quien` es `usuario`, `agente` o `herramienta`; una herramienta
es una línea (cuál y sobre qué), nunca su salida. `recortado` dice si se cortó un texto (más de 4000
caracteres) o se soltaron turnos viejos para no pasar de 60 000 en total. Sin conversación en esta máquina:
`{"hilo", "fuente": "panel", "texto", "recortado"}` con lo último del panel.

## `telar resultado <clave> [día] --json` — lo que una skill dejó un día

Lo que declara `[resultados.<clave>]` (carpeta y, con `en`, la máquina del bus donde vive). Siempre
un objeto con `ok`. Con `en` y bus se lee en esa máquina (pedido `resultado` a su nodo); si no
responde, se lee la carpeta de aquí y `aviso` lo dice.

```json
{"ok": true, "clave": "plan", "nombre": "Plan del día", "dia": "2026-10-07",
 "dias": ["2026-10-07", "2026-10-06"], "formato": "json", "contenido": {"...": "lo que escribió la skill"},
 "desde": "servidor", "aviso": ""}
```

`formato` es `json`, `md` o vacío (no hay archivo ese día: `contenido` es `null`). `dias` son los
que existen, del más nuevo al más viejo (hasta 60). telar no fija la forma de `contenido`: la decide
la skill, y quien lo muestra la conoce (el dashboard dibuja la del plan del día).

## `telar evento notas|nota` — las notas de los eventos del día

`[notas]` dice dónde viven (`carpeta`, `<estado>/notas` por defecto) y, con `en`, en qué máquina.

```
telar evento nota <id del evento> "texto" --de <skill o hilo> [--titulo T] [--inicio HH:MM] [--dia AAAA-MM-DD]
telar evento notas [AAAA-MM-DD] --json
```

```json
{"ok": true, "dia": "2026-10-07", "eventos": {"<id>": {"titulo": "Comité", "inicio": "10:00",
  "notas": [{"de": "planear", "texto": "…", "creado": "2026-10-07T08:30:00-03:00"}]}}}
```

El id es el del evento en el calendario (el `id` de la agenda de `telar hoy --json`). El título y la
hora van al lado para mostrar la nota aunque el id cambie. Con `en`, escribir en otra máquina que no
responde falla (`ok: false`) en vez de dejar la nota aquí, donde nadie la vería.

## `POST /api/enviar` — escribirle a un hilo desde `telar web`

Solo existe con `telar web --escribir`; sin eso responde 403. Pide `Content-Type: application/json`, el
encabezado `X-Telar: 1` y que `Host` (y `Origin`, si viene) sean los de ese servidor.

```json
{"maquina": "", "hilo": "Lumbre", "texto": "hola", "enter": true}
```

`maquina` vacío es la máquina del servidor; con un nombre (el `nombre` de un espejo), esa máquina por
`telar enlace`. `enter` (por defecto `true`) además de escribir el texto lo manda. La respuesta es la de la
puerta (`{"ok": true, "hilo": …, "caracteres": …, "enviado": …}` o `{"ok": false, "error": …}`):

| código | cuándo |
| --- | --- |
| 200 | se escribió |
| 400 / 413 | cuerpo mal formado / de más de 64 KB |
| 403 | la página está en solo lectura, o la petición no es de esta página |
| 404 | ninguna máquina de `[enlaces]` corresponde a `maquina` |
| 409 | la puerta lo rechazó: el hilo no existe o no está vivo, el texto es vacío o pasa de 8000 caracteres… |
| 429 | otro envío hace menos de medio segundo |

`GET /api/yo` dice qué puede hacer esa página: `{"escribir": bool, "plan": bool, "enlaces": ["laptop"]}`.

## `GET /api/plan` — el plan de un día, en la pestaña «plan» de `telar web`

Solo existe si `telar web` arrancó con `--plan CARPETA`; sin eso, 404 y la pestaña no aparece (`/api/yo` dice `plan: true|false`). Los planes
son archivos `AAAA-MM-DD.json` en esa carpeta (o `.md`, los de antes), escritos por quien quiera —en el repo de Nico, la skill `/planear`—; telar solo los lee.

```
/api/plan                    el de hoy; si no hay, el próximo que haya; si no, el último
/api/plan?dia=2026-10-05     el de ese día (404 si no existe o si el nombre no es una fecha)
```
```json
{ "dia": "2026-10-05", "dias": ["2026-10-05", "2026-10-04"], "hoy": "2026-10-04", "plan": { "version": 1, "resumen": {…}, "agenda": […] } }
```

`dias` va del más nuevo al más viejo. Con un `.json`, `plan` es su contenido tal cual (502 si no es JSON válido); su esquema lo define quien lo escribe y lo
documenta la skill (`.claude/skills/planear/esquema.md` en el repo de Nico). La página dibuja el resumen, los resultados, la **agenda con el contexto de cada reunión
plegable**, los pendientes, el foco y las personas. Con un `.md`, viene `texto` (el markdown sin su front-matter) y la página lo dibuja con las tablas apiladas.
Sin ningún plan, `dia` viene vacío y `dias` es `[]`. Si hay `.json` y `.md` del mismo día, manda el `.json`.

## `POST /api/plan/comentar` — un comentario sobre el plan abre una sesión

Solo con `telar web --escribir --plan CARPETA --plan-comando CMD` (si no, 404 o 403; `/api/yo` dice `plan_comentar`). Cuerpo: `{"dia": "2026-10-05", "texto": "…"}`,
de hasta 4.000 caracteres, sobre un plan que exista. Tiene las mismas defensas que `/api/enviar` (encabezado `X-Telar`, `Host` y `Origin` de esta página) y se
anota en `web.log` (solo el tamaño). Un comentario cada cinco segundos.

telar no sabe qué hace una sesión: corre `CMD` con el comentario en la **entrada estándar** —nunca en la línea de comandos— y `TELAR_PLAN_DIA` y
`TELAR_PLAN_CARPETA` en el entorno. La primera línea que imprima es el nombre del hilo que abrió. Respuesta: `{"ok": true, "hilo": "✎ plan 10/05 21:40", "caracteres": 213}`;
un fallo del programa es 502 con su última línea de error.

## `POST /api/hilo/nuevo` — abrir un hilo nuevo desde `telar web`

Solo con `telar web --escribir --nuevo` (si no, 404 o 403; `/api/yo` dice `nuevo`). Cuerpo: `{"nombre": "…", "carpeta": "…", "mensaje": "…"}`.
`nombre` es obligatorio (hasta 60 caracteres) y no puede repetir el de ningún hilo, vivo o archivado: 409 si ya existe. `carpeta` es opcional y solo puede
ser la `ruta` de una unidad de `telar proyectos` (404 si no); sin ella, la que diga `[agente] carpeta`. `mensaje` es opcional (hasta 4.000 caracteres): el primer
prompt del agente; si empieza con «-» se le antepone un espacio para que no se lea como una opción. Mismas defensas que `/api/enviar`; un hilo nuevo cada cinco segundos.

Abre lo mismo que `telar movil`: una sesión tmux `telar-<8 hex>` en esta máquina con el agente configurado, y anota su conversación. `--nuevo-args` agrega palabras a la línea
del agente (p. ej. `--permission-mode auto`). Respuesta: `{"ok": true, "hilo": "…", "carpeta": "…"}`. La conversación del hilo existe en disco recién con su primer mensaje,
así que la página reintenta unos segundos al entrar. `GET /api/proyectos` sirve la lista de unidades para elegir la carpeta (la misma salida de `telar proyectos --json`).

## `GET /api/conversacion` — el historial de un hilo, por páginas

`telar web` sirve la conversación de un hilo **de esta máquina** por trozos (una conversación larga pesa decenas
de MB). Se pide por hilo, no por id: de `telar hilos --json` sale la lista de conversaciones permitidas (`sesiones`),
así que un id suelto nunca abre un archivo. Solo lee, y funciona sin `--escribir`.

```
/api/conversacion?hilo=Faro                       los últimos 60 mensajes
/api/conversacion?hilo=Faro&antes=340&n=60        los 60 anteriores al mensaje 340
/api/conversacion?hilo=Faro&despues=400           lo que llegó desde el 400 (seguirla en vivo)
/api/conversacion?hilo=Faro&sesion=<id>           otra conversación del mismo hilo (la primera es la del hilo)
```

```json
{"sesion": "0f3a…", "sesiones": ["0f3a…"], "total": 390, "desde": 330, "hasta": 390, "modificada": 1790000000000000000,
 "hilo": {"nombre": "Faro", "atencion": "espera", "vivo": true},
 "mensajes": [{"quien": "usuario", "hora": "2026-09-30T10:24:00Z", "texto": "…"},
              {"quien": "herramienta", "hora": "…", "texto": "Bash · ls -la"},
              {"quien": "agente", "hora": "…", "texto": "…", "recortado": 123}]}
```

**De otra máquina** (`&maquina=<nombre del espejo>`): el servidor pide el verbo `leer` de la puerta
(`telar enlace`) y devuelve **la misma forma**, para que la pantalla sea una sola. La otra máquina entrega los
últimos N turnos (`&turnos=10`, hasta 50), no mensajes numerados: `desde` es siempre 0, no hay `despues`, y se
pide más turnos o se vuelve a pedir. Trae además `remota`, `fuente` (`conversacion`, o `panel` si no había
conversación y se leyó la ventana), `turnos`, `total_turnos` y `recortado`. Lo que la otra máquina no entrega
—el verbo `leer` apagado, un hilo vetado por `[enlace] no_leer`, la máquina apagada— llega como 409 con su
motivo. Nada de lo conversado se guarda en el servidor: se pide, se muestra y se olvida (unos 3 s de caché).

Los mensajes se numeran por su posición y una conversación solo crece, así que un índice sigue valiendo mientras
el archivo no se reescriba (si `total` baja, hay que volver a leer). Un mensaje de más de 20 000 caracteres viaja
recortado, con `recortado` = los que faltan. Errores: 400 (falta el hilo o un número mal escrito) y 404 (no hay
ese hilo, la conversación no es de él, o no está en disco en esta máquina).

