"""
fewshot/model_runner.py
========================
Ollama(로컬)와 GLM API를 통해 모델을 호출하는 모듈.

지원 모델:
    - gemma3        → Ollama (로컬, 무료)
    - qwen2.5-coder → Ollama (로컬, 무료)
    - glm-4-flash   → Zhipu AI API (무료 티어)

사용 전 준비:
    # Ollama 설치 후 모델 다운로드
    ollama pull gemma3
    ollama pull qwen2.5-coder

    # GLM API 키 발급: https://open.bigmodel.cn
    # .env 파일에 추가: GLM_API_KEY=your_key_here
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GLM_API_KEY     = os.getenv("GLM_API_KEY", "")
GLM_API_URL     = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

MODEL_CONFIG = {
    "gemma3":        {"type": "ollama", "model": "gemma3"},
    "qwen2.5-coder": {"type": "ollama", "model": "qwen2.5-coder"},
    "glm-4-flash":   {"type": "glm",    "model": "glm-4-flash"},
}


# ──────────────────────────────────────────────────────────────────────────────
# Ollama 호출
# ──────────────────────────────────────────────────────────────────────────────

def _call_ollama(model: str, prompt: str, timeout: int = 120) -> str:
    """
    Ollama 로컬 서버에 프롬프트를 보내고 응답 텍스트를 반환합니다.

    Args:
        model:   올라마 모델 이름 (예: "gemma3")
        prompt:  완성된 few-shot 프롬프트 문자열
        timeout: 응답 대기 시간 (초)

    Returns:
        모델이 생성한 텍스트 (Python 코드)
    """
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # 낮을수록 일관된 코드 출력
            "num_predict": 1024,  # 최대 토큰 수
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Ollama 연결 실패: {e}\n"
            f"→ 'ollama serve' 명령으로 Ollama가 실행 중인지 확인하세요."
        )


# ──────────────────────────────────────────────────────────────────────────────
# GLM API 호출
# ──────────────────────────────────────────────────────────────────────────────

def _call_glm(model: str, prompt: str, timeout: int = 60) -> str:
    """
    Zhipu AI GLM API를 호출합니다.

    Args:
        model:   GLM 모델 이름 (예: "glm-4-flash")
        prompt:  완성된 few-shot 프롬프트 문자열
        timeout: 응답 대기 시간 (초)

    Returns:
        모델이 생성한 텍스트 (Python 코드)
    """
    if not GLM_API_KEY:
        raise ValueError(
            "GLM_API_KEY가 설정되지 않았습니다.\n"
            "→ .env 파일에 GLM_API_KEY=your_key 를 추가하세요.\n"
            "→ API 키 발급: https://open.bigmodel.cn"
        )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }).encode("utf-8")

    req = urllib.request.Request(
        GLM_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GLM_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise ConnectionError(f"GLM API 오류 ({e.code}): {body}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"GLM API 연결 실패: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# 통합 호출 함수
# ──────────────────────────────────────────────────────────────────────────────

def run_model(model_key: str, prompt: str, timeout: int = 120) -> dict:
    """
    모델 이름을 받아 적절한 API를 호출하고 결과를 반환합니다.

    Args:
        model_key: "gemma3", "qwen2.5-coder", "glm-4-flash" 중 하나
        prompt:    완성된 few-shot 프롬프트
        timeout:   응답 대기 시간 (초)

    Returns:
        {
            "model":    모델 이름,
            "output":   생성된 Python 코드 (str),
            "elapsed":  소요 시간 (초, float),
            "error":    오류 메시지 (성공 시 None),
        }
    """
    if model_key not in MODEL_CONFIG:
        return {
            "model": model_key,
            "output": "",
            "elapsed": 0.0,
            "error": f"알 수 없는 모델: {model_key}. 선택지: {list(MODEL_CONFIG.keys())}",
        }

    config = MODEL_CONFIG[model_key]
    start = time.time()

    try:
        if config["type"] == "ollama":
            output = _call_ollama(config["model"], prompt, timeout)
        else:
            output = _call_glm(config["model"], prompt, timeout)

        # 마크다운 코드 펜스 제거 (모델이 ```python ... ``` 로 감싸는 경우)
        output = _strip_code_fence(output)

        return {
            "model": model_key,
            "output": output,
            "elapsed": round(time.time() - start, 2),
            "error": None,
        }

    except Exception as exc:
        return {
            "model": model_key,
            "output": "",
            "elapsed": round(time.time() - start, 2),
            "error": str(exc),
        }


def _strip_code_fence(text: str) -> str:
    """
    모델이 ```python ... ``` 형태로 감쌌을 때 코드만 추출합니다.
    """
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


# ──────────────────────────────────────────────────────────────────────────────
# Ollama 상태 확인
# ──────────────────────────────────────────────────────────────────────────────

def check_ollama_status() -> dict:
    """
    Ollama 서버가 실행 중인지, 필요한 모델이 설치됐는지 확인합니다.
    실행 전 진단용으로 사용하세요.
    """
    result = {"running": False, "models": [], "error": None}

    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result["running"] = True
            result["models"] = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        result["error"] = str(e)

    return result
