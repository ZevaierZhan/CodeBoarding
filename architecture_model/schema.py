from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer

Text = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        value = handler(self)
        for name, default in (
            ("contract", None),
            ("relation_ids", []),
            ("maintenance_targets", {}),
            ("binding_snapshots", {}),
        ):
            field = type(self).model_fields.get(name)
            if field is not None and not field.is_required() and value.get(name, default) == default:
                value.pop(name, None)
        for name, default in (("analysis_kind", "operation"), ("facet_order", []), ("facet_checks", {})):
            if name not in self.model_fields_set and value.get(name) == default:
                value.pop(name, None)
        return value

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


class Location(Strict):
    path: Text
    symbol: str = ""
    kind: Text
    content_hash: Digest
    start: Annotated[int, Field(ge=1)]
    end: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def valid_location(self) -> "Location":
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path or ":" in self.path:
            raise ValueError("path must be repository-relative POSIX")
        if self.end < self.start:
            raise ValueError("end precedes start")
        return self


class SourceVersion(Strict):
    digest: Digest
    git_commit: str = ""
    files: dict[Text, Digest]
    scope: Text


class CallSite(Strict):
    path: Text
    line: Annotated[int, Field(ge=1)]
    column: Annotated[int, Field(ge=0)] = 0


class Call(Strict):
    source: Text
    target: Text
    sites: list[CallSite]


class Facts(Strict):
    schema_version: Literal[1, 2] = 1
    id: Text
    project_id: Text
    source: SourceVersion
    symbols: dict[Text, Location]
    file_locations: dict[Text, Location] = Field(default_factory=dict)
    calls: list[Call]
    tools: dict[Text, Text]
    limitations: list[Text]
    source_root_id: str = ""
    file_languages: dict[Text, Text] = Field(default_factory=dict)
    file_projects: dict[Text, Text] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_identity(self) -> "Facts":
        if self.schema_version == 1 and (self.source_root_id or self.file_languages or self.file_projects):
            raise ValueError("v1 facts cannot carry v2 source identity")
        if self.schema_version == 2 and (
            not self.source_root_id
            or set(self.file_languages) != set(self.source.files)
            or set(self.file_projects) != set(self.source.files)
        ):
            raise ValueError("v2 facts require root identity and language/project for every file")
        return self

    @model_serializer(mode="wrap")
    def preserve_v1(self, handler):
        value = handler(self)
        if self.schema_version == 1:
            for name in ("source_root_id", "file_languages", "file_projects"):
                value.pop(name, None)
        return value


class HistoricalLocation(Strict):
    snapshot_id: Text
    source_version: Digest
    location: Location
    reason: Text


class Binding(Strict):
    id: Text
    snapshot_id: Text
    source_version: Digest
    location: Location
    status: Literal["current", "changed", "missing", "ambiguous"]
    reason: str = ""
    history: list[HistoricalLocation] = Field(default_factory=list)

    @model_validator(mode="after")
    def review_reason(self) -> "Binding":
        if self.status != "current" and not self.reason.strip():
            raise ValueError("non-current binding requires a review reason")
        return self


class Claim(Strict):
    kind: Literal["code_fact", "inference", "intent_hypothesis"]
    explanation: Text
    binding_ids: list[Text]
    assumptions: list[Text] = Field(default_factory=list)
    issues: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence(self) -> "Claim":
        if not self.binding_ids:
            raise ValueError("claim requires source evidence")
        if self.kind != "code_fact" and not (self.assumptions or self.issues):
            raise ValueError("inference requires explicit assumptions or uncertainty")
        return self


class Component(Strict):
    id: Text
    name: Text
    responsibility: Text
    rationale: Text
    parent_id: str = ""
    binding_ids: list[Text]
    claim: Claim


class InterfaceContract(Strict):
    mechanism: Text
    operation: Text
    caller_binding_ids: Annotated[list[Text], Field(min_length=1)]
    receiver_binding_ids: Annotated[list[Text], Field(min_length=1)]
    matching_binding_ids: list[Text] = Field(default_factory=list)
    status: Literal["candidate", "evidenced", "ambiguous", "missing"] = "candidate"
    rationale: Text
    uncertainties: list[Text] = Field(default_factory=list)


class Relation(Strict):
    id: Text
    source_id: Text
    target_id: Text
    meaning: Text
    claim: Claim
    contract: InterfaceContract | None = None


class Step(Strict):
    id: Text
    component_ids: list[Text]
    binding_ids: list[Text]
    claim: Claim
    facet_checks: dict[Text, Text] = Field(default_factory=dict)


class Transition(Strict):
    source_id: Text
    target_id: Text
    kind: Literal["next", "branch", "return", "loop"]
    condition: Text


class Scenario(Strict):
    id: Text
    name: Text
    entry_step_id: Text
    steps: list[Step]
    order: list[Text]
    transitions: list[Transition]
    claim: Claim
    relation_ids: list[Text] = Field(default_factory=list)
    analysis_kind: Literal["operation", "comparison"] = "operation"
    facet_order: list[Text] = Field(default_factory=list)


class Opinion(Strict):
    id: Text
    author: Text
    text: Text
    stance: Literal["accept", "correct", "disagree", "question"]
    object_ids: list[Text]


class Verification(Strict):
    id: Text
    status: Literal["planned", "executed"]
    object_ids: list[Text]
    command: Text
    environment: Text
    inputs: Text
    source_version: Digest
    executor: str = ""
    executed_at: str = ""
    exit_code: int | None = None
    result: str = ""
    binding_snapshots: dict[Text, Text] = Field(default_factory=dict)

    @model_validator(mode="after")
    def execution_record(self) -> "Verification":
        details = (self.executor, self.executed_at, self.result)
        if self.status == "executed" and (self.exit_code is None or not all(details)):
            raise ValueError("executed verification requires executor, time, exit_code and result")
        if self.status == "planned" and (self.exit_code is not None or any(details)):
            raise ValueError("planned verification cannot contain execution results")
        return self


class Revision(Strict):
    revision: Annotated[int, Field(ge=0)]
    author: Text
    summary: Text
    timestamp: Text
    object_ids: list[Text]
    scenario_ids: list[Text]


class Project(Strict):
    id: Text
    name: Text
    boundary: Text


class MaintenanceCandidate(Strict):
    key: Text
    location: Location
    reasons: list[Text]


class MaintenanceResolution(Strict):
    outcome: Literal["confirmed", "revised"]
    author: Text
    reason: Text
    source_version: Digest
    timestamp: Text
    object_ids: list[Text]
    object_versions: dict[Text, Digest] = Field(default_factory=dict)


class Maintenance(Strict):
    id: Text
    binding_id: Text
    basis: HistoricalLocation
    target_snapshot_id: Text
    target_source_version: Digest
    compared_revision: Annotated[int, Field(ge=0)]
    disposition: Literal["unchanged", "changed", "missing", "ambiguous", "indeterminate"]
    reasons: list[Text]
    candidates: list[MaintenanceCandidate]
    component_ids: list[Text]
    relation_ids: list[Text]
    scenario_ids: list[Text]
    step_ids: list[Text]
    call_changes: dict[Literal["before", "after"], list[Call]]
    resolution: MaintenanceResolution | None = None
    coverage_version: Literal["", "objects-v1"] = ""
    object_versions: dict[Text, Digest] = Field(default_factory=dict)


class Model(Strict):
    schema_version: Literal[1] = 1
    id: Text
    project: Project
    revision: Annotated[int, Field(ge=0)] = 0
    facts: list[Facts] = Field(default_factory=list)
    bindings: list[Binding] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    opinions: list[Opinion] = Field(default_factory=list)
    verifications: list[Verification] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)
    maintenance: list[Maintenance] = Field(default_factory=list)
    maintenance_target_snapshot_id: str = ""
    maintenance_targets: dict[Text, Text] = Field(default_factory=dict)


class Operation(Strict):
    action: Literal["create", "update", "delete"]
    collection: Literal["facts", "bindings", "components", "relations", "scenarios", "opinions", "verifications"]
    id: Text
    value: dict = Field(default_factory=dict)


class Patch(Strict):
    author: Text
    summary: Text
    operations: Annotated[list[Operation], Field(min_length=1)]
