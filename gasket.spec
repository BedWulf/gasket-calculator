# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# GEOS + вспомогательные модули ezdxf для импорта и раскроя.
shapely_datas, shapely_bins, shapely_hidden = collect_all('shapely')
ezdxf_datas, ezdxf_bins, ezdxf_hidden = collect_all('ezdxf')
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=shapely_bins + ezdxf_bins,
    datas=shapely_datas + ezdxf_datas + [
        ('assets/app_icon.png', 'assets'),
        ('config.py', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
    ] + shapely_hidden + ezdxf_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='GasketCalculator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Сжатие для уменьшения размера
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Без консольного окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.png',  # Иконка
)
# При сборке на Windows проверьте на чистой машине наличие GEOS/Shapely,
# используемых только в новом режиме смешанного раскроя.
