.PHONY: test-setup test test-unit test-integration test-file test-cov test-nitra db-start db-stop db-reset

COMPOSE = docker compose -f docker-compose.test.yml

## First-time setup: start Docker and load the database
test-setup:
	chmod +x scripts/setup-test-db.sh
	./scripts/setup-test-db.sh

## Run all tests
test:
	ENV=test python -m pytest

## Run only unit tests (no DB required)
test-unit:
	ENV=test python -m pytest tests/unit/ -v

## Run only integration tests (requires DB)
test-integration:
	ENV=test python -m pytest tests/integration/ -v

## Run a specific test file (usage: make test-file FILE=tests/integration/test_drug.py)
test-file:
	ENV=test python -m pytest $(FILE) -v

## Run tests with coverage report
test-cov:
	ENV=test python -m pytest --cov=. --cov-report=html

## Run nutritional tests against nitra_db (docker-compose.nitra.yml must be up)
test-nitra:
	DB_HOST=localhost DB_NAME=noharm DB_USER=postgres DB_PASSWORD="" ENV=test python -m pytest \
		tests/unit/ \
		tests/integration/test_nutritional_d7.py \
		tests/integration/test_nutritional_glim.py \
		tests/integration/test_nutritional_patients.py -v

## Start the database container (data preserved)
db-start:
	$(COMPOSE) start

## Stop the database container (data preserved)
db-stop:
	$(COMPOSE) stop

## Full reset: destroy volume and reload from scratch
db-reset:
	$(COMPOSE) down -v
	./scripts/setup-test-db.sh
