"""
db/connection.py
----------------
BookStore 데이터베이스 연결 관리 모듈.

환경변수로 연결 정보를 설정합니다 (.env 파일 참조).
pyodbc를 사용하며 SQL Server 원본 환경과 동일합니다.

설치 필요:
    pip install pyodbc python-dotenv
"""

import os
from contextlib import contextmanager
import pyodbc
from dotenv import load_dotenv

load_dotenv()

_CONNECTION_STRING = (
    f"DRIVER={os.getenv('DB_DRIVER', '{ODBC Driver 18 for SQL Server}')};"
    f"SERVER={os.getenv('DB_SERVER', 'localhost')};"
    f"DATABASE={os.getenv('DB_NAME', 'BookStore')};"
    f"UID={os.getenv('DB_USER', '')};"
    f"PWD={os.getenv('DB_PASSWORD', '')};"
)


def get_connection() -> pyodbc.Connection:
    """pyodbc 연결 객체를 반환합니다. 호출자가 직접 닫아야 합니다."""
    return pyodbc.connect(_CONNECTION_STRING)


@contextmanager
def get_db_cursor(autocommit: bool = False):
    """
    커서를 yield하는 컨텍스트 매니저.

    - 성공 시 자동 commit
    - 실패 시 자동 rollback
    - 항상 커서와 연결을 닫음

    사용 예:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ...")
    """
    conn = get_connection()
    conn.autocommit = autocommit
    cursor = conn.cursor()
    try:
        yield cursor
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
