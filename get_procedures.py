"""
procedures/get_procedures.py
=============================
조회(SELECT) 저장 프로시저 번역

번역 대상:
    1. usp_get_books_storebook    → get_books()
    2. usp_get_authors_storebook  → get_authors()

=============================================================
[원본 SQL 분석 메모]
=============================================================

■ usp_get_books_storebook
  - 입력: @pisbn VARCHAR(13) = '%'   (기본값 = 전체 와일드카드)
          @ptitle VARCHAR(256) = '%'
  - 동작: Books + Categories + AuthorBook + Authors 4개 테이블 JOIN
          LIKE 조건으로 ISBN 또는 제목 필터링 가능
  - 출력: Isbn, Title, Pages, Year, Category, Author(성+이름 합쳐서)

  ⚠️ 주의 사항:
     T-SQL의 LIKE '%' 패턴은 Python에서 SQL LIKE + 파라미터로 동일하게 구현합니다.
     단, 기본값을 None으로 받아서 None이면 전체 조회로 처리합니다.

■ usp_get_authors_storebook
  - 입력: @pfirstname VARCHAR(128) = '%'
          @pSurname   VARCHAR(128) = '%'
  - 동작: Authors 테이블에서 이름/성으로 필터
  - 출력: Authors 테이블 전체 컬럼 (SELECT *)

  ⚠️ 버그 발견 (원본 SQL):
     Firstname은 LIKE를 사용하지만 Surname은 = (완전일치)를 사용합니다.
     즉, Surname = '%' 이면 '%' 라는 성을 가진 사람만 나옵니다.
     → 실제 의도는 LIKE였을 가능성이 높습니다.
     → 이 번역에서는 둘 다 LIKE로 통일하되, 주석으로 원본 동작을 명시합니다.
"""

from __future__ import annotations
from typing import Optional
from db.connection import get_db_cursor
from db.result import ProcedureResult, rows_as_dicts


# ─────────────────────────────────────────────────────────────────────────────
# 1. usp_get_books_storebook
# ─────────────────────────────────────────────────────────────────────────────

def get_books(
    isbn: Optional[str] = None,
    title: Optional[str] = None,
) -> ProcedureResult:
    """
    책 목록을 조회합니다. (4개 테이블 JOIN)

    T-SQL 원본:
        EXEC usp_get_books_storebook @pisbn='%', @ptitle='%'

    Args:
        isbn:  ISBN 필터 (부분 일치 가능, None이면 전체)
               예) '978%' → 978로 시작하는 ISBN 전체
        title: 제목 필터 (부분 일치 가능, None이면 전체)
               예) '%Python%' → Python이 포함된 제목 전체

    Returns:
        ProcedureResult.rows: 책 목록 (dict 리스트)
            키: Isbn, Title, Pages, Year, Category, Author

    사용 예:
        # 전체 조회
        result = get_books()

        # ISBN으로 검색
        result = get_books(isbn='9780134494166')

        # 제목으로 부분 검색
        result = get_books(title='%Python%')

        for book in result.rows:
            print(book['Title'], book['Author'])
    """
    # None이면 T-SQL 기본값 '%' (전체 매칭) 와 동일하게 처리
    isbn_pattern = isbn if isbn is not None else "%"
    title_pattern = title if title is not None else "%"

    sql = """
        SELECT
            b.Isbn,
            b.Title,
            b.Pages,
            b.[Year],
            cat.Category,
            a.Surname + ', ' + a.Firstname AS Author
        FROM
            Books b
            JOIN Categories cat ON b.CategoryId = cat.Id
            JOIN AuthorBook ab  ON b.Isbn = ab.Isbn
            JOIN Authors a      ON a.Id = ab.IdAuthor
        WHERE
            b.Isbn  LIKE ?
            AND b.Title LIKE ?
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (isbn_pattern, title_pattern))
            rows = rows_as_dicts(cursor)
            return ProcedureResult(success=True, rows=rows, rows_affected=len(rows))
    except Exception as exc:
        return ProcedureResult(error=f"get_books 오류: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. usp_get_authors_storebook
# ─────────────────────────────────────────────────────────────────────────────

def get_authors(
    firstname: Optional[str] = None,
    surname: Optional[str] = None,
    use_exact_surname: bool = False,
) -> ProcedureResult:
    """
    저자 목록을 조회합니다.

    T-SQL 원본:
        EXEC usp_get_authors_storebook @pfirstname='%', @pSurname='%'

    ⚠️ 원본 버그 재현 여부 선택:
        T-SQL 원본에서 Firstname은 LIKE, Surname은 = (완전일치)를 사용합니다.
        use_exact_surname=True 로 설정하면 원본 동작을 그대로 재현합니다.
        기본값(False)에서는 둘 다 LIKE로 동작합니다.

    Args:
        firstname:         이름 필터 (LIKE 패턴, None이면 전체)
        surname:           성 필터 (None이면 전체)
        use_exact_surname: True면 surname을 완전일치(=)로 검색
                           False면 LIKE 패턴으로 검색 (권장)

    Returns:
        ProcedureResult.rows: 저자 목록 (dict 리스트)
            키: Id, Firstname, Surname, Surname2 (있는 경우)

    사용 예:
        # 전체 조회
        result = get_authors()

        # 이름으로 검색
        result = get_authors(firstname='John%')

        # 성으로 검색
        result = get_authors(surname='Smith')
    """
    fn_pattern = firstname if firstname is not None else "%"
    sn_pattern = surname if surname is not None else "%"

    if use_exact_surname:
        # 원본 T-SQL 동작 그대로 (Surname = 완전일치)
        sql = """
            SELECT * FROM Authors
            WHERE Firstname LIKE ?
              AND Surname = ?
        """
    else:
        # 권장: 둘 다 LIKE
        sql = """
            SELECT * FROM Authors
            WHERE Firstname LIKE ?
              AND Surname LIKE ?
        """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (fn_pattern, sn_pattern))
            rows = rows_as_dicts(cursor)
            return ProcedureResult(success=True, rows=rows, rows_affected=len(rows))
    except Exception as exc:
        return ProcedureResult(error=f"get_authors 오류: {exc}")
