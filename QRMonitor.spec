# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

BLOCK_CIPHER = None

try:
    project_root = Path(__file__).resolve().parent
except NameError:
    project_root = Path(os.getcwd())

hidden_imports = [
    # python standard library - required by urllib3/requests
    'http',
    'http.client',
    'http.cookiejar',
    'http.cookies',
    'http.server',
    # opencv
    'cv2',
    'cv2.gapi',
    'cv2.mat_wrapper',
    'cv2.misc',
    # pyzbar
    'pyzbar',
    'pyzbar.pyzbar',
    # numpy
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    # pywin32
    'win32gui',
    'win32con',
    'win32clipboard',
    'win32com.client',
    'win32com.client.gencache',
    'win32com.client.makepy',
    'win32com.client.selecttlb',
    # pydantic
    'pydantic',
    'pydantic.dataclasses',
    'pydantic.fields',
    'pydantic.validators',
    'pydantic.main',
    'pydantic.type_adapter',
    # yaml
    'yaml',
    # pil
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageGrab',
    # mss
    'mss',
    # loguru
    'loguru',
    # pystray
    'pystray',
    # keyboard
    'keyboard',
    # wxauto
    'wxauto',
    'wxauto.wxauto',
    'wxauto.uiautomation',
    'wxauto.elements',
    'wxauto.utils',
    'wxauto.color',
    'wxauto.errors',
    'wxauto.languages',
    # comtypes (wxauto dependency)
    'comtypes',
    'comtypes.client',
    'comtypes.stream',
]

datas = [
    (str(project_root / 'config.yaml'), '.'),
]

binaries = []

datas += collect_data_files('pyzbar', include_py_files=True)
binaries += collect_dynamic_libs('pyzbar')

datas += collect_data_files('cv2')
binaries += collect_dynamic_libs('cv2')

for mod_name in ['win32com', 'win32clipboard', 'win32gui', 'win32con']:
    datas += collect_data_files(mod_name)
    binaries += collect_dynamic_libs(mod_name)

datas += copy_metadata('pydantic')

for mod_name in ['wxauto', 'comtypes']:
    datas += collect_data_files(mod_name)
    binaries += collect_dynamic_libs(mod_name)

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'xml',
        'xmlrpc',
        'pdb',
        'py_compile',
        'doctest',
        'test',
        'distutils',
        'setuptools',
        'pydoc',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QRMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

app = BUNDLE(
    exe,
    name='QRMonitor.exe',
    icon=None,
    bundle_identifier=None,
)