import { KEYWORDS, type Token, TokenType } from "../tokens.js";
import type {
  Assignment,
  BinaryOp,
  Expression,
  FieldRef,
  FunctionCall,
  Literal,
  UnaryOp,
} from "./expressionTypes.js";
import { ParseError } from "./parseError.js";
import type { Aggregation } from "../ast.js";

const DOTTED_NAME_SEGMENT_TYPES = new Set<TokenType>([TokenType.IDENTIFIER, ...Object.values(KEYWORDS)]);

function isDottedNameSegment(token: Token): boolean {
  return DOTTED_NAME_SEGMENT_TYPES.has(token.type);
}

export class ExpressionParser {
  private tokens: Token[];
  private pos = 0;

  constructor(tokens: Token[]) {
    this.tokens = tokens;
  }

  current(): Token {
    if (this.pos < this.tokens.length) return this.tokens[this.pos]!;
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

  consume(type: TokenType, errorMsg: string): Token {
    if (this.current().type === type) return this.advance();
    throw new ParseError(errorMsg, this.current().start);
  }

  atEnd(): boolean {
    return this.current().type === TokenType.EOF;
  }

  parseExpression(): Expression {
    return this.parseOr();
  }

  private parseOr(): Expression {
    let left = this.parseAnd();
    while (this.match(TokenType.OR)) {
      this.advance();
      const right = this.parseAnd();
      left = {
        kind: "BinaryOp",
        left,
        operator: "OR",
        right,
        start: left.start,
        end: right.end,
      };
    }
    return left;
  }

  private parseAnd(): Expression {
    let left = this.parseNot();
    while (this.match(TokenType.AND, TokenType.XOR)) {
      const opTok = this.advance();
      const right = this.parseNot();
      left = {
        kind: "BinaryOp",
        left,
        operator: opTok.value.toUpperCase(),
        right,
        start: left.start,
        end: right.end,
      };
    }
    return left;
  }

  private parseNot(): Expression {
    if (this.match(TokenType.NOT)) {
      const opTok = this.advance();
      const operand = this.parseNot();
      return {
        kind: "UnaryOp",
        operator: "NOT",
        operand,
        start: opTok.start,
        end: operand.end,
      };
    }
    return this.parseComparison();
  }

  private parseComparison(): Expression {
    let left = this.parseAdditive();
    while (true) {
      if (
        this.match(
          TokenType.EQ,
          TokenType.EQEQ,
          TokenType.NEQ,
          TokenType.LT,
          TokenType.GT,
          TokenType.LTE,
          TokenType.GTE,
          TokenType.LIKE,
        )
      ) {
        const opTok = this.advance();
        const right = this.parseAdditive();
        const op =
          opTok.type === TokenType.LIKE ? opTok.value.toUpperCase() : opTok.value;
        left = {
          kind: "BinaryOp",
          left,
          operator: op,
          right,
          start: left.start,
          end: right.end,
        };
        continue;
      }
      if (
        this.match(TokenType.IDENTIFIER) &&
        this.current().value.toLowerCase() === "in" &&
        this.peek(1).type === TokenType.LPAREN
      ) {
        this.advance();
        this.advance();
        const args: Expression[] = [left];
        if (!this.match(TokenType.RPAREN)) {
          args.push(this.parseInListItem());
          while (this.match(TokenType.COMMA)) {
            this.advance();
            args.push(this.parseInListItem());
          }
        }
        const endTok = this.consume(TokenType.RPAREN, "Expected ')' after IN (...) list");
        left = {
          kind: "FunctionCall",
          name: "in",
          args,
          start: left.start,
          end: endTok.end,
        };
        continue;
      }
      break;
    }
    return left;
  }

  private parseInListItem(): Expression {
    const tok = this.current();
    if (tok.type === TokenType.STRING) {
      this.advance();
      return {
        kind: "Literal",
        value: tok.value,
        type: "string",
        start: tok.start,
        end: tok.end,
      };
    }
    if (tok.type === TokenType.NUMBER) {
      this.advance();
      return {
        kind: "Literal",
        value: this.parseNumber(tok.value),
        type: "number",
        start: tok.start,
        end: tok.end,
      };
    }
    if (tok.type === TokenType.TRUE) {
      this.advance();
      return {
        kind: "Literal",
        value: true,
        type: "boolean",
        start: tok.start,
        end: tok.end,
      };
    }
    if (tok.type === TokenType.FALSE) {
      this.advance();
      return {
        kind: "Literal",
        value: false,
        type: "boolean",
        start: tok.start,
        end: tok.end,
      };
    }
    if (tok.type === TokenType.NULL) {
      this.advance();
      return {
        kind: "Literal",
        value: null,
        type: "null",
        start: tok.start,
        end: tok.end,
      };
    }
    if (tok.type === TokenType.IDENTIFIER || tok.type === TokenType.STAR) {
      const start = tok.start;
      const parts = [this.advance().value];
      let end = tok.end;
      while (this.match(TokenType.DOT) && isDottedNameSegment(this.peek(1))) {
        this.advance();
        const partTok = this.advance();
        parts.push(partTok.value);
        end = partTok.end;
      }
      return {
        kind: "Literal",
        value: parts.join("."),
        type: "string",
        start,
        end,
      };
    }
    throw new ParseError("Expected value in IN (...) list", tok.start);
  }

  private parseAdditive(): Expression {
    let left = this.parseMultiplicative();
    while (this.match(TokenType.PLUS, TokenType.MINUS, TokenType.DOT)) {
      const opTok = this.advance();
      const right = this.parseMultiplicative();
      left = {
        kind: "BinaryOp",
        left,
        operator: opTok.value,
        right,
        start: left.start,
        end: right.end,
      };
    }
    return left;
  }

  private parseMultiplicative(): Expression {
    let left = this.parseUnary();
    while (this.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)) {
      const opTok = this.advance();
      const right = this.parseUnary();
      left = {
        kind: "BinaryOp",
        left,
        operator: opTok.value,
        right,
        start: left.start,
        end: right.end,
      };
    }
    return left;
  }

  private parseUnary(): Expression {
    if (this.match(TokenType.MINUS)) {
      const opTok = this.advance();
      const operand = this.parseUnary();
      return {
        kind: "UnaryOp",
        operator: "-",
        operand,
        start: opTok.start,
        end: operand.end,
      };
    }
    return this.parsePrimary();
  }

  private parsePrimary(): Expression {
    const token = this.current();
    if (this.match(TokenType.LPAREN)) {
      this.advance();
      const expr = this.parseExpression();
      this.consume(TokenType.RPAREN, "Expected ')' after expression");
      return expr;
    }
    if (this.match(TokenType.NUMBER)) {
      this.advance();
      return {
        kind: "Literal",
        value: this.parseNumber(token.value),
        type: "number",
        start: token.start,
        end: token.end,
      };
    }
    if (this.match(TokenType.STRING)) {
      this.advance();
      return {
        kind: "Literal",
        value: token.value,
        type: "string",
        start: token.start,
        end: token.end,
      };
    }
    if (this.match(TokenType.TRUE)) {
      if (this.peek(1).type === TokenType.LPAREN) {
        const nameToken = this.advance();
        return this.parseFunctionCall(nameToken);
      }
      this.advance();
      return {
        kind: "Literal",
        value: true,
        type: "boolean",
        start: token.start,
        end: token.end,
      };
    }
    if (this.match(TokenType.FALSE)) {
      if (this.peek(1).type === TokenType.LPAREN) {
        const nameToken = this.advance();
        return this.parseFunctionCall(nameToken);
      }
      this.advance();
      return {
        kind: "Literal",
        value: false,
        type: "boolean",
        start: token.start,
        end: token.end,
      };
    }
    if (this.match(TokenType.NULL)) {
      if (this.peek(1).type === TokenType.LPAREN) {
        const nameToken = this.advance();
        return this.parseFunctionCall(nameToken);
      }
      this.advance();
      return {
        kind: "Literal",
        value: null,
        type: "null",
        start: token.start,
        end: token.end,
      };
    }
    if (this.match(TokenType.IDENTIFIER, TokenType.LIKE)) {
      const nameToken = this.advance();
      if (this.match(TokenType.LPAREN)) {
        return this.parseFunctionCall(nameToken);
      }
      const parts = [nameToken.value];
      let endPos = nameToken.end;
      while (this.match(TokenType.DOT) && isDottedNameSegment(this.peek(1))) {
        this.advance();
        const partTok = this.advance();
        parts.push(partTok.value);
        endPos = partTok.end;
      }
      return {
        kind: "FieldRef",
        name: parts.join("."),
        start: nameToken.start,
        end: endPos,
      };
    }
    if (this.match(TokenType.STAR)) {
      this.advance();
      return { kind: "FieldRef", name: "*", start: token.start, end: token.end };
    }
    if (this.match(TokenType.MACRO)) {
      this.advance();
      return {
        kind: "Literal",
        value: token.value,
        type: "macro",
        start: token.start,
        end: token.end,
      };
    }
    throw new ParseError(`Unexpected token: ${token.type}`, token.start);
  }

  parseFunctionCall(nameToken: Token): FunctionCall {
    this.consume(TokenType.LPAREN, "Expected '(' after function name");
    const args: Expression[] = [];
    if (!this.match(TokenType.RPAREN)) {
      args.push(this.parseExpression());
      while (this.match(TokenType.COMMA)) {
        this.advance();
        args.push(this.parseExpression());
      }
    }
    const endToken = this.consume(TokenType.RPAREN, "Expected ')' after arguments");
    return {
      kind: "FunctionCall",
      name: nameToken.value,
      args,
      start: nameToken.start,
      end: endToken.end,
    };
  }

  private parseNumber(value: string): number {
    if (value.includes(".") || value.toLowerCase().includes("e")) return parseFloat(value);
    return parseInt(value, 10);
  }

  parseAssignment(): Assignment | null {
    if (this.match(TokenType.STRING)) {
      if (this.peek(1).type !== TokenType.EQ) return null;
      const nameToken = this.advance();
      this.advance();
      const value = this.parseExpression();
      return {
        kind: "Assignment",
        field_name: nameToken.value,
        value,
        start: nameToken.start,
        end: value.end,
      };
    }
    let nameToken: Token;
    let parts: string[];
    if (this.match(TokenType.MINUS, TokenType.PLUS)) {
      const signTok = this.advance();
      if (!this.match(TokenType.IDENTIFIER)) return null;
      let offset = 1;
      while (
        this.peek(offset).type === TokenType.DOT &&
        isDottedNameSegment(this.peek(offset + 1))
      ) {
        offset += 2;
      }
      if (this.peek(offset).type !== TokenType.EQ) return null;
      nameToken = this.advance();
      parts = [signTok.value + nameToken.value];
    } else {
      if (!this.match(TokenType.IDENTIFIER)) return null;
      let offset = 1;
      while (
        this.peek(offset).type === TokenType.DOT &&
        isDottedNameSegment(this.peek(offset + 1))
      ) {
        offset += 2;
      }
      if (this.peek(offset).type !== TokenType.EQ) return null;
      nameToken = this.advance();
      parts = [nameToken.value];
    }
    while (this.match(TokenType.DOT) && isDottedNameSegment(this.peek(1))) {
      this.advance();
      parts.push(this.advance().value);
    }
    this.advance();
    const value = this.parseExpression();
    return {
      kind: "Assignment",
      field_name: parts.join("."),
      value,
      start: nameToken.start,
      end: value.end,
    };
  }

  parseAggregation(): Aggregation | null {
    if (!this.match(TokenType.IDENTIFIER)) return null;
    const funcToken = this.advance();
    const funcName = funcToken.value.toLowerCase();
    let aggField: string | null = null;
    const args: Expression[] = [];
    let endPos = funcToken.end;
    if (this.match(TokenType.LPAREN)) {
      this.advance();
      if (!this.match(TokenType.RPAREN)) {
        if (this.match(TokenType.IDENTIFIER)) {
          const fieldToken = this.advance();
          aggField = fieldToken.value;
          endPos = fieldToken.end;
        } else if (this.match(TokenType.STAR)) {
          this.advance();
          aggField = "*";
        } else {
          const expr = this.parseExpression();
          args.push(expr);
          endPos = expr.end;
        }
      }
      const rparen = this.consume(TokenType.RPAREN, "Expected ')' after aggregation");
      endPos = rparen.end;
    }
    let alias: string | null = null;
    if (this.match(TokenType.AS)) {
      this.advance();
      if (this.match(TokenType.IDENTIFIER)) {
        const aliasToken = this.advance();
        alias = aliasToken.value;
        endPos = aliasToken.end;
      }
    }
    return {
      function: funcName,
      agg_field: aggField,
      args,
      alias,
      start: funcToken.start,
      end: endPos,
    };
  }
}
