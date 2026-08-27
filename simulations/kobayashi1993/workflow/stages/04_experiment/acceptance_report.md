# Acceptance report: Modeling and numerical simulations of dendritic crystal growth — Fig. 7

- Case: `kobayashi1993`
- Generated: 2026-08-26T04:12:24.489136+00:00
- Required criteria: 12/12
- Overall: **PASS**

| Criterion | Metric | Actual | Rule | Required | Result |
|---|---|---:|---|---|---|
| authoritative_mph_present | `artifacts.final_mph_bytes` | 1659129698 bytes | > 1000000 | yes | PASS |
| comsol_logs_clean | `quality.comsol_error_count` | 0  | == 0 | yes | PASS |
| phase_lower_bound | `quality.p_min` | -3.644014108444248e-06  | >= -0.05 | yes | PASS |
| phase_upper_bound | `quality.p_max` | 1.0000017967303318  | <= 1.05 | yes | PASS |
| enthalpy_conservation | `quality.max_relative_enthalpy_drift` | 2.0860322444447883e-13  | <= 0.01 | yes | PASS |
| mesh_tip_convergence | `convergence.mesh_tip_relative_difference` | 0.003536067892503586  | <= 0.05 | yes | PASS |
| timestep_tip_convergence | `convergence.timestep_tip_relative_difference` | 0.0  | <= 0.05 | yes | PASS |
| seed_tip_robustness | `convergence.seed_tip_relative_range` | 0.002114164904862659  | <= 0.15 | yes | PASS |
| anisotropy_increases_tip_growth | `paper_trend.delta050_to_delta000_tip_ratio` | 1.850931677018633  | > 1.02 | yes | PASS |
| fourfold_directionality | `paper_trend.delta050_vertical_to_horizontal_extent_ratio` | 2.0135135135135136  | > 1.1 | yes | PASS |
| fig7_silhouette_overlap | `paper_figure.fig7_mean_iou` | 0.3282936401370114  | >= 0.25 | yes | PASS |
| fig7_contour_distance | `paper_figure.fig7_normalized_chamfer` | 0.026200561502855626  | <= 0.1 | yes | PASS |

## Provenance

- case_file: `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/02_theory/case.yml`
- metrics_file: `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/04_experiment/metrics.json`

## Raw metrics

- `artifacts`: `{'final_mph_bytes': 1659129698}`
- `convergence`: `{'mesh_tip_relative_difference': 0.003536067892503586, 'timestep_tip_relative_difference': 0.0, 'seed_tip_relative_range': 0.002114164904862659}`
- `paper_figure`: `{'fig7_mean_iou': 0.3282936401370114, 'fig7_normalized_chamfer': 0.026200561502855626}`
- `paper_trend`: `{'delta050_to_delta000_tip_ratio': 1.850931677018633, 'delta050_vertical_to_horizontal_extent_ratio': 2.0135135135135136}`
- `quality`: `{'comsol_error_count': 0, 'p_min': -3.644014108444248e-06, 'p_max': 1.0000017967303318, 'max_relative_enthalpy_drift': 2.0860322444447883e-13}`
