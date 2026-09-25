"""Mermaid subset extraction over the fixtures (task T027; determinism 10, FR-080, risk R-10).

The ``*.docs.mmd`` fixtures are verbatim from the Mermaid documentation, so they pin that the
parser reads the syntax Mermaid actually documents. They have not been rendered (see
tests/fixtures/mermaid/VERSION.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eil.diagrams import Diagram, normalise_name, parse_diagram

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mermaid"


def load(name: str) -> Diagram:
    return parse_diagram((FIXTURES / name).read_text(encoding="utf-8"), where=name)


def labels(diagram: Diagram) -> set[str]:
    return {e.label for e in diagram.elements}


def unparseable(diagram: Diagram) -> list[tuple[str, str]]:
    return [(f.where, f.message) for f in diagram.findings if f.code == "diagram-unparseable"]


# ---- names


def test_names_compare_case_insensitively_with_whitespace_collapsed() -> None:
    assert normalise_name("  Data   ANALYST ") == "data analyst"
    assert normalise_name("Data Analyst") == normalise_name("data\tanalyst")


# ---- accepted: verbatim from the Mermaid documentation


def test_c4_context_from_the_docs() -> None:
    d = load("c4context.docs.mmd")
    assert d.kind == "c4-context" and d.findings == []
    assert d.title == "System Context diagram for Internet Banking System"
    assert len(d.elements) == 12
    assert {
        "Banking Customer A",
        "Internet Banking System",
        "Mainframe Banking System",
        "E-mail system",
    } <= labels(d)
    assert [b.label for b in d.boundaries] == [
        "BankBoundary0",
        "BankBoundary",
        "BankBoundary2",
        "BankBoundary3",
    ]
    assert len(d.relations) == 4
    by_alias = {e.alias: e for e in d.elements}
    assert by_alias["customerC"].role == "person" and by_alias["customerC"].external
    assert (
        by_alias["SystemE"].role == "system" and by_alias["SystemE"].database and by_alias["SystemE"].external
    )
    assert by_alias["SystemF"].queue and not by_alias["SystemF"].external
    assert by_alias["SystemG"].queue and by_alias["SystemG"].external
    assert by_alias["SystemA"].boundary == "BankBoundary2"  # the innermost enclosing boundary
    assert by_alias["SystemC"].boundary == "BankBoundary"
    assert by_alias["customerA"].boundary == "BankBoundary0"
    assert (d.relations[2].source, d.relations[2].target, d.relations[2].label) == (
        "SystemAA",
        "SystemC",
        "Sends e-mails",
    )


def test_c4_container_from_the_docs_reads_unquoted_labels_and_named_arguments() -> None:
    d = load("c4container.docs.mmd")
    assert d.kind == "c4-container" and d.findings == []
    assert labels(d) == {
        "E-Mail System",
        "Customer",
        "Single-Page App",
        "Mobile App",
        "Web Application",
        "Database",
        "API Application",
        "Mainframe Banking System",
    }
    assert len(d.relations) == 10
    by_alias = {e.alias: e for e in d.elements}
    assert by_alias["customer"].label == "Customer"  # an unquoted label
    assert by_alias["database"].role == "container" and by_alias["database"].database
    assert by_alias["backend_api"].database and by_alias["backend_api"].external
    assert by_alias["spa"].technology == "JavaScript, Angular"
    assert by_alias["spa"].boundary == "Internet Banking"
    assert by_alias["banking_system"].boundary is None
    assert [b.label for b in d.boundaries] == ["Internet Banking"]


def test_c4_component_from_the_docs() -> None:
    d = load("c4component.docs.mmd")
    assert d.kind == "c4-component" and d.findings == []
    assert len(d.elements) == 8 and len(d.relations) == 8
    assert [b.label for b in d.boundaries] == ["API Application"]
    inside = {e.label for e in d.elements if e.boundary == "API Application"}
    assert inside == {
        "Sign In Controller",
        "Accounts Summary Controller",
        "Security Component",
        "Mainframe Banking System Facade",
    }


def test_sequence_from_the_docs() -> None:
    d = load("sequence.docs.mmd")
    assert d.kind == "sequence" and d.findings == []
    assert [(p.alias, p.label, p.actor, p.declared) for p in d.participants] == [
        ("Customer", "Customer", True, True),
        ("Web", "Web app", False, True),
        ("API", "API gateway", False, True),
        ("Bank", "Bank", False, True),
    ]
    assert len(d.messages) == 6
    assert (d.messages[0].source, d.messages[0].target, d.messages[0].text) == (
        "Customer",
        "Web",
        "Place order",
    )


def test_sequence_with_a_frontmatter_block_from_the_docs() -> None:
    d = load("sequence.frontmatter.docs.mmd")
    assert d.kind == "sequence" and d.findings == []
    assert len(d.participants) == 4 and len(d.messages) == 6


def test_er_from_the_docs() -> None:
    d = load("er.docs.mmd")
    assert d.kind == "er" and d.findings == []
    assert {e.label for e in d.entities} == {"CUSTOMER", "ORDER", "LINE_ITEM", "PRODUCT"}
    customer = next(e for e in d.entities if e.label == "CUSTOMER")
    assert customer.attributes == ["string name", "string email"]
    assert [(r.left, r.right, r.label) for r in d.er_relations] == [
        ("CUSTOMER", "ORDER", "places"),
        ("ORDER", "LINE_ITEM", "contains"),
        ("PRODUCT", "LINE_ITEM", "appears in"),
    ]


def test_er_with_a_frontmatter_block_from_the_docs() -> None:
    d = load("er.frontmatter.docs.mmd")
    assert d.kind == "er" and d.findings == [] and len(d.entities) == 4


# ---- borderline: aliases differ, boundary nesting, implied participants


def test_borderline_c4_context() -> None:
    d = load("c4context.borderline.mmd")
    assert d.findings == []
    by_alias = {e.alias: e for e in d.elements}
    assert by_alias["p1"].label == "Analyst" and by_alias["p1"].description == "Reviews duplicates"
    assert by_alias["core"].label == "Duplicate  Analysis"  # kept as written ...
    assert normalise_name(by_alias["core"].label) == "duplicate analysis"  # ... compared normalised
    assert by_alias["core"].boundary == "Customer Platform" and by_alias["crm"].boundary == "Acme"
    assert by_alias["crm"].description == "External CRM, with a comma"
    assert [(b.label, b.parent) for b in d.boundaries] == [("Acme", None), ("Customer Platform", "Acme")]
    assert [(r.source, r.target) for r in d.relations] == [("p1", "core"), ("crm", "core")]


def test_borderline_c4_container_markers_and_queues() -> None:
    d = load("c4container.borderline.mmd")
    assert d.findings == [] and len(d.relations) == 4
    by_alias = {e.alias: e for e in d.elements}
    assert by_alias["api"].marker == "changed" and by_alias["db"].marker == "existing"
    assert by_alias["q"].queue and by_alias["q"].role == "container"
    assert by_alias["mail"].external and by_alias["mail"].marker is None
    assert by_alias["a"].boundary is None


def test_borderline_c4_component() -> None:
    d = load("c4component.borderline.mmd")
    assert d.findings == []
    by_alias = {e.alias: e for e in d.elements}
    assert by_alias["cache"].role == "component" and by_alias["cache"].database and by_alias["cache"].external
    assert by_alias["web"].boundary is None and by_alias["ctl"].boundary == "Import API"
    assert len(d.relations) == 3


def test_borderline_sequence_has_implied_participants_and_new_participant_syntax() -> None:
    d = load("sequence.borderline.mmd")
    assert d.findings == []
    by_alias = {p.alias: p for p in d.participants}
    assert by_alias["W"].label == "Web app" and by_alias["W"].declared
    assert by_alias["API"].label == "Import API" and by_alias["API"].declared  # participant X@{...} as Label
    assert by_alias["Customer"].label == "Data Analyst" and by_alias["Customer"].actor
    assert not by_alias["Queue"].declared and by_alias["Queue"].label == "Queue"
    assert not by_alias["Worker"].declared
    assert len(d.messages) == 7
    assert {p.label for p in d.participants} == {"Web app", "Import API", "Data Analyst", "Queue", "Worker"}
    assert (d.messages[0].source, d.messages[0].target) == ("Customer", "W")  # `->>+` activation shorthand
    assert (d.messages[-1].source, d.messages[-1].target) == ("W", "Customer")  # `-->>-`


def test_borderline_er_aliases_and_entities_without_attributes() -> None:
    d = load("er.borderline.mmd")
    assert d.findings == []
    by_name = {e.name: e for e in d.entities}
    assert by_name["p"].label == "Person" and by_name["a"].label == "Customer Account"
    assert by_name["LINE-ITEM"].attributes == []
    assert by_name["p"].attributes == ["string firstName PK", "string lastName"]
    assert [(r.left, r.right, r.label) for r in d.er_relations] == [
        ("Person", "Customer Account", "has"),
        ("Customer Account", "LINE-ITEM", "buys"),
    ]


# ---- malformed: never an empty pass, always naming the line (determinism 10)


@pytest.mark.parametrize(
    ("name", "line", "text"),
    [
        ("c4context.malformed.mmd", 5, "Frobnicate"),
        ("c4container.malformed.mmd", 5, "ContainerDb"),
        ("c4component.malformed.mmd", 3, "Component("),
        ("sequence.malformed.mmd", 4, "~~>"),
        ("er.malformed.mmd", 3, "==>"),
    ],
)
def test_a_malformed_fixture_reports_the_offending_line(name: str, line: int, text: str) -> None:
    d = load(name)
    problems = unparseable(d)
    assert len(problems) == 1, problems
    where, message = problems[0]
    assert where == f"{name}:{line}"
    assert text in message


def test_a_malformed_diagram_still_yields_what_it_could_read() -> None:
    d = load("c4context.malformed.mmd")
    assert labels(d) == {"Data Analyst", "Customer Platform"}
    assert len(d.relations) == 1


@pytest.mark.parametrize(
    "text",
    ["", "\n\n", "%% only a comment\n", "flowchart TD\n  A --> B\n", "C4Dynamic\n  title x\n", "graph LR\n"],
)
def test_text_that_is_not_a_supported_diagram_is_unparseable(text: str) -> None:
    d = parse_diagram(text)
    assert d.kind is None
    assert [f.code for f in d.findings] == ["diagram-unparseable"]


def test_a_recognised_diagram_with_nothing_in_it_is_unparseable() -> None:
    for text in ("C4Context\n  title Only a title\n", "sequenceDiagram\n  autonumber\n", "erDiagram\n"):
        d = parse_diagram(text)
        assert d.kind is not None
        assert [f.code for f in d.findings] == ["diagram-unparseable"]
        assert "no recognisable elements" in d.findings[0].message


def test_every_unrecognised_line_is_reported() -> None:
    d = parse_diagram('C4Context\n  Person(a, "A")\n  Bogus(x)\n  Alsobogus(y)\n')
    assert [f.where for f in d.findings] == ["line:3", "line:4"]


def test_unbalanced_boundary_braces_are_reported() -> None:
    closing = parse_diagram('C4Context\n  Person(a, "A")\n}\n')
    assert unparseable(closing) and unparseable(closing)[0][0] == "line:3"
    opening = parse_diagram('C4Context\n  System_Boundary(b, "B") {\n    Person(a, "A")\n')
    assert unparseable(opening) and unparseable(opening)[0][0] == "line:2"


def test_a_boundary_without_a_block_is_reported() -> None:
    assert unparseable(parse_diagram('C4Context\n  System_Boundary(b, "B")\n  Person(a, "A")\n'))


def test_unbalanced_quotes_are_reported() -> None:
    assert unparseable(parse_diagram('C4Context\n  Person(a, "unterminated)\n'))


def test_an_element_needs_an_alias_and_a_label() -> None:
    assert unparseable(parse_diagram("C4Context\n  Person(only)\n  System(s, S)\n"))


def test_a_relation_needs_endpoints_and_a_label() -> None:
    assert unparseable(parse_diagram('C4Context\n  Person(a, "A")\n  System(s, "S")\n  Rel(a, s)\n'))


def test_er_relationship_written_in_words_is_outside_the_subset() -> None:
    d = parse_diagram("erDiagram\n  A only one to zero or more B : has\n")
    assert unparseable(d)


def test_sequence_end_without_a_block_is_reported() -> None:
    assert unparseable(parse_diagram("sequenceDiagram\n  A->>B: hi\n  end\n"))


def test_sequence_block_never_closed_is_reported() -> None:
    assert unparseable(parse_diagram("sequenceDiagram\n  A->>B: hi\n  alt x\n    B->>A: no\n"))


# ---- presentation directives and comments are known and ignored


def test_known_presentation_directives_and_comments_are_ignored() -> None:
    text = (
        '%%{init: {"theme": "dark"}}%%\nC4Context\n  %% a comment\n  title T\n  Person(a, "A")\n'
        '  System(s, "S")\n  Rel(a, s, "uses")\n  UpdateElementStyle(a, $bgColor="red")\n'
        '  updateElementStyle(a, $bgColor="red")\n  UpdateRelStyle(a, s, $offsetX="5")\n'
        '  UpdateLayoutConfig($c4ShapeInRow="3")\n'
    )
    d = parse_diagram(text)
    assert d.findings == [] and len(d.elements) == 2 and d.title == "T"


def test_a_frontmatter_block_does_not_shift_reported_line_numbers() -> None:
    d = parse_diagram("---\ntitle: X\n---\nsequenceDiagram\n  A ~~> B: bad\n")
    assert [f.where for f in d.findings] == ["line:5"]


def test_reported_lines_are_offset_by_where_the_fence_starts_in_the_document() -> None:
    d = parse_diagram(
        'C4Context\n  Person(a, "A")\n  Bogus(x)\n', where="s03-technical-spec.md", first_line=40
    )
    assert [f.where for f in d.findings] == ["s03-technical-spec.md:42"]


def test_kind_is_taken_from_the_first_keyword() -> None:
    kinds = {
        'C4Context\n  Person(a, "A")\n': "c4-context",
        'C4Container\n  Person(a, "A")\n': "c4-container",
        'C4Component\n  Component(c, "C")\n': "c4-component",
        "sequenceDiagram\n  A->>B: x\n": "sequence",
        "erDiagram\n  A ||--o{ B : has\n": "er",
    }
    for text, kind in kinds.items():
        assert parse_diagram(text).kind == kind


def test_a_comma_inside_a_quoted_argument_does_not_split_it() -> None:
    d = parse_diagram('C4Context\n  System(s, "Orders, billing", "Handles orders, and bills")\n')
    assert d.findings == [] and d.elements[0].label == "Orders, billing"
    assert d.elements[0].description == "Handles orders, and bills"


def test_marker_extraction_needs_the_bracketed_word() -> None:
    d = parse_diagram(
        "C4Context\n"
        '  System(a, "A", "[new] shiny")\n'
        '  System(b, "B", "brand new")\n'
        '  System(c, "C", "[changed] x")\n'
    )
    assert [e.marker for e in d.elements] == ["new", None, "changed"]
