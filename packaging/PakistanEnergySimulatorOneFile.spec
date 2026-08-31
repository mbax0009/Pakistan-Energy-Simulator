from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).resolve().parent

uvicorn_data, uvicorn_binaries, uvicorn_hidden = collect_all("uvicorn")

datas = [
    (str(project_root / "frontend" / "dist" / "client"), "frontend/dist/client"),
    (str(project_root / "data" / "reference"), "data/reference"),
]
datas += uvicorn_data

hiddenimports = [
    "simulator_api.main",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
] + uvicorn_hidden

a = Analysis(
    [str(project_root / "simulator_api" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=uvicorn_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "boto3",
        "botocore",
        "copernicusmarine",
        "dask",
        "h5py",
        "matplotlib",
        "notebook",
        "numcodecs",
        "pyarrow",
        "pytest",
        "s3fs",
        "scipy",
        "sklearn",
        "xarray",
        "zarr",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PakistanEnergySimulator-OneFile",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
