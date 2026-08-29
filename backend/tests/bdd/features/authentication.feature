Feature: User Registration and Authentication

  Scenario: User can register with username, email, and password
    Given the API server is running
    When I register a new user with username "alice", email "alice@algo.dev", and password "SecurePass123!"
    Then the registration should succeed with status 201
    And the response should contain a JWT access token

  Scenario: User can login with valid credentials
    Given a user "alice" exists with password "SecurePass123!"
    When I login with username "alice" and password "SecurePass123!"
    Then the login should succeed with status 200
    And the response should contain a JWT access token

  Scenario: Login fails with wrong password
    Given a user "alice" exists with password "SecurePass123!"
    When I login with username "alice" and password "WrongPassword"
    Then the login should fail with status 401

  Scenario: Duplicate username registration is rejected
    Given a user "alice" already exists
    When I try to register with username "alice" and email "other@algo.dev"
    Then the registration should fail with status 409

  Scenario: User cannot create problems without admin privileges
    Given a regular user "bob" is logged in
    When bob tries to create a problem
    Then the request should be forbidden with status 403
