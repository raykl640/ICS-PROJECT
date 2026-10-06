"""Entry point of the packaged HakiAI app (PyInstaller, desktop/hakiai.spec); the logic is in backend/app/desktop."""

from backend.app.desktop.launcher import run

if __name__ == "__main__":
    raise SystemExit(run())
