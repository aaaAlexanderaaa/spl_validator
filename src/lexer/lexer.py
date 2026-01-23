"""SPL Lexer - Tokenizer with position tracking and error recovery."""
from typing import Iterator
from .tokens import Token, TokenType, Position, KEYWORDS


class Lexer:
    """Tokenizes SPL input with precise position tracking.
    
    Features:
    - Position tracking (line, column, offset)
    - Error recovery (bad tokens become ERROR tokens, not exceptions)
    - Support for all SPL token types
    """
    
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.line_start = 0
    
    def tokenize(self) -> list[Token]:
        """Tokenize the entire input and return list of tokens."""
        tokens = []
        for token in self._tokenize_iter():
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens
    
    def _tokenize_iter(self) -> Iterator[Token]:
        """Generator that yields tokens one at a time."""
        while self.pos < len(self.source):
            # Skip whitespace
            if self._current().isspace():
                self._skip_whitespace()
                continue
            
            # Search macros: `macro_name(...)`
            if self._current() == '`':
                yield self._scan_macro()
                continue
            
            start_pos = self._make_position()
            char = self._current()
            
            # Single character tokens
            if char == '|':
                self._advance()
                yield self._make_token(TokenType.PIPE, '|', start_pos)
            elif char == ',':
                self._advance()
                yield self._make_token(TokenType.COMMA, ',', start_pos)
            elif char == '(':
                self._advance()
                yield self._make_token(TokenType.LPAREN, '(', start_pos)
            elif char == ')':
                self._advance()
                yield self._make_token(TokenType.RPAREN, ')', start_pos)
            elif char == '[':
                self._advance()
                yield self._make_token(TokenType.LBRACKET, '[', start_pos)
            elif char == ']':
                self._advance()
                yield self._make_token(TokenType.RBRACKET, ']', start_pos)
            elif char == '+':
                self._advance()
                yield self._make_token(TokenType.PLUS, '+', start_pos)
            elif char == '-':
                self._advance()
                yield self._make_token(TokenType.MINUS, '-', start_pos)
            elif char == '*':
                self._advance()
                yield self._make_token(TokenType.STAR, '*', start_pos)
            elif char == '/':
                self._advance()
                yield self._make_token(TokenType.SLASH, '/', start_pos)
            elif char == '%':
                self._advance()
                yield self._make_token(TokenType.PERCENT, '%', start_pos)
            elif char == '.':
                # Could be dot operator or a leading-decimal number like .25
                if self._peek(1).isdigit():
                    yield self._scan_number_starting_with_dot()
                else:
                    self._advance()
                    yield self._make_token(TokenType.DOT, '.', start_pos)
            
            # Multi-character operators
            elif char == '=':
                self._advance()
                if self._current() == '=':
                    self._advance()
                    yield self._make_token(TokenType.EQEQ, '==', start_pos)
                else:
                    yield self._make_token(TokenType.EQ, '=', start_pos)
            elif char == '!':
                self._advance()
                if self._current() == '=':
                    self._advance()
                    yield self._make_token(TokenType.NEQ, '!=', start_pos)
                else:
                    # NOT operator as !
                    yield self._make_token(TokenType.NOT, '!', start_pos)
            elif char == '<':
                self._advance()
                if self._current() == '=':
                    self._advance()
                    yield self._make_token(TokenType.LTE, '<=', start_pos)
                elif self._current() == '>':
                    self._advance()
                    yield self._make_token(TokenType.NEQ, '<>', start_pos)
                else:
                    yield self._make_token(TokenType.LT, '<', start_pos)
            elif char == '>':
                self._advance()
                if self._current() == '=':
                    self._advance()
                    yield self._make_token(TokenType.GTE, '>=', start_pos)
                else:
                    yield self._make_token(TokenType.GT, '>', start_pos)
            
            # Strings
            elif char == '"' or char == "'":
                yield self._scan_string(char)
            
            # Numbers
            elif char.isdigit():
                yield self._scan_number()
            
            # Identifiers and keywords
            elif char.isalpha() or char in '_@$\\{:':
                yield self._scan_identifier()
            
            # Unknown character - error recovery
            else:
                self._advance()
                yield self._make_token(TokenType.ERROR, char, start_pos)
        
        # EOF token
        yield self._make_token(TokenType.EOF, '', self._make_position())

    def _scan_macro(self) -> Token:
        """Scan a backtick-delimited Splunk search macro invocation: `name(args...)`.

        Macros are expanded by Splunk before execution. The validator treats the
        macro invocation as an opaque token.
        """
        start_pos = self._make_position()
        self._advance()  # Skip opening backtick

        value = []
        while self.pos < len(self.source) and self._current() != '`':
            # Macros are typically single-line; stop on newline to avoid swallowing the query.
            if self._current() == '\n':
                break
            value.append(self._current())
            self._advance()

        if self.pos < len(self.source) and self._current() == '`':
            self._advance()  # Skip closing backtick
            return self._make_token(TokenType.MACRO, ''.join(value).strip(), start_pos)

        # Unclosed macro - error recovery
        return self._make_token(TokenType.ERROR, '`' + ''.join(value), start_pos)
    
    def _scan_string(self, quote: str) -> Token:
        """Scan a quoted string literal."""
        start_pos = self._make_position()
        self._advance()  # Skip opening quote
        
        value = []
        while self.pos < len(self.source) and self._current() != quote:
            if self._current() == '\\':
                self._advance()
                if self.pos < len(self.source):
                    escaped = self._current()
                    if escaped == 'n':
                        value.append('\n')
                    elif escaped == 't':
                        value.append('\t')
                    elif escaped == 'r':
                        value.append('\r')
                    elif escaped == '\\':
                        value.append('\\')
                    elif escaped == quote:
                        value.append(quote)
                    else:
                        value.append('\\')
                        value.append(escaped)
                    self._advance()
            elif self._current() == '\n':
                # Unclosed string at newline
                break
            else:
                value.append(self._current())
                self._advance()
        
        if self.pos < len(self.source) and self._current() == quote:
            self._advance()  # Skip closing quote
            return self._make_token(TokenType.STRING, ''.join(value), start_pos)
        else:
            # Unclosed string - error recovery
            return self._make_token(TokenType.ERROR, quote + ''.join(value), start_pos)
    
    def _scan_number(self) -> Token:
        """Scan a numeric literal (integer or float), including time suffixes like 1h, 30m."""
        start_pos = self._make_position()
        value = []
        
        # Integer part
        while self.pos < len(self.source) and self._current().isdigit():
            value.append(self._current())
            self._advance()
        
        # Decimal part
        if self.pos < len(self.source) and self._current() == '.':
            if self._peek(1).isdigit():
                value.append('.')
                self._advance()
                while self.pos < len(self.source) and self._current().isdigit():
                    value.append(self._current())
                    self._advance()
        
        # Exponent part
        if self.pos < len(self.source) and self._current().lower() == 'e':
            next_char = self._peek(1)
            if next_char.isdigit() or next_char in '+-':
                value.append(self._current())
                self._advance()
                if self.pos < len(self.source) and self._current() in '+-':
                    value.append(self._current())
                    self._advance()
                while self.pos < len(self.source) and self._current().isdigit():
                    value.append(self._current())
                    self._advance()
        
        # Time unit suffix (s, sec, m, min, h, hr, d, day, w, week, mon, y, year)
        # Check for common Splunk time units
        if self.pos < len(self.source) and self._current().isalpha():
            suffix_start = self.pos
            suffix = []
            while self.pos < len(self.source) and self._current().isalpha():
                suffix.append(self._current())
                self._advance()
            suffix_str = ''.join(suffix).lower()
            # Valid time suffixes
            time_suffixes = {'s', 'sec', 'm', 'min', 'h', 'hr', 'd', 'day', 'w', 'week', 'mon', 'y', 'year'}
            if suffix_str in time_suffixes:
                value.extend(suffix)
            else:
                # Not a time suffix, roll back
                self.pos = suffix_start
                self.column = self.pos - self.line_start + 1

        # Optional snap-to-time suffix for relative time literals, e.g. 1d@d, -20m@m.
        if self.pos < len(self.source) and self._current() == '@':
            snap_start = self.pos
            self._advance()  # '@'
            snap = []
            while self.pos < len(self.source) and self._current().isalnum():
                snap.append(self._current())
                self._advance()
            if snap:
                value.append('@')
                value.extend(snap)
            else:
                # No snap unit; roll back.
                self.pos = snap_start
                self.column = self.pos - self.line_start + 1
        
        return self._make_token(TokenType.NUMBER, ''.join(value), start_pos)

    def _scan_number_starting_with_dot(self) -> Token:
        """Scan a numeric literal starting with a decimal point, like .25 or .5e-3."""
        start_pos = self._make_position()
        value = []

        # Leading dot
        if self._current() == '.':
            value.append('.')
            self._advance()

        while self.pos < len(self.source) and self._current().isdigit():
            value.append(self._current())
            self._advance()

        # Exponent part
        if self.pos < len(self.source) and self._current().lower() == 'e':
            next_char = self._peek(1)
            if next_char.isdigit() or next_char in '+-':
                value.append(self._current())
                self._advance()
                if self.pos < len(self.source) and self._current() in '+-':
                    value.append(self._current())
                    self._advance()
                while self.pos < len(self.source) and self._current().isdigit():
                    value.append(self._current())
                    self._advance()

        return self._make_token(TokenType.NUMBER, ''.join(value), start_pos)
    
    def _scan_identifier(self) -> Token:
        """Scan an identifier or keyword."""
        start_pos = self._make_position()
        value = []
        
        # First character is alpha or underscore
        while self.pos < len(self.source) and self._is_identifier_char(self._current()):
            value.append(self._current())
            self._advance()
        
        text = ''.join(value)
        
        # Check for keyword (case-insensitive)
        token_type = KEYWORDS.get(text.lower(), TokenType.IDENTIFIER)
        
        return self._make_token(token_type, text, start_pos)
    
    def _is_identifier_char(self, char: str) -> bool:
        """Check if character can be part of identifier."""
        # '.' is tokenized separately as DOT so the parser can disambiguate
        # dotted field refs (a.b) from concatenation (x.".".y).
        return char.isalnum() or char in '_:*@{}$\\\'"'
    
    def _skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < len(self.source) and self._current().isspace():
            if self._current() == '\n':
                self.line += 1
                self._advance()
                self.line_start = self.pos
            else:
                self._advance()
    
    def _skip_comment(self) -> None:
        """Skip backtick-delimited comments."""
        self._advance()  # Skip first backtick
        while self.pos < len(self.source) and self._current() != '`':
            if self._current() == '\n':
                self.line += 1
                self._advance()
                self.line_start = self.pos
            else:
                self._advance()
        if self.pos < len(self.source):
            self._advance()  # Skip closing backtick
    
    def _current(self) -> str:
        """Get current character or empty string if at end."""
        return self.source[self.pos] if self.pos < len(self.source) else ''
    
    def _peek(self, offset: int) -> str:
        """Peek at character at offset from current position."""
        pos = self.pos + offset
        return self.source[pos] if pos < len(self.source) else ''
    
    def _advance(self) -> None:
        """Advance to next character."""
        self.pos += 1
        self.column = self.pos - self.line_start + 1
    
    def _make_position(self) -> Position:
        """Create position for current location."""
        return Position(
            line=self.line,
            column=self.pos - self.line_start + 1,
            offset=self.pos
        )
    
    def _make_token(self, type: TokenType, value: str, start: Position) -> Token:
        """Create token with start and end positions."""
        return Token(
            type=type,
            value=value,
            start=start,
            end=self._make_position()
        )
