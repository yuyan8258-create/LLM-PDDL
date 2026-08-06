from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_object(json_file: Path) -> dict[str, Any]:
    """
    Read a UTF-8 JSON file and require one top-level object.

    This helper is shared by scene and domain configuration loaders.
    UTF-8 files with or without a byte-order mark are supported.
    """

    if not json_file.exists():
        raise FileNotFoundError(
            f"JSON file does not exist: {json_file}"
        )

    if not json_file.is_file():
        raise ValueError(
            f"JSON path is not a file: {json_file}"
        )

    try:
        loaded_data = json.loads(
            json_file.read_text(encoding="utf-8-sig")
        )
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"JSON file is not valid UTF-8: {json_file}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON file: {json_file}\n{exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise ValueError(
            f"JSON file must contain one top-level object: "
            f"{json_file}"
        )

    return loaded_data