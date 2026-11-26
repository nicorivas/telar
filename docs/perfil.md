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

El frontmatter de cada unidad también se lee (`telar proyectos --json` lo trae, en `frontmatter`): un modo agrupa por
uno de sus campos las unidades que llama iniciativas (`agrupar_iniciativas = "{frontmatter:programa}"`,
[configuracion.md](configuracion.md)), con el mismo selector de `productos.yaml`. De una iniciativa se leen también
`estado`, `estado_desde`, `estado_nota` y `estado_fuente` (el vocabulario de `[iniciativas]`, en la configuración);
cambiar su estado desde telar escribe solo las dos primeras.

**Mudar unidades de una carpeta a otra.** Se declara el arquetipo nuevo con su ruta y se mueven las carpetas de a
poco: mientras dura, cada unidad es del arquetipo de la carpeta donde está, y una que esté en las dos (copiada y
todavía sin borrar) es dos unidades, cada una con su dirección y su hilo. Un hilo vinculado a la carpeta vieja sigue
vinculado a ella; la nueva se vincula aparte. Una tarea cuyo `proyecto:` apunta adentro de una unidad es de esa unidad
(la más honda que la contiene); una que apunta a la carpeta vieja ya borrada no es de ninguna: al mudar, se cambia
también el `proyecto:` de sus tareas.

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
  etiqueta: "{campo:Cliente} · {titulo}"    # «Grupo Norte · Adopción IA»
```

De un campo queda solo el nombre: sin lo que va entre paréntesis y cortado en la
primera raya, coma o punto y coma. Si un valor ya está dentro de otro no se repite (con
el título «Molino — Campaña de Ideas», el cliente «Molino» sobra), y un marcador
vacío se lleva su separador. Sin `etiqueta`, se muestra el título del documento.

El título se lee como se ve, sin las barras con que markdown escapa la puntuación:
`# 01\. Reconocimiento` (la barra evita que el número abra una lista) es «01.
Reconocimiento» en todas las vistas. Dentro de un `código` las barras se quedan.

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
| `compilados.yaml` | cómo se vuelve a generar lo compilado (lo que `.gitattributes` marca con `merge=telar-compilado`) y de qué fuentes sale: `telar hilo fusionar` lo corre cuando la rama de un hijo lo toca o toca sus fuentes, en vez de negarse por un choque en lo que sale de un comando, y `telar desplegar` avisa si no corresponde (abajo, «Lo compilado») | sí |
| `despliegue.yaml` | cómo se despliega en cada máquina donde vive: qué preparar, qué servicios reiniciar, qué hacer después y qué comprobar (`telar desplegar`; abajo, «El despliegue») | sí |
| `changelog.yaml` | que el CHANGELOG va por fragmentos: cada hijo con rama escribe su entrada en un archivo propio y `telar hilo fusionar` la pasa a `[Unreleased]` (abajo, «El CHANGELOG por fragmentos») | sí |
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

## Lo compilado: `.telar/compilados.yaml`

Un archivo que sale de un comando (un paquete de la página, un CSS armado) choca cada vez que dos ramas lo tocan, y no
se resuelve a mano: se toma cualquiera de las dos versiones y se vuelve a generar. Un repositorio lo declara en dos
partes. Qué es compilado, en `.gitattributes` (lo que git ya entiende):

```
src/web/app.js   merge=telar-compilado
```

Y cómo se genera, en `.telar/compilados.yaml`: cada comando, en su carpeta (desde la raíz; sin shell, como en una
terminal), en orden, y de qué sale (`fuentes`: rutas desde la raíz, como `si_cambia` del despliegue: `*` cruza
carpetas y `x/` es todo lo de adentro).

```yaml
comandos:
  - carpeta: web
    comando: npm run compilar
    fuentes: [web/src/, web/package.json]
```

Con eso, `telar hilo fusionar` no se niega por lo compilado: si la rama de un hijo lo toca, o toca sus `fuentes`,
fusiona en un worktree temporal, corre los comandos (con los `node_modules` de la carpeta del padre enlazados) y
commitea la fusión con lo generado (docs/contratos.md, `telar hilo <verbo> --json`). Las fuentes importan: una rama
que cambió el CSS y no lo compilado lo dejaría viejo en la base, y se desplegaría así. Sin `fuentes`, solo cuenta
tocar lo compilado. Como red, `telar desplegar` lo vuelve a generar en un worktree temporal del commit que despliega
(si lo que cambia toca las fuentes o lo compilado) y avisa si lo commiteado no corresponde (`compilados` en su
`--json`); no niega el despliegue. Y `telar hilo hijo --rama` deja definido el driver de git
`telar-compilado` solo para los worktrees del repositorio (en un archivo al lado de su `.git/config`, que este incluye
con `includeIf "gitdir:…/worktrees/"`): ahí un `git merge` de la base se queda con la versión de la rama y no se
detiene. En la carpeta principal no se define, y lo compilado sigue chocando como siempre: un `git pull` no deja un
compilado viejo sin que nadie lo vea.

## El despliegue: `.telar/despliegue.yaml`

`telar desplegar` deja corriendo lo que está en la rama principal en cada máquina donde vive el repositorio (esta y
las de `[remotos]`; docs/desarrollar.md, «Llevarlo a las máquinas»). Lo que es del repositorio lo dice él: qué hay
que hacer con su código en una máquina para que corra. Lo que es de cada máquina (dónde está el repositorio allá, si
usa systemd o launchd) no va aquí: sale de la configuración de quien despliega y de la máquina misma
(docs/configuracion.md, «`telar desplegar`»). Un repositorio sin este archivo no se despliega.

```yaml
rama: main                        # opcional: la que se despliega (main por defecto)

preparar:                         # antes de reiniciar, en la carpeta del repositorio de cada máquina, en orden
  - comando: bin/compilar
    si_cambia: [puente/]          # solo si cambió algo de esto desde lo que corre en esa máquina
    si_corre: mi-puente           # solo donde está instalado ese servicio (uno de los de abajo)

servicios:                        # lo que corre este código: se reinicia donde esté instalado (si no, se salta)
  - systemd: mi-puente            # su unidad de usuario en Linux (systemctl --user)
    launchd: com.ejemplo.puente   # su etiqueta en macOS (launchctl, gui/<uid>)
    si_cambia: [puente/, bin/]
  - systemd: telar-serve          # el de telar, para que vea las consultas nuevas de un módulo
    launchd: com.telar.serve

despues:                          # con el código nuevo ya corriendo
  - comando: telar agente instalar --si
    si_cambia: [agente/]

comprobar:                        # que quedó: en cada máquina, también en las que ya estaban al día
  - pagina: /pagina.json          # GET en la página de telar de esa máquina, con su llave
    igual: firma                  # este campo de su JSON, el mismo en todas las máquinas
    sigue: 15                     # y a 15 s de contestar, que conteste de nuevo (0 por defecto: no se pide otra vez)
  - comando: bin/estado           # o un comando, que salga con 0
    plazo: 10                     # segundos para que conteste (30 por defecto): el servicio puede estar arrancando
```

Un comando corre con bash en la carpeta del repositorio (en otra máquina, con el PATH de una sesión: `bash -lc` por
ssh), y uno que sale con algo distinto de 0 detiene el despliegue. `si_cambia` son rutas desde la raíz del
repositorio, con `*` (que también cruza carpetas) o terminadas en `/` (todo lo de adentro), contra lo que cambió desde
el último despliegue en esa máquina (`refs/telar/desplegado`); sin `si_cambia`, cualquier cambio cuenta. Una máquina
que ya corre el commit no prepara ni reinicia nada, y una en la que nunca se desplegó con `telar desplegar` lo hace
todo. Un servicio se nombra en uno de los dos sistemas o en los dos; `si_corre` lo nombra por cualquiera de sus
nombres.

`pagina` le pide la ruta a la página que sirve el `telar serve` de esa máquina, en su puerto de verdad (lo que dice su
`/salud`, `web`) y con su llave (`~/.config/telar/panel.llave`), que no sale de ella: `/pagina.json` dice qué página
sirve; `/api/…`, la API detrás de la página. Con `sigue`, se pide otra vez a esos segundos de la primera respuesta, y
si ya no contesta, el despliegue falla: un servicio que arranca y se cae a los pocos segundos pasaba la primera. El de
telar mismo está en su `.telar/despliegue.yaml`.
## El CHANGELOG por fragmentos: `.telar/changelog.yaml`

Dos ramas que escriben en el CHANGELOG chocan siempre: las dos agregan arriba, en `[Unreleased]`. Un repositorio que
declara `.telar/changelog.yaml` lo junta por fragmentos: el hijo con rama escribe su entrada en un archivo propio de la
carpeta (`changelog.d/<rama>.md`), y `telar hilo fusionar` la pasa a `[Unreleased]` y borra el archivo, en el mismo
commit de la fusión (docs/contratos.md, `telar hilo <verbo> --json`).

```yaml
archivo: CHANGELOG.md        # el CHANGELOG, desde la raíz
carpeta: changelog.d         # los fragmentos: cada .md de ahí, salvo su README.md
ancho: 120                   # opcional: el largo máximo de una línea del fragmento
negrita: true                # opcional: cada entrada empieza con su primera oración en negrita («- **…**»)
secciones: [Added, Changed, Deprecated, Removed, Fixed, Security]   # opcional: las que valen, en su orden
```

Un fragmento es un pedazo del CHANGELOG con una o más secciones, cada una con sus entradas: cada entrada empieza con
`- ` y sus líneas siguientes van sangradas en dos espacios. Cada sección va arriba de la suya en `[Unreleased]`; la
que falta se crea en el orden de `secciones`, y `[Unreleased]`, arriba de la primera versión, si tampoco está. Un
fragmento mal formado (otra sección, texto antes de la primera, una línea que no es entrada, más ancho que `ancho`)
hace que fusionar se niegue antes de tocar nada. Sin la declaración, fusionar hace lo de siempre.

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
