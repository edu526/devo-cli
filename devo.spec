# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Devo CLI Tool
Generates standalone binaries for Linux, macOS, and Windows
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# Collect all submodules
hidden_imports = [
    'cli_tool',
    'cli_tool.cli',
    'cli_tool.config',
    'cli_tool.agents',
    'cli_tool.agents.base_agent',
    'cli_tool.autocomplete',
    'cli_tool.autocomplete.commands',
    'cli_tool.autocomplete.core',
    'cli_tool.aws_login',
    'cli_tool.aws_login.commands',
    'cli_tool.aws_login.core',
    'cli_tool.code_reviewer',
    'cli_tool.code_reviewer.commands',
    'cli_tool.code_reviewer.commands.analyze',
    'cli_tool.code_reviewer.core',
    'cli_tool.code_reviewer.core.analyzer',
    'cli_tool.code_reviewer.core.git_utils',
    'cli_tool.code_reviewer.prompt',
    'cli_tool.code_reviewer.prompt.analysis_rules',
    'cli_tool.code_reviewer.prompt.code_reviewer',
    'cli_tool.code_reviewer.prompt.output_format',
    'cli_tool.code_reviewer.prompt.security_standards',
    'cli_tool.code_reviewer.prompt.tools_guide',
    'cli_tool.code_reviewer.tools',
    'cli_tool.code_reviewer.tools.code_analyzer',
    'cli_tool.code_reviewer.tools.file_reader',
    'cli_tool.codeartifact',
    'cli_tool.codeartifact.commands',
    'cli_tool.codeartifact.core',
    'cli_tool.commit',
    'cli_tool.commit.commands',
    'cli_tool.commit.commands.generate',
    'cli_tool.commit.core',
    'cli_tool.commit.core.generator',
    'cli_tool.config_cmd',
    'cli_tool.config_cmd.commands',
    'cli_tool.config_cmd.core',
    'cli_tool.dynamodb',
    'cli_tool.dynamodb.commands',
    'cli_tool.dynamodb.commands.cli',
    'cli_tool.dynamodb.commands.describe_table',
    'cli_tool.dynamodb.commands.export_table',
    'cli_tool.dynamodb.commands.list_tables',
    'cli_tool.dynamodb.commands.list_templates',
    'cli_tool.dynamodb.core',
    'cli_tool.dynamodb.core.exporter',
    'cli_tool.dynamodb.core.parallel_scanner',
    'cli_tool.dynamodb.utils',
    'cli_tool.dynamodb.utils.filter_builder',
    'cli_tool.dynamodb.utils.templates',
    'cli_tool.dynamodb.utils.utils',
    'cli_tool.eventbridge',
    'cli_tool.eventbridge.commands',
    'cli_tool.eventbridge.core',
    'cli_tool.eventbridge.utils',
    'cli_tool.ssm',
    'cli_tool.ssm.commands',
    'cli_tool.ssm.core',
    'cli_tool.ssm.utils',
    'cli_tool.upgrade',
    'cli_tool.upgrade.commands',
    'cli_tool.upgrade.core',
    'cli_tool.ui',
    'cli_tool.ui.console_ui',
    'cli_tool.utils',
    'cli_tool.utils.aws',
    'cli_tool.utils.config_manager',
    'cli_tool.utils.git_utils',
    'cli_tool.utils.version_check',
    # Third-party dependencies
    'click',
    'requests',
    'rich',
    'rich.console',
    'rich.live',
    'rich.panel',
    'rich.syntax',
    'rich.table',
    'rich.text',
    'rich.markdown',
    'rich.progress',
    'rich.spinner',
    'rich.style',
    'rich.theme',
    'rich.traceback',
    'rich._loop',
    'rich._wrap',
    'rich.abc',
    'rich.align',
    'rich.ansi',
    'rich.bar',
    'rich.box',
    'rich.cells',
    'rich.color',
    'rich.columns',
    'rich.constrain',
    'rich.containers',
    'rich.control',
    'rich.default_styles',
    'rich.diagnose',
    'rich.emoji',
    'rich.errors',
    'rich.file_proxy',
    'rich.filesize',
    'rich.highlighter',
    'rich.json',
    'rich.jupyter',
    'rich.layout',
    'rich.logging',
    'rich.markup',
    'rich.measure',
    'rich.padding',
    'rich.pager',
    'rich.palette',
    'rich.pretty',
    'rich.prompt',
    'rich.protocol',
    'rich.region',
    'rich.repr',
    'rich.rule',
    'rich.scope',
    'rich.screen',
    'rich.segment',
    'rich.status',
    'rich.styled',
    'rich.terminal_theme',
    'rich.tree',
    'strands_agents',
    'strands',
    'git',
    'gitdb',
    'pydantic',
    'pydantic.fields',
    'pydantic.main',
    'pydantic_core',
    'boto3',
    'botocore',
]

# Collect all submodules for packages that need them
hidden_imports += collect_submodules('rich')
hidden_imports += collect_submodules('markdown_it')
hidden_imports += collect_submodules('pygments')
hidden_imports += collect_submodules('strands_agents')
hidden_imports += collect_submodules('strands')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('pydantic_core')
hidden_imports += collect_submodules('click')
hidden_imports += collect_submodules('git')
hidden_imports += collect_submodules('gitdb')

# Collect data files
datas = []

# Collect all data files from dependencies
datas += collect_data_files('strands_agents', include_py_files=True)
datas += collect_data_files('strands', include_py_files=True)
datas += collect_data_files('pydantic', include_py_files=True)
datas += collect_data_files('pydantic_core', include_py_files=True)

# Copy metadata for rich (fixes Windows PyInstaller issue)
# See: https://github.com/pyinstaller/pyinstaller/issues/7113
try:
    datas += copy_metadata('rich')
except Exception:
    pass

try:
    datas += copy_metadata('markdown-it-py')
except Exception:
    pass

try:
    datas += copy_metadata('pygments')
except Exception:
    pass

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
        'test',
        'unittest',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys

# Linux: onefile mode (single binary, easier distribution)
# macOS/Windows: onedir mode (faster startup, no temp extraction overhead)
if sys.platform == 'linux':
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
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    # macOS/Windows: onedir mode for faster startup
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='devo',
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

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='devo',
    )
