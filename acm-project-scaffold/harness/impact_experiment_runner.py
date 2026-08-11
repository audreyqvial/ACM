# Emplacement : harness/impact_experiment_runner.py
"""Runner de l'expérience quantitative d'impact (matrice framework × changement).

Chaîne, par cas (f, c) :
    système natif-équivalent (before/after)
        -> moteur ACM (propagate) sur les deux
        -> P_f(c) = ensemble affecté par le moteur (delta) [PUBLIÉ]
        -> oracle figé M_f(c) [vérifié par digest]
        -> métriques : size/depth/ratio (bloc1), precision/recall (bloc1),
           inspection_reduction (bloc1 + fichier inspection séparé)
        -> cohérence statique : P_f(c) ⊆ reach(root) [test, non publié]
        -> reassessment baseline [signal dérivé, hors P_f(c)]
        -> déterminisme : K répétitions, ensemble/itérations identiques

Un enregistrement par cas, au schéma recommandé en fin du document de review.
Le résultat publié vient du MOTEUR, jamais de reach().
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from acm.impact import compare, impact_metrics, inspection_reduction, reach
from acm.policy import PropagationContext
from acm.propagation.engine import propagate

from .baseline_reassessment import evaluate_baseline_reassessment
from .engine_prediction import affected_set_delta
from .impact_oracle import ImpactOracle, load_oracle_dir
from .inspection_record import InspectionRecord, load_inspection_dir
from .oracle_provenance import OracleManifest, load_manifest, make_provenance
from .reach_consistency import check_consistency

# Import de la fixture native-équivalente (les 3 builders + perturbations).
from scenarios.impact_experiment.native_equivalent import (
    PERTURBATIONS,
    BUILDERS,
    apply_perturbation,
)


@dataclass
class ExperimentRecord:
    """Un cas expérimental (framework × change) — schéma du document de review."""

    framework: str
    change_id: str
    change_class: str
    root_aci: str

    native_graph_size: int          # nb de révisions du graphe extrait
    acm_graph_size: int             # nb d'ids logiques (sommets d'impact)
    relation_count: int

    oracle_affected: List[str]
    predicted_affected: List[str]
    true_positive: List[str]
    false_positive: List[str]
    false_negative: List[str]

    impact_size: int
    impact_depth: int
    impact_ratio: float

    precision: float
    recall: float
    f1: float

    manual_inspections: Optional[int]
    assisted_inspections: Optional[int]
    inspection_reduction: Optional[float]

    fixed_point_iterations: int
    elapsed_ms: float

    # Provenance / vérifications
    oracle_content_sha256: str
    digest_verified: bool
    oracle_git_commit: Optional[str]

    # Cohérence statique (non publiée comme résultat, mais tracée)
    reach_inclusion_holds: bool
    reach_not_activated: List[str]

    # Signal dérivé baseline (hors P_f(c))
    baseline_reassessment_required: bool
    baseline_triggering_items: List[str]

    # Déterminisme
    deterministic: bool
    repetitions: int

    experiment_started_at: str

    def to_dict(self) -> Dict:
        return asdict(self)


def _run_engine(before_tuple, after_tuple, root_aci: str, ctx: PropagationContext):
    """Deux runs moteur (avant/après) -> (P, iterations_after, report_after)."""
    graph_b, ev_b, _ = before_tuple
    graph_a, ev_a, _ = after_tuple
    report_before = propagate(graph_b, ev_b, ctx)
    report_after = propagate(graph_a, ev_a, ctx)
    P = affected_set_delta(report_before, report_after, root_id=root_aci)
    return P, report_after.iterations, report_after


def run_case(
    framework: str,
    change_id: str,
    *,
    oracles: Dict[str, ImpactOracle],
    inspections: Dict[str, InspectionRecord],
    manifest: Optional[OracleManifest],
    oracle_dir: Path,
    repetitions: int = 5,
) -> ExperimentRecord:
    """Exécute un cas (framework, change) et produit son enregistrement."""
    import time

    ctx = PropagationContext()
    started = datetime.now(timezone.utc).isoformat()

    # --- Perturbation : avant / après ---
    before_t, after_t, root_aci = apply_perturbation(framework, change_id)
    graph_after, _, baseline = after_t

    # --- Prédiction moteur + chrono ---
    t0 = time.perf_counter()
    P, iterations, _report = _run_engine(before_t, after_t, root_aci, ctx)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # --- Déterminisme : répéter et comparer ensemble + itérations ---
    det = True
    for _ in range(max(0, repetitions - 1)):
        P2, it2, _ = _run_engine(before_t, after_t, root_aci, ctx)
        if P2 != P or it2 != iterations:
            det = False
            break

    # --- Métriques de portée (bloc 1) sur le graphe après perturbation ---
    m = impact_metrics(graph_after, root_aci)

    # --- Oracle figé + provenance vérifiée ---
    key = f"{framework}::{change_id}"
    oracle = oracles[key]
    oracle_path = oracle_dir / _oracle_filename(framework, change_id)
    _, prov = make_provenance(oracle_path, manifest, experiment_started_at=started)
    M = oracle.affected_ids()

    # --- Comparaison P vs M ---
    cmp = compare(P, M)

    # --- Inspection (fichier séparé) ---
    insp = inspections.get(key)
    if insp is not None:
        red = inspection_reduction(insp.manual_inspections, insp.assisted_inspections)
        manual, assisted, reduction = (
            insp.manual_inspections,
            insp.assisted_inspections,
            red.reduction,
        )
    else:
        manual = assisted = reduction = None

    # --- Cohérence statique P ⊆ reach ---
    cons = check_consistency(graph_after, root_aci, P)

    # --- Reassessment baseline (dérivé, hors P) ---
    reass = evaluate_baseline_reassessment(baseline, P, root_id=root_aci)

    # --- Tailles de graphe ---
    native_graph_size = len(graph_after.revisions)
    acm_graph_size = len({rev.ref.id for rev in graph_after.revisions.values()})
    relation_count = len(graph_after.relations)

    return ExperimentRecord(
        framework=framework,
        change_id=change_id,
        change_class=oracle.change_class,
        root_aci=root_aci,
        native_graph_size=native_graph_size,
        acm_graph_size=acm_graph_size,
        relation_count=relation_count,
        oracle_affected=sorted(M),
        predicted_affected=sorted(P),
        true_positive=sorted(cmp.true_positive),
        false_positive=sorted(cmp.false_positive),
        false_negative=sorted(cmp.false_negative),
        impact_size=m.size,
        impact_depth=m.depth,
        impact_ratio=round(m.ratio, 6),
        precision=cmp.precision,
        recall=cmp.recall,
        f1=cmp.f1,
        manual_inspections=manual,
        assisted_inspections=assisted,
        inspection_reduction=(round(reduction, 6) if reduction is not None else None),
        fixed_point_iterations=iterations,
        elapsed_ms=round(elapsed_ms, 4),
        oracle_content_sha256=prov.oracle_content_sha256,
        digest_verified=prov.digest_verified,
        oracle_git_commit=prov.oracle_git_commit,
        reach_inclusion_holds=cons.inclusion_holds,
        reach_not_activated=sorted(cons.reach_not_activated),
        baseline_reassessment_required=reass.reassessment_required,
        baseline_triggering_items=sorted(reass.triggering_items),
        deterministic=det,
        repetitions=repetitions,
        experiment_started_at=started,
    )


def _oracle_filename(framework: str, change_id: str) -> str:
    """Nom de fichier oracle conventionnel : <framework>_<class-slug>.yaml.

    Les fichiers fournis suivent : langgraph_local.yaml / _intermediate / _global.
    On dérive le slug depuis le change_id (…-local… etc.), avec repli sur le
    change_id complet.
    """
    slug_map = {
        "local-finalizer-prompt": "local",
        "intermediate-research-tool": "intermediate",
        "global-shared-model": "global",
    }
    slug = slug_map.get(change_id, change_id)
    return f"oracle_{framework}_{slug}.yaml"


def run_matrix(
    *,
    oracle_dir: str | Path,
    inspection_dir: str | Path,
    manifest_path: Optional[str | Path] = None,
    frameworks: Optional[List[str]] = None,
    changes: Optional[List[str]] = None,
    repetitions: int = 5,
) -> List[ExperimentRecord]:
    """Exécute la matrice complète framework × change.

    Ne lève pas sur oracle manquant : un cas sans oracle figé est ignoré avec
    un avertissement implicite (absent des résultats). Les frameworks/changes
    par défaut couvrent la matrice 3×3.
    """
    oracle_dir = Path(oracle_dir)
    inspection_dir = Path(inspection_dir)
    oracles = load_oracle_dir(oracle_dir)
    inspections = load_inspection_dir(inspection_dir)
    manifest = load_manifest(manifest_path) if manifest_path else None

    frameworks = frameworks or list(BUILDERS.keys())
    changes = changes or list(PERTURBATIONS.keys())

    records: List[ExperimentRecord] = []
    for f in frameworks:
        for c in changes:
            key = f"{f}::{c}"
            if key not in oracles:
                # Oracle figé absent pour ce cas : on ne fabrique rien.
                continue
            records.append(
                run_case(
                    f,
                    c,
                    oracles=oracles,
                    inspections=inspections,
                    manifest=manifest,
                    oracle_dir=oracle_dir,
                    repetitions=repetitions,
                )
            )
    return records
