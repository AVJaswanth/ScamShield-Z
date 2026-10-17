@echo off
REM ScamShield Z: Windows Batch Runner for Make Targets
REM Allows executing `make all`, `make test`, etc. natively on Windows

SET TARGET=%1
IF "%TARGET%"=="" SET TARGET=all

IF "%TARGET%"=="setup" GOTO target_setup
IF "%TARGET%"=="data" GOTO target_data
IF "%TARGET%"=="train" GOTO target_train
IF "%TARGET%"=="replay" GOTO target_replay
IF "%TARGET%"=="fairness" GOTO target_fairness
IF "%TARGET%"=="run" GOTO target_run
IF "%TARGET%"=="test" GOTO target_test
IF "%TARGET%"=="e2e" GOTO target_e2e
IF "%TARGET%"=="all" GOTO target_all

echo Unknown target: %TARGET%
echo Available targets: setup, data, train, replay, fairness, run, test, e2e, all
exit /b 1

:target_setup
python -m pip install -r requirements.txt
python -m playwright install chromium
goto :eof

:target_data
python src/generate_data.py
goto :eof

:target_train
python src/train.py
goto :eof

:target_replay
python src/replay.py
goto :eof

:target_fairness
python src/fairness.py
goto :eof

:target_run
python -m uvicorn src.app:app --host 127.0.0.1 --port 8000
goto :eof

:target_test
python -m pytest tests/test_features.py tests/test_model.py tests/test_policy.py tests/test_explain.py tests/test_api.py -v
goto :eof

:target_e2e
python tests/e2e_ui.py
goto :eof

:target_all
echo [1/6] Generating synthetic payment stream...
python src/generate_data.py || exit /b 1
echo [2/6] Training baseline and LightGBM model and verifying ONNX parity...
python src/train.py || exit /b 1
echo [3/6] Running 100k event replay latency benchmark...
python src/replay.py || exit /b 1
echo [4/6] Running fairness and demographic audit...
python src/fairness.py || exit /b 1
echo [5/6] Running unit and API integration tests...
python -m pytest tests/test_features.py tests/test_model.py tests/test_policy.py tests/test_explain.py tests/test_api.py -v || exit /b 1
echo [6/6] Running Playwright E2E UI verification suite...
python tests/e2e_ui.py || exit /b 1
echo All stages completed successfully!
goto :eof
