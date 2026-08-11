# ACM — Agentic Configuration Management (Reference v0.1)

Reference implementation of the **Lifecycle & State Propagation Model v0.1** and
evaluation harness for the experimental scenarios reported in the arXiv paper.

The repository contains four layers:

1. the **core** **`acm/`** — the normative model (Pydantic only), which represents
   an agentic system as a composite configuration of identifiable and versioned
   objects, and propagates quality / assurance / impact / eligibility;
2. the **adapters** **`adapters/`** **+ the port** **`ports/`** — project LangGraph, CrewAI
   and OpenAI Agent SDK into the common ACM semantics behind a record/replay boundary;
4. the **harness** **`harness/`** — executes declarative YAML fixtures
   (configuration + evidence + oracle) against the core and produces structured,
   reproducible reports;
5. the **scenarios** — historical case studies (`scenarios/scenario_*.py`) and
   S01..S27 evaluation fixtures (`scenarios/fixtures/*.yaml`).

---

```bash
pip install 'pydantic>=2' pyyaml pytest        # core + harness
# optional extras: pip install -e '.[langgraph,crewai]'

# Full test suite
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m pytest tests/ -q -p no:cacheprovider

# Harness only (evaluation fixtures)
PYTHONPATH=. python -m pytest tests/test_scenarios.py tests/test_transitions.py -v

# Standalone runner: executes scenarios/fixtures/*.yaml → JSON report (§4)
PYTHONPATH=. python run_evaluation.py --repeat 10 --out evaluation_report.json
```

`--repeat N` replays each scenario N times and verifies digest stability
(reproducibility).

```bash
# Generate the preservation report
PYTHONPATH=. python generate_preservation_report.py

# Generate the evaluation report
PYTHONPATH=. python generate_evaluation_report.py

# Generate the impact report
PYTHONPATH=. python generate_impact_report.py

# Inspect the contents of ._meth and .unwrap() — the two remaining CrewAI
# black boxes, for diagnostic purposes
PYTHONPATH=. python diagnose_meth.py

# Deep inspection of CrewAI flow wrappers
PYTHONPATH=. python diagnose_flow_wrappers_deep.py

# 1. Freeze the oracles, then generate the manifest from them
PYTHONPATH=. python -c "from harness.oracle_provenance import build_manifest, save_manifest; save_manifest(build_manifest('scenarios/impact_experiment/oracle'), 'scenarios/impact_experiment/oracle_manifest.json')"

# 2. Commit the oracles + manifest TOGETHER, in the same commit
git add scenarios/impact_experiment/oracle/ scenarios/impact_experiment/oracle_manifest.json
git commit -m "Freeze impact oracles + manifest (evidence chain)"

# 3. Run the experiment — both fields are populated automatically
PYTHONPATH=. python generate_impact_experiment_report.py \
    --oracle-dir scenarios/impact_experiment/oracle \
    --inspection-dir scenarios/impact_experiment/inspection \
    --manifest scenarios/impact_experiment/oracle_manifest.json \
    --out-dir docs
```

## Installation

Recommended: use a virtual environment (venv or conda), with Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
# or: conda create -n acm python=3.11 && conda activate acm
```

Install the core only (no framework dependency):

```bash
pip install -e .
```

Install with a specific framework:

```bash
pip install -e ".[langgraph]"          # LangGraph
pip install -e ".[crewai]"             # CrewAI
pip install -e ".[openai]"             # real OpenAI execution (gpt-5.4)
```

Install everything (frameworks + OpenAI execution + pytest):

```bash
pip install -e ".[all]"
```

## Tests

```bash
pytest tests/ -v
```
