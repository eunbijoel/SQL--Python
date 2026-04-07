"""
fewshot/examples.py
====================
Few-shot 학습에 사용할 (SQL 입력, Python 정답) 예시 쌍 모음.

우리가 직접 번역한 11개 함수 중 4개를 예시로 사용합니다.
- 너무 많으면 프롬프트가 길어져서 모델이 지침에 집중 못함
- 다양한 패턴(SELECT/INSERT/UPDATE/DELETE)을 골고루 포함
- 나머지 7개는 실제 변환 테스트 대상으로 사용
"""

# ──────────────────────────────────────────────────────────────────────────────
# 예시 쌍 (SQL → Python)
# ──────────────────────────────────────────────────────────────────────────────

EXAMPLES = [
    {
        "name": "usp_get_authors_storebook",
        "category": "SELECT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_get_authors_storebook]
@pfirstname varchar(128) = '%'
,@pSurname varchar(128) = '%'
AS
    SET NOCOUNT ON;
    SELECT * FROM Authors
    WHERE Firstname LIKE @pfirstname AND Surname LIKE @pSurname
""",
        "python": """\
def get_authors(firstname=None, surname=None):
    \"\"\"저자 목록 조회. 이름/성으로 LIKE 검색 가능.\"\"\"
    fn_pattern = firstname if firstname is not None else "%"
    sn_pattern = surname if surname is not None else "%"
    sql = \"\"\"
        SELECT * FROM Authors
        WHERE Firstname LIKE ? AND Surname LIKE ?
    \"\"\"
    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (fn_pattern, sn_pattern))
            rows = rows_as_dicts(cursor)
            return ProcedureResult(success=True, rows=rows, rows_affected=len(rows))
    except Exception as exc:
        return ProcedureResult(error=f"get_authors 오류: {exc}")
""",
    },
    {
        "name": "usp_add_author_storebook",
        "category": "INSERT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_add_author_storebook]
    @pfirstname varchar(128),
    @psurname varchar(128),
    @psurname2 varchar(128) = null,
    @presultid int out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO Authors(Firstname, Surname, Surname2)
        VALUES(@pfirstname, @psurname, @psurname2);
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            SELECT @presultid = Id FROM Authors WHERE Id = SCOPE_IDENTITY();
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
        "python": """\
def add_author(firstname, surname, surname2=None):
    \"\"\"새 저자를 Authors 테이블에 추가. 생성된 Id 반환.\"\"\"
    if not firstname or not firstname.strip():
        return ProcedureResult(error="firstname은 필수입니다.")
    if not surname or not surname.strip():
        return ProcedureResult(error="surname은 필수입니다.")
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO Authors (Firstname, Surname, Surname2) VALUES (?, ?, ?)",
                (firstname.strip(), surname.strip(), surname2)
            )
            if cursor.rowcount == 0:
                return ProcedureResult(error="삽입 실패")
            cursor.execute("SELECT SCOPE_IDENTITY()")
            row = cursor.fetchone()
            new_id = int(row[0]) if row and row[0] is not None else None
            return ProcedureResult(success=True, result_id=new_id)
    except Exception as exc:
        return ProcedureResult(error=f"add_author 오류: {exc}")
""",
    },
    {
        "name": "usp_modified_author_storebook",
        "category": "UPDATE",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_modified_author_storebook]
    @pfirstname varchar(128),
    @psurname varchar(128),
    @psurname2 varchar(128) = null,
    @pid int,
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
    UPDATE Authors
    SET Firstname = @pfirstname, Surname = @psurname, Surname2 = @psurname2
    WHERE Id = @pid
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            set @presult = 1
    END TRY
    BEGIN CATCH
        SET @pmsgerror = CONVERT(varchar(8),ERROR_NUMBER()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
        "python": """\
def modify_author(author_id, firstname, surname, surname2=None):
    \"\"\"저자 정보 수정. author_id 기준으로 업데이트.\"\"\"
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")
    if not firstname or not firstname.strip():
        return ProcedureResult(error="firstname은 필수입니다.")
    sql = \"\"\"
        UPDATE Authors
        SET Firstname = ?, Surname = ?, Surname2 = ?
        WHERE Id = ?
    \"\"\"
    try:
        with get_db_cursor() as cursor:
            cursor.execute(sql, (firstname.strip(), surname.strip(), surname2, author_id))
            if cursor.rowcount == 0:
                return ProcedureResult(error=f"저자를 찾을 수 없습니다. Id={author_id}")
            return ProcedureResult(success=True, rows_affected=cursor.rowcount)
    except Exception as exc:
        return ProcedureResult(error=f"modify_author 오류: {exc}")
""",
    },
    {
        "name": "usp_delete_author_storebook",
        "category": "DELETE",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_delete_author_storebook]
    @pid int,
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
    DELETE FROM Authors WHERE Id = @pid
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            set @presult = 1
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
        "python": """\
def delete_author(author_id):
    \"\"\"저자 삭제. FK 제약 있으면 오류 반환.\"\"\"
    if not isinstance(author_id, int) or author_id <= 0:
        return ProcedureResult(error="author_id는 양의 정수여야 합니다.")
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM Authors WHERE Id = ?", (author_id,))
            if cursor.rowcount == 0:
                return ProcedureResult(error=f"저자를 찾을 수 없습니다. Id={author_id}")
            return ProcedureResult(success=True, rows_affected=cursor.rowcount)
    except Exception as exc:
        return ProcedureResult(error=f"delete_author 오류: {exc}")
""",
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# 실제 변환 테스트 대상 SQL (예시로 사용하지 않는 나머지 7개)
# ──────────────────────────────────────────────────────────────────────────────

TEST_TARGETS = [
    {
        "name": "usp_get_books_storebook",
        "category": "SELECT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_get_books_storebook]
@pisbn varchar(13) = '%'
,@ptitle varchar(256) = '%'
AS
    SET NOCOUNT ON;
    SELECT b.Isbn, b.Title, b.Pages, b.[Year], cat.Category,
           a.Surname + ', ' + a.Firstname 'Author'
    FROM Books b
    JOIN Categories cat ON b.CategoryId = cat.Id
    JOIN AuthorBook ab ON b.Isbn = ab.Isbn
    JOIN Authors a ON a.Id = ab.IdAuthor
    WHERE b.Isbn LIKE @pisbn AND b.Title LIKE @ptitle
""",
    },
    {
        "name": "usp_add_book_storebook",
        "category": "INSERT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_add_book_storebook]
    @pisbn varchar(13),
    @ptitle varchar(256),
    @ppages int = null,
    @pyear int = null,
    @pcategory int = null,
    @presult varchar(13) out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO Books(Isbn,Title,Pages,[Year],CategoryId)
        VALUES(@pisbn,@ptitle,@ppages,@pyear,@pcategory);
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            SELECT @presult = Isbn FROM Books WHERE Isbn = @pisbn;
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
    {
        "name": "usp_add_authorbook_storebook",
        "category": "INSERT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_add_authorbook_storebook]
    @pauthorid int,
    @pisbn varchar(13),
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO AuthorBook(IdAuthor,Isbn,Created)
        VALUES(@pauthorid,@pisbn,GETDATE());
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            SET @presult = 1
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
    {
        "name": "usp_add_category_storebook",
        "category": "INSERT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_add_category_storebook]
    @pcategory varchar(46),
    @presultid int out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    SET @presultid = NULL
    BEGIN TRY
        INSERT INTO Categories(Category) VALUES(@pcategory);
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            SELECT @presultid = Id FROM Categories WHERE Id = SCOPE_IDENTITY();
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
    {
        "name": "usp_modified_book_storebook",
        "category": "UPDATE",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_modified_book_storebook]
    @pisbn varchar(13),
    @ptitle varchar(256),
    @ppages int = null,
    @pyear int = null,
    @pcategory int = null,
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        UPDATE Books
        SET Title = @ptitle, Pages = @ppages, [Year] = @pyear, CategoryId = @pcategory
        WHERE Isbn = @pisbn
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            set @presult = 1
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
    {
        "name": "usp_modified_authorbook_storebook",
        "category": "UPDATE",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_modified_authorbook_storebook]
    @pauthorid int,
    @pisbn varchar(13),
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
    UPDATE AuthorBook
    SET IdAuthor = @pauthorid, Isbn = @pisbn
    WHERE IdAuthor = @pauthorid
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            set @presult = 1
    END TRY
    BEGIN CATCH
        SET @pmsgerror = CONVERT(varchar(8),ERROR_NUMBER()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
    {
        "name": "usp_delete_book_storebook",
        "category": "DELETE+TRANSACTION",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_delete_book_storebook]
    @pisbn varchar(13),
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRAN
        DELETE FROM AuthorBook WHERE Isbn = @pisbn
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
        BEGIN
            DELETE FROM Books WHERE Isbn = @pisbn
            IF @@ERROR = 0 AND @@ROWCOUNT = 1
                set @presult = 1
            ELSE
                SET @presult = 0
        END
        ELSE
            SET @pmsgerror = 'Nothing to delete'
        IF @presult = 1
            COMMIT TRAN
        ELSE
            ROLLBACK TRAN
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
    },
]
