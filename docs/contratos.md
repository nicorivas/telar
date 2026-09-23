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
  "id": "@3", "nombre": "faro", "vivo": true, "activo": false,
  "archivado": false, "vinculado": true,
  "ruta": "/casa/trabajo/proyectos/faro", "relativa": "proyectos/faro",
  "arquetipo": "proyecto", "prioridad": 2, "atencion": "espera",
  "visto": "2026-09-18T09:12:44", "tiempo": 4320.0,
  "sesiones": ["a1b2c3d4"],
  "ficha": { … }
}
```

`id` es la llave del multiplexor (`@3` en tmux y el id del tab en zellij, estables mientras la sesión viva) y es lo
que reciben las órdenes. `nombre` es lo que se muestra **y la llave del estado**:
el id se corre cuando alguien abre un tab al principio, el nombre no. `vivo` dice
si el multiplexor lo está mostrando ahora; un hilo archivado, o uno de una sesión
que todavía no se levanta, aparece con `vivo: false` en vez de desaparecer.
`tiempo` son los segundos con el foco **en el día en curso**. `ficha` puede ser
`null` (con `--sin-ficha`) o faltar.

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
  "hecho": false, "en_curso": true, "id": "", "origen": "pendientes",
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

Todo es opcional salvo `titulo` en la página y en cada ítem. `texto` admite párrafos,
`**negrita**`, `*cursiva*`, `` `código` `` y listas con `- `; lo demás se muestra como
texto, nunca como HTML. Un ítem con `conversacion` se abre como conversación; uno con
`hilo` y sin conversación lleva a ese hilo. Si el comando falla, tarda más de 30 s o
devuelve otra forma, la orden sale con 2 y dice por qué.

### `telar agente conversacion <id> --json`

```json
{ "conversacion": "afe0c1cc-…", "archivo": "/…/afe0c1cc-….jsonl", "hilo": "Kichoro",
  "mensajes": [ { "quien": "usuario", "hora": "2026-09-23T14:41:02Z", "texto": "/despertar" },
                { "quien": "herramienta", "hora": "…", "texto": "Bash · listar la carpeta" },
                { "quien": "agente", "hora": "…", "texto": "Listo." } ] }
```

`quien` es `usuario`, `agente` o `herramienta`. Una herramienta es una línea (su nombre y
su `description`, `command` o `file_path`), no su salida. El razonamiento y los resultados
de herramientas se omiten. `hilo` es el hilo donde telar anotó esa conversación, o `""`.

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
