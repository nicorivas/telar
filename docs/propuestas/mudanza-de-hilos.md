# Mudanza de hilos: diagnóstico y propuesta

Estado: **decidida el 24-nov-2026; hechas las cuatro etapas** (su diseño, en [arquitectura](../arquitectura.md),
«El dueño está escrito», «Llevar un hilo a otra máquina» y «Seguir aquí con la dueña apagada»). Diagnóstico medido ese día en las dos máquinas de una persona (un laptop y su servidor).
Rehace la mudanza sobre una copia por pedazos de las conversaciones (solo lo que falta, cuando se muda: sin réplica
continua) y un dueño explícito por hilo, en cuatro etapas. La primera se despliega sola y deja resuelto el caso que
destapó esto. Las cuatro decisiones de la persona, al final. Absorbe
[seguir-sin-su-maquina.md](seguir-sin-su-maquina.md): su réplica no se hace (decisión 1) y su «seguir aquí» es la
etapa 4 de esta, replanteada sin réplica.

## En cinco líneas

1. **La conversación viaja entera, de una vez, por un canal hecho para mensajes chicos.** El bus la manda en trozos de
   700 KB con un tope de 25 MB comprimida, sin retomar si se corta. Las conversaciones vivas pesan de 1 a 300 MB y
   las activas crecen 10 a 50 MB por día. Y cuando un hilo vuelve, la otra máquina ya tiene casi toda: en el caso,
   63,8 de 65 MB.
2. **Dónde vive un hilo no está escrito en ninguna parte: se deduce.** Se deduce de las ventanas de tmux, de
   `remotos.json`, de lo archivado en cada máquina, de las fotos y del progreso de la última mudanza. Por eso quedan
   copias viejas y archivados dobles, y por eso la página tiene que adivinar adónde se fue el hilo.
3. **Hay dos caminos (ssh y bus) que hacen cosas distintas, y no van en las dos direcciones.** El servidor no tiene
   ssh hacia el laptop, así que de vuelta solo queda el bus.
4. **Se copia antes de detener al agente.** Lo que escribe después, aunque sea lo que Claude anota al cerrarse, deja
   las dos copias distintas. Si se pide desde la página o con «traer aquí», la mudanza ni siquiera espera a que
   termine su turno.
5. **Lo más grave es lo que no viaja.** No viaja el árbol de trabajo del repositorio, ni los worktrees de los hijos,
   ni la carpeta de la conversación (resultados guardados, subagentes), ni el «cuelga de», ni los mensajes de su
   casilla local. Del repositorio solo se revisa si está sucio o tiene commits sin subir, entero, y eso suena
   siempre.

**Recomendación**: el camino B (rediseño), en cuatro etapas después de las decisiones (la réplica continua se cayó).
La primera trae lo mejor del camino A: mandar solo lo que falta, por un transporte que aguanta tamaños grandes y se
puede retomar, y esperar siempre a que el agente termine su turno.

## El caso que lo destapó

Un hilo de trabajo se llevó del laptop al servidor por ssh a las 07:14 (63,8 MB, sin problemas). A las 08:53 la
persona pidió traerlo de vuelta y falló así: «la conversación no llegó a laptop: por el bus va hasta 25 MB; para más,
git o el panel. Aquí sigue como estaba.» La persona entendió «pesa 25 MB». En realidad pesaba 65 MB, y comprimida
37,7 MB: el gzip la baja solo 1,7 veces, porque casi todo son capturas en base64. El día anterior pesaba 16,6 MB.

El laptop ya tenía 63,8 MB de esos 65, en la copia que quedó al irse: la del servidor menos una línea `cost-state`
que Claude escribe al cerrarse. Faltaban 1,2 MB (305 líneas). Se terminó a mano: el `.gz` se copió con rsync desde el
laptop (8,2 s) y se corrió la mudanza de siempre con el paso de copiar reemplazado. Después hubo que copiar aparte la
carpeta `<sid>/` de la conversación, de la que faltaban 9,4 MB. Al llegar, el hilo había perdido su «cuelga de».

## Cómo es hoy, en lo que importa aquí

| | por ssh (`[remotos]`) | por el bus (otra máquina en el bus) |
|---|---|---|
| quién puede | quien tiene ssh hacia la otra (hoy, laptop → servidor) | cualquiera, en las dos direcciones |
| revisión previa | ninguna | `hilo-revisar` (agente, `claude`, nombre, carpeta) |
| copia | el `.jsonl` entero, gzip por la entrada de ssh | `entrega.archivo`: trozos de 700 KB en base64, tope 25 MB |
| abrir allá | tmux directo por ssh (no pasa por el nodo de allá) | verbo `hilo-llegar` del nodo de allá |
| aquí queda | una ventana que mira la de allá (mosh) | el hilo archivado, con su copia |
| orden | copiar → abrir → cerrar aquí | revisar allá → copiar → abrir → archivar y cerrar aquí |

«Traer aquí» (`POST /hilo/traer`, verbo `hilo-traer`) le pide al dueño que corra `telar hilo llevar` hacia la que
pide: del servidor al laptop, eso es siempre por el bus.

## Catálogo de fallas

Cada una con lo que se vio o con la línea de código que la produce.

### El transporte

1. **El tope.** `entrega.MAX_TOTAL` (25 MB comprimida). Hoy, 4 de los 7 hilos vivos del laptop y 1 de los 11 del
   servidor ya no se pueden mudar por el bus. Son los más activos. El mensaje de error es el de un archivo
   cualquiera («para más, git o el panel»): no dice qué hacer con un hilo.
2. **Lento, y más desde el laptop.** Cada trozo es un pedido con respuesta, uno detrás de otro, en base64 dentro de
   JSON. Desde un proceso de la CLI, `bus.pedir` abre **una conexión al bus por trozo**. Con 16,7 MB comprimidos:
   60 s del laptop al servidor, contra 22 s por una sola conexión y 3,7 s por ssh (tabla abajo).
3. **Todo o nada.** Si se pierde un trozo, la entrega entera falla y nadie la manda de nuevo. Los trozos a medias
   esperan una hora en `.parciales`. Lo único que se verifica es el largo descomprimido: no hay huella de contenido.
4. **Manda todo, aunque allá ya esté casi todo.** El caso necesitaba 1,2 MB y mandó 65 MB.
5. **No lleva la carpeta de la conversación.** Claude Code guarda junto al `.jsonl` una carpeta `<sid>/` con
   `tool-results/` (salidas largas que la conversación nombra por su ruta), `subagents/` y `workflows/`. En el caso,
   en el servidor, eran 0,8 MB de `tool-results/` y 8,6 MB de `subagents/`; en el laptop, `subagents/` ya pesaba 211 MB.
6. **Todo en memoria.** Las dos puntas leen la conversación entera y la comprimen o descomprimen en memoria. Una de
   300 MB en el servidor, que tiene 8 GB y a veces poco libre, es un riesgo.

### El orden, y los cortes a mitad

7. **Llevar desde la página o traer le corta el turno al agente.** Solo el camino «aparte» (el agente que se lleva a
   sí mismo) espera a que termine (`mudanza.esperar_turno`). `POST /hilo/llevar` y `hilo-traer` corren `telar hilo
   llevar` sin `TELAR_LLEVAR_APARTE`: copian con el agente trabajando y al final cierran su ventana con el turno a
   medias. Lo que escribió entretanto queda solo en la copia de origen (`lo_que_siguio` lo cuenta y lo dice). En el
   caso de hoy hubo que esperar el turno a mano.
8. **Se copia antes de detener.** Aunque espere el turno, el agente de origen sigue vivo hasta el final, y al
   cerrarse Claude agrega líneas (`cost-state`, `last-prompt`). La copia de origen deja de ser un comienzo de la de
   destino, y por eso existen `misma_conversacion` y la misma lógica repetida en `_DEJAR` para reconocer «la misma, más
   larga» a la vuelta.
9. **Un corte entre abrir allá y cerrar aquí deja dos agentes vivos.** Si `hilo-llegar` tarda más de 60 s, más 20 s
   mirando la foto (un servidor cargado, Claude que demora en arrancar), el origen da la mudanza por fallada y sigue
   abierto, mientras allá abrió igual. Nada le dice al destino que se eche atrás. Pasa lo mismo si el proceso de
   origen muere en ese tramo, por ejemplo al cerrar la tapa del laptop: al despertar, su agente sigue ahí. Nadie
   retoma una mudanza a medias: el archivo de progreso se queda en el último paso que alcanzó.
10. **Traer tiene plazos que no calzan y no se ve desde quien pide.** `servicios.llevar.traer` espera 600 s;
    `mudanza.traer_aqui` deja correr al subproceso 900 s. El progreso queda en la máquina que corre la mudanza (`GET
    /mudanza` lee el archivo de allí), así que la página que pidió traer ve solo «trayendo…» hasta que termina o se
    vence. `hilo-traer` corre la mudanza como hija del nodo, en su mismo grupo de procesos. En Linux sobrevive a un
    reinicio del nodo (`KillMode=process`). En el Mac, el plist no tiene `AbandonProcessGroup`, así que launchd puede
    matar el grupo al reiniciar el nodo.

### Dónde vive el hilo

11. **Dos caminos, dos resultados.** El mismo hilo, ida por ssh y vuelta por bus, deja en el laptop una ventana que
    mira y en el servidor un archivado. Por ssh no hay revisión, y la ventana nace por tmux sin pasar por el nodo de
    allá: lo que hace `hilo-llegar` al recibir (vincularlo, anotar su conversación) no corre; solo se le pide
    desarchivarlo. `contratos.md` dice que `hilo-revisar` niega «la conversación ya
    llegada»; el código ya no lo hace.
12. **Copias viejas que se pueden retomar.** Seis conversaciones están en las dos máquinas, y cinco son distintas.
    Dos hilos figuran archivados en las dos con copias que divergieron: 25,2 MB contra 3,7 MB, y 57 MB contra 5,2 MB.
    Si se retoman en la máquina equivocada, siguen la copia vieja sin decir nada.
13. **La página adivina adónde se fue.** `web/donde-vive.ts` cruza la lista de aquí, la mudanza de aquí (15 min) y
    las fotos de las otras (cada 30 s). El `Seguidor` de la página lo sigue durante 3 minutos, por nombre. Una página
    servida por una máquina que no corrió la mudanza (la del servidor mirada desde el teléfono, si la corrió el
    laptop) solo tiene las fotos.

### Las rutas

14. **`/Users/ana` y `/home/ana`.** La carpeta de proyectos de Claude (`-Users-ana-vida` y `-home-ana-vida`) se calcula
    en tres lugares: `mudanza.llegar`, `_DEJAR` y `carpeta_remota`. La conversación del caso lleva 2 850 rutas
    `/home/…` y 2 719 rutas `/Users/…`, entre ellas 12 a archivos de `tool-results/` por su ruta absoluta (9 del
    servidor y 3 del laptop). Un vínculo absoluto (todos los worktrees) no tiene traducción, y el hilo se abre en la
    raíz.

### Lo que no viaja

15. **El árbol de trabajo.** `_sin_subir` mira el repositorio entero de la raíz, de la carpeta del hilo y de la del
    agente, y no lo que tocó el hilo. Como siempre hay algo, el aviso suena siempre: hoy 20 archivos en tres
    repositorios, y en octubre 76 archivos y 7 commits. La persona aprende a apretar «llevar igual». No se pregunta si
    el destino está atrasado o sucio (el 23-nov el repositorio del hilo en el laptop iba 53 commits atrás), y nada
    hace `pull` allá.
16. **Los hijos con rama.** Un hijo con rama está vinculado a su worktree por ruta absoluta (`~/worktrees/…`), que
    existe en una sola máquina. Si se lleva, se abre en la raíz del repositorio principal, y su contexto le dice que
    trabaja en un worktree. Puede terminar editando `main`. A un padre llevado le quedan los hijos en la otra
    máquina, y no puede fusionarlos desde la nueva.
17. **El estado del hilo.** Viajan el vínculo y la conversación. No viajan el padre (el caso llegó sin su «cuelga
    de», así que no le avisa al terminar), las etiquetas, el esfuerzo, la rama ni lo público. La casilla local
    (`<estado>/casillas/<ficha>/`: lo pendiente, los avisos y lo que va en camino) queda en el origen y no se entrega.
18. **Seguir sin su máquina no se puede.** Esto ya lo dice [seguir-sin-su-maquina.md](seguir-sin-su-maquina.md): la
    conversación existe solo donde vive el hilo.

## Lo que se midió (24-nov-2026)

**Tamaño de las conversaciones de los hilos vivos**, solo el `.jsonl`:

| máquina | hilos | total | mediana | la más grande | más de 25 MB | más de 25 MB comprimida (no caben en el bus) |
|---|---|---|---|---|---|---|
| laptop | 7 | 572 MB | 65 MB | 298 MB | 5 | 4 |
| servidor | 11 | 154 MB | 1,3 MB | 102 MB | 1 | 1 |

Además está su carpeta `<sid>/`: 173, 304 y 205 MB en los tres más grandes del laptop, casi todo `subagents/`. En
disco hay 6,4 GB de conversaciones en el laptop y 1,3 GB en el servidor.

**Cuánto crecen.** El hilo del caso pasó de 16,6 a 65 MB en un día. El más grande del laptop lleva 46 MB por día
durante 6,5 días. Otro de desarrollo, 10 MB por día. Los agentes residentes, de 0,3 a 3,5 MB por día. Un hilo activo
cruza los 25 MB comprimidos en uno o dos días de trabajo.

**De qué están hechas** (el caso, 65 MB): las líneas `user` pesan 38,8 MB (resultados de herramientas con
capturas), `api-request-blob` 14,8 MB, `assistant` 4,4 MB y el resto menos de 2 MB. El gzip saca poco (1,7×); lo que
ahorra de verdad es no mandar lo que allá ya está. Las cinco más grandes de las dos máquinas comprimen entre 1,4 y
2,3 veces.

**Cuánto tarda en viajar** (Tailscale directo; archivo de prueba de 25 MB con la forma de una conversación, 16,7 MB
comprimido; `scripts/medir_mudanza.py`):

| camino | laptop → servidor | servidor → laptop |
|---|---|---|
| bus, como hoy (`entrega.archivo`) | 60,3 s y 60,6 s | 12,4 s y 22,9 s |
| bus, los mismos trozos por una sola conexión | 21,9 s | 18,3 s |
| ssh, el `.gz` entero | 3,7 s y 5,7 s | 3,0 s (lo baja el laptop) |
| rsync `-z`, 25 MB sin comprimir | 3,7 s | 9,7 s (lo baja el laptop) |
| rsync del mismo archivo con 1 MB más (algoritmo delta) | 1,8 s | — |
| solo la cola nueva (1 MB, 0,7 MB comprimido) por ssh | 0,74 s | — |
| el caso real: 37,7 MB comprimidos con rsync | — | 8,2 s |

Lo que dice la tabla:

- En el laptop, abrir una conexión por trozo se lleva dos tercios del tiempo. Aun así, por el bus cada trozo cuesta
  casi un segundo, y la variación es grande: el mismo envío del servidor al laptop tardó 12 s una vez y 23 s otra.
- Ssh es de 6 a 16 veces más rápido, pero solo existe del laptop al servidor. Los lugares alojados en el servidor no lo
  tienen.
- El rsync del Mac es openrsync (protocolo 29, sin `--append-verify`): no sirve de base.
- Mandar solo lo que falta cuesta menos de un segundo por cualquier camino. Lo que importa no es el canal: es no
  mandar lo que ya está.

## Dos caminos

### A. Arreglos sobre lo que hay

- **A1. Ssh para lo grande.** Si la conversación pasa del tope y quien la recibe tiene ssh hacia el dueño, la baja
  quien la recibe: es lo que se hizo a mano hoy. Arregla 1 y 2 entre el laptop y el servidor. Medio día.
- **A2. Un transporte de trozos que aguante.** Una conexión, bytes crudos con cabeceras en vez de base64 dentro de
  JSON, sin tope total, leído del disco de a poco, retomable desde el último byte que llegó y con sha256 del total.
  Arregla 1, 2, 3 y 6. Un día y medio.
- **A3. Solo lo que falta.** `hilo-revisar` contesta el largo y la huella de los últimos 64 KB de la copia que ya
  tiene el destino. Si calza, se manda desde ahí; si no, entera. Arregla 4 y hace que ida y vuelta cuesten segundos.
  Medio día.
- **A4. La carpeta `<sid>/`.** Viajan `tool-results/` y `workflows/`; `subagents/` solo si se pide. Arregla 5. Medio
  día.
- **A5. Esperar siempre el turno.** Por la página, por traer y por la CLI. El progreso del dueño se lee por el bus
  desde quien pidió, y `hilo-traer` corre aparte, en su propia sesión. Arregla 7 y 10. Un día.
- **A6. El estado del hilo y su casilla.** El padre, las etiquetas y el esfuerzo viajan en `hilo-llegar`. Lo
  pendiente de la casilla local se vuelve a dejar en la casilla del bus. Arregla 17. Medio día.
- **A7. El árbol de trabajo.** La revisión mira solo el repositorio y la carpeta del hilo. Pregunta también por el
  destino (atrasado, sucio) y ofrece «subir y llevar». Arregla 15. Un día y medio.
- **A8. Los hijos con rama no se llevan.** `hilo-revisar` lo da por grave. Arregla 16. Un cuarto de día.

Son **unos 6 días**. No arreglan 8 (copiar antes de detener), 9 (dos vivos tras un corte), 11 (dos caminos), 12
(copias viejas), 13 (la página que adivina) ni 18 (seguir sin su máquina). Esos salen de que el sistema no sabe quién
es el dueño. Para la persona, la mudanza de un hilo grande pasaría de imposible a uno a cuatro minutos la primera
vez, según su tamaño, y unos segundos de vuelta. Seguiría viendo el progreso solo en la máquina que manda, y
seguirían los archivados dobles.

**Riesgos de A**: más casos especiales sobre un diseño que ya tuvo 37 commits que lo tocan desde septiembre, diez
de ellos el 23-nov. El camino por ssh y el del bus seguirían separados.

### B. Rediseño: la conversación copiada por pedazos y un dueño explícito

La idea, en cuatro piezas.

**B1. La copia por pedazos (`telar.replica`).** Una conversación de Claude Code es un archivo al que solo se le agregan
líneas al final. Por eso se puede copiar de a pedazos: lo que falta en la copia de allá es siempre la cola del original.

- Quien recibe dice, de cada archivo, su largo y la huella (sha256) de los 64 KB antes de cada lugar donde su copia
  podría cortarse para ser un comienzo de la de aquí: su largo entero y, en una conversación, sin las líneas que
  Claude anota al cerrarse. Si una huella calza con la de aquí en ese lugar, se manda desde ahí; si ninguna (Claude
  reescribió el archivo, se siguió allá por su lado), se manda entera y la copia de allá queda aparte, con fecha. Al
  final se compara el largo y el sha256 de cada archivo entero.
- Lo que llega se junta aparte, en `<estado>/llegadas/<sid>/`, y recién verificado pasa a donde Claude lo busca. Cada
  pedazo dice desde qué byte va: quien recibe lo agrega solo si su copia a medias llega justo ahí, así que repetir uno
  no duplica nada, y retomar después de un corte es seguir desde lo que ya juntó.
- Viaja por el bus, por una sola conexión, en mensajes de bytes crudos de hasta 896 KB (comprimidos con zlib si eso
  los achica), varios en camino a la vez. Es el único camino que hay en las dos direcciones y para los lugares
  alojados. Ssh queda para mirar ventanas, no para mover hilos.
- Viaja también la carpeta `<sid>/` entera (`tool-results/`, `subagents/`, `workflows/`), con el mismo criterio: de
  cada archivo, solo lo que falta.
- **Sin respaldo continuo** (decisión 1): solo viaja cuando el hilo se muda. Allá queda la copia de la última vez que
  el hilo vivió ahí, y nada más.
- Reemplaza `mudanza.mandar` y `entrega.archivo` para conversaciones (con su tope), y la copia por ssh de
  `remoto.copiar_conversacion` y `_DEJAR` cuando la otra máquina está en el bus (sin bus quedan como respaldo, igual
  que con un telar de antes allá).

**B2. Un dueño, con época.** El registro de cada hilo en `TELAR_HILOS` agrega `dueno` (la máquina) y `epoca` (un
número que sube con cada traspaso). Publicar el registro pasa a ser una escritura condicionada a la revisión que se
leyó (`kv.update` con `last`). Una máquina con la época vieja no puede publicar: cede. Así nunca hay dos dueños,
aunque una vuelva de dormir sin saber nada. Es lo que le faltaba a [un-dueno-por-hilo.md](un-dueno-por-hilo.md): ahí
ya se decidió que manda una sola máquina, pero el traspaso seguía siendo «archivar aquí, abrir allá».

**El traspaso, con el dueño A en línea**, lo conduce la máquina que recibe, B. Llevar y traer son la misma operación,
pedida desde cualquier página:

1. B revisa lo suyo y le pide a A lo de él: el agente, `claude` en el PATH, la carpeta, el estado del repositorio en
   las dos (B4).
2. A cede. Espera a que el agente termine su turno, lo cierra (su ventana queda diciendo «se va a B») y anota el
   largo final y el sha256. Como el agente ya no corre, la copia de A no vuelve a cambiar. Eso termina con la falla 8
   y con `misma_conversacion`.
3. B baja de A lo que le falta y verifica el sha256. Deja la conversación donde Claude la busca, con su carpeta
   `<sid>/`.
4. B escribe el registro condicionado: `{dueno: B, epoca + 1}`. Si alguien escribió antes, B no abre y A retoma.
5. B abre al agente retomando la conversación. Con el registro viajan el padre, las etiquetas y el resto (B4).
6. A ve el registro nuevo y su ventana pasa a mirar la de B. En A el hilo no se archiva: vive en B.

Si algo falla antes del paso 4, A vuelve a abrir a su agente y no se perdió nada: el hilo estuvo detenido unos
segundos. Después del paso 4 el dueño es B, aunque B no alcance a abrir: se retoma en B, porque la conversación ya
está ahí. Lo que hace imposible tener dos vivos es el registro condicionado, no un plazo. Volver atrás es la misma
operación al revés y, como allá ya está casi todo, tarda segundos.

**El traspaso con A fuera de línea** («seguir aquí», decisiones 3 y 4; la etapa 4): B escribe `{dueno: B, epoca + 1,
tomado_de: A, hasta: <largo de su copia>}` y retoma desde la copia que le quedó de la última vez que el hilo vivió en B.
Antes dice cuánto falta: de cuándo es su copia y cuánto pesaba la de A la última vez que se la vio. Cuando A vuelve,
su nodo ve una época mayor y no publica. Duerme a su agente y deja su ventana mirando la de B. Lo que A tiene más allá
de `hasta` queda aparte, `<sid>.de-A-<fecha>.jsonl.bak`, y se le dice a la persona (decisión 3). Nada se borra en A
sin su nodo.

Reemplaza: archivar en el origen como señal de «se fue», `remotos.json` para los hilos del bus, `misma_conversacion`,
`lo_que_siguio`, `abierto_en_su_foto` y los pasos 2 a 4 de `dondeVive` (la página sigue al `dueno`, sin ventana de
tres minutos). El progreso de una mudanza va en el mismo registro (`mudanza: {a, paso, bytes, de}`), así que lo ve
cualquier página, también la del teléfono. Sin bus no hay dueño que compartir, y la mudanza por ssh de hoy queda como
está.

**B3. Las rutas, en una sola pieza (`telar.rutas`).** Traduce entre máquinas la raíz, el hogar, la carpeta de
worktrees y la carpeta de proyectos de Claude, y la usan todos los que hoy lo hacen cada uno a su manera. Los
vínculos se guardan relativos a la raíz o como `worktree:<repo>-<rama>`, nunca como ruta absoluta de una máquina.
Dentro de la conversación no se cambia nada: es el formato de Claude Code, y reescribirla rompería la copia por
pedazos. Si las rutas difieren, al retomar se le dice al agente una línea, con el primer mensaje que ya existe para
eso: «esta conversación siguió en otra máquina: lo que antes era /home/ana/vida aquí es /Users/ana/vida».

**B4. Lo que no es la conversación.**

- **El repositorio del hilo**, y solo ese: el de su carpeta, o la raíz si no tiene. En A se mira lo sin commitear en
  su carpeta, lo sin commitear en el resto del repositorio (solo informativo) y los commits sin subir. En B, cuánto
  va atrás y si está sucio. Si falta algo, el panel lo dice y ofrece **«subir y llevar»**: en A, `telar commit` de la
  carpeta del hilo y push; en B, `git pull --ff-only` de ese repositorio. Si algo no avanza limpio, se detiene y dice
  qué. «Llevar igual» queda, explícito, con la lista (decisión 2). En el menú la opción es siempre la misma («llevar a
  B»); el panel de la mudanza muestra, solo si hace falta subir algo, el detalle de lo que falta (cada archivo y cada
  commit) con «subir y llevar» y «llevar igual».
- **Los hijos con rama no se mudan**: su rama existe en una sola máquina. Es grave en la revisión, y la revisión lo
  dice. Un padre con hijos con rama vivos se puede llevar, con el aviso de que sus hijos se fusionan en la otra.
- **Lo que corre en su ventana** (un servidor de desarrollo) se nombra en el aviso: la ventana se ve.
- **La casilla**: antes de ceder, A vuelve a dejar en la casilla del bus lo pendiente de su casilla local, con sus
  ids, para que no se dupliquen. B lo recibe como cualquier mensaje.
- **El registro del hilo** lleva el padre, la prioridad, las etiquetas, el esfuerzo, la rama, lo público y los alias.
  Ya lleva el vínculo y si está archivado.

### Lado a lado

| | A. arreglos | B. rediseño |
|---|---|---|
| fallas que arregla | 1–7, 10, 15–17 | todas (1–18; la 18, desde la última copia) |
| trabajo | unos 6 días | unos 6,5 días, en 4 etapas |
| llevar un hilo grande | de 1 a 4 min la primera vez (según su tamaño), segundos de vuelta | lo mismo: sin réplica continua, la primera vez viaja entero |
| progreso | solo en la máquina que manda | en toda página, también el teléfono |
| volver atrás | otra mudanza | la misma operación, segundos |
| máquina apagada | no se puede seguir | «seguir aquí» desde la última copia, con aviso de lo que falta |
| riesgo principal | más casos especiales sobre la base de hoy | tocar cómo publica el nodo; probar con dos nodos de verdad |

**Riesgos de B**, y qué hacer con cada uno:

- **Cambiar cómo el nodo publica sus hilos** (escritura condicionada) puede romper la lista de una máquina. Va en su
  propia etapa (la 3), probada con dos nodos y un tmux real, y la escritura vieja queda detrás de un interruptor hasta
  que la nueva pase una semana.
- **Detener al agente para ceder** significa que un turno muy largo hace esperar la mudanza (hasta 10 minutos, como
  hoy) o que la persona elige cortarlo.
- **Si Claude Code un día reescribe sus archivos**, la huella de la cola lo detecta y se manda entera: más lento, nunca
  equivocado.
- **Sin réplica, la primera mudanza de un hilo grande es lenta** (de uno a cuatro minutos), y «seguir aquí» con el
  dueño apagado parte de una copia vieja. Es lo que la persona eligió (decisión 1): no cargar el servidor con todas
  las conversaciones, y que escale a más de un servidor.

**Qué cambia para la persona.** Un clic en «llevar a laptop», «traer aquí» o «seguir aquí» abre el mismo panel de
hoy, con pasos reales: revisar, esperar el turno, pasar lo que falta (1,2 MB de 65), abrir allá, listo. El panel se ve
desde cualquier página. Si falta subir algo del repositorio, el panel lo dice con un botón para hacerlo. Al terminar
aparece «volver a <máquina>», que también tarda segundos. Ya no hay archivados dobles ni ventanas que se pierden, y
desde el teléfono se puede seguir un hilo con el laptop apagado, desde la copia que quedó la última vez, sabiendo qué
le falta.

## Recomendación y plan por etapas

**B**, en cuatro etapas, en este orden. Cada una se despliega sola y deja todo funcionando. La primera arregla el caso
de hoy. La réplica continua (la etapa 4 de antes) no va: decisión 1.

1. **Hecha: mandar lo que falta, por un camino que aguanta** (A2 a A5 y B1; las rutas de Claude en `telar.rutas`).
   Arregla las fallas 1 a 7 y la 10; la 14, en parte (la carpeta de Claude, calculada en un solo lugar). Su diseño y
   lo medido, en [arquitectura](../arquitectura.md), «Llevar un hilo a otra máquina»; sus pedidos, en
   [contratos](../contratos.md), «`/mudanza` y `hilo-revisar`». La mudanza por ssh sigue abriendo el hilo allá como
   antes (dos caminos, falla 11: la etapa 3).
2. **Hecha: lo que no es la conversación** (A6, A7 y A8, y B4). Arregla las fallas 15, 16 y 17. Se mira solo lo
   del hilo: lo sin commitear que escribió su conversación (se sube con «subir y llevar», solo eso), lo demás de su
   carpeta (se muestra, no se sube) y los commits sin subir; allá, el repositorio se pone al día antes de abrir. La
   opción del menú es siempre la misma, y el panel muestra el detalle solo si hay algo (decisión 2). Los hijos con
   rama no se mudan; su padre se lleva solo. Viajan el padre, las etiquetas, la prioridad, el esfuerzo, lo público y
   la casilla local. Su diseño, en [arquitectura](../arquitectura.md); sus pedidos, en [contratos](../contratos.md).
3. **Hecha: un dueño, con época** (B2 con A en línea). Arregla las fallas 8, 9, 11, 12 y 13. El registro lleva
   `dueno` y `epoca` y el nodo lo publica condicionado (telar.dueno; `[bus] publicar = "simple"`, la escritura de antes,
   queda de interruptor). El traspaso cede, detiene al agente, copia la conversación final, y allá lo toman con esa
   época; si falla antes, aquí se echa atrás. Nada se archiva en el origen, y la lista de allí no lo muestra como suyo.
   La página sigue al dueño (`GET /hilo/registro`). Por ssh ya no se mudan hilos si la otra máquina está en el bus. Se
   retiraron `misma_conversacion`, `lo_que_siguio`, `abierto_en_su_foto`, la entrada entera por el camino de un archivo
   (`_mandar_entera`), `hilo-preparar` y los pasos 2 a 4 de `dondeVive`. Probada con dos nodos de verdad (el nodo a
   medias de `scripts/probar_mudanza.py`, con su registro aparte) matando al de allá antes de copiar, a mitad de la
   copia, después de tomarlo y después de abrirlo, y al proceso de aquí a mitad de la copia (la tapa del laptop): nunca
   dos agentes vivos. Queda con la persona: ordenar los dos hilos archivados dobles de hoy, mirando cuál copia vale.
4. **Hecha: seguir desde la última copia, y la vuelta** (el traspaso con A fuera de línea; la persona eligió el 24-nov
   la segunda manera de abajo). Cierra [seguir-sin-su-maquina.md](seguir-sin-su-maquina.md), sin su réplica.
   telar.seguir: la foto lleva el largo de cada conversación y cuándo creció; «seguir aquí» solo donde hay copia y con
   la dueña apagada, con el aviso de lo que falta; `dueno.seguir` lo toma con la época leída (`tomado_de`, `hasta`); la
   que vuelve cede sola (`Nodo.ceder_seguidos`), deja aparte lo suyo y lo avisa en la franja. Con ella, los archivados
   de otra máquina se ven como de allá y retomarlos va allá. **Probada** con dos nodos de verdad (el arnés, con sus
   fotos en un almacén aparte), en las dos direcciones: la dueña apagada de verdad (su nodo muerto y su agente
   congelado con SIGSTOP, como la tapa cerrada), seguida en la otra desde su copia, y al volver cedió sola en su primera
   vuelta (2 a 5 s), con lo suyo aparte cuando había escrito después de la copia.

Si después de la etapa 1 la persona prefiere esperar, el camino A queda casi completo con la 2. Las etapas 3 y 4 son
las que cambian la base.

### La etapa 4, sin réplica

Sin réplica continua, cuando la máquina dueña (A) está apagada no hay una copia al día en ninguna parte: solo la que
quedó en cada máquina la última vez que el hilo vivió en ella. Hay dos maneras de quedarse:

- **Solo con la dueña en línea.** Entonces «seguir aquí» es «traer», que ya existe: la etapa 4 no se construye, y con
  A apagada lo que queda es lo de hoy (dejarle un mensaje, despertarlo cuando vuelva). La decisión 3 no hace falta:
  A nunca vuelve a encontrar su hilo seguido en otra parte.
- **Desde la última copia, con aviso de lo que falta.** «Seguir aquí» aparece solo en una máquina en línea que tenga
  una copia de esa conversación (en la práctica, donde el hilo vivió antes), y solo con A fuera de línea; con A en
  línea es «traer». Para decir qué falta sin copiar conversaciones, cada nodo agrega a la foto que ya publica cada
  30 s el largo de la conversación de cada hilo suyo y cuándo creció por última vez (dos números por hilo, nada del
  contenido). La pregunta antes de tomarlo dice: «aquí está como quedó el 23-nov a las 07:14 (63,8 MB); en laptop,
  la última vez que se lo vio (hace 2 h), pesaba 65 MB: el agente no va a recordar lo de después». B toma el hilo con
  `tomado_de: A, hasta: <largo de su copia>` (etapa 3) y lo retoma. Al volver, A cede solo: duerme a su agente, su
  ventana pasa a mirar la de B, su copia queda aparte como `<sid>.de-A-<fecha>.jsonl.bak` y la persona recibe un
  aviso en la franja (decisión 3). Lo que A hizo después de la copia no se junta con lo de B: se puede leer, no
  seguir. Sin una copia en ninguna máquina en línea, «seguir aquí» no aparece, y la franja dice que el hilo vuelve
  cuando A vuelva.

**La elegida (24-nov), y hecha: la segunda.** Es la única en que las decisiones 3 y 4 tienen sentido, y el caso que la pidió (el laptop
apagado dos horas, la persona en el teléfono) suele tener una copia reciente en el servidor: el hilo pasa del
servidor al laptop y vuelve varias veces al día. El costo es que el agente sigue sin lo último, pero la persona lo
sabe antes de elegir. La persona la confirmó el 24-nov.

## Decisiones de la persona

Cerradas el 24-nov-2026.

1. **¿Se copian las conversaciones al servidor de forma continua?** **No.** «No lo encuentro necesario. Creo que
   podría saturar el servidor de forma innecesaria y no escalaría para cuando tengamos más de un servidor.» Las
   conversaciones viajan solo cuando el hilo se muda, de a pedazos (B1). La etapa de la réplica se cae, y «seguir
   aquí» se replantea desde la última copia (etapa 4). Reemplaza la decisión 1 de seguir-sin-su-maquina.
2. **Lo sin subir del repositorio del hilo, al mudarlo.** **«Subir y llevar»**, con «llevar igual» explícito, y con
   una condición: que se pueda ver en el panel el detalle de lo que falta subir. La opción del menú es siempre la
   misma; el panel muestra el detalle solo si hace falta subir algo. Es de la etapa 2.
3. **Cuando vuelve una máquina cuyo hilo se siguió en otra.** **Cede sola**: su ventana pasa a mirar al dueño nuevo,
   lo suyo queda aparte y se avisa. Reemplaza la decisión 3 de seguir-sin-su-maquina.
4. **Dónde se ofrece «seguir aquí».** **En cualquier máquina en línea** (que tenga una copia: sin réplica, no
   cualquiera la tiene). Reemplaza la decisión 2 de seguir-sin-su-maquina.

## Lo que no resuelve

- Lo que existe solo en una máquina y no está en git: archivos sueltos, un `npm run dev` que corre, credenciales.
  Se nombra, no se lleva.
- Por qué los hilos se mudan tan seguido: el del caso se movió tres veces en dos días, siguiendo a la persona entre
  el laptop y el teléfono. Si se pudiera hacer en el servidor lo que hoy solo se puede en el laptop (un navegador con
  sesión, programas de escritorio), habría menos mudanzas. Eso es otra propuesta.
