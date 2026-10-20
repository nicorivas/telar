"""Las cuentas del bus (telar.cuentas): una por persona, en la configuración de nats-server."""

import stat

import pytest

from telar import cuentas

HASH = "$2b$11$" + "a" * 53


def test_nombres():
    assert cuentas.validar("marcelo") == "marcelo"
    for malo in ("", "Nico", "1nico", "ni co", "ni.co", "a" * 33, "$G"):
        with pytest.raises(cuentas.ErrorDeCuentas):
            cuentas.validar(malo)


def test_configuracion_una_cuenta_por_persona():
    conf = cuentas.configuracion({"nico": HASH, "marcelo": HASH})
    assert conf.index("marcelo: {") < conf.index("nico: {")
    assert conf.count("jetstream: enabled") == 2
    assert f'users: [ {{ user: "nico", password: "{HASH}" }} ]' in conf


def test_escribir_y_leer(tmp_path):
    base = tmp_path / "bus"
    conf = cuentas.escribir(base, {"nico": HASH, "pablo": HASH})
    assert cuentas.leer(base) == {"nico": HASH, "pablo": HASH}
    assert stat.S_IMODE(conf.stat().st_mode) == 0o600
    assert stat.S_IMODE(base.stat().st_mode) == 0o700
    assert stat.S_IMODE((base / "personas" / "nico.hash").stat().st_mode) == 0o600
    cuentas.escribir(base, {"nico": HASH})          # quitar a una persona borra su hash
    assert cuentas.leer(base) == {"nico": HASH}
    assert "pablo" not in conf.read_text()


def test_leer_rechaza_lo_que_no_es_un_hash(tmp_path):
    (tmp_path / "personas").mkdir()
    (tmp_path / "personas" / "nico.hash").write_text("secreto-en-claro\n")
    with pytest.raises(cuentas.ErrorDeCuentas):
        cuentas.leer(tmp_path)


def test_hashear():
    pytest.importorskip("bcrypt")
    import bcrypt

    h = cuentas.hashear("s" * 48)
    assert cuentas.BCRYPT.match(h)
    assert bcrypt.checkpw(b"s" * 48, h.encode())
