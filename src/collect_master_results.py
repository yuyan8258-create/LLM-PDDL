from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


DOMAIN_SOURCES = {
    "block": Path("results/formal"),
    "occlusion": Path("results/occlusion_formal"),
    "gearbox": Path("results/gearbox_formal"),
}

SCENE_DIFFICULTY = {
    "scene_01_blocksworld_basic": "easy",
    "scene_02_pyramid": "medium",
    "scene_03_large_pyramid": "hard",
    "occlusion_easy": "easy",
    "occlusion_medium": "medium",
    "occlusion_hard": "hard",
    "gearbox_easy": "easy",
    "gearbox_medium": "medium",
    "gearbox_hard": "hard",
}

EXPECTED_RUNS_PER_DOMAIN = 210
EXPECTED_GROUPS_PER_DOMAIN = 21
EXPECTED_RUNS_PER_GROUP = 10
EXPECTED_TOTAL_RUNS = 630
EXPECTED_TOTAL_GROUPS = 63


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect Block, Occlusion, and Gearbox formal experiment results "
            "into cross-domain master summary tables."
        )
    )
    parser.add_argument(
        "--block-base",
        type=Path,
        default=DOMAIN_SOURCES["block"],
        help="Block formal results base directory.",
    )
    parser.add_argument(
        "--occlusion-base",
        type=Path,
        default=DOMAIN_SOURCES["occlusion"],
        help="Occlusion formal results base directory.",
    )
    parser.add_argument(
        "--gearbox-base",
        type=Path,
        default=DOMAIN_SOURCES["gearbox"],
        help="Gearbox formal results base directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/master_summary"),
        help="Directory for cross-domain summary CSV files.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def truthy(value: str) -> bool:
    return str(value).strip().lower() == "true"


def add_domain_metadata(
    rows: list[dict[str, str]],
    domain: str,
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []

    for row in rows:
        scene = row["scene"]

        if scene not in SCENE_DIFFICULTY:
            raise ValueError(
                f"Unknown scene '{scene}' while collecting domain '{domain}'."
            )

        enriched.append(
            {
                "domain": domain,
                "difficulty": SCENE_DIFFICULTY[scene],
                **row,
            }
        )

    return enriched


def audit_domain(
    domain: str,
    runs: list[dict[str, object]],
    summaries: list[dict[str, object]],
) -> None:
    if len(runs) != EXPECTED_RUNS_PER_DOMAIN:
        raise ValueError(
            f"{domain}: expected {EXPECTED_RUNS_PER_DOMAIN} runs, "
            f"found {len(runs)}."
        )

    if len(summaries) != EXPECTED_GROUPS_PER_DOMAIN:
        raise ValueError(
            f"{domain}: expected {EXPECTED_GROUPS_PER_DOMAIN} summary groups, "
            f"found {len(summaries)}."
        )

    for row in summaries:
        total_runs = int(str(row["total_runs"]))

        if total_runs != EXPECTED_RUNS_PER_GROUP:
            raise ValueError(
                f"{domain}: group "
                f"{row['scene']} / {row['method']} / {row['model']} "
                f"contains {total_runs} runs instead of "
                f"{EXPECTED_RUNS_PER_GROUP}."
            )


def build_success_matrix(
    summaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for row in summaries:
        rows.append(
            {
                "domain": row["domain"],
                "difficulty": row["difficulty"],
                "scene": row["scene"],
                "method": row["method"],
                "provider": row["provider"],
                "model": row["model"],
                "total_runs": int(str(row["total_runs"])),
                "first_attempt_successes": int(
                    str(row["first_attempt_successes"])
                ),
                "first_attempt_success_rate": float(
                    str(row["first_attempt_success_rate"])
                ),
                "final_successes": int(str(row["final_successes"])),
                "final_success_rate": float(
                    str(row["final_success_rate"])
                ),
                "average_iterations": float(
                    str(row["average_iterations"])
                ),
            }
        )

    return rows


def build_method_summary(
    summaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "total_runs": 0,
            "first_attempt_successes": 0,
            "final_successes": 0,
            "weighted_iterations": 0.0,
        }
    )

    for row in summaries:
        method = str(row["method"])
        total_runs = int(str(row["total_runs"]))
        average_iterations = float(str(row["average_iterations"]))

        grouped[method]["total_runs"] += total_runs
        grouped[method]["first_attempt_successes"] += int(
            str(row["first_attempt_successes"])
        )
        grouped[method]["final_successes"] += int(
            str(row["final_successes"])
        )
        grouped[method]["weighted_iterations"] += (
            average_iterations * total_runs
        )

    output: list[dict[str, object]] = []

    for method in ("pure_pddl", "pure_llm", "hybrid_feedback"):
        values = grouped[method]
        total = int(values["total_runs"])

        output.append(
            {
                "method": method,
                "total_runs": total,
                "first_attempt_successes": int(
                    values["first_attempt_successes"]
                ),
                "first_attempt_success_rate": (
                    values["first_attempt_successes"] / total
                ),
                "final_successes": int(values["final_successes"]),
                "final_success_rate": values["final_successes"] / total,
                "average_iterations": (
                    values["weighted_iterations"] / total
                ),
            }
        )

    return output


def main() -> None:
    args = parse_args()

    sources = {
        "block": args.block_base,
        "occlusion": args.occlusion_base,
        "gearbox": args.gearbox_base,
    }

    master_runs: list[dict[str, object]] = []
    master_summaries: list[dict[str, object]] = []

    print("=" * 78)
    print("MASTER FORMAL RESULT COLLECTION")
    print("=" * 78)

    for domain, base in sources.items():
        runs_path = base / "tables" / "refinement_runs.csv"
        summary_path = (
            base / "tables" / "refinement_model_summary.csv"
        )

        runs = add_domain_metadata(
            read_csv(runs_path),
            domain,
        )
        summaries = add_domain_metadata(
            read_csv(summary_path),
            domain,
        )

        audit_domain(domain, runs, summaries)

        master_runs.extend(runs)
        master_summaries.extend(summaries)

        print(
            f"{domain.capitalize():10s}: "
            f"{len(runs):3d} runs | "
            f"{len(summaries):2d} groups | PASS"
        )

    if len(master_runs) != EXPECTED_TOTAL_RUNS:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL_RUNS} total runs, "
            f"found {len(master_runs)}."
        )

    if len(master_summaries) != EXPECTED_TOTAL_GROUPS:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL_GROUPS} total groups, "
            f"found {len(master_summaries)}."
        )

    success_matrix = build_success_matrix(master_summaries)
    method_summary = build_method_summary(master_summaries)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    master_run_fields = list(master_runs[0].keys())
    master_summary_fields = list(master_summaries[0].keys())
    success_fields = list(success_matrix[0].keys())
    method_fields = list(method_summary[0].keys())

    write_csv(
        output / "master_runs.csv",
        master_runs,
        master_run_fields,
    )
    write_csv(
        output / "master_group_summary.csv",
        master_summaries,
        master_summary_fields,
    )
    write_csv(
        output / "success_matrix.csv",
        success_matrix,
        success_fields,
    )
    write_csv(
        output / "method_summary.csv",
        method_summary,
        method_fields,
    )

    print("-" * 78)
    print(f"Total runs  : {len(master_runs)}")
    print(f"Total groups: {len(master_summaries)}")
    print("-" * 78)

    for row in method_summary:
        print(
            f"{row['method']:18s} "
            f"{row['final_successes']:3d}/{row['total_runs']:3d} "
            f"= {row['final_success_rate']:.1%}"
        )

    pure_llm = next(
        row
        for row in method_summary
        if row["method"] == "pure_llm"
    )
    hybrid = next(
        row
        for row in method_summary
        if row["method"] == "hybrid_feedback"
    )

    hybrid_gain = (
        float(hybrid["final_success_rate"])
        - float(pure_llm["final_success_rate"])
    )

    print("-" * 78)
    print(f"Hybrid gain vs Pure LLM: {hybrid_gain:+.1%}")
    print(f"Output directory       : {output.resolve()}")
    print("=" * 78)
    print("MASTER AUDIT: PASS")
    print("=" * 78)


if __name__ == "__main__":
    main()