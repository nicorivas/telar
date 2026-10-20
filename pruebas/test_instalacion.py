"""Lo que escribe `telar instalar` (telar.instalacion): el servicio de telar serve y el [bus]."""

import plistlib
import tomllib

from telar import instalacion


def test_argumentos():
    assert instalacion.argumentos() == ["serve", "--web"]
    assert instalacion.argumentos(nodo=True, equipo=True) == ["serve", "--equipo", "--nodo", "--web"]


def test_path_sin_repetir_y_con_lo_basico():
    donde = {"telar": "/h/.local/bin/telar", "tmux": "/usr/bin/tmux", "claude": "/h/.local/bin/claude"}
    path = instalacion.ruta_path(donde.get).split(":")
    assert path[0] == "/h/.local/bin"
    assert path.count("/h/.local/bin") == 1 and path.count("/usr/bin") == 1
    assert {"/usr/local/bin", "/usr/bin", "/bin"} <= set(path)


def test_unidad_systemd():
    u = instalacion.unidad_systemd("/h/.local/bin/telar", ["serve", "--nodo", "--web"], "/h/.local/bin:/bin",
                                   esperar_tailscale=True)
    assert "ExecStart=/h/.local/bin/telar serve --nodo --web\n" in u
    assert "Environment=PATH=/h/.local/bin:/bin\n" in u
    assert "KillMode=process" in u and "ExecStartPre=" in u
    sin = instalacion.unidad_systemd("/t", ["serve", "--web"], "/bin", esperar_tailscale=False)
    assert "ExecStartPre" not in sin


def test_plist_es_valido():
    texto = instalacion.plist_launchd("/Users/a b/telar", ["serve", "--web"], "/x:/bin", "/Users/a/l.log")
    d = plistlib.loads(texto.encode())
    assert d["Label"] == instalacion.ETIQUETA
    assert d["ProgramArguments"] == ["/Users/a b/telar", "serve", "--web"]
    assert d["EnvironmentVariables"]["PATH"] == "/x:/bin"
    assert d["KeepAlive"] is True and d["StandardOutPath"] == "/Users/a/l.log"


def test_bloque_bus_es_toml():
    base = 'raiz = "~/x"\n'
    datos = tomllib.loads(base + instalacion.bloque_bus("nats://100.1.2.3:4222", "~/.config/telar/bus.token", "ana"))
    assert datos["bus"] == {"url": "nats://100.1.2.3:4222", "token": "~/.config/telar/bus.token", "persona": "ana"}
    assert "persona" not in tomllib.loads(instalacion.bloque_bus("nats://h:4222", "t"))["bus"]


def test_escribir_si_cambia(tmp_path):
    f = tmp_path / "a" / "s.service"
    assert instalacion.escribir_si_cambia(f, "x\n") is True
    assert instalacion.escribir_si_cambia(f, "x\n") is False
    assert instalacion.escribir_si_cambia(f, "y\n") is True and f.read_text() == "y\n"
