import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from peak import config
from peak.api import app, mount_web
from peak.db import User

BACKEND = Path(__file__).resolve().parents[1]


def local(monkeypatch, token="t0k3n"):
    monkeypatch.setattr(config, "LOCAL", True)
    monkeypatch.setattr(config, "LOCAL_TOKEN", token)
    monkeypatch.setattr(config, "LOCAL_STUDENT", "addison")


def test_enter_with_token_signs_in_the_student(db, monkeypatch):
    local(monkeypatch)
    db.add(User(username="addison", password_hash="x", role="student"))
    db.commit()
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        r = c.get("/api/local/enter?t=t0k3n", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/today/"
        assert c.get("/api/me").json()["username"] == "addison"


def test_enter_rejects_wrong_or_missing_token_and_is_off_outside_local_mode(db, monkeypatch):
    db.add(User(username="addison", password_hash="x", role="student"))
    db.commit()
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        assert c.get("/api/local/enter?t=anything").status_code == 404  # local mode off
        local(monkeypatch)
        assert c.get("/api/local/enter?t=wrong").status_code == 404
        assert c.get("/api/local/enter").status_code == 404
        assert c.get("/api/me").status_code == 401


def test_local_mode_refuses_non_loopback_hosts(db, monkeypatch):
    """A web page that rebinds its own domain to 127.0.0.1 still sends its own Host header."""
    local(monkeypatch)
    with TestClient(app, base_url="http://evil.example") as c:
        assert c.get("/api/health").status_code == 400
    with TestClient(app, base_url="http://localhost:8765") as c:
        assert c.get("/api/health").status_code == 200


def test_web_ui_is_served_beside_the_api(tmp_path):
    (tmp_path / "index.html").write_text("<p>home</p>")
    (tmp_path / "today").mkdir()
    (tmp_path / "today" / "index.html").write_text("<p>today</p>")
    fresh = FastAPI()

    @fresh.get("/api/health")
    def health():
        return {"status": "ok"}

    assert mount_web(fresh, tmp_path)
    with TestClient(fresh) as c:
        assert "today" in c.get("/today/").text
        assert c.get("/api/health").json() == {"status": "ok"}
    assert not mount_web(FastAPI(), tmp_path / "missing")


def run_local(*args, home):
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    for k in ("DATABASE_URL", "DATA_DIR", "PEAK_DEMO", "APP_BASE_URL", "PEAK_TEST_DATABASE_URL"):
        env.pop(k, None)
    return subprocess.run([sys.executable, "-m", "peak.local", *args, "--home", str(home)],
                          capture_output=True, text=True, env=env, cwd=BACKEND, timeout=120)


def test_launcher_prepares_a_fresh_mac_data_folder_and_backs_up(tmp_path):
    home = tmp_path / "Peak"
    out = run_local("prepare", home=home)
    assert out.returncode == 0, out.stderr
    info = json.loads(out.stdout.strip().splitlines()[-1])
    assert info["questions_ready"] == 0 and (home / "peak.db").exists()
    assert oct(home.stat().st_mode & 0o777) == "0o700"
    again = run_local("prepare", home=home)  # idempotent: migrations and seed run twice cleanly
    assert again.returncode == 0, again.stderr
    b = run_local("backup", home=home)
    assert b.returncode == 0, b.stderr and Path(b.stdout.strip()).exists()
    assert len(list((home / "backups").glob("peak-*.db"))) == 1
