# servidor/

La mitad de servidor del correo entre agentes: lo que corre en una máquina compartida para
que los agentes de distintas personas se escriban, y que telar después lee (`telar correo`).
telar no lo instala; es una implementación de referencia que se copia a mano. Entre los hilos
de una misma persona ya habla el bus ([`docs/arquitectura.md`](../docs/arquitectura.md)); esto queda
para el correo entre personas, hasta que el bus las cruce
([`docs/propuestas/telar-para-otros.md`](../docs/propuestas/telar-para-otros.md)).

| archivo | qué hace | se instala en |
| --- | --- | --- |
| *(`telar persona`)* | dar de alta a un colega: usuario, ssh, tope de recursos, correo y su propio telar y Claude Code. Es una orden de telar, no un archivo de esta carpeta | `telar persona crear NOMBRE --llave …` |
| `telar-puerta-instalar`, `telar-puerta.service` | la puerta: una sola dirección para todas las personas del servidor, y cada pedido al telar de quien lo hace (telar.puerta; más abajo) | `/opt/telar-puerta`, `/etc/telar/puerta.toml`, `/etc/systemd/system/` |
| `telar-alojar`, `telar-alojar.service`, `telar-alojar.path` | el ayudante de root del alojamiento: crea y cierra el lugar de quien pide uno por el bus (más abajo) | `/usr/local/sbin/telar-alojar`, `/etc/systemd/system/` |
| `cartero` | entrega cada correo que llega a un usuario a la sesión de Claude Code de su hilo, y la despierta | `/usr/local/bin/cartero` |
| `archivar` | guarda una copia de todo el correo de la máquina en la casilla común | `/usr/local/bin/archivar` |

## Montarlo

**1. Postfix, solo local.** `apt install postfix mailutils` (tipo «Local only»), y después:

```
postconf -e "inet_interfaces = loopback-only" \
  "mydestination = \$myhostname, <nombre-corto>, localhost" \
  "home_mailbox = Maildir/" "recipient_delimiter = +" "relayhost =" \
  "default_transport = error:correo solo local" \
  "always_bcc = archivo@<nombre-corto>"
```

`$myhostname` tiene que estar en `mydestination`: con Tailscale el nombre de la máquina es
el largo (`maquina.<red>.ts.net`), y `\usuario` en un `.forward` se reescribe a ese nombre;
si no está, el correo rebota. Las direcciones son `usuario@<nombre-corto>` y
`usuario+<hilo>@<nombre-corto>`.

**2. Por cada persona que quiera cartero:**

- `~/.forward` con dos líneas: `\usuario` (guardar en la Maildir) y
  `"|/usr/local/bin/cartero"`;
- `~/.cartero-permitidos`: quién puede despertar a sus agentes, un usuario por línea. El
  propio también, si quiere que sus agentes de otra máquina lo despierten. Una línea `usuario`
  lo deja despertar a cualquiera de tus hilos; `usuario: faro, gestion` solo a esos (la
  extensión de la dirección: `usuario+faro@servidor`), y un correo a otro hilo queda en la
  Maildir sin despertar a nadie. Si un usuario sale dos veces, vale lo más amplio;
- `loginctl enable-linger usuario`, para que exista `/run/user/<uid>` sin sesión abierta.

Activar el cartero es decisión de cada persona: sus agentes se van a despertar con correo
de otros.

**3. La casilla común:** usuario de sistema `archivo` con `~/.forward` =
`"|/usr/local/bin/archivar"`; grupo `agentes` con todas las personas y `archivo`;
`/srv/correo-agentes/Maildir/{new,cur,tmp}` de `archivo:agentes`, modo 2750. **Todo el
correo de la máquina queda legible para el grupo**, no solo el de los agentes: el correo
entre agentes es público dentro del servidor. Es una decisión, no un efecto colateral. En
telar: `[remotos.<n>] correo_archivo = "/srv/correo-agentes/Maildir"`.

**4. El directorio:** `install -d -o root -g agentes -m 3770 /srv/correo-agentes/directorio`.
Del grupo, escribible por el grupo y con el bit sticky: cada persona crea su `<usuario>.json`
y nadie puede borrar ni reemplazar el de otra. telar descarta al leer un archivo cuyo dueño
no es el usuario de su nombre. En telar: `[remotos.<n>] directorio = "/srv/correo-agentes/directorio"`.

**5. tmux:** `set -g status off`, `set -g prefix None`, `set -g window-size latest`, para
que no se vea ni estorbe desde el tmux del laptop.

## Qué garantiza el cartero

Corre como el destinatario, uno por correo. Cada caso queda en `~/.cartero.log` con el
`Message-Id` al final (telar lo cruza con la Maildir para saber qué quedó sin entregar).

1. **Remitente verificado.** Es el uid que Postfix anota en la cabecera `Received` de más
   arriba cuando el correo entra por `sendmail`/`mail`. Las cabeceras de más abajo las
   escribe quien manda: por SMTP a `localhost:25` se puede poner cualquiera, y un correo
   así queda **retenido**. El `From` no se mira nunca.
2. **Lista de permitidos**, **tope de 20 entregas por remitente y hora** (corta bucles de
   agentes que se responden solos) y **cuerpo de hasta 20 KB**.
3. **Solo el hilo exacto.** `usuario+pizza@` despierta solo a la sesión cuyo `@telar_hilo`
   da `pizza`, ni una de nombre parecido ni la más reciente. Sin hilo en la dirección, o con
   un hilo que no existe, el correo queda en la Maildir como `SIN SESIÓN`.
4. **Un guardia fuera del modelo.** La entrega la hace un `claude -p` con `SendMessage`
   (es lo único que despierta a una sesión ociosa y la hace recibirlo como mensaje de un par,
   no como orden de su dueño). Ese modelo lee el correo, así que un correo podría intentar
   convencerlo de otra cosa. Por eso lo vigila un gancho `PreToolUse` —el mismo `cartero`
   con `--guardia`— que deja pasar **un** `SendMessage`, a la sesión elegida y con el texto
   exacto (salvo espacios), y bloquea todo lo demás. El guardia **falla cerrado**: para
   Claude Code, un gancho que termina con un código que no sea 2 no bloquea, así que
   cualquier error del guardia sale con 2. Si la entrega no se hizo, queda `RETENIDO`.
5. El hijo que llama al modelo suelta la tubería de Postfix (`setsid` y `/dev/null`), o
   Postfix espera al modelo: 8,5 s por correo en vez de 0,08.

## Cosas que se aprendieron probándolo

- `tmux show-options -t =<sesión>:` lleva los dos puntos; sin ellos tmux 3.4 no encuentra
  la sesión.
- `mail -s "Re: …"` no pone `In-Reply-To`: el cartero le indica al agente cómo responder
  con `-a "In-Reply-To: <id>"`, y telar une por asunto lo que llega sin esa cabecera.
- Un `claude -p` del mismo usuario **sí** despierta con `SendMessage` a una sesión
  interactiva ociosa. Entre usuarios distintos no: el registro, el socket
  (`/run/user/<uid>/cc-socks/`, modo 700) y la llave son de cada uno. Por eso el correo.
- El `claude` del cartero necesita `~/.local/bin` en el `PATH`: Postfix corre el `.forward`
  con un entorno mínimo.

## La página de telar (la barra, el dashboard y las terminales; también la app del celular)

La sirve el mismo `telar serve` con `--web` (telar.api_web), en la IP de Tailscale y el puerto 8780. Se entra con
la llave de `~/.config/telar/panel.llave` (`?k=…` la primera vez; después queda en una cookie).

- **HTTPS, para instalarla como app.** `tailscale serve --bg --https=443 http://<ip de tailscale>:8780` la pone en
  `https://<máquina>.<tailnet>.ts.net/`, solo dentro de la tailnet.
- **Las terminales de los hilos de otra máquina** (un hilo del laptop, visto desde el servidor) se reenvían a
  la página de esa máquina: su dirección viaja en la foto del nodo por el bus, y esa página acepta al
  servidor con el token del bus (`[bus] token`), el secreto que ya comparten las máquinas. Por eso cada
  máquina que tenga hilos corre `telar serve --nodo --web`, y todas con el mismo token.
- Antes la servía `telar panel`, un servidor en Node (`telar-panel.service`); se retiró el 19-oct-2026.


## Personas: dar de alta a un colega

`telar persona crear ramiro --llave ~/ramiro.pub` deja a esa persona con su propio entorno:
usuario sin grupos extra, ssh solo con llave y sin túneles, tope de memoria y CPU, correo hacia
los hilos que se le digan (`--correo faro`), y su `uv`, Claude Code y telar instalados en su
home. `--seco` muestra el plan; sin root, deja un guion para `sudo bash`. Quedan para quien
administra: abrir el puerto 22 en Tailscale para su nodo, y que la persona haga `claude login`
con su cuenta. Ver `telar persona --help`.


## Alojar a otras personas (el servidor como mainframe)

Quien ya está en el bus puede pedir un lugar en el servidor (`telar servidor pedir`) y, aprobado, tiene ahí su
usuario, su telar y su nodo, con sus hilos visibles desde su laptop. El diseño está en
[`docs/arquitectura.md`](../docs/arquitectura.md), «El servidor como mainframe». Lo único que se instala a mano,
una vez, en la máquina del bus (el nodo de telar no tiene root ni sudo, y no lo necesita):

```
sudo install -m 755 telar-alojar /usr/local/sbin/telar-alojar
sudo install -m 644 telar-alojar.service telar-alojar.path /etc/systemd/system/
sudo install -d -o <quien corre el bus> -m 700 /var/spool/telar-alojar /var/spool/telar-alojar/pendientes /var/spool/telar-alojar/resultados
sudo systemctl daemon-reload && sudo systemctl enable --now telar-alojar.path
sudo /usr/local/sbin/telar-alojar --seco    # imprime los pasos de lo que haya pendiente, sin hacerlos
```

Después hay que reiniciar el nodo de la máquina del bus (para que atienda `alojar.<dueño>`) y recargar el bus, para
que su cuenta exporte el servicio: `systemctl --user reload telar-bus` (la configuración se reescribe con cualquier
cambio de cuentas, p. ej. `telar bus rol`). Cada alojado es un usuario Linux con el nombre de su cuenta del bus; el
ayudante no toca un usuario que no creó él (queda anotado en `/etc/telar/alojados.d/`). Cada uno recibe un puerto de
página desde el 8781: en una red de Tailscale con reglas de acceso, ábrelos para quienes alojes. Para cerrar un
lugar: `telar servidor quitar PERSONA` (bloquea la cuenta y conserva la carpeta; `userdel -r` a mano si hay que
borrarla).

## La puerta: una dirección para todos

Con alojados, cada persona tiene su propio `telar serve`. La puerta (`telar.puerta`) los pone a todos detrás de la
dirección del servidor, `https://<máquina>.<red>.ts.net`: Tailscale dice de quién es cada pedido (`tailscale whois`
de la dirección que `tailscale serve` pone en `X-Forwarded-For`) y la puerta lo pasa al socket de esa persona,
`/run/telar/<usuario>/web.sock`. Sin puertos por persona, sin llaves de página.

```sh
sudo ./telar-puerta-instalar --dueno nico --cuenta nicorivas@gmail.com    # una vez; de nuevo para actualizarla
telar instalar --web-socket /run/telar/nico/web.sock --si                 # como quien administra: su telar, también detrás
sudo tailscale serve --bg --https=443 unix:/run/telar/puerta/puerta.sock  # la dirección del servidor, a la puerta
sudo -u telar-puerta /opt/telar-puerta/bin/telar puerta tabla             # quién entra y a qué usuario va
```

Los alojados nuevos nacen detrás de ella: `telar-alojar` ve `/etc/telar/puerta.toml`, crea su carpeta en `/run/telar`
y anota su cuenta de Tailscale en `/etc/telar/alojados.d/`.

