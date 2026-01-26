# Sample Logs README

This directory contains sample log files in various formats for testing and demonstration.

## Files

| File | Format | Description |
|------|--------|-------------|
| `sample_logs.json` | JSON | Mixed classification samples with metadata |
| `cef_logs.txt` | CEF | Common Event Format logs for SIEM testing |
| `leef_logs.txt` | LEEF | Log Event Extended Format for IBM QRadar |

## Log Formats

### JSON Format
Standard JSON with fields: `id`, `timestamp`, `source`, `category`, `message`, `format`, `expected_classification`

### CEF (Common Event Format)
```
CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
```

### LEEF (Log Event Extended Format)
```
LEEF:Version|Vendor|Product|Version|EventID|Key=Value pairs
```

## Classification Categories

- **critical**: Immediate security threats requiring urgent attention
- **suspicious**: Unusual activity warranting investigation
- **routine**: Normal operational logs with forensic value
- **noise**: Low-value logs that can be filtered
- **bypass_compliance**: Regulated logs that bypass AI (PCI-DSS, HIPAA, etc.)

## Usage

```python
import json

# Load sample logs
with open("data/samples/sample_logs.json") as f:
    samples = json.load(f)

for log in samples:
    print(f"{log['id']}: {log['expected_classification']}")
```
