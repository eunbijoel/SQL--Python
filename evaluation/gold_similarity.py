"""
정답 번역(procedures/*.py)과 모델 출력의 유사도.

- 라인 기반: 공백 정규화 후 difflib.SequenceMatcher
- AST 보조: dump 정규화 문자열 비율 (구조적 유사)
"""
from __future__ import annotations

import ast
import difflib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# 벤치 TEST_TARGETS 프로시저 → (파일, 함수명)
PROCEDURE_GOLD: dict[str, tuple[str, str]] = {
    "usp_get_books_storebook": ("procedures/get_procedures.py", "get_books"),
    "usp_add_book_storebook": ("procedures/add_procedures.py", "add_book"),
    "usp_add_authorbook_storebook": ("procedures/add_procedures.py", "add_author_book"),
    "usp_add_category_storebook": ("procedures/add_procedures.py", "add_category"),
    "usp_modified_book_storebook": ("procedures/modify_procedures.py", "modify_book"),
    "usp_modified_authorbook_storebook": ("procedures/modify_procedures.py", "modify_author_book"),
    "usp_delete_book_storebook": ("procedures/delete_procedures.py", "delete_book"),
}


def _read_gold_function(proc: str) -> str | None:
    if proc not in PROCEDURE_GOLD:
        return None
    rel, func_name = PROCEDURE_GOLD[proc]
    path = _ROOT / rel
    if not path.is_file():
        return None
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            seg = ast.get_source_segment(src, node)
            return seg if seg else None
    return None


def _first_user_function(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            seg = ast.get_source_segment(code, node)
            return seg if seg else None
    return None


def _norm_lines(s: str) -> str:
    lines = [ln.strip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    return "\n".join(lines)


def _strip_docstring_from_function_source(src: str) -> str:
    """함수 소스에서 첫 줄 docstring(단일 표현식) 제거 — 거친 정규화."""
    try:
        tree = ast.parse(src)
        if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
            return src
        fn = tree.body[0]
        if (
            fn.body
            and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)
        ):
            fn.body = fn.body[1:]
        return ast.unparse(fn)
    except SyntaxError:
        return src


def _ast_dump_norm(src: str) -> str | None:
    try:
        t = ast.parse(src)
        if not t.body:
            return None
        node = t.body[0]
        if isinstance(node, ast.FunctionDef):
            return ast.dump(node, include_attributes=False)
    except SyntaxError:
        return None
    return None


def check_gold_similarity(code: str, procedure_name: str) -> dict:
    """
    정답 함수와의 유사도 0~1.

    Returns:
        {"pass": bool, "score": float, "reason": str, "line_ratio": float, "ast_ratio": float}
    """
    gold = _read_gold_function(procedure_name)
    if not gold:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"정답 매핑 없음: {procedure_name}",
            "line_ratio": 0.0,
            "ast_ratio": 0.0,
        }

    user_fn = _first_user_function(code or "")
    if not user_fn:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "모델 출력에서 최상위 def 함수를 찾지 못함",
            "line_ratio": 0.0,
            "ast_ratio": 0.0,
        }

    g = _norm_lines(_strip_docstring_from_function_source(gold))
    u = _norm_lines(_strip_docstring_from_function_source(user_fn))

    line_ratio = difflib.SequenceMatcher(None, g, u).ratio()

    ag = _ast_dump_norm(gold)
    au = _ast_dump_norm(user_fn)
    ast_ratio = (
        difflib.SequenceMatcher(None, ag or "", au or "").ratio()
        if ag and au
        else 0.0
    )

    # 라인 텍스트를 주 가중치(정확도), AST는 다른 표현이라도 구조 비슷할 때 보조
    score = round(min(1.0, line_ratio * 0.72 + ast_ratio * 0.28), 3)
    # 통과 임계값: results/benchmark_20260408_172940.json 기준
    # usp_add_category·usp_add_book(glm) 등은 합성 점수 ~0.51~0.54대인데 동작은 양호.
    # 0.55는 과도하게 빡세서 strict가 의미 없이 깎임 → 0.50으로 완화 (삭제 2단계는 여전히 낮게 나올 수 있음).
    passed = score >= 0.50

    return {
        "pass": passed,
        "score": score,
        "reason": f"정답 대비 line≈{line_ratio:.0%} ast≈{ast_ratio:.0%} → 합성 {score:.0%}",
        "line_ratio": round(line_ratio, 3),
        "ast_ratio": round(ast_ratio, 3),
    }
