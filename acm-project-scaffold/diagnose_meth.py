# Emplacement : diagnose_meth.py (racine — exécuter chez toi)
"""Diagnostic ciblé sur ._meth et .unwrap() des wrappers CrewAI Flow.

Le diagnostic précédent a montré que les wrappers n'ont QUE _instance, _meth() et
unwrap(). Les triggers/paths sont donc probablement des attributs attachés à la
MÉTHODE elle-même (._meth) par les décorateurs @listen/@router. Ce script
inspecte le contenu de ._meth et du résultat de .unwrap().

Lance : PYTHONPATH=. python diagnose_meth.py
"""
from scenarios.native_workflows import build_native_crewai_flow


def dump_callable_attrs(label, fn):
    print(f"\n  --- {label} : {getattr(fn, '__name__', fn)!r} ({type(fn).__name__}) ---")
    for attr in sorted(dir(fn)):
        # On veut TOUT sauf les dunders Python purement standard.
        if attr in ("__class__", "__delattr__", "__dir__", "__doc__", "__eq__",
                    "__format__", "__ge__", "__getattribute__", "__gt__", "__hash__",
                    "__init__", "__init_subclass__", "__le__", "__lt__", "__ne__",
                    "__new__", "__reduce__", "__reduce_ex__", "__repr__", "__setattr__",
                    "__sizeof__", "__str__", "__subclasshook__", "__call__",
                    "__globals__", "__builtins__", "__code__", "__closure__"):
            continue
        try:
            val = getattr(fn, attr)
        except Exception as e:
            print(f"    .{attr} -> <err {type(e).__name__}>")
            continue
        if callable(val) and not isinstance(val, (list, tuple, set, dict, str)):
            continue
        r = repr(val)
        if len(r) > 250:
            r = r[:250] + "..."
        print(f"    .{attr} = {r}")


def main():
    flow = build_native_crewai_flow()
    methods = getattr(flow, "_methods", {})
    for name in ("route_request", "run_research_crew", "finish_from_research",
                 "begin", "run_direct_task"):
        w = methods.get(name)
        if w is None:
            continue
        print(f"\n{'='*60}\n{name} → {type(w).__name__}")

        # 1. Le _meth (méthode liée sous-jacente).
        meth = getattr(w, "_meth", None)
        if meth is not None:
            dump_callable_attrs("_meth", meth)
            # __func__ si c'est une méthode liée.
            func = getattr(meth, "__func__", None)
            if func is not None:
                dump_callable_attrs("_meth.__func__", func)

        # 2. Le résultat de unwrap().
        try:
            unwrapped = w.unwrap()
            dump_callable_attrs("unwrap()", unwrapped)
            func = getattr(unwrapped, "__func__", None)
            if func is not None:
                dump_callable_attrs("unwrap().__func__", func)
        except Exception as e:
            print(f"  unwrap() -> <err {type(e).__name__}: {e}>")


if __name__ == "__main__":
    main()
