# LLM-Based Test Case Generation System

## Overview

This system uses an LLM (Large Language Model) to generate executable test case CSVs for the TECU onboarding form. Instead of enumerating millions of possible combinations, QA teams can describe test scenarios in natural language and receive valid, structured test cases.

## Directory Structure

```
schema/
├── README.md                      # This file
├── form_schema.json               # Hierarchical form structure with XPaths
├── conditional_rules.json         # Field dependencies and business rules
├── prompt_engineering_strategy.md # Detailed prompting guide
├── validator.py                   # Python validation script
└── examples/
    └── simple_flow_example.csv    # Reference test case
```

## Quick Start

### 1. Feed Context to LLM

Provide the LLM with:
- `form_schema.json` (or relevant sections)
- `conditional_rules.json`
- One example CSV from `examples/`

### 2. Use Natural Language Prompts

```
Generate a test case for:
- Single male, 35 years old
- Full-time permanent at ABT Engineers
- Private sector, Professional/Technical
- Salary $15,000 annually
- No beneficiaries, no joint partners
- Not applying for LinCU or FIP
- All PEP/FATCA as No
```

### 3. Validate Output

```bash
python validator.py generated_test.csv form_schema.json conditional_rules.json
```

## Prompt Templates

### Basic Demographics
```
Gender: male/female
Marital Status: single/married/divorced/widowed
Age: [number]
Nationality: Trinidad and Tobago / [Other]
```

### Employment
```
Employment Status: FULL TIME PERMANENT
Employer: ABT ENGINEERS & CONSTRUCTORS L
Sector: PRIVATE SECTOR
Type: Professional/Technical
Salary Range: $12,001-$17,000
Frequency: ANNUALLY
```

### Optional Products
```
Beneficiaries: 0 (none) / 1-5 (with relations)
Joint Partners: 0 (none) / 1-3 (with member IDs)
LinCU Card: yes/no
FIP Application: yes/no (if yes, specify plan)
Group Health: yes/no
```

### PEP/FATCA
```
PEP Status: all no / [specify which are yes]
FATCA Status: all no / [specify which are yes]
```

## Schema Reference

### Pages (in order)
1. **Contact Info** - Name, email, phone, branch, OTP
2. **Documents** - ID uploads, utility bill, address
3. **Additional Details** - Employment, income, nationality
4. **Other Products** - Beneficiaries, joint partners, cards
5. **PEP / FATCA** - Compliance declarations
6. **PDF / Other Details** - Document uploads, final OTP

### Key Boolean Fields (triggers conditional sections)
| Field | When TRUE shows |
|-------|-----------------|
| `permanentAddressSameAsMailing` | (hides address fields) |
| `utilityDocOption` | (hides authorization upload) |
| `hasBeneficiary` | Beneficiary details section |
| `hasJointPartner` | Joint partner search/details |
| `isApplyingForFipApplication` | FIP plan selection |
| `groupHealth` | Health insurance details |
| `addDependent` | Dependent details |

### Repeatable Sections
| Section | Min | Max | Key Fields |
|---------|-----|-----|------------|
| Beneficiary | 0 | 5 | relation, document, mobile |
| Joint Partner | 0 | 3 | member ID, relation, document |
| Dependent | 0 | 10 | TECU member status, document |
| FIP Beneficiary | 1 | 5 | percentage (must sum to 100%) |

## CSV Output Format

```csv
,Group,Element,Action,Value,Strategy,XPath
0,Contact Info,firstName,click,,id,"//*[@id=""firstName""]"
1,Contact Info,firstName,Input,JOHN,id,"//*[@id=""firstName""]"
```

### Column Definitions
| Column | Description |
|--------|-------------|
| (index) | Sequential row number starting at 0 |
| Group | Page/section name |
| Element | Field ID or button text |
| Action | `click` or `Input` |
| Value | Input value (empty for clicks) |
| Strategy | Locator type (id, data-testid, absolute, etc.) |
| XPath | Full XPath expression |

## Validation Rules

The validator checks:
- CSV structure and required columns
- Action values (click/Input only)
- Page sequence order
- Conditional logic compliance
- Phone format (XXX-XXXX)
- Email format

## Common Scenarios

### Scenario 1: Minimal Happy Path
```
Single, employed full-time, no optional products, all PEP/FATCA no
→ ~150 rows
```

### Scenario 2: With Beneficiaries
```
Married, 2 beneficiaries (spouse 60%, child 40%), LinCU card
→ ~200 rows
```

### Scenario 3: Complex Full Flow
```
Multiple beneficiaries, joint partner, FIP application,
different mailing/permanent address, some PEP flags
→ ~300+ rows
```

## Troubleshooting

### "XPath not found in schema"
The schema may not cover all elements. Check `All_elements_flow.csv` for the actual XPath.

### "Conditional field appears without trigger"
Verify the boolean trigger field was set correctly before the conditional fields appear.

### "Page sequence error"
Ensure pages appear in order: Contact Info → Documents → Additional Details → Other Products → PEP/FATCA → PDF/Other Details

## Future Enhancements

1. **RAG Integration** - Vector database for schema retrieval
2. **Auto-completion** - Suggest missing fields based on selections
3. **Visual Diff** - Compare generated vs reference test cases
4. **Batch Generation** - Generate multiple test cases from scenario matrix
