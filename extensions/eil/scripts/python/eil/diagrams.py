"""Line-oriented extraction of Mermaid diagrams (task T028; FR-079..081, research D-20, D-21).

This is not a Mermaid parser and it never renders. It reads a stated subset, one statement per
line, well enough to list the elements and relations the consistency rules compare (contracts/
document-format.md §Accepted Mermaid subset). Anything outside the subset is a
``diagram-unparseable`` finding that names the line, and a diagram that yields nothing is one
too, so a problem is never an empty pass (FR-080). Mermaid's C4 support is experimental
(risk R-10): the constructs recognised here are pinned by ``tests/fixtures/mermaid``.

Element names compare case-insensitively with whitespace collapsed (``normalise_name``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .results import Finding

KIND_KEYWORDS = {
    "C4Context": "c4-context",
    "C4Container": "c4-container",
    "C4Component": "c4-component",
    "sequenceDiagram": "sequence",
    "erDiagram": "er",
}


def normalise_name(name: str) -> str:
    return " ".join(name.split()).casefold()


@dataclass
class Element:
    alias: str
    label: str
    role: str  # person | system | container | component
    external: bool = False
    database: bool = False
    queue: bool = False
    technology: str = ""
    description: str = ""
    marker: str | None = None  # existing | new | changed, from the description
    boundary: str | None = None  # label of the innermost enclosing boundary
    line: int = 0


@dataclass
class Boundary:
    alias: str
    label: str
    macro: str
    parent: str | None
    line: int


@dataclass
class Relation:
    source: str  # aliases as written
    target: str
    label: str
    line: int


@dataclass
class Participant:
    alias: str
    label: str
    actor: bool
    declared: bool
    line: int


@dataclass
class Message:
    source: str
    target: str
    text: str
    line: int


@dataclass
class Entity:
    name: str  # the identifier as written (an alias when one is given)
    label: str
    attributes: list[str] = field(default_factory=list)
    declared: bool = True
    line: int = 0


@dataclass
class ErRelation:
    left: str  # display labels
    right: str
    cardinality: str
    label: str
    line: int


@dataclass
class Diagram:
    kind: str | None = None
    title: str | None = None
    elements: list[Element] = field(default_factory=list)
    boundaries: list[Boundary] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    er_relations: list[ErRelation] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def names(self) -> set[str]:
        """Normalised display names of everything the diagram declares or implies."""
        found = {normalise_name(e.label) for e in self.elements}
        found |= {normalise_name(b.label) for b in self.boundaries}
        found |= {normalise_name(p.label) for p in self.participants}
        found |= {normalise_name(e.label) for e in self.entities}
        return found


# ---- statement grammar

_MACRO = re.compile(r"^(?P<macro>[A-Za-z][A-Za-z0-9_]*)\s*\((?P<args>.*)\)\s*(?P<open>\{)?\s*$")
_ELEMENT_MACRO = re.compile(r"^(?P<role>Person|System|Container|Component)(?P<kind>Db|Queue)?(?P<ext>_Ext)?$")
_BOUNDARY_MACROS = {"Boundary", "Enterprise_Boundary", "System_Boundary", "Container_Boundary"}
_REL_MACROS = {
    "Rel",
    "BiRel",
    "Rel_U",
    "Rel_Up",
    "Rel_D",
    "Rel_Down",
    "Rel_L",
    "Rel_Left",
    "Rel_R",
    "Rel_Right",
    "Rel_Back",
    "RelIndex",
}
_STYLE_MACROS = {"UpdateElementStyle", "updateElementStyle", "UpdateRelStyle", "UpdateLayoutConfig"}
_MARKER = re.compile(r"\[(existing|new|changed)\]")

_ARROW = r"<<-->>|<<->>|-->>|->>|--x|-x|--\)|-\)|-->|->"
_SEQ_PARTICIPANT = re.compile(
    r"^(?:create\s+)?(?P<kw>participant|actor)\s+(?P<alias>[^\s@]+)\s*(?:@\{.*?\})?\s*(?:as\s+(?P<label>.+))?$"
)
_SEQ_MESSAGE = re.compile(
    rf"^(?P<src>\S+?)\s*(?P<arrow>{_ARROW})(?P<act>[+-])?\s*(?P<dst>[^\s:]+)\s*:\s*(?P<text>.*)$"
)
_SEQ_NOTE = re.compile(r"^Note\s+(?:left of|right of|over)\s+[^:]+:\s*.*$", re.IGNORECASE)
_SEQ_BLOCK_OPEN = re.compile(r"^(?:alt|opt|loop|par|critical|break|rect|box)\b")
_SEQ_BLOCK_MID = re.compile(r"^(?:else|and|option)\b")
_SEQ_SIMPLE = re.compile(r"^(?:autonumber\b.*|activate\s+\S+|deactivate\s+\S+|destroy\s+.+|title\b.*)$")

_ER_ID = r'(?:"[^"]+"|[A-Za-z_][\w\-]*)'
_ER_TAIL = r'(?:\[(?P<{label}>"[^"]*"|[^\]]*)\])?(?::::\w+)?'
_ER_BLOCK = re.compile(rf"^(?P<name>{_ER_ID}){_ER_TAIL.format(label='label')}\s*\{{\s*$")
_ER_SINGLE = re.compile(rf"^(?P<name>{_ER_ID}){_ER_TAIL.format(label='label')}$")
_ER_REL = re.compile(
    rf"^(?P<a>{_ER_ID}){_ER_TAIL.format(label='alabel')}\s*(?P<card>[|o}}{{]{{2}}(?:--|\.\.)[|o}}{{]{{2}})\s*"
    rf"(?P<b>{_ER_ID}){_ER_TAIL.format(label='blabel')}\s*(?::\s*(?P<label>.*))?$"
)
_ER_ATTRIBUTE = re.compile(r"^[\w\-\(\),\[\]]+\s+[\w\-\*]+(?:\s+.*)?$")
_ER_SIMPLE = re.compile(r"^(?:direction\s+\w+|style\s+.+|classDef\s+.+|class\s+.+)$")


def split_args(text: str) -> list[str] | None:
    """Split macro arguments on top-level commas. ``None`` if a quote is left open."""
    args: list[str] = []
    current: list[str] = []
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
            current.append(char)
        elif char == "," and not quoted:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if quoted:
        return None
    last = "".join(current).strip()
    if last or args:
        args.append(last)
    return args


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _positional_and_named(args: list[str]) -> tuple[list[str], dict[str, str]]:
    positional: list[str] = []
    named: dict[str, str] = {}
    for arg in args:
        if arg.startswith("$") and "=" in arg:
            key, _, value = arg[1:].partition("=")
            named[key.strip()] = _unquote(value)
        else:
            positional.append(_unquote(arg))
    return positional, named


class _Reader:
    def __init__(self, text: str, where: str, first_line: int) -> None:
        self.where = where
        self.first_line = first_line
        self.rows = [
            (first_line + i, raw.strip()) for i, raw in enumerate(text.replace("\r\n", "\n").split("\n"))
        ]
        self.diagram = Diagram()

    def loc(self, number: int) -> str:
        return f"{self.where}:{number}" if self.where else f"line:{number}"

    def bad(self, number: int, message: str) -> None:
        self.diagram.findings.append(Finding("diagram-unparseable", self.loc(number), message))

    def statements(self) -> list[tuple[int, str]]:
        """Statements after the diagram keyword, with comments and frontmatter removed."""
        rows = [(n, s) for n, s in self.rows if s and not s.startswith("%%")]
        if rows and rows[0][1] == "---":
            end = next((i for i in range(1, len(rows)) if rows[i][1] == "---"), None)
            if end is None:
                self.bad(rows[0][0], "frontmatter block is never closed with ---")
                return []
            rows = rows[end + 1 :]
        if not rows:
            self.bad(self.first_line, "diagram is empty")
            return []
        number, first = rows[0]
        keyword = first.split()[0]
        kind = KIND_KEYWORDS.get(keyword)
        if kind is None or first != keyword:
            self.bad(
                number,
                f"not a supported diagram type: {first!r} "
                f"(expected {', '.join(KIND_KEYWORDS)}; other Mermaid types are outside the subset)",
            )
            return []
        self.diagram.kind = kind
        return rows[1:]


def parse_diagram(text: str, where: str = "", first_line: int = 1) -> Diagram:
    reader = _Reader(text, where, first_line)
    body = reader.statements()
    diagram = reader.diagram
    if diagram.kind is not None:
        if diagram.kind.startswith("c4"):
            _parse_c4(reader, body)
        elif diagram.kind == "sequence":
            _parse_sequence(reader, body)
        else:
            _parse_er(reader, body)
        empty = not (diagram.elements or diagram.participants or diagram.entities)
        if empty and not diagram.findings:
            reader.bad(first_line, "no recognisable elements in the diagram")
    diagram.findings.sort(key=lambda f: int(f.where.rsplit(":", 1)[-1]))
    return diagram


# ---- C4


def _parse_c4(reader: _Reader, body: list[tuple[int, str]]) -> None:
    diagram = reader.diagram
    stack: list[tuple[str, int]] = []  # (boundary label, opening line)
    for number, stmt in body:
        if stmt == "}":
            if not stack:
                reader.bad(number, "closing brace without an open boundary")
            else:
                stack.pop()
            continue
        if stmt.startswith("title ") or stmt == "title":
            diagram.title = stmt[5:].strip() or None
            continue
        match = _MACRO.match(stmt)
        if not match:
            reader.bad(number, f"unrecognised line: {stmt!r}")
            continue
        macro, raw_args, opens = match["macro"], match["args"], bool(match["open"])
        if macro in _STYLE_MACROS:
            continue
        args = split_args(raw_args)
        if args is None:
            reader.bad(number, f"unbalanced quote in {macro}(...): {stmt!r}")
            continue
        positional, named = _positional_and_named(args)
        element = _ELEMENT_MACRO.match(macro)
        if element:
            if len(positional) < 2 or not positional[0] or not positional[1]:
                reader.bad(number, f"{macro} needs an alias and a label: {stmt!r}")
                continue
            role = element["role"].lower()
            person_or_system = role in ("person", "system")
            description = named.get("descr") or (
                positional[2]
                if person_or_system and len(positional) > 2
                else positional[3]
                if len(positional) > 3
                else ""
            )
            technology = named.get("techn") or (
                "" if person_or_system else positional[2] if len(positional) > 2 else ""
            )
            found = _MARKER.search(description)
            diagram.elements.append(
                Element(
                    alias=positional[0],
                    label=positional[1],
                    role=role,
                    external=bool(element["ext"]),
                    database=element["kind"] == "Db",
                    queue=element["kind"] == "Queue",
                    technology=technology,
                    description=description,
                    marker=found.group(1) if found else None,
                    boundary=stack[-1][0] if stack else None,
                    line=number,
                )
            )
        elif macro in _BOUNDARY_MACROS:
            if len(positional) < 2 or not positional[0] or not positional[1]:
                reader.bad(number, f"{macro} needs an alias and a label: {stmt!r}")
            elif not opens:
                reader.bad(number, f"{macro} needs a block: end the line with '{{': {stmt!r}")
            else:
                diagram.boundaries.append(
                    Boundary(positional[0], positional[1], macro, stack[-1][0] if stack else None, number)
                )
                stack.append((positional[1], number))
        elif macro in _REL_MACROS:
            offset = 1 if macro == "RelIndex" else 0
            if len(positional) < 3 + offset:
                reader.bad(number, f"{macro} needs from, to and a label: {stmt!r}")
            else:
                diagram.relations.append(
                    Relation(positional[offset], positional[offset + 1], positional[offset + 2], number)
                )
        else:
            reader.bad(number, f"unrecognised C4 macro {macro!r}: {stmt!r}")
    for label, number in stack:
        reader.bad(number, f"boundary {label!r} is never closed with '}}'")


# ---- sequence


def _parse_sequence(reader: _Reader, body: list[tuple[int, str]]) -> None:
    diagram = reader.diagram
    declared: dict[str, Participant] = {}
    depth: list[int] = []

    def implied(alias: str, number: int) -> None:
        if alias not in declared:
            participant = Participant(alias, alias, actor=False, declared=False, line=number)
            declared[alias] = participant
            diagram.participants.append(participant)

    for number, stmt in body:
        match = _SEQ_PARTICIPANT.match(stmt)
        if match:
            alias = match["alias"]
            label = (match["label"] or alias).strip()
            participant = Participant(alias, label, match["kw"] == "actor", True, number)
            if alias in declared and not declared[alias].declared:
                diagram.participants.remove(declared[alias])
            declared[alias] = participant
            diagram.participants.append(participant)
            continue
        if _SEQ_SIMPLE.match(stmt) or _SEQ_NOTE.match(stmt):
            if stmt.startswith("title"):
                diagram.title = stmt[5:].strip() or None
            continue
        if stmt == "end":
            if not depth:
                reader.bad(
                    number, "'end' without an open block (alt, opt, loop, par, critical, break, rect or box)"
                )
            else:
                depth.pop()
            continue
        if _SEQ_BLOCK_OPEN.match(stmt):
            depth.append(number)
            continue
        if _SEQ_BLOCK_MID.match(stmt):
            continue
        message = _SEQ_MESSAGE.match(stmt)
        if message:
            source, target = message["src"], message["dst"]
            implied(source, number)
            implied(target, number)
            diagram.messages.append(Message(source, target, message["text"].strip(), number))
            continue
        reader.bad(number, f"unrecognised line: {stmt!r}")
    for number in depth:
        reader.bad(number, "block is never closed with 'end'")


# ---- ER


def _er_label(raw: str | None) -> str | None:
    return None if raw is None else raw.strip().strip('"')


def _er_ident(raw: str) -> str:
    return raw.strip().strip('"')


def _parse_er(reader: _Reader, body: list[tuple[int, str]]) -> None:
    diagram = reader.diagram
    entities: dict[str, Entity] = {}
    relations: list[tuple[str, str, str, str, int]] = []
    current: Entity | None = None
    groups: list[int] = []

    def declare(name: str, label: str | None, number: int) -> Entity:
        name = _er_ident(name)
        entity = entities.get(name)
        if entity is None:
            entity = Entity(name, label or name, [], True, number)
            entities[name] = entity
            diagram.entities.append(entity)
        elif label:
            entity.label = label
        return entity

    for number, stmt in body:
        if current is not None:
            if stmt == "}":
                current = None
            elif _ER_ATTRIBUTE.match(stmt):
                current.attributes.append(" ".join(stmt.split()))
            else:
                reader.bad(number, f"unrecognised attribute line: {stmt!r}")
            continue
        if stmt.startswith("title "):
            diagram.title = stmt[6:].strip() or None
            continue
        if _ER_SIMPLE.match(stmt):
            continue
        if stmt.startswith("subgraph"):
            groups.append(number)
            continue
        if stmt == "end":
            if not groups:
                reader.bad(number, "'end' without an open subgraph")
            else:
                groups.pop()
            continue
        block = _ER_BLOCK.match(stmt)
        if block:
            current = declare(block["name"], _er_label(block["label"]), number)
            continue
        rel = _ER_REL.match(stmt)
        if rel:
            relations.append((rel["a"], rel["b"], rel["card"], _er_label(rel["label"]) or "", number))
            for side, label in (("a", "alabel"), ("b", "blabel")):
                if rel[label] is not None:
                    declare(rel[side], _er_label(rel[label]), number)
            continue
        single = _ER_SINGLE.match(stmt)
        if single:
            declare(single["name"], _er_label(single["label"]), number)
            continue
        reader.bad(number, f"unrecognised line: {stmt!r}")
    if current is not None:
        reader.bad(current.line, f"entity {current.name!r} block is never closed with '}}'")
    for number in groups:
        reader.bad(number, "subgraph is never closed with 'end'")
    for left, right, cardinality, label, number in relations:
        for ident in (left, right):
            name = _er_ident(ident)
            if name not in entities:
                entity = Entity(name, name, [], False, number)
                entities[name] = entity
                diagram.entities.append(entity)
        diagram.er_relations.append(
            ErRelation(
                entities[_er_ident(left)].label, entities[_er_ident(right)].label, cardinality, label, number
            )
        )


# ---- technical consistency rules (FR-079 a, c, d; tasks T079)
#
# Each rule takes parsed diagrams and returns messages; the gate turns them into findings and
# decides which criterion they belong to. A message starts with the rule letter so a reader can find
# it in the contract.


def external_names(diagram: Diagram) -> dict[str, str]:
    """People and external systems of a C4 diagram: ``normalised name -> name as written``."""
    return {normalise_name(e.label): e.label for e in diagram.elements if e.role == "person" or e.external}


def element_names(*diagrams: Diagram) -> set[str]:
    """Normalised names of every element (person, system, container, component) in the diagrams."""
    return {normalise_name(e.label) for d in diagrams for e in d.elements}


def zoom_problems(context: Diagram, container: Diagram) -> list[str]:
    """Rule a, level 2 against level 1: the same external people and systems, by name."""
    above, here = external_names(context), external_names(container)
    problems = [
        f"rule a: '{label}' is external in the container diagram but not in the system context diagram"
        for key, label in here.items()
        if key not in above
    ]
    problems += [
        f"rule a: '{label}' is external in the system context diagram but missing from the container diagram"
        for key, label in above.items()
        if key not in here
    ]
    return problems


def component_problems(containers: Diagram, component: Diagram) -> list[str]:
    """Rule a, level 3: the component diagram names, as a ``Container_Boundary``, a container of level 2."""
    boundaries = [b for b in component.boundaries if b.macro == "Container_Boundary"]
    if not boundaries:
        return ["rule a: the component diagram has no Container_Boundary naming the container it details"]
    known = {normalise_name(e.label) for e in containers.elements if e.role == "container"}
    return [
        f"rule a: the component diagram details '{b.label}', which is not a container in the container diagram"
        for b in boundaries
        if normalise_name(b.label) not in known
    ]


def sequence_problems(sequence: Diagram, known: set[str]) -> list[str]:
    """Rule c: every participant is an element of a container or component diagram."""
    return [
        f"rule c: participant '{p.label}' is in no container or component diagram"
        for p in sequence.participants
        if normalise_name(p.label) not in known
    ]


def store_problems(store: str | None, containers: Diagram) -> list[str]:
    """Rule d: the ER diagram declares its data store and the container diagram shows it as a database."""
    if not store:
        return [
            "rule d: the ER diagram declares no data store; add (store: NAME) naming a database in the "
            "container diagram"
        ]
    wanted = normalise_name(store)
    found = [e for e in containers.elements if normalise_name(e.label) == wanted]
    if not found:
        return [f"rule d: store '{store}' is not in the container diagram"]
    if not any(e.database for e in found):
        return [f"rule d: '{store}' is not a data store (a ContainerDb or SystemDb) in the container diagram"]
    return []
