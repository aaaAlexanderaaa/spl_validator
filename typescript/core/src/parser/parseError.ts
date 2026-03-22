import type { Position } from "../tokens.js";

export class ParseError extends Error {
  position: Position;
  constructor(message: string, position: Position) {
    super(`${message} at line ${position.line}, col ${position.column}`);
    this.position = position;
    this.name = "ParseError";
  }
}
