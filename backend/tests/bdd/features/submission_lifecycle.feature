Feature: Code Submission Lifecycle

  Scenario: User submits a correct solution and gets AC
    Given a problem "two-sum" exists with id 1
    And a user "alice" is logged in
    When alice submits correct Python code for problem 1
    Then the submission should be accepted with verdict "AC"
    And the submission status should be "COMPLETED"

  Scenario: User submits an incorrect solution and gets WA
    Given a problem "two-sum" exists with id 1
    And a user "alice" is logged in
    When alice submits wrong Python code for problem 1
    Then the submission verdict should be "WA"

  Scenario: Infinite loop is killed as TLE
    Given a problem exists
    And a user is logged in
    When I submit code that runs an infinite loop with 3s timeout
    Then the submission should be terminated with verdict "TLE"
    And the wall time should be under 5 seconds

  Scenario: Runtime error returns RE
    Given a problem exists
    And a user is logged in
    When I submit code that causes a division by zero
    Then the submission verdict should be "RE"

  Scenario: Submission for unknown problem returns 404
    Given a user is logged in
    When I submit code for a non-existent problem id 99999
    Then the submission should fail with status 404

  Scenario: Run mode only tests sample cases (not hidden)
    Given a problem "two-sum" exists with both sample and hidden test cases
    And a user is logged in
    When alice submits correct code in "run" mode
    Then the submission should be judged against sample cases only
    And hidden test case results should not be visible

  Scenario: Submit mode tests all cases including hidden
    Given a problem "two-sum" exists with both sample and hidden test cases
    And a user is logged in
    When alice submits correct code in "submit" mode
    Then the submission should be judged against all test cases
