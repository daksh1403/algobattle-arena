Feature: Contest Submission and Judging

  As a participant
  I want to submit code for a problem
  So that my solution is judged for correctness and efficiency

  Background:
    Given the backend is running
    And the database is seeded with test problems
    And I am registered as a participant

  @tdd
  Scenario: Submit code in test mode — only sample test cases are judged
    Given a problem exists with title "Two Sum"
    And the problem has sample test cases
    When I submit my code in "test" mode
    Then the system should judge ONLY the sample test cases
    And my submission should have mode "test"
    And hidden test cases should NOT be revealed

  @tdd
  Scenario: Submit code in submit mode — all test cases are judged
    Given a problem exists with title "Two Sum"
    And the problem has hidden test cases
    When I submit my code in "submit" mode
    Then the system should judge ALL test cases
    And my submission should have mode "submit"

  @tdd
  Scenario: Code executes correctly — Accepted verdict
    Given a problem "Two Sum" with correct solution code
    When I submit the correct solution
    Then the verdict should be "AC" (Accepted)
    And my score should be calculated

  @tdd
  Scenario: Code produces wrong output — Wrong Answer verdict
    Given a problem "Two Sum" with incorrect solution code
    When I submit the incorrect solution
    Then the verdict should be "WA" (Wrong Answer)

  @tdd
  Scenario: Code exceeds time limit — TLE verdict
    Given a problem with infinite loop code
    When I submit the infinite loop code
    Then the verdict should be "TLE" (Time Limit Exceeded)
    And the system should kill the process

  @tdd
  Scenario: Code exceeds memory limit — MLE verdict
    Given a problem with memory bomb code
    When I submit the memory bomb code
    Then the verdict should be "MLE" (Memory Limit Exceeded)

  @tdd
  Scenario: Code crashes — Runtime Error verdict
    Given a problem with division by zero code
    When I submit the crashing code
    Then the verdict should be "RE" (Runtime Error)

  @tdd
  Scenario: Determinism — same code produces same verdict every time
    Given a correct solution for "Two Sum"
    When I submit the same code 5 times
    Then all 5 submissions should have the same verdict
    And all 5 submissions should have the same score

  @tdd
  Scenario: Multiple submissions — best score is recorded
    Given a problem "Two Sum"
    When I submit multiple solutions with different scores
    Then the leaderboard should record my best score
    And my rank should reflect my best score

  @bdd
  Scenario: Admin can create problems
    Given I am logged in as an admin user
    When I create a new problem with title and test cases
    Then the problem should be saved in the database
    And the problem should appear in the problem list

  @bdd
  Scenario: Non-admin cannot create problems
    Given I am logged in as a regular participant
    When I try to create a new problem
    Then the system should return 403 Forbidden

  @bdd
  Scenario: Leaderboard updates when participant solves a problem
    Given a contest is active
    And a participant submits an accepted solution
    Then the leaderboard should update immediately
    And the participant's rank should reflect the new score
