# -*- mode: python ; coding: utf-8 -*-
# SQM v865 PyInstaller spec — Phase 6 (2026-04-28)
# 빌드: pyinstaller SQM_v865.spec --clean --noconfirm
# 출력: dist/SQM_v865.exe (단일 파일, ~100~150 MB 예상)

from PyInstaller.utils.hooks import collect_all, collect_submodules
import os

# ──────────────────────────────────────────────────────────────────────────────
# 1. 데이터 파일 번들
# ──────────────────────────────────────────────────────────────────────────────
datas = [
    # ── UI 프론트엔드 전체
    ('frontend',                           'frontend'),
    # ── 설정 파일
    ('settings.ini.template',              '.'),
    ('config.py',                          '.'),
    ('config_logging.py',                  '.'),
    ('config_sql.py',                      '.'),
    # ── DB 폴더 (구조만; 실제 DB는 exe 옆에 별도 유지)
    ('data/db',                            'data/db'),
    # ── Excel/PDF 리포트 템플릿
    ('resources/templates',                'resources/templates'),
    # ── AI 선사 프로파일 (BL 파싱용)
    ('features/ai/carrier_profiles',       'features/ai/carrier_profiles'),
    ('features/ai/carrier_templates',      'features/ai/carrier_templates'),
]

# ──────────────────────────────────────────────────────────────────────────────
# 2. Hidden imports — PyInstaller 자동탐지 불가 서브모듈
# ──────────────────────────────────────────────────────────────────────────────
hiddenimports = []

# ── 프로젝트 내부 패키지 전수 포함 (core 추가)
for pkg in ('core', 'engine_modules', 'features', 'parsers',
            'backend', 'utils', 'gui_app_modular'):
    hiddenimports += collect_submodules(pkg)

# ── uvicorn / FastAPI 런타임
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
    'slowapi',
    'slowapi.util',
    'slowapi.errors',
]

# ── 데이터 / PDF 처리
hiddenimports += [
    'pandas',
    'pandas._libs',
    'pandas._libs.tslibs',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'openpyxl.writer.excel',
    'numpy',
    'numpy.core',
    'fitz',           # PyMuPDF (PDF→PNG)
    'pymupdf',
    'PIL',
    'PIL.Image',
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'pdfplumber',
    'sqlite3',
    'python_multipart',
    'multipart',
    'aiofiles',
    'httpx',
    'requests',
]

# ── AI 공급자 (Gemini / OpenAI-compatible / Groq / OpenRouter)
hiddenimports += [
    'google.generativeai',
    'google.genai',
    'google.auth',
    'google.auth.transport.requests',
    'openai',
    'openai.types',
    'groq',
    'anthropic',
    'keyring',
    'bcrypt',
]

# ── PyWebView (Windows WinForms 백엔드)
hiddenimports += [
    'webview',
    'webview.platforms.winforms',
    'clr',
    'clr_loader',
]

# ── ttkbootstrap (gui_app_modular 일부 코드에서 lazy import)
hiddenimports += [
    'ttkbootstrap',
    'ttkbootstrap.constants',
    'ttkbootstrap.style',
]

# ── 기타 표준/공통
hiddenimports += [
    'typing_extensions',
    'dotenv',
    'email.mime.multipart',
    'email.mime.text',
    'python_barcode',
]

# ──────────────────────────────────────────────────────────────────────────────
# 3. collect_all — 필수 바이너리/데이터 자동 수집
# ──────────────────────────────────────────────────────────────────────────────
binaries = []

for pkg in ('pandas', 'openpyxl', 'webview', 'numpy'):
    try:
        pd, pb, ph = collect_all(pkg)
        datas           += pd
        binaries        += pb
        hiddenimports   += ph
    except Exception as _e:
        print(f'[spec] collect_all({pkg}) 실패 (무시): {_e}')

# PyMuPDF — 패키지명 두 가지 모두 시도
for pkg in ('fitz', 'pymupdf'):
    try:
        pd, pb, ph = collect_all(pkg)
        datas           += pd
        binaries        += pb
        hiddenimports   += ph
        break
    except Exception as _e:
        print(f'[spec] collect_all({pkg}) 실패 (무시): {_e}')

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
        # 개발 전용 — EXE에 불필요
        'pytest',
        'black',
        'IPython',
        'jupyter',
        'notebook',
        # 데이터과학 무거운 패키지
        'matplotlib',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        # tkinter 테스트 코드 (tkinter 자체는 제외하지 않음 — gui_app_modular 의존)
        'tkinter.test',
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
    upx=False,              # UPX 비활성 — Windows Defender 오탐 방지
    runtime_tmpdir=None,
    console=False,          # 콘솔창 없음; 로그는 sqm_debug.log 에 기록
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/favicon.ico',
)
