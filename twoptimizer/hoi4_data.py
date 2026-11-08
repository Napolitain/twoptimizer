"""Read-only presentation of HoI4 source facts and declared base requirements."""

from typing import Any

from games.hoi4.data_pipeline import public_import
from games.hoi4.data_pipeline.dependencies import build_dependency_report
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
        _attach_template_requirements(profiles, equipment)
    except (OSError, ValueError) as error:
        raise ApplicationError(
            f"Cannot read HoI4 reference data: {error}", code="reference_data"
        ) from error
    return {
        "schema_version": 1,
        "game": "hoi4",
        "kind": "reference_data",
        "scenario_ready": False,
        "manifest": manifest,
        "countries": profiles,
        "dependencies": dependencies,
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
        "literal totals; effective requirements remain unresolved."
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
        "  Country starting state remains unresolved; effects are not executed."
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
        manifest["semantics"],
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
        "",
        "Source diagnostics:",
    ]
    for diagnostic in manifest["source_diagnostics"]:
        lines.append(source_diagnostic(diagnostic))
    if not manifest["source_diagnostics"]:
        lines.append("  None recorded.")
    lines.extend(
        ["", "Gameplay optimizer unavailable: no validated starting scenario or evaluated effects."]
    )
    return "\n".join(lines)


def format_reference(report: dict) -> str:
    return "\n\n".join(
        [source_summary(report), *(country_summary(profile) for profile in report["countries"])]
    )
