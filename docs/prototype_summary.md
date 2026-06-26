# Prototype Summary

This prototype demonstrates an image-inspired LLM + PDDL block construction planning system.

The current pipeline is:

1. Manually abstract the target image into symbolic scene relations.
2. Export the symbolic scene as PDDL domain/problem files.
3. Use an LLM to generate a candidate construction plan.
4. Verify each action using a PDDL-style symbolic verifier.
5. Check final goal satisfaction.
6. Save experiment results.

## Basic BlocksWorld Experiment

Before the image-inspired pyramid scene, a simpler BlocksWorld experiment was implemented. In this scene, blockA initially rests on blockB, while blockB and blockC are on the table. The goal is to place blockA on the table and stack blockB on blockC.

Expected plan:

```text
unstack(blockA, blockB)
put-down(blockA)
pick-up(blockB)
stack(blockB, blockC)
```
This experiment is used as the easy baseline scene for testing the LLM + PDDL-style verification loop.

## Pyramid Demo: Successful LLM-Generated Plan
```text
pick-up(B4)
stack-bridge(B4, B1, B2)
pick-up(B5)
stack-bridge(B5, B2, B3)
pick-up(pyramid)
stack-bridge(pyramid, B4, B5)
```

## Initial Model Comparison on Scene 02

An initial model comparison was conducted on the image-inspired pyramid scene.

- `llama3.1:8b` generated a valid 6-step construction plan in one iteration.
- `llama3.2:3b` failed after three verifier-feedback iterations. It first attempted to pick up another object while the robot hand was not empty, and later generated invalid bridge actions using occupied support slots.
- `qwen2.5:latest` also failed after three verifier-feedback iterations. It generated unnecessary extra bridge actions after the target structure had already been completed, violating `right-free` and `left-free` support-slot constraints.

These results show that different LLMs behave differently on the same symbolic construction task. They also demonstrate why symbolic verification is necessary: the generated plans can look plausible, but may violate action preconditions or continue acting after the goal has already been achieved.