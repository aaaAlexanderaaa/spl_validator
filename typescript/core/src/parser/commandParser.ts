import type { Aggregation, Clause } from "../ast.js";
import { KEYWORDS, type Token, TokenType, type Position } from "../tokens.js";
import { isKnownFunction, validateFunctionArity, validateFunctionContext } from "../registry.js";
import { ParseError } from "./parseError.js";

const DOTTED_NAME_SEGMENT_TYPES = new Set<TokenType>([TokenType.IDENTIFIER, ...Object.values(KEYWORDS)]);

function isDottedNameSegment(token: Token): boolean {
  return DOTTED_NAME_SEGMENT_TYPES.has(token.type);
}

export class CommandParser {
  private tokens: Token[];
  private pos = 0;

  constructor(tokens: Token[]) {
    this.tokens = tokens;
  }

  current(): Token {
    if (this.pos < this.tokens.length) return this.tokens[this.pos]!;
    if (this.tokens.length === 0) {
      const zero: Position = { line: 1, column: 1, offset: 0 };
      return { type: TokenType.EOF, value: "", start: zero, end: zero };
    }
    const last = this.tokens[this.tokens.length - 1]!;
    return { type: TokenType.EOF, value: "", start: last.end, end: last.end };
  }

  peek(offset = 0): Token {
    const p = this.pos + offset;
    if (p < this.tokens.length) return this.tokens[p]!;
    return this.current();
  }

  advance(): Token {
    const t = this.current();
    this.pos += 1;
    return t;
  }

  match(...types: TokenType[]): boolean {
    return types.includes(this.current().type);
  }

  atCommandBoundary(): boolean {
    return this.match(TokenType.PIPE, TokenType.EOF);
  }

  getRemainingTokens(): Token[] {
    const remaining: Token[] = [];
    while (!this.atCommandBoundary()) {
      remaining.push(this.current());
      this.advance();
    }
    return remaining;
  }

  private consumeDottedIdentifier(): string | null {
    if (!this.match(TokenType.IDENTIFIER)) return null;
    const parts = [this.advance().value];
    while (this.match(TokenType.DOT) && isDottedNameSegment(this.peek(1))) {
      this.advance();
      parts.push(this.advance().value);
    }
    return parts.join(".");
  }

  parseOptions(): Record<string, unknown> {
    const options: Record<string, unknown> = {};
    while (!this.atCommandBoundary()) {
      if (
        this.match(
          TokenType.BY,
          TokenType.AS,
          TokenType.OVER,
          TokenType.OUTPUT,
          TokenType.OUTPUTNEW,
          TokenType.WHERE,
        )
      ) {
        break;
      }
      if (this.match(TokenType.IDENTIFIER)) {
        let offset = 1;
        while (
          this.peek(offset).type === TokenType.DOT &&
          isDottedNameSegment(this.peek(offset + 1))
        ) {
          offset += 2;
        }
        if (this.peek(offset).type !== TokenType.EQ) break;
        const key = this.consumeDottedIdentifier();
        if (key === null) break;
        this.advance();
        if (this.match(TokenType.STRING)) {
          options[key] = this.advance().value;
        } else if (this.match(TokenType.NUMBER)) {
          const val = this.advance().value;
          try {
            options[key] = !val.includes(".") ? parseInt(val, 10) : parseFloat(val);
          } catch {
            options[key] = val;
          }
        } else if (this.match(TokenType.MINUS, TokenType.PLUS)) {
          const sign = this.advance().value;
          if (this.match(TokenType.NUMBER, TokenType.IDENTIFIER)) {
            options[key] = sign + this.advance().value;
          } else {
            options[key] = sign;
          }
        } else if (this.match(TokenType.TRUE)) {
          this.advance();
          options[key] = true;
        } else if (this.match(TokenType.FALSE)) {
          this.advance();
          options[key] = false;
        } else if (this.match(TokenType.IDENTIFIER)) {
          options[key] = this.advance().value;
        } else {
          this.advance();
        }
      } else {
        break;
      }
    }
    return options;
  }

  parseFieldList(): string[] {
    const fields: string[] = [];
    while (!this.atCommandBoundary()) {
      if (this.match(TokenType.IDENTIFIER)) {
        const name = this.consumeDottedIdentifier();
        if (name === null) break;
        fields.push(name);
      } else if (this.match(TokenType.STAR)) {
        fields.push(this.advance().value);
      } else {
        break;
      }
      if (this.match(TokenType.COMMA)) {
        this.advance();
      } else {
        break;
      }
    }
    return fields;
  }

  parseByClause(): Clause | null {
    if (!this.match(TokenType.BY)) return null;
    const byToken = this.advance();
    const fields = this.parseFieldList();
    return {
      keyword: "BY",
      fields,
      start: byToken.start,
      end: byToken.end,
    };
  }

  parseStatsArgs(): [Aggregation[], Token[], [string, string, Position, Position][]] {
    const aggregations: Aggregation[] = [];
    const unexpected: Token[] = [];
    const functionErrors: [string, string, Position, Position][] = [];

    const firstDottedIdentifier = (inner: Token[]): string | null => {
      let i = 0;
      while (i < inner.length) {
        const t = inner[i]!;
        if (t.type !== TokenType.IDENTIFIER) {
          i += 1;
          continue;
        }
        if (i + 1 < inner.length && inner[i + 1]!.type === TokenType.LPAREN) {
          i += 1;
          continue;
        }
        const parts = [t.value];
        let j = i;
        while (
          j + 2 < inner.length &&
          inner[j + 1]!.type === TokenType.DOT &&
          isDottedNameSegment(inner[j + 2]!)
        ) {
          parts.push(inner[j + 2]!.value);
          j += 2;
        }
        return parts.join(".");
      }
      return null;
    };

    while (!this.atCommandBoundary()) {
      if (this.match(TokenType.BY)) break;
      if (this.match(TokenType.IDENTIFIER)) {
        const funcToken = this.advance();
        let aggField: string | null = null;
        let alias: string | null = null;
        let argCount = 0;
        let endPos = funcToken.end;
        if (this.match(TokenType.LPAREN)) {
          const lparen = this.advance();
          let parenDepth = 1;
          const innerTokens: Token[] = [];
          let currentArgHasTokens = false;
          while (!this.atCommandBoundary() && parenDepth > 0) {
            const tok = this.current();
            if (tok.type === TokenType.LPAREN) {
              parenDepth += 1;
              if (parenDepth >= 2) innerTokens.push(tok);
              this.advance();
              continue;
            }
            if (tok.type === TokenType.RPAREN) {
              parenDepth -= 1;
              endPos = tok.end;
              this.advance();
              if (parenDepth === 0) {
                if (currentArgHasTokens) argCount += 1;
                break;
              }
              if (parenDepth >= 1) innerTokens.push(tok);
              continue;
            }
            if (tok.type === TokenType.COMMA && parenDepth === 1) {
              if (currentArgHasTokens) argCount += 1;
              currentArgHasTokens = false;
              this.advance();
              continue;
            }
            if (parenDepth === 1) {
              currentArgHasTokens = true;
              innerTokens.push(tok);
            } else if (parenDepth >= 2) {
              innerTokens.push(tok);
            }
            this.advance();
          }
          if (parenDepth > 0) {
            functionErrors.push([
              "SPL009",
              `Unclosed parentheses in ${funcToken.value} aggregation`,
              lparen.start,
              endPos,
            ]);
          } else {
            aggField = firstDottedIdentifier(innerTokens);
          }
        } else {
          argCount = 0;
        }

        if (!isKnownFunction(funcToken.value)) {
          functionErrors.push([
            "SPL023",
            `Unknown function '${funcToken.value}'`,
            funcToken.start,
            endPos,
          ]);
        } else {
          const ctxErr = validateFunctionContext(funcToken.value, "stats");
          if (ctxErr) functionErrors.push(["SPL021", ctxErr, funcToken.start, endPos]);
          const arityErr = validateFunctionArity(funcToken.value, argCount, "stats");
          if (arityErr) functionErrors.push(["SPL020", arityErr, funcToken.start, endPos]);
        }

        if (this.match(TokenType.AS)) {
          this.advance();
          let aliasName = this.consumeDottedIdentifier();
          if (aliasName === null && this.match(TokenType.STRING)) {
            aliasName = this.advance().value;
          }
          if (aliasName) {
            alias = aliasName;
            if (this.match(TokenType.LPAREN)) {
              this.advance();
              let depth = 1;
              const inner: string[] = [];
              while (!this.atCommandBoundary() && depth > 0) {
                const tok = this.current();
                if (tok.type === TokenType.LPAREN) {
                  depth += 1;
                  inner.push(tok.value);
                  this.advance();
                  continue;
                }
                if (tok.type === TokenType.RPAREN) {
                  depth -= 1;
                  this.advance();
                  if (depth === 0) break;
                  inner.push(tok.value);
                  continue;
                }
                inner.push(tok.value);
                this.advance();
              }
              if (depth === 0) {
                alias = alias + "(" + inner.join("") + ")";
              }
            }
          }
        }

        aggregations.push({
          function: funcToken.value,
          agg_field: aggField,
          args: [],
          alias,
          start: funcToken.start,
          end: endPos,
        });

        if (this.match(TokenType.COMMA)) {
          this.advance();
          continue;
        }
        if (this.match(TokenType.BY) || this.atCommandBoundary()) continue;
        if (this.match(TokenType.IDENTIFIER)) continue;
        if (!this.atCommandBoundary()) this.advance();
      } else {
        if (!this.atCommandBoundary() && !this.match(TokenType.BY)) {
          unexpected.push(this.advance());
        } else break;
      }
    }

    return [aggregations, unexpected, functionErrors];
  }
}
