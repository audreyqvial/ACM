# Placement des livrables dans l'arbre projet ACM

Rappel : `/mnt/user-data/outputs/` reproduit déjà l'arborescence cible. Il
suffit de copier chaque dossier vers la racine du projet
`~/Audrey/Consulting/Agentic_Configuration_Management/acm-project-scaffold/`
en respectant la structure ci-dessous.

## Nouveau sous-package normatif (cœur, sans dépendance framework)
    acm/impact/__init__.py
    acm/impact/metrics.py          # reach, size, depth, ratio, weight
    acm/impact/comparison.py       # precision/recall vs ensemble fourni
    acm/impact/inspection.py       # réduction de coût, variante stricte

## Harness d'expérience (jamais importé par acm/)
    harness/impact_oracle.py            # schéma + loader d'oracle figé
    harness/inspection_record.py        # loader des coûts d'inspection (séparé)
    harness/oracle_provenance.py        # digest canonique/brut, manifest, provenance
    harness/engine_prediction.py        # P_f(c) depuis le vrai PropagationReport
    harness/reach_consistency.py        # test P_f(c) ⊆ reach(root)
    harness/baseline_reassessment.py    # signal dérivé baseline (hors P_f(c))
    harness/impact_experiment_runner.py # orchestrateur matrice framework × change

## Fixtures et artefacts figés
    scenarios/impact_experiment/native_equivalent.py     # 3 builders build_impact_*
    scenarios/impact_experiment/oracle/*.yaml            # 9 oracles figés (M_f(c))
    scenarios/impact_experiment/inspection/*.yaml        # 9 coûts d'inspection
    scenarios/impact_experiment/oracle_manifest.json     # manifest des digests

## Rapport
    reports/generate_impact_experiment_report.py

## Tests
    tests/test_impact_metrics.py
    tests/test_impact_comparison.py
    tests/test_impact_inspection.py
    tests/test_impact_oracle.py
    tests/impact_fixtures.py                  # graphes jouets (bloc 1)
    tests/test_impact_experiment_block3.py
    tests/test_impact_experiment_block4.py

## __init__.py à prévoir (packages Python)
Selon ta convention "en-tête indiquant le chemin", ajoute si absents :
    harness/__init__.py
    reports/__init__.py
    scenarios/__init__.py
    scenarios/impact_experiment/__init__.py

## pyproject.toml
Voir pyproject_extra_note.md : ajouter l'extra `impact-experiment = ["pyyaml>=6"]`
et l'inclure dans l'agrégat `all`. Ne PAS toucher `dependencies` (cœur = pydantic).

## Convention de test (rappel)
    PYTHONPATH=. python -m pytest tests/ -q -p no:cacheprovider

## Note sur les fichiers manquants côté ton interface
Les 9 oracles et 9 inspections sont bien présents ici (3 frameworks × 3 classes).
Si seuls les langgraph_*.yaml apparaissaient, c'est un artefact d'affichage :
seuls les échantillons langgraph avaient été présentés explicitement bloc par bloc.
