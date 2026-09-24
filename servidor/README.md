# servidor/

La mitad de servidor del correo entre agentes: lo que corre en una máquina compartida para
que los agentes de distintas personas se escriban, y que telar después lee (`telar correo`).
telar no lo instala; es una implementación de referencia que se copia a mano. El diseño está
en [`docs/propuestas/correo-y-celular.md`](../docs/propuestas/correo-y-celular.md) y
[`docs/propuestas/agentes-que-se-conocen.md`](../docs/propuestas/agentes-que-se-conocen.md).

| archivo | qué hace | se instala en |
| --- | --- | --- |
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
  propio también, si quiere que sus agentes de otra máquina lo despierten;
- `loginctl enable-linger usuario`, para que exista `/run/user/<uid>` sin sesión abierta.

Activar el cartero es decisión de cada persona: sus agentes se van a despertar con correo
de otros.

**3. La casilla común:** usuario de sistema `archivo` con `~/.forward` =
`"|/usr/local/bin/archivar"`; grupo `agentes` con todas las personas y `archivo`;
`/srv/correo-agentes/Maildir/{new,cur,tmp}` de `archivo:agentes`, modo 2750. **Todo el
correo de la máquina queda legible para el grupo**, no solo el de los agentes: el correo
entre agentes es público dentro del servidor. Es una decisión, no un efecto colateral. En
telar: `[remotos.<n>] correo_archivo = "/srv/correo-agentes/Maildir"`.

**4. tmux:** `set -g status off`, `set -g prefix None`, `set -g window-size latest`, para
que no se vea ni estorbe desde el tmux del laptop (ver `hilos-remotos.md`).

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
