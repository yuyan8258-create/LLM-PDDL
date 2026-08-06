from __future__ import annotations

import copy
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.plan_model import PlanStep
from src.scene_config import SceneConfig


@dataclass(frozen=True)
class VerificationResult:
    """
    Domain-independent result returned by a symbolic verifier.

    VAL remains the final validation authority. This result is mainly
    used for detailed failure diagnosis and LLM repair feedback.
    """

    success: bool
    message: str
    final_state: dict[str, Any]

    failed_step: int | str | None = None
    failed_action: str | None = None
    error: str | None = None
    state_before_failure: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the result into a JSON-serializable dictionary.
        """

        result: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "final_state": copy.deepcopy(
                self.final_state
            ),
        }

        if self.failed_step is not None:
            result["failed_step"] = (
                self.failed_step
            )

        if self.failed_action is not None:
            result["failed_action"] = (
                self.failed_action
            )

        if self.error is not None:
            result["error"] = self.error

        if self.state_before_failure is not None:
            result["state_before_failure"] = (
                copy.deepcopy(
                    self.state_before_failure
                )
            )

        return result

    def to_feedback_text(self) -> str:
        """
        Return a structured JSON message suitable for LLM feedback.
        """

        return json.dumps(
            self.to_dict(),
            indent=2,
            ensure_ascii=False,
        )


class SymbolicVerifier(ABC):
    """
    Common interface for domain-specific symbolic verifiers.
    """

    @abstractmethod
    def verify(
        self,
        plan: list[PlanStep],
        scene: SceneConfig,
        verbose: bool = False,
    ) -> VerificationResult:
        """
        Simulate one grounded plan against one prepared scene.
        """