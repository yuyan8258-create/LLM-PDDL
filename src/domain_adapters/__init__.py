from __future__ import annotations

from importlib import import_module
from typing import Type

from src.domain_adapters.base import DomainAdapter
from src.domain_config import DomainConfig


def get_domain_adapter(
    domain: DomainConfig,
) -> DomainAdapter:
    """
    Dynamically load the adapter declared by domain_config.json.

    For example:

        "adapter": "block_building"

    loads:

        src.domain_adapters.block_building.Adapter

    No central domain-name registry is required.
    """

    module_name = (
        f"src.domain_adapters.{domain.adapter}"
    )

    try:
        adapter_module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ValueError(
                f"No adapter module exists for domain "
                f"'{domain.domain_id}': {module_name}"
            ) from exc

        raise

    adapter_class = getattr(
        adapter_module,
        "Adapter",
        None,
    )

    if not isinstance(adapter_class, type):
        raise TypeError(
            f"Adapter module '{module_name}' must expose "
            f"a class named Adapter."
        )

    typed_adapter_class: Type[DomainAdapter] = (
        adapter_class
    )

    if not issubclass(
        typed_adapter_class,
        DomainAdapter,
    ):
        raise TypeError(
            f"Adapter class in '{module_name}' must inherit "
            f"from DomainAdapter."
        )

    return typed_adapter_class(domain)