# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Devo CLI Tool
Generates standalone binaries for Linux, macOS, and Windows
"""

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# Collect all submodules
hidden_imports = [
    'cli_tool',
    'cli_tool.cli',
    'cli_tool.config',
    # Core infrastructure
    'cli_tool.core',
    'cli_tool.core.agents',
    'cli_tool.core.agents.base_agent',
    'cli_tool.core.ui',
    'cli_tool.core.ui.console_ui',
    'cli_tool.core.utils',
    'cli_tool.core.utils.aws',
    'cli_tool.core.utils.aws_profile',
    'cli_tool.core.utils.config_manager',
    'cli_tool.core.utils.git_utils',
    'cli_tool.core.utils.version_check',
    # Commands
    'cli_tool.commands',
    'cli_tool.commands.autocomplete',
    'cli_tool.commands.autocomplete.commands',
    'cli_tool.commands.autocomplete.core',
    'cli_tool.commands.aws_login',
    'cli_tool.commands.aws_login.command',
    'cli_tool.commands.aws_login.commands',
    'cli_tool.commands.aws_login.core',
    'cli_tool.commands.aws_login.core.config',
    'cli_tool.commands.aws_login.core.credentials',
    'cli_tool.commands.code_reviewer',
    'cli_tool.commands.code_reviewer.commands',
    'cli_tool.commands.code_reviewer.commands.analyze',
    'cli_tool.commands.code_reviewer.core',
    'cli_tool.commands.code_reviewer.core.analyzer',
    'cli_tool.commands.code_reviewer.core.git_utils',
    'cli_tool.commands.code_reviewer.prompt',
    'cli_tool.commands.code_reviewer.prompt.analysis_rules',
    'cli_tool.commands.code_reviewer.prompt.code_reviewer',
    'cli_tool.commands.code_reviewer.prompt.output_format',
    'cli_tool.commands.code_reviewer.prompt.security_standards',
    'cli_tool.commands.code_reviewer.prompt.tools_guide',
    'cli_tool.commands.code_reviewer.tools',
    'cli_tool.commands.code_reviewer.tools.code_analyzer',
    'cli_tool.commands.code_reviewer.tools.file_reader',
    'cli_tool.commands.codeartifact',
    'cli_tool.commands.codeartifact.commands',
    'cli_tool.commands.codeartifact.core',
    'cli_tool.commands.commit',
    'cli_tool.commands.commit.commands',
    'cli_tool.commands.commit.commands.generate',
    'cli_tool.commands.commit.core',
    'cli_tool.commands.commit.core.generator',
    'cli_tool.commands.config_cmd',
    'cli_tool.commands.config_cmd.commands',
    'cli_tool.commands.config_cmd.core',
    'cli_tool.commands.dynamodb',
    'cli_tool.commands.dynamodb.commands',
    'cli_tool.commands.dynamodb.commands.cli',
    'cli_tool.commands.dynamodb.commands.describe_table',
    'cli_tool.commands.dynamodb.commands.export_table',
    'cli_tool.commands.dynamodb.commands.list_tables',
    'cli_tool.commands.dynamodb.commands.list_templates',
    'cli_tool.commands.dynamodb.core',
    'cli_tool.commands.dynamodb.core.exporter',
    'cli_tool.commands.dynamodb.core.parallel_scanner',
    'cli_tool.commands.dynamodb.core.query_optimizer',
    'cli_tool.commands.dynamodb.core.multi_query_executor',
    'cli_tool.commands.dynamodb.utils',
    'cli_tool.commands.dynamodb.utils.filter_builder',
    'cli_tool.commands.dynamodb.utils.templates',
    'cli_tool.commands.dynamodb.utils.utils',
    'cli_tool.commands.eventbridge',
    'cli_tool.commands.eventbridge.commands',
    'cli_tool.commands.eventbridge.core',
    'cli_tool.commands.eventbridge.utils',
    'cli_tool.commands.ssm',
    'cli_tool.commands.ssm.commands',
    'cli_tool.commands.ssm.commands.database',
    'cli_tool.commands.ssm.commands.forward',
    'cli_tool.commands.ssm.commands.hosts',
    'cli_tool.commands.ssm.commands.instance',
    'cli_tool.commands.ssm.commands.shortcuts',
    'cli_tool.commands.ssm.core',
    'cli_tool.commands.ssm.core.config',
    'cli_tool.commands.ssm.core.port_forwarder',
    'cli_tool.commands.ssm.core.session',
    'cli_tool.commands.ssm.utils',
    'cli_tool.commands.ssm.utils.hosts_manager',
    'cli_tool.commands.upgrade',
    'cli_tool.commands.upgrade.command',
    'cli_tool.commands.upgrade.commands',
    'cli_tool.commands.upgrade.core',
    'cli_tool.commands.upgrade.core.downloader',
    'cli_tool.commands.upgrade.core.installer',
    'cli_tool.commands.upgrade.core.platform',
    'cli_tool.commands.upgrade.core.version',
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

# charset_normalizer ships compiled C extensions (.so/.pyd) that collect_submodules misses.
# collect_all bundles Python modules + binaries + data files so the extension is always included.
_charset_datas, _charset_binaries, _charset_hiddenimports = collect_all('charset_normalizer')

# Collect data files
datas = []
datas += _charset_datas

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
    binaries=_charset_binaries,
    datas=datas,
    hiddenimports=hidden_imports + _charset_hiddenimports,
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
