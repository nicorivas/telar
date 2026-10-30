# El perfil del repositorio

**telar no sabe qué es un proyecto.** Es a propósito: en un repositorio un proyecto
es una carpeta con README, en otro es un archivo, en otro es una fila de una tabla.
Un programa que lo decida por todos sirve para uno solo.

Lo decide el repositorio de trabajo, en su carpeta `.telar/`: `.telar/perfil.yaml`, en su raíz. El perfil
viaja con el repositorio, se versiona con él, y cualquier telar que lo abra teje lo
mismo. Sin perfil, rige la [convención mínima](#sin-perfil-la-convención-mínima).

Un perfil declara tres cosas:

1. **arquetipos** — qué carpetas o archivos son unidades de trabajo, y qué se lee de
   cada una;
2. **secciones** — qué partes del documento son legibles, y cómo;
3. **acciones** — qué ofrece el repositorio hacer sobre un hilo.

## El archivo entero

```yaml
version: 1              # el esquema; hoy solo existe la 1
nombre: taller          # para decirlo en la interfaz; opcional

arquetipos:

  proyecto:                          # el nombre del arquetipo es la llave
    descripcion: Un encargo con carpeta propia.
    ruta: "proyectos/*/"             # glob relativo a la raíz; la barra final importa
    documento: README.md             # el archivo que se parsea, dentro de la carpeta
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\s+(.+)$'     # el grupo 1 es el valor
      estado:
        tipo: parrafo
        encabezado: '^##\s+Estado'
        requerida: true
      pendientes:
        tipo: casillas
        encabezado: '^##\s+Pendientes'
        maximo: 6

  nota:
    ruta: "notas/*.md"               # sin barra final: cada coincidencia ES el documento
    documento: "."
    secciones:
      titulo: { tipo: linea, encabezado: '^#\s+(.+)$' }

acciones:
  - nombre: revisar
    descripcion: Repasa el proyecto del hilo.
    comando: ["make", "revisar"]     # lista de palabras, nunca una línea de shell
    tecla: r                         # sugerencia para la interfaz; opcional
    donde: hilo                      # hilo (la carpeta del hilo) | raiz
    confirmar: false                 # si es true, la interfaz pregunta antes

areas: [Norte, Sur, Interno]         # el orden de las áreas (el `area:` del frontmatter) en el dashboard
internos: [Taller, Interno]          # los «clientes» que son la casa misma: en el dashboard va el nombre
```

`areas` y `internos` son opcionales. Un área que `areas` no nombra va después, por cuántos proyectos tiene. Un
proyecto cuyo cliente (el `{campo:Cliente}` de su etiqueta) está en `internos`, o que no tiene, se muestra por su
nombre sin ese prefijo: «Taller · Plan anual» es «Plan anual», no «Taller». Con varios repositorios, se juntan
las de todos, las del repo más profundo primero.

Hay uno completo y comentado en [`ejemplo/.telar/perfil.yaml`](../ejemplo/.telar/perfil.yaml).

## Arquetipos

Un arquetipo es una **forma** de unidad de trabajo. Un repositorio puede tener
varias: proyectos, notas, clientes.

| Clave | Obligatoria | Qué es |
|---|---|---|
| `ruta` | sí | glob relativo a la raíz. **Si termina en `/`**, cada coincidencia es una carpeta y el documento es `documento` adentro. Si no, cada coincidencia es el documento mismo. |
| `documento` | no (`README.md`) | el archivo que se parsea, dentro de la carpeta |
| `descripcion` | no | una línea, para que la interfaz pueda decir qué es esto |
| `etiqueta` | no (el título) | cómo se llama una unidad en pantalla: `{titulo}` y `{campo:Clave}`, una fila de la tabla de campos. Ver abajo. |
| `secciones` | no | qué se lee del documento |

La ruta tiene que ser relativa y no salir de la raíz: un `..` o un `/` inicial es
un error. telar solo lee dentro del repositorio que lo invitó.

**El orden en que se declaran importa dos veces.** Cuando dos rutas calzan con dos
arquetipos, gana el primero que se declaró —por eso «proyecto cerrado» va antes que
«área de conocimiento» si `conocimiento/proyectos/` calza con los dos—. Y cuando
`telar tejer` tiene que elegir cuáles ocho unidades abre de las que haya, abre las del
primer arquetipo antes que las del segundo. Un repositorio con ciento setenta y nueve
unidades declara así qué es lo que trabaja: el arquetipo de arriba es el que se ve al
entrar.

### El nombre en pantalla

El nombre de un hilo es la llave con que telar lo recuerda —su carpeta, su conversación,
si está archivado— y por eso es el de la carpeta: estable y sin espacios. Lo que se
*lee* en la lista puede ser otra cosa, y lo declara el arquetipo:

```yaml
proyecto:
  ruta: "operacion/proyectos/*/"
  etiqueta: "{campo:Cliente} · {titulo}"    # «Grupo Agrosur · Adopción IA»
```

De un campo queda solo el nombre: sin lo que va entre paréntesis y cortado en la
primera raya, coma o punto y coma. Si un valor ya está dentro de otro no se repite (con
el título «AquaChile — Campaña de Ideas», el cliente «AquaChile» sobra), y un marcador
vacío se lleva su separador. Sin `etiqueta`, se muestra el título del documento.

## Secciones

Una sección dice **dónde** está algo (`encabezado`) y **qué forma** tiene (`tipo`).

| `tipo` | Devuelve |
|---|---|
| `linea` | una línea. Si el `encabezado` tiene un grupo de captura, el valor es ese grupo: así el título sale del propio encabezado. Si no, la primera línea del cuerpo. |
| `parrafo` | el primer párrafo de texto del cuerpo, con los saltos unidos |
| `texto` | el cuerpo entero, tal cual |
| `lista` | las viñetas del cuerpo, en orden |
| `casillas` | las viñetas con casilla: `[ ]` pendiente, `[x]` hecha, `[>]` en curso |
| `tabla` | las filas `\| clave \| valor \|` del cuerpo, como diccionario |

| Clave | Por defecto | Qué es |
|---|---|---|
| `tipo` | `texto` | de la tabla de arriba |
| `encabezado` | — | expresión regular contra la línea del encabezado. **Sin ella la sección no está anclada**: se busca lo primero del documento que calce con el tipo |
| `maximo` | `0` (sin tope) | tope de elementos, para los tipos que devuelven varios |
| `requerida` | `false` | si falta, el documento no cumple lo que su repositorio prometió, y telar lo dice |

### Los tres nombres que telar entiende

El nombre de una sección es libre, pero tres significan algo:

| Nombre | telar lo usa para |
|---|---|
| `titulo` | cómo se llama el hilo cuando no tiene nombre propio |
| `estado` | la línea que se muestra bajo cada hilo |
| `pendientes` | lo que queda por hacer, con su marca de hecho / en curso |

Todo lo demás se lee y se guarda igual, y lo dibuja quien sepa qué significa. Un
`esperando` o un `ficha` valen lo mismo para telar: datos con nombre.

### La regex es contra el encabezado, no contra el cuerpo

`encabezado` calza la **línea del título de la sección**; el cuerpo es lo que va
desde ahí hasta el próximo encabezado del mismo nivel o mayor. Por eso
`'^##\s+Estado'` toma la sección entera y no solo esa línea, y por eso
`'^##\s+Estado(?! anterior)'` sirve para saltarse una sección vecina que empieza
igual.

## Acciones

Lo que el repositorio ofrece hacer sobre un hilo. telar no adivina órdenes: corre
las declaradas, y ninguna otra.

| Clave | Obligatoria | Qué es |
|---|---|---|
| `nombre` | sí | cómo se la llama (`telar accion revisar`) |
| `comando` | sí | **lista de palabras**, no una línea de shell |
| `descripcion` | no | una línea |
| `tecla` | no | una letra, sugerencia para la interfaz |
| `donde` | no (`hilo`) | el `cwd`: `hilo` (la carpeta del hilo) o `raiz` |
| `confirmar` | no (`false`) | si la interfaz pregunta antes de correrla |

El comando es una lista porque así no hay shell en el medio, y sin shell en el
medio no hay una carpeta con comillas en el nombre convertida en dos argumentos, ni
un `;` de alguien convertido en otra orden. Si de verdad hace falta una shell, se
pide explícita: `["sh", "-c", "…"]`, a la vista.

Marcadores que telar reemplaza en cada palabra: `{ruta}` (la carpeta del hilo),
`{hilo}` (su nombre), `{documento}` (el archivo parseado).

## La carpeta `.telar/`

Lo que un repositorio le dice a telar vive en una carpeta, `.telar/`, en su raíz, como `.github/` o `.claude/`:

| archivo | qué es | en git |
| --- | --- | --- |
| `perfil.yaml` | este perfil: lo del equipo, igual para todos | sí |
| `local.yaml` | lo de cada persona, encima del perfil | no: agrégalo a `.gitignore` |
| `fechas.yaml` | los mapas de fechas: cómo se leen los cronogramas que no tienen la forma de por defecto (abajo, «Mapas de fechas») | sí |
| `productos.yaml` | qué unidades son productos (lo que se vende) y cómo son sus ideas: el backlog y el tablero del módulo productos (abajo, «Productos») | sí |
| `equipo.yaml` | el equipo que trabaja en este repositorio: su bus, quién aprueba a las personas nuevas, sus módulos y los programas que hacen falta (`telar instalar --unirse`, docs/arquitectura.md, «Entre máquinas: el bus») | sí |

`local.yaml` tiene la misma forma que el perfil y se lee encima de él: un valor suyo reemplaza al del perfil,
un mapa se mezcla clave por clave (cambiar la `etiqueta` de un arquetipo no borra su `ruta`), y un `null`
quita la clave (`deal: null` esconde ese arquetipo solo para esa persona). Un perfil pedido a mano
(`[repos.<nombre>] perfil`, `[telar] perfil`) se lee solo, sin `local.yaml`.

`telar doctor` avisa si encuentra un `telar-perfil.yaml` suelto en la raíz, que telar ya no lee (el arreglo:
`git mv telar-perfil.yaml .telar/perfil.yaml`), y si `local.yaml` quedó en git.

Un `equipo.yaml`:

```yaml
nombre: faro                      # el equipo (minúsculas)
administra: ana                   # quién aprueba a las personas nuevas: su nombre en el bus
bus: nats://100.64.0.10:4222      # el bus del equipo
puerta: http://100.64.0.10:8780   # opcional: dónde se pide entrar; por defecto, la página de la máquina del bus
modulos:                          # opcional: los que instala quien se une
  grafo: https://github.com/alguien/telar-grafo
requiere: [tmux, claude, tailscale, git]
agente:                           # opcional: el [agente] de quien se une, si no tiene uno
  nombre: claude-code
  carpeta: raiz                   # Claude en la raíz del repositorio: su CLAUDE.md y sus skills
```

Quien se une desde otra máquina suya (su servidor) copia antes su clave (`~/.config/telar/bus.token`): la puerta
dice que ya tiene cuenta, y esa máquina entra con ella sin pedido nuevo. Nada secreto ni personal va ahí: cada persona genera su secreto en su máquina.

## Mapas de fechas: `.telar/fechas.yaml`

`telar fechas` ([contratos](contratos.md#telar-fechas---json)) lee sin que nadie lo diga la tabla `## Cronograma` de
cada unidad, por el nombre de cada columna. Un cronograma con otra forma (otras secciones, otros nombres de
columna, fechas escritas de otra manera, su propio vocabulario de estados, el proyecto nombrado por un código) se lee
con un **mapa**: dice qué secciones son cronogramas y de dónde sale cada campo. Lo que el mapa no dice se busca
por el nombre de la columna, como sin mapa.

```yaml
version: 1
mapas:
  sesiones:
    secciones: '^##\s+(Junio|Julio|Agosto)\s*$'   # una expresión, o una lista; «## Sesiones» vale tal cual
    campos:
      clase: sesion                                  # un valor: igual en todas las filas
      inicio: { columna: Fecha, formato: "EEE d-MMM", año: "frontmatter:actualizado" }
      hora: { columna: Hora, formato: "HH:mm", rango: "–" }
      titulo: "{Cliente} · {Programa}"               # una plantilla sobre las columnas
      responsable: { columna: Relator }
      estado: { columna: Estado, valores: { dictado: hecho, confirmado: pendiente } }
      proyecto: { columna: Proyecto, buscar: codigo } # 70 → la unidad cuyo frontmatter dice «codigo: 70»
documentos:                                          # qué documentos se leen con qué mapa (globs desde aquí)
  - { ruta: equipo/calendario.md, mapa: sesiones }
```

Un documento también puede decir su mapa en su frontmatter, `fechas: sesiones`, que manda sobre `documentos:`
(o el mapa entero ahí mismo, o `{ mapa: sesiones, secciones: "## Otra" }` para cambiarle algo). Los documentos que
nombra `documentos:` se leen además de los de las unidades.

| En un campo | Qué hace |
| --- | --- |
| `columna` | de qué columna sale (por su nombre, sin tildes ni mayúsculas; si no calza entero, por su comienzo) |
| `formato` | el patrón de fecha de Unicode (LDML, el de CLDR e `Intl`): `d-MMM` «17-nov», `EEE d-MMM` «mar 17-nov», `dd/MM/yyyy`, `d 'de' MMMM`, `HH:mm`. Sin él, `AAAA-MM-DD`, `DD-MM-AAAA`, `DD-mes` o un mes entero (`2026-08`) |
| `idioma` | el de los nombres de meses y días (`es` por defecto; `en`; otros con Babel instalado) |
| `rango` | el separador de una celda que trae inicio y fin («10:00–12:00», «3 al 5-jun»: lo que le falta a la primera mitad lo pone la segunda) |
| `año` | el de una fecha que no lo trae: un número, o `frontmatter:<clave>` (el año de esa clave del documento); si no, el año en curso |
| `valores` | lo que dice la celda → lo que significa (`dictado: hecho`), sin tildes ni mayúsculas |
| `buscar` | con `proyecto`: la clave del frontmatter de las unidades que dice ese valor |

Un `patron:` en el mapa lee listas en vez de tablas: cada línea de la sección que calza es una fila, y sus grupos con
nombre son sus columnas (`'^- (?P<inicio>\S+): (?P<titulo>.+)$'`). De qué proyecto es una fila sin `proyecto` en el
mapa: en un documento que no es el de una unidad, la de su enlace (`[Faro](../faro/README.md)`); si no, la que
contiene el documento.

`telar fechas probar <archivo>` dice con qué mapa se lee un documento, qué filas leyó y cuáles saltó y por qué. Un
`fechas.yaml` mal escrito no se lleva a los demás: va a las `fallas` de `telar fechas`. Con `[repos]`, cada repositorio
trae el suyo, con sus rutas relativas a sí mismo.

## Productos: `.telar/productos.yaml`

Qué unidades del perfil son **productos** (lo que el equipo vende: servicios, cursos, productos de software) y cómo
son sus **ideas**: las mejoras y expansiones que todavía no son trabajo comprometido. Lo leen `telar productos` y el
módulo productos (una lista, un backlog y un tablero kanban):

```yaml
productos:
  arquetipo: servicio            # las unidades de este arquetipo son productos
  nombre: servicios              # cómo los llama este equipo
  campos:                        # lo que se muestra de cada uno: {titulo}, {campo:X} (su tabla),
    area: "{ruta:-2}"            #   {frontmatter:x} (el de su documento) y {ruta:N} (la parte N de su carpeta,
    vigencia: "{frontmatter:vigencia}"   #   contada desde el repositorio; -1 es la última)
ideas:                           # todo opcional: estos son los valores de fábrica
  carpeta: backlog               # dentro de cada producto
  estados: [idea, evaluando, priorizada, en-curso, lanzada, descartada]
  backlog: [idea, evaluando]     # las sin compromiso
  tablero: [priorizada, en-curso, lanzada]   # las columnas del tablero
  campos: [valor, esfuerzo, origen, responsable]
  opciones: { valor: [alto, medio, bajo], esfuerzo: [alto, medio, bajo] }
  area_tareas: ""                # el `area` de las tareas que nacen de una idea ("" la de fábrica)
```

Cada idea es un archivo en la carpeta de su producto (`<producto>/backlog/I03.md`) con frontmatter de campos sueltos
(`titulo`, `estado`, los de `campos`, `creada`), su texto y su `## Historia`; se puede editar a mano. telar la
escribe con versión (no pisa un cambio ajeno) y cambia solo las líneas de los campos que cambian, más una línea en
su historia. Al crear la primera, deja un `README.md` en la carpeta.

**Ideas y tareas.** Una tarea que en realidad es una idea se lleva al backlog de un producto (en su menú, «al_backlog»,
o `telar productos desde-tarea T84 <producto>`): nace la idea con su título y su texto (`origen: tarea:T84`) y la
tarea queda descartada diciendo adónde fue; si la tarea no se puede cerrar, la idea no queda. Al revés, una idea
abre tareas operativas (`telar productos tarea idea:… "título"`, o en su menú): con `proyecto` en su producto y
`origen` en la idea, que las muestra mientras sigan abiertas y las anota en su historia. Una idea es también un
objeto (`telar objeto idea:<producto>/I03`): moverla, abrir una tarea, anotar. No commitea: lo escrito queda en el árbol de
trabajo del repositorio. Un `productos.yaml` mal escrito va a las `fallas` de `telar productos`.

## Varios repositorios

Con `[repos]` en la configuración, cada repositorio trae su propio perfil, con rutas relativas a sí mismo, y
telar los junta: los arquetipos de cada uno pasan a ser relativos a la raíz y llevan de qué repo vienen. Si
dos perfiles reconocen la misma carpeta, gana el del repo más profundo. Así un repositorio compartido con un
equipo describe sus carpetas para todos, y el perfil personal de quien lo tiene dentro de su repo de vida no
necesita repetirlas. Las acciones se suman; con el mismo nombre, gana la del repo más profundo.

## Sin perfil: la convención mínima

Un repositorio sin `.telar/perfil.yaml` no queda fuera: rige el **perfil de casa**, que
cubre las tres formas en que la gente guarda su trabajo, sin pedirle que declare nada.

```yaml
arquetipos:
  proyecto:           { ruta: "*/",        documento: README.md }   # carpetas de la raíz
  proyecto anidado:   { ruta: "*/*/",      documento: README.md }   # proyectos/…, projects/…
  repositorio:        { ruta: "README.md" }                         # un repo, un proyecto
```

Los tres leen lo mismo, y sin anclar, porque sin perfil no se sabe cómo titula este
repositorio sus secciones:

```yaml
    secciones:
      titulo:     { tipo: linea, encabezado: '^#\s+(.+)$' }
      estado:     { tipo: parrafo }                # el primer párrafo
      pendientes: { tipo: casillas, maximo: 6 }    # la primera lista de casillas
```

Es el `telar.perfil.PERFIL_MINIMO`. Sirve para el primer día en cualquier carpeta; el
perfil propio se escribe cuando eso ya no alcanza —y `telar init --perfil` lo propone
mirando el repositorio: qué rutas tienen README y con qué encabezados titula sus
secciones.

## Errores

Igual que la configuración: telar prefiere quejarse a adivinar. Una clave que no
existe en este documento, un `tipo` desconocido, una regex inválida, un `comando`
que es una cadena en vez de una lista, o una `ruta` que se sale de la raíz son
`ErrorDePerfil`, con la ruta de la clave en el mensaje (`arquetipos.proyecto.ruta:
…`). Un perfil a medias rompe todos los hilos a la vez, así que no se tolera a
medias.
