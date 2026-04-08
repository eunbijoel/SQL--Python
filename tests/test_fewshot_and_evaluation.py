"""
tests/test_fewshot_and_evaluation.py
=====================================
Ollama/DB 없이 로컬에서 실행 가능한 테스트.

검증 항목:
    1. few-shot 프롬프트가 제대로 구성되는가?
    2. 기존 번역 코드(정답)가 평가 기준을 통과하는가?
    3. 평가기가 나쁜 코드를 올바르게 걸러내는가?

실행:
    python -m pytest tests/test_fewshot_and_evaluation.py -v
    또는
    python tests/test_fewshot_and_evaluation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ast
import unittest

from fewshot.examples import EXAMPLES, TEST_TARGETS
from fewshot.prompt_builder import build_prompt
from evaluation.checker import check_syntax, check_patterns, evaluate
from evaluation.gold_similarity import _read_gold_function, check_gold_similarity
from evaluation.style_rubric import check_style_rubric


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 1: Few-shot 프롬프트 구조 확인
# ──────────────────────────────────────────────────────────────────────────────

class TestPromptBuilder(unittest.TestCase):

    def test_예시가_4개_포함되는가(self):
        prompt = build_prompt("SELECT 1", n_examples=4)
        self.assertEqual(prompt.count("### Example"), 4)

    def test_SQL_입력이_포함되는가(self):
        sql = "CREATE PROCEDURE test_proc AS SELECT 1"
        prompt = build_prompt(sql)
        self.assertIn(sql, prompt)

    def test_Python_정답이_포함되는가(self):
        prompt = build_prompt("SELECT 1")
        # 예시 정답 코드의 일부가 들어있어야 함
        self.assertIn("ProcedureResult", prompt)
        self.assertIn("get_db_cursor", prompt)

    def test_변환요청_마커가_있는가(self):
        prompt = build_prompt("SELECT 1")
        self.assertIn("Now convert the following SQL", prompt)

    def test_Python_Output_마커가_마지막에_있는가(self):
        prompt = build_prompt("SELECT 1")
        # "Python Output:"이 마지막 줄 근처에 있어야 함
        lines = prompt.strip().split("\n")
        last_section = "\n".join(lines[-5:])
        self.assertIn("Python Output:", last_section)

    def test_예시_수_줄이기_가능한가(self):
        prompt_2 = build_prompt("SELECT 1", n_examples=2)
        prompt_4 = build_prompt("SELECT 1", n_examples=4)
        self.assertEqual(prompt_2.count("### Example"), 2)
        self.assertLess(len(prompt_2), len(prompt_4))

    def test_모든_SQL_카테고리_포함(self):
        categories = {ex["category"] for ex in EXAMPLES}
        self.assertIn("SELECT", categories)
        self.assertIn("INSERT", categories)
        self.assertIn("UPDATE", categories)
        self.assertIn("DELETE", categories)


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 2: 기존 정답 코드가 평가 기준을 통과하는가?
# ──────────────────────────────────────────────────────────────────────────────

class TestAnswerCodeQuality(unittest.TestCase):
    """
    우리가 직접 번역한 코드(정답)가 평가기를 통과해야 합니다.
    통과 못하면 평가 기준이 잘못된 것.
    """

    def _load_procedure_code(self, filename: str) -> str:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "procedures", filename)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_add_procedures_문법_검사(self):
        code = self._load_procedure_code("add_procedures.py")
        result = check_syntax(code)
        self.assertTrue(result["pass"], f"문법 오류: {result['reason']}")

    def test_get_procedures_문법_검사(self):
        code = self._load_procedure_code("get_procedures.py")
        result = check_syntax(code)
        self.assertTrue(result["pass"], f"문법 오류: {result['reason']}")

    def test_modify_procedures_문법_검사(self):
        code = self._load_procedure_code("modify_procedures.py")
        result = check_syntax(code)
        self.assertTrue(result["pass"])

    def test_delete_procedures_문법_검사(self):
        code = self._load_procedure_code("delete_procedures.py")
        result = check_syntax(code)
        self.assertTrue(result["pass"])

    def test_add_procedures_패턴_검사(self):
        code = self._load_procedure_code("add_procedures.py")
        result = check_patterns(code)
        self.assertTrue(result["pass"], f"패턴 미충족: {result['reason']}")

    def test_모든_정답_파일_파싱_가능(self):
        files = ["add_procedures.py", "get_procedures.py",
                 "modify_procedures.py", "delete_procedures.py"]
        for fname in files:
            code = self._load_procedure_code(fname)
            try:
                ast.parse(code)
            except SyntaxError as e:
                self.fail(f"{fname} SyntaxError: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 3: 평가기가 나쁜 코드를 걸러내는가?
# ──────────────────────────────────────────────────────────────────────────────

class TestCheckerAccuracy(unittest.TestCase):

    def test_빈_코드_탈락(self):
        r = check_syntax("")
        self.assertFalse(r["pass"])

    def test_문법_오류_탈락(self):
        bad = "def foo(\n    pass"
        r = check_syntax(bad)
        self.assertFalse(r["pass"])

    def test_올바른_코드_통과(self):
        good = """\
def add_author(firstname, surname):
    if not firstname:
        return ProcedureResult(error="필수")
    try:
        with get_db_cursor() as cursor:
            cursor.execute("INSERT INTO Authors VALUES (?)", (firstname,))
            return ProcedureResult(success=True)
    except Exception as e:
        return ProcedureResult(error=str(e))
"""
        r_syntax  = check_syntax(good)
        r_pattern = check_patterns(good)
        self.assertTrue(r_syntax["pass"])
        self.assertTrue(r_pattern["pass"])

    def test_ProcedureResult_없으면_패턴_탈락(self):
        bad = """\
def add_author(firstname):
    try:
        cursor.execute("INSERT INTO Authors VALUES (?)", (firstname,))
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}
"""
        r = check_patterns(bad)
        self.assertFalse(r["pass"])

    def test_try_except_없으면_패턴_탈락(self):
        bad = """\
def add_author(firstname):
    cursor.execute("INSERT INTO Authors VALUES (?)", (firstname,))
    return ProcedureResult(success=True)
"""
        r = check_patterns(bad)
        self.assertFalse(r["pass"])

    def test_get_db_cursor_없으면_패턴_탈락(self):
        bad = """\
def add_author(firstname):
    try:
        conn.execute("INSERT INTO Authors VALUES (?)", (firstname,))
        return ProcedureResult(success=True)
    except Exception as e:
        return ProcedureResult(error=str(e))
"""
        r = check_patterns(bad)
        self.assertFalse(r["pass"])

    def test_함수_없으면_탈락(self):
        no_func = "x = 1 + 2\nprint(x)"
        r = check_syntax(no_func)
        self.assertFalse(r["pass"])


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 3b: 정답 유사도 · 스타일 루브릭
# ──────────────────────────────────────────────────────────────────────────────

class TestGoldAndStyle(unittest.TestCase):

    def test_정답_함수_자기자신과_유사도_높음(self):
        g = _read_gold_function("usp_get_books_storebook")
        self.assertIsNotNone(g)
        r = check_gold_similarity(g, "usp_get_books_storebook")
        self.assertGreaterEqual(r["score"], 0.95, r["reason"])

    def test_엉뚱한_코드는_정답_유사도_낮음(self):
        r = check_gold_similarity("def foo():\n    return 1", "usp_get_books_storebook")
        self.assertLess(r["score"], 0.45)

    def test_evaluate에_gold_style_키_존재(self):
        ev = evaluate("def x():\n    pass", "usp_add_book_storebook")
        self.assertIn("gold", ev)
        self.assertIn("style", ev)
        self.assertIn("all_pass_strict", ev)

    def test_스타일_루브릭_기본_필드(self):
        r = check_style_rubric("def f():\n    pass", "usp_add_book_storebook")
        self.assertIn("details", r)
        self.assertIn("score", r)


# ──────────────────────────────────────────────────────────────────────────────
# 테스트 4: TEST_TARGETS SQL이 모두 존재하는가?
# ──────────────────────────────────────────────────────────────────────────────

class TestExamplesData(unittest.TestCase):

    def test_예시_4개_모두_있음(self):
        self.assertEqual(len(EXAMPLES), 4)

    def test_테스트_타겟_7개_모두_있음(self):
        self.assertEqual(len(TEST_TARGETS), 7)

    def test_각_예시에_필수_필드_있음(self):
        for ex in EXAMPLES:
            self.assertIn("name", ex)
            self.assertIn("sql", ex)
            self.assertIn("python", ex)
            self.assertIn("category", ex)

    def test_각_타겟에_SQL_있음(self):
        for t in TEST_TARGETS:
            self.assertIn("sql", t)
            self.assertGreater(len(t["sql"]), 20)

    def test_예시_Python_코드_문법_정상(self):
        for ex in EXAMPLES:
            try:
                ast.parse(ex["python"])
            except SyntaxError as e:
                self.fail(f"{ex['name']} 예시 Python 코드 오류: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("로컬 검증 테스트 실행 (DB/Ollama 불필요)")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [TestPromptBuilder, TestAnswerCodeQuality,
                TestCheckerAccuracy, TestGoldAndStyle, TestExamplesData]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
