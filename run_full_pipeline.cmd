@echo off
REM 실행 정책 없이 동일 파이프라인 (run_full_pipeline.ps1 과 같음)
cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
REM 원격 Ollama면 아래 주석 제거
REM set OLLAMA_BASE_URL=http://127.0.0.1:11434

echo == 1) pip install ==
py -3 -m pip install -r requirements.txt -q
if errorlevel 1 exit /b 1

echo.
echo == 2) 로컬 테스트 ==
py -3 tests\test_fewshot_and_evaluation.py
if errorlevel 1 exit /b 1

echo.
echo == 3) Ollama 모델 확인 ==
py -3 setup_ollama_models.py

echo.
echo == 4) check-ollama ==
py -3 run_benchmark.py --check-ollama

echo.
echo == 5) 전체 벤치마크 (시간 오래 걸림) ==
py -3 run_benchmark.py

echo.
echo 끝.
