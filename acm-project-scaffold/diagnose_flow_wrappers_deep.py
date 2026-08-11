# Emplacement : diagnose_flow_wrappers_deep.py (racine — exécuter chez toi)
"""Diagnostic EXHAUSTIF du contenu des wrappers CrewAI Flow.

Le diagnostic précédent a montré que les ListenMethod n'exposent que ._instance
en attribut public. Les triggers/paths sont donc ailleurs : attributs PRIVÉS du
wrapper, ou sur la FONCTION décorée qu'il enveloppe. Ce script explore les deux.

Lance : PYTHONPATH=. python diagnose_flow_wrappers_deep.py
"""
from scenarios.native_workflows import build_native_crewai_flow


def dump(label, obj, skip_instance=True):
    print(f"\n  --- {label} : {type(obj).__name__} ---")
    for attr in sorted(dir(obj)):
        if attr.startswith("__"):
            continue
        if skip_instance and attr in ("instance", "_instance"):
            print(f"    .{attr} = <ResearchFlow instance, masqué>")
            continue
        try:
            val = getattr(obj, attr)
        except Exception as e:
            print(f"    .{attr} -> <err {type(e).__name__}>")
            continue
        if callable(val):
            # Pour une fonction/méthode, montrer ses attributs porteurs de triggers.
            fn_attrs = {a: getattr(val, a, None) for a in dir(val)
                        if not a.startswith("__") and not callable(getattr(val, a, None))}
            interesting = {k: v for k, v in fn_attrs.items()
                           if any(s in k.lower() for s in
                                  ("trigger", "listen", "path", "router", "condition",
                                   "method", "name"))}
            print(f"    .{attr}() [callable] interesting_attrs={interesting}")
        else:
            r = repr(val)
            if len(r) > 300:
                r = r[:300] + "..."
            print(f"    .{attr} = {r}")


def main():
    flow = build_native_crewai_flow()
    methods = getattr(flow, "_methods", {})
    for name in ("route_request", "run_research_crew", "finish_from_research"):
        w = methods.get(name)
        if w is None:
            print(f"\n{'='*60}\n{name} : ABSENT de _methods")
            continue
        print(f"\n{'='*60}\n{name} → wrapper {type(w).__name__}")
        dump("wrapper (attrs privés inclus)", w)

        # La fonction décorée que le wrapper enveloppe.
        for fn_attr in ("__wrapped__", "func", "method", "fn", "_func", "_method",
                        "callback", "_callback"):
            fn = getattr(w, fn_attr, None)
            if fn is not None and callable(fn):
                print(f"\n  >>> fonction décorée via .{fn_attr} : {getattr(fn, '__name__', fn)}")
                trig = {a: getattr(fn, a, None) for a in dir(fn)
                        if not a.startswith("__")
                        and any(s in a.lower() for s in
                                ("trigger", "listen", "path", "router", "condition"))}
                print(f"      attrs porteurs de triggers/paths : {trig}")


if __name__ == "__main__":
    main()
