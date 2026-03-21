# Manual analysis: 23 strict-mode invalid `security_content` detections

**Method:** `validate(spl, strict=True)` on YAML `search` text as loaded by PyYAML (same as `tools/scan_external_detections.py`). One corpus snapshot (Splunk `security_content`, shallow clone, 2006 detection searches).

**Summary**

| Category | Count | Meaning |
|----------|------:|---------|
| **A – YAML line wrap inside `"..."` (invalid extracted SPL)** | 16 | Real newline characters appear *inside* double-quoted SPL strings. Standard SPL does not allow raw newlines there; the **logical** regex usually meant `foo\|bar` on one line. Validator is **correct** for the literal string; ESCU import may normalize in product. |
| **B – True content / quoting bugs** | 3 | Issues that would break (or nearly break) in Splunk as written: stray quote, illegal first command, unescaped inner quotes. |
| **C – Subsearch + `summary` (validator policy vs MLTK)** | 4 | Only **SPL021**: we require subsearches to start with a **generating** command; `summary` is registered as **transforming**. MLTK may treat `summary model` as valid at the start of a bracketed subsearch—**disputable / product-specific**. |
| **D – Lexer / encoding edge case** | 1 | Unicode en-dash / em-dash / horizontal bar (U+2013, U+2014, U+2015) inside a quoted regex triggers **SPL007**. If Splunk’s editor accepts those code points inside strings, this is partly a **validator charset** limitation; the search also has newline-in-string like category A. |

---

## Per-file verdict

### A – Multiline double-quoted strings (invalid as extracted; SPL013 after parse are noise)

| # | File | Primary errors | Manual note |
|---|------|----------------|-------------|
| 1 | `application/m365_copilot_failed_authentication_patterns.yml` | SPL004, SPL020 cascade, SPL013 `error"` | `match(status, "(?i)fail` then newline then `\| error"` — string never closes before `\|`. |
| 2 | `application/m365_copilot_impersonation_jailbreak_attack.yml` | SPL004, many SPL013 (`roleplay`, `pretend`, …) | Huge `case(match(...))` with alternations split across lines **inside** quotes. SPL013 tokens are **not** real commands. |
| 3 | `application/suspicious_java_classes.yml` | SPL004, SPL013 `processbuilder` | `regex form_data="(?i)java...(?:runtime` newline `\| processbuilder)"`. |
| 4 | `cloud/asl_aws_detect_users_creating_keys_with_encrypt_policy_without_mfa.yml` | SPL004, SPL006 | `mvzip(...,"` newline `\| ")` and `split(Statement, "` newline `\| `")` — multiline **delimiter** strings. |
| 9 | `endpoint/crowdstrike_falcon_stream_alerts.yml` | SPL004, SPL013 `Intel` | `match(Name, "(NGAV` newline `\|Intel Detection)")`. |
| 10 | `endpoint/linux_proxy_socks_curl.yml` | SPL004 | `match(process, "(?i)socks...` newline `\| --(pre)?proxy")`. |
| 11 | `endpoint/powershell_4104_hunting.yml` | SPL004, mass SPL013 | Multiline match listing PowerShell cmdlet names **inside** one quoted pattern. |
| 13 | `endpoint/regsvr32_silent_and_install_param_dll_loading.yml` | SPL004 | Similar `match(process,"(?i)[\\-` newline `\| \\/][Ss]{1}")`. |
| 14 | `endpoint/regsvr32_with_known_silent_switch_cmdline.yml` | SPL004, SPL013 `\` | Same pattern; backslash command is parse garbage. |
| 16 | `endpoint/windows_ad_gpo_new_cse_addition.yml` | SPL004, SPL013 `\d` | `match(new_values, "^\{[A-Z` newlines `\| \d]+...")` — GUID regex split across lines. |
| 17 | `endpoint/windows_ad_privileged_account_sid_history_addition.yml` | SPL004, SPL007, SPL014 | `rex ... "(^%{\` newline `\| ^)(?P<SidHistory>...)(}$\` newline `\| $)"` — **intended** multiline regex alternation written as physical newlines inside quotes. |
| 19 | `endpoint/wmi_permanent_event_subscription.yml` | SPL004, SPL014 | `rex ... "(?<consumer>[^;\` newline `\| ^$]+)"`. |
| 20 | `endpoint/wmi_temporary_event_subscription.yml` | SPL004, SPL014 | Same for `NotificationQuery`. |
| 21 | `network/detect_snicat_sni_exfiltration.yml` | SPL004, SPL013 `LS`, `SIZE`, … | `rex ... "(?<snicat>(LIST` newline `\| LS` newline …` | finito)-..."`. |
| 23 | `web/windows_exchange_autodiscover_ssrf_abuse.yml` | SPL004, SPL013 `urllib"` | `match(..., "python` newline `\| urllib")`. |

### B – Genuine grammatical / quoting problems in the stored SPL

| # | File | Primary errors | Manual note |
|---|------|----------------|-------------|
| 15 | `endpoint/sunburst_correlation_dll_and_network_event.yml` | SPL006, SPL001 | Pipeline begins with **`\| (`** — nothing after the first pipe is a valid command name. Should be something like `search ( ... )` or drop the leading pipe. **True bug** in the YAML string relative to SPL grammar. |
| 18 | `endpoint/windows_dll_side_loading_in_calc.yml` | SPL004 (line 1 col 1) | Parsed string starts with **`'`** then `` `sysmon` `` — opens a single-quoted literal that never closes sanely. **True bug** (stray quote / wrong YAML quoting). |
| 22 | `network/ssl_certificates_with_punycode.yml` | SPL007, SPL004 | `jsonrecipe="[{"op":"From Punycode",...}]"` — inner `"` **terminates** the outer string early. Must use `\"` or single-quoted JSON fragment per Splunk rules. **True bug** as written. |

### C – MLTK `summary` inside `join` subsearch (validator rule)

| # | File | Primary errors | Manual note |
|---|------|----------------|-------------|
| 5 | `deprecated/abnormally_high_number_of_cloud_infrastructure_api_calls.yml` | SPL021 | `join ... [ summary cloud_excessive_api_calls_v1 ]` — first token in subsearch is `summary`. |
| 6 | `deprecated/abnormally_high_number_of_cloud_instances_destroyed.yml` | SPL021 | Same pattern (different model name). |
| 7 | `deprecated/abnormally_high_number_of_cloud_instances_launched.yml` | SPL021 | Same. |
| 8 | `deprecated/abnormally_high_number_of_cloud_security_group_api_calls.yml` | SPL021 | Same. |

**Assessment:** These are **deprecated** ML-outlier detections. In Splunk with MLTK, `summary <model>` may be legal as the leading command of a subsearch even though it is not a **generating** command in the classic sense. Our **SPL021** is consistent with `subsearch.py` + registry typing, but may be a **false negative for “would Splunk run this?”** if the app registers special behavior. **Not** a YAML newline-string issue.

### D – Unicode dashes + newline (mixed)

| # | File | Primary errors | Manual note |
|---|------|----------------|-------------|
| 12 | `endpoint/powershell___connect_to_internet_with_hidden_window.yml` | SPL004, SPL007 (`\u2013` etc.), SPL006 | Contains **newline inside** `match(process,"...")` like category A, **and** Unicode dash characters inside the character class. If Splunk allows UTF-8 in string literals, **SPL007 on U+2013** may be **over-strict**; the newline still makes the string **unclosed** in normal SPL. |

---

## Bottom line

- **None** of the 23 are “clean” SPL **as the literal string** returned by YAML: even the four `summary` cases fail our rules; the other 19 fail lexer/parser first (or have explicit quote/command bugs).
- **16 + most of #12** are dominated by the **same authoring pattern**: pretty-printed YAML that inserts newlines **inside** Splunk double-quoted strings. **Fix in content:** join those lines into one logical string or use escapes/`+` concatenation.
- **3 files (#15, #18, #22)** should be treated as **actual defects** in the stored search (or as requiring Splunk-specific escaping), independent of the validator.
- **4 deprecated ML files** are **policy/typing** questions (`summary` in subsearch), not string-literal typos.

## Reproducing the list

```bash
python3 tools/scan_external_detections.py --root /path/to/security_content/detections --format json
# or build invalid_items with validate(..., strict=True) as in CI
```

Raw machine-readable dump used for this write-up: run the validator in a loop and serialize `errors` + `search` for each invalid row (see repository history for `invalid23.json` generation scripts).
