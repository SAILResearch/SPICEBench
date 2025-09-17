# Task

## Task Preparation

You will now consider the tests that will be used to check whether a given issue is resolved. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. Please carefully study the issue, the test patch, and the gold patch shown below.

- Issue:
            
Title: {issue_title}

Body: {issue_body}

- Gold patch:

{patch}

- Test patch:

{test_patch}

## Task Description

Answer the following question and provide me with your rationale: "Are the tests well-scoped such that all reasonable solutions to the issue should pass the tests?" 

Next, please assign the tests a score from 0 to 3 based on the following guideline:
- 0: The tests perfectly cover all possible solutions.
- 1: The tests cover the majority of correct solutions, however some unusual solutions may be missed
- 2: The tests work but some perfectly reasonable solutions may be missed by the tests
- 3: The tests are too narrow, too broad, or they look for something different than what the issue is about.

Notes:
- Remember that a solution means a valid patch for the issue and nothing else.
- Leverage your understanding of the entire codebase to understand what an "unusual solution" means.
- Only score tests higher than 0 if you can think of a reasonable counter-example (i.e., some valid patch that would be missed by the tests)