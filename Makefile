# ScamShield Z: Real-Time Scam Payment Detection Demo
# IBM Z Datathon 2026: Real-Time AI for Critical Decisions

.PHONY: setup data train run test e2e all clean

PYTHON ?= python

setup:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m playwright install chromium

data:
	$(PYTHON) src/generate_data.py

train:
	$(PYTHON) src/train.py

replay:
	$(PYTHON) src/replay.py

fairness:
	$(PYTHON) src/fairness.py

run:
	$(PYTHON) -m uvicorn src.app:app --host 127.0.0.1 --port 8000

test:
	$(PYTHON) -m pytest tests/test_features.py tests/test_model.py tests/test_policy.py tests/test_explain.py tests/test_api.py -v

e2e:
	$(PYTHON) tests/e2e_ui.py

all: data train replay fairness test e2e
