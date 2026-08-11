# acm-project-scaffold

## Structure du projet

```
└── acm-project-scaffold
    ├── acm
    │   ├── models
    │   │   ├── __init__.py
    │   │   ├── aci.py
    │   │   ├── enums.py
    │   │   ├── refs.py
    │   │   └── status.py
    │   ├── propagation
    │   │   ├── __init__.py
    │   │   ├── assurance.py
    │   │   ├── eligibility.py
    │   │   ├── engine.py
    │   │   ├── impact.py
    │   │   └── quality.py
    │   ├── runtime
    │   │   ├── __init__.py
    │   │   ├── evaluator.py
    │   │   ├── governance.py
    │   │   ├── instance.py
    │   │   ├── signal.py
    │   │   └── spec.py
    │   ├── state_machines
    │   │   ├── __init__.py
    │   │   ├── baselines.py
    │   │   ├── machines.py
    │   │   ├── revisions.py
    │   │   └── validator.py
    │   ├── __init__.py
    │   ├── invariants.py
    │   └── policy.py
    ├── adapters
    │   ├── __init__.py
    │   ├── crewai_adapter.py
    │   ├── crewai_extractor.py
    │   ├── deterministic_stub.py
    │   ├── langgraph_adapter.py
    │   └── langgraph_extractor.py
    ├── docs
    │   ├── ACM Lifecycle and State Propagation Model v0.1.pdf
    │   ├── acm_coverage_6_vs_27_scenarios.png
    │   ├── ACM_P1_Extraction_et_Perte_d_information.md
    │   ├── ACM_plan_scenarios_evaluation_v0.1.md
    │   ├── Analyse_technique_et_gap_analysis_ACM_20260728.md
    │   ├── article_summary.md
    │   ├── evaluation_report_20260728-112238.md
    │   ├── evaluation_report_20260728-164905.md
    │   ├── evaluation_report_20260728-180408.md
    │   ├── evaluation_report_consolidated.md
    │   ├── evaluation_report_consolidated_v0.1.md
    │   ├── evaluation_report_latest.md
    │   ├── FAILURES_test_crewai_flow.txt
    │   ├── gap_analysis_next_steps_20260728.md
    │   ├── impact_report_20260728-154810.json
    │   ├── impact_report_20260728-154810.md
    │   ├── impact_report_20260728-164858.json
    │   ├── impact_report_20260728-164858.md
    │   ├── impact_report_latest.json
    │   ├── impact_report_latest.md
    │   ├── preservation_report_20260728-170019.json
    │   ├── preservation_report_20260728-170019.md
    │   ├── preservation_report_20260728-180424.json
    │   ├── preservation_report_20260728-180424.md
    │   ├── preservation_report_20260728-181328.json
    │   ├── preservation_report_20260728-181328.md
    │   ├── preservation_report_20260728-193115.json
    │   ├── preservation_report_20260728-193115.md
    │   ├── preservation_report_20260729-092721.json
    │   ├── preservation_report_20260729-092721.md
    │   ├── preservation_report_example.md
    │   ├── preservation_report_latest.json
    │   ├── preservation_report_latest.md
    │   └── requirements_update_I4_I5.md
    ├── examples
    │   ├── records
    │   │   ├── recorded_run_crewai.json
    │   │   └── recorded_run_langgraph.json
    │   ├── __init__.py
    │   ├── crewai_demo.py
    │   └── langgraph_demo.py
    ├── harness
    │   ├── __init__.py
    │   ├── asserter.py
    │   ├── digest.py
    │   ├── extraction_oracle.py
    │   ├── impact_analysis.py
    │   ├── information_loss.py
    │   ├── loader.py
    │   ├── reporter.py
    │   ├── runner.py
    │   ├── runtime_conformity.py
    │   └── workflow_ir.py
    ├── ports
    │   ├── __init__.py
    │   └── runtime_adapter.py
    ├── scenarios
    │   ├── fixtures
    │   │   ├── ACM-S01.yaml
    │   │   ├── ACM-S02.yaml
    │   │   ├── ACM-S03.yaml
    │   │   ├── ACM-S05.yaml
    │   │   ├── ACM-S06.yaml
    │   │   ├── ACM-S07.yaml
    │   │   ├── ACM-S08.yaml
    │   │   ├── ACM-S09.yaml
    │   │   ├── ACM-S10.yaml
    │   │   ├── ACM-S11.yaml
    │   │   └── ACM-S13.yaml
    │   ├── __init__.py
    │   ├── impact_case_study.py
    │   ├── native_workflows.py
    │   ├── scenario_a.py
    │   ├── scenario_b.py
    │   ├── scenario_c.py
    │   ├── scenario_de.py
    │   ├── scenario_f.py
    │   └── workflow_golden.py
    ├── tests
    │   ├── __init__.py
    │   ├── strategies.py
    │   ├── test_assurance_composition.py
    │   ├── test_config_digest.py
    │   ├── test_core_no_extras.py
    │   ├── test_crewai_adapter.py
    │   ├── test_impact_analysis.py
    │   ├── test_invariants.py
    │   ├── test_langgraph_adapter.py
    │   ├── test_langgraph_execution.py
    │   ├── test_p0_review.py
    │   ├── test_p1_review.py
    │   ├── test_p2_properties.py
    │   ├── test_recorded_runs.py
    │   ├── test_scenario_a.py
    │   ├── test_scenario_b.py
    │   ├── test_scenario_c.py
    │   ├── test_scenario_de.py
    │   ├── test_scenario_f.py
    │   ├── test_scenario_s02.py
    │   ├── test_scenarios.py
    │   ├── test_scenarios_baselines.py
    │   ├── test_scenarios_group_b.py
    │   ├── test_scenarios_group_c.py
    │   ├── test_scenarios_group_d.py
    │   ├── test_scenarios_group_e.py
    │   ├── test_transitions.py
    │   ├── test_workflow_extraction.py
    │   └── test_workflow_extractors_native.py
    ├── conftest.py
    ├── diagnose_crewai_flow.py
    ├── diagnose_flow_wrappers_deep.py
    ├── diagnose_meth.py
    ├── evaluation_report.json
    ├── generate_evaluation_report.py
    ├── generate_impact_report.py
    ├── generate_preservation_report.py
    ├── generate_tree.py
    ├── pyproject.toml
    ├── README.md
    └── run_evaluation.py
```

---
*Structure générée automatiquement.*
