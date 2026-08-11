# Ajout pyproject.toml pour le bloc 2 (oracle figé)

Le loader d'oracle utilise `pyyaml`. Le cœur ACM reste sans nouvelle dépendance.
Ajouter `pyyaml` dans un extra d'expérience, pas dans `dependencies` :

```toml
[project.optional-dependencies]
# ... extras existants ...
impact-experiment = ["pyyaml>=6"]
# et l'inclure dans l'agrégat "all" :
all = [
    "pytest>=8", "hypothesis>=6",
    "langgraph>=1", "langchain-core>=1",
    "crewai>=1",
    "langchain-openai>=1",
    "pyyaml>=6",
]
```

`harness/impact_oracle.py` importe `yaml` en LOCAL (dans les fonctions), donc
l'absence de pyyaml n'empêche pas d'importer le module — seul le chargement
d'un fichier échoue proprement si l'extra n'est pas installé.
