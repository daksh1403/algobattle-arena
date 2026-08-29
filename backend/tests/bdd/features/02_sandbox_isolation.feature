Feature: Sandbox Isolation and Resource Limits

  As the platform operator
  I want submissions to run in isolated sandboxes
  So that malicious or broken code cannot affect other participants or the system

  Background:
    Given the sandbox runner is available
    And a 5-second timeout is configured

  @bdd
  Scenario: Infinite loop is killed within time limit
    Given a Python code with infinite loop
    When the code is executed in the sandbox
    Then it should be killed within 10 seconds
    And the verdict should be TLE

  @bdd
  Scenario: Infinite recursion causes stack overflow — RE verdict
    Given a Python code with infinite recursion
    When the code is executed in the sandbox
    Then the verdict should be RE (Runtime Error)

  @bdd
  Scenario: Memory bomb is killed — MLE verdict
    Given a Python code that allocates memory indefinitely
    When the code is executed in the sandbox
    Then the verdict should be MLE (Memory Limit Exceeded)

  @bdd
  Scenario: Division by zero raises exception — RE verdict
    Given a Python code that divides by zero
    When the code is executed in the sandbox
    Then the verdict should be RE (Runtime Error)

  @bdd
  Scenario: Index out of bounds raises exception — RE verdict
    Given a Python code that accesses out-of-bounds index
    When the code is executed in the sandbox
    Then the verdict should be RE (Runtime Error)

  @bdd
  Scenario: Output limit is enforced — OLE verdict
    Given a Python code that prints more than 128KB
    When the code is executed in the sandbox
    Then the verdict should be OLE (Output Limit Exceeded)

  @bdd
  Scenario: Correct solution produces Accepted verdict
    Given a Python code that solves "Two Sum" correctly
    When the code is executed in the sandbox with test input
    Then the verdict should be AC
    And the output should match the expected answer

  @bdd
  Scenario: Sandbox process cannot access network
    Given a Python code that tries to make a network request
    When the code is executed in the sandbox
    Then the network request should be blocked or timeout
    And the verdict should be TLE or RE

  @bdd
  Scenario: Sandbox process cannot read arbitrary files
    Given a Python code that tries to read /etc/passwd
    When the code is executed in the sandbox
    Then the file access should be denied
    And the verdict should be RE

  @bdd
  Scenario: Sandbox is deterministic — same code same input = same verdict
    Given a Python code snippet
    When the code is executed 5 times with the same input
    Then all 5 runs should produce identical verdicts
    And all 5 runs should produce identical outputs
    And the time variance should be less than 10ms²
