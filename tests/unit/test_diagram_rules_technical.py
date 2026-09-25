"""Technical consistency rules a, c and d (task T075; FR-079 a, c, d, FR-081, determinism 11).

Each rule has a passing and a failing fixture, and each finding clears when a configured confirmer
overrides the criterion it belongs to.
"""

from __future__ import annotations

import pytest
from eil.diagrams import (
    component_problems,
    element_names,
    external_names,
    parse_diagram,
    sequence_problems,
    store_problems,
    zoom_problems,
)
from eil.gates import check_stage
from eil.package import Package

from tests.helpers.package import (
    COMPONENT_DIAGRAM,
    CONTAINER_DIAGRAM,
    CONTEXT_DIAGRAM,
    TECHNICAL_SEQUENCE,
    Story,
    record_block,
    with_technical,
)


def parsed(text: str):
    diagram = parse_diagram(text)
    assert not diagram.findings, diagram.findings
    return diagram


CONTEXT = parsed(CONTEXT_DIAGRAM)
CONTAINERS = parsed(CONTAINER_DIAGRAM)
COMPONENTS = parsed(COMPONENT_DIAGRAM)
SEQUENCE = parsed(TECHNICAL_SEQUENCE)


# ---- what counts as external


def test_people_and_external_systems_are_external_and_the_system_itself_is_not() -> None:
    assert external_names(CONTEXT) == {"data analyst": "Data Analyst", "crm": "CRM"}
    assert external_names(CONTAINERS) == {"data analyst": "Data Analyst", "crm": "CRM"}


def test_names_compare_without_regard_to_case_or_spacing() -> None:
    other = parsed(CONTAINER_DIAGRAM.replace('"Data Analyst"', '"data   ANALYST"'))
    assert set(external_names(other)) == set(external_names(CONTEXT))


# ---- rule a, level 2 against level 1 (FR-079 a)


def test_rule_a_passes_when_the_externals_match() -> None:
    assert zoom_problems(CONTEXT, CONTAINERS) == []


def test_rule_a_names_a_renamed_external_on_both_sides() -> None:
    renamed = parsed(CONTAINER_DIAGRAM.replace('"CRM"', '"Salesforce"'))
    problems = zoom_problems(CONTEXT, renamed)
    assert len(problems) == 2
    assert any("'Salesforce'" in p and "system context" in p for p in problems)
    assert any("'CRM'" in p and "container diagram" in p for p in problems)


def test_rule_a_reports_an_external_missing_from_the_container_diagram() -> None:
    lacking = parsed("\n".join(ln for ln in CONTAINER_DIAGRAM.splitlines() if "crm" not in ln.lower()))
    problems = zoom_problems(CONTEXT, lacking)
    assert problems and "'CRM'" in problems[0]


def test_rule_a_reports_an_external_that_the_context_diagram_does_not_have() -> None:
    extra = parsed(
        CONTAINER_DIAGRAM.replace(
            "  System_Boundary", '  System_Ext(mail, "Mail", "[new] Sends mail")\n  System_Boundary'
        )
    )
    problems = zoom_problems(CONTEXT, extra)
    assert len(problems) == 1 and "'Mail'" in problems[0]


# ---- rule a, level 3 names a level 2 container (FR-079 a)


def test_rule_a_passes_for_a_component_diagram_inside_a_container_of_the_container_diagram() -> None:
    assert component_problems(CONTAINERS, COMPONENTS) == []


def test_rule_a_reports_a_component_diagram_that_names_no_container_of_the_container_diagram() -> None:
    other = parsed(COMPONENT_DIAGRAM.replace('"Duplicate Worker"', '"Matching Service"'))
    problems = component_problems(CONTAINERS, other)
    assert len(problems) == 1 and "'Matching Service'" in problems[0] and "container diagram" in problems[0]


def test_rule_a_reports_a_component_diagram_with_no_container_boundary() -> None:
    bare = parsed('C4Component\n  Component(a, "Matcher", "Python", "[new] x")')
    problems = component_problems(CONTAINERS, bare)
    assert len(problems) == 1 and "Container_Boundary" in problems[0]


def test_a_system_boundary_is_not_a_container_boundary() -> None:
    wrong = parsed(
        'C4Component\n  System_Boundary(s, "Duplicate Worker") {\n    Component(a, "Matcher", "Python", "[new] x")\n  }'
    )
    assert "Container_Boundary" in component_problems(CONTAINERS, wrong)[0]


# ---- rule c (FR-079 c)


def test_rule_c_passes_when_every_participant_is_a_diagram_element() -> None:
    known = element_names(CONTAINERS, COMPONENTS)
    assert sequence_problems(SEQUENCE, known) == []


def test_rule_c_accepts_a_component_and_a_person_as_participants() -> None:
    text = "sequenceDiagram\n  participant M as Matcher\n  actor A as Data Analyst\n  A->>M: asks"
    assert sequence_problems(parsed(text), element_names(CONTAINERS, COMPONENTS)) == []


def test_rule_c_names_a_participant_that_is_in_no_c4_diagram() -> None:
    text = TECHNICAL_SEQUENCE.replace(
        "participant Worker as Duplicate Worker", "participant Worker as Rabbit Queue"
    )
    problems = sequence_problems(parsed(text), element_names(CONTAINERS, COMPONENTS))
    assert len(problems) == 1 and "'Rabbit Queue'" in problems[0]


def test_a_functional_sequence_diagram_of_actors_and_the_system_fails_rule_c() -> None:
    text = (
        "sequenceDiagram\n  actor Analyst as Data Analyst\n  participant System\n  Analyst->>System: upload"
    )
    problems = sequence_problems(parsed(text), element_names(CONTAINERS, COMPONENTS))
    assert any("'System'" in p for p in problems)


# ---- rule d (FR-079 d)


def test_rule_d_passes_when_the_store_is_a_database_in_the_container_diagram() -> None:
    assert store_problems("Customer DB", CONTAINERS) == []
    assert store_problems("customer   db", CONTAINERS) == []


def test_rule_d_needs_a_store() -> None:
    problems = store_problems(None, CONTAINERS)
    assert len(problems) == 1 and "(store: NAME)" in problems[0]


def test_rule_d_rejects_a_store_that_is_not_in_the_container_diagram() -> None:
    problems = store_problems("Orders DB", CONTAINERS)
    assert (
        len(problems) == 1 and "'Orders DB'" in problems[0] and "not in the container diagram" in problems[0]
    )


def test_rule_d_rejects_a_store_that_is_not_a_database() -> None:
    problems = store_problems("Import API", CONTAINERS)
    assert len(problems) == 1 and "not a data store" in problems[0]


def test_rule_d_accepts_a_system_database() -> None:
    text = CONTAINER_DIAGRAM.replace(
        "  System_Ext(crm,", '  SystemDb_Ext(ledger, "Ledger", "[existing] Books")\n  System_Ext(crm,'
    )
    assert store_problems("Ledger", parsed(text)) == []


# ---- through the gate: findings, criteria and overrides

OVERRIDE = {
    "id": "OVR-001",
    "stage": "technical",
    "by": "Ada Dev",
    "reason": "the diagram is deliberately partial",
    "at": "2026-09-25T00:00:00Z",
}


def override_of(criterion: str) -> str:
    return record_block("override", {**OVERRIDE, "criterion": criterion})


def gate(story: Story):
    return check_stage(Package(story.root), "technical")


def status(result, criterion: str) -> str:
    return next(c.status for c in result.criteria if c.id == criterion)


DIAGRAM_CRITERIA = ["TEC-G15", "TEC-G16", "TEC-G17", "TEC-G18"]

CASES = [
    pytest.param(
        {"container": CONTAINER_DIAGRAM.replace('"CRM"', '"Salesforce"')},
        "TEC-G15",
        "rule a",
        id="rule-a-externals-differ",
    ),
    pytest.param(
        {"components": COMPONENT_DIAGRAM.replace('"Duplicate Worker"', '"Matching Service"')},
        "TEC-G16",
        "rule a",
        id="rule-a-unknown-container",
    ),
    pytest.param(
        {"sequence": TECHNICAL_SEQUENCE.replace("Duplicate Worker", "Rabbit Queue")},
        "TEC-G17",
        "rule c",
        id="rule-c-unknown-participant",
    ),
    pytest.param({"er_store": "Orders DB"}, "TEC-G18", "rule d", id="rule-d-unknown-store"),
    pytest.param({"er_store": None}, "TEC-G18", "rule d", id="rule-d-no-store"),
    pytest.param({"er_store": "Import API"}, "TEC-G18", "rule d", id="rule-d-not-a-database"),
]


@pytest.mark.parametrize(("kwargs", "criterion", "rule"), CASES)
def test_each_rule_fails_its_criterion_with_an_inconsistency_finding(
    story_dir: Story, kwargs: dict, criterion: str, rule: str
) -> None:
    with_technical(story_dir, **kwargs)
    result = gate(story_dir)
    assert status(result, criterion) == "not-met"
    assert any(f.code == "diagram-inconsistent" and rule in f.message for f in result.findings)
    others = [
        c.id
        for c in result.criteria
        if c.id in DIAGRAM_CRITERIA and c.id != criterion and c.status == "not-met"
    ]
    assert others == [], others


@pytest.mark.parametrize(("kwargs", "criterion", "rule"), CASES)
def test_a_configured_confirmer_can_override_each_rule(
    story_dir: Story, kwargs: dict, criterion: str, rule: str
) -> None:
    with_technical(story_dir, extra=override_of(criterion), **kwargs)
    result = gate(story_dir)
    assert status(result, criterion) == "overridden"
    assert any(f.code == "diagram-inconsistent" for f in result.findings), "the finding stays visible"


def test_a_diagram_at_the_wrong_level_fails_the_gate_and_an_unparseable_one_is_never_skipped(
    story_dir: Story,
) -> None:
    with_technical(story_dir, container='C4Container\n  Container(a, "API", "REST"')
    result = gate(story_dir)
    assert status(result, "TEC-G15") == "not-met"
    assert any(f.code == "diagram-unparseable" for f in result.findings)


def test_a_functional_only_sequence_diagram_in_the_technical_document_fails(story_dir: Story) -> None:
    functional_only = (
        "sequenceDiagram\n  actor Analyst as Data Analyst\n  participant System\n  Analyst->>System: upload"
    )
    with_technical(story_dir, sequence=functional_only)
    result = gate(story_dir)
    assert status(result, "TEC-G17") == "not-met"
    assert any(f.code == "diagram-inconsistent" and "'System'" in f.message for f in result.findings)


def test_the_rules_are_skipped_not_failed_when_the_diagram_they_compare_against_is_absent(
    story_dir: Story,
) -> None:
    with_technical(story_dir, container=None)
    result = gate(story_dir)
    assert status(result, "TEC-G15") == "not-met"
    assert not any(f.code == "diagram-inconsistent" for f in result.findings)


def test_a_missing_context_diagram_upstream_does_not_invent_a_rule_a_failure(story_dir: Story) -> None:
    from tests.helpers.package import requirements_doc

    with_technical(story_dir)
    story_dir.write("requirements", requirements_doc(diagram=None))
    result = gate(story_dir)
    assert status(result, "TEC-G15") == "met"


def test_a_clean_document_has_no_inconsistencies(story_dir: Story) -> None:
    with_technical(story_dir)
    result = gate(story_dir)
    assert not [f for f in result.findings if f.code.startswith("diagram-")]
