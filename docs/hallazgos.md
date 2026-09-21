# Hallazgos conocidos

Los dejó la revisión que acompañó a la construcción del esqueleto: una prueba de humo con
comandos reales y dos lecturas del árbol, una por portabilidad y otra por coherencia.

**Los 37 están arreglados** (20-sep-2026): dos bloqueantes, quince serios y veinte menores. Cada
uno queda escrito con su síntoma y dónde vivía, porque la lista también es la memoria de por qué
el código es como es. Tres se cerraron comprobando que ya no ocurrían; el resto, con código y
pruebas.

Arreglarlos destapó dos cosas que no estaban en la lista: el estado se mudaba solo a un tab ajeno
cuando el multiplexor reciclaba los ids —la reconciliación va ahora atada a una huella de la
sesión—, y unas pruebas de tmux que sí existían se perdieron al sobrescribir el archivo sin
mirarlo (se recuperaron del commit).

## [bloqueante] La configuración del proveedor de estado que documenta contratos.md no tiene camino de ejecución, y declararla rompe `telar doctor` — **arreglado**
**Dónde:** docs/contratos.md:97-101 y :165-169 · src/telar/ordenes/_comun.py:290-296 · src/telar/proveedores/estado.py:867-890

contratos.md enseña a configurar el proveedor de estado con `[proveedores.estado]` (cascada, marcas, maximo, meses) y el proveedor `comando` con `[proveedores.estado-externo]`. Ninguna de las dos cosas la lee nadie: `_comun.leer_ficha`, el único camino por el que la CLI arma una ficha, llama `prov_estado.leer(documento, arquetipo)` con las opciones por defecto y jamás mira `ctx.config`. `estado.obtener(cfg)` —la función que sí leería la configuración— no la llama nadie en todo el árbol, y además busca `cfg.nombre` en un REGISTRO cuyas llaves son "documento" y "comando", así que con `[proveedores.estado-externo]` nunca resolvería. Peor: como `config.proveedores` es una sola tabla compartida con los proveedores de ítems, declarar la sección del ejemplo hace que `telar doctor` salga con 1 («declarados y no registrados: estado») y que `telar hoy` y `telar pendientes --proveedores` reporten una falla permanente. La sección «El proveedor `comando`» de contratos.md, entera, describe algo que hoy no se puede encender.

**Arreglo propuesto:** Decidir dónde vive esa configuración y cablearla: o `_comun.leer_ficha` construye la fuente con `estado.obtener()` a partir de una clave propia (p. ej. `[estado]`, fuera de `[proveedores.*]`), o se saca de contratos.md la promesa hasta que exista. En cualquier caso, separar la tabla de los proveedores de estado de la de los proveedores de ítems: hoy comparten espacio de nombres y se pisan.

## [bloqueante] `telar agente instalar` escribe en el ~/.claude/settings.json real sin confirmar ni avisar antes — **arreglado**
**Dónde:** src/telar/ordenes/agente.py:209 (_instalar) y src/telar/agente/claude_code.py:190

Con TELAR_CONFIG, TELAR_ESTADO, TELAR_RAIZ, TELAR_MULTIPLEXOR y TELAR_SESION apuntando todos a temporales, es el único comando de telar que se sale del arenero: toma `self.ruta_ajustes()` (~/.claude/settings.json), lo reescribe con seis ganchos que apuntan al ejecutable desde donde se corrió —en mi caso un venv de /private/tmp— y recién después imprime dónde escribió. No hay confirmación, ni pregunta, ni impresión previa de la ruta. En esta corrida le metió a Nico seis hooks (SessionStart, UserPromptSubmit, Notification, PostToolUse, Stop, SessionEnd) que apuntaban a un venv temporal; si no lo hubiera revertido, al borrarse el scratchpad cada evento de Claude Code habría invocado un binario inexistente. Para un paquete que se publica y cuyo README promete «no writing to your work repository unless you ask», el verbo `instalar` no alcanza como consentimiento cuando el destino es la configuración global de otro programa.

**Arreglo propuesto:** Que `instalar` sin banderas imprima la ruta y el diff y pida sí/no, con `--si` para saltarlo (y `--json` implicando `--si`). Rechazar o avisar fuerte cuando el ejecutable a escribir no esté en una ruta estable (venv temporal, /tmp): `shutil.which('telar')` fuera del PATH permanente es señal de prueba, no de instalación. Y documentar `--seco` y `--ajustes RUTA` en el README, que hoy solo viven en el docstring.

## [serio] UnicodeEncodeError con traceback si la salida no es UTF-8 — **arreglado**
**Dónde:** src/telar/ordenes/doctor.py:58, src/telar/ordenes/pendientes.py:146 y :152, src/telar/ordenes/_comun.py:121-126 (SIMBOLO)

Toda la CLI imprime ·, ✓, ✗, ☐, ▣, ●, ○ y «». Si stdout no codifica UTF-8, el print revienta con un stack trace de Python en vez de un error legible. Verificado: `PYTHONIOENCODING=ascii telar --raiz ejemplo pendientes --repo` → «UnicodeEncodeError: 'ascii' codec can't encode character '\xb7' in position 14»; con latin-1 → «can't encode character '▣'»; `telar doctor` cae igual en doctor.py:58. En Linux/macOS con LC_ALL=C Python coacciona a UTF-8 y se salva, pero cualquier wrapper que fije PYTHONIOENCODING, una consola cp1252 o un entorno que fuerce la codificación mata todas las órdenes que dibujan.

**Arreglo propuesto:** En cli.py:main(), antes de despachar: sys.stdout.reconfigure(errors='replace') (y stderr), o un juego de símbolos ASCII de reserva elegido según sys.stdout.encoding.

## [serio] El driver de zellij no declara ni verifica versión mínima del multiplexor — **arreglado**
**Dónde:** README.md:31, src/telar/mux/zellij.py:65 (VERSION_PROBADA), src/telar/ordenes/doctor.py:104-118 (_multiplexor)

README.md:31 solo pide «a terminal multiplexer (tmux or zellij)», sin piso de versión. zellij.py habla por acciones recientes de la CLI —current-tab-info, go-to-tab-by-id, close-tab-by-id, write-chars -p— y «0.45» vive únicamente en una constante interna que jamás se comprueba. doctor solo hace shutil.which(): en una máquina con un zellij de distro (0.39-0.42) marca ✓ multiplexor y después cada orden falla con el error crudo de la CLI, sin decir que el problema es la versión. Esta máquina tiene zellij 0.45.1 y tmux 3.7c, ambos muy por delante de lo que trae cualquier distro estable, así que el desarrollo no ve el problema. (El camino tmux sí es seguro: todos los formatos que usa —#{window_id}, #{pane_current_command}…— existen desde tmux 1.8.)

**Arreglo propuesto:** Correr `zellij --version` / `tmux -V` en doctor y comparar contra un piso declarado; escribir ese piso en README.md:31 junto a «Python 3.11+».

## [serio] «pip install telar» y la sección «Try it» del README no se componen: ejemplo/ y docs/ no viajan en la distribución — **arreglado**
**Dónde:** README.md:26 vs :38-43, y pyproject.toml:35-40

El sdist y el wheel (verificado construyéndolos) contienen solo src/telar, LICENSE, NOTICE, README y metadatos. Quien siga el README —`pip install telar`, y tres líneas más abajo `telar --raiz ejemplo perfil`— no tiene carpeta ejemplo/: la orden falla o cae a la convención mínima sin explicar por qué. Además, ese README es el long_description de PyPI, donde los ~10 links relativos a docs/*.md (líneas 20, 68, 69, 86-92) apuntan a pypi.org y dan 404. Y varios mensajes de error de la propia CLI mandan a docs/perfil.md y docs/contratos.md, que un usuario de pip no tiene en ninguna parte.

**Arreglo propuesto:** O empaquetar ejemplo/ y docs/ como package data, o que la sección «Try it» diga explícitamente «desde un clon» y que los links del README sean absolutos a github.com/nicorivas/telar.

## [serio] La extensión de VS Code es impublicable tal como está: publisher TODO y URL de repo contradictoria — **arreglado**
**Dónde:** vscode/package.json:6, :15, :19, :21

`publisher: "TODO-publisher"` y repository.url / bugs.url / homepage apuntando a github.com/TODO-publisher/telar. `vsce publish` publicaría bajo un publisher inexistente, y la ficha del Marketplace enlazaría a un repo que no existe. Además contradice pyproject.toml:31-32, que sí declara el repo real (github.com/nicorivas/telar). Está avisado en vscode/README.md:108-110, pero el archivo sigue mintiendo, y cualquiera que clone y corra `npm run package` produce un .vsix con metadatos falsos.

**Arreglo propuesto:** Poner el publisher real y github.com/nicorivas/telar en los cuatro campos, o dejar el TODO pero hacer que el script `package` falle si lo encuentra.

## [serio] mux/zellij.py no implementa la interfaz de mux/base.py: le faltan 17 de 27 miembros — **arreglado**
**Dónde:** src/telar/mux/zellij.py:136 (class Zellij) frente a src/telar/mux/base.py:128 (MultiplexorBase) y src/telar/mux/tmux.py:148 (class Tmux)

base.py:21-23 dice «Quien escriba un multiplexor nuevo hereda de `MultiplexorBase`» y tmux.py:1 se llama «la implementación de referencia de `telar.mux.base.MultiplexorBase`». `Zellij` no hereda de ella y solo cumple el protocolo estrecho de `telar.mux.Multiplexor`. Verificado: `issubclass(Zellij, MultiplexorBase)` es False y le faltan `tabs, tab_activo, ir_a_tab, crear_tab, renombrar_tab, cerrar_tab, panes, pane_de, pane_activo, enfocar_pane, escribir_pane, abrir_pane, cerrar_pane, mover_pane, buscar_tab, hilo_de, disponible`. Todo el vocabulario de paneles —que base.py:12-19 justifica como imprescindible para reconocer al agente y para escribirle— existe solo en tmux. La divergencia ya obligó a duck-typing en producción: `agente/base.py:249-268` prueba primero `mux.panes()` (objetos `Pane`) y después `mux.paneles()` (diccionarios crudos de zellij), y lo documenta como «las dos formas que hay hoy de listar paneles».

**Arreglo propuesto:** Hacer que `Zellij` herede de `MultiplexorBase` e implemente los primitivos (`tabs`, `panes`, `crear_tab`, `escribir_pane`…), dejando que los derivados salgan gratis; `paneles()` y `reemplazar()` quedan como extras propios de zellij. Mientras tanto, `agente/base.py:249-268` puede borrar la rama de diccionarios crudos.

## [serio] zellij no tiene la guardia de salto de línea que sí tiene tmux: `escribir` sin enviar puede enviar — **arreglado**
**Dónde:** src/telar/mux/zellij.py:384-403 frente a src/telar/mux/tmux.py:421-433

tmux.py:424-428 rechaza un texto con `\n` o `\r` cuando `enviar=False` («el salto ES el ↩»). `Zellij.escribir` no comprueba nada: manda el texto tal cual con `write-chars`, y un salto en la entrada de un agente es un Enter. Verificado: la misma llamada levanta ErrorDeMux en tmux y pasa en silencio en zellij. Lo usa `telar pendiente <ref>` (ordenes/pendiente.py:78), cuya promesa escrita en contratos.md:358-360 es «telar **escribe** la frase en la entrada del agente y no la manda. Apretar Enter es de la persona», y que devuelve `"enviado": false` en el JSON aunque la frase se haya ejecutado. `--texto` es texto libre del usuario, y el `titulo` de un proveedor `comando` tampoco está saneado.

**Arreglo propuesto:** Mover la guardia a `MultiplexorBase.escribir` (o a un helper de `mux/base.py`) para que rija en las dos implementaciones, en vez de vivir dentro de `Tmux.escribir_pane`.

## [serio] `telar hoy` ordena y muestra la agenda por reloj de pared ajeno cuando el proveedor trae zona — **arreglado**
**Dónde:** src/telar/ordenes/pendientes.py:92 · src/telar/ordenes/hoy.py:61 y :97

`de_proveedores` emite `cuando` con `item.cuando.isoformat(timespec="minutes")`, y los eventos de calendario son datetimes con zona (calendario.py:78-81 lo declara explícito). Después `hoy.py:61` ordena la agenda comparando esas cadenas y `hoy.py:97` saca la hora cortando `[11:16]`. Con un proveedor de tipo `comando`, verificado: una reunión a las 09:00+02:00 (04:00 en Santiago) se imprime «09:00» y después de otra de las 08:00 locales. Además el valor sale como `'2026-09-18T09:00+02:00'`, contra contratos.md:231-232, que promete «ISO de la máquina, **sin zona**». El mismo campo mezcla naive (tareas, `datetime.combine(vence, time.min)`) y aware (calendario).

**Arreglo propuesto:** Normalizar en `de_proveedores`: `item.cuando.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")`, y ordenar por el datetime, no por la cadena. `calendario.DeICS` ya convierte a local; el que no lo hace es `_hora` (calendario.py:603-610) en la rama `comando`.

## [serio] `ruta` y `ficha.documento` salen relativas cuando la raíz es relativa, contra el contrato — **arreglado**
**Dónde:** docs/contratos.md:228 · src/telar/cli.py:154-158 · src/telar/config.py:120-123 y :205-206

contratos.md:228 promete «`ruta` es absoluta (sirve para `cd`)». Ni `--raiz` ni `TELAR_RAIZ` ni la clave `raiz` del TOML resuelven la ruta: solo `expanduser()`. Verificado con el comando que el propio README.md:40-42 le propone al usuario: `telar --raiz ejemplo hilos --json` devuelve `ruta: "ejemplo/proyectos/faro"` y `ficha.documento: "ejemplo/proyectos/faro/README.md"`. La extensión de VS Code ya se topó con esto y lo documenta como límite propio en vscode/src/cli.ts:184-197 en vez de tratarlo como un fallo de telar.

**Arreglo propuesto:** Resolver la raíz una sola vez al construir la Config (`Path(...).expanduser().resolve()`) en `cli.py:158`, `config._ruta` y `config._entorno`. El valor por defecto ya es absoluto (`Path.cwd()`), así que la única incoherencia es la raíz dada a mano.

## [serio] `relativa` puede venir absoluta cuando la carpeta del hilo cae fuera de la raíz — **arreglado**
**Dónde:** src/telar/ordenes/_comun.py:137-143 · docs/contratos.md:228-229 · vscode/src/cli.ts:190-198

`ruta_relativa` devuelve `str(ruta)` cuando `relative_to` falla, es decir cuando la carpeta no cuelga de la raíz. Eso pasa en el caso más común de todos: un tab abierto en cualquier directorio fuera del repositorio de trabajo. Verificado con zellij sobre una sesión real: `"relativa": "/private/tmp/telarprueba"`. contratos.md:228-229 dice que `relativa` es «relativa a la raíz del repositorio» y que se usa «Vacío, no `null`, cuando no hay». `vscode/src/cli.ts:192` hace `path.join(raiz, h.relativa)` confiando en esa promesa.

**Arreglo propuesto:** Devolver cadena vacía cuando la ruta cae fuera de la raíz, y dejar el camino absoluto solo en `ruta`; si el fallback existe para mostrar algo, que sea el propio `ruta` en la vista de terminal, no el campo `relativa` del contrato.

## [serio] `vinculado` dice `true` para un hilo que nadie vinculó — **arreglado**
**Dónde:** src/telar/modelo.py:102-103 y :118-120 · src/telar/mux/base.py:306-324 · src/telar/estado.py:278

`Hilo.ruta` está documentada como «carpeta del repositorio de trabajo asociada; None si el hilo no está vinculado», y `vinculado` es simplemente `ruta is not None`. Pero el multiplexor rellena `ruta` con el `cwd` del panel (base.py:313-324 y zellij.py:291-292), y `vestir` (estado.py:278) hace `ruta=ruta or hilo.ruta`, así que el cwd sobrevive cuando no hay vínculo. Verificado con zellij: un tab recién creado con cwd `/private/tmp/telarprueba` sale con `"vinculado": true` y `"arquetipo": ""`. La consecuencia visible es `telar hilo ver`, que imprime la carpeta como si fuera el vínculo, y la vista de la extensión, que decide con ese campo. El campo mezcla dos preguntas distintas: «¿el usuario decidió una carpeta?» y «¿el panel tiene un cwd?».

**Arreglo propuesto:** Separar los dos datos en el modelo (`ruta` = el vínculo decidido, `cwd` = lo que dice el panel), o calcular `vinculado` contra `est.vinculos()` en vez de contra `ruta`. Hoy no hay forma de distinguirlos desde el JSON.

## [serio] La plantilla que escribe `telar init` sugiere un nombre de proveedor que hace fallar a `telar doctor` — **arreglado**
**Dónde:** src/telar/ordenes/init.py:54-57 · src/telar/ordenes/_comun.py:266-278 · docs/configuracion.md:78-79

`asegurar_proveedores` importa `telar.proveedores.<nombre de la sección>`, así que el nombre de la sección tiene que ser el nombre del módulo. Eso no está escrito en ninguna parte: docs/configuracion.md:78-79 presenta `proveedores.<n>` como un nombre libre. La plantilla que `telar init` deja en la configuración del usuario trae comentado `# [proveedores.agenda]`; verificado: al descomentarla, `telar doctor` sale con 1 y dice «declarados y no registrados: agenda», con un arreglo equivocado («instala el paquete que los registra»).

**Arreglo propuesto:** Cambiar el ejemplo de la plantilla a `[proveedores.calendario]` (que sí existe) y documentar en configuracion.md que el nombre de la sección es el del proveedor, no una etiqueta libre. Si se quiere permitir varias instancias, hace falta una clave `proveedor = "calendario"` separada del nombre de sección.

## [serio] `desinstalar` (y un segundo `instalar`) pisan el respaldo con la versión ya modificada — **arreglado**
**Dónde:** src/telar/agente/claude_code.py:254-268 (_escribir), líneas 260-261

`_escribir` siempre copia el archivo ACTUAL a `<nombre>.telar.bak` antes de reescribirlo, sin mirar si ya hay un respaldo. Comprobado: tras `instalar`, el .bak tenía el settings.json original (3894 B); tras `desinstalar`, el mismo .bak pasó a tener la versión CON los ganchos de telar (5848 B). El único respaldo del estado previo a telar queda destruido por la propia orden que deshace telar. Lo mismo pasa con dos `instalar` seguidos. La red de seguridad se come a sí misma justo en el escenario en que hace falta. Se agrega que el respaldo se escribe con la umask por defecto: el settings.json era -rw------- (0600) y el .telar.bak salió -rw-r--r-- (0644), o sea que una configuración privada termina copiada legible por todos.

**Arreglo propuesto:** No pisar un respaldo existente: si `<nombre>.telar.bak` ya está, escribir `<nombre>.telar.<timestamp>.bak`, o directamente no respaldar en `desinstalar` (que solo quita lo propio y es idempotente). Y crear el respaldo con los permisos del original: `os.chmod(respaldo, ruta.stat().st_mode & 0o777)` justo después de escribirlo, o `shutil.copy2`.

## [serio] Renombrar un tab desde el multiplexor huérfana todo el estado, inventa un hilo fantasma y bloquea la recuperación — **arreglado**
**Dónde:** src/telar/estado.py (todo el estado va indexado por nombre), src/telar/estado.py:313 (partir), src/telar/ordenes/hilos.py:57

El estado —vínculo, prioridad, atención, archivado— se guarda con el NOMBRE del tab como llave (vinculos.json: {"arboleda": "proyectos/arboleda"}), y el nombre del tab en tmux lo cambia cualquiera con prefix + coma, que es la forma natural de renombrar una ventana. Comprobado con `tmux rename-window arboleda arb2`: (a) la atención anotada se queda colgada del nombre viejo y el tab vivo pierde su símbolo; (b) el vínculo y la prioridad también, así que el tab vivo deja de apuntar a su proyecto; (c) aparece un hilo FANTASMA «arboleda» que no existe en tmux, con la prioridad y el vínculo puestos; (d) `partir()` separa por `archivado`, no por `vivo`, así que el fantasma entra en `vivos` y la cabecera anuncia «4 hilos» con tres ventanas abiertas —lo mismo en `telar doctor`, que reporta vínculos y atenciones de tabs que no existen—; (e) y la salida está cerrada: `telar hilo renombrar arboleda --hilo arb2`, que es lo que uno haría para recuperar el estado, responde «ya hay un hilo llamado «arboleda»», porque el fantasma ocupa el nombre. El único modo de volver es editar los JSON a mano. El README vende «held together across restarts», y basta un renombre para que no.

**Arreglo propuesto:** Dos piezas. Primero, dejar de contar como vivo lo que no lo está: que la cabecera de `hilos` y el conteo de `doctor` usen `tel.vivo(h)` y no `partir()`, y que el fantasma se muestre en su propia sección. Segundo, poder reconciliar: si un tab vivo no tiene entrada de estado pero su cwd coincide con el vínculo de un hilo no vivo, ofrecer adoptarlo (`telar hilo adoptar`, o que `renombrar` acepte un nombre ocupado por un hilo muerto y lo fusione). Lo de fondo, si vale el cambio: guardar el estado bajo una llave estable —el id del multiplexor más la ruta— y dejar el nombre como etiqueta.

## [serio] `telar ficha` imprime dicts crudos de Python en las secciones de tipo lista y tabla — **arreglado**
**Dónde:** src/telar/ordenes/ficha.py:123-131 (_dibujar), llamada desde la línea 111

La ficha de faro muestra literalmente: «· {'texto': 'El electricista confirma si el motor viejo sirve de repuesto', 'cuando': None, 'ori» y «· {'que': 'Empezó', 'cuando': '2026-03-02', 'origen': 'campos'}». `_dibujar` aplica `str(v)` a cada elemento, y el proveedor de estado entrega las secciones `lista` y `tabla` como listas de diccionarios, no de strings. Le pasa a ESPERANDO y a HITOS, que son justamente las dos secciones que contestan «quién me tiene frenado» y «cuándo entrego». Ocurre con el perfil de ejemplo que trae el propio repo, en la vista principal de la herramienta: es lo primero que va a ver quien pruebe telar.

**Arreglo propuesto:** En `_dibujar`, tratar el dict con forma conocida: si el elemento es un dict, imprimir su campo de texto (`texto` o `que`) y colgarle la fecha si trae `cuando` —«· El electricista confirma… » / «· Entrega — 2026-06-30»—, y caer a `str(v)` solo para lo que no reconozca. Y agregar una prueba de `telar ficha` en modo texto contra ejemplo/proyectos/faro, que hoy no existe (test_ordenes.py solo ejercita el --json).

## [serio] El multiplexor por defecto, tmux, no tiene ninguna prueba — **arreglado**
**Dónde:** pruebas/ — hay test_mux_zellij.py (33 pruebas) y no hay test_mux_tmux.py; src/telar/mux/tmux.py son 535 líneas

tmux es el valor por defecto de `multiplexor` en config.py y la propia cabecera de tmux.py se presenta como «la implementación de referencia», pero de los 407 tests ninguno lo toca: `grep -l tmux pruebas/*.py` solo devuelve menciones de paso en test_config, test_agente y un comentario de test_ordenes. Todo lo delicado de ese archivo —el parseo por \x1f con recuento de campos, la traducción de id/índice/nombre a objetivo, `_linea` citando palabra por palabra para que no haya inyección de shell, `mover_pane` con sus tres destinos, `switch-client -c <tty>`— está sin red. El propio ci.yml lo admite en un comentario: «El multiplexor no lo usan las pruebas de hoy, pero las del mux sí lo van a necesitar». Instala tmux en CI y no lo usa. En esta corrida todo lo que probé a mano funcionó, así que no es un bug: es que la parte que puede romperse en silencio al cambiar de versión de tmux es la que nadie vigila.

**Arreglo propuesto:** Escribir pruebas/test_mux_tmux.py con dos capas: unitarias sobre las funciones puras (_linea, _tamano, _banderas, _tab, _pane_desde con campos de más y de menos), y de integración contra un tmux real levantando una sesión con nombre propio y `skipUnless(shutil.which('tmux'))`, que crean tabs, renombran, mueven un panel entre tabs y cierran la sesión en tearDown. El CI ya tiene tmux instalado para recibirlas.

## [menor] doctor trunca con slice negativo en terminales de menos de 20 columnas — **arreglado**
**Dónde:** src/telar/ordenes/doctor.py:58

`r['dice'][:ancho - 20]` con ancho = get_terminal_size().columns. Con COLUMNS=20 exacto el slice es [:0] y la columna de valor sale VACÍA; con menos de 20 el índice es negativo y Python recorta por el FINAL, borrando silenciosamente los últimos caracteres. Verificado con COLUMNS=10: doctor imprime «✓ raíz» y «✓ multiplexor» sin ningún valor al lado, y «sin archivo; todo por defecto (se buscaría en /Users/…/co» cortado a media palabra. Un pane angosto (que es justo el caso de uso: telar vive en una barra lateral) da un diagnóstico ilegible.

**Arreglo propuesto:** `r['dice'][:max(ancho - 20, 20)]`, igual que ya hace pendientes.py:151 con `resto = max(ancho - 34 - len(cola), 20)`.

## [menor] package-lock.json ignorado y la extensión nunca se compila en CI — **arreglado**
**Dónde:** vscode/.gitignore:4, .github/workflows/ci.yml (sin job de node)

El lockfile está en .gitignore, así que en otra máquina `npm install` resuelve typescript ^5.5.0, @vscode/vsce ^3.2.0 y ovsx ^0.10.0 a lo que sea más nuevo ese día: la compilación de la extensión no es reproducible. Y el workflow solo corre Python en ubuntu; ningún paso hace `npm ci && npm run compile`, de modo que un TypeScript roto se sube sin que nadie se entere. (Hoy compila: lo verifiqué copiando vscode/ fuera del repo, tsc sale 0.)

**Arreglo propuesto:** Quitar package-lock.json del .gitignore y commitearlo; agregar un job `vscode` al ci.yml con `npm ci` + `npm run compile`.

## [menor] CI nunca se dispara en la rama que el repo tiene de verdad — **arreglado**
**Dónde:** .github/workflows/ci.yml:5

`on.push.branches: [main]`, pero la única rama del repo es `master` (y todavía sin ningún commit: `git log` responde «your current branch 'master' does not have any commits yet»). Al hacer el primer push a master, el CI de push no corre nunca y el repo aparenta estar verde sin haberse probado jamás en Linux.

**Arreglo propuesto:** Renombrar la rama a main antes del primer push (`git branch -m master main`), o agregar master a la lista.

## [menor] El proveedor de estado por comando corre el programa del usuario sin cerrarle stdin — **arreglado**
**Dónde:** src/telar/proveedores/estado.py:777-783

Comando.leer() llama subprocess.run(...) sin `stdin=subprocess.DEVNULL` y sin `env=`. Los otros tres caminos que corren programas de afuera sí lo pasan (proveedores/tareas.py:586, proveedores/calendario.py:576). Un comando de estado que lea stdin se queda con la entrada de la terminal del usuario y solo muere al vencer el timeout, colgando la lectura de la ficha; y a diferencia de los otros dos no recibe ninguna variable marcadora en el entorno. Es una inconsistencia entre cuatro sitios que deberían ser idénticos.

**Arreglo propuesto:** Agregar `stdin=subprocess.DEVNULL` (y decidir si va `env=` como en tareas.py:585) en estado.py:777.

## [menor] _atajo() abrevia el hogar por prefijo de texto, no por componente de ruta — **arreglado**
**Dónde:** src/telar/ordenes/init.py:204-208 (usado en :120-121)

`return "~" + texto[len(hogar):] if texto.startswith(hogar) else texto`. En una máquina donde otra ruta empiece con el string del hogar, el config.toml que escribe `telar init` sale corrupto. Verificado con Path.home() = /Users/nico: '/Users/nicolas/trabajo' → '~las/trabajo' y '/Users/nico2/repo' → '~2/repo'. Path('~las/trabajo').expanduser() no expande nada, así que raiz o estado quedan como una ruta relativa literal y doctor después dice «la raíz no existe». Pasa en cualquier caja multiusuario (/home/nico y /home/nico2) o con un usuario cuyo nombre sea prefijo de otro directorio hermano.

**Arreglo propuesto:** Usar `ruta.relative_to(Path.home())` dentro de try/ValueError, en vez de comparar strings.

## [menor] El instalador de ganchos congela una ruta absoluta de telar y doctor no detecta cuando muere — **arreglado**
**Dónde:** src/telar/agente/base.py:372-383 (ejecutable_telar), src/telar/ordenes/doctor.py:264-320 (_ganchos)

`shutil.which("telar")` escribe la ruta absoluta del binario dentro del settings.json del usuario: si telar se instaló en un venv (que es justo lo que recomienda README.md:27, `pip install -e .`), los seis ganchos quedan apuntando a ese venv. Rehacerlo, moverlo o reinstalar con pipx deja los seis ganchos apuntando a un ejecutable muerto, y como Claude Code se los traga en silencio la atención simplemente deja de actualizarse. doctor solo mira si hay huellas («nunca se anotó un cambio de foco»), nunca resuelve el comando anotado, así que da un diagnóstico que manda a arreglar lo que ya estaba puesto. La decisión de escribir la ruta absoluta está razonada en el docstring y es correcta; lo que falta es el chequeo.

**Arreglo propuesto:** En doctor._ganchos, leer los ganchos instalados del settings.json y verificar que el ejecutable que nombran todavía exista; si no, decir «los ganchos apuntan a X, que ya no está: telar agente instalar».

## [menor] pyproject usa la forma de licencia que setuptools deja de soportar en febrero de 2027 — **arreglado**
**Dónde:** pyproject.toml:10 y :19

`python -m build` avisa dos veces: «WARNING `project.license` as a TOML table is deprecated […] By 2027-Feb-18, you need to update your project and remove deprecated calls or your builds will no longer be supported» y «License classifiers are deprecated» por el clasificador `License :: OSI Approved :: MIT License`. Faltan cinco meses. En una máquina con setuptools reciente hoy solo avisa; después de esa fecha el build del paquete falla, y `requires = ["setuptools>=68"]` no fija techo que lo evite.

**Arreglo propuesto:** `license = "MIT"` (expresión SPDX) más `license-files = ["LICENSE", "NOTICE"]`, borrar el clasificador, y subir el piso a `setuptools>=77`.

## [menor] El README de la extensión enlaza fuera del .vsix — **arreglado**
**Dónde:** vscode/README.md:33 y :36

La línea 33 dice `[telar](../README.md)` y la 36 remite a `docs/perfil.md`. El .vscodeignore empaqueta solo la carpeta vscode/, así que en la ficha del Marketplace —que es donde ese README se lee— los dos apuntan a nada. Es el único documento que ve alguien que instala la extensión sin clonar el repo, y su primer requisito («telar on your PATH») lleva a un link muerto.

**Arreglo propuesto:** Cambiarlos por URLs absolutas al repo, igual que habrá que hacer con el publisher.

## [menor] El `id` del hilo está mal descrito en tres documentos, y uno apoya en eso una decisión de diseño — **arreglado**
**Dónde:** src/telar/modelo.py:96-97 · docs/contratos.md:252-253 · docs/estado.md:35-36

Los tres dicen «el índice del tab en tmux, el nombre en zellij». El código dice lo contrario y lo argumenta largo: tmux.py:16-19 usa `window_id` («`@3`», estable), zellij.py:18-21 usa el TAB_ID numérico y explícitamente **no** el nombre. Verificado en vivo: tmux devuelve `"@3"`, zellij devuelve `"0"`. contratos.md se contradice consigo mismo en cuatro líneas: el ejemplo de :243 muestra `"id": "@3"` y el texto de :252 dice que es el índice. Y docs/estado.md:35-36 usa esa afirmación falsa («el `id` es posicional en tmux») como la razón de indexar el estado por nombre: la justificación del diseño se apoya en un hecho que dejó de ser cierto.

**Arreglo propuesto:** Corregir las tres frases. Si la razón de indexar por nombre sigue siendo válida (renombrar es del usuario, el id no se lee), reescribir el argumento de estado.md sobre esa base y no sobre la estabilidad del id.

## [menor] `telar agente --json` produce cuatro formas que docs/contratos.md no documenta — **arreglado**
**Dónde:** src/telar/ordenes/agente.py:141-148, :249-255, :282-293 y :330 · docs/contratos.md:213-218 · src/telar/cli.py:66-67

cli.py:66-67 y contratos.md:215-218 afirman que «lo que imprime con `--json` es un contrato: está escrito en docs/contratos.md», y la página tiene una sección «Orden por orden» que cubre hilos, ficha, hilo, pendientes, pendiente, hoy, atencion, tiempo, doctor, config, perfil, init y tejer. Falta `agente`, que es la orden con más consumidores automáticos (la corren los ganchos del agente) y que emite cuatro objetos distintos según el verbo: aviso (`aplicado/evento/hilo/atencion/conversacion/conversaciones`), instalar/desinstalar (`ruta/ganchos/reemplazados/escrito/respaldo`), ver (`agente/hilo/atencion/ganchos/ajustes/conversaciones`) y retomar/nuevo (`hilo/comando`).

**Arreglo propuesto:** Agregar la entrada «`telar agente <verbo> --json`» a docs/contratos.md con las cuatro formas, o quitar de cli.py:66 la promesa de que están todas escritas.

## [menor] `Estado.foto()` existe para evitar lecturas partidas y el único camino que dibuja no la usa — **arreglado**
**Dónde:** src/telar/ordenes/_comun.py:209-230 · src/telar/estado.py:699-717 · docs/estado.md:216-218

docs/estado.md:216-218 presenta `Estado.foto(tope=…)` como «el puente: lee todo de una vez y bajo candado… para que nadie dibuje media lista de antes y media de después», y el ejemplo de estado.md:222-228 la usa. `_comun.tejer` —por donde pasan hilos, hoy, ficha, pendientes, pendiente y accion, es decir todo lo que dibuja— llama en cambio a `est.vinculos()`, `est.prioridades()`, `est.archivados()`, `est.atenciones()`, `est.sesiones()` y lee `foco.log` por separado, sin candado, exactamente el patrón que `foto()` fue escrita para evitar. De paso, `foto()` acota el tiempo con `desde` y `hasta` y `_comun.tejer` solo con `desde`.

**Arreglo propuesto:** En `_comun.tejer`, reemplazar las seis lecturas por `est.foto(tope=config.intervalos.foco_maximo)` y pasarlo a `vestir(**foto)`, que es justo la firma que `foto()` devuelve.

## [menor] configuracion.md dice que el estado guarda una caché de fichas; estado.md dice lo contrario y el código tampoco la tiene — **arreglado**
**Dónde:** docs/configuracion.md:31 · docs/estado.md:231-233 · src/telar/estado.py:78-87 · src/telar/config.py:80-81

configuracion.md:31 describe `estado` como «el estado derivado (caché de fichas, semáforo, tiempo por hilo)», y config.py:80-81 repite «(caché, semáforo, tiempo)». docs/estado.md:231-233, en cambio, es explícito: «Lo que el estado no guarda: **La ficha.** Se lee del documento, que es la fuente. Guardarla sería tener dos verdades y una desactualizada». `ARCHIVOS` (estado.py:79-87) confirma a estado.md: vinculos, prioridades, archivados, atencion, sesiones, paneles, y nada de fichas.

**Arreglo propuesto:** Quitar «caché de fichas» de configuracion.md:31 y «caché» de config.py:80; estado.md tiene razón.

## [menor] `viva: true` con `aviso` no vacío, contra lo que promete el contrato — **arreglado**
**Dónde:** src/telar/ordenes/_comun.py:201-206 · docs/contratos.md:303-305

contratos.md:303-305 dice «con `aviso` no vacío, `viva` es `false` y los hilos son los que telar recuerda». En `_comun.tejer` la asignación `viva = mux.viva()` ocurre antes de `mux.hilos()`, dentro del mismo `try`: si la sesión está viva pero listarla falla, queda `viva=True` y `aviso` lleno. Verificado con un multiplexor de prueba. Es exactamente el caso que `doctor.py:124-127` sí contempla («viva, pero no pude listarla»).

**Arreglo propuesto:** Poner `viva = False` en el `except`, o separar las dos llamadas en dos `try` y decidir explícitamente qué informa cada una.

## [menor] docs/agentes.md lista siete momentos de Claude Code y dice que instala seis ganchos — **arreglado**
**Dónde:** docs/agentes.md:156-168 · src/telar/agente/claude_code.py:65-73 y :76-84

La tabla «Traduce así» tiene siete filas (SessionStart, UserPromptSubmit, Notification, PostToolUse, SubagentStop, Stop, SessionEnd) y la frase siguiente dice «Los seis ganchos que instala». Las dos cosas son ciertas por separado —`EVENTOS` traduce siete momentos, `GANCHOS` instala seis— pero el texto no dice que `SubagentStop` se entiende y no se engancha, así que un lector cuenta siete y encuentra seis en su settings.json.

**Arreglo propuesto:** Marcar en la tabla la fila que no se instala, o instalar también `SubagentStop` si la omisión no es deliberada.

## [menor] La implementación de referencia del multiplexor es la única sin pruebas — **arreglado**
**Dónde:** pruebas/ (existe test_mux_zellij.py, no hay test_mux_tmux.py ni prueba de mux/base.py) · .github/workflows/ci.yml

tmux.py (535 líneas, «la implementación de referencia») y mux/base.py (366 líneas, el contrato y todos los derivados: `buscar_tab`, `pane_de`, `pane_activo`, `hilo_de`, `hilos`, `escribir`) no tienen ningún archivo de pruebas; la única implementación con suite es la que no cumple la interfaz. El comentario de ci.yml lo admite («El multiplexor no lo usan las pruebas de hoy») y sin embargo instala tmux en CI. Ninguna de las divergencias de este informe entre tmux y zellij la habría cazado la suite: los 407 casos pasan.

**Arreglo propuesto:** Escribir una prueba de contrato compartida —una tabla de casos que se corra contra ambas implementaciones con el proceso simulado— en vez de una suite por multiplexor. Es lo que habría hecho visible la falta de `disponible()` y de la guardia de salto de línea.

## [menor] `alcance` se declara obligatorio en el contrato de proveedores y ninguna orden lo muestra — **arreglado**
**Dónde:** src/telar/proveedores/__init__.py:10-12 y :41 · src/telar/ordenes/config.py:53-57 · src/telar/ordenes/doctor.py:236-259

El contrato de proveedores dice que cada uno «declara en `alcance` qué toca del mundo, **para que se pueda leer antes de encenderlo**», y las tres implementaciones lo rellenan con cuidado (calendario.py:487, :496, :564; tareas.py:495, :574). Ninguna orden lo imprime: `telar config` muestra nombre, activo y opciones; `telar doctor` muestra solo la cuenta de activos. La única garantía de privacidad que telar le ofrece al usuario por escrito no tiene superficie por donde leerse.

**Arreglo propuesto:** Incluir `alcance` en el JSON y en la vista de `telar config`, y en la revisión de proveedores de `telar doctor`: es barato y es justo lo que la promesa del módulo requiere.

## [menor] Las salidas de texto truncan rutas y frases al ancho del terminal sin decirlo — **arreglado**
**Dónde:** src/telar/ordenes/doctor.py:58, ficha.py:97 y 118, hilos.py:_linea

`telar doctor` en un terminal de 80 columnas imprime «✓ config  /private/tmp/un/directorio/bastante/largo/de/tra…/ba» — la ruta cortada a la mitad de un segmento, sin elipsis, sin ninguna señal de que falta algo. Con COLUMNS=200 se ve entera. En una orden cuyo trabajo es decirte dónde están las cosas para que las arregles, una ruta cortada en seco es peor que ninguna: se copia y no funciona. Lo mismo en ESTADO de `telar ficha` y en la línea de estado de `telar hilos`, donde la frase se corta a media palabra.

**Arreglo propuesto:** Un helper único `recortar(texto, ancho)` que ponga «…» cuando corta, y que en `doctor` las rutas no se recorten nunca —que pasen a la línea siguiente indentadas, como ya hace con el `→ arreglo`.

## [menor] Concordancia de número en los mensajes contados — **arreglado**
**Dónde:** src/telar/ordenes/doctor.py:233 y 296, ordenes/perfil.py

«1 hilos vinculados», «1 hilos con atención anotada», «(1 documentos)» en `telar perfil`. En un proyecto donde la prosa está cuidada hasta en los mensajes de error, el plural forzado canta.

**Arreglo propuesto:** Un helper `plural(n, 'hilo', 'hilos')` en _comun, usado en los tres sitios.

## [menor] `--sin-ficha` vacía `arquetipo` en el contrato de `hilo` sin que el contrato lo diga — **arreglado**
**Dónde:** src/telar/ordenes/_comun.py:439 y alrededores (json_hilo)

`telar hilos --json` devuelve arquetipo="proyecto"; `telar hilos --json --sin-ficha` devuelve arquetipo="" para los mismos hilos. docs/contratos.md advierte que con --sin-ficha «`ficha` puede ser null», pero no que `arquetipo` se vacíe. Un consumidor que use --sin-ficha por velocidad (la barra de estado, la extensión de VS Code) pierde la clasificación sin enterarse.

**Arreglo propuesto:** O calcular el arquetipo sin leer el documento —sale de casar la ruta contra los globs del perfil, que no cuesta nada— o decirlo en docs/contratos.md junto a la nota de `ficha`.

## [menor] El repositorio no tiene ningún commit y la rama no es la que el CI escucha — **arreglado**
**Dónde:** .git y .github/workflows/ci.yml:4

`git log` responde «your current branch 'master' does not have any commits yet»: los 12 archivos de primer nivel están sin seguir. El workflow dispara `on: push: branches: [main]`. Tal como está, el primer push no corre CI. Además, pyproject declara Homepage en github.com/nicorivas/telar, que todavía no existe.

**Arreglo propuesto:** `git branch -m master main` antes del primer commit, y commitear. Ya verifiqué que .gitignore cubre lo derivado: tras mi corrida solo quedaron __pycache__/ y src/telar.egg-info, ambos ignorados.

---

# Lo que destapó el primer CI

Dos fallas que ninguna prueba local podía ver, porque las dos dependen de la máquina: el CI
corre Linux con tmux 3.4 y con Python 3.11, y el desarrollo es macOS con tmux 3.7 y Python 3.13.

## [bloqueante] Un tmux anterior a 3.5 disfraza el separador de campos y ningún renglón se puede leer — **arreglado**
**Dónde:** src/telar/mux/tmux.py:67 (`SEP`) y :263 (`_tab`)

Los campos se piden pegados con el byte 0x1f, que no aparece en un nombre de ventana. Hasta 3.4,
tmux pasa por `vis()` todo lo que imprime, así que ese byte vuelve como los cuatro caracteres
`\037` y el renglón llega de una pieza: «tmux devolvió 1 campos donde iban 5». Las veintiséis
pruebas de integración cayeron en el CI mientras las 574 pasaban en macOS. No es un problema de
pruebas: contra un tmux de Ubuntu estable, `telar hilos` no habría leído un solo tab.

**Arreglo:** `_descamuflar()` deshace el disfraz en la salida de `_tmux`, y solo cuando el byte
de verdad no vino en toda la salida —si vino, este tmux no disfraza nada y esos cuatro caracteres
son parte de un nombre—. Cinco pruebas nuevas con la salida escapada, incluida una con acento:
`utf8_stravis` deja pasar el UTF-8 válido, así que «reunión» vuelve entero.

## [bloqueante] Una f-string anidada con comillas dobles no compila en Python 3.11 — **arreglado**
**Dónde:** src/telar/ordenes/perfil.py:87

`f"… ({_comun.plural(len(documentos), "documento")})"` es válido desde 3.12 (PEP 701) y un
`SyntaxError` en 3.11, que es el piso que declara pyproject. El paso «Compilar todo» del CI lo
cazó; ninguna prueba lo habría cazado, porque en 3.12 y 3.13 el archivo compila.

**Arreglo:** sacar la llamada a una variable antes del `print`. Verificado con un Python 3.11 de
verdad: las 579 pruebas pasan en 3.11 y en 3.13.
