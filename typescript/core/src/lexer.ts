import { KEYWORDS, type Position, type Token, TokenType } from "./tokens.js";

const TIME_SUFFIXES = new Set([
  "s",
  "sec",
  "m",
  "min",
  "h",
  "hr",
  "d",
  "day",
  "w",
  "week",
  "mon",
  "y",
  "year",
]);

export class Lexer {
  private source: string;
  private pos = 0;
  private line = 1;
  private column = 1;
  private lineStart = 0;

  constructor(source: string) {
    this.source = source;
  }

  tokenize(): Token[] {
    const out: Token[] = [];
    for (const t of this.tokenizeIter()) {
      out.push(t);
    }
    return out;
  }

  private *tokenizeIter(): Generator<Token> {
    while (this.pos < this.source.length) {
      if (this.current().match(/\s/)) {
        this.skipWhitespace();
        continue;
      }
      if (this.current() === "`") {
        yield this.scanMacro();
        continue;
      }
      const startPos = this.makePosition();
      const char = this.current();

      if (char === "|") {
        this.advance();
        yield this.makeToken(TokenType.PIPE, "|", startPos);
      } else if (char === ",") {
        this.advance();
        yield this.makeToken(TokenType.COMMA, ",", startPos);
      } else if (char === "(") {
        this.advance();
        yield this.makeToken(TokenType.LPAREN, "(", startPos);
      } else if (char === ")") {
        this.advance();
        yield this.makeToken(TokenType.RPAREN, ")", startPos);
      } else if (char === "[") {
        this.advance();
        yield this.makeToken(TokenType.LBRACKET, "[", startPos);
      } else if (char === "]") {
        this.advance();
        yield this.makeToken(TokenType.RBRACKET, "]", startPos);
      } else if (char === "+") {
        this.advance();
        yield this.makeToken(TokenType.PLUS, "+", startPos);
      } else if (char === "-") {
        this.advance();
        yield this.makeToken(TokenType.MINUS, "-", startPos);
      } else if (char === "*") {
        this.advance();
        yield this.makeToken(TokenType.STAR, "*", startPos);
      } else if (char === "/") {
        this.advance();
        yield this.makeToken(TokenType.SLASH, "/", startPos);
      } else if (char === "%") {
        this.advance();
        yield this.makeToken(TokenType.PERCENT, "%", startPos);
      } else if (char === ".") {
        if (/\d/.test(this.peek(1))) {
          yield this.scanNumberStartingWithDot();
        } else {
          this.advance();
          yield this.makeToken(TokenType.DOT, ".", startPos);
        }
      } else if (char === "=") {
        this.advance();
        if (this.current() === "=") {
          this.advance();
          yield this.makeToken(TokenType.EQEQ, "==", startPos);
        } else {
          yield this.makeToken(TokenType.EQ, "=", startPos);
        }
      } else if (char === "!") {
        this.advance();
        if (this.current() === "=") {
          this.advance();
          yield this.makeToken(TokenType.NEQ, "!=", startPos);
        } else {
          yield this.makeToken(TokenType.NOT, "!", startPos);
        }
      } else if (char === "<") {
        this.advance();
        if (this.current() === "=") {
          this.advance();
          yield this.makeToken(TokenType.LTE, "<=", startPos);
        } else if (this.current() === ">") {
          this.advance();
          yield this.makeToken(TokenType.NEQ, "<>", startPos);
        } else {
          yield this.makeToken(TokenType.LT, "<", startPos);
        }
      } else if (char === ">") {
        this.advance();
        if (this.current() === "=") {
          this.advance();
          yield this.makeToken(TokenType.GTE, ">=", startPos);
        } else {
          yield this.makeToken(TokenType.GT, ">", startPos);
        }
      } else if (char === '"' || char === "'") {
        yield this.scanString(char);
      } else if (/\d/.test(char)) {
        yield this.scanNumber();
      } else if (/[a-zA-Z_]/.test(char) || "_@$\\{:".includes(char)) {
        yield this.scanIdentifier();
      } else {
        this.advance();
        yield this.makeToken(TokenType.ERROR, char, startPos);
      }
    }
    yield this.makeToken(TokenType.EOF, "", this.makePosition());
  }

  private scanMacro(): Token {
    const startPos = this.makePosition();
    this.advance();
    const value: string[] = [];
    while (this.pos < this.source.length && this.current() !== "`") {
      if (this.current() === "\n") break;
      value.push(this.current());
      this.advance();
    }
    if (this.pos < this.source.length && this.current() === "`") {
      this.advance();
      return this.makeToken(TokenType.MACRO, value.join("").trim(), startPos);
    }
    return this.makeToken(TokenType.ERROR, "`" + value.join(""), startPos);
  }

  private scanString(quote: string): Token {
    const startPos = this.makePosition();
    this.advance();
    const value: string[] = [];
    while (this.pos < this.source.length && this.current() !== quote) {
      if (this.current() === "\\") {
        this.advance();
        if (this.pos < this.source.length) {
          const escaped = this.current();
          if (escaped === "n") value.push("\n");
          else if (escaped === "t") value.push("\t");
          else if (escaped === "r") value.push("\r");
          else if (escaped === "\\") value.push("\\");
          else if (escaped === quote) value.push(quote);
          else {
            value.push("\\");
            value.push(escaped);
          }
          this.advance();
        }
      } else if (this.current() === "\n") {
        break;
      } else {
        value.push(this.current());
        this.advance();
      }
    }
    if (this.pos < this.source.length && this.current() === quote) {
      this.advance();
      return this.makeToken(TokenType.STRING, value.join(""), startPos);
    }
    return this.makeToken(TokenType.ERROR, quote + value.join(""), startPos);
  }

  private scanNumber(): Token {
    const startPos = this.makePosition();
    const value: string[] = [];
    while (this.pos < this.source.length && /\d/.test(this.current())) {
      value.push(this.current());
      this.advance();
    }
    if (this.pos < this.source.length && this.current() === ".") {
      if (/\d/.test(this.peek(1))) {
        value.push(".");
        this.advance();
        while (this.pos < this.source.length && /\d/.test(this.current())) {
          value.push(this.current());
          this.advance();
        }
      }
    }
    if (this.pos < this.source.length && this.current().toLowerCase() === "e") {
      const nextChar = this.peek(1);
      if (/\d/.test(nextChar) || "+-".includes(nextChar)) {
        value.push(this.current());
        this.advance();
        if (this.pos < this.source.length && "+-".includes(this.current())) {
          value.push(this.current());
          this.advance();
        }
        while (this.pos < this.source.length && /\d/.test(this.current())) {
          value.push(this.current());
          this.advance();
        }
      }
    }
    if (this.pos < this.source.length && /[a-zA-Z]/.test(this.current())) {
      const suffixStart = this.pos;
      const suffix: string[] = [];
      while (this.pos < this.source.length && /[a-zA-Z]/.test(this.current())) {
        suffix.push(this.current());
        this.advance();
      }
      const suffixStr = suffix.join("").toLowerCase();
      if (TIME_SUFFIXES.has(suffixStr)) {
        value.push(...suffix);
      } else {
        this.pos = suffixStart;
        this.column = this.pos - this.lineStart + 1;
      }
    }
    if (this.pos < this.source.length && this.current() === "@") {
      const snapStart = this.pos;
      this.advance();
      const snap: string[] = [];
      while (this.pos < this.source.length && /[a-zA-Z0-9]/.test(this.current())) {
        snap.push(this.current());
        this.advance();
      }
      if (snap.length) {
        value.push("@");
        value.push(...snap);
      } else {
        this.pos = snapStart;
        this.column = this.pos - this.lineStart + 1;
      }
    }
    return this.makeToken(TokenType.NUMBER, value.join(""), startPos);
  }

  private scanNumberStartingWithDot(): Token {
    const startPos = this.makePosition();
    const value: string[] = [];
    if (this.current() === ".") {
      value.push(".");
      this.advance();
    }
    while (this.pos < this.source.length && /\d/.test(this.current())) {
      value.push(this.current());
      this.advance();
    }
    if (this.pos < this.source.length && this.current().toLowerCase() === "e") {
      const nextChar = this.peek(1);
      if (/\d/.test(nextChar) || "+-".includes(nextChar)) {
        value.push(this.current());
        this.advance();
        if (this.pos < this.source.length && "+-".includes(this.current())) {
          value.push(this.current());
          this.advance();
        }
        while (this.pos < this.source.length && /\d/.test(this.current())) {
          value.push(this.current());
          this.advance();
        }
      }
    }
    return this.makeToken(TokenType.NUMBER, value.join(""), startPos);
  }

  private scanIdentifier(): Token {
    const startPos = this.makePosition();
    const value: string[] = [];
    while (this.pos < this.source.length && this.isIdentifierChar(this.current())) {
      value.push(this.current());
      this.advance();
    }
    const text = value.join("");
    const tokenType = KEYWORDS[text.toLowerCase()] ?? TokenType.IDENTIFIER;
    return this.makeToken(tokenType, text, startPos);
  }

  private isIdentifierChar(char: string): boolean {
    return /[a-zA-Z0-9]/.test(char) || "_:*@{}$\\'\"".includes(char);
  }

  private skipWhitespace(): void {
    while (this.pos < this.source.length && this.current().match(/\s/)) {
      if (this.current() === "\n") {
        this.line += 1;
        this.advance();
        this.lineStart = this.pos;
      } else {
        this.advance();
      }
    }
  }

  private current(): string {
    return this.pos < this.source.length ? this.source[this.pos]! : "";
  }

  private peek(offset: number): string {
    const p = this.pos + offset;
    return p < this.source.length ? this.source[p]! : "";
  }

  private advance(): void {
    this.pos += 1;
    this.column = this.pos - this.lineStart + 1;
  }

  private makePosition(): Position {
    return {
      line: this.line,
      column: this.pos - this.lineStart + 1,
      offset: this.pos,
    };
  }

  private makeToken(type: TokenType, value: string, start: Position): Token {
    return {
      type,
      value,
      start,
      end: this.makePosition(),
    };
  }
}
