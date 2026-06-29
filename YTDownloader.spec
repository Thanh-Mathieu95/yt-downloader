# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        ('yt-dlp.exe', '.'),
    ],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'flask',
        'flask.templating',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy packages not needed by this app
    excludes=[
        'yt_dlp',
        'numpy', 'pandas', 'matplotlib', 'scipy', 'sklearn',
        'IPython', 'ipykernel', 'jupyter', 'notebook',
        'pygame', 'PIL', 'cv2', 'tkinter', '_tkinter',
        'PyQt5', 'PyQt6', 'wx', 'gi',
        'tensorflow', 'torch', 'keras',
        'pytest', 'unittest',
        'sphinx', 'docutils',
        'zmq', 'pyzmq',
        'psutil', 'pymongo', 'sqlalchemy',
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
    name='YTDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # keep console so users can see errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YTDownloader',
)
