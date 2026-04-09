"""
fewshot/prompt_builder.py
==========================
Few-shot 프롬프트를 만드는 모듈.

역할:
    예시 SQL + 정답 Python 쌍을 조합해서
    모델에게 보낼 프롬프트 문자열을 완성합니다.

사용법:
    from fewshot.prompt_builder import build_prompt
    prompt = build_prompt(target_sql="CREATE PROCEDURE ...")
    print(prompt)  # 눈으로 확인 가능
"""

from fewshot.examples import EXAMPLES


SYSTEM_INSTRUCTION = """\
You are an expert SQL-to-Python converter.
Convert T-SQL stored procedures into clean, production-ready Python functions.

Rules you must follow:
1. Always return a ProcedureResult object (with fields: success, result_id, rows, rows_affected, error).
2. Use get_db_cursor() as the database context manager.
3. Use parameterized queries with ? placeholders — never string formatting.
4. Add input validation before the SQL call.
5. Wrap the SQL call in try/except and set error on failure.
6. Map T-SQL OUTPUT parameters to ProcedureResult fields:
   - @presult bit OUT     → success (bool)
   - @presultid int OUT   → result_id (int)
   - @pmsgerror OUT       → error (str)
   - SELECT result set    → rows (list of dict)
7. Output ONLY the Python function. No explanation, no markdown fences.
"""


def build_prompt(target_sql: str, n_examples: int = 6) -> str:
    """
    Few-shot 프롬프트를 만들어 반환합니다.

    구조:
        [시스템 지침]
        [예시 1: SQL → Python]
        [예시 2: SQL → Python]
        ...
        [실제 변환할 SQL]
        → 모델이 Python 코드를 출력

    Args:
        target_sql: 변환할 SQL 프로시저 코드
        n_examples: 사용할 예시 개수 (기본 6개, 최대 len(EXAMPLES))

    Returns:
        완성된 프롬프트 문자열
    """
    examples = EXAMPLES[:n_examples]
    parts = [SYSTEM_INSTRUCTION.strip(), ""]

    for i, ex in enumerate(examples, 1):
        parts.append(f"### Example {i} — {ex['category']}: {ex['name']}")
        parts.append("")
        parts.append("SQL Input:")
        parts.append("```sql")
        parts.append(ex["sql"].strip())
        parts.append("```")
        parts.append("")
        parts.append("Python Output:")
        parts.append("```python")
        parts.append(ex["python"].strip())
        parts.append("```")
        parts.append("")

    parts.append("### Now convert the following SQL:")
    parts.append("")
    parts.append("SQL Input:")
    parts.append("```sql")
    parts.append(target_sql.strip())
    parts.append("```")
    parts.append("")
    parts.append("Python Output:")

    return "\n".join(parts)


def print_prompt_preview(target_sql: str, n_examples: int = 6) -> None:
    """
    프롬프트를 출력해서 눈으로 확인할 수 있게 합니다.
    실행 전 '내용이 제대로 들어갔나?' 확인용.
    """
    prompt = build_prompt(target_sql, n_examples)
    lines = prompt.split("\n")
    total_chars = len(prompt)

    print("=" * 60)
    print(f"프롬프트 미리보기 (총 {len(lines)}줄 / {total_chars}자)")
    print("=" * 60)

    # 처음 40줄만 표시 (너무 길면 읽기 힘드니까)
    for line in lines[:40]:
        print(line)
    if len(lines) > 40:
        print(f"\n... (이하 {len(lines)-40}줄 생략) ...")
        print(lines[-5])  # 마지막 줄 확인

    print("=" * 60)
    print(f"예시 개수: {n_examples}개 | 변환 대상 SQL 포함 여부: OK")
    print("=" * 60)
