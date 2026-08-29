Feature: Platform Operations and Contest Management

  As a contest admin
  I want to manage contests and problems
  So that participants can compete fairly

  Background:
    Given the backend is running
    And the database is seeded with 4007 problems

  @bdd
  Scenario: Contest can be created by admin
    Given I am logged in as an admin user
    When I create a contest with name "Weekly Challenge 1"
    Then the contest should be created successfully
    And the contest should be in the database

  @bdd
  Scenario: Contest can be joined by participants
    Given a contest "Weekly Challenge 1" exists
    And I am registered as a participant
    When I join the contest
    Then I should appear in the contest's participant list
    And I should be able to see the contest problems

  @bdd
  Scenario: Contest leaderboard is ordered by score
    Given a contest with multiple participants
    And participants have submitted solutions with different scores
    When I query the leaderboard
    Then participants should be ordered by score (highest first)
    And participants with equal scores should be ordered by time (fastest first)

  @bdd
  Scenario: Rate limiting prevents submission spam
    Given I am a registered participant
    When I submit more than 30 times in one minute
    Then the system should return 429 Too Many Requests
    And subsequent submissions should be blocked until the rate limit resets

  @bdd
  Scenario: Stuck submissions are recovered after worker crash
    Given a submission has been in "RUNNING" state for more than 60 seconds
    When the periodic checker runs
    Then the submission should be re-enqueued
    And the submission should eventually complete

  @bdd
  Scenario: All 4007 problems are reachable via API
    Given the system is running
    When I query all problems
    Then I should receive all 4007 problems
    And each problem should have title, slug, and difficulty

  @bdd
  Scenario: Problem difficulty filter works correctly
    Given all 4007 problems are seeded
    When I filter by difficulty "Easy"
    Then I should only receive Easy problems
    When I filter by difficulty "Hard"
    Then I should only receive Hard problems

  @bdd
  Scenario: WebSocket delivers real-time submission updates
    Given I am watching a submission
    When the submission status changes to "ACCEPTED"
    Then I should receive a WebSocket push notification
    And the notification should contain the submission ID and verdict
