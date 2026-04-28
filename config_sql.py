"""
SQM - SQL 호환 유틸 (v5.7.8 config 분할)
=========================================
DB 타입(SQLite/PostgreSQL)에 따른 SQL 표현 생성.
출고/리포트 등에서 from config import sql_* 로 사용.
"""


def sql_group_concat(db_type: str, column: str, separator: str = ',') -> str:
    """DB 타입에 따른 문자열 집계. SQLite: GROUP_CONCAT, PostgreSQL: STRING_AGG"""
    if (db_type or '').lower() == 'postgresql':
        return f"STRING_AGG({column}::TEXT, '{separator}')"
    return f"GROUP_CONCAT({column}, '{separator}')"


def sql_ifnull(column: str, default: str) -> str:
    """NULL 대체 (COALESCE 호환)"""
    return f"COALESCE({column}, {default})"


def sql_date_format(db_type: str, column: str, format_str: str) -> str:
    """DB 타입에 따른 날짜 포맷. SQLite: strftime, PostgreSQL: to_char"""
    if (db_type or '').lower() == 'postgresql':
        pg = format_str.replace('%Y', 'YYYY').replace('%m', 'MM').replace('%d', 'DD')
        pg = pg.replace('%H', 'HH24').replace('%M', 'MI').replace('%S', 'SS')
        return f"to_char({column}, '{pg}')"
    return f"strftime('{format_str}', {column})"


def sql_current_timestamp() -> str:
    """현재 타임스탬프 (양쪽 동일)"""
    return "CURRENT_TIMESTAMP"


def sql_auto_increment(db_type: str) -> str:
    """자동 증가 컬럼 타입. SQLite: INTEGER PRIMARY KEY AUTOINCREMENT, PG: SERIAL PRIMARY KEY"""
    if (db_type or '').lower() == 'postgresql':
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"
