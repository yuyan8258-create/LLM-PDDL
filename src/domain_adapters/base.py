from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.domain_config import DomainConfig
from src.scene_config import SceneConfig


class DomainAdapter(ABC):
    """
    Common interface for every planning-domain adapter.

    The unified pipeline should communicate with block, occlusion,
    gearbox, and future domains through this interface instead of
    containing domain-specific if/elif branches.
    """

    def __init__(
        self,
        domain: DomainConfig,
    ) -> None:
        self.domain = domain

    def validate_domain_link(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Require the scene and adapter to use the same domain.

        This validation is common to every planning domain.
        """

        if scene.domain_id != self.domain.domain_id:
            raise ValueError(
                f"Scene '{scene.scene_id}' uses domain "
                f"'{scene.domain_id}', but this adapter was "
                f"created for '{self.domain.domain_id}'."
            )

    @abstractmethod
    def validate_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate domain-specific scene requirements.

        Implementations may check object types, required predicates,
        domain-specific relationships, and other semantic constraints.
        """

    @abstractmethod
    def prepare_scene(
        self,
        scene: SceneConfig,
    ) -> SceneConfig:
        """
        Return a prepared copy of the scene.

        The original frozen SceneConfig and its nested state data must
        not be modified.

        Examples:
        - block: supply missing bridge support-slot defaults;
        - occlusion: derive accessibility defaults;
        - gearbox: derive domain-specific assembly defaults.
        """

    @abstractmethod
    def build_plan_prompt(
        self,
        scene: SceneConfig,
        feedback: str | None = None,
    ) -> str:
        """
        Build the domain-specific LLM planning prompt.

        The common LLM caller should receive the completed prompt from
        the adapter and should not contain block, occlusion, or gearbox
        object names or action rules.
        """

    def build_feedback(
        self,
        scene: SceneConfig,
        verifier_feedback: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Convert verifier output into feedback for plan refinement.

        The default implementation preserves the verifier message.
        Individual domains may override this method to add safe,
        domain-specific repair guidance.
        """

        self.validate_domain_link(scene)

        cleaned_feedback = verifier_feedback.strip()

        if not cleaned_feedback:
            cleaned_feedback = (
                "The candidate plan failed verification, but no "
                "detailed verifier message was available."
            )

        if not context:
            return cleaned_feedback

        context_lines = [
            f"- {key}: {value}"
            for key, value in sorted(context.items())
        ]

        return (
            f"{cleaned_feedback}\n\n"
            "Additional verification context:\n"
            + "\n".join(context_lines)
        )