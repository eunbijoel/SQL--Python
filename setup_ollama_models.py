#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BookStore 벤치마크용 Ollama 모델 맞추기 (확인 + pull 안내/실행).

Cursor에서 이 파일과 터미널을 같이 보려면:
  1) 이 파일을 에디터에서 연다.
  2) Ctrl+` (백틱) 로 터미널을 연다.
  3) 에디터 탭을 우클릭 → Split Right 로 스크립트를 오른쪽에 두고,
     왼쪽(또는 아래)에 터미널을 두면 출력을 보면서 명령을 복사해 실행하기 좋다.

터미널에서:
  py -3 setup_ollama_models.py              # 설치 여부만 표 + pull 명령 출력
  py -3 setup_ollama_models.py --pull       # 빠진 모델마다 y 물어보고 ollama pull
  py -3 setup_ollama_models.py --pull -y    # 확인 없이 전부 pull (용량·시간 큼)

원격 Ollama면 (예: SSH 터널):
  set OLLAMA_BASE_URL=http://127.0.0.1:11434
  ※ pull 은 보통 모델이 돌아가는 그 PC에서 ollama CLI로 해야 한다.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv()

from fewshot.model_runner import (  # noqa: E402
    MODEL_CONFIG,
    OLLAMA_BASE_URL,
    check_ollama_status,
    ollama_resolved_id,
)


def _ollama_cli() -> str | None:
    return shutil.which("ollama")


def main() -> int:
    parser = argparse.ArgumentParser(description="벤치마크용 Ollama 모델 확인 / pull")
    parser.add_argument(
        "--pull",
        action="store_true",
        help="설치 안 된 모델에 대해 ollama pull 시도",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="--pull 시 확인 없이 진행",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Ollama 서버:", OLLAMA_BASE_URL)
    print("=" * 60)

    status = check_ollama_status()
    if not status["running"]:
        print("Ollama에 연결할 수 없습니다:", status.get("error", ""))
        print("→ 그 PC에서 Ollama를 켠 뒤 다시 실행하세요 (ollama serve / 서비스).")
        return 1

    installed = set(status["models"])
    print("설치된 모델 (ollama list /api/tags):\n ", "\n  ".join(sorted(installed)), sep="")

    print("\n" + "-" * 60)
    print("벤치마크 logical 키 → 실제로 /api/generate 에 넣을 이름")
    print("-" * 60)

    missing: list[tuple[str, str]] = []

    for key, cfg in MODEL_CONFIG.items():
        if cfg["type"] != "ollama":
            continue
        resolved = ollama_resolved_id(key)
        ok = resolved in installed
        mark = "OK " if ok else "없음"
        env_hint = {
            "gemma3": "OLLAMA_MODEL_GEMMA3",
            "qwen2.5-coder": "OLLAMA_MODEL_QWEN2_5_CODER",
            "glm-4-flash": "OLLAMA_MODEL_GLM",
        }.get(key, "")
        extra = f"  (환경변수 {env_hint} 로 덮어쓰기 가능)" if env_hint else ""
        print(f"  [{mark}] {key:16} → {resolved}{extra}")
        if not ok:
            missing.append((key, resolved))

    print("\n" + "=" * 60)
    print("터미널에 복사해서 쓸 pull 예시 (레지스트리에 있을 때)")
    print("=" * 60)
    print(
        "  공식 라이브러리에 올라온 이름이면 아래처럼 받을 수 있습니다.\n"
        "  (태그는 ollama.com/library 에서 확인)\n"
    )
    print("  ollama pull qwen2.5-coder")
    print("  ollama pull gemma3")
    print()
    print(
        "  GLM(glm-4.7-flash:Q4_K_M 등)은 공식 library에 없을 수 있습니다.\n"
        "  그 경우: 이미 만든 Modelfile/GGUF가 있으면 그 PC에서 import 하거나,\n"
        "  본인이 쓰는 정확한 태그에 맞게 fewshot/model_runner.py 의\n"
        "  MODEL_CONFIG 와 OLLAMA_MODEL_GLM 을 맞추면 됩니다.\n"
    )
    print("  pull 할 때는 보통 `ollama pull <이름>` 에 `ollama list` 와 같은 문자열을 씁니다.")

    if not missing:
        print("\n필요한 Ollama 모델이 모두 잡혀 있습니다. 바로:")
        print("  py -3 run_benchmark.py --check-ollama")
        print("  py -3 run_benchmark.py")
        return 0

    ollama_exe = _ollama_cli()
    print("\n" + "=" * 60)
    print("아직 없는 항목 — pull 제안 (resolved 이름 기준)")
    print("=" * 60)
    for key, resolved in missing:
        print(f"  ollama pull {resolved}")

    if not args.pull:
        print("\n(자동 pull 은 안 했습니다. 필요하면: py -3 setup_ollama_models.py --pull)")
        return 0

    if not ollama_exe:
        print("\n`ollama` CLI 가 PATH 에 없어 pull 을 실행할 수 없습니다.")
        print("Ollama 설치 후 터미널을 다시 열고 위 명령을 직접 실행하세요.")
        return 1

    print("\nollama 실행 파일:", ollama_exe)

    for key, resolved in missing:
        cmd = [ollama_exe, "pull", resolved]
        line = " ".join(cmd)
        if not args.yes:
            try:
                ans = input(f"\n실행할까요? [y/N]  {line}\n> ").strip().lower()
            except EOFError:
                print("(비대화형 환경 — -y 로 다시 실행하세요)")
                return 1
            if ans not in ("y", "yes"):
                print("  건너뜀.")
                continue
        print("\n>>>", line, flush=True)
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"  실패 (exit {r.returncode}). 이름이 레지스트리와 다를 수 있습니다.")
            continue

    print("\n다시 확인:")
    status2 = check_ollama_status()
    for key, cfg in MODEL_CONFIG.items():
        if cfg["type"] != "ollama":
            continue
        resolved = ollama_resolved_id(key)
        ok = resolved in set(status2.get("models", []))
        print(f"  [{'OK ' if ok else '없음'}] {key} → {resolved}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
