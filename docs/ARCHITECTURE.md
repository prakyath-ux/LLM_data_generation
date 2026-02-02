# LLM-Based Test Case Generation System

## Complete Architecture & Documentation

---

## 1. THE PROBLEM WE SOLVED

### Original Challenge
You have an onboarding web form with:
- **5-6 pages** (Contact Info → Documents → Additional Details → Other Products → PEP/FATCA → PDF)
- **15+ binary Yes/No fields** → 2^15 = 32,768 combinations
- **Multiple dropdowns** (Employment: 8 options, Salary: 6 options, etc.) → multiplicative
- **Repeatable sections** (0-8 beneficiaries, 0-3 joint partners, 0-10 dependents)

**Result**: Millions of possible test paths. Manual test case creation is impossible.

### Our Solution
Use an **LLM (GPT-4o)** as a "test case composer" that:
1. Understands the form structure from a schema
2. Knows the conditional logic (if X, then show Y)
3. Generates specific test cases from natural language prompts
4. Outputs executable CSV files for automation

---

## 2. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER WORKFLOW                                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. DESCRIBE SCENARIO (Natural Language)                            │
│     "Single male, full-time employed, no beneficiaries, no FIP"     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. GENERATE TEST CASE (generate_test_case.py)                      │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │ form_schema │ + │ conditional │ + │ example_csv │ = CONTEXT     │
│  │   .json     │   │ _rules.json │   │             │   (~16K tokens)│
│  └─────────────┘   └─────────────┘   └─────────────┘               │
│         │                 │                 │                        │
│         └─────────────────┴─────────────────┘                        │
│                           │                                          │
│                           ▼                                          │
│                    ┌─────────────┐                                   │
│                    │   GPT-4o    │                                   │
│                    │   API Call  │                                   │
│                    └─────────────┘                                   │
│                           │                                          │
│                           ▼                                          │
│                    ┌─────────────┐                                   │
│                    │  Raw CSV    │                                   │
│                    │  Output     │                                   │
│                    └─────────────┘                                   │
│                           │                                          │
│                           ▼                                          │
│                    ┌─────────────┐                                   │
│                    │ fix_csv_    │  (Fix comma quoting issues)       │
│                    │ quoting()   │                                   │
│                    └─────────────┘                                   │
│                           │                                          │
│                           ▼                                          │
│                    ┌─────────────┐                                   │
│                    │ Save to     │                                   │
│                    │ generated/  │                                   │
│                    └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. VALIDATE (Two-Stage)                                            │
│                                                                      │
│  ┌─────────────────────┐    ┌─────────────────────┐                │
│  │   validator.py      │    │ scenario_validator  │                │
│  │   (Structural)      │    │      .py            │                │
│  │                     │    │   (Semantic)        │                │
│  │ • CSV format OK?    │    │                     │                │
│  │ • Columns exist?    │    │ • Matches prompt?   │                │
│  │ • XPaths valid?     │    │ • Employment OK?    │                │
│  │ • Page order OK?    │    │ • Beneficiaries?    │                │
│  └─────────────────────┘    │ • LinCU/FIP flags?  │                │
│                             │ • PEP/FATCA = No?   │                │
│                             └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. EXECUTE (Your Automation Framework)                             │
│     Selenium / Playwright reads CSV and performs actions            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. FILE STRUCTURE & PURPOSE

```
version4.1/schema/
├── form_schema.json          # 🔵 CORE: Form structure (pages, fields, XPaths)
├── conditional_rules.json    # 🔵 CORE: Business logic (if X then Y)
├── generate_test_case.py     # 🟢 MAIN: LLM integration script
├── validator.py              # 🟡 VALIDATION: CSV structure checker
├── scenario_validator.py     # 🟡 VALIDATION: Requirement matcher
├── prompt_engineering_strategy.md  # 📚 DOCS: Prompting guide
├── requirements.txt          # 📦 Dependencies
├── README.md                 # 📚 Quick reference
├── ARCHITECTURE.md           # 📚 This file
├── examples/
│   └── simple_flow_example.csv    # 📋 Reference test case (154 rows)
└── generated/
    ├── *.csv                 # 📋 Generated test cases
    └── cost_log.json         # 💰 API cost tracking
```

---

## 4. DETAILED CODE FLOW

### Step 1: Load Context
```python
# generate_test_case.py
schema = load_json("form_schema.json")      # ~8,800 tokens
rules = load_json("conditional_rules.json")  # ~1,700 tokens
example_csv = load_file("examples/simple_flow_example.csv")  # ~4,600 tokens
# Total context: ~16,000 tokens
```

### Step 2: Build System Prompt
```python
system_prompt = f"""
You are a test case generator...

## FORM SCHEMA
{json.dumps(schema)}

## CONDITIONAL RULES
{json.dumps(rules)}

## EXAMPLE CSV
{example_csv}

Output ONLY CSV content...
"""
```

### Step 3: Call GPT-4o API
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate test case for: {scenario}"}
    ],
    temperature=0.2,  # Low for consistency
    max_tokens=16000  # Enough for ~400 rows
)
```

### Step 4: Fix CSV Quoting
```python
# Problem: GPT might output "$12,001-$17,000" without quotes
# Solution: Parse and re-quote with Python's csv module
content = fix_csv_quoting(response.content)
```

### Step 5: Save & Track Costs
```python
# Save CSV
filepath = save_test_case(content, scenario_name)

# Log costs
session.add_call(usage_stats, scenario)
save_cost_log(session, output_dir)
```

---

## 5. KEY DATA STRUCTURES

### form_schema.json Structure
```json
{
  "pages": [
    {
      "id": "contact_info",
      "name": "Contact Info",
      "order": 1,
      "sections": [
        {
          "id": "basic_info",
          "fields": [
            {
              "id": "firstName",
              "type": "text",
              "required": true,
              "strategy": "id",
              "xpath": "//*[@id=\"firstName\"]"
            },
            {
              "id": "employmentStatus",
              "type": "dropdown",
              "options": [
                {"value": "FULL TIME PERMANENT", "xpath": "..."},
                {"value": "SELF EMPLOYED", "xpath": "..."}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### conditional_rules.json Structure
```json
{
  "dependency_rules": [
    {
      "rule_id": "R003",
      "name": "Employed Status Fields",
      "trigger_field": "employmentStatus",
      "trigger_values": ["FULL TIME PERMANENT", "PART TIME"],
      "required_fields": ["employer", "employerCity", "workPhoneNo"],
      "excluded_fields": []
    },
    {
      "rule_id": "R006",
      "name": "Beneficiary Section",
      "trigger_field": "hasBeneficiary",
      "trigger_value": true,
      "required_fields_per_instance": ["beneficiaryMobileNo", "beneficiaryRelation"]
    }
  ],
  "repeatable_section_rules": {
    "beneficiary": {"min": 0, "max": 8},
    "joint_partner": {"min": 0, "max": 3}
  }
}
```

### Generated CSV Structure
```csv
,Group,Element,Action,Value,Strategy,XPath
0,Contact Info,firstName,click,,id,"//*[@id=""firstName""]"
1,Contact Info,firstName,Input,JOHN,id,"//*[@id=""firstName""]"
2,Contact Info,email,click,,id,"//*[@id=""email""]"
3,Contact Info,email,Input,john@test.com,id,"//*[@id=""email""]"
...
```

---

## 6. VALIDATION LOGIC

### Structural Validator (validator.py)
```python
# Checks:
1. CSV has required columns (Group, Element, Action, Value, Strategy, XPath)
2. Actions are "click" or "Input"
3. XPaths start with "/"
4. Pages appear in correct order
5. Basic conditional logic (if hasBeneficiary=false, no beneficiary fields)
```

### Scenario Validator (scenario_validator.py)
```python
# Parses natural language scenario:
"Single male, full-time permanent, no beneficiaries"
     ↓
ScenarioRequirements(
    gender="male",
    marital_status="SINGLE",
    employment_status="FULL TIME PERMANENT",
    has_beneficiary=False
)

# Then validates CSV against these requirements:
- Does CSV have employmentStatus = "FULL TIME PERMANENT"? ✅
- Does CSV have maritalStatus = "SINGLE"? ✅
- Does CSV have hasBeneficiary = false? ✅
```

### Boolean Detection from XPath
```python
# Problem: CSV might only have click action, not Input
# Solution: Detect from XPath pattern

# label[1] in XPath → True/Yes
# label[2] in XPath → False/No

xpath = "/html/.../label[2]/input[1]"  # This means FALSE
```

---

## 7. COST TRACKING

### Per-Call Tracking
```python
# GPT-4o Pricing (Jan 2025)
Input:  $2.50 / 1M tokens
Output: $10.00 / 1M tokens

# Typical call:
Prompt tokens:     ~16,000  →  $0.04
Completion tokens: ~2,000   →  $0.02
Total per call:              ~$0.06
```

### Session Summary
```
============================================================
SESSION SUMMARY
============================================================
Total API Calls:      5
Total Prompt Tokens:  80,000
Total Output Tokens:  10,000
Total Cost:           $0.30
============================================================
```

---

## 8. FILES TO STUDY (In Order)

### Priority 1: Core Logic
| File | What You'll Learn |
|------|-------------------|
| `form_schema.json` | How form structure is represented (pages, fields, XPaths, options) |
| `conditional_rules.json` | How business rules are encoded (dependencies, triggers) |
| `generate_test_case.py` | Main orchestration: loading context, calling API, saving output |

### Priority 2: Validation
| File | What You'll Learn |
|------|-------------------|
| `scenario_validator.py` | Natural language parsing, requirement extraction, CSV checking |
| `validator.py` | Structural validation, XPath checking, page order |

### Priority 3: Reference & Docs
| File | What You'll Learn |
|------|-------------------|
| `examples/simple_flow_example.csv` | Exact CSV format expected |
| `prompt_engineering_strategy.md` | How to write effective prompts |
| `README.md` | Quick reference for usage |

---

## 9. COMMANDS CHEAT SHEET

```bash
# Navigate to schema directory
cd /Users/impactoinfra/test_case_generation/version4.1/schema

# Estimate cost without API call
python generate_test_case.py --estimate-only

# Generate with specific scenario
python generate_test_case.py "Single male, full-time, no beneficiaries"

# Interactive mode
python generate_test_case.py -i

# Use cheaper model
python generate_test_case.py -m gpt-4o-mini "your scenario"

# Structural validation
python validator.py generated/test.csv form_schema.json conditional_rules.json

# Scenario validation
python scenario_validator.py generated/test.csv "your scenario description"

# Check cost log
cat generated/cost_log.json
```

---

## 10. WHAT WE ACCOMPLISHED

| Component | Status | Purpose |
|-----------|--------|---------|
| Form Schema | ✅ Built | Captures all pages, fields, XPaths, options |
| Conditional Rules | ✅ Built | Encodes 12+ business rules |
| LLM Integration | ✅ Built | GPT-4o API with full context |
| Cost Tracking | ✅ Built | Token counting, session totals, JSON log |
| CSV Fix | ✅ Built | Auto-fixes comma quoting issues |
| Structural Validator | ✅ Built | Checks CSV format validity |
| Scenario Validator | ✅ Built | Matches CSV to requirements |
| Example CSV | ✅ Created | 154-row reference for few-shot learning |

### End-to-End Flow Working
```
Prompt → GPT-4o → CSV → Validation → Ready for Automation
```

---

## 11. NEXT STEPS (Future Enhancements)

1. **Batch Generation**: Generate 10+ test cases from a scenario matrix
2. **Selenium/Playwright Integration**: Execute CSVs automatically
3. **RAG System**: Vector DB for schema retrieval (if context grows)
4. **Web UI**: Simple interface for QA team to generate tests
5. **CI/CD Integration**: Auto-generate regression tests on PR
