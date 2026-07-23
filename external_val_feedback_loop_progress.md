# External VAL Feedback Loop — Progress Record

## 1. Current project status

The project has now completed the first working version of an external validation feedback loop for Scene 02.

The implemented pipeline is:

1. A local LLM generates a candidate symbolic plan.
2. The candidate plan is converted into a VAL-compatible `.plan` file.
3. VAL checks whether the plan is executable and whether the goal conditions are achieved.
4. If VAL rejects the plan, the system generates structured feedback containing the failed step, failed action, error reason, and state before failure.
5. The feedback is used to generate a new complete plan.
6. The process repeats until VAL accepts the plan or the maximum number of iterations is reached.
7. The system saves all intermediate files and a final run summary.

## 2. Existing components reused

The implementation reuses the project's existing modules:

- `src/pyramid_demo_v3.py`
  - `LLMPlanner`
  - `PlanStep`
  - plan parsing and normalisation
  - `SymbolicVerifier`
  - Scene 02 symbolic state and reference plan

- `src/external_tools/val_runner.py`
  - invokes VAL through Ubuntu WSL
  - returns a structured `ValResult`
  - saves VAL logs

- `generated_pddl/scene_02_pyramid/domain.pddl`
- `generated_pddl/scene_02_pyramid/problem.pddl`

The new loop is implemented in:

- `src/external_val_feedback_loop.py`

## 3. Mock-mode validation

The loop was first tested in mock mode:

```powershell
python src\external_val_feedback_loop.py --mode mock --max-iterations 3
```

### Iteration 1

The first mock plan deliberately contained an ordering error:

```text
pick-up(B4)
pick-up(B5)
stack-bridge(B4, B1, B2)
stack-bridge(B5, B2, B3)
pick-up(pyramid)
stack-bridge(pyramid, B4, B5)
```

VAL rejected the plan because the robot attempted to pick up `B5` while already holding `B4`.

The generated structured feedback identified:

- failed step: 2
- failed action: `pick-up(B5)`
- missing precondition: `handempty`
- state before failure: the robot was holding `B4`

### Iteration 2

The corrected plan was:

```text
pick-up(B4)
stack-bridge(B4, B1, B2)
pick-up(B5)
stack-bridge(B5, B2, B3)
pick-up(pyramid)
stack-bridge(pyramid, B4, B5)
```

VAL accepted the corrected plan.

This mock test demonstrated that:

- the candidate plan is saved correctly;
- VAL can reject an invalid plan;
- structured feedback can be generated;
- a corrected plan can be validated in a later iteration;
- the loop stops automatically after success;
- run artefacts are saved correctly.

## 4. Real LLM-mode validation

The loop was then tested with the local model:

```powershell
python src\external_val_feedback_loop.py --mode llm --model llama3.1:8b --max-iterations 3
```

The model generated the correct six-step plan on the first attempt:

```text
pick-up(B4)
stack-bridge(B4, B1, B2)
pick-up(B5)
stack-bridge(B5, B2, B3)
pick-up(pyramid)
stack-bridge(pyramid, B4, B5)
```

VAL accepted the plan.

Recorded outcome:

- mode: `llm`
- model: `llama3.1:8b`
- success: `true`
- iterations: `1`
- plan length: `6`
- VAL final value: `6`

This confirms that the real LLM-to-VAL pipeline is operational.

However, because the first plan was already correct, this run did not test whether the real LLM could repair a failed plan. Further repeated experiments with weaker prompts, smaller models, or more complex scenes are required.

## 5. Files generated for each run

Each run creates a directory under:

```text
results/refinement/scene_02_pyramid/run_<timestamp>/
```

Typical files include:

```text
attempt_01_plan.json
attempt_01.plan
attempt_01_val.txt
attempt_01_feedback.json
attempt_02_plan.json
attempt_02.plan
attempt_02_val.txt
final_validated.plan
domain.pddl
problem.pddl
run_summary.json
```

Not every run contains every file. For example, `attempt_01_feedback.json` is only created if the first plan fails.

## 6. Evidence to preserve

### A. Source-code evidence

Preserve:

- `src/external_val_feedback_loop.py`
- `src/external_tools/val_runner.py`
- `src/pyramid_demo_v3.py`
- `generated_pddl/scene_02_pyramid/domain.pddl`
- `generated_pddl/scene_02_pyramid/problem.pddl`

### B. Mock-run evidence

Preserve one complete successful mock-run folder containing:

- invalid first plan;
- first VAL failure log;
- structured feedback JSON;
- corrected second plan;
- second VAL success log;
- final validated plan;
- run summary.

### C. Real LLM-run evidence

Preserve one complete `llama3.1:8b` run folder containing:

- first generated plan JSON;
- VAL-compatible plan;
- VAL log;
- final validated plan;
- run summary.

### D. Screenshots

Keep the following screenshots:

1. The project structure in VS Code showing:
   - `external_val_feedback_loop.py`
   - `val_runner.py`
   - the generated run folder and files

2. The mock run, iteration 1:
   - invalid candidate plan
   - `VAL valid: False`
   - structured feedback showing missing `handempty`

3. The mock run, iteration 2:
   - corrected plan
   - `VAL valid: True`
   - success after two iterations

4. The real LLM run:
   - `Mode: llm`
   - `Model: llama3.1:8b`
   - first candidate plan
   - `VAL valid: True`
   - success after one iteration

5. The opened `run_summary.json` showing:
   - mode
   - model
   - success
   - iterations
   - final plan

Avoid saving screenshots that only show long raw logs without a clear purpose.

## 7. Recommended screenshot locations

Store screenshots under:

```text
screenshots/external_feedback_loop/
```

Suggested names:

```text
01_mock_iteration1_val_failure.png
02_mock_structured_feedback.png
03_mock_iteration2_val_success.png
04_llama31_first_attempt_success.png
05_refinement_run_files.png
06_run_summary_llama31.png
```

## 8. Recommended result folders to preserve

Keep one representative mock run and one representative real LLM run.

Suggested naming after copying:

```text
results/refinement/evidence/
├── mock_failure_then_success/
└── llama31_first_attempt_success/
```

Do not overwrite or delete the original timestamped run directories until the dissertation is submitted.

## 9. Current limitations

The current prototype has the following limitations:

1. The test scene is a manually defined symbolic pyramid scene.
2. The real LLM run succeeded on the first attempt, so real LLM self-repair has not yet been demonstrated.
3. The prompt contains strong task-specific guidance, which may make the task too easy.
4. The detailed structured feedback appears to combine VAL's formal pass/fail result with symbolic state reconstruction from the Python verifier.
5. Evaluation has currently been demonstrated on one main scene and a small number of runs.

## 10. Immediate next steps

1. Run repeated trials for `llama3.1:8b`.
2. Test `llama3.2:3b` and `qwen2.5:latest`.
3. Record first-attempt success rate and final success rate.
4. Record the number of refinement iterations.
5. Record common failure categories.
6. Test a weaker prompt so that feedback repair is genuinely exercised.
7. Extend the loop to Scene 03 or another longer-horizon scene.
8. Export results into a CSV table for later evaluation.

## 11. Short progress summary

A working external validation feedback loop has been implemented for Scene 02. The system can generate candidate plans, save them in VAL-compatible format, formally validate them using VAL, produce structured feedback after failure, and repeat planning until a valid plan is found. The mock test demonstrated a failure followed by successful correction in the second iteration. A real run using `llama3.1:8b` generated a valid six-step plan on the first attempt. The next stage is systematic repeated evaluation across models, prompts, and scene complexity.
