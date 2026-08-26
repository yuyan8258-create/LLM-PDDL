# LLM-PDDL

## Overview

This repository contains the implementation and experimental artefacts for an MSc dissertation project on reliable symbolic planning with Large Language Models (LLMs), PDDL, and formal verification.

The project compares three planning conditions:

- **Pure LLM**: an LLM generates a complete candidate plan. The candidate is validated by VAL. If the first attempt is invalid, diagnostic information can still be recorded, but no second LLM generation is performed in the formal Pure LLM condition.
- **Pure PDDL**: Fast Downward performs classical PDDL planning without an LLM. If Fast Downward finds a plan, the plan is checked by the domain-specific Python symbolic verifier and then by VAL.
- **Hybrid LLM + Verification Feedback**: an LLM generates a complete candidate plan. VAL validates the plan. If VAL rejects it, the corresponding Python symbolic verifier is used to localise the symbolic failure. The resulting diagnostic information is converted into structured feedback and supplied to the LLM for another complete-plan generation attempt.

The formal evaluation covers three symbolic planning domains:

1. **Block Building**
2. **Occlusion Manipulation**
3. **Gearbox Assembly**

Each domain contains one Easy, one Medium, and one Hard task instance.

The formal LLM evaluation uses:

- `llama3.1:8b`
- `qwen2.5:latest`
- `deepseek-v4-flash`

The final formal experiment contains **630 runs**:

- Pure PDDL: 90 runs
- Pure LLM: 270 runs
- Hybrid LLM + Verification Feedback: 270 runs

The aggregated formal results in `results/master_summary/master_runs.csv` contain:

- Pure PDDL: 90/90 successful runs
- Pure LLM: 110/270 successful runs
- Hybrid LLM + Verification Feedback: 141/270 successful runs

These success results refer to validity within the encoded symbolic models. They do not establish physical feasibility, collision safety, kinematic feasibility, or successful real-world robot execution.

---

## Planning and Validation Architecture

### Pure LLM

The LLM receives task information for the selected scene and generates a complete candidate plan. In the formal Pure LLM condition, `max_iterations=1`.

The generated plan is validated by VAL. If VAL rejects the plan, the pipeline can still produce symbolic diagnostic information and save it with the run artefacts, but the Pure LLM condition does not use that feedback for another generation attempt.

### Pure PDDL

Fast Downward performs the planning step. If Fast Downward does not find a solution, the run fails at the Fast Downward stage and no symbolic-verifier or VAL check is performed for a candidate plan.

If Fast Downward finds a solution, the generated action sequence is parsed into the project's internal plan representation, checked by the domain-specific Python symbolic verifier, and then validated by VAL.

A Pure PDDL run is recorded as successful only when:

```text
Fast Downward solved the task
AND
Python symbolic verification succeeded
AND
VAL returned valid
```

Fast Downward is used only for the Pure PDDL planning condition. It is not used to repair Hybrid LLM plans.

### Hybrid LLM + Verification Feedback

The Hybrid condition follows this process:

```text
Task / Scene
    -> LLM complete-plan generation
    -> VAL validation
        -> valid: success
        -> invalid:
             Python symbolic diagnosis
             -> structured feedback
             -> LLM complete-plan regeneration
             -> VAL validation again
```

The formal Hybrid experiments use a maximum of three generation attempts.

For LLM-generated plans, VAL is the final formal validity authority. The Python symbolic verifier is used for failure localisation and diagnostic information, including failed actions, unsatisfied preconditions, and state information around the failure.

Hybrid refinement uses complete-plan regeneration. It does not perform local action replacement or local plan patching.

---

## Repository Structure

```text
LLM-PDDL/
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   └── scenes/
│
├── domains/
│   ├── block_building/
│   ├── occlusion_manipulation/
│   └── gearbox/
│
├── generated_pddl/
├── prompts/
│
├── src/
│   ├── domain_adapters/
│   ├── external_tools/
│   ├── verifiers/
│   ├── collect_master_results.py
│   ├── collect_refinement_results.py
│   ├── config_io.py
│   ├── domain_config.py
│   ├── external_val_feedback_loop.py
│   ├── llm_provider.py
│   ├── pddl_llm_demo.py
│   ├── pddl_problem_builder.py
│   ├── plan_model.py
│   ├── pyramid_demo_v3.py
│   ├── run_batch_refinement.py
│   ├── run_pure_pddl.py
│   └── scene_config.py
│
├── tests/
│   └── fixtures/
│
├── test_*.py
│
└── results/
    ├── formal/
    ├── occlusion_formal/
    ├── gearbox_formal/
    ├── master_summary/
    ├── refinement/
    ├── pure_pddl/
    └── additional development and regression outputs
```

The repository contains both final formal experiment artefacts and earlier development/regression artefacts. The dissertation statistics are based on the three formal domain result roots and the cross-domain master summary:

```text
results/formal/
results/occlusion_formal/
results/gearbox_formal/
results/master_summary/
```

---

## Scene Definitions: `data/scenes/`

The planning tasks are defined as JSON scene files.

Current formal scene files are:

```text
scene_01_blocksworld_basic.json
scene_02_pyramid.json
scene_03_large_pyramid.json
occlusion_easy.json
occlusion_medium.json
occlusion_hard.json
gearbox_easy.json
gearbox_medium.json
gearbox_hard.json
```

The corresponding scene IDs and formal task categories are:

```text
Block Building
  scene_01_blocksworld_basic   easy
  scene_02_pyramid             medium
  scene_03_large_pyramid       hard

Occlusion Manipulation
  occlusion_easy               easy
  occlusion_medium             medium
  occlusion_hard               hard

Gearbox Assembly
  gearbox_easy                 easy
  gearbox_medium               medium
  gearbox_hard                 hard
```

All scene files contain the core task information used by the pipeline, including fields such as:

- `scene_id`
- `domain_id`
- `scene_name`
- `description`
- `difficulty`
- `objects`
- `initial_state`
- `goal_state`
- `expected_plan`

Some domain-specific scenes also contain optional fields such as:

- `negative_goal_state`
- `planning_guidance`

The Easy/Medium/Hard labels are task categories within each domain. They are not a calibrated numerical difficulty measure for direct cross-domain comparison.

---

## PDDL Domain Packs: `domains/`

The three current domain packs are:

```text
domains/block_building/
    domain.pddl
    domain_config.json

domains/occlusion_manipulation/
    domain.pddl
    domain_config.json

domains/gearbox/
    domain.pddl
    domain_config.json
```

Each `domain.pddl` file defines the predicates and actions for that symbolic planning domain.

Each `domain_config.json` file records metadata used by the generic Python pipeline, including:

- `domain_id`
- PDDL domain name
- adapter identifier
- description
- predicate arities
- action arities

The adapter identifier is used by the loader to select the matching domain adapter and symbolic verifier module.

---

## Generated PDDL: `generated_pddl/`

The current code generates PDDL problem files from scene JSON configurations. `src/scene_config.py` defines `generated_pddl/` as the generated-PDDL location, and `src/pddl_problem_builder.py` writes scene-specific PDDL problem files used by the runtime pipeline.

The repository also contains generated PDDL files from earlier development stages. These files are artefacts rather than separate formal domain definitions. The authoritative domain definitions are the `domain.pddl` files under `domains/`.

---

## Prompt Files: `prompts/`

The repository contains the following prompt text files from development of the LLM planning workflow:

```text
weak_prompt.txt
medium_prompt.txt
strong_prompt.txt
repair_prompt.txt
```

The current formal LLM pipeline does not load these files as its main prompt source. Instead, task-specific planning prompts and feedback prompts are constructed programmatically by the current adapter/pipeline code.

---

## Source Code Guide

### `src/external_val_feedback_loop.py`

This is the main LLM planning, VAL validation, and feedback-guided refinement pipeline.

It is responsible for:

- loading the selected scene and domain configuration
- initialising the matching domain adapter and symbolic verifier
- generating the scene-specific PDDL problem file
- creating a run directory
- copying the exact domain and problem PDDL files used by an LLM-based run into that run directory
- constructing the planning prompt
- calling the selected LLM provider
- parsing the generated plan
- saving candidate plans in JSON and VAL-compatible `.plan` form
- invoking VAL
- invoking the domain-specific Python symbolic verifier when VAL rejects an LLM-generated plan
- constructing and saving structured feedback
- performing complete-plan regeneration in Hybrid mode
- recording attempt-level and run-level artefacts

In the formal setup:

- Pure LLM uses one generation attempt
- Hybrid uses up to three generation attempts
- Hybrid regeneration produces a new complete plan rather than modifying only a local part of the previous plan

### `src/run_batch_refinement.py`

Runs repeated LLM-based experiments for one fixed scene, provider, model, and method.

Supported methods are:

```text
pure_llm
hybrid_feedback
```

Supported providers are:

```text
ollama
deepseek
```

The script creates a batch directory and records files including:

```text
batch_config.json
batch_runs_partial.json
batch_summary.json
```

It also refreshes the run-level and model-level CSV summaries for the selected results base.

### `src/run_pure_pddl.py`

Runs one Pure PDDL experiment.

The implemented path is:

```text
scene/domain initialisation
-> generated PDDL problem
-> Fast Downward
-> parse Fast Downward plan
-> Python symbolic verification
-> VAL validation
-> run summary
```

If Fast Downward does not solve the task, the run terminates with `failure_stage="fast_downward"`.

The default Fast Downward alias is `lama-first`, and the default timeout is 120 seconds.

### `src/collect_refinement_results.py`

Collects run summaries from LLM-based refinement directories and Pure PDDL directories and writes domain-level CSV summaries.

When `--results-base` is supplied, the collector reads:

```text
<results-base>/refinement/
<results-base>/pure_pddl/
```

and writes:

```text
<results-base>/tables/refinement_runs.csv
<results-base>/tables/refinement_model_summary.csv
```

The run-level schema includes fields such as:

```text
run_id
scene
mode
method
provider
model
success
first_attempt_valid
iterations
first_plan_length
final_plan_length
first_failed_step
first_failed_action
first_error
final_failed_step
final_failed_action
final_error
inferred_root_cause
total_val_runtime_seconds
average_val_runtime_seconds
failure_stage
run_directory
summary_file
```

`inferred_root_cause` is an auxiliary helper field. It includes domain-specific heuristics and should not be interpreted as a universal failure taxonomy.

### `src/collect_master_results.py`

Combines the three formal domain result sets into the cross-domain tables used for the dissertation.

Default formal inputs are:

```text
results/formal
results/occlusion_formal
results/gearbox_formal
```

The default output directory is:

```text
results/master_summary
```

The script audits the expected formal experiment structure:

```text
210 runs per domain
21 groups per domain
10 runs per group
630 total runs
63 total groups
```

It writes:

```text
master_runs.csv
master_group_summary.csv
success_matrix.csv
method_summary.csv
```

### `src/llm_provider.py`

Defines the common LLM provider interface and two current provider implementations:

- `OllamaProvider`
- `DeepSeekProvider`

`OllamaProvider` uses the `ollama` Python package.

`DeepSeekProvider` uses the OpenAI Python client with:

```text
base_url = https://api.deepseek.com
```

and reads the API key from `DEEPSEEK_API_KEY` when an API key is not supplied directly to the provider object.

The formal LLM pipeline constructs both providers with temperature `0.0`.

### `src/scene_config.py`

Discovers and loads scene JSON files under `data/scenes/`.

It validates the scene identifier and the declared `domain_id`, normalises object declarations, preserves domain-specific state dictionaries, and defines shared project paths including:

```text
data/scenes/
domains/
generated_pddl/
results/
```

### `src/domain_config.py`

Discovers and loads `domain_config.json` files under `domains/`.

It validates required fields, including:

- domain ID
- PDDL domain name
- adapter name
- description
- predicate arities
- action arities

It also checks that the corresponding `domain.pddl` file exists.

### `src/config_io.py`

Provides shared JSON configuration-loading utilities used by the scene and domain configuration modules.

### `src/pddl_problem_builder.py`

Builds a PDDL problem from a loaded scene and domain configuration.

It converts initial-state and goal-state data into PDDL atoms, supports flat and typed object declarations, handles optional negative goals, and writes the scene-specific PDDL problem used by Fast Downward and VAL.

### `src/plan_model.py`

Defines the domain-independent internal plan-step representation and parsing/conversion helpers used by the current pipeline.

It supports conversion between external planner action text, structured plan steps, and PDDL-style action text.

### `src/pyramid_demo_v3.py`

Contains Block Building components from the earlier pyramid prototype that are still imported by the current LLM/VAL pipeline and regression tests.

Although the filename reflects the earlier prototype stage, it remains a dependency of the current implementation.

### `src/pddl_llm_demo.py`

Contains earlier prototype/demo code from development of the LLM-PDDL workflow. It is not the entry point used for the final formal experiments.

---

## Domain Adapters

### `src/domain_adapters/base.py`

Defines the common interface for domain-specific adapters.

### `src/domain_adapters/block_building.py`

Implements the adapter for Block Building.

### `src/domain_adapters/occlusion_manipulation.py`

Implements the adapter for Occlusion Manipulation.

### `src/domain_adapters/gearbox.py`

Implements the adapter for Gearbox Assembly.

The adapter layer allows the same experiment pipeline to prepare scenes, prompts, plans, and domain-specific data for domains with different predicates and action semantics.

---

## Python Symbolic Verifiers

### `src/verifiers/base.py`

Defines the common symbolic-verifier interface and result structures.

### `src/verifiers/block_building.py`

Performs action-by-action symbolic checking for Block Building plans.

### `src/verifiers/occlusion_manipulation.py`

Performs domain-specific symbolic checking for Occlusion Manipulation plans.

### `src/verifiers/gearbox.py`

Performs domain-specific symbolic checking for Gearbox Assembly plans, including the ordering and assembly-aid constraints represented by the Gearbox task model.

For LLM-generated plans, these Python verifiers are used for diagnosis and failure localisation. VAL remains the final formal validity authority.

---

## External Tool Wrappers

### `src/external_tools/fast_downward_runner.py`

Runs Fast Downward inside the Ubuntu WSL distribution by calling `wsl.exe` from the Windows-side Python process.

The wrapper:

- converts Windows paths to WSL paths
- invokes Fast Downward
- reads the generated plan file
- records the process return code and measured wrapper runtime
- parses planner-reported values where available, including plan length, plan cost, expanded states, evaluated states, generated states, and planner-reported time

The current source contains this machine-specific Fast Downward path:

```text
/home/lyy/planning-tools/fast-downward/fast-downward.py
```

Before using the wrapper on another machine, update `FAST_DOWNWARD_SCRIPT` to the local Fast Downward path. The wrapper also currently assumes a WSL distribution named `Ubuntu`.

### `src/external_tools/val_runner.py`

Runs the VAL `Validate` executable inside the Ubuntu WSL distribution.

The wrapper converts paths, invokes VAL, determines validity from the VAL output, records VAL runtime, and can write a cleaned validation log when a log path is supplied.

The current source contains this machine-specific VAL path:

```text
/home/lyy/planning-tools/VAL/build/bin/Validate
```

Before using the wrapper on another machine, update `VAL_EXECUTABLE` to the local VAL installation path. The wrapper also currently assumes a WSL distribution named `Ubuntu`.

### `src/external_tools/path_utils.py`

Converts absolute Windows drive paths such as `D:\...` into WSL `/mnt/<drive>/...` paths.

The current external-tool wrappers are therefore written for a Windows + WSL setup rather than for native Linux/macOS execution.

### `src/external_tools/test_external_pipeline.py`

Development/integration test script for the Fast Downward + VAL external toolchain. It is not a formal experiment entry point.

---

## Tests

The root-level `test_*.py` files and the files under `tests/` are development tests covering parts of the current pipeline.

They include checks for areas such as:

- scene configuration
- domain configuration
- plan parsing
- PDDL problem generation
- domain adapters
- domain-specific symbolic verifiers
- LLM provider behaviour and provider injection
- Fast Downward integration
- VAL integration
- Hybrid feedback handling
- malformed feedback handling
- multi-scene execution
- batch scene selection
- result collection

The directory:

```text
tests/fixtures/gearbox_adl_smoke/
```

contains Gearbox PDDL domains, problems, and valid/invalid plan fixtures used during development to check VAL behaviour and the transition to the quantifier-free Gearbox encoding used by the final domain.

---

## Results Directory Guide

The `results/` directory contains both the final dissertation experiments and earlier development/regression outputs.

### Final formal experiment roots

#### `results/formal/`

Formal Block Building experiments.

Its main structure includes:

```text
batches/
pure_pddl/
refinement/
tables/
*.log
```

#### `results/occlusion_formal/`

Formal Occlusion Manipulation experiments using the same general organisation.

#### `results/gearbox_formal/`

Formal Gearbox Assembly experiments using the same general organisation.

#### `results/master_summary/`

Cross-domain aggregate tables used for the dissertation analysis.

Current files are:

```text
master_runs.csv
master_group_summary.csv
success_matrix.csv
method_summary.csv
```

`master_runs.csv` contains 630 formal run records, and `master_group_summary.csv` contains 63 fixed experiment groups.

### Other result directories

The repository also retains non-final outputs produced during implementation. These are not included in the final 630-run dissertation statistics unless they were later copied/aggregated into the formal roots above.

#### `results/refinement/`

Default output tree used by the LLM refinement pipeline and batch runner when a separate formal results base is not supplied. It also contains development/regression runs from earlier stages.

#### `results/pure_pddl/`

Default Pure PDDL output tree when `--results-base` is not supplied.

#### `results/tables/`

Default summary-table location used by the refinement collector when no formal results base is supplied. It also contains earlier comparison tables from development.

#### `results/external_pipeline/`

Output from development/integration testing of the external planner/validator pipeline.

#### `results/fast_downward/`

Earlier Fast Downward integration artefacts.

#### `results/val/`

Earlier VAL validation artefacts.

#### `results/local_llm_test/`

Legacy local-LLM development outputs. They are not part of the final 630 formal runs.

#### `results/occlusion_smoke/`

Occlusion smoke/development outputs.

#### `results/occlusion_formal_test/`

Pre-formal or regression outputs generated while checking the Occlusion experiment pipeline.

#### `results/occlusion_invalid_runs/`

Invalid Occlusion run artefacts retained for failure inspection.

#### `results/raw/` and `results/pyramid_demo_result.json`

Earlier Block Building/pyramid prototype outputs.

---

## Formal Run Artefacts

### LLM-based runs

A normal LLM-based run directory can contain files such as:

```text
domain.pddl
problem.pddl
attempt_01_prompt.txt
attempt_01_raw_llm.txt
attempt_01_plan.json
attempt_01.plan
attempt_01_val.txt
attempt_01_feedback.json
run_summary.json
```

If a Hybrid run continues to another attempt, the same pattern is repeated with `attempt_02_*` and possibly `attempt_03_*` files.

When VAL accepts a candidate plan, the accepted plan is also copied to:

```text
final_validated.plan
```

If LLM generation or plan parsing raises an exception, the run can instead contain an error record such as:

```text
attempt_01_generation_error.json
```

Not every file appears in every run. For example, a first-attempt valid run does not need an `attempt_01_feedback.json` file.

### Pure PDDL runs

A successful Pure PDDL run directory contains:

```text
fast_downward.plan
candidate.plan
run_summary.json
```

If Fast Downward fails to solve the task, a run may contain only the available planner output artefact(s) and `run_summary.json`; no candidate VAL plan is required.

### Batch artefacts

A batch directory created by `src/run_batch_refinement.py` contains:

```text
batch_config.json
batch_runs_partial.json
batch_summary.json
```

The run-level artefacts are kept so that an aggregated CSV record can be traced back to its source run directory.

---

## Installation

### Python dependencies

Create and activate a virtual environment, then install the Python packages listed in `requirements.txt`.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The current core Python dependencies are:

```text
ollama
openai
```

### Ollama

Ollama is required for the local Llama and Qwen experiments.

The formal model names used in the dissertation experiments are:

```text
llama3.1:8b
qwen2.5:latest
```

These model names must be available in the local Ollama installation before those experiments are run.

### DeepSeek API

The DeepSeek experiments use the OpenAI Python client with DeepSeek's OpenAI-compatible API endpoint.

Set the API key through the environment rather than placing it in source code.

PowerShell example:

```powershell
$env:DEEPSEEK_API_KEY="YOUR_API_KEY"
```

The formal model string recorded in the experiment results is:

```text
deepseek-v4-flash
```

### Fast Downward and VAL

Fast Downward and VAL are external tools and are not installed through `requirements.txt`.

The current wrappers are written for Windows calling an Ubuntu WSL environment. Before running the full pipeline on another machine, check the local installation paths in:

```text
src/external_tools/fast_downward_runner.py
src/external_tools/val_runner.py
```

and the WSL distribution name used by the wrapper commands.

---

## Running Experiments

Run commands from the repository root.

### Pure LLM batch

Example: Block Building Easy with Llama.

```powershell
python src/run_batch_refinement.py `
  --scene scene_01_blocksworld_basic `
  --method pure_llm `
  --provider ollama `
  --model llama3.1:8b `
  --runs 10 `
  --max-iterations 1 `
  --results-base results/formal
```

For Qwen, use:

```text
qwen2.5:latest
```

For DeepSeek, use:

```powershell
python src/run_batch_refinement.py `
  --scene scene_01_blocksworld_basic `
  --method pure_llm `
  --provider deepseek `
  --model deepseek-v4-flash `
  --runs 10 `
  --max-iterations 1 `
  --results-base results/formal
```

### Hybrid batch

Example: Block Building Easy with Llama.

```powershell
python src/run_batch_refinement.py `
  --scene scene_01_blocksworld_basic `
  --method hybrid_feedback `
  --provider ollama `
  --model llama3.1:8b `
  --runs 10 `
  --max-iterations 3 `
  --results-base results/formal
```

### Pure PDDL single run

`src/run_pure_pddl.py` imports the project as the `src` package, so the reliable command from the repository root is module execution:

```powershell
python -m src.run_pure_pddl `
  --scene scene_01_blocksworld_basic `
  --alias lama-first `
  --timeout 120 `
  --results-base results/formal
```

The formal result base used for each domain is:

```text
Block Building            results/formal
Occlusion Manipulation    results/occlusion_formal
Gearbox Assembly          results/gearbox_formal
```

---

## Collecting Domain-Level Results

After experiments have been written under a result base, generate its CSV summaries with:

```powershell
python src/collect_refinement_results.py --results-base results/formal
```

For the other formal domains:

```powershell
python src/collect_refinement_results.py --results-base results/occlusion_formal
python src/collect_refinement_results.py --results-base results/gearbox_formal
```

The collector reads the `refinement/` and `pure_pddl/` subdirectories of the selected base and writes:

```text
<results-base>/tables/refinement_runs.csv
<results-base>/tables/refinement_model_summary.csv
```

---

## Collecting Cross-Domain Master Results

Once the three formal result roots contain their domain-level `tables/refinement_runs.csv` files, run:

```powershell
python src/collect_master_results.py
```

The default output is:

```text
results/master_summary/
```

The script checks the expected run and group counts before writing the master tables.

---

## Formal Experiment Design

For each domain:

```text
3 task instances: Easy, Medium, Hard
```

Pure PDDL:

```text
3 scenes x 10 runs = 30 runs per domain
```

Pure LLM:

```text
3 scenes x 3 LLM models x 10 runs = 90 runs per domain
```

Hybrid LLM + Verification Feedback:

```text
3 scenes x 3 LLM models x 10 runs = 90 runs per domain
```

Total per domain:

```text
210 runs
```

Across three domains:

```text
630 formal runs
```

For the LLM-based conditions, the first generation uses the same task representation and generation path. The difference appears after an invalid first attempt: Pure LLM stops because its formal maximum is one attempt, while Hybrid can use the saved verification-derived feedback to generate a new complete plan.

---

## Main Formal Result Files

### `results/master_summary/master_runs.csv`

Contains all 630 formal run records.

### `results/master_summary/master_group_summary.csv`

Contains 63 fixed domain/difficulty/scene/method/provider/model groups, with 10 runs per group.

### `results/master_summary/success_matrix.csv`

Contains one row for each of the same 63 formal groups and provides a compact group-level comparison of first-attempt and final success information.

### `results/master_summary/method_summary.csv`

Contains aggregate results for the three planning methods:

```text
pure_pddl
pure_llm
hybrid_feedback
```

---

## Verified Aggregate Results

The current `results/master_summary/master_runs.csv` contains:

```text
Pure PDDL                       90 runs   90 successes
Pure LLM                       270 runs  110 successes
Hybrid LLM + Verification      270 runs  141 successes
```

This corresponds to:

```text
Pure PDDL       100.00%
Pure LLM         40.74%
Hybrid           52.22%
```

The Hybrid condition therefore has 31 more successful runs than Pure LLM in this fixed formal experiment set, corresponding to an 11.48 percentage-point difference in final success rate.

These values describe the recorded formal experiment results only. They should not be interpreted as universal performance estimates for the models or domains outside the tested configuration.

---

## Important Interpretation Notes

1. **Formal validity is model-relative.** A plan passing VAL is valid with respect to the supplied PDDL domain and problem. It does not prove real-world feasibility.

2. **VAL and the Python symbolic verifier have different roles.** For LLM-generated plans, VAL provides the final formal validity judgement. The Python symbolic verifier provides domain-specific diagnosis and failure localisation.

3. **Pure PDDL uses a combined success criterion.** A Pure PDDL run is successful only when Fast Downward solves the task, the symbolic verifier succeeds, and VAL returns valid.

4. **Hybrid refinement uses complete-plan regeneration.** The system does not perform local plan patching.

5. **Fast Downward is not used for Hybrid repair.** Fast Downward is the planner for the Pure PDDL condition.

6. **The project does not implement LLM-guided classical search-space reduction.** LLM-generated search constraints, intermediate subgoals, or heuristics for guiding Fast Downward remain a possible future extension rather than an implemented experiment.

7. **Recorded VAL timing is not end-to-end runtime.** The `total_val_runtime_seconds` and `average_val_runtime_seconds` fields describe VAL validation timing, not the complete computational cost of LLM generation, Fast Downward search, symbolic diagnosis, and refinement.

8. **The repeated formal LLM runs use temperature 0.0 with fixed configurations.** They are separate executions, but they should not be interpreted as highly variable independent stochastic samples.

9. **The Easy/Medium/Hard labels are within-domain task categories.** They are not a common numerical difficulty scale across all three domains.

10. **`inferred_root_cause` is an auxiliary field.** It includes domain-specific heuristics and is not a universal failure taxonomy.

---

## Dependencies

Python dependencies are listed in:

```text
requirements.txt
```

The current core entries are:

```text
ollama
openai
```

External software/services used by the complete experiment pipeline are:

- Fast Downward
- VAL
- Ollama
- DeepSeek API access for DeepSeek runs

---

## Project Status

This repository contains the implementation and experiment artefacts used for the final MSc dissertation evaluation, together with selected development and regression artefacts retained for traceability.

The final dissertation statistics are based on:

```text
results/formal/
results/occlusion_formal/
results/gearbox_formal/
results/master_summary/
```

Other result directories are development, smoke-test, regression, or earlier prototype artefacts unless explicitly stated otherwise.
