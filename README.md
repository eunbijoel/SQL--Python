# SQL→Python Few-shot 벤치마크

T-SQL 저장 프로시저를 Python으로 변환하는 Few-shot 프롬프트를 만들고,
Gemma / Qwen / GLM 세 모델의 변환 성능을 자동으로 비교합니다.

---

## 전체 구조

```
bookstore_bench/
│
├── db/                         # DB 연결 (기존 코드)
│   ├── connection.py           # pyodbc 연결 + 커서 컨텍스트 매니저
│   └── result.py               # ProcedureResult 공통 반환 타입
│
├── procedures/                 # 정답 Python 번역 (기존 코드 = few-shot 예시 재료)
│   ├── add_procedures.py
│   ├── delete_procedures.py
│   ├── get_procedures.py
│   └── modify_procedures.py
│
├── fewshot/                    # Few-shot 핵심
│   ├── examples.py             # 예시 쌍 (SQL→Python) + 테스트 타겟 SQL
│   ├── prompt_builder.py       # 프롬프트 조립기
│   └── model_runner.py         # 기본: Gemma/Qwen/GLM 모두 Ollama (선택: Zhipu GLM)
│
├── evaluation/                 # 자동 평가기
│   ├── checker.py              # 검사 1(문법) + 검사 2(패턴) + 검사 3(논리)
│   └── reporter.py             # 결과 표 출력 + JSON 저장
│
├── tests/
│   ├── test_all_procedures.py      # 기존 번역 함수 단위 테스트
│   └── test_fewshot_and_evaluation.py  # 프롬프트 + 평가기 검증 (DB 불필요)
│
├── results/                    # 벤치마크 결과 JSON 자동 저장
├── run_benchmark.py            # 메인 실행 파일
├── .env.example
└── requirements.txt
```

---

## 1단계: 설치

```bash
# Python 패키지
pip install pyodbc python-dotenv pytest requests

# Ollama 설치 (https://ollama.com)
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 모델 다운로드 (최초 1회, 시간 걸림)
ollama pull gemma3          # ~5GB
ollama pull qwen2.5-coder   # ~4GB
```

## 2단계: 모델 이름·환경 (API 키는 기본 불필요)

**기본 설정은 Gemma / Qwen / GLM 세 모두 Ollama** `/api/generate` 입니다. `glm-4-flash` 슬롯은 `ollama list`의 GGUF 태그(예: `glm-4.7-flash:Q4_K_M`)를 가리키며, **Zhipu API 키는 필요 없습니다.**

`fewshot/model_runner.py`의 `MODEL_CONFIG`에서 GLM 기본 태그를 본인 서버에 맞게 바꾸거나, 환경변수로 덮어쓸 수 있습니다 (sql2python `config.yaml`의 `model_name`과 동일한 문자열).

```bash
# 예: PowerShell
$env:OLLAMA_MODEL_GEMMA3 = "gemma3:12b"
$env:OLLAMA_MODEL_QWEN2_5_CODER = "qwen2.5-coder:14b"
$env:OLLAMA_MODEL_GLM = "glm-4.7-flash:Q4_K_M"
# 원격 Ollama: $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
# 긴 코드 생성: $env:OLLAMA_NUM_PREDICT = "4096"
# 느린 GPU: $env:OLLAMA_GENERATE_TIMEOUT = "600"
```

**Zhipu 클라우드 GLM**을 쓰려면 `MODEL_CONFIG`에 별도 항목을 두고 `type: "glm"`으로 설정한 뒤 `GLM_API_KEY`를 넣으면 됩니다 (기본 glm 슬롯과 분리하는 편이 안전합니다).

## 3단계: 로컬 검증 (DB/Ollama 없이)

```bash
# 프롬프트가 제대로 만들어지는지, 평가기가 잘 작동하는지 확인
python tests/test_fewshot_and_evaluation.py

# 예상 결과: Ran 25 tests ... OK
```

## 4단계: 프롬프트 눈으로 확인

```bash
# Windows 콘솔에서 유니코드 출력 오류가 나면:
#   PowerShell: $env:PYTHONIOENCODING = "utf-8"
python run_benchmark.py --preview
# 프롬프트 내용이 화면에 출력됨
# 예시 SQL + 예시 Python + 변환할 SQL 순서 확인
```

## 5단계: Ollama 모델 맞추기 · 상태 확인

모델이 부족할 때는 루트의 `**setup_ollama_models.py**` 를 열어 두고 터미널을 옆에 두고 실행하면, 부족한 항목과 `ollama pull …` 예시가 같이 나옵니다.

```bash
python setup_ollama_models.py              # 설치 여부 + 복사용 pull 명령
python setup_ollama_models.py --pull       # 없는 모델만 순서대로 pull (대화형)
python setup_ollama_models.py --pull -y    # 확인 없이 pull (시간·용량 큼)
```

- **Qwen**: 보통 `ollama pull qwen2.5-coder` (원하는 태그는 [library](https://ollama.com/library) 참고).
- **GLM GGUF** (`glm-4.7-flash:Q4_K_M` 등): 공식 `pull` 로 안 될 수 있음 → 그 PC에서 이미 쓰는 Modelfile/import 태그에 맞추거나 `OLLAMA_MODEL_GLM` / `MODEL_CONFIG` 로 이름 통일.

```bash
ollama serve  # 별도 터미널에서 실행

python run_benchmark.py --check-ollama
# 각 logical 키 → 해석된 Ollama 이름 옆에 O/X
```

## 6단계: 빠른 미니 테스트 (SQL 1개)

```bash
python run_benchmark.py --mini
# SQL 1개 × 3모델 = 3번 변환 (세 모델 모두 Ollama에 있어야 함)

python run_benchmark.py --mini --models gemma3 qwen2.5-coder
# GLM 슬롯 제외 시 2회 변환
```

## 7단계: 전체 벤치마크 실행

```bash
# 7개 SQL × 3개 모델 = 21회 변환 + 자동 평가
python run_benchmark.py

# 상세 결과 포함
python run_benchmark.py --detail

# 특정 모델만
python run_benchmark.py --models gemma3 qwen2.5-coder
```

---

## 출력 예시

```
벤치마크 시작: 3개 모델 × 7개 SQL = 21개 조합

[01/21] gemma3 ← usp_get_books_storebook ... 총점 87% | 문법(O) 패턴(O) 논리(X)
[02/21] qwen2.5-coder ← usp_get_books_storebook ... 총점 100% | 문법(O) 패턴(O) 논리(O)
...

================================================================
프로시저                        gemma3            qwen2.5-coder     glm-4-flash
================================================================
usp_get_books_storebook        87% [X]  (8.2s)   100% [O]  (6.1s)  73% [X]  (3.4s)
usp_add_book_storebook         100% [O] (7.4s)   100% [O]  (5.8s)  87% [X]  (2.9s)
...
----------------------------------------------------------------
평균                           83%               94%               71%
================================================================

==================================================
최종 결과
==================================================
  qwen2.5-coder        94%  ████████████████████
  gemma3               83%  ████████████████
  glm-4-flash          71%  ██████████████

  승자: qwen2.5-coder (94%)
==================================================

결과 저장됨: results/benchmark_20240407_153022.json
```

---

## 평가 기준

종합 **총점**은 아래 가중 평균입니다. **정답 유사도**가 가장 큽니다 (정확도 우선).

| 검사 | 가중치 | 내용 |
| --- | --- | --- |
| 문법 | 10% | `ast.parse()` 통과, `def` 함수 존재 |
| 패턴 | 10% | 문자열 기준 `ProcedureResult` / `get_db_cursor` / `try` (few-shot 정렬용) |
| 논리 | 22% | Mock DB로 실행 → `success`, `result_id` 등 (휴리스틱 인자) |
| **정답 유사도** | **38%** | `procedures/*.py` 해당 함수와 라인·AST 유사도 (`difflib` 등) |
| 스타일 루브릭 | 20% | Comparator 스타일: `?`/인자 균형, 위험 패턴, `get_db_cursor` 등 |

표의 `[O]`/`[X]`는 기존과 같이 **문법·패턴·논리** 3종만 모두 통과일 때 `O`입니다.  
`run_benchmark.py --detail` 출력에 **정답·스타일·엄격통과**(5종 전부)가 추가로 나옵니다.


---

## Few-shot 구성

- 예시 4개 (SELECT 1개, INSERT 1개, UPDATE 1개, DELETE 1개)
- 테스트 대상 7개 (나머지 프로시저)
- 예시 수 조정: `--examples 2` 옵션으로 변경 가능

---

## 새 SQL 파일 추가 방법

1. `sql_files/` 폴더에 `.sql` 파일 추가
2. `fewshot/examples.py`의 `TEST_TARGETS` 리스트에 항목 추가
3. `evaluation/checker.py`의 `EXPECTED_BY_PROCEDURE`에 기대값 추가
4. `python run_benchmark.py` 재실행

