"""GUI tabs module
v8.1.7: ReturnTabMixin, MoveTabMixin 추가 (신규 탭)
v5.5.3 P8: SearchTab, AdvancedTabs, PivotTab 제거 (죽은 코드)
"""

from .allocation_lot_overview_mixin import AllocationLotOverviewMixin
from .allocation_tab import AllocationTabMixin
from .cargo_overview_tab import CargoOverviewTabMixin, ReturnTabMixin
from .dashboard_tab import DashboardTabMixin
from .inventory_tab import InventoryTabMixin
from .log_tab import LogTabMixin
from .move_tab import MoveTabMixin
from .outbound_scheduled_tab import OutboundScheduledTabMixin
from .picked_tab import PickedTabMixin
from .sold_tab import SoldTabMixin
from .scan_tab import ScanTabMixin
from .summary_tab import SummaryTabMixin
from .tonbag_tab import TonbagTabMixin

__all__ = [
    'AllocationLotOverviewMixin',
    'AllocationTabMixin',
    'CargoOverviewTabMixin',
    'DashboardTabMixin',
    'InventoryTabMixin',
    'MoveTabMixin',
    'OutboundScheduledTabMixin',
    'PickedTabMixin',
    'ReturnTabMixin',
    'SoldTabMixin',
    'ScanTabMixin',
    'TonbagTabMixin',
    'LogTabMixin',
    'SummaryTabMixin',
]
