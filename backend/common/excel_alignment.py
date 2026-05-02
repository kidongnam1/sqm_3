"""FastAPI 등에서 utils.sqm_excel_alignment를 안전하게 호출하는 래퍼."""
import logging

logger = logging.getLogger(__name__)


def safe_apply_sqm_workbook(wb) -> None:
    try:
        from utils.sqm_excel_alignment import apply_sqm_workbook_alignment

        apply_sqm_workbook_alignment(wb)
    except Exception as e:
        logger.warning("SQM 엑셀 정렬 적용 실패(무시): %s", e)


def safe_apply_sqm_file(path: str) -> None:
    try:
        from utils.sqm_excel_alignment import apply_sqm_excel_file_alignment

        apply_sqm_excel_file_alignment(path)
    except Exception as e:
        logger.warning("SQM 엑셀 파일 정렬 후처리 실패(무시): %s", e)
