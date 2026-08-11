"""P0-10 — le cœur ACM doit s'importer et fonctionner sans les extras.

Simule l'absence de langgraph / langchain / crewai et vérifie que le cœur
(modèles, propagation, invariants, évaluation runtime) reste pleinement
utilisable. Les adaptateurs sont les seuls à dépendre des frameworks, et leurs
tests sont protégés par pytest.importorskip.
"""
from __future__ import annotations

import builtins

import pytest


def test_core_imports_and_runs_without_extras():
    """Bloque les imports de frameworks puis exerce le cœur de bout en bout."""
    blocked_roots = {"langgraph", "langchain_core", "langchain_openai", "crewai"}
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in blocked_roots:
            raise ImportError(f"{name} bloqué (simulation sans extra)")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded
    try:
        # Import du cœur + exécution d'une propagation minimale.
        import importlib
        import acm
        importlib.reload(acm)

        from acm import (
            ACIRef,
            ACIRevision,
            ConfigurationGraph,
            PropagationContext,
            propagate,
        )
        from acm.models.aci import AssurancePolicy, DeclaredStatus
        from acm.models.enums import ACIType, LifecycleState, QualityState, AssuranceState

        rev = ACIRevision(
            ref=ACIRef(id="aci:x", revision_id="01J", digest="sha256:x"),
            aci_type=ACIType.AGENT,
            declared=DeclaredStatus(
                lifecycle_state=LifecycleState.VALIDATED,
                quality_state=QualityState.OK,
                assurance_state=AssuranceState.ASSESSED,
            ),
            assurance_policy=AssurancePolicy(required_assurance_dimensions=[]),
        )
        graph = ConfigurationGraph.build([rev], [])
        report = propagate(graph, [], PropagationContext())
        assert report.converged is True
        assert len(report.items) == 1

        # L'évaluation runtime (cœur) doit aussi marcher sans frameworks.
        from acm import evaluate_runtime_instance, RuntimeSignal, ResolvedConfig, Traceability
        sig = RuntimeSignal(
            instance_id="rt:x",
            definition_ref=ACIRef(id="aci:template:x", revision_id="01J", digest="d"),
            resolved_config=ResolvedConfig(),
            traceability=Traceability(),
        )
        verdict = evaluate_runtime_instance(sig)
        assert verdict is not None
    finally:
        builtins.__import__ = real_import


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
