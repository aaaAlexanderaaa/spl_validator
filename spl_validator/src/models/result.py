"""Validation result models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from ..lexer.tokens import Position

if TYPE_CHECKING:
    from ..parser.ast import Pipeline


class Severity(Enum):
    """Severity level of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue (error, warning, or info)."""
    severity: Severity
    code: str           # e.g., "SPL001"
    message: str        # Human-readable message
    start: Position
    end: Position
    suggestion: Optional[str] = None  # Quick fix suggestion
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message} at {self.start}"
    
    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR
    
    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING


@dataclass
class ValidationResult:
    """Complete result of SPL validation."""
    spl: str                    # Original SPL text
    is_valid: bool              # True if no errors (warnings OK)
    issues: list[ValidationIssue] = field(default_factory=list)
    ast: Optional[Pipeline] = None   # Parsed AST (if successful)
    _lex_spl: Optional[str] = None   # Lexer input after map/markdown preprocessing
    # Parallel lists for O(1) access (CLI/JSON iterate these repeatedly).
    errors: list[ValidationIssue] = field(default_factory=list, init=False, repr=False)
    warnings: list[ValidationIssue] = field(default_factory=list, init=False, repr=False)
    infos: list[ValidationIssue] = field(default_factory=list, init=False, repr=False)

    def add_error(self, code: str, message: str, start: Position, end: Position,
                  suggestion: Optional[str] = None) -> None:
        """Add an error issue."""
        issue = ValidationIssue(
            severity=Severity.ERROR,
            code=code,
            message=message,
            start=start,
            end=end,
            suggestion=suggestion
        )
        self.issues.append(issue)
        self.errors.append(issue)
        self.is_valid = False

    def add_warning(self, code: str, message: str, start: Position, end: Position,
                    suggestion: Optional[str] = None) -> None:
        """Add a warning issue."""
        issue = ValidationIssue(
            severity=Severity.WARNING,
            code=code,
            message=message,
            start=start,
            end=end,
            suggestion=suggestion
        )
        self.issues.append(issue)
        self.warnings.append(issue)

    def add_info(self, code: str, message: str, start: Position, end: Position) -> None:
        """Add an info issue."""
        issue = ValidationIssue(
            severity=Severity.INFO,
            code=code,
            message=message,
            start=start,
            end=end
        )
        self.issues.append(issue)
        self.infos.append(issue)
