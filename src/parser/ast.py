"""AST node definitions for SPL parser."""
from dataclasses import dataclass, field
from typing import Optional, Any
from ..lexer.tokens import Position


@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    start: Position
    end: Position


# === Pipeline Structure ===

@dataclass
class Pipeline(ASTNode):
    """Root node representing entire SPL pipeline."""
    commands: list['Command'] = field(default_factory=list)


@dataclass
class Subsearch(ASTNode):
    """Subsearch enclosed in [...] brackets."""
    pipeline: 'Pipeline' = field(default=None)


# === Commands ===

@dataclass 
class Command(ASTNode):
    """A single SPL command with its arguments."""
    name: str = ""
    args: list['Argument'] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    clauses: dict[str, 'Clause'] = field(default_factory=dict)
    aggregations: list['Aggregation'] = field(default_factory=list)
    subsearch: Optional[Subsearch] = None


@dataclass
class Argument(ASTNode):
    """Generic command argument."""
    value: Any = None


@dataclass
class Clause(ASTNode):
    """Command clause like BY, AS, OVER."""
    keyword: str = ""
    fields: list[str] = field(default_factory=list)
    condition: Optional['Expression'] = None


# === Expressions ===

@dataclass
class Expression(ASTNode):
    """Base class for expressions."""
    pass


@dataclass
class BinaryOp(Expression):
    """Binary operation: left op right."""
    left: Expression = None
    operator: str = ""
    right: Expression = None


@dataclass
class UnaryOp(Expression):
    """Unary operation: op expr."""
    operator: str = ""
    operand: Expression = None


@dataclass
class FunctionCall(Expression):
    """Function call: name(args)."""
    name: str = ""
    args: list[Expression] = field(default_factory=list)


@dataclass
class FieldRef(Expression):
    """Reference to a field."""
    name: str = ""
    

@dataclass
class Literal(Expression):
    """Literal value: string, number, boolean."""
    value: Any = None
    type: str = "unknown"  # string, number, boolean, null


@dataclass
class Assignment(Expression):
    """Field assignment: field = expr."""
    field_name: str = ""
    value: Expression = None


# === Stats/Aggregation ===

@dataclass
class Aggregation(ASTNode):
    """Aggregation function call with alias."""
    function: str = ""
    agg_field: Optional[str] = None  # Renamed from 'field' to avoid shadowing
    args: list[Expression] = field(default_factory=list)
    alias: Optional[str] = None
    
    @property
    def default_name(self) -> str:
        """Generate default name if no alias."""
        if self.alias:
            return self.alias
        if self.agg_field:
            return f"{self.function}({self.agg_field})"
        return self.function


# === Rename ===

@dataclass
class RenamePair(ASTNode):
    """Rename pair: old AS new."""
    old_name: str = ""
    new_name: str = ""


# === Search Terms ===

@dataclass
class SearchTerm(Expression):
    """Search term in search command."""
    term: str = ""
    is_wildcard: bool = False


@dataclass
class FieldComparison(Expression):
    """Field comparison: field op value."""
    field_name: str = ""  # Renamed from 'field' to avoid shadowing
    operator: str = ""
    value: Any = None
