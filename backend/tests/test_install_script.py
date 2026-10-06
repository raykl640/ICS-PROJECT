"""scripts/install.sh (D34) on a fake release archive: per-user install, checksum check, menu entry, uninstall."""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install.sh"
ASSET = "HakiAI-linux-x86_64.tar.gz"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("bash") is None, reason="the installer is a Linux bash script"
)


def _release(tmp_path: Path, checksum: str | None = None) -> Path:
    """A tarball shaped like the real one (HakiAI/HakiAI + icon), with its .sha256 file."""
    app = tmp_path / "build" / "HakiAI"
    app.mkdir(parents=True)
    (app / "HakiAI").write_text('#!/bin/sh\necho hakiai "$@"\n', encoding="utf-8")
    (app / "HakiAI").chmod(0o755)
    (app / "hakiai.png").write_bytes(b"png")
    tarball = tmp_path / ASSET
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(app, arcname="HakiAI")
    digest = checksum or hashlib.sha256(tarball.read_bytes()).hexdigest()
    Path(f"{tarball}.sha256").write_text(f"{digest}  {ASSET}\n", encoding="utf-8")
    return tarball


def _run(home: Path, *args: str, tarball: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    if tarball is not None:
        env["HAKI_TARBALL"] = str(tarball)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        start_new_session=True,  # no controlling terminal: every question answers "no"
        check=False,
    )


def test_install_then_uninstall(tmp_path: Path) -> None:
    home = tmp_path / "home"
    share = home / ".local" / "share"
    result = _run(home, "--no-ollama", "--no-setup", tarball=_release(tmp_path))
    assert result.returncode == 0, result.stderr
    app = share / "hakiai-app" / "HakiAI"
    link = home / ".local" / "bin" / "hakiai"
    assert link.resolve() == app.resolve()
    assert subprocess.run([str(link), "--x"], capture_output=True, text=True, check=True).stdout == "hakiai --x\n"
    entry = (share / "applications" / "hakiai.desktop").read_text(encoding="utf-8")
    assert f'Exec="{app}"' in entry
    assert (share / "icons" / "hicolor" / "256x256" / "apps" / "hakiai.png").read_bytes() == b"png"

    user_data = share / "HakiAI"
    user_data.mkdir()
    kept = _run(home, "--uninstall")
    assert kept.returncode == 0, kept.stderr
    assert not (share / "hakiai-app").exists()
    assert not link.is_symlink()
    assert not (share / "applications" / "hakiai.desktop").exists()
    assert user_data.is_dir(), "accounts and history are kept unless the user agrees or passes --purge"
    assert _run(home, "--uninstall", "--purge").returncode == 0
    assert not user_data.exists()


def test_a_damaged_download_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "home"
    result = _run(home, "--no-ollama", "--no-setup", tarball=_release(tmp_path, checksum="0" * 64))
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr
    assert not (home / ".local" / "share" / "hakiai-app").exists()


def test_unknown_option_is_an_error(tmp_path: Path) -> None:
    result = _run(tmp_path, "--frobnicate")
    assert result.returncode != 0
    assert "unknown option" in result.stderr
