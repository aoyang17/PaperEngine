# Materials and simulation paper structure

Use six reader-facing blocks for battery-material, electrochemical, mechanics, and multiphysics papers:

1. Paper overview
2. Research system and problem definition
3. Model and physical mechanisms
4. Computational setup and reproducibility
5. Results, validation, and mechanistic interpretation
6. Research value and resources

Do not expose algorithm-paper labels such as algorithm steps, datasets, benchmarks, or theorem chains unless the paper actually contains those objects and the terminology helps a materials reader.

## Block 1: Paper overview

Always include:

- study identity: experimental, computational, theoretical, review, or mixed;
- alignment with each configured topic module, including a 0–1 score, role, paper-specific rationale, and source references;
- one-sentence conclusion;
- why the paper is worth reading;
- research problem;
- gap in prior work;
- core contribution;
- conclusion and applicability boundary.

Module relevance is not overall paper quality. Score the paper against the precise module definition. State absent objects explicitly: for example, an isolated silicon calculation is not evidence for porous-carbon geometry or CVD manufacture, and a continuum intrinsic length does not by itself constitute a multiscale parameter-transfer chain.

Each substantive overview statement must cite source-map blocks. Chinese translations must convey the same scientific meaning and preserve limitations rather than merely translating headings.

## Block 2: Research system and problem definition

Extract the physical object, geometry and scale, phases and chemical composition, process and loading, solved state variables, and target outputs. Distinguish imposed conditions from predicted quantities.

## Block 3: Model and physical mechanisms

State the overall framework, assumptions, free-energy terms, governing equations, material constitutive relations, and coupling logic. Preserve the actual equations and explain every term's physical role. Do not call a numerical time-stepping sequence an algorithm unless the paper does.

## Block 4: Computational setup and reproducibility

Tabulate model parameters with symbols, values, units, roles, and sources. Record initial conditions, boundary conditions, discretization, solver, mesh, time integration, convergence information, and missing reproduction inputs. Separate “rebuildable in principle” from executable reproducibility.

## Block 5: Results, validation, and mechanisms

Separate predicted results, validation/comparisons, mechanistic interpretation, parameter sensitivity and uncovered questions, and correspondence with experiments. Never treat qualitative agreement, internal analytical checks, comparison with another model, and direct experimental validation as equivalent evidence.

## Block 6: Research value and resources

Explain the paper's value to each configured research module, reusable equations/models/benchmarks, limitations and concrete next steps, and a reproducibility verdict. Show key figures, the local PDF, reading note, BibTeX, and verified code/data/model availability.

All six blocks must be paper-specific, bilingual, and source-traceable. Do not fill them by renaming legacy algorithm-template fields.
