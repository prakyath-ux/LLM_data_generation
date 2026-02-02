#!/usr/bin/env python3
"""
Test Case Generator using OpenAI GPT-4o

Generates executable test case CSVs from natural language descriptions.
Uses the form schema and conditional rules as context.

Features:
- Token counting and cost tracking
- Session cost accumulation
- Detailed usage logging
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# Configuration - paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent  # /test_case_generation/
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output" / "test_cases"
LOGS_DIR = PROJECT_ROOT / "output" / "logs"

SCHEMA_FILE = CONFIG_DIR / "form_schema.json"
RULES_FILE = CONFIG_DIR / "conditional_rules.json"
EXAMPLE_FILE = DATA_DIR / "examples" / "simple_flow_example.csv"

# GPT-4o Pricing 
# https://openai.com/pricing
PRICING = {
    "gpt-4o": {
        "input": 2.50 / 1_000_000,   # $2.50 per 1M input tokens
        "output": 10.00 / 1_000_000,  # $10.00 per 1M output tokens
    },
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,   # $0.15 per 1M input tokens
        "output": 0.60 / 1_000_000,  # $0.60 per 1M output tokens
    },
}


@dataclass
class UsageStats:
    """Track token usage and costs."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0


@dataclass
class SessionStats:
    """Track cumulative session statistics."""
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost: float = 0.0
    call_history: list = field(default_factory=list)

    def add_call(self, usage: UsageStats, scenario: str):
        """Add a call's usage to session totals."""
        self.total_calls += 1
        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.total_cost += usage.total_cost
        self.call_history.append({
            "timestamp": datetime.now().isoformat(),
            "scenario": scenario[:50],
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost": usage.total_cost
        })

    def print_summary(self):
        """Print session summary."""
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"Total API Calls:      {self.total_calls}")
        print(f"Total Prompt Tokens:  {self.total_prompt_tokens:,}")
        print(f"Total Output Tokens:  {self.total_completion_tokens:,}")
        print(f"Total Tokens:         {self.total_prompt_tokens + self.total_completion_tokens:,}")
        print(f"Total Cost:           ${self.total_cost:.4f}")
        print("=" * 60)


def calculate_cost(usage, model: str = "gpt-4o") -> UsageStats:
    """Calculate costs from API usage response."""
    pricing = PRICING.get(model, PRICING["gpt-4o"])

    stats = UsageStats(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        input_cost=usage.prompt_tokens * pricing["input"],
        output_cost=usage.completion_tokens * pricing["output"],
    )
    stats.total_cost = stats.input_cost + stats.output_cost
    return stats


def print_usage(stats: UsageStats, model: str = "gpt-4o"):
    """Print detailed usage information."""
    print("\n" + "-" * 50)
    print("TOKEN USAGE & COST")
    print("-" * 50)
    print(f"Model:            {model}")
    print(f"Prompt Tokens:    {stats.prompt_tokens:,}")
    print(f"Completion Tokens:{stats.completion_tokens:,}")
    print(f"Total Tokens:     {stats.total_tokens:,}")
    print("-" * 50)
    print(f"Input Cost:       ${stats.input_cost:.6f}")
    print(f"Output Cost:      ${stats.output_cost:.6f}")
    print(f"TOTAL COST:       ${stats.total_cost:.6f}")
    print("-" * 50)


def load_file(path: str) -> str:
    """Load file contents as string."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_json(path: str) -> dict:
    """Load and parse JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count (avg 4 chars per token)."""
    return len(text) // 4


def build_system_prompt(schema: dict, rules: dict, example_csv: str) -> str:
    """Build the system prompt with FULL context (no truncation)."""

    return f"""You are a test case generator for a web-based onboarding application. Your task is to generate valid, executable test case CSV files based on user requirements.

## FORM STRUCTURE OVERVIEW
The form has these pages in order:
1. Contact Info - Name, email, phone, branch selection, OTP verification
2. Documents - ID uploads (Passport/NIC/DP), utility bill, address
3. Additional Details - Employment, income, nationality, marital status
4. Other Products - Beneficiaries, joint partners, LinCU card, FIP, health insurance
5. PEP / FATCA - Political exposure and tax compliance declarations (16 boolean questions)
6. PDF / Other Details - Document uploads, final OTP

## OUTPUT FORMAT
Generate a CSV with these exact columns:
- First column: Sequential index starting at 0
- Group: Page/section name
- Element: Field ID or button text (QUOTE with double quotes if contains commas, e.g., "$12,001-$17,000")
- Action: "click" or "Input"
- Value: The value to input (QUOTE with double quotes if contains commas)
- Strategy: Locator strategy (id, data-testid, data-testid+text, absolute, name, class)
- XPath: The XPath expression (already quoted)

IMPORTANT: Any field containing commas MUST be wrapped in double quotes. Example:
60,Additional Details,"$12,001-$17,000",click,,data-testid,"//*[@data-testid=""option-0""]"

## CRITICAL RULES
1. **Sequence**: Follow page order strictly (Contact Info → Documents → Additional Details → Other Products → PEP/FATCA → PDF/Other Details)
2. **Dropdowns**: Always click trigger FIRST, then click the option
3. **Booleans**: Use correct XPath for true vs false (they have DIFFERENT XPaths!)
4. **Conditionals**: Only include fields that would be VISIBLE based on selections
5. **OTP**: Always use "121212" split as 1,2,1,2,1,2 across 6 inputs
6. **No fabrication**: ONLY use XPaths from the schema or example below - NEVER invent XPaths

## REPEATABLE SECTIONS
- Beneficiaries: 0-8 instances (each needs: document type, mobile, relation, upload)
- Joint Partners: 0-3 instances (each needs: member ID search, relation, document)
- Dependents: 0-10 instances (each needs: TECU member status, document type, upload)
- For percentages (beneficiary/FIP): Must sum to 100%

## COMPLETE CONDITIONAL RULES
{json.dumps(rules, indent=2)}

## COMPLETE FORM SCHEMA (All pages, fields, XPaths)
{json.dumps(schema, indent=2)}

## COMPLETE REFERENCE EXAMPLE (Simple flow - 154 rows)
This shows the exact format to follow:
```csv
{example_csv}
```

## GENERATION INSTRUCTIONS
When generating, think through:
1. What employment status? → Determines which employer fields to include/exclude
2. What boolean selections? → Determines which conditional sections appear
3. How many repeatable instances? → Determines how many beneficiary/partner/dependent blocks
4. Match XPaths EXACTLY from schema or example above

Output ONLY the CSV content. Start directly with the header row. No markdown code blocks, no explanations before or after.
"""


def generate_test_case(
    client: OpenAI,
    system_prompt: str,
    user_scenario: str,
    model: str = "gpt-4o",
    session: Optional[SessionStats] = None
) -> tuple[str, UsageStats]:
    """
    Call GPT-4o to generate a test case.

    Returns:
        Tuple of (csv_content, usage_stats)
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Generate a complete test case CSV for the following scenario:

{user_scenario}

Output ONLY the CSV content. Start directly with the header row. No markdown code blocks, no explanations."""}
        ],
        temperature=0.2,  # Low temperature for consistency
        max_tokens=16000,  # Enough for ~400 rows
    )

    # Calculate usage and cost
    usage_stats = calculate_cost(response.usage, model)

    # Print usage
    print_usage(usage_stats, model)

    # Add to session if tracking
    if session:
        session.add_call(usage_stats, user_scenario)

    return response.choices[0].message.content, usage_stats


def fix_csv_quoting(csv_content: str) -> str:
    """
    Fix CSV quoting issues in LLM-generated content.
    Ensures fields with commas are properly quoted.
    """
    import csv
    import io

    lines = csv_content.strip().split('\n')
    if not lines:
        return csv_content

    # Parse and re-write with proper quoting
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    for line in lines:
        # Try to parse each line, handling various edge cases
        # First, try simple split (works for well-formed lines)
        parts = []
        in_quotes = False
        current = ""

        i = 0
        while i < len(line):
            char = line[i]

            if char == '"':
                # Handle escaped quotes ""
                if i + 1 < len(line) and line[i + 1] == '"':
                    current += '"'
                    i += 2
                    continue
                else:
                    in_quotes = not in_quotes
                    i += 1
                    continue
            elif char == ',' and not in_quotes:
                parts.append(current)
                current = ""
            else:
                current += char
            i += 1

        parts.append(current)  # Add last field

        # Ensure we have exactly 7 columns (index, Group, Element, Action, Value, Strategy, XPath)
        if len(parts) >= 7:
            # Take first 4 fields as-is, then Value (may have commas), Strategy, XPath
            # Reconstruct: sometimes the Element or Value field has commas
            if len(parts) > 7:
                # Try to identify which field has the extra commas
                # Usually it's the Element (col 2) or Value (col 4) field
                # XPath is always last and Strategy is second-to-last
                xpath = parts[-1]
                strategy = parts[-2]

                # First 2 columns (index, Group) are usually clean
                index = parts[0]
                group = parts[1]

                # Action is usually 'click' or 'Input' - find it
                action_idx = -1
                for idx in range(2, len(parts) - 2):
                    if parts[idx] in ('click', 'Input'):
                        action_idx = idx
                        break

                if action_idx > 0:
                    # Element is everything between Group and Action
                    element = ','.join(parts[2:action_idx])
                    action = parts[action_idx]
                    # Value is everything between Action and Strategy
                    value = ','.join(parts[action_idx + 1:-2])
                    parts = [index, group, element, action, value, strategy, xpath]
                else:
                    # Fallback: just take first 7
                    parts = parts[:7]

        writer.writerow(parts)

    return output.getvalue()


def save_test_case(csv_content: str, scenario_name: str) -> str:
    """Save generated CSV to file."""

    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in scenario_name[:30])
    filename = f"{safe_name}_{timestamp}.csv"
    filepath = OUTPUT_DIR / filename

    # Clean up content (remove markdown code blocks if present)
    content = csv_content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    # Fix CSV quoting issues
    content = fix_csv_quoting(content)

    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return str(filepath)


def save_cost_log(session: SessionStats):
    """Save cost log to JSON file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "cost_log.json"

    # Load existing log if present
    existing = []
    if log_file.exists():
        with open(log_file, 'r') as f:
            existing = json.load(f)

    # Append new session
    existing.append({
        "session_start": session.call_history[0]["timestamp"] if session.call_history else datetime.now().isoformat(),
        "total_calls": session.total_calls,
        "total_prompt_tokens": session.total_prompt_tokens,
        "total_completion_tokens": session.total_completion_tokens,
        "total_cost": session.total_cost,
        "calls": session.call_history
    })

    # Save
    with open(log_file, 'w') as f:
        json.dump(existing, f, indent=2)

    print(f"\nCost log saved to: {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate test cases using GPT-4o")
    parser.add_argument("scenario", nargs="?", help="Test scenario description")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate after generation")
    parser.add_argument("--model", "-m", default="gpt-4o", choices=["gpt-4o", "gpt-4o-mini"],
                        help="Model to use (default: gpt-4o)")
    parser.add_argument("--estimate-only", "-e", action="store_true",
                        help="Only estimate cost without making API call")
    args = parser.parse_args()

    # Load environment variables from .env file
    env_paths = [
        Path(__file__).parent.parent.parent / ".env",  # /test_case_generation/.env
        Path(__file__).parent / ".env",  # /schema/.env
        Path.cwd() / ".env",  # current directory
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded environment from: {env_path}")
            break

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found")
        print("\nSet it in .env file or export it:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        return 1

    # Load context files
    try:
        schema = load_json(SCHEMA_FILE)
        rules = load_json(RULES_FILE)
        example_csv = load_file(EXAMPLE_FILE)
    except FileNotFoundError as e:
        print(f"Error: Required file not found: {e.filename}")
        return 1

    # Build system prompt
    system_prompt = build_system_prompt(schema, rules, example_csv)

    # Estimate prompt size
    estimated_tokens = estimate_tokens(system_prompt)
    pricing = PRICING[args.model]
    estimated_input_cost = estimated_tokens * pricing["input"]

    print("\n" + "=" * 60)
    print("CONTEXT SIZE ESTIMATE")
    print("=" * 60)
    print(f"System Prompt:     {len(system_prompt):,} characters")
    print(f"Estimated Tokens:  ~{estimated_tokens:,} tokens")
    print(f"Model:             {args.model}")
    print(f"Est. Input Cost:   ~${estimated_input_cost:.4f} per call")
    print("=" * 60)

    if args.estimate_only:
        print("\n--estimate-only flag set. Exiting without API call.")
        return 0

    # Initialize client and session tracker
    client = OpenAI(api_key=api_key)
    session = SessionStats()

    # Get scenario
    if args.interactive:
        print("\n" + "="*60)
        print("TEST CASE GENERATOR - Interactive Mode")
        print("="*60)
        print(f"\nUsing model: {args.model}")
        print("\nDescribe your test scenario. Examples:")
        print("  - Single male, employed full-time, no optional products")
        print("  - Married, 2 beneficiaries, applying for LinCU card")
        print("  - Self-employed, different permanent address, FIP Plan A")
        print("\nCommands: 'quit' to exit, 'cost' for session summary\n")

        while True:
            scenario = input("Scenario> ").strip()

            if scenario.lower() in ('quit', 'exit', 'q'):
                break
            if scenario.lower() == 'cost':
                session.print_summary()
                continue
            if not scenario:
                continue

            print("\nGenerating test case...")
            try:
                csv_content, usage = generate_test_case(
                    client, system_prompt, scenario,
                    model=args.model, session=session
                )
                filepath = save_test_case(csv_content, scenario)

                # Count rows
                row_count = len(csv_content.strip().split('\n')) - 1
                print(f"\nGenerated: {filepath}")
                print(f"Rows: {row_count}")

                if args.validate:
                    print("\nValidating...")
                    os.system(f"python {PROJECT_ROOT}/src/validators/validator.py {filepath} {SCHEMA_FILE} {RULES_FILE}")

            except Exception as e:
                print(f"Error: {e}")

            print()

        # Print session summary and save log
        if session.total_calls > 0:
            session.print_summary()
            save_cost_log(session)

    elif args.scenario:
        print(f"\nGenerating test case for: {args.scenario}")
        try:
            csv_content, usage = generate_test_case(
                client, system_prompt, args.scenario,
                model=args.model, session=session
            )
            filepath = save_test_case(csv_content, args.scenario)

            row_count = len(csv_content.strip().split('\n')) - 1
            print(f"\nGenerated: {filepath}")
            print(f"Rows: {row_count}")

            if args.validate:
                print("\nValidating...")
                os.system(f"python {PROJECT_ROOT}/src/validators/validator.py {filepath} {SCHEMA_FILE} {RULES_FILE}")

            # Save cost log
            save_cost_log(session)

        except Exception as e:
            print(f"Error: {e}")
            return 1

    else:
        # Default demo scenario
        demo_scenario = """
        Single male, 30 years old
        Full-time permanent employee at ABT Engineers
        Private sector, Professional/Technical field
        Salary $15,000 annually, paid via salary
        Trinidad and Tobago national
        Postgraduate education
        Communication preference: Email
        No beneficiaries
        No joint partners
        Not applying for LinCU card
        Not applying for FIP
        No recommender
        Permanent address same as mailing
        Utility document in applicant's name
        All PEP questions: No
        All FATCA questions: No
        """

        print("\nNo scenario provided. Running demo...")
        print(f"Demo scenario: Simple employed male, no optional products\n")

        try:
            csv_content, usage = generate_test_case(
                client, system_prompt, demo_scenario,
                model=args.model, session=session
            )
            filepath = save_test_case(csv_content, "demo_simple_flow")

            row_count = len(csv_content.strip().split('\n')) - 1
            print(f"\nGenerated: {filepath}")
            print(f"Rows: {row_count}")

            # Show first few rows
            print("\nFirst 10 rows:")
            print("-" * 80)
            for line in csv_content.split('\n')[:11]:
                print(line[:100])
            print("-" * 80)

            # Save cost log
            save_cost_log(session)

        except Exception as e:
            print(f"Error: {e}")
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
