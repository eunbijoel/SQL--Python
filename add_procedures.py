"""
procedures/add_procedures.py
==============================
추가(INSERT) 저장 프로시저 번역

번역 대상:
    1. usp_add_author_storebook      → add_author()
    2. usp_add_book_storebook        → add_book()
    3. usp_add_authorbook_storebook  → add_author_book()
    4. usp_add_category_storebook    → add_category()

=============================================================
[원본 SQL 분석 메모]
=============================================================

■ 공통 OUTPUT 파라미터 패턴:
    T-SQL:   @presultid int out  + SCOPE_IDENTITY()
    Python:  ProcedureResult.result_id 에 저장

■ SCOPE_IDENTITY() 처리:
    INSERT 직후 같은 연결에서 SELECT SCOPE_IDENTITY() 실행
    → 동시 접속 환경에서도 올바른 ID 반환

■ usp_add_author_storebook
    입력: firstname (필수), surname (필수), surname2 (선택, 두 번째 성)
    반환: 생성된 Authors.Id

■ usp_add_book_storebook
    입력: isbn (필수, PK), title (필수),
          pages / year / category (모두 선택)
    반환: 삽입된 Isbn (문자열)
    ※ Books 테이블의 PK는 자동생성 ID가 아니라 isbn (varchar)입니다.
       따라서 SCOPE_IDENTITY() 대신 isbn을 그대로 반환합니다.

■ usp_add_authorbook_storebook
    입력: author_id (int), isbn (varchar)
    반환: 성공 여부 (bit → bool)
    ※ Created 컬럼에 GETDATE() → Python datetime.now() 사용

■ usp_add_category_storebook
    입력: category (varchar(46))
    반환: 생성된 Categories.Id
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from db.connection import get_db_cursor
from db.result import ProcedureResult


# ─────────────────────────────────────────────────────────────────────────────
# 1. usp_add_author_storebook
# ─────────────────────────────────────────────────────────────────────────────

def add_author(
    firstname: str,
    surname: str,
    surname2: Optional[str] = None,
) -> ProcedureResult:
    """
    새 저자를 Authors 테이블에 추가합니다.

    T-SQL 원본:
        EXEC usp_add_author_storebook
            @pfirstname = 'John',
            @psurname   = 'Doe',
            @psurname2  = NULL,
            @presultid  = @id OUTPUT,
            @pmsgerror  = @err OUTPUT

    Args:
        firstname: 저자 이름 (필수, 최대 128자)
        surname:   저자 성 (필수, 최대 128자)
        surname2:  두 번째 성 (선택, 스페인어권 이름 등에 사용)

    Returns:
        ProcedureResult:
            .success   = True / False
            .result_id = 생성된 Authors.Id (int)
            .error     = 오류 메시지 (실패 시)

    사용 예:
        result = add_author("John", "Doe")
        if result.success:
            print("새 저자 ID:", result.result_id)
    """
    # 입력값 검증
    if not firstname or not firstname.strip():
        return ProcedureResult(error="firstname(이름)은 필수입니다.")
    if not surname or not surname.strip():
        return ProcedureResult(error="surname(성)은 필수입니다.")
    if len(firstname) > 128:
        return ProcedureResult(error="firstname이 128자를 초과합니다.")
    if len(surname) > 128:
        return ProcedureResult(error="surname이 128자를 초과합니다.")
    if surname2 and len(surname2) > 128:
        return ProcedureResult(error="surname2가 128자를 초과합니다.")

    insert_sql = """
        INSERT INTO Authors (Firstname, Surname, Surname2)
        VALUES (?, ?, ?)
    """
    identity_sql = "SELECT SCOPE_IDENTITY()"

    try:
        with get_db_cursor() as cursor:
            cursor.execute(insert_sql, (firstname.strip(), surname.strip(), surname2))
            if cursor.rowcount == 0:
                return ProcedureResult(error="저자 추가 실패: 삽입된 행이 없습니다.")

            cursor.execute(identity_sql)
            row = cursor.fetchone()
            new_id = int(row[0]) if row and row[0] is not None else None

            return ProcedureResult(success=True, result_id=new_id)

    except Exception as exc:
        return ProcedureResult(error=f"add_author 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. usp_add_book_storebook
# ─────────────────────────────────────────────────────────────────────────────

def add_book(
    isbn: str,
    title: str,
    pages: Optional[int] = None,
    year: Optional[int] = None,
    category_id: Optional[int] = None,
) -> ProcedureResult:
    """
    새 책을 Books 테이블에 추가합니다.

    T-SQL 원본:
        EXEC usp_add_book_storebook
            @pisbn     = '9780134494166',
            @ptitle    = 'Clean Code',
            @ppages    = 431,
            @pyear     = 2008,
            @pcategory = 3,
            @presult   = @isbn OUTPUT,
            @pmsgerror = @err OUTPUT

    Args:
        isbn:        ISBN-13 문자열 (PK, 필수)
        title:       책 제목 (필수, 최대 256자)
        pages:       페이지 수 (선택)
        year:        출판 연도 (선택)
        category_id: Categories.Id 외래키 (선택)

    Returns:
        ProcedureResult:
            .success   = True / False
            .result_id = 삽입된 ISBN 문자열
            .error     = 오류 메시지 (실패 시)

    ※ Books의 PK는 ISBN(varchar)이므로 SCOPE_IDENTITY() 대신
       삽입한 isbn 값 자체를 반환합니다.

    사용 예:
        result = add_book("9780134494166", "Clean Code", pages=431, year=2008)
        if result.success:
            print("추가된 ISBN:", result.result_id)
    """
    if not isbn or not isbn.strip():
        return ProcedureResult(error="isbn은 필수입니다.")
    if len(isbn) > 13:
        return ProcedureResult(error="isbn은 최대 13자입니다.")
    if not title or not title.strip():
        return ProcedureResult(error="title(제목)은 필수입니다.")
    if len(title) > 256:
        return ProcedureResult(error="title이 256자를 초과합니다.")

    insert_sql = """
        INSERT INTO Books (Isbn, Title, Pages, [Year], CategoryId)
        VALUES (?, ?, ?, ?, ?)
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(insert_sql, (isbn.strip(), title.strip(), pages, year, category_id))
            if cursor.rowcount == 0:
                return ProcedureResult(error="책 추가 실패: 삽입된 행이 없습니다.")

            return ProcedureResult(success=True, result_id=isbn.strip())

    except Exception as exc:
        return ProcedureResult(error=f"add_book 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. usp_add_authorbook_storebook
# ─────────────────────────────────────────────────────────────────────────────

def add_author_book(
    author_id: int,
    isbn: str,
) -> ProcedureResult:
    """
    저자-책 연결 관계를 AuthorBook 테이블에 추가합니다.
    (다대다 관계 테이블)

    T-SQL 원본:
        EXEC usp_add_authorbook_storebook
            @pauthorid = 1,
            @pisbn     = '9780134494166',
            @presult   = @result OUTPUT,
            @pmsgerror = @err OUTPUT

    Args:
        author_id: Authors.Id (필수)
        isbn:      Books.Isbn (필수)

    Returns:
        ProcedureResult:
            .success      = True / False
            .rows_affected = 1 (성공 시)
            .error        = 오류 메시지 (실패 시)

    ※ Created 컬럼: T-SQL의 GETDATE() → Python의 datetime.now()

    사용 예:
        result = add_author_book(author_id=1, isbn='9780134494166')
        if result.success:
            print("저자-책 연결 완료")
    """
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")
    if not isbn or not isbn.strip():
        return ProcedureResult(error="isbn은 필수입니다.")

    insert_sql = """
        INSERT INTO AuthorBook (IdAuthor, Isbn, Created)
        VALUES (?, ?, ?)
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(insert_sql, (author_id, isbn.strip(), datetime.now()))
            if cursor.rowcount == 0:
                return ProcedureResult(error="저자-책 연결 실패: 삽입된 행이 없습니다.")

            return ProcedureResult(success=True, rows_affected=cursor.rowcount)

    except Exception as exc:
        return ProcedureResult(error=f"add_author_book 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. usp_add_category_storebook
# ─────────────────────────────────────────────────────────────────────────────

def add_category(category: str) -> ProcedureResult:
    """
    새 카테고리를 Categories 테이블에 추가합니다.

    T-SQL 원본:
        EXEC usp_add_category_storebook
            @pcategory  = 'Fiction',
            @presultid  = @id OUTPUT,
            @pmsgerror  = @err OUTPUT

    Args:
        category: 카테고리 이름 (필수, 최대 46자)

    Returns:
        ProcedureResult:
            .success   = True / False
            .result_id = 생성된 Categories.Id (int)
            .error     = 오류 메시지 (실패 시)

    사용 예:
        result = add_category("Science Fiction")
        if result.success:
            print("새 카테고리 ID:", result.result_id)
    """
    if not category or not category.strip():
        return ProcedureResult(error="category(카테고리명)는 필수입니다.")
    if len(category) > 46:
        return ProcedureResult(error="category가 46자를 초과합니다.")

    insert_sql = "INSERT INTO Categories (Category) VALUES (?)"
    identity_sql = "SELECT SCOPE_IDENTITY()"

    try:
        with get_db_cursor() as cursor:
            cursor.execute(insert_sql, (category.strip(),))
            if cursor.rowcount == 0:
                return ProcedureResult(error="카테고리 추가 실패: 삽입된 행이 없습니다.")

            cursor.execute(identity_sql)
            row = cursor.fetchone()
            new_id = int(row[0]) if row and row[0] is not None else None

            return ProcedureResult(success=True, result_id=new_id)

    except Exception as exc:
        return ProcedureResult(error=f"add_category 오류: {exc}")
