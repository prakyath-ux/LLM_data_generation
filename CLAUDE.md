# LLM Test Case Generator - Project Status

## Current Stage: POC Complete

**Date:** February 2, 2026
**Version:** 4.1
**Status:** Proof of Concept Validated

---

## Metrics Summary

### Test Coverage

| Scenario | Description | Structural | Semantic | Status |
|----------|-------------|------------|----------|--------|
| 1 | Single male, full-time permanent | Pass | Pass | Validated |
| 2 | Single female, self-employed, 1 beneficiary, LinCU | Pass | Pass | Validated |
| 3 | Married male, part-time, 2 beneficiaries | Pass | Pass | Validated |
| 4 | Married female, full-time, 2 beneficiaries, joint partner, FIP | Pass | Pass | Validated |
| 5 | Single male, unemployed | Pass | Pass | Validated |

**Total Validated Scenarios:** 5/5 (100%)

### Cost Metrics

| Metric | Value |
|--------|-------|
| Average cost per generation | ~$0.06 - $0.11 |
| Context tokens (input) | ~16,000 - 18,500 |
| Output tokens (generated CSV) | ~2,000 - 6,600 |
| Model used | GPT-4o |

### Generation Performance

| Metric | Value |
|--------|-------|
| Average rows per test case | 133 - 177 |
| Pages covered | 6/6 (100%) |
| OTP verifications | 4 (exceeds minimum of 2) |

---

## Known Warnings (Non-blocking)

| Warning | Explanation | Impact |
|---------|-------------|--------|
| Beneficiary count 2× expected | Counts click + Input rows | None - correct behavior |
| Empty Input value | Row numbering offset | False positive |
| fipPlan may be required | Reminder check when FIP enabled | None |

---

## Project Structure

```
test_case_generation/
├── config/                 # Schema and rules
│   ├── form_schema.json
│   └── conditional_rules.json
├── data/                   # Reference data
│   ├── examples/
│   └── scenarios/
├── docs/                   # Documentation
├── notebooks/              # Analysis notebooks
├── output/                 # Generated files
│   ├── logs/
│   └── test_cases/
├── src/                    # Source code
│   ├── generate_test_case.py
│   └── validators/
│       ├── validator.py
│       └── scenario_validator.py
├── .env                    # API keys
├── requirements.txt
└── README.md
```

---

## Quick Commands

```bash
# Generate test case (interactive)
python3 src/generate_test_case.py -i

# Generate single scenario
python3 src/generate_test_case.py "your scenario"

# Validate structure
python3 src/validators/validator.py "output/test_cases/FILE.csv"

# Validate scenario
python3 src/validators/scenario_validator.py "output/test_cases/FILE.csv" "scenario text"
```

---

## What's Working

- LLM-powered test case generation from natural language
- Two-stage validation (structural + semantic)
- Cost tracking with session logs
- Clean project structure
- Consistent CSV output format
- Correct conditional logic application

## Next Steps (Future)

- [ ] Batch generation from scenario matrix
- [ ] Selenium/Playwright direct execution
- [ ] Web UI for non-technical users
- [ ] CI/CD pipeline integration
- [ ] Beneficiary count validation fix (divide by 2)
- [ ] Ctrl+C graceful exit with log saving

---

*Last Updated: February 2, 2026*
