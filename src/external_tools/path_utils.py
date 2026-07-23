from __future__ import annotations

import re
from pathlib import Path


class WSLPathError(RuntimeError):
    """Raised when a Windows path cannot be converted to a WSL path."""


def to_wsl_path(path: str | Path) -> str:
    """
    Convert a Windows path into a WSL path.

    Example:
        E:\\桌面\\LLM-PDDL\\generated_pddl\\domain.pddl

    becomes:
        /mnt/e/桌面/LLM-PDDL/generated_pddl/domain.pddl
    """
    windows_path = str(Path(path).resolve())

    match = re.match(r"^([A-Za-z]):[\\/](.*)$", windows_path)

    if not match:
        raise WSLPathError(
            "Expected an absolute Windows drive path, "
            f"but received: {windows_path}"
        )

    drive_letter = match.group(1).lower()
    remaining_path = match.group(2).replace("\\", "/")

    return f"/mnt/{drive_letter}/{remaining_path}"