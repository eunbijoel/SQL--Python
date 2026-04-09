# BookStore SQL → Python Few-shot 벤치마크

## 목적

이 저장소는 **Microsoft SQL Server(T-SQL) 저장 프로시저**를 **Python 함수**로 바꾸는 작업을, **Few-shot 프롬프트**로 여러 언어 모델에 시키고 **같은 기준으로 자동 채점**해 비교하기 위한 실험용 프로젝트입니다.

- **입력**: BookStore 시나리오의 T-SQL `CREATE PROCEDURE` 문 (일부는 프롬프트 예시, 일부는 변환 대상).
- **출력**: 각 모델이 생성한 Python 코드.
- **비교**: Gemma / Qwen / GLM(논리 이름) 등 **여러 모델**을 같은 SQL·같은 프롬프트로 돌린 뒤, **문법·패턴·Mock 논리·정답 유사도·스타일**을 합쳐 점수화합니다.

처음 보는 사람은 **「SQL→Python 변환 품질을 모델별로 재현 가능하게 재는 도구」**라고 이해하면 됩니다.

---

## 저장소 구조 (Git과 동일)

클론 후 루트는 대략 다음과 같습니다.

```
SQL--Python/
├── run_benchmark.py          # 벤치마크 메인 CLI
├── setup_ollama_models.py    # Ollama 모델 설치 여부 점검·pull 안내
├── run_full_pipeline.cmd     # Windows: 전체 파이프라인 일괄 실행 (실행 정책 무관)
├── run_full_pipeline.ps1     # PowerShell용 (막히면 ExecutionPolicy Bypass)
├── requirements.txt
├── connection.py             # (레거시) DB 연결 — 벤치 Mock 평가와는 별개
├── result.py                 # (레거시) ProcedureResult 타입 정의 참고용
├── fewshot/
│   ├── examples.py           # Few-shot 예시 쌍 + 벤치 대상 SQL 목록
│   ├── prompt_builder.py     # 시스템 지시 + 예시 + 변환 요청 프롬프트 조립
│   └── model_runner.py       # Ollama / (선택) Zhipu GLM 호출
├── procedures/
│   ├── add_procedures.py     # 정답 번역(INSERT/추가 계열) — 채점 기준·유사도 기준
│   ├── delete_procedures.py
│   ├── get_procedures.py
│   └── modify_procedures.py
├── evaluation/
│   ├── checker.py            # 통합 평가 evaluate() — 가중 총점
│   ├── gold_similarity.py    # procedures 정답 함수와 라인·AST 유사도
│   ├── style_rubric.py       # placeholder 균형·위험 패턴 등 공학 루브릭
│   └── reporter.py           # 터미널 표·승자·JSON 저장
├── tests/
│   └── test_fewshot_and_evaluation.py  # DB/Ollama 없이 프롬프트·평가기 검증
├── results/                  # 실행 시 benchmark_*.json 자동 생성
│   └── .gitkeep
└── README.md
```

---

## 폴더·파일별 역할

| 위치 | 역할 |
|------|------|
| `fewshot/examples.py` | `EXAMPLES`: 프롬프트에 넣을 SQL↔Python 예시. `TEST_TARGETS`: 실제로 모델에 변환시킬 SQL 7개. |
| `fewshot/prompt_builder.py` | 예시와 타깃 SQL을 합쳐 한 덩어리 프롬프트 문자열 생성. |
| `fewshot/model_runner.py` | `MODEL_CONFIG`: 논리 이름(`gemma3` 등) → Ollama 모델 태그 또는 클라우드 GLM. `/api/generate` 호출. |
| `procedures/*.py` | 사람이 써 둔 **참고 구현**. Few-shot 예시의 재료이기도 하고, `gold_similarity`가 **문자열·AST 유사도**를 재는 기준. |
| `evaluation/checker.py` | `evaluate(code, procedure_name)` — 5지표 합산 `total_score`, `all_pass`(3종), `all_pass_strict`(5종). |
| `evaluation/gold_similarity.py` | 프로시저 이름 → `procedures`의 특정 `def`와 모델 출력 **첫 번째 최상위 함수** 비교. |
| `evaluation/style_rubric.py` | `?` 개수와 인자 개수, `get_db_cursor`, 위험 문자열 등 **정적 루브릭**. |
| `evaluation/reporter.py` | 표 출력, `--detail` 시 항목별 이유, `results/benchmark_타임스탬프.json` 저장. |
| `run_benchmark.py` | 인자 파싱, `load_dotenv()`, 전체 루프·저장. |
| `results/` | JSON에는 `eval` 전체(문법·패턴·논리·gold·style 등)가 들어가며, 코드 본문은 길이 위주로 요약 저장. |

---

## 필수 환경 및 설치

- **Python** 3.10 이상 권장 (표준 라이브러리 `ast.unparse` 등 사용).
- **의존성**: 저장소 루트에서  
  `pip install -r requirements.txt`  
  (`pyodbc`, `python-dotenv`, `pytest`, `requests` 등).
- **Ollama** (기본 워크플로): 로컬 또는 원격에서 API 서버가 떠 있어야 합니다.  
  - 기본 URL: `http://localhost:11434`  
  - 다른 포트/원격이면 환경변수 `OLLAMA_BASE_URL` (예: `http://127.0.0.1:11435`).
- **GPU**: 필수는 아님. Ollama가 GPU를 쓰는지는 Ollama 쪽 설정에 따름.
- **API 키**: 기본 설정은 **세 모델 모두 Ollama**라 **Zhipu·Hugging Face 키 불필요**. 클라우드 GLM만 쓸 때 `GLM_API_KEY` + `MODEL_CONFIG`에서 `type: "glm"` 항목을 따로 두는 방식.

선택적으로 프로젝트 루트에 `.env`를 두면 `run_benchmark.py`가 로드합니다.

```env
OLLAMA_BASE_URL=http://127.0.0.1:11435
OLLAMA_MODEL_GEMMA3=gemma3:27b
OLLAMA_MODEL_QWEN2_5_CODER=qwen2.5-coder:32b
OLLAMA_MODEL_GLM=glm-4.7-flash:Q4_K_M
OLLAMA_NUM_PREDICT=4096
OLLAMA_GENERATE_TIMEOUT=600
```

---

## 사용법 (권장 워크플로)

아래는 **한 번도 안 돌려본 사람** 기준 순서입니다. 명령은 Windows에서 `py -3` 또는 `python`으로 통일해도 됩니다.

1. **의존성**  
   `pip install -r requirements.txt`

2. **코드만 검증 (DB·Ollama 불필요)**  
   `python tests/test_fewshot_and_evaluation.py`  
   → 약 29개 테스트가 통과하면 프롬프트·평가 파이프는 정상에 가깝습니다.

3. **프롬프트 확인**  
   `python run_benchmark.py --preview`  
   - Windows 콘솔에서 유니코드 오류가 나면:  
     `set PYTHONIOENCODING=utf-8` (cmd) 또는 `$env:PYTHONIOENCODING="utf-8"` (PowerShell).

4. **Ollama 모델 정렬**  
   `python setup_ollama_models.py`  
   → 부족한 태그와 `ollama pull …` 예시가 출력됩니다.  
   그다음 `python run_benchmark.py --check-ollama` 로 논리 키별 O/X 확인.

5. **짧은 연습**  
   `python run_benchmark.py --mini`  
   → SQL 1개 × 기본 3모델.

6. **전체 벤치마크**  
   `python run_benchmark.py`  
   → SQL 7개 × 기본 3모델 = 21회.  
   - 상세 항목: `python run_benchmark.py --detail`  
   - 모델 일부만: `python run_benchmark.py --models gemma3 qwen2.5-coder`  
   - Few-shot 개수: `--examples 6` (기본 6)

**한 번에 끝까지 (Windows)**  
`run_full_pipeline.cmd` 더블클릭 또는 프로젝트 루트에서 실행.  
PowerShell 스크립트는 막히면:  
`powershell -ExecutionPolicy Bypass -File .\run_full_pipeline.ps1`

---

## 출력 예시 및 결과 해석

### 진행 로그 (매 조합 1줄)

```
벤치마크 시작: 3개 모델 × 7개 SQL = 21개 조합

[01/21] gemma3 ← usp_get_books_storebook ... 총점 78% | 문법(O) 패턴(O) 논리(O) 정답(X) 스타일(O)
```

- **총점**: 아래 **「평가 기준」** 절의 가중 평균.
- **문법~스타일 O/X**: 각 하위 검사의 pass 여부 (정답·스타일은 임계값이 있음).

모델 호출 실패 시 같은 줄에 `ERROR: …` 로 끝나고 총점은 0에 가깝게 잡힙니다.

### 요약 표 (`print_table`)

```
프로시저                          gemma3           glm-4-flash      qwen2.5-coder
================================================================================
usp_get_books_storebook           78% [O] (25s)    76% [O] (32s)    74% [X] (22s)
...
----------------------------------------------------------------
평균                              77%              75%              73%
================================================================================
```

- **퍼센트**: 위와 같은 **종합 총점** 평균이 아니라, 해당 칸의 **`total_score`** (0~1을 퍼센트로 표시).
- **`[O]` / `[X]`**: **문법·패턴·논리** 세 가지만 모두 통과하면 `[O]`.  
  정답 유사도나 스타일이 낮아도 세 가지가 통과하면 `[O]`일 수 있으니, **총점과 함께** 봐야 합니다.

### 승자 블록

모델별 **평균 총점**으로 막대 그래프(텍스트)와 승자 한 줄. 동점이면 구현상 먼저 잡히는 모델이 승자로 표시될 수 있습니다.

### `--detail`

각 `(프로시저, 모델)`마다 문법·패턴·논리·**정답**·**스타일** 이유 문자열과 **엄격통과**(5종 모두 pass), 다시 한 번 총점·요약이 출력됩니다.

### JSON (`results/benchmark_YYYYMMDD_HHMMSS.json`)

- 타임스탬프·`results` 배열.
- 각 원소: `procedure`, `model`, `elapsed`, `eval`(전체 지표), `code_length` 등.
- 재현·스프레드시트·추가 시각화에 사용.

---

## 평가 기준 (5지표 및 가중치)

| 지표 | 가중치 | 내용 |
|------|--------|------|
| 문법 | 10% | `ast.parse` 성공, 최상위 `def` 최소 1개. |
| 패턴 | 15% | 문자열 수준: `ProcedureResult`, `try`, `get_db_cursor` 등 (Few-shot과 맞춘 최소 관례). |
| 논리 | 30% | 고정 Mock 커서로 서브프로세스 실행 후 `success` / `result_id` 등이 `EXPECTED_BY_PROCEDURE`와 맞는지. 인자는 휴리스틱으로 채워 **참 구현과 어긋날 수 있음**. |
| 정답 유사도 | 25% | `procedures/*.py`에 매핑된 **정답 함수**와 모델 출력 **첫 함수**의 정규화 라인 유사도 + AST dump 유사도 혼합. 동작이 맞아도 표현 차이로 점수가 낮을 수 있어 비중을 완화. |
| 스타일 루브릭 | 20% | `cursor.execute`의 `?`와 인자 개수, 위험 패턴 문자열, `get_db_cursor` 등 Comparator류 체크. |

**`all_pass`**: 문법·패턴·논리만 모두 pass.  
**`all_pass_strict`**: 위 5개 모두 pass (정답·스타일 임계값 포함).

한계: 정답과 **다르지만 동등하게 맞는** 구현은 유사도가 깎일 수 있음. Mock 논리는 완전한 의미 검증이 아님.

---

## Few-shot 구성

- **`EXAMPLES`** (기본 6개): SELECT / INSERT / UPDATE / DELETE, 2단계 트랜잭션 삭제, varchar PK INSERT 등 **SQL + 정답 Python** 쌍. 프롬프트에 그대로 포함됩니다.
- **`TEST_TARGETS`** (7개): **예시에는 넣지 않고**, 모델이 실제로 변환해야 하는 T-SQL만 가진 항목들. 벤치마크는 이 7개를 순회합니다.
- 예시 개수 변경: `python run_benchmark.py --examples 2` 처럼 CLI로 조절 (프롬프트 길이·난이도 트레이드오프).

자세한 이름·SQL 본문은 `fewshot/examples.py`를 열어보면 됩니다.

---

## 새 프로시저를 벤치에 넣으려면

1. `fewshot/examples.py`의 **`TEST_TARGETS`**에 `name`, `category`, `sql` 추가.
2. `evaluation/checker.py`의 **`EXPECTED_BY_PROCEDURE`**에 Mock 논리 검사용 기대값 추가.
3. `evaluation/gold_similarity.py`의 **`PROCEDURE_GOLD`**에 `(파일, 함수명)` 매핑 추가.
4. (선택) 정답 구현을 `procedures/` 적절한 파일에 추가.
5. `python run_benchmark.py` 재실행.

---

## 문제 해결 메모

- **PowerShell에서 `.ps1` 실행 거부**: `run_full_pipeline.cmd` 사용 또는 `powershell -ExecutionPolicy Bypass -File .\run_full_pipeline.ps1`.
- **Ollama 404 / 모델 없음**: `setup_ollama_models.py`, `OLLAMA_MODEL_*`, `MODEL_CONFIG`의 태그를 `ollama list`와 일치시키기.
- **정답 유사도가 낮은데 동작은 맞아 보임**: 다른 함수명·다른 분기 구조면 정상적으로 점수가 낮을 수 있음. 필요 시 가중치나 `PROCEDURE_GOLD` 매핑을 조정.

---

## 라이선스·저장소

원격 저장소 주소는 Git `origin` 설정을 따릅니다. (예: `https://github.com/eunbijoel/SQL--Python.git`)
