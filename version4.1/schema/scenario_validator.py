#!/usr/bin/env python3
"""
Scenario Validator for Generated Test Cases

Validates that a generated CSV matches the requirements specified in the prompt.
This is SEMANTIC validation (does it match what I asked for?), not just
structural validation (is it a valid CSV?).

Usage:
    python scenario_validator.py <csv_file> "<scenario_description>"

Example:
    python scenario_validator.py test.csv "Single male, full-time employed, no beneficiaries"
"""

import csv
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class CheckResult(Enum):
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    INFO = "ℹ️ INFO"


@dataclass
class ValidationCheck:
    name: str
    result: CheckResult
    expected: str
    actual: str
    details: str = ""


@dataclass
class ScenarioRequirements:
    """Parsed requirements from the scenario description."""
    # Employment
    employment_status: Optional[str] = None
    employer: Optional[str] = None
    sector: Optional[str] = None
    salary_range: Optional[str] = None

    # Personal
    marital_status: Optional[str] = None
    gender: Optional[str] = None

    # Optional sections
    has_beneficiary: Optional[bool] = None
    beneficiary_count: Optional[int] = None
    has_joint_partner: Optional[bool] = None
    joint_partner_count: Optional[int] = None
    lincu_card: Optional[bool] = None
    fip_application: Optional[bool] = None
    fip_plan: Optional[str] = None

    # Address
    permanent_address_same: Optional[bool] = None

    # PEP/FATCA
    all_pep_no: Optional[bool] = None
    all_fatca_no: Optional[bool] = None
    pep_positive_fields: List[str] = field(default_factory=list)


class ScenarioValidator:
    """Validates generated CSV against scenario requirements."""

    # Keywords for parsing scenarios
    EMPLOYMENT_KEYWORDS = {
        'full-time permanent': 'FULL TIME PERMANENT',
        'full-time temporary': 'FULL TIME TEMPORARY',
        'part-time': 'PART TIME',
        'self-employed': 'SELF EMPLOYED',
        'unemployed': 'UNEMPLOYED',
        'retired pensioned': 'RETIRED PENSIONED',
        'retired non-pensioned': 'RETIRED NON PENSIONED',
    }

    MARITAL_KEYWORDS = {
        'single': 'SINGLE',
        'married': 'MARRIED',
        'divorced': 'DIVORCED',
        'widowed': 'WIDOWED',
        'common law': 'COMMON LAW',
    }

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.rows: List[Dict] = []
        self.checks: List[ValidationCheck] = []
        self._load_csv()

    def _load_csv(self):
        """Load and parse the CSV file."""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.rows = list(reader)

    def parse_scenario(self, scenario: str) -> ScenarioRequirements:
        """Parse natural language scenario into structured requirements."""
        req = ScenarioRequirements()
        scenario_lower = scenario.lower()

        # Parse employment status
        for keyword, value in self.EMPLOYMENT_KEYWORDS.items():
            if keyword in scenario_lower:
                req.employment_status = value
                break

        # Parse marital status
        for keyword, value in self.MARITAL_KEYWORDS.items():
            if keyword in scenario_lower:
                req.marital_status = value
                break

        # Parse gender (look for male/female as standalone words)
        if re.search(r'\bmale\b', scenario_lower):
            req.gender = 'male'
        elif re.search(r'\bfemale\b', scenario_lower):
            req.gender = 'female'

        # Parse beneficiaries
        if 'no beneficiar' in scenario_lower:
            req.has_beneficiary = False
            req.beneficiary_count = 0
        elif match := re.search(r'(\d+)\s*beneficiar', scenario_lower):
            req.has_beneficiary = True
            req.beneficiary_count = int(match.group(1))

        # Parse joint partners
        if 'no joint partner' in scenario_lower:
            req.has_joint_partner = False
            req.joint_partner_count = 0
        elif match := re.search(r'(\d+)\s*joint partner', scenario_lower):
            req.has_joint_partner = True
            req.joint_partner_count = int(match.group(1))

        # Parse LinCU card
        if 'no lincu' in scenario_lower or 'not applying for lincu' in scenario_lower:
            req.lincu_card = False
        elif 'lincu card' in scenario_lower or 'applying for lincu' in scenario_lower:
            req.lincu_card = True

        # Parse FIP
        if 'no fip' in scenario_lower or 'not applying for fip' in scenario_lower:
            req.fip_application = False
        elif 'fip' in scenario_lower:
            req.fip_application = True
            if 'plan a' in scenario_lower:
                req.fip_plan = 'Plan A'
            elif 'plan b' in scenario_lower:
                req.fip_plan = 'Plan B'
            elif 'plan c' in scenario_lower:
                req.fip_plan = 'Plan C'

        # Parse address
        if 'permanent address same' in scenario_lower or 'same as mailing' in scenario_lower:
            req.permanent_address_same = True
        elif 'different' in scenario_lower and 'address' in scenario_lower:
            req.permanent_address_same = False

        # Parse PEP/FATCA
        if 'all pep' in scenario_lower and 'no' in scenario_lower:
            req.all_pep_no = True
        if 'all fatca' in scenario_lower and 'no' in scenario_lower:
            req.all_fatca_no = True
        if 'pep/fatca' in scenario_lower and 'no' in scenario_lower:
            req.all_pep_no = True
            req.all_fatca_no = True

        return req

    def get_field_value(self, element_name: str) -> Optional[str]:
        """Get the value set for a field in the CSV."""
        for row in self.rows:
            if row.get('Element') == element_name and row.get('Action') == 'Input':
                return row.get('Value')
        return None

    def get_boolean_value(self, element_name: str) -> Optional[bool]:
        """
        Get boolean value for a field.
        Checks both Input values AND click XPaths (label[1]=true, label[2]=false).
        """
        # First try explicit Input value
        value = self.get_field_value(element_name)
        if value is not None:
            return value.lower() == 'true'

        # If no Input, check click action XPath for label[1] (true) or label[2] (false)
        for row in self.rows:
            if row.get('Element') == element_name and row.get('Action') == 'click':
                xpath = row.get('XPath', '')
                # label[1] = Yes/True, label[2] = No/False (common pattern in this form)
                if 'label[1]' in xpath:
                    return True
                elif 'label[2]' in xpath:
                    return False

        return None

    def has_element(self, element_name: str) -> bool:
        """Check if an element exists in the CSV."""
        return any(row.get('Element') == element_name for row in self.rows)

    def count_element_occurrences(self, element_pattern: str) -> int:
        """Count occurrences of elements matching a pattern."""
        count = 0
        for row in self.rows:
            element = row.get('Element', '')
            if re.search(element_pattern, element, re.IGNORECASE):
                count += 1
        return count

    def get_selected_dropdown_value(self, trigger_text: str) -> Optional[str]:
        """Get the value selected in a dropdown after its trigger."""
        found_trigger = False
        for row in self.rows:
            element = row.get('Element', '')
            action = row.get('Action', '')

            if trigger_text.lower() in element.lower() and action == 'click':
                found_trigger = True
            elif found_trigger and action == 'click' and 'option' in row.get('XPath', '').lower():
                return element

        return None

    def validate(self, scenario: str) -> Tuple[bool, List[ValidationCheck]]:
        """Validate the CSV against the scenario requirements."""
        self.checks = []
        req = self.parse_scenario(scenario)

        # Basic stats
        self.checks.append(ValidationCheck(
            name="Row Count",
            result=CheckResult.INFO,
            expected="100-400 typical",
            actual=str(len(self.rows)),
            details="Total rows in generated CSV"
        ))

        # Check pages coverage
        pages = set(row.get('Group', '') for row in self.rows)
        expected_pages = {'Contact Info', 'Documents', 'Additional Details',
                         'Other Products', 'PEP / FATCA', 'PDF / Other Details'}
        # Normalize page names
        pages_normalized = set()
        for p in pages:
            for ep in expected_pages:
                if ep.lower() in p.lower() or p.lower() in ep.lower():
                    pages_normalized.add(ep)

        missing_pages = expected_pages - pages_normalized
        self.checks.append(ValidationCheck(
            name="Page Coverage",
            result=CheckResult.PASS if not missing_pages else CheckResult.FAIL,
            expected="All 6 pages",
            actual=f"{len(pages_normalized)}/6 pages",
            details=f"Missing: {missing_pages}" if missing_pages else "All pages covered"
        ))

        # Validate employment status
        if req.employment_status:
            actual = self.get_selected_dropdown_value("Employment Status")
            match = actual and req.employment_status.lower() in actual.lower()
            self.checks.append(ValidationCheck(
                name="Employment Status",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=req.employment_status,
                actual=actual or "Not found",
            ))

        # Validate marital status
        if req.marital_status:
            actual = self.get_selected_dropdown_value("Marital Status")
            match = actual and req.marital_status.lower() in actual.lower()
            self.checks.append(ValidationCheck(
                name="Marital Status",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=req.marital_status,
                actual=actual or "Not found",
            ))

        # Validate beneficiary setting
        if req.has_beneficiary is not None:
            actual_value = self.get_boolean_value('hasBeneficiary')
            if actual_value is None:
                # Try to infer from whether beneficiary fields exist
                has_beneficiary_fields = self.has_element('beneficiaryMobileNo')
                actual_value = has_beneficiary_fields

            match = actual_value == req.has_beneficiary
            self.checks.append(ValidationCheck(
                name="Has Beneficiary",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=str(req.has_beneficiary),
                actual=str(actual_value),
            ))

            # Check beneficiary count if specified
            if req.beneficiary_count is not None and req.beneficiary_count > 0:
                # Count beneficiary mobile fields as proxy
                count = self.count_element_occurrences(r'beneficiaryMobileNo')
                match = count == req.beneficiary_count
                self.checks.append(ValidationCheck(
                    name="Beneficiary Count",
                    result=CheckResult.PASS if match else CheckResult.WARN,
                    expected=str(req.beneficiary_count),
                    actual=str(count),
                ))

        # Validate joint partner setting
        if req.has_joint_partner is not None:
            actual_value = self.get_boolean_value('hasJointPartner')
            if actual_value is None:
                has_jp_fields = self.has_element('customerId')
                actual_value = has_jp_fields

            match = actual_value == req.has_joint_partner
            self.checks.append(ValidationCheck(
                name="Has Joint Partner",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=str(req.has_joint_partner),
                actual=str(actual_value),
            ))

        # Validate LinCU card
        if req.lincu_card is not None:
            actual_value = self.get_boolean_value('isApplyingForLincuCardApplication')
            match = actual_value == req.lincu_card
            self.checks.append(ValidationCheck(
                name="LinCU Card Application",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=str(req.lincu_card),
                actual=str(actual_value) if actual_value is not None else "Not found",
            ))

        # Validate FIP application
        if req.fip_application is not None:
            actual_value = self.get_boolean_value('isApplyingForFipApplication')
            match = actual_value == req.fip_application
            self.checks.append(ValidationCheck(
                name="FIP Application",
                result=CheckResult.PASS if match else CheckResult.FAIL,
                expected=str(req.fip_application),
                actual=str(actual_value) if actual_value is not None else "Not found",
            ))

        # Validate PEP/FATCA all No
        if req.all_pep_no:
            pep_fields = ['isHeadOfState', 'isHeadOfGovt', 'isSenPolitician',
                         'isSenGovtOfficial', 'isSenJudicialOfficial', 'isSenMilitaryOfficial',
                         'isSenExecSOC', 'isImpPPO', 'isImmediateFamily',
                         'isMemberOfSeniorManagement', 'isPepAssociate']
            all_false = True
            for pep_field in pep_fields:
                value = self.get_boolean_value(pep_field)
                if value is True:
                    all_false = False
                    break

            self.checks.append(ValidationCheck(
                name="All PEP Questions = No",
                result=CheckResult.PASS if all_false else CheckResult.FAIL,
                expected="All False",
                actual="All False" if all_false else "Some True",
            ))

        if req.all_fatca_no:
            fatca_fields = ['isCitizenOfOtherCountry', 'isGreenCardHolder',
                           'isGranteePOA', 'hasStandingInstructIncome',
                           'isDisclosureTaxResidency']
            all_false = True
            for fatca_field in fatca_fields:
                value = self.get_boolean_value(fatca_field)
                if value is True:
                    all_false = False
                    break

            self.checks.append(ValidationCheck(
                name="All FATCA Questions = No",
                result=CheckResult.PASS if all_false else CheckResult.FAIL,
                expected="All False",
                actual="All False" if all_false else "Some True",
            ))

        # Check for OTP sections (should have 2: initial and final)
        otp_count = self.count_element_occurrences(r'otp-input-0')
        self.checks.append(ValidationCheck(
            name="OTP Verifications",
            result=CheckResult.PASS if otp_count >= 2 else CheckResult.WARN,
            expected="2 (initial + final)",
            actual=str(otp_count),
        ))

        # Calculate pass rate
        passes = sum(1 for c in self.checks if c.result == CheckResult.PASS)
        fails = sum(1 for c in self.checks if c.result == CheckResult.FAIL)
        total = passes + fails

        all_passed = fails == 0
        return all_passed, self.checks

    def print_report(self, scenario: str):
        """Print a formatted validation report."""
        print("\n" + "=" * 70)
        print("SCENARIO VALIDATION REPORT")
        print("=" * 70)
        print(f"CSV File: {self.csv_path}")
        print(f"Scenario: {scenario[:80]}...")
        print("=" * 70)

        # Group by result
        passes = [c for c in self.checks if c.result == CheckResult.PASS]
        fails = [c for c in self.checks if c.result == CheckResult.FAIL]
        warns = [c for c in self.checks if c.result == CheckResult.WARN]
        infos = [c for c in self.checks if c.result == CheckResult.INFO]

        print(f"\nSummary: {len(passes)} passed, {len(fails)} failed, {len(warns)} warnings\n")

        for check in self.checks:
            print(f"{check.result.value} {check.name}")
            print(f"      Expected: {check.expected}")
            print(f"      Actual:   {check.actual}")
            if check.details:
                print(f"      Details:  {check.details}")
            print()

        print("=" * 70)
        if fails:
            print("RESULT: ❌ VALIDATION FAILED")
        else:
            print("RESULT: ✅ VALIDATION PASSED")
        print("=" * 70)


def main():
    if len(sys.argv) < 3:
        print("Usage: python scenario_validator.py <csv_file> \"<scenario_description>\"")
        print("\nExample:")
        print('  python scenario_validator.py test.csv "Single male, full-time employed, no beneficiaries"')
        sys.exit(1)

    csv_path = sys.argv[1]
    scenario = sys.argv[2]

    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    validator = ScenarioValidator(csv_path)
    passed, checks = validator.validate(scenario)
    validator.print_report(scenario)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
