# Prototype Summary

This prototype demonstrates an image-inspired LLM + PDDL block construction planning system.

The current pipeline is:

1. Manually abstract the target image into symbolic scene relations.
2. Export the symbolic scene as PDDL domain/problem files.
3. Use an LLM to generate a candidate construction plan.
4. Verify each action using a PDDL-style symbolic verifier.
5. Check final goal satisfaction.
6. Save experiment results.

The current successful LLM-generated plan is:

```text
pick-up(B4)
stack-bridge(B4, B1, B2)
pick-up(B5)
stack-bridge(B5, B2, B3)
pick-up(pyramid)
stack-bridge(pyramid, B4, B5)