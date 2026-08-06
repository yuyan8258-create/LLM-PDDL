from src.domain_config import (
    discover_domain_config_files,
    list_supported_domains,
    load_domain_config,
)
from src.scene_config import (
    list_supported_scenes,
    load_scene_config,
)


def main() -> None:
    print("=" * 72)
    print("DOMAIN CONFIGURATION TEST")
    print("=" * 72)

    discovered_files = discover_domain_config_files()

    if not discovered_files:
        raise AssertionError(
            "No domain configurations were discovered."
        )

    domain_ids = list_supported_domains()

    if domain_ids != sorted(domain_ids):
        raise AssertionError(
            "Domain IDs are not returned in sorted order."
        )

    if set(domain_ids) != set(discovered_files):
        raise AssertionError(
            "list_supported_domains() and "
            "discover_domain_config_files() disagree."
        )

    for domain_id in domain_ids:
        config = load_domain_config(domain_id)

        if config.domain_id != domain_id:
            raise AssertionError(
                f"Loaded domain ID mismatch for {domain_id}."
            )

        if not config.domain_file.exists():
            raise AssertionError(
                f"Domain PDDL file does not exist: "
                f"{config.domain_file}"
            )

        if not config.domain_config_file.exists():
            raise AssertionError(
                f"Domain config file does not exist: "
                f"{config.domain_config_file}"
            )

        if not config.predicate_arities:
            raise AssertionError(
                f"Domain '{domain_id}' has no predicates."
            )

        if not config.action_arities:
            raise AssertionError(
                f"Domain '{domain_id}' has no actions."
            )

        print()
        print(f"Domain ID        : {config.domain_id}")
        print(
            f"PDDL domain name : "
            f"{config.pddl_domain_name}"
        )
        print(f"Adapter          : {config.adapter}")
        print(
            f"Predicate count  : "
            f"{len(config.predicate_arities)}"
        )
        print(
            f"Action count     : "
            f"{len(config.action_arities)}"
        )
        print(
            f"Predicates       : "
            f"{sorted(config.predicate_arities)}"
        )
        print(
            f"Actions          : "
            f"{sorted(config.action_arities)}"
        )
        print(f"Domain file      : {config.domain_file}")
        print(
            f"Config file      : "
            f"{config.domain_config_file}"
        )

    print()
    print("-" * 72)
    print("CHECKING SCENE-TO-DOMAIN LINKS")
    print("-" * 72)

    for scene_id in list_supported_scenes():
        scene = load_scene_config(scene_id)
        domain = load_domain_config(scene.domain_id)

        if scene.domain_file != domain.domain_file:
            raise AssertionError(
                f"Scene '{scene_id}' domain path does not match "
                f"loaded domain '{domain.domain_id}'."
            )

        print(
            f"{scene_id} -> {domain.domain_id} "
            f"({domain.domain_file})"
        )

    print()
    print("=" * 72)
    print("ALL DOMAIN CONFIGURATIONS LOADED SUCCESSFULLY")
    print("=" * 72)


if __name__ == "__main__":
    main()