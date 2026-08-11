#!/usr/bin/env python3
"""
Générateur de structure de dossier pour README.md
Usage: python generate_tree.py [chemin_du_dossier]
"""

import os
import sys
from pathlib import Path


def should_ignore(name: str) -> bool:
    """Détermine si un fichier ou dossier doit être ignoré."""
    return name.startswith(".") or name == "__pycache__"


def generate_tree(directory: Path, prefix: str = "", is_last: bool = True) -> str:
    """Génère la structure arborescente en markdown."""
    lines = []

    # Nom du dossier/fichier courant
    connector = "└── " if is_last else "├── "
    lines.append(f"{prefix}{connector}{directory.name}")

    if directory.is_dir():
        try:
            entries = sorted(
                [e for e in directory.iterdir() if not should_ignore(e.name)],
                key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            return "
".join(lines)

        for i, entry in enumerate(entries):
            is_last_entry = i == len(entries) - 1
            extension = "    " if is_last else "│   "
            subtree = generate_tree(entry, prefix + extension, is_last_entry)
            lines.append(subtree)

    return "
".join(lines)


def create_readme(directory: Path, output_path: Path) -> None:
    """Crée le README.md avec la structure du dossier."""
    tree = generate_tree(directory, is_last=True)

    readme_content = f"""# {directory.name}

## Structure du projet

```
{tree}
```

---
*Structure générée automatiquement.*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"✅ README.md généré avec succès : {output_path.resolve()}")


def main():
    # Récupère le chemin du dossier (ou utilise le dossier courant)
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).resolve()
    else:
        target_dir = Path.cwd()

    if not target_dir.exists():
        print(f"❌ Erreur : le dossier '{target_dir}' n'existe pas.")
        sys.exit(1)

    if not target_dir.is_dir():
        print(f"❌ Erreur : '{target_dir}' n'est pas un dossier.")
        sys.exit(1)

    # Le README.md est créé dans le dossier cible
    output_path = target_dir / "README.md"

    create_readme(target_dir, output_path)

    # Affiche un aperçu
    print("\n📋 Aperçu de la structure générée :")
    print("-" * 50)
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
        # Extrait juste la partie entre les backticks
        lines = content.split("\n")
        in_tree = False
        for line in lines:
            if "```" in line:
                in_tree = not in_tree
                if not in_tree:
                    break
                continue
            if in_tree:
                print(line)
    print("-" * 50)


if __name__ == "__main__":
    main()
