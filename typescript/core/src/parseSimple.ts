/**
 * Pipeline parser (mirrors spl_validator.core.parse_simple).
 */
import type { Aggregation, Argument, Clause, Command, Pipeline, Subsearch } from "./ast.js";
import { CommandParser } from "./parser/commandParser.js";
import { ExpressionParser } from "./parser/expressionParser.js";
import { ParseError } from "./parser/parseError.js";
import { KEYWORDS, type Token, TokenType, pos } from "./tokens.js";
import { addError, addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { isGeneratingCommand, isKnownCommand } from "./registry.js";
import {
  appendMissingPipeError,
  coalesceDottedIdentifiers,
  extractSingleSubsearch,
  isCommandKeyword,
  isPositionalArgToken,
  normalizePositionalArgTokens,
  scanSearchKvOptions,
} from "./parseSimple/helpers.js";

export function parseSimple(tokens: Token[], result: ValidationResult): Pipeline | null {
  if (!tokens.length) return null;

  const commands: Command[] = [];
  let i = 0;

  if (tokens[0]!.type !== TokenType.PIPE) {
    const startPos = tokens[0]!.start;
    const cmdTokens: Token[] = [];
    let bracketDepth = 0;
    while (i < tokens.length && tokens[i]!.type !== TokenType.EOF) {
      if (tokens[i]!.type === TokenType.PIPE && bracketDepth === 0) break;
      if (tokens[i]!.type === TokenType.LBRACKET) bracketDepth += 1;
      else if (tokens[i]!.type === TokenType.RBRACKET && bracketDepth > 0) bracketDepth -= 1;
      cmdTokens.push(tokens[i]!);
      i += 1;
    }

    if (cmdTokens.length) {
      const firstToken = cmdTokens[0]!;
      const options: Record<string, unknown> = {};
      const clauses: Record<string, Clause> = {};
      let args: Argument[] = [];
      let currentCmd: Command | null = null;

      if (firstToken.type === TokenType.IDENTIFIER) {
        const cmdName = firstToken.value.toLowerCase();
        if (isKnownCommand(cmdName) && !isGeneratingCommand(cmdName)) {
          currentCmd = {
            name: firstToken.value,
            start: firstToken.start,
            end: cmdTokens[cmdTokens.length - 1]!.end,
            options: {},
            clauses: {},
            args: [],
            aggregations: [],
            subsearch: null,
          };
        } else if (isKnownCommand(cmdName)) {
          let subsearch: Subsearch | null = null;
          let argToks = cmdTokens.slice(1);
          if (cmdTokens.length > 1) {
            const [ss, rem] = extractSingleSubsearch(cmdTokens.slice(1), result, parseSimple);
            subsearch = ss;
            argToks = rem;
          }
          const cmdParser = new CommandParser(argToks);
          try {
            const parsedOpts = cmdParser.parseOptions();
            Object.assign(options, parsedOpts);
            const remaining = cmdParser.getRemainingTokens();
            for (const tok of remaining) {
              args.push({ start: tok.start, end: tok.end, value: tok.value });
            }
            if (cmdName === "search") {
              Object.assign(options, scanSearchKvOptions(remaining));
            }
            const fl = remaining[0];
            if (fl) appendMissingPipeError(result, fl);
          } catch (e) {
            if (e instanceof ParseError) {
              addError(result, "SPL011", e.message, e.position, e.position);
            } else throw e;
          }
          currentCmd = {
            name: firstToken.value,
            start: firstToken.start,
            end: cmdTokens[cmdTokens.length - 1]!.end,
            options,
            clauses,
            args,
            aggregations: [],
            subsearch,
          };
        } else {
          let subsearch: Subsearch | null = null;
          const [ss, argToks] = extractSingleSubsearch(cmdTokens, result, parseSimple);
          subsearch = ss;
          const cmdParser = new CommandParser(argToks);
          try {
            const parsedOpts = cmdParser.parseOptions();
            Object.assign(options, parsedOpts);
            const remaining = cmdParser.getRemainingTokens();
            for (const tok of remaining) {
              args.push({ start: tok.start, end: tok.end, value: tok.value });
            }
            Object.assign(options, scanSearchKvOptions(remaining));
            const fl = remaining[0];
            if (fl) appendMissingPipeError(result, fl);
          } catch (e) {
            if (e instanceof ParseError) {
              addError(result, "SPL011", e.message, e.position, e.position);
            } else throw e;
          }
          currentCmd = {
            name: "search",
            start: startPos,
            end: cmdTokens[cmdTokens.length - 1]!.end,
            options,
            clauses,
            args,
            aggregations: [],
            subsearch,
          };
        }
      } else {
        let subsearch: Subsearch | null = null;
        const [ss, argToks] = extractSingleSubsearch(cmdTokens, result, parseSimple);
        subsearch = ss;
        const cmdParser = new CommandParser(argToks);
        try {
          const parsedOpts = cmdParser.parseOptions();
          Object.assign(options, parsedOpts);
          const remaining = cmdParser.getRemainingTokens();
          for (const tok of remaining) {
            args.push({ start: tok.start, end: tok.end, value: tok.value });
          }
          Object.assign(options, scanSearchKvOptions(remaining));
        } catch (e) {
          if (e instanceof ParseError) {
            addError(result, "SPL011", e.message, e.position, e.position);
          } else throw e;
        }
        currentCmd = {
          name: "search",
          start: startPos,
          end: cmdTokens[cmdTokens.length - 1]!.end,
          options,
          clauses,
          args,
          aggregations: [],
          subsearch,
        };
      }
      if (currentCmd) commands.push(currentCmd);
    }
  }

  while (i < tokens.length) {
    const token = tokens[i]!;
    if (token.type === TokenType.EOF) break;

    if (token.type === TokenType.PIPE) {
      i += 1;
      if (
        i < tokens.length &&
        (tokens[i]!.type === TokenType.IDENTIFIER ||
          isCommandKeyword(tokens[i]!.type) ||
          tokens[i]!.type === TokenType.MACRO)
      ) {
        const cmdStart = tokens[i]!;
        let cmdName = cmdStart.value;
        const cmdTokens: Token[] = [];
        let j = i;
        let bracketDepth = 0;
        while (j < tokens.length && tokens[j]!.type !== TokenType.EOF) {
          if (tokens[j]!.type === TokenType.PIPE && bracketDepth === 0) break;
          if (tokens[j]!.type === TokenType.LBRACKET) bracketDepth += 1;
          else if (tokens[j]!.type === TokenType.RBRACKET && bracketDepth > 0) bracketDepth -= 1;
          cmdTokens.push(tokens[j]!);
          j += 1;
        }
        const cmdEnd = j > i ? tokens[j - 1]! : cmdStart;
        i = j;

        let subsearch: Subsearch | null = null;
        let argTokens = cmdTokens.slice(1);
        let bracketStart: number | null = null;
        let bracketEnd: number | null = null;
        let depth = 0;
        for (let idx = 0; idx < argTokens.length; idx++) {
          if (argTokens[idx]!.type === TokenType.LBRACKET) {
            bracketStart = idx;
            depth = 1;
            for (let jdx = idx + 1; jdx < argTokens.length; jdx++) {
              if (argTokens[jdx]!.type === TokenType.LBRACKET) depth += 1;
              else if (argTokens[jdx]!.type === TokenType.RBRACKET) {
                depth -= 1;
                if (depth === 0) {
                  bracketEnd = jdx;
                  break;
                }
              }
            }
            break;
          }
        }

        if (bracketStart !== null && bracketEnd === null) {
          const startTok = argTokens[bracketStart]!;
          addError(
            result,
            "SPL011",
            "Unclosed subsearch bracket '['",
            startTok.start,
            startTok.end,
            "Add a closing ']' for the subsearch",
          );
        } else if (bracketStart !== null && bracketEnd !== null) {
          const inner = argTokens.slice(bracketStart + 1, bracketEnd);
          const lbr = argTokens[bracketStart]!;
          const rbr = argTokens[bracketEnd]!;
          let innerPipeline: Pipeline | null = null;
          if (inner.length) {
            const eofPos = inner[inner.length - 1]!.end;
            innerPipeline = parseSimple(
              [...inner, { type: TokenType.EOF, value: "", start: eofPos, end: eofPos }],
              result,
            );
          }
          subsearch = { start: lbr.start, end: rbr.end, pipeline: innerPipeline };
          argTokens = argTokens.slice(0, bracketStart).concat(argTokens.slice(bracketEnd + 1));
        }

        const options: Record<string, unknown> = {};
        const clauses: Record<string, Clause> = {};
        let args: Argument[] = [];
        let aggregations: Aggregation[] = [];

        if (cmdStart.type === TokenType.MACRO) {
          args.push({ start: cmdStart.start, end: cmdStart.end, value: cmdStart.value });
          cmdName = "macro";
        } else if (cmdTokens.length > 1) {
          const cmdParser = new CommandParser(argTokens);
          const statsCommands = new Set(["stats", "chart", "timechart", "eventstats", "streamstats"]);
          try {
            if (statsCommands.has(cmdName.toLowerCase())) {
              for (const tok of argTokens) {
                if (tok.type === TokenType.IDENTIFIER || tok.type === TokenType.AS) {
                  args.push({ start: tok.start, end: tok.end, value: tok.value });
                }
              }
              const po = cmdParser.parseOptions();
              Object.assign(options, po);
              const [aggs, unexpected, fnErrs] = cmdParser.parseStatsArgs();
              aggregations = aggs;
              for (const tok of unexpected) {
                addError(
                  result,
                  "SPL008",
                  `Unexpected identifier '${tok.value}' in ${cmdName} command`,
                  tok.start,
                  tok.end,
                  "Check syntax: this may be a typo or misplaced argument",
                );
              }
              for (const [code, message, st, en] of fnErrs) {
                addError(result, code, message, st, en);
              }
              const byClause = cmdParser.parseByClause();
              if (byClause) clauses.BY = byClause;
            } else if (cmdName.toLowerCase() === "top" || cmdName.toLowerCase() === "rare") {
              Object.assign(options, cmdParser.parseOptions());
              let remaining = normalizePositionalArgTokens(cmdParser.getRemainingTokens());
              let k = 0;
              if (k < remaining.length && remaining[k]!.type === TokenType.NUMBER && !("limit" in options)) {
                try {
                  options["limit"] = parseInt(remaining[k]!.value, 10);
                } catch {
                  options["limit"] = remaining[k]!.value;
                }
                k += 1;
              }
              const targetTokens: Token[] = [];
              const byTokens: Token[] = [];
              let sawBy = false;
              while (k < remaining.length) {
                const tok = remaining[k]!;
                if (tok.type === TokenType.BY) {
                  sawBy = true;
                  k += 1;
                  break;
                }
                targetTokens.push(tok);
                k += 1;
              }
              if (sawBy) byTokens.push(...remaining.slice(k));
              for (const item of coalesceDottedIdentifiers(targetTokens)) {
                if (typeof item === "string") {
                  args.push({ start: cmdStart.start, end: cmdEnd.end, value: item });
                } else if (item.type === TokenType.IDENTIFIER) {
                  args.push({ start: item.start, end: item.end, value: item.value });
                }
              }
              if (byTokens.length) {
                const byFields: string[] = [];
                for (const item of coalesceDottedIdentifiers(byTokens)) {
                  if (typeof item === "string") byFields.push(item);
                  else if (item.type === TokenType.IDENTIFIER) byFields.push(item.value);
                }
                if (byFields.length) {
                  clauses.BY = {
                    keyword: "BY",
                    fields: byFields,
                    start: byTokens[0]!.start,
                    end: byTokens[byTokens.length - 1]!.end,
                  };
                }
              }
            } else if (cmdName.toLowerCase() === "eval") {
              if (!argTokens.length) {
                addError(
                  result,
                  "SPL014",
                  "eval is missing required assignments",
                  cmdStart.start,
                  cmdEnd.end,
                  "Example: | eval status=if(code>=400,\"error\",\"ok\")",
                );
              } else {
                const exprParser = new ExpressionParser(argTokens);
                while (!exprParser.atEnd()) {
                  if (exprParser.match(TokenType.MACRO)) {
                    const tok = exprParser.advance();
                    addWarning(
                      result,
                      "SPL053",
                      "Macro used inside eval; skipping further eval validation (macro expansion is not supported)",
                      tok.start,
                      tok.end,
                      "Expand the macro before validating, or remove it from eval.",
                    );
                    break;
                  }
                  let assignment;
                  try {
                    assignment = exprParser.parseAssignment();
                  } catch (e) {
                    if (e instanceof ParseError) {
                      addError(result, "SPL011", e.message, e.position, e.position);
                      if (!exprParser.atEnd()) exprParser.advance();
                      continue;
                    }
                    throw e;
                  }
                  if (assignment === null) {
                    const startToken = exprParser.current();
                    try {
                      exprParser.parseExpression();
                    } catch (e) {
                      if (e instanceof ParseError) {
                        addError(result, "SPL011", e.message, e.position, e.position);
                        exprParser.advance();
                      }
                    }
                    addError(
                      result,
                      "SPL010",
                      "eval requires assignment syntax: <field>=<expression>",
                      startToken.start,
                      startToken.end,
                      'Example: | eval status=if(code>=400,"error","ok")',
                    );
                  } else {
                    args.push({
                      start: assignment.start,
                      end: assignment.end,
                      value: assignment,
                    });
                  }
                  if (exprParser.atEnd()) break;
                  if (exprParser.match(TokenType.COMMA)) {
                    exprParser.advance();
                    if (exprParser.atEnd()) {
                      addError(
                        result,
                        "SPL011",
                        "Trailing comma in eval assignment list",
                        cmdStart.start,
                        cmdEnd.end,
                        "Remove the trailing comma",
                      );
                      break;
                    }
                    continue;
                  }
                  if (exprParser.match(TokenType.MACRO)) {
                    const tok = exprParser.advance();
                    addWarning(
                      result,
                      "SPL053",
                      "Macro used inside eval; skipping further eval validation (macro expansion is not supported)",
                      tok.start,
                      tok.end,
                      "Expand the macro before validating, or remove it from eval.",
                    );
                    break;
                  }
                  const nextTok = exprParser.current();
                  addError(
                    result,
                    "SPL010",
                    "Expected ',' between eval assignments",
                    nextTok.start,
                    nextTok.end,
                    "Use: | eval a=1, b=2",
                  );
                }
              }
            } else if (cmdName.toLowerCase() === "where") {
              if (!argTokens.length) {
                addError(
                  result,
                  "SPL014",
                  "where is missing a required expression",
                  cmdStart.start,
                  cmdEnd.end,
                  "Example: | where status>=400",
                );
              } else {
                const exprParser = new ExpressionParser(argTokens);
                try {
                  const expr = exprParser.parseExpression();
                  args.push({ start: expr.start, end: expr.end, value: expr });
                  if (!exprParser.atEnd()) {
                    const extra = exprParser.current();
                    if (extra.type === TokenType.MACRO) {
                      const tok = exprParser.advance();
                      addWarning(
                        result,
                        "SPL053",
                        "Macro used inside where; skipping further where validation (macro expansion is not supported)",
                        tok.start,
                        tok.end,
                        "Expand the macro before validating, or remove it from where.",
                      );
                    } else {
                      addError(
                        result,
                        "SPL011",
                        "Trailing tokens after where expression",
                        extra.start,
                        extra.end,
                        "Remove trailing tokens or add the missing operator/parenthesis",
                      );
                    }
                  }
                } catch (e) {
                  if (e instanceof ParseError) {
                    addError(result, "SPL011", e.message, e.position, e.position);
                  } else throw e;
                }
              }
            } else if (cmdName.toLowerCase() === "bin") {
              parseBinCommand(argTokens, cmdStart, cmdEnd, options, args, result);
            } else {
              Object.assign(options, cmdParser.parseOptions());
              const byClause = cmdParser.parseByClause();
              if (byClause) clauses.BY = byClause;
              const remaining = normalizePositionalArgTokens(cmdParser.getRemainingTokens());
              for (const item of coalesceDottedIdentifiers(remaining)) {
                if (typeof item === "string") {
                  args.push({ start: cmdStart.start, end: cmdEnd.end, value: item });
                } else if (isPositionalArgToken(item)) {
                  args.push({ start: item.start, end: item.end, value: item.value });
                }
              }
            }
          } catch (e) {
            if (e instanceof ParseError) {
              addError(result, "SPL011", e.message, e.position, e.position);
            } else throw e;
          }
        }

        commands.push({
          name: cmdName,
          start: cmdStart.start,
          end: cmdEnd.end,
          options,
          clauses,
          args,
          aggregations,
          subsearch,
        });
      } else if (i < tokens.length && tokens[i]!.type !== TokenType.EOF) {
        addError(
          result,
          "SPL006",
          `Expected command name after pipe, got ${tokens[i]!.type}`,
          tokens[i]!.start,
          tokens[i]!.end,
        );
        i += 1;
      }
    } else {
      i += 1;
    }
  }

  if (!commands.length) {
    addError(result, "SPL005", "Empty pipeline - no commands found", pos(1, 1, 0), pos(1, 1, 0));
    return null;
  }

  return {
    commands,
    start: commands[0]!.start,
    end: commands[commands.length - 1]!.end,
  };
}

function parseBinCommand(
  binTokens: Token[],
  cmdStart: Token,
  cmdEnd: Token,
  options: Record<string, unknown>,
  args: Argument[],
  result: ValidationResult,
): void {
  const consumed = new Set<number>();
  let idx = 0;
  while (idx + 2 < binTokens.length) {
    const t0 = binTokens[idx]!;
    const t1 = binTokens[idx + 1]!;
    const t2 = binTokens[idx + 2]!;
    if (t0.type === TokenType.IDENTIFIER && t1.type === TokenType.EQ) {
      const key = t0.value;
      if (t2.type === TokenType.STRING) {
        options[key] = t2.value;
      } else if (t2.type === TokenType.NUMBER) {
        try {
          options[key] = !t2.value.includes(".") ? parseInt(t2.value, 10) : parseFloat(t2.value);
        } catch {
          options[key] = t2.value;
        }
      } else if (t2.type === TokenType.TRUE || t2.type === TokenType.FALSE) {
        options[key] = t2.type === TokenType.TRUE;
      } else if (t2.type === TokenType.IDENTIFIER) {
        options[key] = t2.value;
      } else {
        options[key] = t2.value;
      }
      consumed.add(idx);
      consumed.add(idx + 1);
      consumed.add(idx + 2);
      idx += 3;
      continue;
    }
    idx += 1;
  }
  let fieldTok: Token | null = null;
  for (let iTok = 0; iTok < binTokens.length; iTok++) {
    if (consumed.has(iTok)) continue;
    const tok = binTokens[iTok]!;
    if (tok.type === TokenType.AS) continue;
    if (tok.type === TokenType.IDENTIFIER) {
      fieldTok = tok;
      consumed.add(iTok);
      break;
    }
  }
  if (fieldTok === null) {
    addError(
      result,
      "SPL010",
      "bin requires a target field (e.g. _time)",
      cmdStart.start,
      cmdEnd.end,
      "Example: | bin span=1d _time",
    );
  } else {
    args.push({ start: fieldTok.start, end: fieldTok.end, value: fieldTok.value });
  }
  for (let iTok = 0; iTok < binTokens.length; iTok++) {
    if (consumed.has(iTok)) continue;
    const tok = binTokens[iTok]!;
    if (tok.type === TokenType.AS) {
      consumed.add(iTok);
      let aliasTok: Token | null = null;
      for (let j = iTok + 1; j < binTokens.length; j++) {
        if (consumed.has(j)) continue;
        if (binTokens[j]!.type === TokenType.IDENTIFIER) {
          aliasTok = binTokens[j]!;
          consumed.add(j);
          break;
        }
      }
      if (aliasTok === null) {
        addError(
          result,
          "SPL010",
          "bin AS requires a field name after AS",
          tok.start,
          tok.end,
          "Example: | bin span=1d _time AS day",
        );
      }
      break;
    }
  }
  const leftovers = binTokens.filter((_, i) => !consumed.has(i));
  if (leftovers.length) {
    const first = leftovers[0]!;
    if (first.type === TokenType.IDENTIFIER && isKnownCommand(first.value.toLowerCase())) {
      addError(
        result,
        "SPL012",
        `Missing pipe '|' before command '${first.value}'`,
        first.start,
        first.end,
        `Did you forget a pipe '|' before '${first.value}'?`,
      );
    } else {
      addError(
        result,
        "SPL008",
        `Unexpected token '${first.value}' in bin command`,
        first.start,
        first.end,
        "Check bin syntax: bin (<options>)* <field> (AS <field>)?",
      );
    }
  }
}
