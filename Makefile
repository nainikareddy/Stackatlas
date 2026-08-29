.PHONY: install dev eval test tasks pipeline clean

install:            ## install python deps
	pip install -r requirements-dev.txt

dev:                ## run the dashboard (http://localhost:3000)
	npm install && npm run dev

eval:               ## score the shipped demo catalog against gold labels
	python -m evals.run_eval

test:               ## run the full test + self-verification suite
	python -m pytest -q

tasks:              ## (re)generate the RL task dataset -> evals/tasks.jsonl
	python -m evals.build_tasks

pipeline:           ## run introspection + docgen against $(DSN)
	python pipeline/introspect.py "$(DSN)" > catalog_raw.json
	python pipeline/docgen.py catalog_raw.json > mcp_server/catalog.json

clean:
	rm -rf .next node_modules __pycache__ */__pycache__ .pytest_cache catalog_raw.json

# --- Reproducible Postgres (hackathon) ---------------------------------------
DSN ?= postgresql://stackatlas:stackatlas@localhost:5433/vibeshop

.PHONY: db-up db-wait db-down db-reset

# start dockerized Postgres + seed vibeshop, then block until ready
db-up:
	docker compose up -d
	$(MAKE) db-wait

# block until Postgres accepts connections
db-wait:
	@until docker compose exec -T db pg_isready -U stackatlas -d vibeshop >/dev/null 2>&1; do sleep 1; done; echo "vibeshop ready on localhost:5433"

# stop and delete the database (fresh next time)
db-down:
	docker compose down -v

# rebuild the database from seed
db-reset: db-down db-up

