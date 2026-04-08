"""
fewshot/model_runner.py
========================
기본은 Gemma / Qwen / GLM **모두 Ollama** `/api/generate` (API 키 불필요).
원하면 MODEL_CONFIG에서 항목의 type을 \"glm\"으로 두어 Zhipu 클라우드 API를 쓸 수 있습니다.

Ollama model 문자열은 `ollama list`와 동일해야 합니다 (태그 포함).
짧은 이름만 쓴 경우 `/api/tags`로 자동 보완합니다.

환경변수로 이름 고정:
    OLLAMA_MODEL_GEMMA3=gemma3:12b
    OLLAMA_MODEL_QWEN2_5_CODER=qwen2.5-coder:14b
    OLLAMA_MODEL_GLM=glm-4.7-flash:Q4_K_M

원격 Ollama(DGX, SSH 터널 등):
    OLLAMA_BASE_URL=http://127.0.0.1:11434

긴 출력: OLLAMA_NUM_PREDICT (기본 4096)
"""

import json
import os
import time
import urllib.request
import urllib.error
# ──────────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
DEFAULT_GENERATE_TIMEOUT = int(os.getenv("OLLAMA_GENERATE_TIMEOUT", "300"))
GLM_API_KEY     = os.getenv("GLM_API_KEY", "")
GLM_API_URL     = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

MODEL_CONFIG = {
    "gemma3":        {"type": "ollama", "model": "gemma3"},
    "qwen2.5-coder": {"type": "ollama", "model": "qwen2.5-coder"},
    # GLM도 Ollama GGUF 등 로컬 태그로 실행 (sql2python config.yaml 과 동일한 이름)
    "glm-4-flash":   {"type": "ollama", "model": "glm-4.7-flash:Q4_K_M"},
}

# logical_key → env: `ollama list`와 동일한 전체 이름을 강제할 때 사용
_OLLAMA_ENV_BY_KEY = {
    "gemma3": "OLLAMA_MODEL_GEMMA3",
    "qwen2.5-coder": "OLLAMA_MODEL_QWEN2_5_CODER",
    "glm-4-flash": "OLLAMA_MODEL_GLM",
}


def _ollama_model_id_for_key(model_key: str) -> str:
    """config 기본값 또는 환경변수로 Ollama에 넘길 model id."""
    env_name = _OLLAMA_ENV_BY_KEY.get(model_key)
    if env_name:
        override = os.getenv(env_name, "").strip()
        if override:
            return override
    return MODEL_CONFIG[model_key]["model"]


# ──────────────────────────────────────────────────────────────────────────────
# Ollama 호출
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_ollama_model_name(short: str) -> str:
    """
    `ollama pull gemma3` 처럼 태그 없이 쓴 이름과, 실제 설치된 `gemma3:27b` 이름을 맞춥니다.
    """
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = [m["name"] for m in data.get("models", [])]
    except Exception:
        return short
    if short in names:
        return short
    for n in names:
        if n.startswith(short + ":"):
            return n
    return short


def ollama_resolved_id(model_key: str) -> str:
    """진단용: logical 키에 대해 /api/tags 기준으로 최종 전달될 Ollama model 이름."""
    return _resolve_ollama_model_name(_ollama_model_id_for_key(model_key))


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
    model = _resolve_ollama_model_name(model)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # 낮을수록 일관된 코드 출력
            "num_predict": OLLAMA_NUM_PREDICT,
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
            if data.get("error"):
                err = data["error"]
                msg = f"Ollama 오류: {err}"
                if "not found" in str(err).lower():
                    msg += (
                        f"\n→ 로컬에 해당 태그가 없을 수 있습니다. "
                        f"`ollama pull {model!r}` 후 `ollama list`로 이름을 확인하세요. "
                        f"또는 OLLAMA_MODEL_GEMMA3 / OLLAMA_MODEL_QWEN2_5_CODER / OLLAMA_MODEL_GLM 으로 지정하세요."
                    )
                raise ConnectionError(msg)
            return data.get("response", "").strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 404:
            raise ConnectionError(
                f"Ollama 모델을 찾을 수 없습니다 (HTTP 404).\n"
                f"→ `ollama list`의 model 이름과 일치하는지 확인하세요. (예: gemma3:12b)\n"
                f"→ 환경변수 OLLAMA_MODEL_GEMMA3, OLLAMA_MODEL_QWEN2_5_CODER, OLLAMA_MODEL_GLM 로 지정 가능.\n"
                f"응답: {body[:500]}"
            ) from e
        raise ConnectionError(f"Ollama HTTP {e.code}: {body[:500]}") from e
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

def run_model(model_key: str, prompt: str, timeout: int | None = None) -> dict:
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
    if timeout is None:
        timeout = DEFAULT_GENERATE_TIMEOUT

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
            output = _call_ollama(_ollama_model_id_for_key(model_key), prompt, timeout)
        elif config["type"] == "glm":
            output = _call_glm(config["model"], prompt, timeout)
        else:
            raise ValueError(f"Unknown backend type: {config['type']!r}")

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
