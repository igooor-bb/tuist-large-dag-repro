# Tuist Large DAG Repro

Standalone Tuist fixture for reproducing stack-safety issues on a large valid
acyclic dependency graph.

The primary repro uses the `stress` graph and intentionally does not pass a
focused target:

```bash
./scripts/reproduce.sh
```

This defaults to:

```bash
./scripts/reproduce.sh stress --no-focus
```

On an unpatched Tuist binary, the first expected crash stack usually includes
`CircularDependencyLinter`. As recursive stack-safety fixes are applied, the same
fixture can expose later recursive risks in the graph pipeline.

The fixes were validated in this order:

```text
CircularDependencyLinter
GraphCircularDetector (recursive-risk audit; no crash reproduced)
FocusTargetsGraphMappers / GraphAlgorithms.topologicalSort
ModuleMapMapper
StaticProductsGraphLinter
```

On a fully patched Tuist binary, generation should pass.

## Contents

- [What Stack-Safety Means Here](#what-stack-safety-means-here)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Finding Crash Reports](#finding-crash-reports)
- [Presets](#presets)
- [Focused Target Note](#focused-target-note)
- [What The Script Does](#what-the-script-does)
- [Graph Shape](#graph-shape)
- [Manual Commands](#manual-commands)
- [Custom Preset Configuration](#custom-preset-configuration)
- [Repository Files](#repository-files)
- [Troubleshooting](#troubleshooting)
- [Authorship Note](#authorship-note)

## What Stack-Safety Means Here

This fixture investigates stack overflows caused by recursive graph traversal on
a very deep but valid DAG.

The graph has no dependency cycles. The problem being tested is not whether
Tuist detects an invalid graph. The problem is whether graph algorithms can walk
a large acyclic workspace without exhausting the process call stack.

Typical failing symptoms are a Tuist process crash, stack overflow, or crash log
with many repeated frames from one graph-processing component.

## Requirements

```text
macOS
Python 3
Tuist binary to test
```

The generator uses only Python standard library modules. It does not call Xcode
directly. A selected Xcode installation may still be required by the Tuist binary
you are testing.

The fixture does not use private code, CocoaPods, Sourcery, external Swift
packages, or internal services.

## Quick Start

Use the Tuist binary from `PATH`:

```bash
./scripts/reproduce.sh
```

Use a specific Tuist binary:

```bash
TUIST_BIN=/path/to/tuist ./scripts/reproduce.sh stress --no-focus
```

Run the smaller smoke preset:

```bash
./scripts/reproduce.sh realistic --no-focus
```

Run with a focused target:

```bash
./scripts/reproduce.sh stress --focus
```

`--focus` runs `tuist generate --no-open App`. Without focus, the command is
`tuist generate --no-open`.

## Finding Crash Reports

After a crash, macOS usually records a report for the `tuist` process.

Using Console.app:

```text
1. Open Console.app.
2. Select Crash Reports in the sidebar.
3. Search for "tuist".
4. Open the newest report from the repro run.
5. Check the crashing thread for Tuist graph-processing frames.
```

Relevant frames may include:

```text
CircularDependencyLinter
GraphCircularDetector
FocusTargetsGraphMappers
GraphAlgorithms.topologicalSort
ModuleMapMapper
StaticProductsGraphLinter
```

The same reports are usually stored under:

```text
~/Library/Logs/DiagnosticReports/
```

## Presets

```text
realistic
  nodes: ~2000-3000
  edges: ~8000-12000
  longest path: 50-150
  purpose: smaller smoke-sized graph

stress
  nodes: ~3000-6000
  edges: ~10000-25000
  longest path: deep enough to stress recursive graph processing
  purpose: primary stack-safety repro fixture
```

Both presets can run with or without `--focus`:

```bash
./scripts/reproduce.sh realistic --no-focus
./scripts/reproduce.sh realistic --focus
./scripts/reproduce.sh stress --no-focus
./scripts/reproduce.sh stress --focus
```

## Focused Target Note

The primary stack-safety repro should start with `--no-focus`.

Passing `App` enables `FocusTargetsGraphMappers`. On the stress graph, that may
expose a separate recursive stack overflow in `GraphAlgorithms.topologicalSort`
before the no-focus graph linting path reaches later checks.

Use focused mode only when you intentionally want to check that path:

```bash
./scripts/reproduce.sh stress --focus
```

## What The Script Does

`scripts/reproduce.sh` performs:

```text
1. Generate Tuist manifests and sources.
2. Verify graph.json.
3. Print graph stats.
4. Run Tuist generation.
5. If generation succeeds, delete only Tuist output.
6. Run Tuist generation again from the already generated DSL.
```

The repeat check verifies that existing generated DSL is reusable. Skip it when
you only need the first crash:

```bash
./scripts/reproduce.sh stress --no-focus --skip-repeat
```

Compatibility wrappers are also available:

```bash
./scripts/reproduce-linter.sh            # stress --no-focus
./scripts/reproduce-realistic.sh         # realistic --focus
./scripts/reproduce-focused-toposort.sh  # stress --focus
```

## Graph Shape

This fixture is intentionally not a single linked list.
It models a large monorepo DAG with wide layers, shared infrastructure modules,
feature modules, test-support modules, and bridge modules with high fan-in.
The graph is acyclic and topologically sortable.

The generated workspace has three broad areas:

```text
App
  -> recent FeatureNNNNUI targets
  -> BridgeNNN targets

Feature layer N
  FeatureNNNNUI
    -> FeatureNNNNCore
    -> lower-index Feature UI/Core targets
    -> Bridge000 / Bridge002 / Bridge003

  FeatureNNNNCore
    -> FeatureNNNNModels
    -> lower-index Feature Core/Models targets
    -> SharedNNN
    -> Bridge001 / Bridge002 / Bridge004

  FeatureNNNNModels
    -> SharedNNN
    -> FoundationNNN

  FeatureNNNNTestsSupport / FeatureNNNNTests
    -> feature targets
    -> SharedTestsSupport

Infrastructure
  BridgeNNN
    -> SharedNNN
    -> FoundationNNN

  SharedNNN
    -> FoundationNNN

  FoundationNNN
```

`Bridge000`, `Bridge001`, and `Bridge002` are intentionally referenced by many
feature targets, so they get high fan-in. This is meant to look more like a
large app workspace with shared design-system, networking, analytics, and
platform modules than like a chain of single dependencies.

Targets are written into multiple `Projects/ShardNNN/Project.swift` files.
Each shard is just a generated Tuist project containing a small batch of targets
(`project-size`, default `25`). This keeps the fixture closer to a multi-project
workspace and exercises both same-project `.target(...)` dependencies and
cross-project `.project(target:path:)` dependencies.

All dependency edges point toward lower-index layers. For example,
`Feature0120UI` may depend on `Feature0119UI` or `Feature0117Core`, but those
lower-index features never point back to `Feature0120...`.

## Manual Commands

Generate only, without running Tuist:

```bash
python3 scripts/generate-fixture.py --preset stress
```

Verify the generated graph:

```bash
python3 scripts/verify-graph.py --preset stress
```

Print graph stats:

```bash
python3 scripts/graph-stats.py
```

Clean only Tuist output while keeping generated DSL:

```bash
./scripts/clean-tuist-output.sh
```

Clean all generated output:

```bash
./scripts/clean.sh
```

## Custom Preset Configuration

Reviewers can start from an existing preset and override individual generator
parameters:

```bash
python3 scripts/generate-fixture.py \
  --preset stress \
  --layers 1800 \
  --width 3 \
  --foundation-count 60 \
  --shared-count 250 \
  --bridge-count 30 \
  --project-size 25
```

Common knobs:

```text
--layers        increases graph depth
--width         adds extra lower-index feature edges
--shared-count  changes shared infrastructure size
--bridge-count  changes high fan-in bridge target count
--project-size  changes how many targets go into each Shard project
--seed          keeps custom graphs reproducible
```

After changing parameters, run:

```bash
python3 scripts/verify-graph.py
python3 scripts/graph-stats.py
```

## Repository Files

```text
Tuist.swift                           Tuist root marker and config
scripts/generate-fixture.py           generator, Python stdlib only
scripts/verify-graph.py               DAG verifier
scripts/graph-stats.py                graph statistics
scripts/reproduce.sh                  main entrypoint
scripts/reproduce-linter.sh           legacy stress --no-focus wrapper
scripts/reproduce-realistic.sh        realistic --focus wrapper
scripts/reproduce-focused-toposort.sh stress --focus wrapper
scripts/clean-tuist-output.sh         keeps generated DSL
scripts/clean.sh                      removes generated output
```

`Projects/`, `Workspace.swift`, and `graph.json` are generated and ignored by
git. They can always be recreated by the scripts.

## Troubleshooting

If Tuist cannot locate the root directory, check that `Tuist.swift` exists at the
repository root.

If Xcode opens, make sure the command includes `--no-open`; the scripts already
do this.

If `tuist` is not on `PATH`, pass `TUIST_BIN=/path/to/tuist`.

## Authorship Note

This fixture was mostly created with AI assistance and then reviewed and adjusted
for the Tuist stack-safety reproduction use case.
