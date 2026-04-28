"""
SQM 재고관리 - GUI 모듈화 패키지
================================

v2.9.99 - gui_app.py 10,000줄을 모듈로 분리
v2.9.99 - SQMInventoryApp export 추가 (실제 사용 전환)

구조:
    gui_app_modular/
    ├── __init__.py          # 이 파일
    ├── main_app.py          # 메인 앱 클래스 ★
    ├── tabs/                # 탭 모듈
    │   ├── inventory_tab.py
    │   ├── tonbag_tab.py
    │   └── search_tab.py
    ├── dialogs/             # 다이얼로그
    │   ├── lot_detail.py
    │   └── settings.py
    ├── handlers/            # 이벤트 핸들러
    │   ├── import_handlers.py
    │   └── export_handlers.py
    ├── mixins/              # 기능 믹스인
    │   ├── menu_mixin.py
    │   └── feature_mixin.py
    └── utils/               # 유틸리티
        ├── constants.py
        ├── safe_utils.py
        └── helpers.py
"""

# ★★★ v2.9.99: 메인 앱 클래스 export ★★★
# v3.6.0: SQMInventoryAppFull (모든 mixin 포함) 사용
from .main_app import SQMInventoryAppFull as SQMInventoryApp
from .utils.constants import (
    APP_NAME,
    HAS_PANDAS,
    HAS_TTKBOOTSTRAP,
    __version__,
)
from .utils.safe_utils import (
    find_column,
    safe_date,
    safe_float,
    safe_int,
    safe_str,
)

__all__ = [
    # ★ 메인 앱 클래스
    'SQMInventoryApp',
    # 상수
    '__version__',
    'APP_NAME',
    'HAS_TTKBOOTSTRAP',
    'HAS_PANDAS',
    # 유틸리티
    'safe_str',
    'safe_float',
    'safe_int',
    'safe_date',
    'find_column',
]
