Feature: Judge Sandbox — Correctness

  Scenario: Correct Python solution is judged Accepted
    When I run Python code that returns the correct answer for "two sum"
    Then the verdict should be "AC"
    And the stdout should contain the correct output

  Scenario: Incorrect Python solution is judged Wrong Answer
    When I run Python code that returns a wrong answer
    Then the verdict should be "WA"

  Scenario: Missing output is judged Wrong Answer
    When I run Python code that produces no output
    Then the verdict should be "WA"

Feature: Judge Sandbox — Disruption Handling

  Scenario: Infinite while loop is killed as TLE within the wall clock
    When I run Python code with an infinite while loop with wall_time_s=3
    Then the verdict should be "TLE"
    And the wall time should be less than 5000ms

  Scenario: Infinite recursion is caught as Runtime Error
    When I run Python code with infinite recursion
    Then the verdict should be "RE"

  Scenario: Division by zero is caught as Runtime Error
    When I run Python code with division by zero
    Then the verdict should be "RE"

  Scenario: Index out of bounds is caught as Runtime Error
    When I run Python code with an index error
    Then the verdict should be "RE"

  Scenario: Memory exhaustion is caught as MLE or terminated as TLE
    When I run Python code that allocates unbounded memory
    Then the verdict should be one of "MLE", "TLE", or "RE"

  Scenario: Excessive output is caught as OLE or Runtime Error
    When I run Python code that prints more than 1KB
    Then the verdict should be one of "OLE" or "RE"

Feature: Judge Sandbox — Determinism

  Scenario: Same code and input produces identical output across 5 runs
    When I run the same Python code 5 times with the same input
    Then all 5 results should have verdict "AC"
    And all 5 stdout values should be identical

  Scenario: Sort operation is deterministic
    When I run a sort algorithm 5 times
    Then all 5 stdout values should be identical

Feature: Judge Sandbox — Performance Measurement

  Scenario: Fast algorithm is measured correctly
    When I run a binary search on 100 elements
    Then the verdict should be "AC"
    And the wall time should be under 2000ms

  Scenario: Slow but correct algorithm completes
    When I run a sort on 10000 elements
    Then the verdict should be "AC"
    And the wall time should be under 10000ms

Feature: Contest Leaderboard

  Scenario: Leaderboard shows participants sorted by score
    Given a contest "Weekly #1" exists with id 1
    And participants alice, bob, and charlie have submitted solutions
    When I fetch the leaderboard for contest 1
    Then participants should be sorted by score in descending order
    And tied scores should be sorted by solve time

  Scenario: Leaderboard updates when new submission is judged
    Given a contest exists
    And a participant submits code
    When the submission is judged and accepted
    Then the leaderboard should reflect the new score
    And a WebSocket event should be pushed to connected clients

Feature: Stuck Submission Recovery

  Scenario: Submission stuck in RUNNING state for over 60s is re-enqueued
    Given a submission has been in "RUNNING" state for 70 seconds
    When the periodic checker runs
    Then the submission should be re-enqueued for judging
    And the submission status should remain "RUNNING"
