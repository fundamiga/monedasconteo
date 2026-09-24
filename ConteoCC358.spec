# -*- mode: python ; coding: utf-8 -*-
# Spec file para empaquetar ConteoCC358 como ejecutable Windows

block_cipher = None

a = Analysis(
    ['app_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Carpeta config completa (credentials.json, datos.py)
        ('config/credentials.json', 'config'),
        ('config/datos.py',         'config'),
        ('config/__init__.py',      'config'),
        # Carpeta sheets
        ('sheets/google_sheets.py', 'sheets'),
        ('sheets/__init__.py',      'sheets'),
        # Carpeta serial_reader
        ('serial_reader/cc358_reader.py', 'serial_reader'),
        ('serial_reader/__init__.py',     'serial_reader'),
        # Widgets adicionales
        ('selector_trabajador.py', '.'),
        ('ventana_conteo.py',      '.'),
        ('vista_tabla.py',         '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'gspread',
        'google.oauth2',
        'google.oauth2.service_account',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'threading',
        'tkinter',
        'tkinter.messagebox',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'node_modules',
        'src',
        '.next',
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
    [],
    exclude_binaries=True,
    name='ConteoCC358',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # Con consola temporal para diagnóstico de lectura serial
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
    upx=True,
    upx_exclude=[],
    name='ConteoCC358',
)
