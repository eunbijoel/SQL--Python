"""
procedures/modify_procedures.py
================================
수정(UPDATE) 저장 프로시저 번역

번역 대상:
    1. usp_modified_author_storebook      → modify_author()
    2. usp_modified_book_storebook        → modify_book()
    3. usp_modified_authorbook_storebook  → modify_author_book()

=============================================================
[원본 SQL 분석 메모]
=============================================================

■ usp_modified_author_storebook
    WHERE 조건: Id = @pid (PK 기준)
    수정 컬럼: Firstname, Surname, Surname2
    반환: @presult bit (성공=1)

■ usp_modified_book_storebook
    WHERE 조건: Isbn = @pisbn
    수정 컬럼: Title, Pages, [Year], CategoryId

    ⚠️ 원본 SQL 버그 발견:
        SET [Year] = @ppages   ← @pyear가 아닌 @ppages로 잘못 매핑되어 있음
        즉, Year 컬럼에 Pages 값이 들어가는 버그입니다.
        이 번역에서는 의도대로 [Year] = @pyear 로 수정하고,
        원본 버그를 주석으로 명시합니다.

■ usp_modified_authorbook_storebook
    WHERE 조건: IdAuthor = @pauthorid
    수정 컬럼: IdAuthor, Isbn

    ⚠️ 주의:
        WHERE IdAuthor = @pauthorid 이면서 SET IdAuthor = @pauthorid 이면
        IdAuthor는 실제로 변경되지 않고, Isbn만 변경됩니다.
        즉, 이 프로시저는 "특정 저자의 ISBN을 변경"하는 용도입니다.
"""

from __future__ import annotations
from typing import Optional
from db.connection import get_db_cursor
from db.result import ProcedureResult


# ─────────────────────────────────────────────────────────────────────────────
# 1. usp_modified_author_storebook
# ─────────────────────────────────────────────────────────────────────────────

def modify_author(
    author_id: int,
    firstname: str,
    surname: str,
    surname2: Optional[str] = None,
) -> ProcedureResult:
    """
    기존 저자 정보를 수정합니다.

    T-SQL 원본:
        EXEC usp_modified_author_storebook
            @pid       = 1,
            @pfirstname = 'Jane',
            @psurname   = 'Doe',
            @psurname2  = NULL,
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    Args:
        author_id: 수정할 저자의 Id (PK)
        firstname: 새 이름
        surname:   새 성
        surname2:  새 두 번째 성 (선택)

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 1 (성공 시)
            .error        = 오류 메시지 (실패 또는 ID 없음)

    사용 예:
        result = modify_author(author_id=1, firstname="Jane", surname="Doe")
        if result.success:
            print("수정 완료")
        else:
            print("오류:", result.error)
    """
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")
    if not firstname or not firstname.strip():
        return ProcedureResult(error="firstname(이름)은 필수입니다.")
    if not surname or not surname.strip():
        return ProcedureResult(error="surname(성)은 필수입니다.")

    sql = """
        UPDATE Authors
        SET
            Firstname = ?,
            Surname   = ?,
            Surname2  = ?
        WHERE Id = ?
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (firstname.strip(), surname.strip(), surname2, author_id))
            rows = cursor.rowcount

            if rows == 0:
                return ProcedureResult(
                    error=f"해당 저자를 찾을 수 없습니다. Id={author_id}"
                )
            return ProcedureResult(success=True, rows_affected=rows)

    except Exception as exc:
        return ProcedureResult(error=f"modify_author 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. usp_modified_book_storebook
# ─────────────────────────────────────────────────────────────────────────────

def modify_book(
    isbn: str,
    title: str,
    pages: Optional[int] = None,
    year: Optional[int] = None,
    category_id: Optional[int] = None,
) -> ProcedureResult:
    """
    기존 책 정보를 수정합니다.

    T-SQL 원본:
        EXEC usp_modified_book_storebook
            @pisbn     = '9780134494166',
            @ptitle    = 'Clean Code (2nd Ed.)',
            @ppages    = 450,
            @pyear     = 2020,
            @pcategory = 3,
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    ⚠️ 원본 버그 수정:
        원본 T-SQL: SET [Year] = @ppages  ← 버그! Pages 값이 Year에 들어감
        이 번역:    SET [Year] = @pyear   ← 의도에 맞게 수정

    Args:
        isbn:        수정할 책의 ISBN (PK)
        title:       새 제목
        pages:       새 페이지 수 (선택)
        year:        새 출판 연도 (선택)
        category_id: 새 카테고리 ID (선택)

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 1 (성공 시)
            .error        = 오류 메시지

    사용 예:
        result = modify_book("9780134494166", "Clean Code 2nd", pages=450, year=2020)
        if result.success:
            print("책 정보 수정 완료")
    """
    if not isbn or not isbn.strip():
        return ProcedureResult(error="isbn은 필수입니다.")
    if not title or not title.strip():
        return ProcedureResult(error="title(제목)은 필수입니다.")
    if len(title) > 256:
        return ProcedureResult(error="title이 256자를 초과합니다.")

    # 원본 버그: SET [Year] = @ppages → 수정: SET [Year] = @pyear
    sql = """
        UPDATE Books
        SET
            Title      = ?,
            Pages      = ?,
            [Year]     = ?,
            CategoryId = ?
        WHERE Isbn = ?
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (title.strip(), pages, year, category_id, isbn.strip()))
            rows = cursor.rowcount

            if rows == 0:
                return ProcedureResult(
                    error=f"해당 책을 찾을 수 없습니다. Isbn={isbn}"
                )
            return ProcedureResult(success=True, rows_affected=rows)

    except Exception as exc:
        return ProcedureResult(error=f"modify_book 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. usp_modified_authorbook_storebook
# ─────────────────────────────────────────────────────────────────────────────

def modify_author_book(
    author_id: int,
    new_isbn: str,
) -> ProcedureResult:
    """
    특정 저자에 연결된 책의 ISBN을 변경합니다.
    (AuthorBook 연결 테이블 수정)

    T-SQL 원본:
        EXEC usp_modified_authorbook_storebook
            @pauthorid = 1,
            @pisbn     = '9780134494166',
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    ※ 동작 설명:
        WHERE IdAuthor = @pauthorid (저자 ID로 행을 찾음)
        SET Isbn = @pisbn           (그 저자의 ISBN을 새 값으로 변경)
        SET IdAuthor = @pauthorid   (IdAuthor는 사실상 변경 없음)

    Args:
        author_id: 대상 저자의 Id
        new_isbn:  새로 연결할 책의 ISBN

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 변경된 행 수
            .error        = 오류 메시지

    ⚠️ 주의:
        저자가 여러 책과 연결되어 있으면 모든 행이 같은 ISBN으로 변경됩니다.
        이 동작이 의도된 것인지 확인 후 사용하세요.

    사용 예:
        result = modify_author_book(author_id=1, new_isbn='9780201633610')
        if result.success:
            print(f"{result.rows_affected}개 행 수정 완료")
    """
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")
    if not new_isbn or not new_isbn.strip():
        return ProcedureResult(error="new_isbn은 필수입니다.")

    sql = """
        UPDATE AuthorBook
        SET
            IdAuthor = ?,
            Isbn     = ?
        WHERE IdAuthor = ?
    """

    try:
        with get_db_cursor() as cursor:
            # IdAuthor는 SET과 WHERE 모두 같은 값 → Isbn만 실질적으로 변경
            cursor.execute(sql, (author_id, new_isbn.strip(), author_id))
            rows = cursor.rowcount

            if rows == 0:
                return ProcedureResult(
                    error=f"해당 저자-책 연결을 찾을 수 없습니다. IdAuthor={author_id}"
                )
            return ProcedureResult(success=True, rows_affected=rows)

    except Exception as exc:
        return ProcedureResult(error=f"modify_author_book 오류: {exc}")
