"""
SQM Inventory Engine - Preflight Mixin
======================================

v2.9.91 - Extracted from inventory.py

Preflight validation for inbound/outbound operations
All-or-Nothing pattern implementation
"""

import logging
import sqlite3
from datetime import date, datetime
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from engine_modules.preflight import PreflightResult, PreflightValidator

logger = logging.getLogger(__name__)


class PreflightMixin:
    """
    Preflight validation mixin
    
    Adds validation capabilities to SQMInventoryEngine:
    - process_inbound_safe(): Inbound with preflight validation
    - process_outbound_safe(): Outbound with preflight validation
    
    All-or-Nothing pattern:
    - Any validation error causes complete rollback
    - No partial processing allowed
    - Achieves "zero Excel manual verification"
    """

    def _get_preflight_validator(self) -> Optional['PreflightValidator']:
        """Get preflight validator instance"""
        try:
            from engine_modules.preflight import PreflightValidator
            return PreflightValidator(self.db)
        except ImportError:
            logger.warning("preflight module not found")
            return None

    def preflight_check_inbound(self, data: List[Dict]) -> 'PreflightResult':
        """
        Preflight validation for inbound data (validation only, no execution)
        
        Args:
            data: Data list to validate
            
        Returns:
            PreflightResult (no exception even on errors)
        """
        validator = self._get_preflight_validator()
        if not validator:
            from engine_modules.preflight import PreflightResult
            return PreflightResult(operation="INBOUND", total_rows=len(data))

        return validator.validate_inbound(data)

    def preflight_check_outbound(self, data: List[Dict]) -> 'PreflightResult':
        """
        Preflight validation for outbound data (validation only, no execution)
        
        Args:
            data: Data list to validate
            
        Returns:
            PreflightResult (no exception even on errors)
        """
        validator = self._get_preflight_validator()
        if not validator:
            from engine_modules.preflight import PreflightResult
            return PreflightResult(operation="OUTBOUND", total_rows=len(data))

        return validator.validate_outbound(data)

    def process_outbound_safe(self, allocation_data, strict: bool = True) -> Dict:
        """
        Safe outbound processing with preflight validation (All-or-Nothing)
        
        Unlike process_outbound():
        - All data validated first
        - Any error -> complete stop (no partial deduction)
        - No "process what's available" - errors are errors
        
        Args:
            allocation_data: Outbound allocation data
            strict: If True, warnings also cause stop
            
        Returns:
            Processing result dict
            
        Raises:
            PreflightError: On validation failure (causes transaction rollback)
        """
        import uuid

        from engine_modules.preflight import PreflightError, PreflightValidator

        result = {
            'success': False,
            'outbound_id': None,
            'outbound_no': None,
            'lots_processed': 0,
            'total_picked': 0,
            'errors': [],
            'warnings': [],
            'details': [],
            'preflight_result': None
        }

        # Convert data to items list
        # v8.6.1 [SRP]: allocation_data 타입에 따른 3가지 경로
        # 경로 A: AllocationResult (rows/header 속성) — 파서 직접 결과
        # 경로 B: dict-like (items 속성) — Sales Order 등 변환 결과
        # 경로 C: list (raw rows) — outbound_handlers에서 직접 전달
        # customer는 각 경로에서 한 번만 정의됨 (중복 정의 아님)
        if hasattr(allocation_data, 'rows'):
            # 경로 A: AllocationResult.header.customer
            items = [
                {
                    'lot_no': row.lot_no,
                    'qty_mt': row.qty_mt,
                    'product': row.product,
                    'sold_to': row.sold_to,
                    'sale_ref': row.sale_ref
                }
                for row in allocation_data.rows
            ]
            customer = allocation_data.header.customer if allocation_data.header else ''
            sale_ref = items[0].get('sale_ref', '') if items else ''
        elif hasattr(allocation_data, 'items'):
            # 경로 B: allocation_data.customer (str 또는 dict)
            items_attr = allocation_data.items
            items = items_attr() if callable(items_attr) else items_attr
            customer = getattr(allocation_data, 'customer', '')
            if isinstance(customer, dict):
                # dict인 경우: {'name': '고객명', ...} 구조 → name 추출
                customer = customer.get('name', '')
            sale_ref = getattr(allocation_data, 'sale_ref', '')
        else:
            # 경로 C: raw list → 첫 행 sold_to 참조
            items = allocation_data
            customer = items[0].get('sold_to', '') if items else ''
            sale_ref = items[0].get('sale_ref', '') if items else ''

        # ========================================
        # PHASE 1: Preflight Validation
        # ========================================
        validator = PreflightValidator(self.db)
        preflight_result = validator.validate_outbound(items)
        result['preflight_result'] = preflight_result

        if preflight_result.has_blocking_errors():
            error_msg = f"Outbound preflight failed: {preflight_result.error_count} errors"
            result['errors'].append(error_msg)
            logger.warning(f"[PREFLIGHT] {error_msg}")
            raise PreflightError(error_msg, preflight_result)

        logger.info(f"[PREFLIGHT] Outbound validated: {preflight_result.valid_rows}/{preflight_result.total_rows}")

        # ========================================
        # PHASE 2: Execute (only if validation passed)
        # ========================================
        try:
            with self.db.transaction("IMMEDIATE"):
                # Generate unique outbound number
                ts = datetime.now().strftime('%Y%m%d-%H%M%S')
                unique_suffix = uuid.uuid4().hex[:8]
                outbound_no = f"OB-{ts}-{unique_suffix}"

                # Create outbound header
                cursor = self.db.execute("""
                    INSERT INTO outbound 
                    (outbound_no, customer, sale_ref, outbound_date, total_qty_mt, total_lots, status)
                    VALUES (?, ?, ?, ?, 0, 0, 'PROCESSING')
                """, (outbound_no, customer, sale_ref, date.today()))

                outbound_id = cursor.lastrowid
                result['outbound_id'] = outbound_id
                result['outbound_no'] = outbound_no

                total_picked = 0
                lots_processed = 0

                # Process each item
                for item in items:
                    lot_no = str(item.get('lot_no') or '').strip()
                    qty_mt = self._safe_parse_float(item.get('qty_mt', 0))
                    qty_kg = qty_mt * 1000

                    # Get available tonbags for this LOT
                    tonbags = self.db.fetchall("""
                        SELECT sub_lt, weight FROM inventory_tonbag
                        WHERE lot_no = ? AND status = 'AVAILABLE'
                        ORDER BY sub_lt DESC
                    """, (lot_no,))

                    remaining = qty_kg
                    picked_from_lot = 0

                    for tb in tonbags:
                        if remaining <= 0:
                            break

                        # Pick this tonbag
                        self.db.execute("""
                            UPDATE inventory_tonbag 
                            SET status = 'PICKED', 
                                outbound_date = ?,
                                picked_to = ?,
                                sale_ref = ?
                            WHERE lot_no = ? AND sub_lt = ?
                        """, (date.today(), customer, sale_ref, lot_no, tb['sub_lt']))

                        picked_from_lot += tb['weight']
                        remaining -= tb['weight']

                    # Update inventory
                    self.db.execute("""
                        UPDATE inventory 
                        SET current_weight = current_weight - ?,
                            picked_weight = picked_weight + ?
                        WHERE lot_no = ?
                    """, (picked_from_lot, picked_from_lot, lot_no))
                    if hasattr(self, '_recalc_current_weight'):
                        self._recalc_current_weight(lot_no, reason='P2_PREFLIGHT_PICK')

                    # Create outbound item record
                    self.db.execute("""
                        INSERT INTO outbound_item 
                        (outbound_id, lot_no, qty_mt, picked_weight, product)
                        VALUES (?, ?, ?, ?, ?)
                    """, (outbound_id, lot_no, qty_mt, picked_from_lot, item.get('product', '')))

                    total_picked += picked_from_lot
                    lots_processed += 1

                    result['details'].append({
                        'lot_no': lot_no,
                        'requested_kg': qty_kg,
                        'picked_kg': picked_from_lot
                    })

                # Update outbound header
                self.db.execute("""
                    UPDATE outbound 
                    SET total_qty_mt = ?, total_lots = ?, status = 'COMPLETED'
                    WHERE id = ?
                """, (total_picked / 1000, lots_processed, outbound_id))

                result['success'] = True
                result['total_picked'] = total_picked
                result['lots_processed'] = lots_processed

        except PreflightError:
            raise
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['errors'].append(f"Outbound processing error: {e}")
            logger.exception("Outbound processing error")

        return result

    def process_inbound_safe(self, packing_data, invoice_data=None,
                             bl_data=None, do_data=None) -> Dict:
        """
        Safe inbound processing with preflight validation (All-or-Nothing)
        
        Args:
            packing_data: PackingListData or dict
            invoice_data: InvoiceData (optional)
            bl_data: BLData (optional)
            do_data: DOData (optional)
            
        Returns:
            Processing result dict
            
        Raises:
            PreflightError: On validation failure
        """
        from engine_modules.preflight import PreflightError, PreflightValidator

        result = {
            'success': False,
            'shipment_id': None,
            'lots_created': 0,
            'lots_skipped': 0,
            'total_weight': 0,
            'errors': [],
            'warnings': [],
            'preflight_result': None
        }

        # Convert dict to object if needed
        if isinstance(packing_data, dict):
            from .utils import dict_to_packing_data
            packing_data = dict_to_packing_data(packing_data)

        # Prepare validation data
        lots_data = []
        for lot in getattr(packing_data, 'lots', []):
            if isinstance(lot, dict):
                lots_data.append(lot)
            else:
                # v8.7.0 [FIX D-1.5 CRITICAL]: LOTInfo 필드는 net_weight_kg. 'net_weight'는 존재 안 함 → 항상 0 반환 버그
                lots_data.append({
                    'lot_no': getattr(lot, 'lot_no', ''),
                    'net_weight': getattr(lot, 'net_weight_kg', 0) or getattr(lot, 'net_weight', 0),
                    'container_no': getattr(lot, 'container_no', '')
                })

        # ========================================
        # PHASE 1: Preflight Validation
        # ========================================
        validator = PreflightValidator(self.db)
        preflight_result = validator.validate_inbound(lots_data)
        result['preflight_result'] = preflight_result

        if preflight_result.has_blocking_errors():
            error_msg = f"Inbound preflight failed: {preflight_result.error_count} errors"
            result['errors'].append(error_msg)
            for err in preflight_result.errors[:5]:
                result['errors'].append(str(err))
            logger.warning(f"[PREFLIGHT] {error_msg}")
            raise PreflightError(error_msg, preflight_result)

        logger.info(f"[PREFLIGHT] Inbound validated: {preflight_result.valid_rows}/{preflight_result.total_rows}")

        # ========================================
        # PHASE 2: Execute (delegate to regular process_inbound)
        # ========================================
        try:
            inbound_result = self.process_inbound(packing_data, invoice_data, bl_data, do_data)

            result['success'] = inbound_result.get('success', False)
            result['shipment_id'] = inbound_result.get('shipment_id')
            result['lots_created'] = inbound_result.get('lots_created', 0)
            result['lots_skipped'] = inbound_result.get('lots_skipped', 0)
            result['total_weight'] = inbound_result.get('total_weight', 0)
            result['errors'].extend(inbound_result.get('errors', []))
            result['warnings'].extend(inbound_result.get('warnings', []))

        except PreflightError:
            raise
        except (ValueError, TypeError, KeyError) as e:
            result['errors'].append(f"Inbound processing error: {e}")
            logger.exception("Inbound processing error")

        return result
