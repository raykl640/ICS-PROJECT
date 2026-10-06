# PyInstaller spec of the HakiAI desktop app (D34): one folder (dist/HakiAI/) with a console window that shows setup
# progress and the local address. Build with scripts/build_desktop.sh (Linux) or scripts/build_desktop.ps1 (Windows),
# which first build the frontend and the indexes. Models are not bundled: the first run downloads them.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
APP = ROOT / "backend" / "app"
SKIP_SUFFIXES = {".py", ".pyc"}


def app_resources():
    """Every non-Python file under backend/app (YAML, JSON, SQL migrations), at its repository-relative folder."""
    return [
        (str(path), str(path.parent.relative_to(ROOT)))
        for path in sorted(APP.rglob("*"))
        if path.is_file() and path.suffix not in SKIP_SUFFIXES and "__pycache__" not in path.parts
    ]


datas = [
    *app_resources(),
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "data" / "sources.yaml"), "data"),
    (str(ROOT / "data" / "processed" / "chunks.json"), "data/processed"),
    (str(ROOT / "data" / "indexes"), "data/indexes"),
    *collect_data_files("langdetect"),
    *collect_data_files("docx"),
]
hiddenimports = [
    *collect_submodules("backend.app", filter=lambda name: not name.startswith("backend.app.evaluation")),
    # --self-test runs the API on the synthetic test corpus and fake models.
    "backend.tests.corpus",
    "backend.tests.fakes",
    "backend.tests.fake_pipeline",
    *collect_submodules("uvicorn"),
]
excludes = ["tkinter", "matplotlib", "IPython", "pytest", "_pytest", "tensorboard", "torch.utils.tensorboard"]

a = Analysis(
    [str(ROOT / "desktop" / "hakiai.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HakiAI",
    console=True,
    icon=str(ROOT / "desktop" / "icons" / "hakiai.ico") if sys.platform == "win32" else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="HakiAI", upx=False)
