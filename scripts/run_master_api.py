# -*- coding: utf-8 -*-
"""
run_master.bat 의 `claude --print` 대체 초안 — Anthropic Messages API (REST).

- 환경변수 ANTHROPIC_API_KEY 필수 — Windows 사용자/시스템 환경변수에 등록해 두면 됩니다 (CMD 에서 매번 set 불필요).
- 선택: ANTHROPIC_MODEL (기본 claude-sonnet-4-20250514), ANTHROPIC_MAX_TOKENS (기본 8192).

주의:
  이 스크립트는 “텍스트 응답만” 받습니다. Claude Code 처럼 도구로 파일을 수정하지 않습니다.
  실행 계획·체크리스트·요약 용도이며, 실제 수정은 Cursor/사람이 진행합니다.

사용 예:
  cd D:\\program\\SQM_inventory\\SQM_v866_CLEAN
  set ANTHROPIC_API_KEY=sk-ant-api03-...
  python scripts\\run_master_api.py --phase 1

  복구 프롬프트:
  python scripts\\run_master_api.py --recover

표준 출력에 모델 응답 본문을 인쇄하고, REPORTS/run_master_last_api_response.txt 에도 저장합니다.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
DEFAULT_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "8192"))
MAX_CONTEXT_CHARS = int(os.environ.get("RUN_MASTER_MAX_CONTEXT_CHARS", "180000"))


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path, label: str, bucket: list[str], budget: int) -> None:
    if not path.exists():
        bucket.append(f"\n\n### [{label}] (없음: {path})\n")
        return
    raw = path.read_text(encoding="utf-8", errors="replace")
    if len(raw) > budget:
        raw = raw[:budget] + f"\n\n... [잘림: {label} 원본 초과, RUN_MASTER_MAX_CONTEXT_CHARS 조정 가능]\n"
    bucket.append(f"\n\n### [{label}] `{path.name}`\n\n{raw}")


def _build_context(phase: int | None, recover: bool) -> tuple[str, str]:
    root = _root()
    parts: list[str] = []

    budget = max(4000, MAX_CONTEXT_CHARS // 4)
    _read_text(root / "CLAUDE.md", "CLAUDE.md", parts, budget)
    _read_text(root / "progress.txt", "progress.txt", parts, budget // 2)

    if recover:
        _read_text(root / "error_report.md", "error_report.md", parts, budget // 2)
        user_extra = (
            "위는 error_report.md와 progress.txt 컨텍스트다. "
            "문제 원인·수정 우선순위·progress.txt에 쓸 RECOVERY 한 줄을 제시하라. "
            "코드 블록으로 바로 적용 가능한 패치 초안이 있으면 제시하라."
        )
        system = _system_base() + "\n모드: RECOVERY (에러 복구 조언)"
        return system, "".join(parts) + "\n\n" + user_extra

    master_map = {
        1: root / "Claude_SQM_v866_SPLIT" / "MASTER_P1.md",
        2: root / "Claude_SQM_v866_SPLIT" / "MASTER_P2.md",
        3: root / "Claude_SQM_v866_SPLIT" / "MASTER_P3.md",
        4: root / "Claude_SQM_v866_SPLIT" / "MASTER_P4.md",
    }
    if phase not in master_map:
        raise ValueError("phase는 1~4 또는 --recover")
    _read_text(master_map[phase], f"MASTER_P{phase}", parts, budget)

    instructions = {
        1: (
            "Phase 1 (Bug Fix): MASTER_P1과 progress.txt 기준으로 남은 작업·검증 명령을 단계별로 나열하라. "
            "Ruby 정책: 에러 시 중단하지 말고 복구 방향을 제시하라."
        ),
        2: (
            "Phase 2 (Backend API): MASTER_P2 기준 API 보완 항목과 검증 커맨드를 정리하라."
        ),
        3: (
            "Phase 3 (Frontend JS): MASTER_P3 기준 프론트 연결·node --check 항목을 정리하라."
        ),
        4: (
            "Phase 4 (QA + ZIP): MASTER_P4 기준 교차검증·pytest·ZIP·DONE.md 체크리스트를 정리하라. "
            "실제 파일 생성은 사람/IDE가 수행한다는 점을 명시하라."
        ),
    }[phase]

    user = (
        "".join(parts)
        + "\n\n---\n\n"
        + "### 지시\n\n"
        + instructions
        + "\n\n한국어로 간결하게. 불필요한 서론 생략."
    )
    system = _system_base() + f"\n모드: PHASE {phase}"
    return system, user


def _system_base() -> str:
    return (
        "당신은 SQM Inventory v866 마이그레이션 프로젝트의 기술 조력자다. "
        "프로젝트 루트는 사용자가 제공한 파일 내용을 따른다. "
        "engine_modules/, features/parsers/, utils/ 등 원본 레이어는 문서상 수정 금지일 수 있다. "
        "답변은 실행 가능한 명령과 파일 경로를 구체적으로 적어라."
    )


def _messages_api(api_key: str, model: str, max_tokens: int, system: str, user_text: str) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
    }
    data = json.dumps(body).encode("utf-8")
    req = Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.exception("Anthropic HTTPError")
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {err_body}") from e
    except URLError as e:
        raise RuntimeError(f"네트워크 오류: {e}") from e


def _extract_text(payload: dict[str, Any]) -> str:
    blocks = payload.get("content") or []
    out: list[str] = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text") or "")
    return "\n".join(out).strip() or json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Anthropic API runner for run_master prompts")
    ap.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="MASTER Phase")
    ap.add_argument("--recover", action="store_true", help="error_report.md + progress 복구 프롬프트")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = ap.parse_args()

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        logging.error("ANTHROPIC_API_KEY 환경변수가 없습니다.")
        return 2

    if args.recover:
        system, user = _build_context(None, recover=True)
    elif args.phase:
        system, user = _build_context(args.phase, recover=False)
    else:
        ap.print_help()
        return 2

    total_len = len(system) + len(user)
    if total_len > MAX_CONTEXT_CHARS:
        logging.warning("컨텍스트가 큼 (%s chars). RUN_MASTER_MAX_CONTEXT_CHARS 로 조정 가능.", total_len)

    logging.info("호출 model=%s max_tokens=%s user_chars=%s", args.model, args.max_tokens, len(user))
    payload = _messages_api(key, args.model, args.max_tokens, system, user)
    text = _extract_text(payload)

    reports = _root() / "REPORTS"
    reports.mkdir(parents=True, exist_ok=True)
    out_path = reports / "run_master_last_api_response.txt"
    out_path.write_text(text, encoding="utf-8")

    print(text)
    print(f"\n---\n저장: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        logging.error("%s", e)
        raise SystemExit(1)
