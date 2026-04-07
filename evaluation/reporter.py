"""
evaluation/reporter.py
=======================
비교 결과를 표로 출력하고 JSON으로 저장합니다.
"""

import json
import os
from datetime import datetime


def print_table(results: list[dict]) -> None:
    """
    터미널에 비교 결과표를 출력합니다.

    results 형식:
        [{"procedure": str, "model": str, "eval": {...}, "elapsed": float}, ...]
    """
    models = sorted({r["model"] for r in results})
    procs  = sorted({r["procedure"] for r in results})

    # 헤더
    col = 32
    header = f"{'프로시저':<{col}}" + "".join(f"{m:^18}" for m in models)
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))

    total_scores = {m: [] for m in models}

    for proc in procs:
        row = f"{proc:<{col}}"
        for model in models:
            match = [r for r in results if r["procedure"] == proc and r["model"] == model]
            if match:
                ev = match[0]["eval"]
                score = ev["total_score"]
                total_scores[model].append(score)
                flag = "O" if ev["all_pass"] else "X"
                row += f"  {score:.0%} [{flag}]  ({match[0]['elapsed']:.1f}s)"
            else:
                row += f"  {'N/A':^14}"
        print(row)

    # 평균
    print("-" * len(header))
    avg_row = f"{'평균'::<{col}}"
    for model in models:
        scores = total_scores[model]
        avg = sum(scores) / len(scores) if scores else 0
        avg_row += f"  {avg:.0%}{'':^12}"
    print(avg_row)
    print("=" * len(header))


def print_detail(results: list[dict]) -> None:
    """각 프로시저별 상세 결과를 출력합니다."""
    for r in results:
        ev = r["eval"]
        print(f"\n[{r['procedure']}] — {r['model']}")
        print(f"  문법:  {'PASS' if ev['syntax']['pass'] else 'FAIL'} | {ev['syntax']['reason']}")
        print(f"  패턴:  {'PASS' if ev['pattern']['pass'] else 'FAIL'} | {ev['pattern']['reason']}")
        print(f"  논리:  {'PASS' if ev['logic']['pass'] else 'FAIL'} | {ev['logic']['reason']}")
        print(f"  총점:  {ev['total_score']:.0%} | {ev['summary']}")


def save_json(results: list[dict], output_dir: str = "results") -> str:
    """결과를 JSON 파일로 저장합니다."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"benchmark_{timestamp}.json")

    # JSON 직렬화 가능하도록 정리
    clean = []
    for r in results:
        clean.append({
            "procedure": r["procedure"],
            "category":  r.get("category", ""),
            "model":     r["model"],
            "elapsed":   r["elapsed"],
            "eval":      r["eval"],
            "code_length": len(r.get("output", "")),
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp, "results": clean}, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장됨: {path}")
    return path


def print_winner(results: list[dict]) -> None:
    """최종 승자를 출력합니다."""
    models = sorted({r["model"] for r in results})
    avg_scores = {}
    for model in models:
        scores = [r["eval"]["total_score"] for r in results if r["model"] == model]
        avg_scores[model] = sum(scores) / len(scores) if scores else 0

    winner = max(avg_scores, key=avg_scores.get)
    print("\n" + "=" * 50)
    print("최종 결과")
    print("=" * 50)
    for model, score in sorted(avg_scores.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20)
        print(f"  {model:<20} {score:.0%}  {bar}")
    print(f"\n  승자: {winner} ({avg_scores[winner]:.0%})")
    print("=" * 50)
