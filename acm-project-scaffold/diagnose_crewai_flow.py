# Emplacement : diagnose_crewai_flow.py (racine du projet — à exécuter chez toi)
"""Diagnostic d'introspection d'un CrewAI Flow — À EXÉCUTER AVEC crewai installé.

Affiche ce que le vrai objet Flow expose réellement, pour ajuster l'extracteur
aux noms d'attributs de TA version de CrewAI. Lance :

    PYTHONPATH=. python diagnose_crewai_flow.py
"""
from scenarios.native_workflows import build_native_crewai_flow


def main():
    flow = build_native_crewai_flow()
    print("=== Type ===")
    print(type(flow).__mro__[:3])

    print("\n=== Attributs '_...' liés à la structure du Flow ===")
    for name in dir(flow):
        if any(k in name.lower() for k in
               ("start", "router", "listen", "trigger", "path", "method", "state")):
            try:
                val = getattr(flow, name)
                if not callable(val):
                    print(f"  {name} = {val!r}")
            except Exception as e:
                print(f"  {name} -> <err {e}>")

    print("\n=== Marqueurs attachés aux méthodes décorées ===")
    for mname in ("begin", "route_request", "run_research_crew",
                  "run_direct_task", "finish_from_research", "finish_from_direct"):
        method = getattr(flow, mname, None)
        if method is None:
            continue
        markers = {a: getattr(method, a, None) for a in dir(method)
                   if a.startswith("__") and any(
                       k in a for k in ("start", "router", "trigger",
                                        "listen", "condition", "path"))}
        markers = {k: v for k, v in markers.items() if v is not None}
        print(f"  {mname}: {markers}")

    print("\n=== Attributs de classe possiblement utiles ===")
    for name in ("_start_methods", "_routers", "_listeners", "_router_paths",
                 "_methods", "_method_execution_order"):
        val = getattr(flow, name, "<absent>")
        print(f"  {name} = {val!r}")


if __name__ == "__main__":
    main()


def inspect_wrappers():
    """Inspecte le contenu des wrappers de flow._methods (StartMethod, etc.).

    Ajouté suite au 1er diagnostic : on sait que la structure est dans _methods,
    il faut maintenant les noms d'attributs portant triggers et paths.
    """
    flow = build_native_crewai_flow()
    methods = getattr(flow, "_methods", {})
    print("\n=== CONTENU des wrappers flow._methods ===")
    for name, wrapper in methods.items():
        print(f"\n  {name} → {type(wrapper).__name__}")
        for attr in dir(wrapper):
            if attr.startswith("__"):
                continue
            try:
                val = getattr(wrapper, attr)
                if callable(val):
                    continue
                print(f"      .{attr} = {val!r}")
            except Exception as e:
                print(f"      .{attr} -> <err {e}>")


if __name__ == "__main__":
    main()
    inspect_wrappers()
