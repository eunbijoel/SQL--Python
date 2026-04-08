"""
Comparator(tsql2py) 스타일을 BookStore 관례에 맞게 단순 이식.

- 이 프로젝트는 pyodbc.connect 대신 get_db_cursor() 사용
- execution_score 를 0~1 로 스케일
"""
from __future__ import annotations

import ast
import re
from typing import Any


def _placeholder_balance(code: str) -> bool:
    """cursor.execute(...) 안 ? 개수와 인자 튜플/리스트 요소 수 거칠게 비교."""
    pattern = re.compile(
        r"cursor\.execute\s*\(\s*"
        r'(?P<query>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[\s\S]*?"|\'[\s\S]*?\')\s*'
        r"(?P<args>,[\s\S]*?)?\)",
        re.MULTILINE,
    )
    lower = code.lower()
    if "cursor.execute(" not in lower:
        return True
    for m in pattern.finditer(code):
        query = m.group("query")
        args = m.group("args") or ""
        ph = query.count("?")
        if ph == 0:
            continue
        arg_text = args.strip().lstrip(",").strip()
        if not arg_text:
            arg_count = 0
        else:
            arg_count = len([a for a in arg_text.split(",") if a.strip()])
        if ph != arg_count:
            return False
    return True


def check_style_rubric(code: str, procedure_name: str = "") -> dict[str, Any]:
    """
    세부 공학 체크 (Comparator 영감). 점수는 가중 합 → 0~1.

    Returns:
        {"pass": bool, "score": float, "reason": str, "details": dict}
    """
    if not code or not code.strip():
        return {"pass": False, "score": 0.0, "reason": "빈 코드", "details": {}}

    tree: ast.AST | None = None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        pass

    lower = code.lower()
    details: dict[str, bool] = {}

    details["syntax_valid"] = tree is not None
    details["parameterized"] = (
        ("cursor.execute(" in lower and "?" in code)
        or ("params=" in lower)
    )
    details["try_except"] = (
        any(isinstance(n, ast.Try) for n in ast.walk(tree))
        if tree
        else ("try:" in code and "except" in code)
    )
    details["get_db_cursor"] = "get_db_cursor" in code
    details["procedure_result"] = "ProcedureResult" in code
    dangerous = [
        "cursor.rownumber",
        "@@error",
        "select @@error",
        "lastrowid",
    ]
    details["no_dangerous"] = not any(p in lower for p in dangerous)
    details["placeholder_balance"] = _placeholder_balance(code)

    # 함수명: usp_add_book_storebook → add_book 등 정답 stem 힌트 (느슨하게)
    details["name_hint"] = True
    if procedure_name:
        stem = procedure_name.replace("usp_", "").replace("_storebook", "").strip("_")
        parts = stem.split("_")
        hint = parts[0] if parts else ""
        if hint and tree:
            names = [n.name.lower() for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            details["name_hint"] = any(hint in n for n in names) or len(names) == 0

    weights = {
        "syntax_valid": 0.18,
        "parameterized": 0.18,
        "try_except": 0.12,
        "get_db_cursor": 0.12,
        "procedure_result": 0.12,
        "no_dangerous": 0.10,
        "placeholder_balance": 0.10,
        "name_hint": 0.08,
    }

    score = sum(weights[k] for k, w in weights.items() if details.get(k))
    score = round(min(1.0, score), 3)
    passed = score >= 0.75

    miss = [k for k in weights if not details.get(k)]
    reason = f"스타일 {score:.0%} | 미충족: {', '.join(miss) if miss else '없음'}"

    return {"pass": passed, "score": score, "reason": reason, "details": details}
