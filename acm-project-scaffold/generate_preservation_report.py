# Emplacement : generate_preservation_report.py (racine du projet)
"""Génère l'Information Preservation Report des extractions natives (vague 1.b).

Exécute les extracteurs sur de vrais workflows LangGraph/CrewAI, compare au golden
oracle, et produit un rapport horodaté chiffrant la préservation d'information :
couvertures (nœuds, relations, branches, références), statuts de perte
(preserved / approximated / unsupported), éléments unresolved, stabilité du
digest.

C'est l'artefact qui étaie la revendication forte de portabilité :
« ACM normalise des workflows natifs existants vers une représentation
framework-indépendante », avec des chiffres reproductibles.

Sortie :
    docs/preservation_report_<horodatage>.md
    docs/preservation_report_<horodatage>.json
    docs/preservation_report_latest.{md,json}

Usage :
    python generate_preservation_report.py [--out-dir docs]

Nécessite les frameworks : `pip install -e '.[langgraph,crewai]'`. Sans eux, le
rapport est produit mais signale les frameworks manquants (aucune extraction).
"""
from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from harness.extraction_oracle import evaluate_extraction
from scenarios.workflow_golden import (
    golden_crewai,
    golden_crewai_flow,
    golden_crewai_flow_plus_crew,
    golden_langgraph,
    golden_openai_agent,
    golden_openai_agent_graph,
)


def _framework_available(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _run_langgraph_extraction() -> Optional[Dict]:
    """Extrait le workflow LangGraph natif et le compare au golden."""
    if not _framework_available("langgraph"):
        return None
    from adapters.langgraph_extractor import extract_langgraph
    from scenarios.native_workflows import (
        LANGGRAPH_METADATA,
        LANGGRAPH_STATE_KEYS,
        build_native_langgraph,
    )

    native = build_native_langgraph()
    # Extraction répétée pour vérifier la stabilité du digest.
    extracted = extract_langgraph(
        native, workflow_id="wf:research-pipeline",
        node_metadata=LANGGRAPH_METADATA, state_schema_keys=LANGGRAPH_STATE_KEYS,
    )
    extracted_again = extract_langgraph(
        native, workflow_id="wf:research-pipeline",
        node_metadata=LANGGRAPH_METADATA, state_schema_keys=LANGGRAPH_STATE_KEYS,
    )
    metrics = evaluate_extraction(golden_langgraph(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == extracted_again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _run_crewai_crew_extraction() -> Optional[Dict]:
    """CAS 1 — Crew-only : agents, tâches, contexte, outils, process.

    Compare extract_crew(Crew séquentiel) au golden Crew. Ne contient AUCUNE
    topologie de Flow — c'est le niveau d'abstraction « crew ».
    """
    if not _framework_available("crewai"):
        return None
    from adapters.crewai_extractor import extract_crew
    from scenarios.native_workflows import CREWAI_METADATA, build_native_crewai

    native = build_native_crewai()
    extracted = extract_crew(native, workflow_id="wf:research-pipeline",
                             agent_metadata=CREWAI_METADATA)
    again = extract_crew(native, workflow_id="wf:research-pipeline",
                         agent_metadata=CREWAI_METADATA)
    metrics = evaluate_extraction(golden_crewai(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _run_crewai_flow_only_extraction() -> Optional[Dict]:
    """CAS 2 — Flow-only : start, router, listeners, branches, état.

    Compare extract_flow(include_crew=False) au golden Flow. Contient la
    topologie du Flow SANS les composants internes du Crew — niveau « flow ».
    """
    if not _framework_available("crewai"):
        return None
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    extracted = extract_flow(
        flow, workflow_id="wf:research-flow",
        flow_metadata=CREWAI_FLOW_METADATA, flow_edges=CREWAI_FLOW_EDGES,
        include_crew=False,
    )
    again = extract_flow(
        flow, workflow_id="wf:research-flow",
        flow_metadata=CREWAI_FLOW_METADATA, flow_edges=CREWAI_FLOW_EDGES,
        include_crew=False,
    )
    metrics = evaluate_extraction(golden_crewai_flow(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _run_crewai_flow_plus_crew_extraction() -> Optional[Dict]:
    """CAS 3 — Flow+Crew : topologie du Flow ET composants du Crew fusionnés.

    Compare extract_flow(include_crew=True) au golden Flow+Crew. Superpose les
    deux niveaux d'abstraction : orchestration (Flow) et détail des tâches (Crew).
    """
    if not _framework_available("crewai"):
        return None
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, CREWAI_METADATA,
        build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    extracted = extract_flow(
        flow, workflow_id="wf:research-flow-full",
        flow_metadata=CREWAI_FLOW_METADATA, flow_edges=CREWAI_FLOW_EDGES,
        agent_metadata=CREWAI_METADATA, include_crew=True,
    )
    again = extract_flow(
        flow, workflow_id="wf:research-flow-full",
        flow_metadata=CREWAI_FLOW_METADATA, flow_edges=CREWAI_FLOW_EDGES,
        agent_metadata=CREWAI_METADATA, include_crew=True,
    )
    metrics = evaluate_extraction(golden_crewai_flow_plus_crew(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _run_openai_agent_extraction() -> Optional[Dict]:
    """CAS 1 — Agent seul : un `agents.Agent` isolé (mono-nœud).

    Compare extract_agent(Agent isolé) au golden Agent. Aucune topologie —
    c'est le niveau d'abstraction « agent », symétrique du Crew-only mono.
    """
    if not _framework_available("agents"):
        return None
    from adapters.openai_agents_extractor import extract_agent
    from scenarios.native_workflows import (
        OPENAI_AGENTS_METADATA, build_native_openai_agent,
    )

    native = build_native_openai_agent()
    extracted = extract_agent(native, workflow_id="wf:research-agent",
                              agent_metadata=OPENAI_AGENTS_METADATA)
    again = extract_agent(native, workflow_id="wf:research-agent",
                          agent_metadata=OPENAI_AGENTS_METADATA)
    metrics = evaluate_extraction(golden_openai_agent(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _run_openai_agent_graph_extraction() -> Optional[Dict]:
    """CAS 2 — Agent + handoffs : la fermeture transitive du graphe de délégation.

    Compare extract_agent_graph(Agent racine) au golden graphe. Les arêtes de
    handoff sont EXTRAITES (topologie introspectable sur les objets), à la
    différence du CrewAI Flow dont les arêtes sont déclarées — niveau « graphe ».
    """
    if not _framework_available("agents"):
        return None
    from adapters.openai_agents_extractor import extract_agent_graph
    from scenarios.native_workflows import (
        OPENAI_AGENTS_METADATA, build_native_openai_agent_graph,
    )

    root = build_native_openai_agent_graph()
    extracted = extract_agent_graph(root, workflow_id="wf:research-agent-graph",
                                    agent_metadata=OPENAI_AGENTS_METADATA)
    again = extract_agent_graph(root, workflow_id="wf:research-agent-graph",
                                agent_metadata=OPENAI_AGENTS_METADATA)
    metrics = evaluate_extraction(golden_openai_agent_graph(), extracted)
    payload = metrics.to_dict()
    payload["digest_stable"] = extracted.digest() == again.digest()
    payload["digest"] = extracted.digest()
    return payload


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _render_framework_section(name: str, data: Optional[Dict]) -> List[str]:
    lines: List[str] = [f"### {name}\n"]
    if data is None:
        lines.append(f"Framework `{name.lower()}` non installé — aucune extraction "
                     "exécutée dans cet environnement.\n")
        return lines

    loss = data["loss"]
    counts = loss["counts"]
    lines += [
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Couverture des nœuds | {_pct(data['node_coverage'])} |",
        f"| Couverture des relations | {_pct(data['relation_coverage'])} |",
        f"| Couverture des branches | {_pct(data['branch_coverage'])} |",
        f"| Entry point préservé | {'oui' if data['entry_preserved'] else 'non'} |",
        f"| Nœuds terminaux préservés | {'oui' if data['terminal_preserved'] else 'non'} |",
        f"| Réf. agent–prompt | {_pct(data['agent_prompt_ref_coverage'])} |",
        f"| Réf. agent–outil | {_pct(data['agent_tool_ref_coverage'])} |",
        f"| Éléments unresolved | {data['unresolved_count']} |",
        f"| Digest stable (extraction répétée) | {'oui' if data['digest_stable'] else 'non'} |",
        "",
        "**Périmètre normatif — statuts de préservation :**\n",
        f"- preserved : {counts['preserved']}",
        f"- approximated : {counts['approximated']}",
        f"- unsupported : {counts['unsupported']}",
        "",
    ]
    # Détail des propriétés non preserved.
    non_preserved = [p for p in loss["properties"] if p["status"] != "preserved"]
    if non_preserved:
        lines.append("**Propriétés non intégralement préservées :**\n")
        lines.append("| Propriété | Statut | Détail |")
        lines.append("|---|---|---|")
        for p in non_preserved:
            lines.append(f"| {p['property']} | `{p['status']}` | {p['detail']} |")
        lines.append("")
    # Statuts d'extraction des nœuds.
    esc = data["extraction_status_counts"]
    lines.append("**Statuts d'extraction des nœuds :** "
                 f"extracted={esc.get('extracted', 0)}, "
                 f"declared_by_adapter={esc.get('declared_by_adapter', 0)}, "
                 f"unresolved={esc.get('unresolved', 0)}\n")
    return lines


def _render_md(lg: Optional[Dict], crew: Optional[Dict],
               flow_only: Optional[Dict], flow_plus: Optional[Dict],
               oa_agent: Optional[Dict], oa_graph: Optional[Dict],
               generated_at: datetime) -> str:
    any_crewai = crew or flow_only or flow_plus
    any_openai = oa_agent or oa_graph
    lines: List[str] = [
        "# ACM — Information Preservation Report (auto-généré)\n",
        f"**Généré le :** {generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}  ",
        f"**Python :** {platform.python_version()} — "
        f"**Plateforme :** {platform.system()} {platform.machine()}  ",
        f"**Frameworks :** langgraph={'oui' if lg else 'non'}, "
        f"crewai={'oui' if any_crewai else 'non'}, "
        f"openai_agents={'oui' if any_openai else 'non'}\n",
        "> Mesure la préservation d'information lors de l'extraction de workflows "
        "natifs non triviaux vers la représentation ACM. Chiffres dérivés de "
        "l'exécution des extracteurs, jamais codés en dur.\n",
        "## Cadre\n",
        "Pour chaque workflow natif F, on calcule E(F) (extraction) et on compare "
        "à une représentation golden manuelle sur le périmètre normatif d'ACM. "
        "Une propriété est `preserved` (reconstruite exactement), `approximated` "
        "(abstraction ACM conservée, ex. condition opaque) ou `unsupported` "
        "(aucun concept ACM correspondant).\n",
        "## LangGraph\n",
    ]
    lines += _render_framework_section("Branche conditionnelle", lg)

    # Les trois niveaux d'abstraction CrewAI, distincts pour ne pas les mélanger.
    lines.append("## CrewAI — trois niveaux d'abstraction\n")
    lines.append(
        "CrewAI distingue plusieurs niveaux : un `Crew` (agents + tâches + "
        "process), un `Flow` (orchestration via start/router/listeners), et leur "
        "combinaison. On mesure les trois séparément pour ne pas confondre ce qui "
        "vient du Crew, du Flow, ou de leur fusion.\n")
    lines += _render_framework_section("Cas 1 — Crew-only (agents, tâches, contexte)", crew)
    lines += _render_framework_section("Cas 2 — Flow-only (start, router, branches)", flow_only)
    lines += _render_framework_section("Cas 3 — Flow+Crew (orchestration + tâches fusionnées)", flow_plus)

    # Note sur la frontière extraction / déclaration, propre au Flow.
    ref = flow_only or flow_plus
    if ref:
        esc = ref.get("extraction_status_counts", {})
        declared = esc.get("declared_by_adapter", 0)
        extracted = esc.get("extracted", 0)
        lines.append("### Lecture des cas Flow — extraction vs déclaration\n")
        lines.append(
            "Le Flow CrewAI illustre la frontière d'extractibilité, centrale pour "
            "l'article. Les nœuds et leurs rôles (start/router/listen) sont lus "
            f"directement depuis `flow._methods` ({extracted} nœud(s) `extracted`). "
            "En revanche, la topologie des arêtes n'est pas introspectable "
            "statiquement dans les versions récentes de CrewAI (elle est résolue à "
            "l'exécution) : les arêtes sont fournies par métadonnées "
            f"(`declared_by_adapter`, {declared} nœud(s) concerné(s)). Contrairement "
            "à LangGraph, dont la topologie est explicite et entièrement extraite, "
            "le Flow CrewAI relève partiellement de la déclaration d'adaptateur — "
            "une distinction que le métamodèle ACM rend explicite plutôt que de "
            "la masquer.\n")

    # OpenAI Agents SDK — deux niveaux d'abstraction (agent seul, graphe de handoffs).
    lines.append("## OpenAI Agents SDK — deux niveaux d'abstraction\n")
    lines.append(
        "Le SDK OpenAI Agents exprime un système multi-agents comme un `Agent` "
        "racine portant des `handoffs` (délégations) et des `tools`. On mesure "
        "deux niveaux : un `Agent` isolé (mono-nœud) et le graphe complet obtenu "
        "par fermeture transitive des handoffs. À la différence du Flow CrewAI, "
        "la topologie de handoffs est directement lisible sur les objets — les "
        "arêtes sont donc extraites, pas déclarées.\n")
    lines += _render_framework_section("Cas 1 — Agent seul (mono-nœud, outils)", oa_agent)
    lines += _render_framework_section("Cas 2 — Agent + handoffs (graphe de délégation)", oa_graph)

    # Note sur l'introspectabilité, propre au SDK OpenAI (miroir de la note Flow).
    if oa_graph:
        esc = oa_graph.get("extraction_status_counts", {})
        declared = esc.get("declared_by_adapter", 0)
        extracted_c = esc.get("extracted", 0)
        lines.append("### Lecture du graphe de handoffs — topologie extraite\n")
        lines.append(
            "Le SDK OpenAI illustre le cas SYMÉTRIQUE du Flow CrewAI. La topologie "
            "de délégation (`agent.handoffs`) est un attribut direct des objets : "
            "l'extracteur reconstruit les arêtes par introspection, sans aucune "
            "déclaration d'adaptateur ni élément de topologie `unresolved`. Le "
            "mapping des nœuds vers les références ACM (agent/prompt/model/outil) "
            f"reste, lui, déclaré par métadonnées ({declared} nœud(s) "
            "`declared_by_adapter`), exactement comme pour LangGraph — le framework "
            "ne connaît que des chaînes de modèle et des fonctions Python. Les trois "
            "frameworks couvrent ainsi trois régimes d'introspectabilité à périmètre "
            "normatif ACM constant : topologie déclarée (CrewAI Flow), topologie "
            "extraite avec conditions opaques signalées (LangGraph), topologie "
            "entièrement extraite sans condition opaque (OpenAI Agents SDK).\n")

    # Portabilité croisée.
    if lg and any_crewai:
        lines.append("## Portabilité croisée\n")
        n_fw = 2 + (1 if any_openai else 0)
        lines.append(
            "Les workflows, exprimés dans les abstractions natives de chaque "
            "framework et extraits indépendamment, sont normalisés vers la même "
            "représentation ACM sur le périmètre normatif. C'est la preuve "
            "d'extraction (plus forte que l'instanciabilité) : ACM comprend et "
            "normalise des systèmes natifs existants, pas seulement des "
            "spécifications qu'il a lui-même produites. La comparaison LangGraph "
            "(topologie extraite) / CrewAI Flow (topologie déclarée)"
            + (" / OpenAI Agents SDK (topologie extraite via handoffs)"
               if any_openai else "")
            + " documente aussi honnêtement les limites d'introspection propres à "
            f"chaque framework ({n_fw} frameworks normalisés vers le même noyau "
            "d'agents ACM).\n")

    lines.append("---\n")
    lines.append(f"*Rapport généré automatiquement — {generated_at.isoformat()}*")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Information Preservation Report ACM")
    parser.add_argument("--out-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).astimezone()

    lg = _run_langgraph_extraction()
    crew = _run_crewai_crew_extraction()
    flow_only = _run_crewai_flow_only_extraction()
    flow_plus = _run_crewai_flow_plus_crew_extraction()
    oa_agent = _run_openai_agent_extraction()
    oa_graph = _run_openai_agent_graph_extraction()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")

    md = _render_md(lg, crew, flow_only, flow_plus, oa_agent, oa_graph, generated_at)
    (args.out_dir / f"preservation_report_{stamp}.md").write_text(md, encoding="utf-8")
    (args.out_dir / "preservation_report_latest.md").write_text(md, encoding="utf-8")

    any_crewai = crew is not None or flow_only is not None or flow_plus is not None
    any_openai = oa_agent is not None or oa_graph is not None
    payload = {
        "generated_at": generated_at.isoformat(),
        "python": platform.python_version(),
        "frameworks": {"langgraph": lg is not None, "crewai": any_crewai,
                       "openai_agents": any_openai},
        "langgraph": lg,
        "crewai_crew_only": crew,
        "crewai_flow_only": flow_only,
        "crewai_flow_plus_crew": flow_plus,
        "openai_agent_only": oa_agent,
        "openai_agent_graph": oa_graph,
    }
    js = json.dumps(payload, indent=2, ensure_ascii=False)
    (args.out_dir / f"preservation_report_{stamp}.json").write_text(js, encoding="utf-8")
    (args.out_dir / "preservation_report_latest.json").write_text(js, encoding="utf-8")

    print(f"✓ Rapport : {args.out_dir / f'preservation_report_{stamp}.md'}")
    print(f"✓ JSON    : {args.out_dir / f'preservation_report_{stamp}.json'}")
    if not (lg and crew and flow_only and flow_plus and oa_agent and oa_graph):
        missing = [n for n, d in [("langgraph", lg), ("crewai-crew", crew),
                                  ("crewai-flow-only", flow_only),
                                  ("crewai-flow+crew", flow_plus),
                                  ("openai-agent", oa_agent),
                                  ("openai-agent-graph", oa_graph)] if d is None]
        print(f"  (extractions manquantes : {', '.join(missing)} — "
              "rapport partiel, relancer avec les extras installés)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
