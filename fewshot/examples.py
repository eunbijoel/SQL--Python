"""
fewshot/examples.py
====================
Few-shot 학습에 사용할 (SQL 입력, Python 정답) 예시 쌍 모음.

직접 번역한 BookStore 계열 11개 중, 6개를 EXAMPLES로 프롬프트에 넣습니다.
- 나머지 7개(TEST_TARGETS)는 예시에 넣지 않고 변환·채점만 수행
- 6개: SELECT/LIKE, INSERT+SCOPE_IDENTITY, UPDATE+ROWCOUNT, 단순 DELETE,
       2단계 트랜잭션 DELETE(다른 테이블), varchar PK INSERT(다른 테이블)
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
    # ── TEST_TARGETS의 usp_delete_book 과 테이블이 겹치지 않는 2단계 삭제 패턴 ──
    {
        "name": "usp_delete_order_storebook",
        "category": "DELETE",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_delete_order_storebook]
    @porderid int,
    @presult bit out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRAN
        DELETE FROM OrderItems WHERE OrderId = @porderid
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
        BEGIN
            DELETE FROM Orders WHERE OrderId = @porderid
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
        "python": """\
def delete_order(order_id):
    \"\"\"주문: OrderItems 먼저 삭제 후 Orders 삭제 (한 트랜잭션).\"\"\"
    if not isinstance(order_id, int) or order_id <= 0:
        return ProcedureResult(error="order_id는 양의 정수여야 합니다.")
    try:
        with get_db_cursor(autocommit=False) as cursor:
            cursor.execute("DELETE FROM OrderItems WHERE OrderId = ?", (order_id,))
            items_deleted = cursor.rowcount
            if items_deleted == 0:
                return ProcedureResult(error="삭제할 주문 항목이 없습니다.")
            cursor.execute("DELETE FROM Orders WHERE OrderId = ?", (order_id,))
            order_rows = cursor.rowcount
            if order_rows != 1:
                return ProcedureResult(
                    error=(
                        f"주문 본체 삭제 실패: 예상 1행, 실제 {order_rows}행"
                    )
                )
            return ProcedureResult(
                success=True,
                rows_affected=items_deleted + order_rows,
            )
    except Exception as exc:
        return ProcedureResult(error=f"delete_order 오류: {exc}")
""",
    },
    # ── TEST_TARGETS의 usp_add_book 과 겹치지 않는 varchar PK INSERT 패턴 ──
    {
        "name": "usp_add_product_storebook",
        "category": "INSERT",
        "sql": """\
CREATE PROCEDURE [dbo].[usp_add_product_storebook]
    @pcode varchar(20),
    @pname varchar(256),
    @pprice decimal(10,2) = null,
    @presult varchar(20) out,
    @pmsgerror varchar(256) out
AS
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO Products(Code, Name, Price)
        VALUES(@pcode, @pname, @pprice);
        IF @@ROWCOUNT > 0 AND @@ERROR = 0
            SELECT @presult = Code FROM Products WHERE Code = @pcode;
    END TRY
    BEGIN CATCH
        SET @pmsgerror = convert(varchar(8),ERROR_LINE()) + ': ' + ERROR_MESSAGE()
    END CATCH
""",
        "python": """\
def add_product(code: str, name: str, price=None):
    \"\"\"Products 삽입. PK가 varchar(Code)이면 SCOPE_IDENTITY 대신 code 반환.\"\"\"
    if not code or not str(code).strip():
        return ProcedureResult(error="code는 필수입니다.")
    if not name or not str(name).strip():
        return ProcedureResult(error="name은 필수입니다.")
    code = str(code).strip()
    name = str(name).strip()
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO Products (Code, Name, Price) VALUES (?, ?, ?)",
                (code, name, price),
            )
            if cursor.rowcount == 0:
                return ProcedureResult(error="상품 추가 실패: 삽입된 행이 없습니다.")
            return ProcedureResult(success=True, result_id=code)
    except Exception as exc:
        return ProcedureResult(error=f"add_product 오류: {exc}")
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
