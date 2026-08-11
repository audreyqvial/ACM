"""Tests du digest de config résolue (§3.5, I2).

Propriétés garanties :
  - déterminisme (même config -> même digest) ;
  - indépendance à l'ordre des tools ;
  - sensibilité aux overrides et aux refs ;
  - indépendance vis-à-vis de la traçabilité/permissions (contexte, pas config) ;
  - égalité inter-adaptateurs (même spec -> même digest côté stub et LangGraph).
"""
from __future__ import annotations

from acm import (
    ResolvedConfig,
    digest_of_resolved_config,
    resolved_config_from_spec,
)
from acm.models.refs import ACIRef
from acm.runtime.spec import AgentSpec
from adapters.langgraph_adapter import LangGraphAdapter

P = ACIRef(id="aci:prompt:planner", revision_id="01JR1")
M = ACIRef(id="aci:model:gpt-5.4", revision_id="01JM1")
T1 = ACIRef(id="aci:tool:web-search", revision_id="01JR1")
T2 = ACIRef(id="aci:tool:calculator", revision_id="01JR1")


def test_digest_is_deterministic():
    c = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T1, T2])
    assert digest_of_resolved_config(c) == digest_of_resolved_config(c)


def test_digest_ignores_tool_order():
    c1 = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T1, T2])
    c2 = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T2, T1])
    assert digest_of_resolved_config(c1) == digest_of_resolved_config(c2)


def test_digest_sensitive_to_override():
    c1 = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T1])
    c2 = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T1], prompt_overridden=True)
    assert digest_of_resolved_config(c1) != digest_of_resolved_config(c2)


def test_digest_sensitive_to_model_ref():
    c1 = ResolvedConfig(prompt_ref=P, model_ref=M, tool_refs=[T1])
    other_model = ACIRef(id="aci:model:other", revision_id="01JM2")
    c2 = ResolvedConfig(prompt_ref=P, model_ref=other_model, tool_refs=[T1])
    assert digest_of_resolved_config(c1) != digest_of_resolved_config(c2)


def test_digest_has_sha256_prefix():
    c = ResolvedConfig(prompt_ref=P, model_ref=M)
    assert digest_of_resolved_config(c).startswith("sha256:")


def test_langgraph_signal_carries_digest():
    spec = AgentSpec(
        instance_id="rt:x",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        prompt_ref=P, model_ref=M, model_name="gpt-5.4",
    )
    sig = LangGraphAdapter().create_instance({"spec": spec})
    assert sig.resolved_config_digest is not None
    # correspond au calcul direct du cœur
    assert sig.resolved_config_digest == digest_of_resolved_config(
        resolved_config_from_spec(spec)
    )


def test_same_spec_same_digest_across_signal_and_core():
    """Le digest ne dépend que de la config, pas du chemin de production."""
    spec = AgentSpec(
        instance_id="rt:y",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        factory_ref=ACIRef(id="aci:factory:f1", revision_id="01JF1"),
        prompt_ref=P, model_ref=M, tool_refs=[T1, T2],
        tool_names=["web_search", "calculator"], model_name="gpt-5.4",
    )
    lg_digest = LangGraphAdapter().create_instance({"spec": spec}).resolved_config_digest
    core_digest = digest_of_resolved_config(resolved_config_from_spec(spec))
    assert lg_digest == core_digest


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
