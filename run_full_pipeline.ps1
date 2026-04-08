# BookStore 벤치마크 — 어제와 같은 전체 흐름 (Windows PowerShell)
# 실행이 막히면(ExecutionPolicy): 아래 중 하나
#   powershell -ExecutionPolicy Bypass -File .\run_full_pipeline.ps1
#   또는 run_full_pipeline.cmd 더블클릭 / cmd에서 실행
# 사용: 프로젝트 루트에서  .\run_full_pipeline.ps1
# 원격 GPU/Ollama(SSH 터널 등)면 아래 주석 해제:
#   $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:PYTHONIOENCODING = "utf-8"

Write-Host "== 1) pip install ==" -ForegroundColor Cyan
py -3 -m pip install -r requirements.txt -q

Write-Host "`n== 2) 로컬 테스트 (DB/Ollama 불필요) ==" -ForegroundColor Cyan
py -3 tests\test_fewshot_and_evaluation.py

Write-Host "`n== 3) Ollama 모델 vs 벤치마크 이름 ==" -ForegroundColor Cyan
py -3 setup_ollama_models.py

Write-Host "`n== 4) run_benchmark --check-ollama ==" -ForegroundColor Cyan
py -3 run_benchmark.py --check-ollama

Write-Host "`n== 5) 전체 벤치마크 (7 SQL x 3 모델) — 시간 오래 걸림 ==" -ForegroundColor Cyan
py -3 run_benchmark.py

Write-Host "`n끝." -ForegroundColor Green
