from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config_io import read_json_object
from src.scene_config import DOMAINS_DIRECTORY


@dataclass(frozen=True)
class DomainConfig:
    """
    Domain-independent configuration for one PDDL domain pack.

    Each domain pack is expected to contain:

        domains/<domain_id>/domain.pddl
        domains/<domain_id>/domain_config.json
    """

    domain_id: str
    pddl_domain_name: str
    adapter: str
    description: str

    predicate_arities: dict[str, int]
    action_arities: dict[str, int]

    domain_directory: Path
    domain_file: Path
    domain_config_file: Path

    domain_data: dict[str, Any]


def discover_domain_config_files() -> dict[str, Path]:
    """
    Discover every domain_config.json below the domains directory.

    Domain IDs must be unique across the whole project.
    """

    if not DOMAINS_DIRECTORY.exists():
        raise FileNotFoundError(
            f"Domains directory does not exist: "
            f"{DOMAINS_DIRECTORY}"
        )

    discovered: dict[str, Path] = {}

    for config_file in sorted(
        DOMAINS_DIRECTORY.rglob("domain_config.json")
    ):
        domain_data = read_json_object(config_file)

        raw_domain_id = domain_data.get("domain_id")

        if not isinstance(raw_domain_id, str):
            raise ValueError(
                f"Domain configuration must contain a string "
                f"domain_id: {config_file}"
            )

        domain_id = raw_domain_id.strip()

        if not domain_id:
            raise ValueError(
                f"Domain configuration contains an empty "
                f"domain_id: {config_file}"
            )

        if domain_id in discovered:
            raise ValueError(
                f"Duplicate domain_id '{domain_id}' found in:\n"
                f"  {discovered[domain_id]}\n"
                f"  {config_file}"
            )

        discovered[domain_id] = config_file

    return discovered


def _normalise_arity_map(
    domain_id: str,
    field_name: str,
    raw_mapping: Any,
) -> dict[str, int]:
    """
    Validate and normalise predicate or action arity mappings.

    Example:

        {
            "holding": 1,
            "handempty": 0
        }
    """

    if not isinstance(raw_mapping, dict):
        raise ValueError(
            f"Domain '{domain_id}' field '{field_name}' "
            f"must be an object."
        )

    normalised: dict[str, int] = {}

    for raw_name, raw_arity in raw_mapping.items():
        name = str(raw_name).strip()

        if not name:
            raise ValueError(
                f"Domain '{domain_id}' field '{field_name}' "
                f"contains an empty name."
            )

        # bool is a subclass of int in Python, so reject it explicitly.
        if (
            not isinstance(raw_arity, int)
            or isinstance(raw_arity, bool)
        ):
            raise ValueError(
                f"Domain '{domain_id}' {field_name} entry "
                f"'{name}' must have an integer arity."
            )

        if raw_arity < 0:
            raise ValueError(
                f"Domain '{domain_id}' {field_name} entry "
                f"'{name}' cannot have a negative arity."
            )

        normalised[name] = raw_arity

    if not normalised:
        raise ValueError(
            f"Domain '{domain_id}' field '{field_name}' "
            f"cannot be empty."
        )

    return normalised


def _validate_domain_data(
    requested_domain_id: str,
    domain_data: dict[str, Any],
    config_file: Path,
) -> None:
    """
    Validate domain-independent configuration structure.

    Detailed action semantics remain defined by domain.pddl and the
    selected domain adapter.
    """

    required_fields = {
        "domain_id",
        "pddl_domain_name",
        "adapter",
        "description",
        "predicate_arities",
        "action_arities",
    }

    missing_fields = sorted(
        required_fields - set(domain_data)
    )

    if missing_fields:
        raise ValueError(
            f"Domain configuration {config_file} is missing "
            f"required field(s): {', '.join(missing_fields)}"
        )

    raw_domain_id = domain_data["domain_id"]

    if not isinstance(raw_domain_id, str):
        raise ValueError(
            f"domain_id must be a string: {config_file}"
        )

    if raw_domain_id.strip() != requested_domain_id:
        raise ValueError(
            "Domain identifier mismatch: "
            f"requested '{requested_domain_id}', but configuration "
            f"contains '{raw_domain_id}'."
        )

    for field_name in (
        "pddl_domain_name",
        "adapter",
        "description",
    ):
        value = domain_data[field_name]

        if not isinstance(value, str):
            raise ValueError(
                f"Domain '{requested_domain_id}' field "
                f"'{field_name}' must be a string."
            )

        if not value.strip():
            raise ValueError(
                f"Domain '{requested_domain_id}' field "
                f"'{field_name}' cannot be empty."
            )


def load_domain_config(domain_id: str) -> DomainConfig:
    """
    Load one domain pack using its explicit domain_id.
    """

    requested_domain_id = domain_id.strip()

    if not requested_domain_id:
        raise ValueError("domain_id cannot be empty.")

    config_files = discover_domain_config_files()

    if requested_domain_id not in config_files:
        supported_text = ", ".join(
            sorted(config_files)
        )

        raise ValueError(
            f"Unsupported domain '{requested_domain_id}'. "
            f"Discovered domains: {supported_text}"
        )

    config_file = config_files[requested_domain_id]
    domain_data = read_json_object(config_file)

    _validate_domain_data(
        requested_domain_id=requested_domain_id,
        domain_data=domain_data,
        config_file=config_file,
    )

    predicate_arities = _normalise_arity_map(
        domain_id=requested_domain_id,
        field_name="predicate_arities",
        raw_mapping=domain_data["predicate_arities"],
    )

    action_arities = _normalise_arity_map(
        domain_id=requested_domain_id,
        field_name="action_arities",
        raw_mapping=domain_data["action_arities"],
    )

    domain_directory = config_file.parent
    domain_file = domain_directory / "domain.pddl"

    if not domain_file.exists():
        raise FileNotFoundError(
            f"PDDL domain file does not exist for domain "
            f"'{requested_domain_id}': {domain_file}"
        )

    if not domain_file.is_file():
        raise ValueError(
            f"PDDL domain path is not a file: {domain_file}"
        )

    return DomainConfig(
        domain_id=requested_domain_id,
        pddl_domain_name=(
            domain_data["pddl_domain_name"].strip()
        ),
        adapter=domain_data["adapter"].strip(),
        description=domain_data["description"].strip(),
        predicate_arities=predicate_arities,
        action_arities=action_arities,
        domain_directory=domain_directory,
        domain_file=domain_file,
        domain_config_file=config_file,
        domain_data=copy.deepcopy(domain_data),
    )


def list_supported_domains() -> list[str]:
    """
    Return every discovered domain ID in stable sorted order.
    """

    return sorted(discover_domain_config_files())