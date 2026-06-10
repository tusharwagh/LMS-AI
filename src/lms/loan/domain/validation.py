"""Aggregated rule validation at workflow boundary (REQ-29)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RuleViolation:
    rule_id: str
    message: str


@dataclass
class ValidationReport:
    violations: list[RuleViolation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.violations

    def add(self, rule_id: str, message: str) -> None:
        self.violations.append(RuleViolation(rule_id=rule_id, message=message))
