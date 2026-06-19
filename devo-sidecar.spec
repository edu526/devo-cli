# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Devo Desktop sidecar server.
Produces a standalone binary named 'devo-sidecar' that is bundled inside the
Tauri AppImage / .dmg / installer via tauri.conf.json > bundle.externalBin.
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

hidden_imports = [
    # Sidecar package
    "cli_tool.sidecar",
    "cli_tool.sidecar.app",
    "cli_tool.sidecar.bootstrap",
    "cli_tool.sidecar.deps",
    "cli_tool.sidecar.state",
    "cli_tool.sidecar.routers",
    "cli_tool.sidecar.routers.config",
    "cli_tool.sidecar.routers.connections",
    "cli_tool.sidecar.routers.databases",
    "cli_tool.sidecar.routers.hosts",
    "cli_tool.sidecar.routers.instances",
    "cli_tool.sidecar.routers.preflight",
    "cli_tool.sidecar.routers.profiles",
    "cli_tool.sidecar.routers.ws",
    "cli_tool.sidecar.services",
    "cli_tool.sidecar.services.connection_service",
    "cli_tool.sidecar.services.hosts_service",
    "cli_tool.sidecar.services.profile_service",
    # SSM core
    "cli_tool.commands.ssm",
    "cli_tool.commands.ssm.core",
    "cli_tool.commands.ssm.core.config",
    "cli_tool.commands.ssm.core.session",
    "cli_tool.commands.ssm.core.connection_runner",
    "cli_tool.commands.ssm.utils",
    "cli_tool.commands.ssm.utils.hosts_manager",
    # AWS login (profile listing + credential verification)
    "cli_tool.commands.aws_login",
    "cli_tool.commands.aws_login.core",
    "cli_tool.commands.aws_login.core.config",
    "cli_tool.commands.aws_login.core.credentials",
    "cli_tool.commands.aws_login.commands",
    "cli_tool.commands.aws_login.commands.refresh",
    # Config
    "cli_tool.core",
    "cli_tool.core.utils",
    "cli_tool.core.utils.config_manager",
    # Third-party: web framework
    "fastapi",
    "uvicorn",
    "uvicorn.main",
    "uvicorn.config",
    "uvicorn.server",
    "uvicorn.lifespan.on",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.loops.auto",
    "starlette",
    "starlette.applications",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    # Third-party: file watching
    "watchdog",
    "watchdog.observers",
    "watchdog.observers.inotify",
    "watchdog.observers.kqueue",
    "watchdog.observers.fsevents",
    "watchdog.events",
    # Third-party: AWS
    "boto3",
    "botocore",
    # Third-party: validation / serialization
    "pydantic",
    "pydantic.fields",
    "pydantic.main",
    "pydantic_core",
    # Third-party: misc
    "anyio",
    "anyio._backends._asyncio",
    "sniffio",
    "h11",
    "httptools",
    "websockets",
]

hidden_imports += collect_submodules("fastapi")
hidden_imports += collect_submodules("starlette")
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("watchdog")
hidden_imports += collect_submodules("pydantic")
hidden_imports += collect_submodules("pydantic_core")
hidden_imports += collect_submodules("boto3")
hidden_imports += collect_submodules("botocore")
hidden_imports += collect_submodules("anyio")

_charset_datas, _charset_binaries, _charset_hiddenimports = collect_all("charset_normalizer")

datas = []
datas += _charset_datas
datas += collect_data_files("pydantic", include_py_files=True)
datas += collect_data_files("pydantic_core", include_py_files=True)

a = Analysis(
    ["cli_tool/sidecar/__main__.py"],
    pathex=[],
    binaries=_charset_binaries,
    datas=datas,
    hiddenimports=hidden_imports + _charset_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/rth_charset_normalizer.py"],
    excludes=[
        "matplotlib", "numpy", "pandas", "scipy", "PIL", "tkinter",
        "test", "unittest", "pydoc",
        # CLI-only dependencies not needed in the sidecar
        "rich", "click", "strands_agents", "strands", "gitpython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="devo-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
