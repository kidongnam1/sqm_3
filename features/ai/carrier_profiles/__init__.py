# -*- coding: utf-8 -*-
"""
features/ai/carrier_profiles — SQM v8.7.0
=========================================
Carrier Profile YAML plugin (옵셔널).

기존 Python 레지스트리(`bl_carrier_registry.CARRIER_TEMPLATES`)를
**교체하지 않고 보완**하는 설정 저장소 역할. 사용자가 UI에서 선택한 선사의
파싱 힌트/정규식/컨테이너 prefix 등을 YAML 1개 파일로 관리할 수 있게 한다.

노출 API:
    from features.ai.carrier_profiles import (
        load_all_profiles,   # Dict[str, dict]
        get_profile,         # Optional[dict]
        merge_with_registry, # dict → dict
    )
"""
from __future__ import annotations

try:
    from .carrier_profile_loader import (
        load_all_profiles,
        get_profile,
        merge_with_registry,
    )
    __all__ = ["load_all_profiles", "get_profile", "merge_with_registry"]
except Exception:  # pragma: no cover — loader 자체 실패도 앱은 계속
    __all__ = []
