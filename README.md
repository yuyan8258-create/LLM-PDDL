# LLM-PDDL

A prototype project for LLM-generated PDDL planning and symbolic verification in image-inspired block construction tasks.

## Project Overview

This project investigates how Large Language Models can generate candidate construction plans, while PDDL-style symbolic verification checks whether each action satisfies its logical preconditions and effects.

The current prototype focuses on an image-inspired block construction task. The target image is manually abstracted into symbolic scene relations and exported as PDDL domain/problem files.

## Current Features

- Image-inspired block construction scene
- Manual symbolic scene abstraction
- PDDL domain/problem export
- LLM plan generation through Ollama
- PDDL-style symbolic verifier
- Structured feedback for plan refinement
- Robust parser for LLM outputs
- Experiment result logging

## Example Target Structure

```text
             [pyramid]
        [B4]          [B5]
   [B1]      [B2]          [B3]
   ------------------------- table
```

## Goal Conditions

```text
on-bridge(B4, B1, B2)
on-bridge(B5, B2, B3)
on-bridge(pyramid, B4, B5)
ontable(B1), ontable(B2), ontable(B3), handempty
```

## How to Run

Manual/reference plan verification:

```bash
python src/pyramid_demo_v3.py --planner manual
```

LLM planning mode:

```bash
python src/pyramid_demo_v3.py --planner llm --model llama3.1:8b
```

If a different local Ollama model is available, replace the model name. For example:

```bash
python src/pyramid_demo_v3.py --planner llm --model llama3.2:3b
```

## Example Successful Output

```text
Result: SUCCESS
Iterations: 1

Final validated plan:
1. pick-up(B4)
2. stack-bridge(B4, B1, B2)
3. pick-up(B5)
4. stack-bridge(B5, B2, B3)
5. pick-up(pyramid)
6. stack-bridge(pyramid, B4, B5)
```

## Current Limitations

- The current prototype does not perform computer vision.
- The image-to-symbolic-scene abstraction is manually defined.
- The verifier is a lightweight PDDL-style verifier.
- External PDDL solver integration is planned as the next step.
- The current version has only one main image-inspired pyramid scene.

## Planned Experiments

- Extend to 4–5 block construction scenes with different complexity levels.
- Include simple, complex, partially occluded, and LEGO-like construction scenes.
- Compare different LLMs, such as Llama and Qwen.
- Repeat experiments on the same model and scene to evaluate stability.
- Compare Pure LLM, Pure PDDL, and Hybrid LLM + PDDL approaches.
- Evaluate success rate, runtime, number of iterations, output format errors, and logical error types.

## Repository Structure

```text
LLM-PDDL/
│
├── src/
│   └── pyramid_demo_v3.py
│
├── prompts/
│   ├── weak_prompt.txt
│   ├── medium_prompt.txt
│   ├── strong_prompt.txt
│   └── repair_prompt.txt
│
├── data/
│   └── scenes/
│       └── scene_02_pyramid.json
│
├── generated_pddl/
│   └── scene_02_pyramid/
│       ├── domain.pddl
│       └── problem.pddl
│
├── results/
│   ├── raw/
│   │   └── pyramid_demo_result.json
│   └── tables/
│       └── experiment_summary.csv
│
├── docs/
│   ├── prototype_summary.md
│   ├── supervisor_feedback.md
│   └── meeting_notes.md
│
└── screenshots/
    ├── manual_success.png
    ├── llm_failed_feedback.png
    └── llm_success.png
```

## Notes

This repository is part of an MSc dissertation project on combining LLM-based planning with symbolic PDDL-style verification. The current implementation is an early prototype and will be extended with additional scenes, model comparisons, repeated trials, and more formal PDDL solver integration.