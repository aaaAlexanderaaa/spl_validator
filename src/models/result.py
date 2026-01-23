"""Validation result models."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from ..lexer.tokens import Position


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
    ast: Optional[Any] = None   # Parsed AST (if successful)
    
    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]
    
    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]
    
    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.INFO]
    
    def add_error(self, code: str, message: str, start: Position, end: Position,
                  suggestion: Optional[str] = None) -> None:
        """Add an error issue."""
        self.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            code=code,
            message=message,
            start=start,
            end=end,
            suggestion=suggestion
        ))
        self.is_valid = False
    
    def add_warning(self, code: str, message: str, start: Position, end: Position,
                    suggestion: Optional[str] = None) -> None:
        """Add a warning issue."""
        self.issues.append(ValidationIssue(
            severity=Severity.WARNING,
            code=code,
            message=message,
            start=start,
            end=end,
            suggestion=suggestion
        ))
    
    def add_info(self, code: str, message: str, start: Position, end: Position) -> None:
        """Add an info issue."""
        self.issues.append(ValidationIssue(
            severity=Severity.INFO,
            code=code,
            message=message,
            start=start,
            end=end
        ))
