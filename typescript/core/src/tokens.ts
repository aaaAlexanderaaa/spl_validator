export const TokenType = {
  PIPE: "PIPE",
  COMMA: "COMMA",
  LPAREN: "LPAREN",
  RPAREN: "RPAREN",
  LBRACKET: "LBRACKET",
  RBRACKET: "RBRACKET",
  IDENTIFIER: "IDENTIFIER",
  STRING: "STRING",
  NUMBER: "NUMBER",
  MACRO: "MACRO",
  AND: "AND",
  OR: "OR",
  NOT: "NOT",
  XOR: "XOR",
  BY: "BY",
  AS: "AS",
  OVER: "OVER",
  OUTPUT: "OUTPUT",
  OUTPUTNEW: "OUTPUTNEW",
  WHERE: "WHERE",
  TRUE: "TRUE",
  FALSE: "FALSE",
  NULL: "NULL",
  EQ: "EQ",
  EQEQ: "EQEQ",
  NEQ: "NEQ",
  LT: "LT",
  GT: "GT",
  LTE: "LTE",
  GTE: "GTE",
  LIKE: "LIKE",
  PLUS: "PLUS",
  MINUS: "MINUS",
  STAR: "STAR",
  SLASH: "SLASH",
  PERCENT: "PERCENT",
  DOT: "DOT",
  ASSIGN: "ASSIGN",
  WILDCARD: "WILDCARD",
  EOF: "EOF",
  ERROR: "ERROR",
} as const;

export type TokenType = (typeof TokenType)[keyof typeof TokenType];

export const KEYWORDS: Record<string, TokenType> = {
  and: TokenType.AND,
  or: TokenType.OR,
  not: TokenType.NOT,
  xor: TokenType.XOR,
  by: TokenType.BY,
  as: TokenType.AS,
  over: TokenType.OVER,
  output: TokenType.OUTPUT,
  outputnew: TokenType.OUTPUTNEW,
  where: TokenType.WHERE,
  like: TokenType.LIKE,
  true: TokenType.TRUE,
  false: TokenType.FALSE,
  null: TokenType.NULL,
};

export interface Position {
  line: number;
  column: number;
  offset: number;
}

export interface Token {
  type: TokenType;
  value: string;
  start: Position;
  end: Position;
}

export function pos(line: number, column: number, offset: number): Position {
  return { line, column, offset };
}
