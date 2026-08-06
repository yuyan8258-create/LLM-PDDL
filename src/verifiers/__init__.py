from __future__ import annotations

from importlib import import_module
from typing import Type

from src.domain_config import DomainConfig
from src.verifiers.base import (
    SymbolicVerifier,
)


def get_symbolic_verifier(
    domain: DomainConfig,
) -> SymbolicVerifier:
    """
    Load the verifier module matching the domain adapter name.

    Example:
        block_building
        -> src.verifiers.block_building.Verifier
    """

    module_name = (
        f"src.verifiers.{domain.adapter}"
    )

    try:
        verifier_module = import_module(
            module_name
        )
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ValueError(
                f"No symbolic verifier module exists for "
                f"domain '{domain.domain_id}': "
                f"{module_name}"
            ) from exc

        raise

    verifier_class = getattr(
        verifier_module,
        "Verifier",
        None,
    )

    if not isinstance(
        verifier_class,
        type,
    ):
        raise TypeError(
            f"Verifier module '{module_name}' must expose "
            f"a class named Verifier."
        )

    typed_verifier_class: Type[
        SymbolicVerifier
    ] = verifier_class

    if not issubclass(
        typed_verifier_class,
        SymbolicVerifier,
    ):
        raise TypeError(
            f"Verifier class in '{module_name}' must inherit "
            f"from SymbolicVerifier."
        )

    return typed_verifier_class(domain)