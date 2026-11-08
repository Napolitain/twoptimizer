"""Read-only presentation of HoI4 source facts and declared base requirements."""

from collections import Counter
from typing import Any

from games.hoi4.data_pipeline import public_import, resolved_import
from games.hoi4.data_pipeline.dependencies import build_dependency_report
from games.hoi4.data_pipeline.patch_overlay import apply_patch_overlays
from games.hoi4.data_pipeline.template_requirements import summarize_template_requirements
from games.hoi4.planning.time import CampaignDate
from twoptimizer.errors import ApplicationError

COUNTRIES = public_import.COUNTRIES
FACTORY_FIELDS = ("industrial_complex", "arms_factory", "dockyard")


def inspect_reference(country: str = "FRA") -> dict[str, Any]:
    """Give both interfaces caller-owned evidence, preserving unresolved statements."""
    tag = country.upper()
    if tag != "ALL" and tag not in COUNTRIES:
        raise ApplicationError(
            f"Unknown HoI4 country {country!r}; choose {', '.join(COUNTRIES)} or all"
        )
    try:
        manifest = public_import.load_reference_manifest()
        profiles = [
            public_import.load_reference_country(key) for key in COUNTRIES if tag in (key, "ALL")
        ]
        equipment = public_import.load_reference_equipment()
        dependencies = build_dependency_report(equipment, countries=profiles, include_graph=False)
        equipment, template_patches = apply_patch_overlays(equipment)
        _attach_template_requirements(profiles, equipment)
    except (OSError, ValueError) as error:
        raise ApplicationError(
            f"Cannot read HoI4 reference data: {error}", code="reference_data"
        ) from error
    resolved = _attach_resolved_data(profiles)
    return {
        "schema_version": 1,
        "game": "hoi4",
        "kind": "reference_data",
        "scenario_ready": False,
        "manifest": manifest,
        "countries": profiles,
        "dependencies": dependencies,
        "template_patch_corrections": template_patches,
        "resolved_reference": resolved,
    }


def _attach_resolved_data(profiles: list[dict]) -> dict:
    """Keep raw inspection usable if a supplementary artifact is absent or invalid."""
    try:
        manifest = resolved_import.load_resolved_manifest()
        summary = _resolved_manifest_summary(manifest)
    except (OSError, ValueError, KeyError) as error:
        for profile in profiles:
            profile["derived_error"] = str(error)
        return {"available": False, "scenario_ready": False, "error": str(error)}
    summary.update(available=True, country_errors={})
    for profile in profiles:
        try:
            profile["derived"] = resolved_import.load_resolved_country(profile["tag"])
        except (OSError, ValueError, KeyError) as error:
            summary["country_errors"][profile["tag"]] = str(error)
            profile["derived_error"] = str(error)
    return summary


def _resolved_manifest_summary(manifest: dict) -> dict:
    return {
        key: manifest[key]
        for key in (
            "schema_version",
            "kind",
            "source",
            "target",
            "start",
            "tutorial",
            "enabled_gameplay_dlc",
            "full_version_validated",
            "scenario_ready",
            "scope",
            "equipment_counts",
            "patch_counts",
        )
    }


def _attach_template_requirements(profiles: list[dict], equipment: dict) -> None:
    for profile in profiles:
        for candidate in profile["oob_candidates"]:
            for template in candidate["templates"]:
                template["base_requirements"] = summarize_template_requirements(template, equipment)


def template_requirements_summary(report: dict) -> str:
    summaries = [
        template["base_requirements"]
        for profile in report["countries"]
        for candidate in profile["oob_candidates"]
        for template in candidate["templates"]
    ]
    complete = sum(summary["base_requirements_complete"] for summary in summaries)
    return (
        f"  Base template requirements: {complete}/{len(summaries)} variants have complete "
        "base totals with sourced patch corrections; effective requirements remain unresolved."
    )


def literal_building(state: dict, field: str) -> str:
    """Show declarations individually: missing fields do not imply zero capacity."""
    values = [
        str(item["value"])
        for block in state["base_building_blocks"]
        for item in block["declarations"]
        if item["field"] == field
    ]
    return ", ".join(values) if values else "—"


def state_row(state: dict) -> tuple[str, ...]:
    return (
        str(state["id"]),
        state["name_key"],
        state["category"] or "—",
        *(literal_building(state, field) for field in (*FACTORY_FIELDS, "infrastructure")),
    )


def country_summary(profile: dict) -> str:
    totals = profile["literal_state_totals"]
    selection = profile.get("source_selection")
    candidates = (
        f"{len(selection['oob_references'])} candidate OOB references"
        if selection is not None
        else "source selection unavailable"
    )
    return (
        f"{profile['name']} ({profile['tag']}) · {totals['state_count']} state records\n"
        f"Literal declarations: {totals['industrial_complex']} civilian factories · "
        f"{totals['arms_factory']} military factories · {totals['dockyard']} dockyards.\n"
        f"{len(profile['oob_candidates'])} source OOB variants; {candidates}; "
        f"{len(profile['unresolved_country_statements'])} unresolved country statements."
    )


def source_selection_summary(profile: dict) -> str:
    selection = profile.get("source_selection")
    if selection is None:
        return f"{profile['tag']}: source selection unavailable; source variants retained."
    references = ", ".join(str(item["value"]) for item in selection["oob_references"])
    return (
        f"{profile['tag']}: partial source selection at "
        f"{CampaignDate.from_dict(selection['start'])}; "
        f"{len(selection['enabled_gameplay_dlc'])} sourced gameplay DLC enabled.\n"
        f"  {len(selection['decisions'])} control-flow decisions; "
        f"{len(selection['blockers'])} unknown-condition blockers; "
        f"{len(selection['unexecuted_statements'])} unexecuted statements.\n"
        f"  Candidate OOB references: {references or 'none recorded'}.\n"
        "  Raw selection remains partial; supported derived facts appear in Army/Economy."
    )


def requested_ruleset_summary(manifest: dict) -> str:
    policy = manifest.get("requested_ruleset", {}).get("gameplay_dlc_policy")
    label = "all enabled" if policy == "all_enabled" else policy or "not specified"
    return f"Requested gameplay DLC: {label}; source validation remains incomplete."


def state_source(state: dict) -> str:
    source = state["source"]
    unresolved = len(state["unresolved_history_statements"]) + len(
        state["unresolved_state_statements"]
    )
    unresolved += sum(
        len(block["unresolved_statements"]) for block in state["base_building_blocks"]
    )
    return (
        f"State {state['id']} · {source['path']}\nSHA-256 {source['sha256']}\n"
        f"{unresolved} unresolved state/history/building statements. "
        "— means not declared; repeated values remain separate declarations."
    )


def source_diagnostic(diagnostic: dict) -> str:
    details = [diagnostic["status"]]
    for field, label in (
        ("excluded_from_line", "excluded from line"),
        ("unclosed_parent_line", "unclosed parent at line"),
        ("recovered_complete_children", "complete child statements recovered"),
    ):
        if field in diagnostic:
            details.append(f"{label}: {diagnostic[field]}")
    return f"  {diagnostic['path']}: {diagnostic['error']} ({'; '.join(details)})"


def source_summary(report: dict) -> str:
    manifest = report["manifest"]
    source, target = manifest["source"], manifest["requested_target"]
    references = report["dependencies"]["counts"]["reference_issues"]
    lines = [
        "HOI4 PUBLIC REFERENCE DATA · PROVISIONAL",
        f"Requested target: {target['version']} / {target['checksum']} "
        f"(checked {target['checked_at']}).",
        "Source patch unverified; this reference is not validated against the requested target.",
        f"Repository: {source['repository']}",
        f"Revision: {source['revision']}",
        f"Retrieved: {source['retrieved_at_utc']}",
        requested_ruleset_summary(manifest),
        "Literal import semantics: " + manifest["semantics"],
        "",
        "Partial country source selection:",
        *(source_selection_summary(profile) for profile in report["countries"]),
        "",
        "Source coverage:",
        *(f"  {key.replace('_', ' ')}: {value}" for key, value in manifest["coverage"].items()),
        "  Declared dependencies: "
        f"{references.get('missing_reference', 0)} missing, "
        f"{references.get('ambiguous_reference', 0)} ambiguous, "
        f"{references.get('nonliteral_reference', 0)} nonliteral references.",
        "  Dependency checks do not resolve inheritance or establish gameplay feasibility.",
        template_requirements_summary(report),
        resolved_summary(report),
        "",
        "Source diagnostics:",
    ]
    for diagnostic in manifest["source_diagnostics"]:
        lines.append(source_diagnostic(diagnostic))
    if not manifest["source_diagnostics"]:
        lines.append("  None recorded.")
    lines.extend(
        ["", "Gameplay optimizer unavailable: no validated starting scenario or feasibility model."]
    )
    return "\n".join(lines)


def format_reference(report: dict) -> str:
    return "\n\n".join(
        [
            source_summary(report),
            *(
                "\n\n".join(
                    (country_summary(profile), army_summary(profile), economy_summary(profile))
                )
                for profile in report["countries"]
            ),
        ]
    )


def resolved_summary(report: dict) -> str:
    derived = report["resolved_reference"]
    if not derived["available"]:
        return f"  Derived reference unavailable: {derived['error']}"
    equipment = derived["equipment_counts"]
    statuses = equipment["statuses"]
    patches = derived["patch_counts"]
    unsupported_patches = sum(
        count
        for status, count in patches.items()
        if status not in {"applied", "already_target_value"}
    )
    errors = derived["country_errors"]
    lines = [
        f"  Equipment base economics: {statuses.get('resolved_base', 0)}/{equipment['equipment']} "
        f"resolved; {statuses.get('partial', 0)} partial; "
        f"{statuses.get('unresolved', 0)} unresolved.",
        f"  Sourced patch corrections: {patches.get('applied', 0)} applied; "
        f"{patches.get('already_target_value', 0)} already at target value; "
        f"{unsupported_patches} unsupported corrections.",
        "  Covered fields only; the full source version and gameplay scenario remain unvalidated.",
    ]
    lines.extend(f"  {tag} derived data unavailable: {error}" for tag, error in errors.items())
    return "\n".join(lines)


def _value(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:g}" if isinstance(value, float) else str(value)


def _values(values: dict) -> str:
    return ", ".join(f"{field}: {_value(value)}" for field, value in sorted(values.items()))


def _unavailable(profile: dict) -> str:
    return "Derived data unavailable: " + profile.get("derived_error", "supplement not loaded")


def army_summary(profile: dict) -> str:
    """Selected source roster and requirements, distinct from combat-ready troops."""
    if "derived" not in profile:
        return _unavailable(profile)
    army = profile["derived"]["army"]
    totals = army["summary"]
    counts = Counter(row["template_index"] for row in army["divisions"])
    lines = [
        "ARMY · selected source roster; readiness unresolved",
        f"{totals['division_count']} deployed division records · "
        f"{totals['template_count']} templates · "
        f"{totals['production_line_count']} production-line declarations.",
        "Selected OOBs: " + ", ".join(row["name"] for row in army["selected_oobs"]),
        f"Full-strength base manpower requirement: {_value(totals['full_manpower_requirement'])}.",
        "Full-strength base equipment: " + _values(totals["full_equipment_requirements"]),
        f"Complete equipment allocation targets: {totals['equipment_allocation_targets_complete']}"
        f"/{totals['division_count']}; resolved manpower allocations: "
        f"{totals['manpower_allocations_resolved']}/{totals['division_count']}.",
        "These allocation targets do not establish actual inventory or trained readiness.",
        "Reserve stockpiles: "
        + ("unresolved" if army["stockpile_totals"] is None else str(army["stockpile_totals"])),
        "",
        "Templates · deployed records / base manpower / base training days:",
    ]
    lines.extend(
        f"  {row['name']}: {counts[index]} / {_value(row['base_manpower'])} / "
        f"{_value(row['base_training_days'])}"
        for index, row in enumerate(army["templates"])
    )
    lines.append(
        f"\nArmy blockers: {len(army['blockers'])}; "
        f"unhandled startup effects: {len(army['unhandled_army_effects'])}."
    )
    return "\n".join(lines)


def economy_summary(profile: dict) -> str:
    """Present base capacity and selected contributions without claiming effective output."""
    if "derived" not in profile:
        return _unavailable(profile)
    derived = profile["derived"]
    states, modifiers = derived["states"], derived["modifiers"]
    totals = states["totals"]
    factories = totals["declared_factories"]
    variants = derived["variants"]
    resolved_variants = sum(row["status"] == "resolved_variant_base" for row in variants)
    return "\n".join(
        [
            "ECONOMY · source base facts; effective capacity unresolved",
            f"Factories: {_value(factories['industrial_complex'])} CIV · "
            f"{_value(factories['arms_factory'])} MIL · {_value(factories['dockyard'])} dockyards.",
            "Shared building slots: "
            f"{_value(totals['category_shared_slot_capacity'])} category base; "
            f"{_value(totals['declared_shared_slots_used'])} declared use.",
            "Category slots are not effective free construction slots.",
            f"Base population: {_value(totals['base_population'])}; "
            f"core population: {_value(totals['base_core_population'])} "
            "(not recruitable manpower).",
            "Base resource deposits: " + _values(totals["declared_resource_deposits"]),
            "Deposits exclude extraction modifiers, trade and access limits.",
            f"State unknowns: {len(states['unknowns'])}; gap categories: "
            + _values(states["gap_counts"]),
            "",
            f"Selected country modifiers: {len(modifiers['contributions'])} contributions; "
            f"{len(modifiers['blockers'])} blockers; "
            f"{len(modifiers['blocked_fields'])} blocked fields.",
            "Additive contributions (source numeric units):",
            *(
                f"  {field}: {_value(value)}"
                for field, value in sorted(modifiers["additive_modifiers"].items())
            ),
            "Consumer-goods factor product: " + _value(modifiers["consumer_goods_factor_product"]),
            "Landmark contributions under declared ownership: "
            + (_values(states["landmark_country_modifiers"]) or "none selected"),
            f"Named variant base economics: {resolved_variants}/{len(variants)} resolved; "
            "country/MIO modifiers and equipment eligibility remain separate.",
            "No income, available construction capacity or campaign feasibility is asserted.",
        ]
    )
