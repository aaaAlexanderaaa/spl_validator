"""SPL Lexer - Token types and definitions."""
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    """All token types recognized by the SPL lexer."""
    
    # Structural
    PIPE = auto()           # |
    COMMA = auto()          # ,
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    
    # Literals
    IDENTIFIER = auto()     # field names, command names
    STRING = auto()         # "..." or '...'
    NUMBER = auto()         # integers and floats
    MACRO = auto()          # `macro_name(...)`
    
    # Keywords (case-insensitive)
    AND = auto()
    OR = auto()
    NOT = auto()
    XOR = auto()
    BY = auto()
    AS = auto()
    OVER = auto()
    OUTPUT = auto()
    OUTPUTNEW = auto()
    WHERE = auto()          # As clause keyword
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    
    # Comparison operators
    EQ = auto()             # =
    EQEQ = auto()           # ==
    NEQ = auto()            # != or <>
    LT = auto()             # <
    GT = auto()             # >
    LTE = auto()            # <=
    GTE = auto()            # >=
    LIKE = auto()           # LIKE (eval compare operator)
    
    # Arithmetic operators
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # *
    SLASH = auto()          # /
    PERCENT = auto()        # %
    
    # String operators
    DOT = auto()            # . (concatenation)
    
    # Special
    ASSIGN = auto()         # = (in assignments)
    WILDCARD = auto()       # * at start/end of identifier
    
    # Control
    EOF = auto()            # End of input
    ERROR = auto()          # Lexer error (for error recovery)


# Keywords mapping (lowercase for case-insensitive matching)
KEYWORDS: dict[str, TokenType] = {
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "xor": TokenType.XOR,
    "by": TokenType.BY,
    "as": TokenType.AS,
    "over": TokenType.OVER,
    "output": TokenType.OUTPUT,
    "outputnew": TokenType.OUTPUTNEW,
    "where": TokenType.WHERE,
    "like": TokenType.LIKE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
}


@dataclass(frozen=True)
class Position:
    """Source position for error reporting."""
    line: int       # 1-indexed
    column: int     # 1-indexed
    offset: int     # Character offset from start
    
    def __str__(self) -> str:
        return f"line {self.line}, column {self.column}"


@dataclass(frozen=True)
class Token:
    """A single token from the SPL source."""
    type: TokenType
    value: str
    start: Position
    end: Position
    
    def __str__(self) -> str:
        if self.type == TokenType.ERROR:
            return f"ERROR({self.value!r})"
        elif self.type in (TokenType.STRING, TokenType.NUMBER, TokenType.IDENTIFIER, TokenType.MACRO):
            return f"{self.type.name}({self.value!r})"
        else:
            return self.type.name
