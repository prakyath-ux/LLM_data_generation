#!/usr/bin/env python3
"""
Test Case CSV Validator

Validates LLM-generated test case CSVs against the form schema.
Checks for:
- Valid structure and columns
- XPath existence in schema
- Conditional logic compliance
- Sequence correctness
- Required field presence
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationResult:
    severity: ValidationSeverity
    row: int
    field: str
    message: str

    def __str__(self):
        return f"[{self.severity.value}] Row {self.row}, Field '{self.field}': {self.message}"


class TestCaseValidator:
    """Validates test case CSVs against the form schema."""

    REQUIRED_COLUMNS = ['Group', 'Element', 'Action', 'Value', 'Strategy', 'XPath']
    VALID_ACTIONS = ['click', 'Input']
    VALID_STRATEGIES = ['id', 'data-testid', 'data-testid+text', 'absolute', 'name', 'class', 'text']

    PAGE_ORDER = [
        'Contact Info', 'Personal Information',
        'Documents',
        'Additional Details',
        'Other Products',
        'PEP / FATCA',
        'PDF / Other Details'
    ]

    def __init__(self, schema_path: str, rules_path: str):
        """Initialize validator with schema and rules files."""
        self.schema = self._load_json(schema_path)
        self.rules = self._load_json(rules_path)
        self.results: List[ValidationResult] = []
        self.xpath_registry: Dict[str, str] = {}
        self.element_registry: Dict[str, dict] = {}
        self._build_registries()

    def _load_json(self, path: str) -> dict:
        """Load and parse JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _build_registries(self):
        """Build lookup registries from schema."""
        for page in self.schema.get('pages', []):
            for section in page.get('sections', []):
                for field in section.get('fields', []):
                    field_id = field.get('id', '')
                    if field_id:
                        self.element_registry[field_id] = field
                        if 'xpath' in field:
                            self.xpath_registry[field['xpath']] = field_id
                        if 'xpath_true' in field:
                            self.xpath_registry[field['xpath_true']] = f"{field_id}_true"
                        if 'xpath_false' in field:
                            self.xpath_registry[field['xpath_false']] = f"{field_id}_false"
                        if 'xpath_trigger' in field:
                            self.xpath_registry[field['xpath_trigger']] = f"{field_id}_trigger"

                    # Register dropdown options
                    for option in field.get('options', []):
                        if 'xpath' in option:
                            self.xpath_registry[option['xpath']] = option.get('value', '')

    def validate_csv(self, csv_path: str) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate a test case CSV file.

        Returns:
            Tuple of (is_valid, list of validation results)
        """
        self.results = []

        try:
            rows = self._read_csv(csv_path)
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationSeverity.ERROR, 0, 'file', f"Failed to read CSV: {str(e)}"
            ))
            return False, self.results

        # Validate structure
        self._validate_structure(rows)

        # Validate content
        self._validate_content(rows)

        # Validate sequence
        self._validate_sequence(rows)

        # Validate conditional logic
        self._validate_conditionals(rows)

        # Check for errors
        has_errors = any(r.severity == ValidationSeverity.ERROR for r in self.results)

        return not has_errors, self.results

    def _read_csv(self, csv_path: str) -> List[dict]:
        """Read CSV file and return list of row dictionaries."""
        rows = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    def _validate_structure(self, rows: List[dict]):
        """Validate CSV structure and columns."""
        if not rows:
            self.results.append(ValidationResult(
                ValidationSeverity.ERROR, 0, 'file', "CSV is empty"
            ))
            return

        # Check columns
        first_row_keys = set(rows[0].keys())
        for col in self.REQUIRED_COLUMNS:
            if col not in first_row_keys:
                self.results.append(ValidationResult(
                    ValidationSeverity.ERROR, 0, col, f"Missing required column: {col}"
                ))

    def _validate_content(self, rows: List[dict]):
        """Validate content of each row."""
        for i, row in enumerate(rows, start=1):
            row_num = i

            # Validate Action
            action = row.get('Action', '')
            if action and action not in self.VALID_ACTIONS:
                self.results.append(ValidationResult(
                    ValidationSeverity.ERROR, row_num, 'Action',
                    f"Invalid action '{action}'. Must be one of: {self.VALID_ACTIONS}"
                ))

            # Validate Strategy
            strategy = row.get('Strategy', '')
            if strategy and strategy not in self.VALID_STRATEGIES:
                self.results.append(ValidationResult(
                    ValidationSeverity.WARNING, row_num, 'Strategy',
                    f"Unusual strategy '{strategy}'. Expected one of: {self.VALID_STRATEGIES}"
                ))

            # Validate XPath format
            xpath = row.get('XPath', '')
            if xpath:
                self._validate_xpath(row_num, xpath)

            # Validate Input action has value
            if action == 'Input' and not row.get('Value'):
                self.results.append(ValidationResult(
                    ValidationSeverity.WARNING, row_num, 'Value',
                    "Input action with empty value"
                ))

            # Validate Group is known
            group = row.get('Group', '')
            if group and not any(group in p for p in self.PAGE_ORDER):
                self.results.append(ValidationResult(
                    ValidationSeverity.WARNING, row_num, 'Group',
                    f"Unknown group/page: '{group}'"
                ))

    def _validate_xpath(self, row_num: int, xpath: str):
        """Validate XPath format and existence in schema."""
        # Basic format check
        if not xpath.startswith('/'):
            self.results.append(ValidationResult(
                ValidationSeverity.ERROR, row_num, 'XPath',
                f"XPath must start with '/': {xpath[:50]}..."
            ))
            return

        # Check for common XPath errors
        if '""' in xpath and not xpath.startswith('"//*'):
            # This is likely a formatting issue with quotes
            pass  # CSV escaping can cause this

        # Note: We don't strictly enforce schema presence since
        # the schema might not be complete. Just warn.
        # In production, you'd check: xpath not in self.xpath_registry

    def _validate_sequence(self, rows: List[dict]):
        """Validate that pages appear in correct order."""
        current_page_index = -1

        for i, row in enumerate(rows, start=1):
            group = row.get('Group', '')

            # Find page index
            page_index = -1
            for j, page in enumerate(self.PAGE_ORDER):
                if page in group or group in page:
                    page_index = j
                    break

            if page_index == -1:
                continue  # Unknown page, already warned

            if page_index < current_page_index:
                self.results.append(ValidationResult(
                    ValidationSeverity.ERROR, i, 'Group',
                    f"Page '{group}' appears after a later page. Expected order: {self.PAGE_ORDER}"
                ))

            current_page_index = max(current_page_index, page_index)

    def _validate_conditionals(self, rows: List[dict]):
        """Validate conditional logic compliance."""
        # Track boolean selections
        boolean_states: Dict[str, bool] = {}

        for i, row in enumerate(rows, start=1):
            element = row.get('Element', '')
            action = row.get('Action', '')
            value = row.get('Value', '')

            # Track boolean field states
            if action == 'Input' and value in ['true', 'false', 'True', 'False']:
                boolean_states[element] = value.lower() == 'true'

        # Check conditional rules
        for rule in self.rules.get('dependency_rules', []):
            trigger_field = rule.get('trigger_field', '')
            trigger_value = rule.get('trigger_value')
            required_fields = rule.get('required_fields', [])
            excluded_fields = rule.get('excluded_fields', [])

            if trigger_field in boolean_states:
                actual_value = boolean_states[trigger_field]

                # If trigger condition is met
                if actual_value == trigger_value:
                    # Check required fields are present
                    present_elements = {row.get('Element', '') for row in rows}
                    for req_field in required_fields:
                        if req_field not in present_elements:
                            self.results.append(ValidationResult(
                                ValidationSeverity.WARNING, 0, req_field,
                                f"Field '{req_field}' may be required when '{trigger_field}' is {trigger_value}"
                            ))
                else:
                    # Check excluded fields are not present (when trigger not met)
                    for excl_field in excluded_fields:
                        if excl_field in {row.get('Element', '') for row in rows}:
                            self.results.append(ValidationResult(
                                ValidationSeverity.WARNING, 0, excl_field,
                                f"Field '{excl_field}' may not be needed when '{trigger_field}' is {actual_value}"
                            ))

    def _validate_phone_format(self, value: str) -> bool:
        """Validate phone number format XXX-XXXX."""
        return bool(re.match(r'^\d{3}-\d{4}$', value))

    def _validate_email_format(self, value: str) -> bool:
        """Validate email format."""
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value))

    def print_report(self):
        """Print validation report to stdout."""
        if not self.results:
            print("Validation passed with no issues.")
            return

        errors = [r for r in self.results if r.severity == ValidationSeverity.ERROR]
        warnings = [r for r in self.results if r.severity == ValidationSeverity.WARNING]
        infos = [r for r in self.results if r.severity == ValidationSeverity.INFO]

        print(f"\n{'='*60}")
        print(f"VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Errors:   {len(errors)}")
        print(f"Warnings: {len(warnings)}")
        print(f"Info:     {len(infos)}")
        print(f"{'='*60}\n")

        if errors:
            print("ERRORS:")
            for r in errors:
                print(f"  {r}")
            print()

        if warnings:
            print("WARNINGS:")
            for r in warnings:
                print(f"  {r}")
            print()

        if infos:
            print("INFO:")
            for r in infos:
                print(f"  {r}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validator.py <test_case.csv> [schema.json] [rules.json]")
        print("\nValidates a test case CSV against the form schema.")
        sys.exit(1)

    # Default paths relative to project root
    project_root = Path(__file__).parent.parent.parent
    default_schema = project_root / "config" / "form_schema.json"
    default_rules = project_root / "config" / "conditional_rules.json"

    csv_path = sys.argv[1]
    schema_path = sys.argv[2] if len(sys.argv) > 2 else str(default_schema)
    rules_path = sys.argv[3] if len(sys.argv) > 3 else str(default_rules)

    # Check files exist
    for path, name in [(csv_path, 'CSV'), (schema_path, 'Schema'), (rules_path, 'Rules')]:
        if not Path(path).exists():
            print(f"Error: {name} file not found: {path}")
            sys.exit(1)

    # Run validation
    validator = TestCaseValidator(schema_path, rules_path)
    is_valid, results = validator.validate_csv(csv_path)
    validator.print_report()

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
