# Prompt Engineering Strategy for Test Case Generation

## Overview

This document outlines the prompt engineering approach for using an LLM to generate test cases for the TECU onboarding form. The strategy uses a structured schema as context and natural language prompts to generate executable CSV test cases.

---

## System Prompt Template

```
You are a test case generator for a web-based onboarding application. You have been provided with:

1. **Form Schema** (form_schema.json): Complete structure of all pages, sections, fields, and their XPaths
2. **Conditional Rules** (conditional_rules.json): Dependencies between fields and sections
3. **Example Test Cases**: Reference CSVs showing the exact output format

Your task is to generate valid, executable test case CSV files based on user requirements.

## Output Format

Generate a CSV with these exact columns:
- Column A: Sequential index (0, 1, 2, ...)
- Group: Page/section name from schema
- Element: Field ID or display name
- Action: "click" or "Input"
- Value: The value to input (empty for clicks)
- Strategy: Locator strategy (id, data-testid, absolute, etc.)
- XPath: The XPath from the schema

## Critical Rules

1. **Sequence Matters**: Actions must follow the page order defined in the schema
2. **Conditional Fields**: Only include fields that are visible based on the selected options
3. **Dropdown Pattern**: Always click dropdown trigger first, then click the option
4. **Boolean Pattern**: Use the correct XPath for true/false based on the selected value
5. **Repeatable Sections**: When multiple instances requested, include all required fields per instance
6. **OTP Fields**: Always use the default OTP value "121212" (split across 6 inputs)
7. **File Uploads**: Use the default file paths from global_rules

## Validation Checks Before Output

- All required fields for selected paths are included
- Conditional fields match their trigger conditions
- XPaths exist in the schema (never fabricate)
- Percentage fields sum to 100% where applicable
- Phone numbers match XXX-XXXX format
```

---

## Few-Shot Examples

### Example 1: Simple Flow (Single, Employed, No Optional Products)

**User Prompt:**
> Generate a test case for: Single male, full-time permanent employee at ABT Engineers, salary $15,000 annually, no beneficiaries, no joint partners, no LinCU card, no FIP application, all PEP/FATCA answers as No.

**Expected Output (abbreviated):**
```csv
,Group,Element,Action,Value,Strategy,XPath
0,Contact Info,firstName,click,,id,"//*[@id=""firstName""]"
1,Contact Info,firstName,Input,JOHN,id,"//*[@id=""firstName""]"
2,Contact Info,email,click,,id,"//*[@id=""email""]"
3,Contact Info,email,Input,john.doe@test.com,id,"//*[@id=""email""]"
...
54,Additional Details,Select Employment Status,click,,data-testid+text,"//*[@data-testid=""dropdown-text"" and contains(., ""Select Employment Status"")]"
55,Additional Details,FULL TIME PERMANENT,click,,data-testid,"//*[@data-testid=""option-0""]"
56,Additional Details,Select Employer,click,,data-testid+text,"//*[@data-testid=""dropdown-button"" and contains(., ""Select Employer"")]"
57,Additional Details,ABT ENGINEERS & CONSTRUCTORS L,click,,data-testid,"//*[@data-testid=""option-0""]"
...
101,Other Products,hasBeneficiary,click,,absolute,/html/body/.../label[2]/input[1]
102,Other Products,hasBeneficiary,Input,false,absolute,/html/body/.../label[2]/input[1]
103,Other Products,hasJointPartner,click,,absolute,/html/body/.../label[2]/input[1]
104,Other Products,hasJointPartner,Input,false,absolute,/html/body/.../label[2]/input[1]
...
```

---

### Example 2: Complex Flow (Married, With Beneficiaries and Joint Partner)

**User Prompt:**
> Generate a test case for: Married female, self-employed in private sector, salary over $27,000 monthly, 2 beneficiaries (spouse and son), 1 joint partner (existing member ID 121668), applying for LinCU card, NOT applying for FIP, permanent address different from mailing.

**Key Differences in Output:**
- `maritalStatus` = MARRIED
- `employmentStatus` = SELF EMPLOYED (no employer fields)
- `permanentAddressSameAsMailing` = false (triggers address fields)
- `hasBeneficiary` = true with 2 instances
- `hasJointPartner` = true with customer search
- `isApplyingForLincuCardApplication` = true
- `isApplyingForFipApplication` = false

---

### Example 3: Edge Case (Non-National, PEP Positive)

**User Prompt:**
> Generate a test case for: Non-Trinidad national (US Green Card holder), head of government official (PEP positive), retired pensioned, applying for FIP Plan B with 2 FIP beneficiaries.

**Key Differences:**
- `nationalOfTTPrimary` = false
- `nationalOfTTSecondary` = false
- `isGreenCardHolder` = true (FATCA trigger)
- `isHeadOfGovt` = true (PEP trigger)
- `employmentStatus` = RETIRED PENSIONED
- FIP section fully populated

---

## Prompt Patterns for Common Scenarios

### Pattern 1: Specifying Demographics
```
Gender: [male/female]
Marital Status: [single/married/divorced/widowed/common law/separated]
Nationality: [Trinidad and Tobago / Other - specify]
Education: [postgraduate/undergraduate/secondary/primary]
```

### Pattern 2: Employment Configuration
```
Employment Status: [full-time permanent / full-time temporary / part-time / self-employed / retired pensioned / retired non-pensioned / unemployed / other]
If employed:
  - Employer: [name from list or "any"]
  - Sector: [private/public/self-employed/others]
  - Employment Type: [agricultural/financial/manufacturing/professional/service]
  - Salary Range: [under 5k / 5k-12k / 12k-17k / 17k-22k / 22k-27k / over 27k]
  - Salary Frequency: [annually/monthly/biweekly/fortnightly/daily/hourly/quarterly]
```

### Pattern 3: Repeatable Sections
```
Beneficiaries: [0-8]
  For each: relation [brother/son/daughter/spouse/parent], document type [passport/NIC/DP]

Joint Partners: [0-3]
  For each: existing member ID, relation, document type

Dependents: [0-10]
  For each: is TECU member [yes/no], relation, document type
```

### Pattern 4: Product Applications
```
LinCU Card: [yes/no]
FIP Application: [yes/no]
  If yes: Plan [A/B/C], number of FIP beneficiaries [1-5]
Group Health: [yes/no]
  If yes: spouse covered by other plan [yes/no]
```

### Pattern 5: PEP/FATCA Declarations
```
PEP Status: [all no / specify which are yes]
  Options: head of state, head of govt, senior politician, senior govt official,
           senior judicial, senior military, senior exec SOC, important PPO,
           immediate family of PEP, senior management, PEP associate

FATCA Status: [all no / specify which are yes]
  Options: citizen of other country, green card holder, grantee POA,
           standing instructions, tax residency disclosure
```

---

## Advanced Prompting Techniques

### 1. Scenario-Based Generation
```
Generate a test case for the following business scenario:
"A retired teacher (pensioned) wants to open an account. She is widowed, has 3 adult children
who should be beneficiaries (equal split), and wants the LinCU card for convenience.
She does not want FIP or any health insurance products."
```

### 2. Edge Case Testing
```
Generate test cases for these edge cases:
1. Maximum beneficiaries (5) with unequal percentage split (40/30/15/10/5)
2. Joint partner who is also listed as a beneficiary
3. Self-employed person with salary under $5,000
4. All PEP questions answered "Yes"
```

### 3. Regression Test Suite
```
Generate a minimal test case that covers:
- All 5 pages navigated
- At least one dropdown selection per page
- At least one boolean toggle per page
- One file upload per document type
- Both OTP verifications
```

### 4. Negative Testing
```
Generate test cases with intentionally invalid data to verify form validation:
- Empty required fields
- Invalid phone format (missing hyphen)
- Invalid email format
- Beneficiary percentages that don't sum to 100
```

---

## Prompt Chaining Strategy

For complex test suites, use multi-turn conversations:

**Turn 1 - Establish Context:**
```
I'm going to ask you to generate multiple test cases for the TECU onboarding form.
First, confirm you understand the schema structure by listing:
1. The 6 page names in order
2. All repeatable sections
3. The employment status options
```

**Turn 2 - Generate Base Case:**
```
Generate Test Case 1: The "happy path" - simplest possible flow with all defaults
```

**Turn 3 - Generate Variations:**
```
Now generate Test Case 2: Same as Test Case 1 but with:
- Employment changed to SELF EMPLOYED
- Add 1 beneficiary (spouse)
```

**Turn 4 - Validate:**
```
Compare Test Case 1 and Test Case 2. List only the rows that are different.
```

---

## Error Prevention Prompts

### Prevent XPath Hallucination
```
IMPORTANT: Only use XPaths that exist in the provided schema.
If a field is requested that doesn't have an XPath in the schema,
respond with: "WARNING: No XPath found for field [field_name]. Skipping."
```

### Prevent Invalid Combinations
```
Before generating, validate these rules:
- If employmentStatus is UNEMPLOYED, do not include employer fields
- If permanentAddressSameAsMailing is true, do not include permanent address fields
- If hasBeneficiary is false, do not include any beneficiary fields
```

### Ensure Completeness
```
After generating, verify:
1. All required fields for each selected option are present
2. The sequence ends with the final OTP verification
3. Total row count is reasonable (typical range: 150-350 rows)
```

---

## Output Validation Checklist

The LLM should verify before returning:

- [ ] CSV starts with index 0
- [ ] All pages are represented in correct order
- [ ] Dropdown selections have both trigger click and option click
- [ ] Boolean fields have correct XPath for selected value
- [ ] File uploads use valid default file paths
- [ ] OTP sections have all 6 input fields plus verify button
- [ ] Conditional sections only appear when triggered
- [ ] No duplicate consecutive rows
- [ ] All XPaths come from the schema (no fabrication)

---

## Integration Notes

### Feeding Schema to LLM

Due to token limits, consider:
1. **Chunking**: Feed schema page-by-page for complex generations
2. **Summarization**: Create a compressed schema with only IDs and key rules
3. **RAG**: Store schema in vector DB, retrieve relevant sections based on prompt

### Post-Processing Pipeline

```
User Prompt → LLM Generation → Schema Validation → XPath Verification → CSV Output
```

Implement validators that:
1. Parse generated CSV
2. Check each element against schema
3. Verify XPath existence
4. Validate conditional logic
5. Flag errors before test execution
