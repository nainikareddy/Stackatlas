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
