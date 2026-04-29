# 🚀 SQM v864.3 — 실행 방법 (10초 가이드)

> **진입점은 단 1개입니다: `main_webview.py`**
> 그 외 옛 파일은 모두 `archive/legacy_entrypoints/` 로 격리됨.

---

## ✅ 가장 빠른 실행 — 아래 셋 중 아무거나

### 방법 ①: 더블클릭 (권장)
- `실행.bat` 더블클릭

### 방법 ②: Python 직접
```cmd
python main_webview.py
```

### 방법 ③: 정식 EXE (배포 후)
- 바탕화면 **📦 SQM Inventory** 아이콘 더블클릭
- (먼저 `installer\build.bat` 으로 빌드 필요)

---

## 📁 진입점 매트릭스

| 종류 | 파일 | 위치 | 용도 |
|---|---|---|---|
| **메인 진입점** | `main_webview.py` | 루트 | Python 실행 (개발/검토) |
| **사용자 더블클릭** | `실행.bat` | 루트 | 한글 파일명, 더블클릭 즉시 실행 |
| **포터블 EXE** | `SQM_v864_3.exe` | `build/dist/` | PyInstaller 빌드 결과 |
| **인스톨러** | `SQM_v864_3_Setup.exe` | `installer/dist/` | Inno Setup 빌드 결과 |
| 옛 진입점 (사용 X) | `run.py`, `run_bootstrap.py`, `run_*.bat` | `archive/legacy_entrypoints/` | 보존만 |

---

## ⚙️ 빌드 명령

```cmd
REM 포터블 EXE 만들기
pyinstaller build\SQM_v864_3.spec --noconfirm

REM 인스톨러까지 한 번에
installer\build.bat
```

---

## 🆘 문제 발생 시

1. `python --version` 으로 3.10+ 확인
2. `pip install -r requirements_webview.txt` 재실행
3. 포트 8765 충돌 확인: `netstat -ano | findstr 8765`
4. 로그: `%APPDATA%\SQM\logs\sqm_webview.log`
5. 진단 ZIP: `python tools\log_collector.py`

---

**작성:** Ruby, 2026-04-21
**버전:** v8.6.4.3
