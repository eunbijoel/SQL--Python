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
│   └── model_runner.py         # Ollama(Gemma/Qwen) + GLM API 호출
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

## 2단계: API 키 (선택)

**Ollama만 쓰는 비교**(`--models gemma3 qwen2.5-coder` 등)에는 **별도 API 키나 Hugging Face 토큰이 필요 없습니다.** 로컬 `ollama serve`와 설치된 모델만 있으면 됩니다.

`ollama list`에 나오는 이름이 `gemma3:12b`처럼 태그까지 붙어 있다면, 아래 환경변수로 벤치마크에 넘길 이름을 고정할 수 있습니다 (tsql2py의 `config.yaml` `model_name`과 같은 역할).

```bash
# 예: PowerShell
$env:OLLAMA_MODEL_GEMMA3 = "gemma3:12b"
$env:OLLAMA_MODEL_QWEN2_5_CODER = "qwen2.5-coder:14b"
```

**GLM(클라우드)까지 3-way 비교**할 때만 Zhipu 키가 필요합니다.

```bash
# .env 또는 환경변수
# GLM_API_KEY=your_key_here
# API 키 발급: https://open.bigmodel.cn (무료 티어 있음)
```

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

## 5단계: Ollama 상태 확인

```bash
ollama serve  # 별도 터미널에서 실행

python run_benchmark.py --check-ollama
# 예상 출력:
# Ollama 실행 중 (설치된 모델: ['gemma3', 'qwen2.5-coder'])
# O gemma3
# O qwen2.5-coder
```

## 6단계: 빠른 미니 테스트 (SQL 1개)

```bash
python run_benchmark.py --mini
# SQL 1개 × 3모델 = 3번 변환 (GLM 키 없으면 glm 단계는 실패할 수 있음)

python run_benchmark.py --mini --models gemma3 qwen2.5-coder
# Ollama만: 키 없이 2회 변환
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

| 검사 | 가중치 | 내용 |
|---|---|---|
| 문법 검사 | 30% | `ast.parse()` 통과, `def` 함수 존재 |
| 패턴 검사 | 30% | `ProcedureResult` / `get_db_cursor` / `try-except` |
| 논리 검사 | 40% | Mock DB로 실행 → `success`, `result_id` 반환값 확인 |

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
