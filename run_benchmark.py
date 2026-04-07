"""
run_benchmark.py
================
전체 벤치마크를 실행하는 메인 파일.

실행 방법:
    python run_benchmark.py                    # 전체 실행 (3모델 × 7SQL)
    python run_benchmark.py --preview          # 프롬프트 미리보기만
    python run_benchmark.py --check-ollama     # Ollama 상태 확인
    python run_benchmark.py --models gemma3 qwen2.5-coder   # 특정 모델만
    python run_benchmark.py --mini             # SQL 1개로 빠른 테스트
"""

import argparse
import sys
import os

# 경로 설정 (어디서 실행해도 동작하도록)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from fewshot.examples import TEST_TARGETS
from fewshot.prompt_builder import build_prompt, print_prompt_preview
from fewshot.model_runner import run_model, check_ollama_status, MODEL_CONFIG
from evaluation.checker import evaluate
from evaluation.reporter import print_table, print_detail, save_json, print_winner


DEFAULT_MODELS = ["gemma3", "qwen2.5-coder", "glm-4-flash"]


def run_full_benchmark(models: list[str], targets: list[dict], n_examples: int = 4) -> list[dict]:
    """
    모든 모델 × 모든 SQL 조합을 실행하고 평가합니다.

    Args:
        models:     실행할 모델 목록
        targets:    변환할 SQL 프로시저 목록
        n_examples: few-shot 예시 개수

    Returns:
        평가 결과 목록
    """
    results = []
    total = len(models) * len(targets)
    done  = 0

    print(f"\n벤치마크 시작: {len(models)}개 모델 × {len(targets)}개 SQL = {total}개 조합\n")

    for target in targets:
        prompt = build_prompt(target["sql"], n_examples)

        for model in models:
            done += 1
            print(f"[{done:02d}/{total}] {model} ← {target['name']} ...", end=" ", flush=True)

            # 모델 호출
            result = run_model(model, prompt)

            if result["error"]:
                print(f"ERROR: {result['error'][:60]}")
                results.append({
                    "procedure": target["name"],
                    "category":  target.get("category", ""),
                    "model":     model,
                    "output":    "",
                    "elapsed":   result["elapsed"],
                    "eval": {
                        "syntax":      {"pass": False, "score": 0.0, "reason": result["error"]},
                        "pattern":     {"pass": False, "score": 0.0, "reason": "모델 호출 실패"},
                        "logic":       {"pass": False, "score": 0.0, "reason": "모델 호출 실패"},
                        "total_score": 0.0,
                        "all_pass":    False,
                        "summary":     f"모델 오류: {result['error'][:50]}",
                    },
                })
                continue

            # 평가
            ev = evaluate(result["output"], target["name"])
            print(f"{ev['summary']}")

            results.append({
                "procedure": target["name"],
                "category":  target.get("category", ""),
                "model":     model,
                "output":    result["output"],
                "elapsed":   result["elapsed"],
                "eval":      ev,
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="SQL-to-Python Few-shot 벤치마크")
    parser.add_argument("--preview",      action="store_true", help="프롬프트 미리보기")
    parser.add_argument("--check-ollama", action="store_true", help="Ollama 상태 확인")
    parser.add_argument("--mini",         action="store_true", help="SQL 1개로 빠른 테스트")
    parser.add_argument("--models",       nargs="+",           help="사용할 모델 목록", default=DEFAULT_MODELS)
    parser.add_argument("--examples",     type=int, default=4, help="few-shot 예시 개수 (기본 4)")
    parser.add_argument("--detail",       action="store_true", help="상세 결과 출력")
    parser.add_argument("--no-save",      action="store_true", help="JSON 저장 안 함")
    args = parser.parse_args()

    # ── Ollama 상태 확인 ──────────────────────────────────────────────────────
    if args.check_ollama:
        status = check_ollama_status()
        if status["running"]:
            print(f"Ollama 실행 중 (설치된 모델: {status['models']})")
            needed = ["gemma3", "qwen2.5-coder"]
            for m in needed:
                found = any(m in installed for installed in status["models"])
                print(f"  {'O' if found else 'X'} {m}")
        else:
            print(f"Ollama 미실행: {status['error']}")
            print("→ 'ollama serve' 명령으로 실행하세요")
        return

    # ── 프롬프트 미리보기 ────────────────────────────────────────────────────
    if args.preview:
        sample_sql = TEST_TARGETS[0]["sql"]
        print_prompt_preview(sample_sql, args.examples)
        return

    # ── 미니 테스트 (SQL 1개) ────────────────────────────────────────────────
    targets = [TEST_TARGETS[0]] if args.mini else TEST_TARGETS

    # ── 전체 실행 ────────────────────────────────────────────────────────────
    results = run_full_benchmark(args.models, targets, args.examples)

    # ── 결과 출력 ────────────────────────────────────────────────────────────
    print_table(results)

    if args.detail:
        print_detail(results)

    print_winner(results)

    if not args.no_save:
        save_json(results)


if __name__ == "__main__":
    main()
