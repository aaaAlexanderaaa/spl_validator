# Detailed manual review: 23 strict-mode invalid `security_content` detections

**Corpus:** [splunk/security_content](https://github.com/splunk/security_content) `detections/**/*.yml`  
**Method:** `yaml.safe_load` → `validate(search, strict=True)` (`spl_validator`).

**Splunk Search Reference hub (10.0.x family):**

- [Welcome to the Search Reference](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/introduction/welcome-to-the-search-reference)  
- [Using the Help portal](https://help.splunk.com/en/release-notes-and-updates/using-the-help-portal)

**Cross-cutting SPL references (judgement basis):**

| Topic | Reference |
|-------|-----------|
| Pipeline structure (`\|`, commands) | Search manual: *Write searches* / pipeline stages; Search Reference command pages. |
| Quoted literals & escaping | Splunk expects **paired** delimiters; embedded `"` inside `"..."` must be escaped (`\"`) or use alternate quoting—see **rex**, **eval**, **where** command pages and *Quotation marks* in Splunk documentation. |
| `rex` | [rex command](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) — pattern is typically a double-quoted string; newlines inside the string break the literal the same way as elsewhere in SPL. |
| `match` (eval) | [match(X,Y)](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) — second argument is a regex string. |
| Subsearches | [subsearch](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/subsearch) / Splunk *Subsearches* manual topic—first command inside `[ ... ]` must be able to produce a result set; **generating** commands are the usual pattern (`search`, `inputlookup`, …). |
| Metrics | [mstats](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/mstats) (registered in this validator). |

**Validator codes (this repo):**

- **SPL001** — pipeline / generating-command ordering  
- **SPL004** — unclosed string literal (lexer)  
- **SPL006** — expected command name after `\|`, got other token  
- **SPL007** — invalid character for current lexer mode  
- **SPL009** — unclosed parentheses in stats aggregation (downstream of bad parse)  
- **SPL011** — unexpected token (parse recovery)  
- **SPL013** — unknown command (`strict=True`)  
- **SPL014** — known command missing required arguments (often **after** parse broke)  
- **SPL020** — function arity  
- **SPL021** — subsearch generating-command rule **or** function wrong context (here: subsearch text)

---

## Category A — YAML line breaks *inside* double-quoted SPL strings

**Judgement:** For the **literal** string PyYAML produces, the lexer is **correct**: a newline inside `"..."` leaves the string **unclosed** before the next `\|`, so Splunk-style alternation `a|b` must be written **on one line** or built with concatenation / escapes—not a physical newline in the middle of the quotes.

**Secondary SPL013:** After the string breaks, tokens like `Invoke`, `LS`, or `roleplay` are mis-read as command names—they are **not** real missing Splunk commands.

---

### 1. `application/m365_copilot_failed_authentication_patterns.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` Unclosed string @ L3:286; `SPL009` Unclosed parens in `sum` @ L3:263; `SPL020` `sum` arity 0 @ L3:260; `SPL013` Unknown command `error"` @ L4:5 |
| **Excerpt (logical)** | `sum(eval(if(match(status, "(?i)fail` **⏎** `  \| error"), 1, 0)))` — newline **inside** the `match` regex string. |
| **Judgement** | **Invalid SPL as stored.** Intended regex is likely `(?i)fail\|error` on one line. `SPL020`/`SPL009` are **cascades** from the broken `stats` parse. `SPL013` is **noise** (`error"` is leftover from broken quoting). |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match); [stats](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/stats) |

---

### 2. `application/m365_copilot_impersonation_jailbreak_attack.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | Multiple `SPL004`; `SPL011`; **8×** `SPL013` (`roleplay`, `pretend`, `multiple`, `behave`, `malicious`, `harmful`, `unlimited`, `uncensored`) |
| **Excerpt** | `case(match(Subject_Title, "(?i)(act as` **⏎** `  \| roleplay as).*AI"), ...` and similar patterns with newlines **inside** quoted regexes. |
| **Judgement** | **Invalid as stored**; **SPL013 list is entirely false command names** (fragments of regex alternation). |
| **References** | [case](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/case); [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) |

---

### 3. `application/suspicious_java_classes.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×2; `SPL014` regex missing args; `SPL013` `processbuilder` |
| **Excerpt** | `\| regex form_data="(?i)java\.lang\.(?:runtime` **⏎** `  \| processbuilder)"` |
| **Judgement** | **Invalid as stored.** `SPL014`/`SPL013` follow from unclosed `"` on first line. |
| **References** | [regex command](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/regex); [rex](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) (same quoting discipline) |

---

### 4. `cloud/asl_aws_detect_users_creating_keys_with_encrypt_policy_without_mfa.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×6; `SPL011` ×3; `SPL006` ×3 (after `\|`, got `ERROR`) |
| **Excerpt** | `eval Statement=mvzip(Action,Principal,"` **⏎** `  \| ")` and `split(Statement, "` **⏎** `  \| `", 0)` — delimiter string split across lines. |
| **Judgement** | **Invalid as stored** if the delimiter must include newline+pipe: express with `char(10)` / concatenation on **one** SPL line, or a single-line escape; raw newline inside `"..."` still breaks the string literal. |
| **References** | [eval](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/eval); [mvzip](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/mvzip); [split](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/split) |

---

### 9. `endpoint/crowdstrike_falcon_stream_alerts.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×2; `SPL011`; `SPL013` `Intel` |
| **Excerpt** | `eval mitre_technique = case(!match(Name, "(NGAV` **⏎** `\|Intel Detection)"), Technique)` |
| **Judgement** | **Invalid as stored.** `Intel` SPL013 is noise. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match); [eval](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/eval) |

---

### 10. `endpoint/linux_proxy_socks_curl.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` @ L13:50; `SPL007` `?` @ L14:10; `SPL011`; `SPL006` after `\|`, got `MINUS` |
| **Excerpt** | `where match(process, "-x\s") OR match(process, "(?i)socks\d\w?:\/\/` **⏎** `\| --(pre)?proxy")` |
| **Judgement** | **Invalid as stored**; line 14’s `?` is read outside any string → **SPL007**. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match); [where](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/where) |

---

### 11. `endpoint/powershell_4104_hunting.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | **178 issues** (many `SPL004`, `SPL007`, `SPL011`, `SPL006`, `SPL013`) |
| **Excerpt** | Very large `match(ScriptBlockText, "(?i)Add-Exfiltration` **⏎** `  \| Add-Persistence` **⏎** `  \| …` with cmdlet list continued **inside** one pair of quotes across dozens of lines. |
| **Judgement** | **Invalid as stored.** The bulk of **SPL013** (`Invoke`, `Get`, …) are **PowerShell tokens**, not Splunk commands. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) |

---

### 13. `endpoint/regsvr32_silent_and_install_param_dll_loading.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004`; `SPL011`; `SPL013` `\` |
| **Excerpt** | `where match(process,"(?i)[\\-` **⏎** `\| \\/][Ss]{1}")` |
| **Judgement** | **Invalid as stored**; `\` command is lexer garbage. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) |

---

### 14. `endpoint/regsvr32_with_known_silent_switch_cmdline.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | Same pattern as #13 |
| **Judgement** | Same as #13. |
| **References** | Same as #13. |

---

### 16. `endpoint/windows_ad_gpo_new_cse_addition.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004`; `SPL011`; `SPL013` `\d` |
| **Excerpt** | `match(new_values, "^\{[A-Z` **⏎** `  \| \d]+\\-[A-Z` **⏎** …` | \d]+\\}")` |
| **Judgement** | **Invalid as stored**; `\d` SPL013 is **regex artifact**, not a command. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) |

---

### 17. `endpoint/windows_ad_privileged_account_sid_history_addition.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×2; `SPL007` (`^`, `?`, `}`); `SPL006`; `SPL014` rex; `SPL013` `$` |
| **Excerpt** | `\| rex field=SidHistory "(^%{\` **⏎** `\| ^)(?P<SidHistory>.*?)(}$\` **⏎** `\| $)"` |
| **Judgement** | **Invalid as stored**—multiline **delimiter** inside `rex` string; `$` SPL013 is noise. |
| **References** | [rex](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) |

---

### 19. `endpoint/wmi_permanent_event_subscription.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×2; `SPL007` `^`; `SPL006`; `SPL014` rex |
| **Excerpt** | `rex field=Message "Consumer =\s+(?<consumer>[^;\` **⏎** `\| ^$]+)"` |
| **Judgement** | **Invalid as stored**—`[^;|…]` split across lines inside quotes. |
| **References** | [rex](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) |

---

### 20. `endpoint/wmi_temporary_event_subscription.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | Same structural pattern as #19 |
| **Excerpt** | `rex ... "(?<query>[^;\` **⏎** `\| ^$]+)"` |
| **Judgement** | Same as #19. |
| **References** | [rex](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) |

---

### 21. `network/detect_snicat_sni_exfiltration.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004` ×2; `SPL014` rex; **9×** `SPL013` (`LS`, `SIZE`, `LD`, …, `finito`) |
| **Excerpt** | `rex field=server_name "(?<snicat>(LIST` **⏎** `\| LS` **⏎** `\| SIZE` **⏎** … `\| finito)-[A-Za-z0-9]{16}\\.)"` |
| **Judgement** | **Invalid as stored**; SPL013 tokens are **SNI keywords inside regex**, not commands. |
| **References** | [rex](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/rex) |

---

### 23. `web/windows_exchange_autodiscover_ssrf_abuse.yml`

| Field | Detail |
|-------|--------|
| **Category** | A |
| **Errors** | `SPL004`; `SPL011`; `SPL013` `urllib"` |
| **Excerpt** | `match(lower(http_user_agent), "python` **⏎** `\| urllib")` |
| **Judgement** | **Invalid as stored**; `urllib"` is trailing garbage from broken string. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match) |

---

## Category B — Clear grammatical / quoting defects (content bugs)

---

### 15. `endpoint/sunburst_correlation_dll_and_network_event.yml`

| Field | Detail |
|-------|--------|
| **Category** | B |
| **Errors** | `SPL006` Expected command after `\|`, got `LPAREN` @ L1:3; `SPL001` `eventstats` requires input / no generating command @ L2:5 |
| **Excerpt** | Search **begins**: `\| (\`sysmon\` EventCode=7 ...) OR (\`sysmon\` ...)` — first stage after `\|` is `(` not a command name. |
| **Judgement** | **True SPL grammar error** as written. Typical fix: `search ( ... ) OR ( ... )` without a leading `\|`, or `| search ( ... )` depending on intent. **SPL001** is a follow-on (pipeline never established a base search in our model). |
| **References** | Search manual: *Search commands* and pipeline stages; [search command](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/search) |

---

### 18. `endpoint/windows_dll_side_loading_in_calc.yml`

| Field | Detail |
|-------|--------|
| **Category** | B |
| **Errors** | `SPL004` Unclosed string @ L1:1 |
| **Excerpt** | YAML block produces: **`'`**`` `sysmon` ``**\n**`EventCode=7`… — a **leading single quote** opens a literal that consumes the rest of the search incorrectly. |
| **Judgement** | **True content bug** (stray `'` or wrong quoting in YAML / export). |
| **References** | Splunk *Quotation marks* / field literals in Search manual |

---

### 22. `network/ssl_certificates_with_punycode.yml`

| Field | Detail |
|-------|--------|
| **Category** | B |
| **Errors** | `SPL007` `}` @ L8:120; `SPL004` unclosed string @ L8:122 |
| **Excerpt** | `\| cyberchef ... jsonrecipe="[{"op":"From Punycode","args":[true]}]"` — the **`"`** after `[{`** ends the SPL string early. |
| **Judgement** | **True quoting bug**; inner double quotes must be **`\"`** (or use a macro / alternate quoting strategy per Splunk rules). |
| **References** | [cyberchef](https://splunkbase.splunk.com/app/5348) (app); Splunk string escaping in command arguments |

---

## Category C — `summary` leading a `join` subsearch (validator vs MLTK)

---

### 5–8. Deprecated cloud ML outlier detections

| Files | Detail |
|-------|--------|
| **Paths** | `deprecated/abnormally_high_number_of_cloud_infrastructure_api_calls.yml` (L9); `..._instances_destroyed.yml` (L13); `..._instances_launched.yml` (L12); `..._cloud_security_group_api_calls.yml` (L11) |
| **Category** | C |
| **Errors** | **Only** `SPL021`: *Subsearch must start with a generating command … got `summary`* |
| **Excerpt** | `\| join user HourOfDay isWeekend [ summary cloud_excessive_api_calls_v1 ]` (model name varies). |
| **Judgement** | **Not** a newline-in-string issue. **Disputable:** ML Toolkit may install **`summary`** such that this subsearch is legal in product; this validator types **`summary`** as **transforming** and enforces a **generating** first command in `[ ... ]` (`spl_validator/src/analyzer/subsearch.py`). **Verdict:** *policy mismatch possible*; treat as **validator limitation** relative to MLTK, not as “random typo.” |
| **References** | Splunk ML Toolkit docs for `summary`, `apply`, `fit`; [join](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/join); [subsearch](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/search-commands/subsearch) |

---

## Category D — Unicode dashes + newline (mixed)

---

### 12. `endpoint/powershell___connect_to_internet_with_hidden_window.yml`

| Field | Detail |
|-------|--------|
| **Category** | D (+ A) |
| **Errors** | `SPL004`; `SPL007` for **U+2013 EN DASH**, **U+2014 EM DASH**, **U+2015 HORIZONTAL BAR**; `SPL006`; `SPL013` `\` |
| **Excerpt** | `match(process,"(?i)[\\-` **⏎** `\| \/` **⏎** `<U+2013><U+2014><U+2015>`**…**`w(in*d*o*w*s*t*y*l*e*)*\s+[^-]")` |
| **Judgement** | **(A)** Newline inside quotes → **invalid** as with other Category A items. **(D)** If Splunk’s lexer accepts Unicode punctuation inside double-quoted strings, **SPL007** may be **validator charset strictness**; confirm against Splunk behavior in your deployment. |
| **References** | [match](https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/evaluation-functions/match); Splunk docs on UTF-8 in searches |

---

## Summary table (all 23)

| # | File | Cat | Primary judgement |
|---|------|-----|-------------------|
| 1 | `application/m365_copilot_failed_authentication_patterns.yml` | A | Newline inside `match` string → invalid literal; cascades + noise |
| 2 | `application/m365_copilot_impersonation_jailbreak_attack.yml` | A | Same; many false SPL013 |
| 3 | `application/suspicious_java_classes.yml` | A | Newline inside `regex` pattern |
| 4 | `cloud/asl_aws_detect_users_creating_keys_with_encrypt_policy_without_mfa.yml` | A | Newline inside `mvzip`/`split` delimiter strings |
| 5 | `deprecated/...cloud_infrastructure_api_calls.yml` | C | `summary` first in subsearch vs validator rule |
| 6 | `deprecated/...instances_destroyed.yml` | C | Same |
| 7 | `deprecated/...instances_launched.yml` | C | Same |
| 8 | `deprecated/...security_group_api_calls.yml` | C | Same |
| 9 | `endpoint/crowdstrike_falcon_stream_alerts.yml` | A | Newline inside `match` |
| 10 | `endpoint/linux_proxy_socks_curl.yml` | A | Newline inside `match` |
| 11 | `endpoint/powershell_4104_hunting.yml` | A | Massive multiline `match`; hundreds of false SPL013 |
| 12 | `endpoint/powershell___connect_to_internet_with_hidden_window.yml` | D+A | Unicode dashes + newline in `match` |
| 13 | `endpoint/regsvr32_silent_and_install_param_dll_loading.yml` | A | Newline inside `match` |
| 14 | `endpoint/regsvr32_with_known_silent_switch_cmdline.yml` | A | Same |
| 15 | `endpoint/sunburst_correlation_dll_and_network_event.yml` | B | `\| (` illegal first stage |
| 16 | `endpoint/windows_ad_gpo_new_cse_addition.yml` | A | Newline inside `match` (GUID regex) |
| 17 | `endpoint/windows_ad_privileged_account_sid_history_addition.yml` | A | Newline inside `rex` pattern |
| 18 | `endpoint/windows_dll_side_loading_in_calc.yml` | B | Leading stray `'` |
| 19 | `endpoint/wmi_permanent_event_subscription.yml` | A | Newline inside `rex` |
| 20 | `endpoint/wmi_temporary_event_subscription.yml` | A | Newline inside `rex` |
| 21 | `network/detect_snicat_sni_exfiltration.yml` | A | Newline inside `rex`; false SPL013 |
| 22 | `network/ssl_certificates_with_punycode.yml` | B | Unescaped `"` inside `jsonrecipe="..."` |
| 23 | `web/windows_exchange_autodiscover_ssrf_abuse.yml` | A | Newline inside `match` |

---

## Reproducing

```bash
git clone --depth 1 https://github.com/splunk/security_content.git /tmp/security_content
python3 tools/scan_external_detections.py --root /tmp/security_content/detections
```

To dump JSON for each invalid row (errors + full `search` text), loop `validate(s, strict=True)` and serialize—used to build this analysis.
