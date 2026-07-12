install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install .[all]

test:
	python3 -m pytest

coverage:
	python3 -m pytest --cov=pyworkflow --cov-report=html

format:
	python3 -m black pyworkflow/ tests/

lint:
	python3 -m flake8 pyworkflow/

typecheck:
	python3 -m mypy pyworkflow/

release:
	python3 -m build
	python3 -m twine check dist/*
