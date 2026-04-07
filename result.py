"""
db/result.py
------------
모든 저장 프로시저 번역 함수의 공통 반환 타입.

T-SQL의 OUTPUT 파라미터 패턴을 Python 데이터클래스로 대체합니다.

T-SQL 원본:
    @presult    bit out         → result.success  (bool)
    @presultid  int out         → result.result_id (int | None)
    @pmsgerror  varchar(256) out → result.error   (str | None)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProcedureResult:
    """
    저장 프로시저 실행 결과를 담는 공통 클래스.

    Attributes:
        success:      True = 성공, False = 실패 (T-SQL의 @presult bit)
        result_id:    INSERT 후 생성된 ID, 또는 ISBN 등 (T-SQL의 @presultid)
        rows:         SELECT 결과 행 목록 (list of dict)
        rows_affected: 변경된 행 수 (T-SQL의 @@ROWCOUNT)
        error:        오류 메시지 (T-SQL의 @pmsgerror)
    """
    success: bool = False
    result_id: Optional[Any] = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    rows_affected: int = 0
    error: Optional[str] = None


def rows_as_dicts(cursor) -> list[dict[str, Any]]:
    """cursor.fetchall() 결과를 dict 리스트로 변환합니다."""
    if cursor.description is None:
        return []
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def row_as_dict(cursor) -> Optional[dict[str, Any]]:
    """cursor.fetchone() 결과를 dict로 변환합니다. 없으면 None."""
    if cursor.description is None:
        return None
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))
