from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from src.domain_config import DomainConfig
from src.scene_config import SceneConfig


@dataclass(frozen=True)
class PlanStep:
    """
    Domain-independent representation of one grounded planning action.

    Examples:

        PlanStep(
            action="pick-up",
            args=("B4",),
        )

        PlanStep(
            action="stack-bridge",
            args=("B4", "B1", "B2"),
        )
    """

    action: str
    args: tuple[str, ...]

    def to_function_text(self) -> str:
        """
        Return the project/JSON-style action representation.

        Example:
            stack-bridge(B4, B1, B2)
        """

        return (
            f"{self.action}("
            f"{', '.join(self.args)}"
            f")"
        )

    def to_pddl_text(self) -> str:
        """
        Return the PDDL/VAL-style grounded action representation.

        Example:
            (stack-bridge B4 B1 B2)
        """

        if self.args:
            return (
                f"({self.action} "
                f"{' '.join(self.args)})"
            )

        return f"({self.action})"

    def to_json_object(self) -> dict[str, Any]:
        """
        Return the structured JSON representation expected from an LLM.
        """

        return {
            "action": self.action,
            "args": list(self.args),
        }


_FUNCTION_ACTION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<action>[A-Za-z][A-Za-z0-9_-]*)
    \s*
    \(
    \s*
    (?P<args>.*?)
    \s*
    \)
    \s*$
    """,
    flags=re.VERBOSE,
)


_PDDL_ACTION_PATTERN = re.compile(
    r"""
    ^\s*
    \(
    \s*
    (?P<action>[A-Za-z][A-Za-z0-9_-]*)
    (?P<args>(?:\s+[^()\s]+)*)
    \s*
    \)
    \s*$
    """,
    flags=re.VERBOSE,
)


def parse_plan_step(
    raw_step: str,
) -> PlanStep:
    """
    Parse one action string without assuming a particular domain.

    Accepted forms:

        pick-up(B4)
        stack-bridge(B4, B1, B2)
        (pick-up B4)
        (stack-bridge B4 B1 B2)

    Action legality and arity are checked separately against
    DomainConfig.
    """

    if not isinstance(raw_step, str):
        raise TypeError(
            f"Plan step must be a string, got "
            f"{type(raw_step).__name__}."
        )

    cleaned_step = raw_step.strip()

    if not cleaned_step:
        raise ValueError(
            "Plan step cannot be empty."
        )

    function_match = (
        _FUNCTION_ACTION_PATTERN.fullmatch(
            cleaned_step
        )
    )

    if function_match:
        action = (
            function_match
            .group("action")
            .strip()
            .lower()
        )

        raw_arguments = (
            function_match
            .group("args")
            .strip()
        )

        if raw_arguments:
            arguments = tuple(
                argument.strip()
                for argument
                in raw_arguments.split(",")
            )
        else:
            arguments = ()

        if any(
            not argument
            for argument in arguments
        ):
            raise ValueError(
                f"Plan step contains an empty argument: "
                f"{raw_step!r}"
            )

        return PlanStep(
            action=action,
            args=arguments,
        )

    pddl_match = (
        _PDDL_ACTION_PATTERN.fullmatch(
            cleaned_step
        )
    )

    if pddl_match:
        action = (
            pddl_match
            .group("action")
            .strip()
            .lower()
        )

        raw_arguments = (
            pddl_match
            .group("args")
            .strip()
        )

        arguments = (
            tuple(raw_arguments.split())
            if raw_arguments
            else ()
        )

        return PlanStep(
            action=action,
            args=arguments,
        )

    raise ValueError(
        "Could not parse plan step. Expected a form such as "
        "'pick-up(B4)' or '(pick-up B4)', but received: "
        f"{raw_step!r}"
    )


def parse_plan_steps(
    raw_steps: Iterable[str],
) -> list[PlanStep]:
    """
    Parse an ordered collection of action strings.
    """

    parsed_plan: list[PlanStep] = []

    for step_number, raw_step in enumerate(
        raw_steps,
        start=1,
    ):
        try:
            parsed_step = parse_plan_step(
                raw_step
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid plan step {step_number}: "
                f"{exc}"
            ) from exc

        parsed_plan.append(parsed_step)

    if not parsed_plan:
        raise ValueError(
            "Plan must contain at least one action."
        )

    return parsed_plan


def validate_plan_step(
    step: PlanStep,
    scene: SceneConfig,
    domain: DomainConfig,
    step_number: int | None = None,
) -> None:
    """
    Validate one grounded action against its scene and domain.

    Checks:
    - scene/domain link;
    - action exists;
    - action arity;
    - arguments are declared scene objects.
    """

    location = (
        f"Plan step {step_number}"
        if step_number is not None
        else "Plan step"
    )

    if scene.domain_id != domain.domain_id:
        raise ValueError(
            f"{location}: scene '{scene.scene_id}' uses domain "
            f"'{scene.domain_id}', but validation received "
            f"'{domain.domain_id}'."
        )

    if step.action not in domain.action_arities:
        available_actions = ", ".join(
            sorted(domain.action_arities)
        )

        raise ValueError(
            f"{location}: unknown action '{step.action}' for "
            f"domain '{domain.domain_id}'. Available actions: "
            f"{available_actions}"
        )

    expected_arity = domain.action_arities[
        step.action
    ]

    if len(step.args) != expected_arity:
        raise ValueError(
            f"{location}: action '{step.action}' requires "
            f"{expected_arity} argument(s), but received "
            f"{len(step.args)}: {step.args}"
        )

    declared_objects = set(scene.objects)

    for argument in step.args:
        if argument not in declared_objects:
            raise ValueError(
                f"{location}: action '{step.action}' references "
                f"undeclared object '{argument}' in scene "
                f"'{scene.scene_id}'."
            )


def validate_plan(
    plan: list[PlanStep],
    scene: SceneConfig,
    domain: DomainConfig,
) -> None:
    """
    Validate every step in an ordered plan.

    This performs structural validation only. It does not simulate
    action preconditions or effects; that is the verifier's role.
    """

    if not plan:
        raise ValueError(
            f"Scene '{scene.scene_id}' plan cannot be empty."
        )

    for step_number, step in enumerate(
        plan,
        start=1,
    ):
        validate_plan_step(
            step=step,
            scene=scene,
            domain=domain,
            step_number=step_number,
        )


def load_expected_plan(
    scene: SceneConfig,
    domain: DomainConfig,
) -> list[PlanStep]:
    """
    Parse and structurally validate expected_plan from SceneConfig.
    """

    plan = parse_plan_steps(
        scene.expected_plan
    )

    validate_plan(
        plan=plan,
        scene=scene,
        domain=domain,
    )

    return plan


def plan_to_json(
    plan: list[PlanStep],
) -> str:
    """
    Serialize a plan into the structured LLM JSON format.
    """

    return json.dumps(
        [
            step.to_json_object()
            for step in plan
        ],
        indent=2,
        ensure_ascii=False,
    )


def plan_to_pddl_text(
    plan: list[PlanStep],
) -> str:
    """
    Serialize a plan into the line-oriented format used by VAL.
    """

    return "\n".join(
        step.to_pddl_text()
        for step in plan
    ) + "\n"