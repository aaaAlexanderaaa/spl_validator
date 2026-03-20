"""SPL Expression Parser - Recursive descent parser for SPL expressions.

Parses:
- Binary operations: +, -, *, /, %, AND, OR, =, !=, <, >, <=, >=
- Unary operations: NOT, -
- Function calls: count(field), if(cond, then, else)
- Literals: strings, numbers, booleans, null
- Field references: field_name, field.subfield
- Assignments: field = expression
"""
from typing import Optional, Any
from ..lexer.tokens import Token, TokenType, Position
from .ast import (
    Expression, BinaryOp, UnaryOp, FunctionCall, FieldRef, Literal,
    Assignment, Pipeline, Command, Clause, Aggregation
)


class ParseError(Exception):
    """Raised when parsing fails."""
    def __init__(self, message: str, position: Position):
        self.message = message
        self.position = position
        super().__init__(f"{message} at {position}")


_DOTTED_NAME_SEGMENT_TYPES = {
    TokenType.IDENTIFIER,
    # Lexer keywords: allow them as dotted field segments (e.g., foo.by, foo.like).
    TokenType.AND,
    TokenType.OR,
    TokenType.NOT,
    TokenType.XOR,
    TokenType.BY,
    TokenType.AS,
    TokenType.OVER,
    TokenType.OUTPUT,
    TokenType.OUTPUTNEW,
    TokenType.WHERE,
    TokenType.LIKE,
    TokenType.TRUE,
    TokenType.FALSE,
    TokenType.NULL,
}


def _is_dotted_name_segment(token: Token) -> bool:
    return token.type in _DOTTED_NAME_SEGMENT_TYPES


class ExpressionParser:
    """Recursive descent parser for SPL expressions.
    
    Operator precedence (lowest to highest):
    1. OR
    2. AND, XOR
    3. NOT (unary)
    4. =, !=, <, >, <=, >=
    5. +, -
    6. *, /, %
    7. Unary -, function calls, literals, parentheses
    """
    
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def current(self) -> Token:
        """Get current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        # Return EOF token
        last = self.tokens[-1] if self.tokens else Token(TokenType.EOF, '', Position(1,1,0), Position(1,1,0))
        return Token(TokenType.EOF, '', last.end, last.end)
    
    def peek(self, offset: int = 0) -> Token:
        """Peek at token at offset from current."""
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.current()
    
    def advance(self) -> Token:
        """Advance and return previous token."""
        token = self.current()
        self.pos += 1
        return token
    
    def match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self.current().type in types
    
    def consume(self, type: TokenType, error_msg: str) -> Token:
        """Consume token of expected type or raise error."""
        if self.current().type == type:
            return self.advance()
        raise ParseError(error_msg, self.current().start)
    
    def at_end(self) -> bool:
        """Check if at end of tokens."""
        return self.current().type == TokenType.EOF
    
    # === Expression Parsing (Recursive Descent) ===
    
    def parse_expression(self) -> Expression:
        """Parse a full expression."""
        return self.parse_or()
    
    def parse_or(self) -> Expression:
        """Parse OR expressions."""
        left = self.parse_and()
        
        while self.match(TokenType.OR):
            op_token = self.advance()
            right = self.parse_and()
            left = BinaryOp(
                left=left,
                operator="OR",
                right=right,
                start=left.start,
                end=right.end
            )
        
        return left
    
    def parse_and(self) -> Expression:
        """Parse AND/XOR expressions."""
        left = self.parse_not()
        
        while self.match(TokenType.AND, TokenType.XOR):
            op_token = self.advance()
            right = self.parse_not()
            left = BinaryOp(
                left=left,
                operator=op_token.value.upper(),
                right=right,
                start=left.start,
                end=right.end
            )
        
        return left
    
    def parse_not(self) -> Expression:
        """Parse NOT expressions."""
        if self.match(TokenType.NOT):
            op_token = self.advance()
            operand = self.parse_not()
            return UnaryOp(
                operator="NOT",
                operand=operand,
                start=op_token.start,
                end=operand.end
            )
        return self.parse_comparison()
    
    def parse_comparison(self) -> Expression:
        """Parse comparison expressions: =, ==, !=, <, >, <=, >=, LIKE."""
        left = self.parse_additive()
        
        while True:
            if self.match(
                TokenType.EQ,
                TokenType.EQEQ,
                TokenType.NEQ,
                TokenType.LT,
                TokenType.GT,
                TokenType.LTE,
                TokenType.GTE,
                TokenType.LIKE,
            ):
                op_token = self.advance()
                right = self.parse_additive()
                left = BinaryOp(
                    left=left,
                    operator=op_token.value.upper() if op_token.type == TokenType.LIKE else op_token.value,
                    right=right,
                    start=left.start,
                    end=right.end
                )
                continue

            if (
                self.match(TokenType.IDENTIFIER)
                and self.current().value.lower() == "in"
                and self.peek(1).type == TokenType.LPAREN
            ):
                self.advance()  # IN
                self.advance()  # (
                args: list[Expression] = [left]
                if not self.match(TokenType.RPAREN):
                    args.append(self._parse_in_list_item())
                    while self.match(TokenType.COMMA):
                        self.advance()
                        args.append(self._parse_in_list_item())
                end_token = self.consume(TokenType.RPAREN, "Expected ')' after IN (...) list")
                left = FunctionCall(name="in", args=args, start=left.start, end=end_token.end)
                continue

            break
        
        return left

    def _parse_in_list_item(self) -> Expression:
        tok = self.current()

        if tok.type == TokenType.STRING:
            self.advance()
            return Literal(value=tok.value, type="string", start=tok.start, end=tok.end)

        if tok.type == TokenType.NUMBER:
            self.advance()
            return Literal(value=self._parse_number(tok.value), type="number", start=tok.start, end=tok.end)

        if tok.type == TokenType.TRUE:
            self.advance()
            return Literal(value=True, type="boolean", start=tok.start, end=tok.end)

        if tok.type == TokenType.FALSE:
            self.advance()
            return Literal(value=False, type="boolean", start=tok.start, end=tok.end)

        if tok.type == TokenType.NULL:
            self.advance()
            return Literal(value=None, type="null", start=tok.start, end=tok.end)

        if tok.type in (TokenType.IDENTIFIER, TokenType.STAR):
            start = tok.start
            parts: list[str] = [self.advance().value]
            end = tok.end
            while self.match(TokenType.DOT) and _is_dotted_name_segment(self.peek(1)):
                self.advance()  # DOT
                part_tok = self.advance()
                parts.append(part_tok.value)
                end = part_tok.end
            return Literal(value=".".join(parts), type="string", start=start, end=end)

        raise ParseError("Expected value in IN (...) list", tok.start)
    
    def parse_additive(self) -> Expression:
        """Parse + and - expressions."""
        left = self.parse_multiplicative()
        
        while self.match(TokenType.PLUS, TokenType.MINUS, TokenType.DOT):
            op_token = self.advance()
            right = self.parse_multiplicative()
            left = BinaryOp(
                left=left,
                operator=op_token.value,
                right=right,
                start=left.start,
                end=right.end
            )
        
        return left
    
    def parse_multiplicative(self) -> Expression:
        """Parse *, /, % expressions."""
        left = self.parse_unary()
        
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_token = self.advance()
            right = self.parse_unary()
            left = BinaryOp(
                left=left,
                operator=op_token.value,
                right=right,
                start=left.start,
                end=right.end
            )
        
        return left
    
    def parse_unary(self) -> Expression:
        """Parse unary - expressions."""
        if self.match(TokenType.MINUS):
            op_token = self.advance()
            operand = self.parse_unary()
            return UnaryOp(
                operator="-",
                operand=operand,
                start=op_token.start,
                end=operand.end
            )
        return self.parse_primary()
    
    def parse_primary(self) -> Expression:
        """Parse primary expressions: literals, identifiers, function calls, parentheses."""
        token = self.current()
        
        # Parenthesized expression
        if self.match(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')' after expression")
            return expr
        
        # Literals
        if self.match(TokenType.NUMBER):
            self.advance()
            return Literal(
                value=self._parse_number(token.value),
                type="number",
                start=token.start,
                end=token.end
            )
        
        if self.match(TokenType.STRING):
            self.advance()
            return Literal(
                value=token.value,
                type="string",
                start=token.start,
                end=token.end
            )
        
        if self.match(TokenType.TRUE):
            if self.peek(1).type == TokenType.LPAREN:
                name_token = self.advance()
                return self.parse_function_call(name_token)
            self.advance()
            return Literal(value=True, type="boolean", start=token.start, end=token.end)
        
        if self.match(TokenType.FALSE):
            if self.peek(1).type == TokenType.LPAREN:
                name_token = self.advance()
                return self.parse_function_call(name_token)
            self.advance()
            return Literal(value=False, type="boolean", start=token.start, end=token.end)
        
        if self.match(TokenType.NULL):
            if self.peek(1).type == TokenType.LPAREN:
                name_token = self.advance()
                return self.parse_function_call(name_token)
            self.advance()
            return Literal(value=None, type="null", start=token.start, end=token.end)
        
        # Identifier (field reference or function call)
        if self.match(TokenType.IDENTIFIER, TokenType.LIKE):
            name_token = self.advance()
            
            # Check for function call
            if self.match(TokenType.LPAREN):
                return self.parse_function_call(name_token)
            
            # Field reference (dotted identifiers are a single FieldRef).
            parts = [name_token.value]
            end_pos = name_token.end
            while self.match(TokenType.DOT) and _is_dotted_name_segment(self.peek(1)):
                self.advance()  # DOT
                part_tok = self.advance()  # IDENTIFIER or keyword token
                parts.append(part_tok.value)
                end_pos = part_tok.end

            return FieldRef(name=".".join(parts), start=name_token.start, end=end_pos)
        
        # STAR as wildcard
        if self.match(TokenType.STAR):
            self.advance()
            return FieldRef(name="*", start=token.start, end=token.end)

        if self.match(TokenType.MACRO):
            self.advance()
            return Literal(value=token.value, type="macro", start=token.start, end=token.end)
        
        raise ParseError(f"Unexpected token: {token.type.name}", token.start)
    
    def parse_function_call(self, name_token: Token) -> FunctionCall:
        """Parse a function call: name(arg1, arg2, ...)"""
        self.consume(TokenType.LPAREN, "Expected '(' after function name")
        
        args: list[Expression] = []
        
        if not self.match(TokenType.RPAREN):
            args.append(self.parse_expression())
            
            while self.match(TokenType.COMMA):
                self.advance()
                args.append(self.parse_expression())
        
        end_token = self.consume(TokenType.RPAREN, "Expected ')' after arguments")
        
        return FunctionCall(
            name=name_token.value,
            args=args,
            start=name_token.start,
            end=end_token.end
        )
    
    def _parse_number(self, value: str) -> float | int:
        """Parse number string to int or float."""
        if '.' in value or 'e' in value.lower():
            return float(value)
        return int(value)
    
    # === Assignment Parsing ===
    
    def parse_assignment(self) -> Optional[Assignment]:
        """Parse assignment: field = expression
        
        Returns None if not an assignment.
        """
        if self.match(TokenType.STRING):
            if self.peek(1).type != TokenType.EQ:
                return None
            name_token = self.advance()
            self.advance()  # Skip '='
            value = self.parse_expression()
            return Assignment(
                field_name=name_token.value,
                value=value,
                start=name_token.start,
                end=value.end,
            )

        # Look ahead for <dotted-field> =, allowing a leading +/- in the field name.
        if self.match(TokenType.MINUS, TokenType.PLUS):
            sign_tok = self.advance()
            if not self.match(TokenType.IDENTIFIER):
                return None
            offset = 1
            while self.peek(offset).type == TokenType.DOT and _is_dotted_name_segment(self.peek(offset + 1)):
                offset += 2
            if self.peek(offset).type != TokenType.EQ:
                return None
            name_token = self.advance()
            parts = [sign_tok.value + name_token.value]
        else:
            if not self.match(TokenType.IDENTIFIER):
                return None
            offset = 1
            while self.peek(offset).type == TokenType.DOT and _is_dotted_name_segment(self.peek(offset + 1)):
                offset += 2
            if self.peek(offset).type != TokenType.EQ:
                return None
            name_token = self.advance()
            parts = [name_token.value]

        while self.match(TokenType.DOT) and _is_dotted_name_segment(self.peek(1)):
            self.advance()  # DOT
            parts.append(self.advance().value)  # IDENTIFIER or keyword token

        self.advance()  # Skip '='
        value = self.parse_expression()
        
        return Assignment(
            field_name=".".join(parts),
            value=value,
            start=name_token.start,
            end=value.end
        )
    
    # === Aggregation Parsing (for stats commands) ===
    
    def parse_aggregation(self) -> Optional[Aggregation]:
        """Parse aggregation: func(field) [AS alias]
        
        Examples:
            count
            count(field)
            sum(bytes) AS total
        """
        if not self.match(TokenType.IDENTIFIER):
            return None
        
        func_token = self.advance()
        func_name = func_token.value.lower()
        
        agg_field = None
        args: list[Expression] = []
        end_pos = func_token.end
        
        # Check for function arguments
        if self.match(TokenType.LPAREN):
            self.advance()
            
            if not self.match(TokenType.RPAREN):
                # Parse field or expression
                if self.match(TokenType.IDENTIFIER):
                    field_token = self.advance()
                    agg_field = field_token.value
                    end_pos = field_token.end
                elif self.match(TokenType.STAR):
                    self.advance()
                    agg_field = "*"
                else:
                    # Expression argument
                    expr = self.parse_expression()
                    args.append(expr)
                    end_pos = expr.end
            
            rparen = self.consume(TokenType.RPAREN, "Expected ')' after aggregation")
            end_pos = rparen.end
        
        # Check for AS alias
        alias = None
        if self.match(TokenType.AS):
            self.advance()
            if self.match(TokenType.IDENTIFIER):
                alias_token = self.advance()
                alias = alias_token.value
                end_pos = alias_token.end
        
        return Aggregation(
            function=func_name,
            agg_field=agg_field,
            args=args,
            alias=alias,
            start=func_token.start,
            end=end_pos
        )


class CommandParser:
    """Parser for SPL commands with arguments, options, and clauses."""
    
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        last = self.tokens[-1] if self.tokens else Token(TokenType.EOF, '', Position(1,1,0), Position(1,1,0))
        return Token(TokenType.EOF, '', last.end, last.end)
    
    def peek(self, offset: int = 0) -> Token:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.current()
    
    def advance(self) -> Token:
        token = self.current()
        self.pos += 1
        return token
    
    def match(self, *types: TokenType) -> bool:
        return self.current().type in types
    
    def at_command_boundary(self) -> bool:
        """Check if at a command boundary (pipe or EOF)."""
        return self.match(TokenType.PIPE, TokenType.EOF)
    
    def get_remaining_tokens(self) -> list[Token]:
        """Get all remaining unconsumed tokens until command boundary."""
        remaining = []
        while not self.at_command_boundary():
            remaining.append(self.current())
            self.advance()
        return remaining

    def _consume_dotted_identifier(self) -> Optional[str]:
        """Consume IDENTIFIER (DOT IDENTIFIER)* as a single name."""
        if not self.match(TokenType.IDENTIFIER):
            return None
        parts = [self.advance().value]
        while self.match(TokenType.DOT) and _is_dotted_name_segment(self.peek(1)):
            self.advance()  # DOT
            parts.append(self.advance().value)  # IDENTIFIER or keyword token
        return ".".join(parts)
    
    def parse_options(self) -> dict[str, Any]:
        """Parse key=value options until command boundary or clause keyword."""
        options = {}
        
        while not self.at_command_boundary():
            # Check for clause keywords
            if self.match(TokenType.BY, TokenType.AS, TokenType.OVER, 
                          TokenType.OUTPUT, TokenType.OUTPUTNEW, TokenType.WHERE):
                break
            
            # Look for key=value pattern
            if self.match(TokenType.IDENTIFIER):
                offset = 1
                while self.peek(offset).type == TokenType.DOT and _is_dotted_name_segment(self.peek(offset + 1)):
                    offset += 2

                if self.peek(offset).type != TokenType.EQ:
                    break  # Not an option, may be positional arg

                key = self._consume_dotted_identifier()
                if key is None:
                    break
                self.advance()  # Skip '='
                
                # Parse value
                if self.match(TokenType.STRING):
                    options[key] = self.advance().value
                elif self.match(TokenType.NUMBER):
                    val = self.advance().value
                    # Try to parse as int/float, keep as string if it has time suffix
                    try:
                        options[key] = int(val) if '.' not in val else float(val)
                    except ValueError:
                        options[key] = val  # Keep time literals like '1h' as string
                elif self.match(TokenType.MINUS, TokenType.PLUS):
                    # Relative time modifiers like -h, +2d@d.
                    sign = self.advance().value
                    if self.match(TokenType.NUMBER, TokenType.IDENTIFIER):
                        options[key] = sign + self.advance().value
                    else:
                        options[key] = sign
                elif self.match(TokenType.TRUE):
                    self.advance()
                    options[key] = True
                elif self.match(TokenType.FALSE):
                    self.advance()
                    options[key] = False
                elif self.match(TokenType.IDENTIFIER):
                    options[key] = self.advance().value
                else:
                    self.advance()  # Skip unknown
            else:
                break  # Not an option, may be positional arg
        
        return options
    
    def parse_field_list(self) -> list[str]:
        """Parse comma-separated field list."""
        fields = []
        
        while not self.at_command_boundary():
            if self.match(TokenType.IDENTIFIER):
                name = self._consume_dotted_identifier()
                if name is None:
                    break
                fields.append(name)
            elif self.match(TokenType.STAR):
                fields.append(self.advance().value)
            else:
                break
            
            # Optional comma
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        return fields
    
    def parse_by_clause(self) -> Optional[Clause]:
        """Parse BY clause: BY field1, field2, ..."""
        if not self.match(TokenType.BY):
            return None
        
        by_token = self.advance()
        fields = self.parse_field_list()
        
        end_pos = fields[-1] if fields else by_token.end
        
        return Clause(
            keyword="BY",
            fields=fields,
            start=by_token.start,
            end=by_token.end  # Simplified
        )
    
    def parse_as_clause(self) -> Optional[tuple[str, str]]:
        """Parse AS clause: old AS new. Returns (old_name, new_name)."""
        if not self.match(TokenType.IDENTIFIER):
            return None
        
        if self.peek(1).type != TokenType.AS:
            return None
        
        old_token = self.advance()
        self.advance()  # Skip AS
        
        if self.match(TokenType.IDENTIFIER):
            new_token = self.advance()
            return (old_token.value, new_token.value)
        
        return None
    
    def parse_stats_args(self) -> tuple[list, list[Token], list[tuple[str, str, Position, Position]]]:
        """Parse stats-style command arguments: func(field) [AS alias], ... BY fields
        
        Returns:
            Tuple of (aggregations, unexpected_tokens, function_errors)
        """
        aggregations = []
        unexpected = []
        function_errors: list[tuple[str, str, Position, Position]] = []

        from ..registry.functions import (
            is_known_function,
            validate_function_arity,
            validate_function_context,
        )

        def _first_dotted_identifier(inner: list[Token]) -> Optional[str]:
            """Extract first dotted identifier sequence from tokens inside outer parens."""
            if not inner:
                return None
            i = 0
            parts: list[str] = []
            while i < len(inner):
                t = inner[i]
                if t.type != TokenType.IDENTIFIER:
                    i += 1
                    continue
                # Skip identifiers that are clearly function calls at this nesting level, e.g. eval(...), if(...).
                if i + 1 < len(inner) and inner[i + 1].type == TokenType.LPAREN:
                    i += 1
                    continue
                parts = [t.value]
                j = i
                while (
                    j + 2 < len(inner)
                    and inner[j + 1].type == TokenType.DOT
                    and _is_dotted_name_segment(inner[j + 2])
                ):
                    parts.append(inner[j + 2].value)
                    j += 2
                return ".".join(parts)
            return None
        
        while not self.at_command_boundary():
            # Check for BY clause
            if self.match(TokenType.BY):
                break
            
            # Check for aggregation: identifier followed by ( or AS or comma
            if self.match(TokenType.IDENTIFIER):
                # Could be: func(...) or func AS alias or just func
                start_pos = self.pos
                func_token = self.advance()
                
                agg_field = None
                alias = None
                
                # Check for function call and validate top-level arity for stats aggregations.
                arg_count = 0
                end_pos = func_token.end
                if self.match(TokenType.LPAREN):
                    lparen = self.advance()  # (
                    paren_depth = 1
                    inner_tokens: list[Token] = []

                    # Count top-level arguments inside the outer parentheses. Commas inside nested
                    # parentheses (e.g., `sum(eval(if(a,b,c)))`) do not count as additional args.
                    current_arg_has_tokens = False
                    while not self.at_command_boundary() and paren_depth > 0:
                        tok = self.current()

                        if tok.type == TokenType.LPAREN:
                            paren_depth += 1
                            if paren_depth == 2:
                                # Still part of the current top-level arg (function call, grouping)
                                current_arg_has_tokens = True
                            if paren_depth >= 2:
                                inner_tokens.append(tok)
                            self.advance()
                            continue

                        if tok.type == TokenType.RPAREN:
                            paren_depth -= 1
                            end_pos = tok.end
                            self.advance()
                            if paren_depth == 0:
                                if current_arg_has_tokens:
                                    arg_count += 1
                                break
                            if paren_depth >= 1:
                                inner_tokens.append(tok)
                            continue

                        if tok.type == TokenType.COMMA and paren_depth == 1:
                            if current_arg_has_tokens:
                                arg_count += 1
                            current_arg_has_tokens = False
                            self.advance()
                            continue

                        if paren_depth == 1:
                            current_arg_has_tokens = True
                            inner_tokens.append(tok)
                        elif paren_depth >= 2:
                            inner_tokens.append(tok)
                        self.advance()

                    if paren_depth > 0:
                        function_errors.append((
                            "SPL009",
                            f"Unclosed parentheses in {func_token.value} aggregation",
                            lparen.start,
                            end_pos,
                        ))
                    else:
                        agg_field = _first_dotted_identifier(inner_tokens)
                else:
                    # No parentheses: e.g. `count`
                    arg_count = 0

                # Validate aggregation function name and arity in stats context.
                if not is_known_function(func_token.value):
                    function_errors.append(
                        (
                            "SPL023",
                            f"Unknown function '{func_token.value}'",
                            func_token.start,
                            end_pos,
                        )
                    )
                else:
                    ctx_err = validate_function_context(func_token.value, "stats")
                    if ctx_err:
                        function_errors.append(("SPL021", ctx_err, func_token.start, end_pos))
                    arity_err = validate_function_arity(
                        func_token.value, arg_count, context="stats"
                    )
                    if arity_err:
                        function_errors.append(
                            ("SPL020", arity_err, func_token.start, end_pos)
                        )
                
                # Check for AS alias
                if self.match(TokenType.AS):
                    self.advance()  # AS
                    alias_name = self._consume_dotted_identifier()
                    if alias_name is None and self.match(TokenType.STRING):
                        alias_name = self.advance().value
                    if alias_name:
                        alias = alias_name
                        # Some real-world searches use parenthetical suffixes in alias names,
                        # e.g. `AS aceFlags(inheritance)`. Treat the parenthetical as part of
                        # the alias token stream to avoid mis-parsing it as another aggregation.
                        if self.match(TokenType.LPAREN):
                            self.advance()  # '('
                            depth = 1
                            inner: list[str] = []
                            while not self.at_command_boundary() and depth > 0:
                                tok = self.current()
                                if tok.type == TokenType.LPAREN:
                                    depth += 1
                                    inner.append(tok.value)
                                    self.advance()
                                    continue
                                if tok.type == TokenType.RPAREN:
                                    depth -= 1
                                    self.advance()
                                    if depth == 0:
                                        break
                                    inner.append(tok.value)
                                    continue
                                inner.append(tok.value)
                                self.advance()
                            if depth == 0:
                                alias = alias + "(" + "".join(inner) + ")"

                aggregations.append(
                    Aggregation(
                        function=func_token.value,
                        agg_field=agg_field,
                        args=[],
                        alias=alias,
                        start=func_token.start,
                        end=end_pos,
                    )
                )
                
                # After an aggregation, expect comma, BY, or end
                if self.match(TokenType.COMMA):
                    self.advance()
                    continue
                elif self.match(TokenType.BY) or self.at_command_boundary():
                    continue
                elif self.match(TokenType.IDENTIFIER):
                    continue
                else:
                    # Other token, skip
                    if not self.at_command_boundary():
                        self.advance()
            else:
                # Non-identifier, skip
                if not self.at_command_boundary() and not self.match(TokenType.BY):
                    unexpected.append(self.advance())
        
        return aggregations, unexpected, function_errors
