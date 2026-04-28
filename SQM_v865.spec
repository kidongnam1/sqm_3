# -*- mode: python ; coding: utf-8 -*-
# SQM v865 PyInstaller spec
# 빌드: pyinstaller SQM_v865.spec --clean
# 출력: dist/SQM_v865.exe (단일 파일, ~80~120 MB 예상)

from PyInstaller.utils.hooks import collect_all, collect_submodules
import os

# ──────────────────────────────────────────────────────────────────────────────
# 1. 데이터 파일 번들
# ──────────────────────────────────────────────────────────────────────────────
datas = [
    # UI
    ('frontend',          'frontend'),
    # 설정
    ('config.py',         '.'),
    ('config_logging.py', '.'),
    ('config_sql.py',     '.'),
    # DB 폴더 (구조만, 실제 DB는 exe 옆에 별도 유지)
    ('data/db',           'data/db'),
    # 선사 프로파일 (BL 파싱 캐리어 데이터)
    ('features/ai/carrier_profiles', 'features/ai/carrier_profiles'),
    ('features/ai/carrier_templates', 'features/ai/carrier_templates'),
]

# ──────────────────────────────────────────────────────────────────────────────
# 2. Hidden imports — PyInstaller 자동탐지 불가 서브모듈
# ──────────────────────────────────────────────────────────────────────────────
hiddenimports = []

# 프로젝트 내부 패키지 전수 포함
for pkg in ('engine_modules', 'features', 'parsers', 'backend', 'utils'):
    hiddenimports += collect_submodules(pkg)

# uvicorn / FastAPI 런타임
hiddenimports += [
    'fastapi',
    'fastapi.middleware.cors',
    'uvicorn',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'pydantic',
    'pydantic.v1',
    'anyio',
    'anyio._backends._asyncio',
    'anyio._backends._trio',
]

# 데이터/PDF 처리
hiddenimports += [
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'fitz',          # PyMuPDF (PDF→PNG, Gemini fallback)
    'PIL',
    'PIL.Image',
    'sqlite3',
]

# PyWebView
hiddenimports += [
    'webview',
    'webview.platforms.winforms',
    'clr',
    'clr_loader',
]

# Gemini (선택적 — API 키 없어도 실행 가능해야 함)
hiddenimports += [
    'google.generativeai',
    'google.genai',
    'google.auth',
]

# 기타
hiddenimports += [
    'ttkbootstrap',
    'requests',
    'httpx',
    'aiofiles',
    'multipart',
    'python_multipart',
    'dotenv',
    'typing_extensions',
    'email.mime.multipart',
    'email.mime.text',
]

# ──────────────────────────────────────────────────────────────────────────────
# 3. collect_all — 필수 바이너리/데이터 자동 수집
# ──────────────────────────────────────────────────────────────────────────────
binaries = []
for pkg in ('pandas', 'openpyxl', 'webview'):
    try:
        pd, pb, ph = collect_all(pkg)
        datas    += pd
        binaries += pb
        hiddenimports += ph
    except Exception as _e:
        print(f'[spec] collect_all({pkg}) 실패 (무시): {_e}')

# PyMuPDF (fitz) — 별도 처리 (패키지명이 다름)
try:
    pd, pb, ph = collect_all('fitz')
    datas    += pd
    binaries += pb
    hiddenimports += ph
except Exception as _e:
    print(f'[spec] collect_all(fitz) 실패 (무시): {_e}')

# ──────────────────────────────────────────────────────────────────────────────
# 4. Analysis
# ──────────────────────────────────────────────────────────────────────────────
a = Analysis(
    ['main_webview.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter.test',
        'pytest',
        'black',
        'IPython',
        'jupyter',
        'notebook',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ──────────────────────────────────────────────────────────────────────────────
# 5. EXE — onefile, no console
# ──────────────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SQM_v865',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX 비활성 — Windows Defender 오탐 방지
    runtime_tmpdir=None,
    console=False,      # 콘솔창 없음 (로그는 sqm_debug.log에 기록)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/favicon.ico',
)
