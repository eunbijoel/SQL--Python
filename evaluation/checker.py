"""
evaluation/checker.py
======================
모델이 출력한 Python 코드를 자동으로 평가합니다.

검사 5가지 (종합 total_score 는 가중 평균):
    1. 문법   — ast.parse + def 존재
    2. 패턴   — 문자열 기반 필수 토큰 (few-shot 정렬용, 거친 층)
    3. 논리   — Mock DB 실행 후 success/result_id
    4. 정답 유사도 — procedures/*.py 해당 함수와 라인·AST 유사도 (정확도 핵심)
    5. 스타일 루브릭 — Comparator 스타일(placeholder 균형, 위험 패턴 등)을 BookStore 관례에 맞게

가중치(합 1.0): 문법 0.10, 패턴 0.10, 논리 0.22, 정답 0.38, 스타일 0.20

설계 원칙:
    - 실제 DB 연결 없이 동작
    - 각 검사는 독립적 (하나 실패해도 나머지 진행)
    - 결과는 점수(0~1) + 이유 문자열로 반환
"""

import ast
import textwrap
from typing import Optional

from .gold_similarity import check_gold_similarity
from .style_rubric import check_style_rubric


# ──────────────────────────────────────────────────────────────────────────────
# 검사 1: 문법 검사
# ──────────────────────────────────────────────────────────────────────────────

def check_syntax(code: str) -> dict:
    """
    Python 문법 오류가 없는지 확인합니다.

    Returns:
        {"pass": bool, "score": float, "reason": str}
    """
    if not code or not code.strip():
        return {"pass": False, "score": 0.0, "reason": "빈 코드 출력"}

    try:
        ast.parse(code)
        # def 로 시작하는 함수가 최소 1개 있는지 추가 확인
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return {"pass": False, "score": 0.3, "reason": "함수 정의(def)가 없음"}
        return {"pass": True, "score": 1.0, "reason": f"함수 {len(funcs)}개 정상 파싱"}
    except SyntaxError as e:
        return {"pass": False, "score": 0.0, "reason": f"SyntaxError: {e.msg} (line {e.lineno})"}


# ──────────────────────────────────────────────────────────────────────────────
# 검사 2: 패턴 검사
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_PATTERNS = {
    "ProcedureResult":  "ProcedureResult 반환 타입 사용",
    "try":              "try/except 오류 처리",
    "get_db_cursor":    "get_db_cursor() DB 컨텍스트 매니저 사용",
}

BONUS_PATTERNS = {
    "error=":           "오류 메시지 설정",
    "success=True":     "success 필드 설정",
    "strip()":          "문자열 공백 제거",
    "isinstance":       "입력값 타입 검증",
}


def check_patterns(code: str) -> dict:
    """
    Few-shot 예시에서 학습했어야 할 패턴이 있는지 확인합니다.

    Returns:
        {"pass": bool, "score": float, "reason": str, "details": dict}
    """
    if not code:
        return {"pass": False, "score": 0.0, "reason": "빈 코드", "details": {}}

    details = {}
    required_hits = 0

    for pattern, desc in REQUIRED_PATTERNS.items():
        found = pattern in code
        details[desc] = found
        if found:
            required_hits += 1

    bonus_hits = sum(1 for p in BONUS_PATTERNS if p in code)
    total_bonus = len(BONUS_PATTERNS)

    # 필수 패턴 3개 기준 점수 + 보너스
    base_score  = required_hits / len(REQUIRED_PATTERNS)
    bonus_score = (bonus_hits / total_bonus) * 0.3
    final_score = min(1.0, round(base_score * 0.7 + bonus_score, 2))

    passed = required_hits == len(REQUIRED_PATTERNS)
    missing = [desc for p, desc in REQUIRED_PATTERNS.items() if p not in code]
    reason = (
        f"필수 패턴 {required_hits}/{len(REQUIRED_PATTERNS)} 충족"
        + (f" | 미충족: {', '.join(missing)}" if missing else "")
        + f" | 보너스 {bonus_hits}/{total_bonus}"
    )

    return {"pass": passed, "score": final_score, "reason": reason, "details": details}


# ──────────────────────────────────────────────────────────────────────────────
# 검사 3: 논리 검사 (Mock 실행)
# ──────────────────────────────────────────────────────────────────────────────

_MOCK_HARNESS = """\
# ── Mock 환경 주입 ──────────────────────────────────────────────
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

class ProcedureResult:
    def __init__(self, success=False, result_id=None, rows=None,
                 rows_affected=0, error=None):
        self.success = success
        self.result_id = result_id
        self.rows = rows or []
        self.rows_affected = rows_affected
        self.error = error

def rows_as_dicts(cursor):
    if cursor.description is None:
        return []
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]

_mock_cursor = MagicMock()
_mock_cursor.rowcount = {rowcount}
_mock_cursor.description = {description}
_mock_cursor.fetchone.return_value = {fetchone}
_mock_cursor.fetchall.return_value = {fetchall}

@contextmanager
def get_db_cursor(autocommit=False):
    yield _mock_cursor

# ── 모델이 출력한 코드 ────────────────────────────────────────
{user_code}

# ── 테스트 호출 ───────────────────────────────────────────────
import inspect, datetime
_fn = [v for k,v in locals().items()
       if callable(v) and not k.startswith('_')
       and k not in ('MagicMock','patch','contextmanager',
                     'ProcedureResult','rows_as_dicts','get_db_cursor')]
if _fn:
    _func = _fn[0]
    _sig  = inspect.signature(_func)
    _args = {{}}
    for pname, param in _sig.parameters.items():
        if param.default is inspect.Parameter.empty:
            if 'id' in pname.lower():
                _args[pname] = 1
            elif 'isbn' in pname.lower():
                _args[pname] = '9780134494166'
            elif 'date' in pname.lower() or 'created' in pname.lower():
                _args[pname] = datetime.datetime.now()
            else:
                _args[pname] = 'TestValue'
    try:
        _result = _func(**_args)
        print('RESULT_SUCCESS:', getattr(_result, 'success', None))
        print('RESULT_ID:', getattr(_result, 'result_id', None))
        print('RESULT_ERROR:', getattr(_result, 'error', None))
        print('RESULT_ROWS:', len(getattr(_result, 'rows', [])))
    except Exception as e:
        print('EXEC_ERROR:', e)
else:
    print('NO_FUNCTION_FOUND')
"""


def check_logic(code: str, expected: dict) -> dict:
    """
    Mock DB 환경에서 코드를 실제로 실행해 반환값을 확인합니다.

    Args:
        code: 모델이 출력한 Python 코드
        expected: {
            "rowcount": int,          # Mock cursor.rowcount
            "fetchone": tuple|None,   # Mock cursor.fetchone 반환값
            "fetchall": list,         # Mock cursor.fetchall 반환값
            "description": list|None, # Mock cursor.description
            "success": bool,          # 기대하는 result.success
            "has_result_id": bool,    # result_id 가 None이 아니어야 하면 True
        }

    Returns:
        {"pass": bool, "score": float, "reason": str}
    """
    if not code or not code.strip():
        return {"pass": False, "score": 0.0, "reason": "빈 코드"}

    # 먼저 문법 검사
    syntax = check_syntax(code)
    if not syntax["pass"]:
        return {"pass": False, "score": 0.0, "reason": f"문법 오류로 실행 불가: {syntax['reason']}"}

    harness = _MOCK_HARNESS.format(
        rowcount    = expected.get("rowcount", 1),
        description = repr(expected.get("description", [("Id",)])),
        fetchone    = repr(expected.get("fetchone", (42,))),
        fetchall    = repr(expected.get("fetchall", [])),
        user_code   = textwrap.indent(code, ""),
    )

    import subprocess, sys
    try:
        proc = subprocess.run(
            [sys.executable, "-c", harness],
            capture_output=True, text=True, timeout=10
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if "NO_FUNCTION_FOUND" in stdout:
            return {"pass": False, "score": 0.2, "reason": "함수를 찾지 못함"}

        if "EXEC_ERROR:" in stdout:
            err_line = [l for l in stdout.splitlines() if "EXEC_ERROR:" in l]
            return {"pass": False, "score": 0.3, "reason": f"실행 오류: {err_line[0] if err_line else stderr[:100]}"}

        # 결과 파싱
        result_map = {}
        for line in stdout.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                result_map[key.strip()] = val.strip()

        actual_success = result_map.get("RESULT_SUCCESS", "None") == "True"
        actual_id      = result_map.get("RESULT_ID", "None")
        actual_error   = result_map.get("RESULT_ERROR", "None")
        actual_rows    = int(result_map.get("RESULT_ROWS", "0"))

        checks = []
        # success 필드 확인
        exp_success = expected.get("success", True)
        if actual_success == exp_success:
            checks.append("success 일치")
        else:
            checks.append(f"success 불일치 (기대:{exp_success}, 실제:{actual_success})")

        # result_id 확인
        if expected.get("has_result_id", False):
            if actual_id != "None":
                checks.append("result_id 반환됨")
            else:
                checks.append("result_id 없음 (기대됨)")

        # error 필드 확인
        if actual_error != "None" and exp_success:
            checks.append(f"불필요한 error 설정됨: {actual_error}")

        passed = actual_success == exp_success
        if expected.get("has_result_id") and actual_id == "None":
            passed = False

        score = 1.0 if passed else 0.4
        return {"pass": passed, "score": score, "reason": " | ".join(checks)}

    except subprocess.TimeoutExpired:
        return {"pass": False, "score": 0.0, "reason": "실행 타임아웃 (10초 초과)"}
    except Exception as e:
        return {"pass": False, "score": 0.0, "reason": f"검사 실행 오류: {e}"}


# ──────────────────────────────────────────────────────────────────────────────
# 통합 평가
# ──────────────────────────────────────────────────────────────────────────────

# 각 SQL 프로시저별 Mock 기대값 설정
EXPECTED_BY_PROCEDURE = {
    "usp_get_books_storebook":         {"rowcount": 2, "description": [("Isbn",),("Title",),("Pages",),("Year",),("Category",),("Author",)], "fetchall": [("9780134494166", "Clean Code", 431, 2008, "Programming", "Martin, Robert")], "fetchone": None, "success": True, "has_result_id": False},
    "usp_add_book_storebook":          {"rowcount": 1, "fetchone": None, "fetchall": [], "success": True, "has_result_id": False},
    "usp_add_authorbook_storebook":    {"rowcount": 1, "fetchone": None, "fetchall": [], "success": True, "has_result_id": False},
    "usp_add_category_storebook":      {"rowcount": 1, "fetchone": (7,), "fetchall": [], "success": True, "has_result_id": True},
    "usp_modified_book_storebook":     {"rowcount": 1, "fetchone": None, "fetchall": [], "success": True, "has_result_id": False},
    "usp_modified_authorbook_storebook": {"rowcount": 1, "fetchone": None, "fetchall": [], "success": True, "has_result_id": False},
    "usp_delete_book_storebook":       {"rowcount": 1, "fetchone": None, "fetchall": [], "success": True, "has_result_id": False},
}


def evaluate(code: str, procedure_name: str) -> dict:
    """
    3가지 검사를 모두 실행하고 종합 점수를 반환합니다.

    Args:
        code:           모델이 출력한 Python 코드
        procedure_name: 프로시저 이름 (예: "usp_add_book_storebook")

    Returns:
        {
            "syntax":  {"pass", "score", "reason"},
            "pattern": {"pass", "score", "reason", "details"},
            "logic":   {"pass", "score", "reason"},
            "total_score": float (0.0 ~ 1.0),
            "summary": str,
        }
    """
    syntax  = check_syntax(code)
    pattern = check_patterns(code)
    expected = EXPECTED_BY_PROCEDURE.get(procedure_name, {
        "rowcount": 1, "fetchone": (42,), "fetchall": [],
        "success": True, "has_result_id": False,
    })
    logic = check_logic(code, expected)
    gold = check_gold_similarity(code, procedure_name)
    style = check_style_rubric(code, procedure_name)

    # 가중 평균 — 정답 유사도 비중 최대 (정확도 우선)
    w_syn, w_pat, w_log, w_gold, w_sty = 0.10, 0.10, 0.22, 0.38, 0.20
    total = round(
        syntax["score"]  * w_syn +
        pattern["score"] * w_pat +
        logic["score"]   * w_log +
        gold["score"]    * w_gold +
        style["score"]   * w_sty,
        3
    )

    # 기존: 3종만 만족 시 True (하위 호환)
    all_pass = syntax["pass"] and pattern["pass"] and logic["pass"]
    # 엄격: 정답·스타일까지 (리포트용)
    all_pass_strict = all_pass and gold["pass"] and style["pass"]

    summary = (
        f"총점 {total:.0%} | "
        f"문법({'O' if syntax['pass'] else 'X'}) "
        f"패턴({'O' if pattern['pass'] else 'X'}) "
        f"논리({'O' if logic['pass'] else 'X'}) "
        f"정답({'O' if gold['pass'] else 'X'}) "
        f"스타일({'O' if style['pass'] else 'X'})"
    )

    return {
        "syntax":      syntax,
        "pattern":     pattern,
        "logic":       logic,
        "gold":        gold,
        "style":       style,
        "total_score": total,
        "all_pass":    all_pass,
        "all_pass_strict": all_pass_strict,
        "summary":     summary,
    }
