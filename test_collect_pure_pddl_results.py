from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.collect_refinement_results import (
    load_run_rows,
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(
            message
        )


def write_json(
    path: Path,
    data: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    print("=" * 72)
    print("PURE PDDL RESULT COLLECTION TEST")
    print("=" * 72)

    with tempfile.TemporaryDirectory(
        prefix="pure_pddl_collection_"
    ) as temporary_directory:

        root = Path(
            temporary_directory
        )

        refinement_root = (
            root / "refinement"
        )

        pure_pddl_root = (
            root / "pure_pddl"
        )

        # Ensure both experiment roots exist.
        refinement_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        pure_run_directory = (
            pure_pddl_root
            / "occlusion_manipulation"
            / "occlusion_hard"
            / "run_test"
        )

        summary_file = (
            pure_run_directory
            / "run_summary.json"
        )

        write_json(
            summary_file,
            {
                "scene": "occlusion_hard",
                "domain":
                    "occlusion_manipulation",
                "method": "pure_pddl",
                "planner":
                    "fast_downward",
                "planner_alias":
                    "lama-first",
                "success": True,
                "plan_steps": 14,
                "planner_return_code": 0,
                "planner_runtime_seconds":
                    0.5,
                "symbolic_valid": True,
                "val_valid": True,
                "val_return_code": 0,
                "val_runtime_seconds":
                    0.125,
                "run_directory":
                    str(
                        pure_run_directory
                    ),
            },
        )

        rows = load_run_rows(
            results_roots=(
                refinement_root,
                pure_pddl_root,
            )
        )

        require(
            len(rows) == 1,
            (
                "Expected exactly one "
                "Pure PDDL run row."
            ),
        )

        row = rows[0]

        require(
            row["scene"]
            == "occlusion_hard",
            "Scene ID was incorrect.",
        )

        require(
            row["method"]
            == "pure_pddl",
            "Method was incorrect.",
        )

        require(
            row["mode"]
            == "pddl",
            "Pure PDDL mode was incorrect.",
        )

        require(
            row["provider"] == "",
            (
                "Pure PDDL should not have "
                "an LLM provider."
            ),
        )

        require(
            row["model"]
            == "fast_downward",
            (
                "Planner was not mapped into "
                "the common model column."
            ),
        )

        require(
            row["success"] is True,
            "Pure PDDL success was lost.",
        )

        require(
            row["first_attempt_valid"]
            is True,
            (
                "Single Pure PDDL attempt "
                "should be marked valid."
            ),
        )

        require(
            row["iterations"] == 1,
            (
                "Pure PDDL should use one "
                "common-schema iteration."
            ),
        )

        require(
            row["first_plan_length"]
            == 14,
            (
                "Pure PDDL plan length "
                "was incorrect."
            ),
        )

        require(
            row["final_plan_length"]
            == 14,
            (
                "Pure PDDL final plan length "
                "was incorrect."
            ),
        )

        require(
            row[
                "total_val_runtime_seconds"
            ]
            == 0.125,
            (
                "Pure PDDL VAL runtime "
                "was incorrect."
            ),
        )

        require(
            row["first_failed_step"]
            == "",
            (
                "Pure PDDL should not invent "
                "LLM failure details."
            ),
        )

        print()
        print(
            "Pure PDDL schema detection : SUCCESS"
        )

        print(
            "Common row normalisation   : SUCCESS"
        )

        print(
            "Planner identity mapping   : SUCCESS"
        )

        print(
            "VAL runtime mapping        : SUCCESS"
        )

        print(
            "LLM-only fields remain empty: SUCCESS"
        )

    print()
    print("=" * 72)
    print(
        "ALL PURE PDDL COLLECTION TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()