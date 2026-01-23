"""Core orchestrator - main validation pipeline."""
from typing import Optional, Any
from .src.lexer import Lexer, Token, TokenType, Position, KEYWORDS
from .src.parser.ast import Pipeline, Command, Clause, Subsearch
from .src.parser.parser import CommandParser, ExpressionParser, ParseError
from .src.models import ValidationResult, Severity
from .src.registry import is_generating_command, is_known_command, get_command, get_function
from .src.analyzer import validate_sequence, get_limit
from .src.analyzer.suggestions import check_suggestions


# Keyword tokens that can also be command names
COMMAND_KEYWORDS = {TokenType.WHERE}


def _is_command_keyword(token_type: TokenType) -> bool:
    """Check if token type is a keyword that can also be a command name."""
    return token_type in COMMAND_KEYWORDS


def validate(
    spl: str,
    *,
    strict: bool = False,
    schema_fields: Optional[set[str]] = None,
    schema_missing_severity: str = "error",
) -> ValidationResult:
    """Validate an SPL query string.
    
    Returns:
        ValidationResult with is_valid, errors, warnings, and AST.
    """
    result = ValidationResult(spl=spl, is_valid=True)

    def _pos_from_offset(text: str, offset: int) -> Position:
        line = 1
        col = 1
        last_nl = -1
        for i, ch in enumerate(text):
            if i >= offset:
                break
            if ch == "\n":
                line += 1
                last_nl = i
        col = offset - last_nl
        return Position(line=line, column=col, offset=offset)

    def _mask_markdown_triple_backticks(text: str) -> tuple[str, list[tuple[int, int]], bool]:
        """Replace ```...``` spans with whitespace (preserving newlines and offsets)."""
        spans: list[tuple[int, int]] = []
        out = list(text)
        i = 0
        unclosed = False
        while True:
            start = text.find("```", i)
            if start < 0:
                break
            end = text.find("```", start + 3)
            if end < 0:
                unclosed = True
                break
            end += 3
            spans.append((start, end))
            for j in range(start, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
        return "".join(out), spans, unclosed

    spl_for_lexing, fenced_spans, unclosed_fence = _mask_markdown_triple_backticks(spl)
    if fenced_spans:
        start_off, end_off = fenced_spans[0]
        result.add_warning(
            "SPL052",
            "Ignoring markdown fence ```...``` blocks (not SPL syntax)",
            _pos_from_offset(spl, start_off),
            _pos_from_offset(spl, end_off),
            suggestion="Remove ```...``` from the SPL before running in Splunk.",
        )
    if unclosed_fence:
        start_off = spl.find("```")
        start = _pos_from_offset(spl, start_off if start_off >= 0 else 0)
        result.add_error(
            "SPL011",
            "Unclosed markdown fence ``` (expected closing ```)",
            start,
            start,
            suggestion="Add the closing ``` or remove the fence markers.",
        )
        return result
    setattr(result, "_lex_spl", spl_for_lexing)
    
    # Phase 1: Lexical analysis
    lexer = Lexer(spl_for_lexing)
    tokens = lexer.tokenize()
    
    # Check for lexer errors
    for token in tokens:
        if token.type == TokenType.ERROR:
            if token.value.startswith('"') or token.value.startswith("'"):
                result.add_error(
                    "SPL004",
                    f"Unclosed string literal",
                    token.start,
                    token.end,
                    suggestion="Add closing quote"
                )
            else:
                result.add_error(
                    "SPL007",
                    f"Invalid character: {token.value!r}",
                    token.start,
                    token.end
                )
    
    # Phase 2: Parse into AST (simplified for now)
    ast = parse_simple(tokens, result)
    result.ast = ast
    
    if ast is None:
        return result
    
    # Phase 3: Semantic validation
    validate_sequence(ast, result)
    from .src.analyzer.subsearch import validate_all_subsearches
    validate_all_subsearches(ast, result)
    validate_commands(ast, result, strict=strict)
    validate_limits(ast, result)
    validate_functions(ast, result)
    validate_semantics(ast, result)  # KB-aligned semantic warnings
    check_suggestions(ast, result)  # Best-practice and optimization suggestions
    
    # Phase 4: Field tracking
    from .src.analyzer.fields import track_fields
    missing_sev = schema_missing_severity.lower().strip()
    if missing_sev not in {"error", "warning"}:
        missing_sev = "error"
    track_fields(
        ast,
        result,
        schema_fields=schema_fields,
        missing_field_severity=(Severity.ERROR if missing_sev == "error" else Severity.WARNING),
    )
    
    return result


def parse_simple(tokens: list[Token], result: ValidationResult) -> Optional[Pipeline]:
    """Simple parser that extracts commands from tokens.
    
    This is a simplified parser for Phase 1. Full parser with expression
    parsing will be implemented in Phase 2.
    """
    if not tokens:
        return None
    
    commands: list[Command] = []
    current_cmd: Optional[Command] = None
    i = 0

    def _extract_single_subsearch(arg_tokens: list[Token]) -> tuple[Optional[Subsearch], list[Token]]:
        """Extract at most one bracketed subsearch: [...], returning (subsearch, remaining_tokens)."""
        bracket_start: Optional[int] = None
        bracket_end: Optional[int] = None
        depth = 0
        for idx, tok in enumerate(arg_tokens):
            if tok.type == TokenType.LBRACKET:
                bracket_start = idx
                depth = 1
                for jdx in range(idx + 1, len(arg_tokens)):
                    if arg_tokens[jdx].type == TokenType.LBRACKET:
                        depth += 1
                    elif arg_tokens[jdx].type == TokenType.RBRACKET:
                        depth -= 1
                        if depth == 0:
                            bracket_end = jdx
                            break
                break

        if bracket_start is None:
            return None, arg_tokens

        if bracket_end is None:
            start_tok = arg_tokens[bracket_start]
            result.add_error(
                "SPL011",
                "Unclosed subsearch bracket '['",
                start_tok.start,
                start_tok.end,
                suggestion="Add a closing ']' for the subsearch",
            )
            return None, arg_tokens

        inner = arg_tokens[bracket_start + 1 : bracket_end]
        lbr = arg_tokens[bracket_start]
        rbr = arg_tokens[bracket_end]

        inner_pipeline: Optional[Pipeline] = None
        if inner:
            eof_pos = inner[-1].end
            inner_tokens = inner + [Token(TokenType.EOF, "", eof_pos, eof_pos)]
            inner_pipeline = parse_simple(inner_tokens, result)

        subsearch = Subsearch(start=lbr.start, end=rbr.end, pipeline=inner_pipeline)
        remaining = arg_tokens[:bracket_start] + arg_tokens[bracket_end + 1 :]
        return subsearch, remaining

    def _scan_search_kv_options(search_tokens: list[Token]) -> dict[str, Any]:
        """Extract common base-search key=value options even when they are not leading."""
        keys = {"index", "sourcetype", "host", "source", "earliest", "latest"}
        out: dict[str, Any] = {}
        k = 0
        while k < len(search_tokens):
            tok = search_tokens[k]
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() in keys:
                if k + 1 < len(search_tokens) and search_tokens[k + 1].type == TokenType.EQ:
                    key = tok.value
                    v_idx = k + 2
                    if v_idx >= len(search_tokens):
                        break
                    v = search_tokens[v_idx]

                    if v.type == TokenType.STRING:
                        out[key] = v.value
                        k = v_idx + 1
                        continue

                    if v.type == TokenType.NUMBER:
                        try:
                            out[key] = int(v.value) if "." not in v.value else float(v.value)
                        except ValueError:
                            out[key] = v.value
                        k = v_idx + 1
                        continue

                    if v.type in (TokenType.MINUS, TokenType.PLUS):
                        sign = v.value
                        if v_idx + 1 < len(search_tokens) and search_tokens[v_idx + 1].type in (
                            TokenType.NUMBER,
                            TokenType.IDENTIFIER,
                        ):
                            out[key] = sign + search_tokens[v_idx + 1].value
                            k = v_idx + 2
                            continue
                        out[key] = sign
                        k = v_idx + 1
                        continue

                    if v.type == TokenType.TRUE:
                        out[key] = True
                        k = v_idx + 1
                        continue

                    if v.type == TokenType.FALSE:
                        out[key] = False
                        k = v_idx + 1
                        continue

                    if v.type in (TokenType.IDENTIFIER, TokenType.MACRO):
                        out[key] = v.value
                        k = v_idx + 1
                        continue
            k += 1
        return out
    
    # Handle implicit search at start (no pipe)
    if tokens[0].type != TokenType.PIPE:
        # Find first pipe or end
        start_pos = tokens[0].start
        cmd_tokens = []
        bracket_depth = 0
        while i < len(tokens) and tokens[i].type != TokenType.EOF:
            if tokens[i].type == TokenType.PIPE and bracket_depth == 0:
                break
            if tokens[i].type == TokenType.LBRACKET:
                bracket_depth += 1
            elif tokens[i].type == TokenType.RBRACKET and bracket_depth > 0:
                bracket_depth -= 1
            cmd_tokens.append(tokens[i])
            i += 1
        
        if cmd_tokens:
            # Check if first token is a known command name
            first_token = cmd_tokens[0]
            options = {}
            clauses = {}
            args = []
            
            if first_token.type == TokenType.IDENTIFIER:
                cmd_name = first_token.value.lower()
                if is_known_command(cmd_name) and not is_generating_command(cmd_name):
                    # It's a command but not generating - will error in sequence validation
                    current_cmd = Command(
                        name=first_token.value,
                        start=first_token.start,
                        end=cmd_tokens[-1].end if cmd_tokens else first_token.end
                    )
                elif is_known_command(cmd_name):
                    # Known generating command - parse options
                    subsearch: Optional[Subsearch] = None
                    if len(cmd_tokens) > 1:
                        subsearch, arg_tokens = _extract_single_subsearch(cmd_tokens[1:])
                        cmd_parser = CommandParser(arg_tokens)
                        try:
                            options = cmd_parser.parse_options()
                            remaining = cmd_parser.get_remaining_tokens()
                            if remaining:
                                from .src.parser.ast import Argument
                                for tok in remaining:
                                    args.append(Argument(start=tok.start, end=tok.end, value=tok.value))
                                if cmd_name == "search":
                                    options.update(_scan_search_kv_options(remaining))
                                # If the leftover begins with a known command name, it's very likely a missing pipe.
                                first_leftover = remaining[0]
                                if first_leftover.type == TokenType.IDENTIFIER and is_known_command(first_leftover.value.lower()):
                                    result.add_error(
                                        "SPL012",
                                        f"Missing pipe '|' before command '{first_leftover.value}'",
                                        first_leftover.start,
                                        first_leftover.end,
                                        suggestion=f"Did you forget a pipe '|' before '{first_leftover.value}'?"
                                    )
                        except ParseError as e:
                            result.add_error("SPL011", e.message, e.position, e.position)
                    current_cmd = Command(
                        name=first_token.value,
                        start=first_token.start,
                        end=cmd_tokens[-1].end if cmd_tokens else first_token.end,
                        options=options,
                        clauses=clauses,
                        args=args,
                        subsearch=subsearch,
                    )
                else:
                    # Implicit search - parse from all tokens
                    subsearch, arg_tokens = _extract_single_subsearch(cmd_tokens)
                    cmd_parser = CommandParser(arg_tokens)
                    try:
                        options = cmd_parser.parse_options()
                        remaining = cmd_parser.get_remaining_tokens()
                        if remaining:
                            from .src.parser.ast import Argument
                            for tok in remaining:
                                args.append(Argument(start=tok.start, end=tok.end, value=tok.value))
                            options.update(_scan_search_kv_options(remaining))
                            first_leftover = remaining[0]
                            if first_leftover.type == TokenType.IDENTIFIER and is_known_command(first_leftover.value.lower()):
                                result.add_error(
                                    "SPL012",
                                    f"Missing pipe '|' before command '{first_leftover.value}'",
                                    first_leftover.start,
                                    first_leftover.end,
                                    suggestion=f"Did you forget a pipe '|' before '{first_leftover.value}'?"
                                )
                    except ParseError as e:
                        result.add_error("SPL011", e.message, e.position, e.position)
                    current_cmd = Command(
                        name="search",
                        start=start_pos,
                        end=cmd_tokens[-1].end if cmd_tokens else start_pos,
                        options=options,
                        clauses=clauses,
                        args=args,
                        subsearch=subsearch,
                    )
            else:
                # Implicit search with terms (starts with non-identifier like NOT, (, [, "...")
                subsearch, arg_tokens = _extract_single_subsearch(cmd_tokens)
                cmd_parser = CommandParser(arg_tokens)
                try:
                    options = cmd_parser.parse_options()
                    remaining = cmd_parser.get_remaining_tokens()
                    if remaining:
                        from .src.parser.ast import Argument
                        for tok in remaining:
                            args.append(Argument(start=tok.start, end=tok.end, value=tok.value))
                        options.update(_scan_search_kv_options(remaining))
                except ParseError as e:
                    result.add_error("SPL011", e.message, e.position, e.position)
                current_cmd = Command(
                    name="search",
                    start=start_pos,
                    end=cmd_tokens[-1].end if cmd_tokens else start_pos,
                    options=options,
                    clauses=clauses,
                    args=args,
                    subsearch=subsearch,
                )
            
            commands.append(current_cmd)
    
    # Process pipe-separated commands
    while i < len(tokens):
        token = tokens[i]
        
        if token.type == TokenType.EOF:
            break
        
        if token.type == TokenType.PIPE:
            pipe_pos = token.start
            i += 1
            
                # Next token should be command name (IDENTIFIER or keyword like WHERE)
            if i < len(tokens) and (
                tokens[i].type == TokenType.IDENTIFIER
                or _is_command_keyword(tokens[i].type)
                or tokens[i].type == TokenType.MACRO
            ):
                cmd_start = tokens[i]
                cmd_name = cmd_start.value
                
                # Collect all tokens for this command.
                # Pipes inside bracketed subsearches do not end the outer command.
                cmd_tokens = []
                j = i
                bracket_depth = 0
                while j < len(tokens) and tokens[j].type != TokenType.EOF:
                    if tokens[j].type == TokenType.PIPE and bracket_depth == 0:
                        break
                    if tokens[j].type == TokenType.LBRACKET:
                        bracket_depth += 1
                    elif tokens[j].type == TokenType.RBRACKET and bracket_depth > 0:
                        bracket_depth -= 1
                    cmd_tokens.append(tokens[j])
                    j += 1
                
                cmd_end = tokens[j-1] if j > i else cmd_start
                i = j

                def _coalesce_dotted_identifiers(raw_tokens: list[Token]) -> list[Token | str]:
                    """Coalesce IDENTIFIER (DOT IDENTIFIER)+ sequences into single string values.

                    Outside eval expressions, a.b generally denotes a field name, not concatenation.
                    """
                    dotted_segment_types = {TokenType.IDENTIFIER}.union(set(KEYWORDS.values()))
                    out: list[Token | str] = []
                    k = 0
                    while k < len(raw_tokens):
                        t = raw_tokens[k]
                        if t.type == TokenType.IDENTIFIER:
                            parts = [t.value]
                            end_tok = t
                            kk = k
                            while (
                                kk + 2 < len(raw_tokens)
                                and raw_tokens[kk + 1].type == TokenType.DOT
                                and raw_tokens[kk + 2].type in dotted_segment_types
                            ):
                                parts.append(raw_tokens[kk + 2].value)
                                end_tok = raw_tokens[kk + 2]
                                kk += 2
                            if kk != k:
                                out.append(".".join(parts))
                                k = kk + 1
                                continue
                        out.append(t)
                        k += 1
                    return out

                def _normalize_positional_arg_tokens(raw_tokens: list[Token]) -> list[Token]:
                    """Drop separators and coalesce +/- prefixes with following names."""
                    dotted_segment_types = {TokenType.IDENTIFIER}.union(set(KEYWORDS.values()))
                    out: list[Token] = []
                    k = 0
                    while k < len(raw_tokens):
                        t = raw_tokens[k]

                        if t.type == TokenType.COMMA:
                            k += 1
                            continue

                        if t.type in (TokenType.MINUS, TokenType.PLUS):
                            if k + 1 < len(raw_tokens) and raw_tokens[k + 1].type in dotted_segment_types:
                                nxt = raw_tokens[k + 1]
                                out.append(Token(TokenType.IDENTIFIER, t.value + nxt.value, t.start, nxt.end))
                                k += 2
                                continue
                            # Standalone +/- should not count as a positional arg.
                            k += 1
                            continue

                        out.append(t)
                        k += 1
                    return out

                def _is_positional_arg_token(tok: Token) -> bool:
                    return tok.type in (
                        TokenType.IDENTIFIER,
                        TokenType.STRING,
                        TokenType.NUMBER,
                        TokenType.STAR,
                        TokenType.MACRO,
                    )

                # Extract at most one bracketed subsearch: [...]. Keep it structured in cmd.subsearch.
                subsearch: Optional[Subsearch] = None
                arg_tokens = cmd_tokens[1:]  # Skip command name
                bracket_start = None
                bracket_end = None
                depth = 0
                for idx, tok in enumerate(arg_tokens):
                    if tok.type == TokenType.LBRACKET:
                        bracket_start = idx
                        depth = 1
                        for jdx in range(idx + 1, len(arg_tokens)):
                            if arg_tokens[jdx].type == TokenType.LBRACKET:
                                depth += 1
                            elif arg_tokens[jdx].type == TokenType.RBRACKET:
                                depth -= 1
                                if depth == 0:
                                    bracket_end = jdx
                                    break
                        break

                if bracket_start is not None and bracket_end is None:
                    # Unclosed subsearch; record and continue parsing remaining args as-is.
                    start_tok = arg_tokens[bracket_start]
                    result.add_error(
                        "SPL011",
                        "Unclosed subsearch bracket '['",
                        start_tok.start,
                        start_tok.end,
                        suggestion="Add a closing ']' for the subsearch",
                    )
                elif bracket_start is not None and bracket_end is not None:
                    inner = arg_tokens[bracket_start + 1 : bracket_end]
                    lbr = arg_tokens[bracket_start]
                    rbr = arg_tokens[bracket_end]
                    inner_pipeline: Optional[Pipeline] = None
                    if inner:
                        eof_pos = inner[-1].end
                        inner_tokens = inner + [Token(TokenType.EOF, "", eof_pos, eof_pos)]
                        inner_pipeline = parse_simple(inner_tokens, result)
                    subsearch = Subsearch(start=lbr.start, end=rbr.end, pipeline=inner_pipeline)
                    arg_tokens = arg_tokens[:bracket_start] + arg_tokens[bracket_end + 1 :]
                
                # Parse options and clauses using CommandParser
                options = {}
                clauses = {}
                args = []  # Capture command arguments
                aggregations = []
                if cmd_start.type == TokenType.MACRO:
                    # Represent a macro invocation as an opaque "macro" command.
                    from .src.parser.ast import Argument
                    args.append(Argument(start=cmd_start.start, end=cmd_start.end, value=cmd_start.value))
                    cmd_name = "macro"
                elif len(cmd_tokens) > 1:  # Has more than just command name
                    # For some commands (eval/where), the "arguments" are full expressions
                    # and should not be parsed as key=value options.
                    cmd_parser = CommandParser(arg_tokens)  # Skip command name (and any subsearch)
                    try:
                        # For stats-like commands, use specialized parsing
                        stats_commands = {"stats", "chart", "timechart", "eventstats", "streamstats"}
                        if cmd_name.lower() in stats_commands:
                            # Store all tokens as args for field tracking to parse aliases
                            from .src.parser.ast import Argument
                            for tok in arg_tokens:  # Skip command name
                                if tok.type in (TokenType.IDENTIFIER, TokenType.AS):
                                    args.append(Argument(
                                        start=tok.start,
                                        end=tok.end,
                                        value=tok.value
                                    ))
                            
                            # First parse options (e.g., span=1h for timechart)
                            options = cmd_parser.parse_options()
                            # Then parse aggregations and detect unexpected tokens / invalid aggregations
                            aggregations, unexpected_tokens, function_errors = cmd_parser.parse_stats_args()
                            for tok in unexpected_tokens:
                                result.add_error(
                                    "SPL008",
                                    f"Unexpected identifier '{tok.value}' in {cmd_name} command",
                                    tok.start,
                                    tok.end,
                                    suggestion="Check syntax: this may be a typo or misplaced argument"
                                )
                            for code, message, start, end in function_errors:
                                result.add_error(code, message, start, end)
                            by_clause = cmd_parser.parse_by_clause()
                            if by_clause:
                                clauses['BY'] = by_clause
                        elif cmd_name.lower() in ("top", "rare"):
                            # top/rare syntax includes an optional leading number and an inline BY clause.
                            from .src.parser.ast import Argument, Clause

                            options = cmd_parser.parse_options()
                            remaining = _normalize_positional_arg_tokens(cmd_parser.get_remaining_tokens())

                            k = 0
                            if k < len(remaining) and remaining[k].type == TokenType.NUMBER and "limit" not in options:
                                try:
                                    options["limit"] = int(remaining[k].value)
                                except ValueError:
                                    options["limit"] = remaining[k].value
                                k += 1

                            # Parse target field list until BY or end
                            target_tokens: list[Token] = []
                            by_tokens: list[Token] = []
                            saw_by = False
                            while k < len(remaining):
                                tok = remaining[k]
                                if tok.type == TokenType.BY:
                                    saw_by = True
                                    k += 1
                                    break
                                target_tokens.append(tok)
                                k += 1

                            if saw_by:
                                by_tokens = remaining[k:]

                            for item in _coalesce_dotted_identifiers(target_tokens):
                                if isinstance(item, str):
                                    args.append(Argument(start=cmd_start.start, end=cmd_end.end, value=item))
                                else:
                                    if item.type == TokenType.IDENTIFIER:
                                        args.append(Argument(start=item.start, end=item.end, value=item.value))

                            if by_tokens:
                                by_fields: list[str] = []
                                for item in _coalesce_dotted_identifiers(by_tokens):
                                    if isinstance(item, str):
                                        by_fields.append(item)
                                    else:
                                        if item.type == TokenType.IDENTIFIER:
                                            by_fields.append(item.value)
                                if by_fields:
                                    clauses["BY"] = Clause(
                                        keyword="BY",
                                        fields=by_fields,
                                        start=by_tokens[0].start,
                                        end=by_tokens[-1].end,
                                    )
                        elif cmd_name.lower() == "eval":
                            # Parse one or more assignments separated by commas:
                            #   eval a=expr, b=expr2
                            from .src.parser.ast import Argument, Assignment

                            if not arg_tokens:
                                result.add_error(
                                    "SPL014",
                                    "eval is missing required assignments",
                                    cmd_start.start,
                                    cmd_end.end,
                                    suggestion="Example: | eval status=if(code>=400,\"error\",\"ok\")",
                                )
                            else:
                                expr_parser = ExpressionParser(arg_tokens)
                                while not expr_parser.at_end():
                                    if expr_parser.match(TokenType.MACRO):
                                        tok = expr_parser.advance()
                                        result.add_warning(
                                            "SPL053",
                                            "Macro used inside eval; skipping further eval validation (macro expansion is not supported)",
                                            tok.start,
                                            tok.end,
                                            suggestion="Expand the macro before validating, or remove it from eval.",
                                        )
                                        break
                                    try:
                                        assignment = expr_parser.parse_assignment()
                                    except ParseError as e:
                                        result.add_error("SPL011", e.message, e.position, e.position)
                                        # Make progress to avoid infinite loop.
                                        if not expr_parser.at_end():
                                            expr_parser.advance()
                                        continue
                                    if assignment is None:
                                        # Avoid infinite loops: consume one expression (or token) and report.
                                        start_token = expr_parser.current()
                                        try:
                                            expr_parser.parse_expression()
                                        except ParseError as e:
                                            result.add_error("SPL011", e.message, e.position, e.position)
                                            expr_parser.advance()
                                        result.add_error(
                                            "SPL010",
                                            "eval requires assignment syntax: <field>=<expression>",
                                            start_token.start,
                                            start_token.end,
                                            suggestion='Example: | eval status=if(code>=400,"error","ok")',
                                        )
                                    else:
                                        args.append(Argument(start=assignment.start, end=assignment.end, value=assignment))

                                    if expr_parser.at_end():
                                        break

                                    if expr_parser.match(TokenType.COMMA):
                                        expr_parser.advance()
                                        if expr_parser.at_end():
                                            result.add_error(
                                                "SPL011",
                                                "Trailing comma in eval assignment list",
                                                cmd_start.start,
                                                cmd_end.end,
                                                suggestion="Remove the trailing comma",
                                            )
                                            break
                                        continue
                                    if expr_parser.match(TokenType.MACRO):
                                        tok = expr_parser.advance()
                                        result.add_warning(
                                            "SPL053",
                                            "Macro used inside eval; skipping further eval validation (macro expansion is not supported)",
                                            tok.start,
                                            tok.end,
                                            suggestion="Expand the macro before validating, or remove it from eval.",
                                        )
                                        break

                                    # Not end and not comma: missing separator between assignments.
                                    next_tok = expr_parser.current()
                                    result.add_error(
                                        "SPL010",
                                        "Expected ',' between eval assignments",
                                        next_tok.start,
                                        next_tok.end,
                                        suggestion="Use: | eval a=1, b=2",
                                    )
                                    # Recovery: treat as if a comma was present and continue.
                                    continue
                        elif cmd_name.lower() == "where":
                            from .src.parser.ast import Argument

                            if not arg_tokens:
                                result.add_error(
                                    "SPL014",
                                    "where is missing a required expression",
                                    cmd_start.start,
                                    cmd_end.end,
                                    suggestion="Example: | where status>=400",
                                )
                            else:
                                expr_parser = ExpressionParser(arg_tokens)
                                try:
                                    expr = expr_parser.parse_expression()
                                    args.append(Argument(start=expr.start, end=expr.end, value=expr))
                                    if not expr_parser.at_end():
                                        extra = expr_parser.current()
                                        if extra.type == TokenType.MACRO:
                                            tok = expr_parser.advance()
                                            result.add_warning(
                                                "SPL053",
                                                "Macro used inside where; skipping further where validation (macro expansion is not supported)",
                                                tok.start,
                                                tok.end,
                                                suggestion="Expand the macro before validating, or remove it from where.",
                                            )
                                        else:
                                            result.add_error(
                                                "SPL011",
                                                "Trailing tokens after where expression",
                                                extra.start,
                                                extra.end,
                                                suggestion="Remove trailing tokens or add the missing operator/parenthesis",
                                            )
                                except ParseError as e:
                                    result.add_error("SPL011", e.message, e.position, e.position)
                        elif cmd_name.lower() == "bin":
                            # bin syntax (searchbnf): bin (<bin-options> )* <field> (as <field>)?
                            # We support options appearing before or after the field, but we do NOT
                            # allow extra tokens beyond [AS <field>]. Extra tokens usually indicate
                            # a missing pipe before the next command.
                            from .src.parser.ast import Argument

                            bin_tokens = arg_tokens
                            consumed: set[int] = set()

                            # 1) Capture all key=value options anywhere in the command
                            idx = 0
                            while idx + 2 < len(bin_tokens):
                                t0, t1, t2 = bin_tokens[idx], bin_tokens[idx + 1], bin_tokens[idx + 2]
                                if t0.type == TokenType.IDENTIFIER and t1.type == TokenType.EQ:
                                    key = t0.value
                                    if t2.type == TokenType.STRING:
                                        options[key] = t2.value
                                    elif t2.type == TokenType.NUMBER:
                                        val = t2.value
                                        try:
                                            options[key] = int(val) if "." not in val else float(val)
                                        except ValueError:
                                            options[key] = val
                                    elif t2.type in (TokenType.TRUE, TokenType.FALSE):
                                        options[key] = (t2.type == TokenType.TRUE)
                                    elif t2.type == TokenType.IDENTIFIER:
                                        options[key] = t2.value
                                    else:
                                        options[key] = t2.value
                                    consumed.update({idx, idx + 1, idx + 2})
                                    idx += 3
                                    continue
                                idx += 1

                            # 2) Find the field token (first IDENTIFIER not part of key=value and not AS)
                            field_tok: Optional[Token] = None
                            for i_tok, tok in enumerate(bin_tokens):
                                if i_tok in consumed:
                                    continue
                                if tok.type == TokenType.AS:
                                    continue
                                if tok.type == TokenType.IDENTIFIER:
                                    field_tok = tok
                                    consumed.add(i_tok)
                                    break

                            if field_tok is None:
                                result.add_error(
                                    "SPL010",
                                    "bin requires a target field (e.g. _time)",
                                    cmd_start.start,
                                    cmd_end.end,
                                    suggestion="Example: | bin span=1d _time",
                                )
                            else:
                                args.append(Argument(start=field_tok.start, end=field_tok.end, value=field_tok.value))

                            # 3) Optional AS <field>
                            for i_tok, tok in enumerate(bin_tokens):
                                if i_tok in consumed:
                                    continue
                                if tok.type == TokenType.AS:
                                    consumed.add(i_tok)
                                    # Find next IDENTIFIER
                                    alias_tok = None
                                    for j in range(i_tok + 1, len(bin_tokens)):
                                        if j in consumed:
                                            continue
                                        if bin_tokens[j].type == TokenType.IDENTIFIER:
                                            alias_tok = bin_tokens[j]
                                            consumed.add(j)
                                            break
                                    if alias_tok is None:
                                        result.add_error(
                                            "SPL010",
                                            "bin AS requires a field name after AS",
                                            tok.start,
                                            tok.end,
                                            suggestion="Example: | bin span=1d _time AS day",
                                        )
                                    break

                            # 4) Anything left is unexpected (often missing pipe)
                            leftovers = [bin_tokens[i] for i in range(len(bin_tokens)) if i not in consumed]
                            if leftovers:
                                first = leftovers[0]
                                suggestion = None
                                if first.type == TokenType.IDENTIFIER and is_known_command(first.value.lower()):
                                    suggestion = f"Did you forget a pipe '|' before '{first.value}'?"
                                    result.add_error(
                                        "SPL012",
                                        f"Missing pipe '|' before command '{first.value}'",
                                        first.start,
                                        first.end,
                                        suggestion=suggestion,
                                    )
                                else:
                                    result.add_error(
                                        "SPL008",
                                        f"Unexpected token '{first.value}' in bin command",
                                        first.start,
                                        first.end,
                                        suggestion="Check bin syntax: bin (<options>)* <field> (AS <field>)?",
                                    )
                        else:
                            # Regular commands - parse options
                            options = cmd_parser.parse_options()
                            by_clause = cmd_parser.parse_by_clause()
                            if by_clause:
                                clauses['BY'] = by_clause
                            # Capture remaining tokens as arguments
                            remaining = _normalize_positional_arg_tokens(cmd_parser.get_remaining_tokens())
                            from .src.parser.ast import Argument
                            for item in _coalesce_dotted_identifiers(remaining):
                                if isinstance(item, str):
                                    # Coalesced dotted field name
                                    args.append(Argument(start=cmd_start.start, end=cmd_end.end, value=item))
                                else:
                                    if _is_positional_arg_token(item):
                                        args.append(Argument(start=item.start, end=item.end, value=item.value))
                    except ParseError as e:
                        result.add_error("SPL011", e.message, e.position, e.position)
                
                current_cmd = Command(
                    name=cmd_name,
                    start=cmd_start.start,
                    end=cmd_end.end,
                    options=options,
                    clauses=clauses,
                    args=args,
                    aggregations=aggregations,
                    subsearch=subsearch,
                )
                commands.append(current_cmd)
            elif i < len(tokens) and tokens[i].type != TokenType.EOF:
                # Invalid: something other than identifier after pipe
                result.add_error(
                    "SPL006",
                    f"Expected command name after pipe, got {tokens[i].type.name}",
                    tokens[i].start,
                    tokens[i].end
                )
                i += 1
        else:
            # Unexpected token outside command context
            i += 1
    
    if not commands:
        result.add_error(
            "SPL005",
            "Empty pipeline - no commands found",
            Position(1, 1, 0),
            Position(1, 1, 0)
        )
        return None
    
    # Build pipeline
    pipeline = Pipeline(
        commands=commands,
        start=commands[0].start,
        end=commands[-1].end
    )
    
    return pipeline


def validate_commands(pipeline: Pipeline, result: ValidationResult, *, strict: bool) -> None:
    """Validate individual commands."""
    for idx, cmd in enumerate(pipeline.commands):
        cmd_def = get_command(cmd.name)
        
        if cmd_def is None:
            if strict:
                result.add_error(
                    "SPL013",
                    f"Unknown command '{cmd.name}'",
                    cmd.start,
                    cmd.end
                )
            else:
                result.add_warning(
                    "SPL006",
                    f"Unknown command '{cmd.name}' - validation skipped",
                    cmd.start,
                    cmd.end
                )
            continue

        _validate_required_arguments(cmd, cmd_def, result)
        if cmd.name.lower() == "search":
            validate_search_terms(cmd, result, warn_plain_text=(idx == 0))


def _validate_required_arguments(cmd: Command, cmd_def, result: ValidationResult) -> None:
    """Validate that a known command has its required arguments."""
    if not getattr(cmd_def, "required_args", None):
        return

    cmd_name = cmd.name.lower()

    # These commands enforce required arguments during parsing (or have specialized handling).
    if cmd_name in ("eval", "where", "bin"):
        return

    if cmd_name == "regex":
        # Supported forms:
        # - regex <field>=<regex>
        # - regex field=<field> <regex>
        # - regex <regex>   (defaults to _raw)
        if _has_meaningful_positional_args(cmd):
            return
        if any(k != "field" for k in cmd.options.keys()):
            return
        required_str = ", ".join(cmd_def.required_args)
        result.add_error(
            "SPL014",
            f"{cmd.name} is missing required arguments ({required_str})",
            cmd.start,
            cmd.end,
        )
        return

    # Subsearch-bearing commands: require a parsed subsearch.
    if cmd_name in ("join", "append", "appendcols") and cmd.subsearch is None:
        result.add_error(
            "SPL014",
            f"{cmd.name} requires a subsearch in brackets: [...]",
            cmd.start,
            cmd.end,
            suggestion=f"Example: | {cmd.name} <fields> [ search index=... ]",
        )
        return

    # `eval` and `where` are parsed into AST expressions; require at least one parsed arg.
    if cmd_name in ("eval", "where"):
        if not cmd.args:
            result.add_error(
                "SPL014",
                f"{cmd.name} is missing required arguments",
                cmd.start,
                cmd.end,
            )
        return

    # Generic: require either positional args or a required option key.
    if _has_meaningful_positional_args(cmd):
        return

    for req in cmd_def.required_args:
        if req in cmd.options:
            return

    required_str = ", ".join(cmd_def.required_args)
    result.add_error(
        "SPL014",
        f"{cmd.name} is missing required arguments ({required_str})",
        cmd.start,
        cmd.end,
    )


def _has_meaningful_positional_args(cmd: Command) -> bool:
    """Treat punctuation-only leftovers as not satisfying required args."""
    for arg in cmd.args:
        if not hasattr(arg, "value"):
            continue
        value = arg.value
        # Parsed AST nodes (eval/where) count as meaningful, but those commands are excluded above.
        if not isinstance(value, str):
            return True

        s = value.strip()
        if not s:
            continue

        # Ignore pure punctuation (e.g., "," or "-" or "+").
        if all((not ch.isalnum()) and ch not in ("*", "_") for ch in s):
            continue

        return True

    return False


def validate_search_terms(cmd: Command, result: ValidationResult, *, warn_plain_text: bool = True) -> None:
    """Validate search command has valid search patterns.
    
    Valid patterns include:
    - index=value, sourcetype=value, host=value, source=value
    - field=value comparisons
    - Boolean terms with valid structure
    
    Arbitrary text like "stupid validator" should warn.
    """
    import re

    def _command_tokens() -> list[Token]:
        lex_source = getattr(result, "_lex_spl", result.spl)
        lexer = Lexer(lex_source)
        all_tokens = lexer.tokenize()
        out: list[Token] = []
        for t in all_tokens:
            if t.type == TokenType.EOF:
                break
            if t.start.offset >= cmd.start.offset and t.end.offset <= cmd.end.offset:
                out.append(t)
        # Drop a leading pipe if included in the span.
        while out and out[0].type == TokenType.PIPE:
            out.pop(0)
        # Drop explicit `search` keyword, if present.
        if out and out[0].type == TokenType.IDENTIFIER and out[0].value.lower() == "search":
            out = out[1:]
        return out

    def _consume_field_ref(tokens: list[Token], start: int) -> tuple[str, int] | None:
        dotted_segment_types = {TokenType.IDENTIFIER}.union(set(KEYWORDS.values()))
        if start >= len(tokens) or tokens[start].type != TokenType.IDENTIFIER:
            return None
        parts = [tokens[start].value]
        i = start
        while (
            i + 2 < len(tokens)
            and tokens[i + 1].type == TokenType.DOT
            and tokens[i + 2].type in dotted_segment_types
        ):
            parts.append(tokens[i + 2].value)
            i += 2
        return ".".join(parts), i + 1

    def _consume_in_value(tokens: list[Token], start: int) -> tuple[int, bool] | None:
        """Consume one <value> from a search-style IN (...) list.

        Supports:
        - STRING, NUMBER
        - wildcard/dotted bare values like *.kube, *Astrill*, or entitlements.production.platform
        """
        if start >= len(tokens):
            return None
        t0 = tokens[start]
        if t0.type == TokenType.STRING:
            return start + 1, False
        if t0.type == TokenType.NUMBER:
            # Accept IPv4-ish dotted numbers that the lexer tokenizes as:
            #   NUMBER("172.16") NUMBER(".0") NUMBER(".0") [SLASH NUMBER("12")]
            i = start + 1
            saw_ip_like_suffix = False
            while (
                i < len(tokens)
                and tokens[i].type == TokenType.NUMBER
                and tokens[i].value.startswith(".")
            ):
                saw_ip_like_suffix = True
                i += 1
            if (
                saw_ip_like_suffix
                and i + 1 < len(tokens)
                and tokens[i].type == TokenType.SLASH
                and tokens[i + 1].type == TokenType.NUMBER
            ):
                i += 2
            if saw_ip_like_suffix:
                return i, False
            return start + 1, False

        if t0.type not in (TokenType.IDENTIFIER, TokenType.STAR, TokenType.MINUS, TokenType.PLUS):
            return None

        i = start
        saw_dotted = False
        saw_slash_number = False
        # Consume patterns like:
        # - *.kube               => STAR DOT IDENTIFIER
        # - *Astrill*            => STAR IDENTIFIER STAR
        # - *Express*VPN*        => STAR IDENTIFIER(Express*VPN*) (lexer keeps * inside IDENTIFIER)
        # - 172.16.0.0/12        => NUMBER NUMBER NUMBER SLASH NUMBER (lexer tokenizes IP segments as NUMBER/.NUMBER)
        while i < len(tokens):
            t = tokens[i]
            if t.type in (TokenType.IDENTIFIER, TokenType.STAR, TokenType.NUMBER, TokenType.MINUS, TokenType.PLUS):
                i += 1
                continue
            if (
                t.type == TokenType.SLASH
                and not saw_slash_number
                and i > start
                and i + 1 < len(tokens)
                and tokens[i + 1].type == TokenType.NUMBER
            ):
                saw_slash_number = True
                i += 2
                continue
            if (
                t.type == TokenType.DOT
                and i + 1 < len(tokens)
                and tokens[i + 1].type in (TokenType.IDENTIFIER, TokenType.STAR)
            ):
                saw_dotted = True
                i += 2
                continue
            break
        return i, saw_dotted

    def _validate_in_operators(tokens: list[Token]) -> None:
        # IN operator is case-insensitive in SPL, but warn when not uppercase.
        saw_lowercase_in = False
        saw_lowercase_not = False

        for t in tokens:
            if t.type == TokenType.NOT and t.value.lower() == "not" and t.value != "NOT":
                saw_lowercase_not = True
            if t.type == TokenType.IDENTIFIER and t.value.lower() == "in" and t.value != "IN":
                # Only warn when it's used as IN operator (followed by "(") to avoid flagging the word "in".
                # This is checked later; here we just record potential candidates.
                pass

        i = 0
        while i < len(tokens):
            consumed = _consume_field_ref(tokens, i)
            if consumed is None:
                i += 1
                continue
            _, j = consumed

            # Detect SQL-style "<field> NOT IN (...)" which does not match Splunk's search BNF.
            if (
                j + 2 < len(tokens)
                and tokens[j].type == TokenType.NOT
                and tokens[j + 1].type == TokenType.IDENTIFIER
                and tokens[j + 1].value.lower() == "in"
                and tokens[j + 2].type == TokenType.LPAREN
            ):
                if tokens[j + 1].value != "IN":
                    saw_lowercase_in = True

                result.add_error(
                    "SPL011",
                    "Invalid search syntax: use NOT <field> IN (...) (prefix NOT), not <field> NOT IN (...)",
                    tokens[j].start,
                    tokens[j + 2].end,
                    suggestion="Example: index=main NOT action IN (addtocart, purchase)",
                )
                i = j + 3
                continue

            # Validate "<field> IN (<value>(,<value>)*)" when it looks like the IN operator.
            if (
                j + 1 < len(tokens)
                and tokens[j].type == TokenType.IDENTIFIER
                and tokens[j].value.lower() == "in"
                and tokens[j + 1].type == TokenType.LPAREN
            ):
                if tokens[j].value != "IN":
                    saw_lowercase_in = True

                k = j + 2  # after "("
                if k >= len(tokens):
                    result.add_error(
                        "SPL011",
                        "IN operator requires a value list: IN (<value>(,<value>)*)",
                        tokens[j].start,
                        tokens[j + 1].end,
                        suggestion="Example: action IN (addtocart, purchase)",
                    )
                    i = j + 2
                    continue

                expect_value = True
                seen_any_value = False
                while k < len(tokens):
                    t = tokens[k]
                    if t.type == TokenType.RPAREN:
                        break
                    if expect_value:
                        consumed = _consume_in_value(tokens, k)
                        if consumed is None:
                            result.add_error(
                                "SPL011",
                                "Invalid IN value list: expected a value",
                                t.start,
                                t.end,
                                suggestion="Example: action IN (addtocart, purchase)",
                            )
                            break
                        seen_any_value = True
                        expect_value = False
                        k = consumed[0]
                        continue
                    # Expect comma between values.
                    if t.type == TokenType.COMMA:
                        expect_value = True
                        k += 1
                        continue
                    result.add_error(
                        "SPL011",
                        "Invalid IN value list: expected ',' or ')'",
                        t.start,
                        t.end,
                        suggestion="Example: action IN (addtocart, purchase)",
                    )
                    break

                if k < len(tokens) and tokens[k].type == TokenType.RPAREN and expect_value and seen_any_value:
                    # Trailing comma before ')'.
                    result.add_error(
                        "SPL011",
                        "Trailing comma in IN value list",
                        tokens[k].start,
                        tokens[k].end,
                        suggestion="Remove the trailing comma before ')'",
                    )
                    i = k + 1
                    continue

                if k >= len(tokens) or tokens[k].type != TokenType.RPAREN:
                    # If we already emitted an error above, don't spam.
                    if not any(
                        e.code == "SPL011" and e.start == tokens[j].start for e in result.errors
                    ):
                        end_tok = tokens[min(k, len(tokens) - 1)]
                        result.add_error(
                            "SPL011",
                            "Unclosed IN value list: expected ')'",
                            tokens[j + 1].start,
                            end_tok.end,
                        )
                elif not seen_any_value:
                    result.add_error(
                        "SPL011",
                        "IN value list cannot be empty",
                        tokens[j + 1].start,
                        tokens[k].end,
                        suggestion="Example: action IN (addtocart, purchase)",
                    )

                i = k + 1
                continue

            i = j

        if saw_lowercase_in:
            # Use the command span for the warning; exact token might be ambiguous in text-heavy searches.
            result.add_warning(
                "BEST011",
                "Use uppercase keyword IN in search filters (case-insensitive but clearer)",
                cmd.start,
                cmd.end,
                suggestion="Example: action IN (addtocart, purchase)",
            )
        if saw_lowercase_not:
            result.add_warning(
                "BEST012",
                "Use uppercase keyword NOT in search filters (case-insensitive but clearer)",
                cmd.start,
                cmd.end,
                suggestion="Example: NOT action IN (addtocart, purchase)",
            )

    # Validate IN/NOT filter grammar for this search command.
    _validate_in_operators(_command_tokens())
    
    # Get the original SPL text for this command from the result
    # For now, check if options dict has any valid search patterns
    has_valid_pattern = False
    
    # Check if command has parsed options (index=, sourcetype=, etc.)
    if cmd.options:
        valid_search_keys = {'index', 'sourcetype', 'host', 'source', 'earliest', 'latest'}
        for key in cmd.options:
            if key.lower() in valid_search_keys:
                has_valid_pattern = True
                break
    
    # If no options parsed but command has clauses, that's also valid
    if cmd.clauses:
        has_valid_pattern = True
    
    # If no valid patterns detected, add warning (base search only; mid-pipeline `| search ...` is common and valid)
    if warn_plain_text and (not has_valid_pattern and not cmd.options):
        result.add_warning(
            "SPL050",
            "Search appears to be plain text without index/sourcetype specification. "
            "Consider using: index=<index_name> <search_terms>",
            cmd.start,
            cmd.end,
            suggestion="Valid search: index=main sourcetype=access_combined status=200"
        )




def validate_limits(pipeline: Pipeline, result: ValidationResult) -> None:
    """Add limitation warnings for commands with default limits."""
    for cmd in pipeline.commands:
        cmd_def = get_command(cmd.name)
        
        if cmd_def and cmd_def.limit_key:
            if cmd.name.lower() in ("head", "tail"):
                # `head`/`tail` only have a "default 10" warning when a count is not specified.
                has_count = False
                if "limit" in cmd.options or "count" in cmd.options:
                    has_count = True
                else:
                    for a in cmd.args:
                        if hasattr(a, "value") and isinstance(a.value, str):
                            try:
                                int(a.value)
                                has_count = True
                                break
                            except ValueError:
                                continue
                if has_count:
                    continue

            limit = get_limit(cmd_def.limit_key)
            if limit:
                result.add_warning(
                    f"LIM{cmd_def.limit_key.upper()[:3]}",
                    f"{cmd.name}: {limit.message}",
                    cmd.start,
                    cmd.end
                )
    
    # Note: Time bounds checking requires parsing search arguments (earliest=, latest=)
    # which will be implemented in Phase 2 parser. Removed dead code that always warned.


def validate_functions(pipeline: Pipeline, result: ValidationResult) -> None:
    """Validate function usage in pipeline (arity, context)."""
    from .src.parser.ast import FunctionCall
    
    for cmd in pipeline.commands:
        cmd_name = cmd.name.lower()
        
        # Determine context based on command
        if cmd_name in ('eval', 'where'):
            context = 'eval'
        elif cmd_name in ('stats', 'chart', 'timechart', 'eventstats', 'streamstats', 'top', 'rare'):
            context = 'stats'
        else:
            context = 'eval'  # Default
        
        # Check function calls in args
        for arg in cmd.args:
            if not hasattr(arg, "value"):
                continue
            expr = arg.value
            for func_call in _find_function_calls(expr):
                _validate_single_function(func_call, context, result)


def _find_function_calls(expr):
    """Yield FunctionCall nodes found within an expression tree."""
    from .src.parser.ast import FunctionCall, BinaryOp, UnaryOp, Assignment

    if isinstance(expr, FunctionCall):
        yield expr
        return

    if isinstance(expr, Assignment):
        yield from _find_function_calls(expr.value)
        return

    if isinstance(expr, BinaryOp):
        yield from _find_function_calls(expr.left)
        yield from _find_function_calls(expr.right)
        return

    if isinstance(expr, UnaryOp):
        yield from _find_function_calls(expr.operand)
        return


def _validate_single_function(func_call, context: str, result: ValidationResult) -> None:
    """Validate a single function call."""
    from .src.registry.functions import validate_function_arity, validate_function_context
    from .src.parser.ast import FunctionCall
    
    # Check arity
    arity_error = validate_function_arity(func_call.name, len(func_call.args), context=context)
    if arity_error:
        result.add_error(
            "SPL020",
            arity_error,
            func_call.start,
            func_call.end
        )
    
    # Check context
    context_error = validate_function_context(func_call.name, context)
    if context_error:
        result.add_error(
            "SPL021",
            context_error,
            func_call.start,
            func_call.end
        )
    
    # Recursively check nested function calls
    for arg in func_call.args:
        if isinstance(arg, FunctionCall):
            _validate_single_function(arg, context, result)


def validate_semantics(pipeline: Pipeline, result: ValidationResult) -> None:
    """Add semantic warnings about command behaviors that may surprise users.
    
    KB Sources:
    - aggregation-and-statistics.md: BY clause excludes nulls
    - filtering-and-selection.md: where/dedup filter events
    - data-enrichment.md: join excludes non-matching, transaction orphans
    """
    from .src.analyzer.limits import get_semantic_warning
    
    for cmd in pipeline.commands:
        cmd_def = get_command(cmd.name)
        if not cmd_def:
            continue
        
        cmd_name = cmd.name.lower()
        
        # 1. Check command-level semantic warning (from semantic_key)
        if cmd_def.semantic_key:
            # Skip BY warning if command has BY clause (dynamic warning below is more specific)
            skip_warning = False
            if cmd_def.semantic_key == "by_clause_excludes":
                by_clause = cmd.clauses.get("BY")
                if by_clause and hasattr(by_clause, 'fields') and by_clause.fields:
                    skip_warning = True  # Dynamic warning below will cover this
            
            if not skip_warning:
                warning = get_semantic_warning(cmd_def.semantic_key)
                if warning:
                    result.add_warning(
                        f"SEM-{cmd_name[:3].upper()}",
                        f"{cmd.name}: {warning.message}",
                        cmd.start,
                        cmd.end,
                        suggestion=warning.suggestion
                    )
        
        # 2. Check for BY clause on aggregation commands (dynamic warning with field names)
        if cmd_name in ("stats", "chart", "timechart", "eventstats", "streamstats"):
            by_clause = cmd.clauses.get("BY")
            if by_clause and hasattr(by_clause, 'fields') and by_clause.fields:
                fields_str = ", ".join(by_clause.fields)
                result.add_warning(
                    "SEM-BY",
                    f"{cmd.name} BY {fields_str}: Events where '{fields_str}' is null/missing are EXCLUDED.",
                    cmd.start,
                    cmd.end,
                    suggestion=f"Use 'fillnull {fields_str}' before {cmd.name} to include missing values."
                )
        
        # 3. filters_events flag warning (for commands that remove events)
        if cmd_def.filters_events and not cmd_def.semantic_key:
            # Only add generic filter warning if no specific semantic_key warning
            result.add_warning(
                "SEM-FLT",
                f"{cmd.name}: This command FILTERS (removes) events from results.",
                cmd.start,
                cmd.end
            )
