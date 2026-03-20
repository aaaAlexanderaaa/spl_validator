# Validating `splunk/security_content` detection searches

This repository includes a scanner that runs the SPL validator over YAML `search` fields (same shape as Splunk ESCU / security content detections).

## Run the scan

Clone [splunk/security_content](https://github.com/splunk/security_content) and point the tool at its `detections` folder:

```bash
git clone --depth 1 https://github.com/splunk/security_content.git /tmp/security_content
python3 tools/scan_external_detections.py --root /tmp/security_content/detections
```

Or use the environment variable:

```bash
export SECURITY_CONTENT_ROOT=/tmp/security_content/detections
python3 tools/scan_external_detections.py
```

Optional pytest (skipped unless the variable is set):

```bash
SECURITY_CONTENT_ROOT=/tmp/security_content/detections python3 -m pytest tests/test_security_content_scan.py -v
```

## Snapshot (clone dated **2026-03-20**)

| Metric | Value |
|--------|------:|
| YAML files with `search` | 2006 |
| Valid per validator | 1987 |
| Invalid | 19 |

Dominant error codes on invalid rows: **SPL004** (unclosed string), **SPL011** / **SPL006** (parse recovery), **SPL007** (invalid character inside botched strings), plus occasional **SPL014** (regex argument not seen because parsing stopped earlier).

## Are the “syntax” failures real Splunk bugs?

Almost all invalid rows share one **content-encoding pattern**: multi-line YAML block scalars (`search: |-`) where **physical line breaks fall inside a Splunk double-quoted string**. PyYAML preserves those newlines, so the string passed to the validator contains **raw newline characters inside `"..."`**. Standard SPL does not treat that as a line continuation inside the string—the quote is still “open” across the newline, so the lexer reports **unclosed string** (SPL004). The **author intent** is usually a single-line regex or string with a `|` alternation (e.g. `python|urllib`), not a newline.

**Conclusion:** For those 17+ cases, the **detection logic is usually sound**, but **the YAML as stored is not equivalent to valid one-line SPL** if pasted verbatim into Splunk’s search bar. Packaging/import pipelines may normalize whitespace; the validator is correct for the literal string extracted by YAML.

### Cases that look genuinely wrong as written (not just wrapping)

1. **`endpoint/windows_dll_side_loading_in_calc.yml`** — Parsed `search` begins with a **leading single quote** before the macro (`` '`sysmon`\n...``). That opens a string literal and breaks the rest of the pipeline.

2. **`network/ssl_certificates_with_punycode.yml`** — `cyberchef` argument `jsonrecipe="[{"op":"From Punycode",...}]"` embeds **unescaped double quotes** inside a double-quoted SPL string, so the closing quote is reached too early. This needs `\"` escaping or different quoting.

3. **`endpoint/sunburst_correlation_dll_and_network_event.yml`** — Search starts with **`| (`** (parenthesis immediately after the pipe). SPL expects a **command name** after `|`, so the validator reports **SPL006** and then **SPL001** (no generating command). If Splunk does not rewrite this form, it is invalid; a fix would be something like wrapping in `search (...)` or removing the erroneous leading pipe.

### Representative “line wrap inside quotes” files (intent OK, literal string invalid)

Includes, among others:

- `application/m365_copilot_failed_authentication_patterns.yml`
- `application/m365_copilot_impersonation_jailbreak_attack.yml`
- `application/suspicious_java_classes.yml`
- `cloud/asl_aws_detect_users_creating_keys_with_encrypt_policy_without_mfa.yml` (also uses multi-line string fragments for `mvzip` / `split` delimiters—same newline issue)
- `endpoint/crowdstrike_falcon_stream_alerts.yml`
- `endpoint/linux_proxy_socks_curl.yml`
- `endpoint/powershell_4104_hunting.yml`
- `endpoint/regsvr32_*.yml`, `endpoint/wmi_*_event_subscription.yml`, `endpoint/windows_ad_*.yml` (rex / match patterns split across lines)
- `network/detect_snicat_sni_exfiltration.yml`
- `web/windows_exchange_autodiscover_ssrf_abuse.yml`

## Maintenance

Upstream may fix YAML formatting over time; re-run the scanner after major pulls. The optional pytest only checks that a configured tree is scannable and reports the invalid fraction—it does **not** require zero invalid searches.
