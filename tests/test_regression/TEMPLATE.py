"""
Regression test template for Issue #XXX: [Brief description of the bug]

This test verifies that [describe what the test verifies].

Bug Description:
  [Detailed description of the bug behavior before the fix]
  [Include specific error messages, stack traces, or unexpected behavior]

Expected Behavior:
  [Describe the correct behavior after the fix]
  [Explain what should happen instead of the bug]

Reproduction Steps (Original Bug):
  1. [Step 1 to reproduce the bug]
  2. [Step 2 to reproduce the bug]
  3. [Expected: bug occurs]

GitHub Issue: https://github.com/org/repo/issues/XXX
Jira Ticket: DEVO-XXX (if applicable)
Fixed in: PR #XXX or commit hash
Related Issues: #YYY, #ZZZ (if applicable)
"""

import pytest

# Import the modules/functions being tested
# from cli_tool.module_name import function_name


@pytest.mark.unit  # or @pytest.mark.integration, @pytest.mark.platform
def test_issue_nnn_brief_description():
    """
    Regression test for Issue #XXX: [one-line description].

    Bug: [Brief description of what was broken]
    Fix: [Brief description of how it was fixed]

    Issue: https://github.com/org/repo/issues/XXX
    """
    # ARRANGE: Set up the test scenario that reproduces the bug
    # This should recreate the exact conditions that caused the bug

    # ACT: Execute the code that previously caused the bug
    # This would have failed/crashed/produced wrong output before the fix

    # ASSERT: Verify the fix is working correctly
    # Check that the expected behavior now occurs


# Optional: Add additional test cases for edge cases related to the bug
@pytest.mark.unit
def test_issue_nnn_edge_case_1():
    """
    Regression test for Issue #NNN: [edge case description].

    Verify that the fix also handles [specific edge case].
    """
    pass


@pytest.mark.unit
def test_issue_nnn_edge_case_2():
    """
    Regression test for Issue #NNN: [another edge case description].

    Verify that the fix doesn't break [related functionality].
    """
    pass


# ============================================================================
# TEMPLATE USAGE INSTRUCTIONS
# ============================================================================
#
# 1. COPY THIS TEMPLATE
#    - Copy this file to a new file named after your issue
#    - Use naming convention: test_issue_<number>.py or test_<project>_<number>.py
#
# 2. FILL IN THE HEADER
#    - Replace XXX with actual issue number
#    - Fill in bug description, expected behavior, reproduction steps
#    - Add links to GitHub issue, Jira ticket, and PR/commit
#
# 3. WRITE THE TEST
#    - Import necessary modules
#    - Set up test fixtures if needed
#    - Write test that would have FAILED before the fix
#    - Verify test PASSES with the fix in place
#
# 4. ADD APPROPRIATE MARKERS
#    - @pytest.mark.unit for unit-level tests
#    - @pytest.mark.integration for integration tests
#    - @pytest.mark.platform for platform-specific tests
#    - @pytest.mark.slow for tests that take >5 seconds
#
# 5. FOLLOW AAA PATTERN
#    - ARRANGE: Set up test data and conditions
#    - ACT: Execute the code being tested
#    - ASSERT: Verify expected outcomes
#
# 6. ADD EDGE CASES
#    - Consider boundary conditions
#    - Test related functionality isn't broken
#    - Test error handling if applicable
#
# 7. DOCUMENT THOROUGHLY
#    - Explain WHY the bug occurred
#    - Explain HOW the fix addresses it
#    - Include links for traceability
#
# 8. RUN THE TEST
#    - pytest tests/test_regression/test_issue_XXX.py
#    - Verify it passes
#    - Run with coverage to ensure it tests the fix
#
# 9. DELETE THIS SECTION
#    - Remove the "TEMPLATE USAGE INSTRUCTIONS" section
#    - Keep only the actual test code
#
# ============================================================================
