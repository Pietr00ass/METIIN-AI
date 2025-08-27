.PHONY: lint
lint:
	isort .
	black .
	flake8
