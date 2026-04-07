"""
procedures/delete_procedures.py
================================
삭제(DELETE) 저장 프로시저 번역

번역 대상:
    1. usp_delete_author_storebook  → delete_author()
    2. usp_delete_book_storebook    → delete_book()

=============================================================
[원본 SQL 분석 메모]
=============================================================

■ usp_delete_author_storebook
    단순 단일 테이블 삭제: DELETE FROM Authors WHERE Id = @pid
    반환: @presult bit

    ⚠️ 주의: AuthorBook 테이블에 FK가 걸려 있으면 삭제 실패합니다.
       원본 SQL은 이를 처리하지 않습니다.
       이 번역에서는 FK 위반 오류를 명확히 안내합니다.

■ usp_delete_book_storebook
    2단계 순서로 삭제 (명시적 트랜잭션 사용):
        1단계: DELETE FROM AuthorBook WHERE Isbn = @pisbn
               → 먼저 연결 데이터 삭제
        2단계: DELETE FROM Books WHERE Isbn = @pisbn
               → 그 다음 책 본체 삭제

    @@ROWCOUNT 조건:
        - 1단계에서 삭제된 행이 0이면 → 삭제할 것 없음 (@pmsgerror 설정)
        - 2단계에서 정확히 1행이 삭제되어야 성공

    트랜잭션 처리:
        T-SQL: BEGIN TRAN → (조건부) COMMIT / ROLLBACK
        Python: get_connection() 직접 사용 + 명시적 commit/rollback
"""

from __future__ import annotations
from typing import Optional
import pyodbc
from db.connection import get_connection, get_db_cursor
from db.result import ProcedureResult


# ─────────────────────────────────────────────────────────────────────────────
# 1. usp_delete_author_storebook
# ─────────────────────────────────────────────────────────────────────────────

def delete_author(author_id: int) -> ProcedureResult:
    """
    저자를 Authors 테이블에서 삭제합니다.

    T-SQL 원본:
        EXEC usp_delete_author_storebook
            @pid       = 1,
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    Args:
        author_id: 삭제할 저자의 Id (PK)

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 1 (성공 시)
            .error        = 오류 메시지

    ⚠️ FK 주의:
        AuthorBook 테이블에 이 저자의 데이터가 남아 있으면
        FK 제약 위반으로 삭제가 실패합니다.
        저자를 삭제하기 전에 먼저 AuthorBook에서 해당 행을 삭제하거나
        delete_book()을 사용하세요.

    사용 예:
        result = delete_author(author_id=1)
        if result.success:
            print("저자 삭제 완료")
        else:
            print("오류:", result.error)
    """
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")

    sql = "DELETE FROM Authors WHERE Id = ?"

    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (author_id,))
            rows = cursor.rowcount

            if rows == 0:
                return ProcedureResult(
                    error=f"해당 저자를 찾을 수 없습니다. Id={author_id}"
                )
            return ProcedureResult(success=True, rows_affected=rows)

    except Exception as exc:
        # FK 위반 오류를 더 명확하게 안내
        if "FOREIGN KEY" in str(exc) or "FK" in str(exc):
            return ProcedureResult(
                error=(
                    f"저자 삭제 실패: AuthorBook 테이블에 연결된 데이터가 있습니다. "
                    f"먼저 연결된 책을 삭제하세요. (Id={author_id})"
                )
            )
        return ProcedureResult(error=f"delete_author 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. usp_delete_book_storebook
# ─────────────────────────────────────────────────────────────────────────────

def delete_book(isbn: str) -> ProcedureResult:
    """
    책과 관련 저자-책 연결 데이터를 트랜잭션으로 삭제합니다.

    T-SQL 원본:
        EXEC usp_delete_book_storebook
            @pisbn     = '9780134494166',
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    삭제 순서 (원본 T-SQL과 동일):
        1. AuthorBook WHERE Isbn = isbn  (연결 데이터 먼저 삭제)
        2. Books WHERE Isbn = isbn       (책 본체 삭제)

    두 단계 모두 성공해야 commit, 하나라도 실패하면 rollback.

    Args:
        isbn: 삭제할 책의 ISBN

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 삭제된 총 행 수 (AuthorBook + Books)
            .error        = 오류 메시지

    사용 예:
        result = delete_book("9780134494166")
        if result.success:
            print(f"삭제 완료 (총 {result.rows_affected}개 행)")
        else:
            print("오류:", result.error)
    """
    if not isbn or not isbn.strip():
        return ProcedureResult(error="isbn은 필수입니다.")

    isbn = isbn.strip()
    conn: Optional[pyodbc.Connection] = None

    try:
        conn = get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        # ── 1단계: AuthorBook 삭제 ─────────────────────────────────────────
        cursor.execute("DELETE FROM AuthorBook WHERE Isbn = ?", (isbn,))
        author_book_rows = cursor.rowcount

        if author_book_rows == 0:
            # 원본: @pmsgerror = 'Nothing to delete' → ROLLBACK
            conn.rollback()
            return ProcedureResult(
                error=f"삭제할 데이터가 없습니다. Isbn={isbn}"
            )

        # ── 2단계: Books 삭제 ──────────────────────────────────────────────
        cursor.execute("DELETE FROM Books WHERE Isbn = ?", (isbn,))
        book_rows = cursor.rowcount

        if book_rows != 1:
            # 원본: @@ROWCOUNT = 1 이어야 성공 → 아니면 ROLLBACK
            conn.rollback()
            return ProcedureResult(
                error=(
                    f"책 삭제 실패: 예상 1행, 실제 {book_rows}행. "
                    f"트랜잭션이 롤백되었습니다. Isbn={isbn}"
                )
            )

        # ── 모두 성공 → COMMIT ────────────────────────────────────────────
        conn.commit()
        return ProcedureResult(
            success=True,
            rows_affected=author_book_rows + book_rows,
        )

    except Exception as exc:
        if conn:
            conn.rollback()
        return ProcedureResult(error=f"delete_book 오류 (롤백됨): {exc}")

    finally:
        if conn:
            conn.close()
