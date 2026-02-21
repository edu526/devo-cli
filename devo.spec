# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Devo CLI Tool
Generates standalone binaries for Linux, macOS, and Windows
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules
hidden_imports = [
    'cli_tool',
    'cli_tool.cli',
    'cli_tool.config',
    'cli_tool.commands',
    'cli_tool.commands.code_reviewer',
    'cli_tool.commands.codeartifact_login',
    'cli_tool.commands.commit_prompt',
    'cli_tool.commands.completion',
    'cli_tool.commands.generate',
    'cli_tool.commands.upgrade',
    'cli_tool.agents',
    'cli_tool.agents.base_agent',
    'cli_tool.code_reviewer',
    'cli_tool.code_reviewer.analyzer',
    'cli_tool.code_reviewer.git_utils',
    'cli_tool.code_reviewer.prompt',
    'cli_tool.code_reviewer.tools',
    'cli_tool.templates',
    'cli_tool.ui',
    'cli_tool.ui.console_ui',
    'cli_tool.utils',
    'cli_tool.utils.aws',
    'cli_tool.utils.aws_profile',
    'cli_tool.utils.git_utils',
    'cli_tool.utils.templates',
    # Third-party dependencies
    'click',
    'jinja2',
    'requests',
    'rich',
    'strands_agents',
    'git',
    'pydantic',
    'boto3',
    'botocore',
]

# Collect all submodules for packages that need them
hidden_imports += collect_submodules('rich')
hidden_imports += collect_submodules('strands_agents')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('click')
hidden_imports += collect_submodules('jinja2')
hidden_imports += collect_submodules('gitpython')

# Collect data files (templates)
datas = [
    ('cli_tool/templates/*.j2', 'cli_tool/templates'),
]

# Collect all data files from dependencies
datas += collect_data_files('strands_agents')
datas += collect_data_files('rich')
datas += collect_data_files('pydantic')
datas += collect_data_files('click')

a = Analysis(
    ['cli_tool/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='devo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
