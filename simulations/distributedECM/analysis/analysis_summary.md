# Distributed ECM simulation summary

| Metric at 500 s | Uniform | Nonuniform |
|---|---:|---:|
| Integrated boundary current (A) | 60 | 60 |
| Current-balance relative error | 4.441e-08 | 4.613e-09 |
| Mean local C-rate | 1.00054 | 1.0377 |
| Min / max local C-rate | 0.00272423 / 1.12538 | 5.44669e-05 / 5.15255 |
| Current coefficient of variation | 0.14008 | 1.08489 |
| Terminal voltage (V) | 3.00499 | 3.12363 |
| Mean boundary SOC | 0.138854 | 0.145164 |

The nonuniform/uniform current-CV ratio is **7.745**,
the peak local C-rate changes by **+4.027**, and
the terminal voltage changes by **+0.1186 V**.

See `current_distribution.svg` and `current_profile.svg` for spatial diagnostics.
