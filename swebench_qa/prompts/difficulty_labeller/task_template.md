# Task

We wish to understand how difficult it is to solve an issue.

## Task Preparation

Please carefully study the issue, the test patch, and the gold patch shown below. The Gold Patch is the solution for the issue given in the original PR, and the Test Patch contains any new tests that were added in that same PR to verify that the issue was resolved. 

- Issue:
            
Title: {issue_title}

Body: {issue_body}

- Gold patch:

{patch}

- Test patch:

{test_patch}

## Task Description

Answer the following question and provide me with your rationale: "How long would it take (for an experienced software engineer who had a few hours to familiarize themselves with the codebase) to understand the problem described in the GitHub issue, arrive at a solution and write the code for a solution?" To provide your estimation, consider both (i) the time it would take to figure out what files need to be changed (a.k.a., "bug localization" in the context of bugs) as well as (ii) the time it would take for coming up with the solution itself.

Next, please assign a score from 0 to 3 based on your time estimation and the following guideline:
- 0: Less than 15 min.
- 1: From 15 min. to 1 hour 
- 2: From 1 hour to 4 hours
- 3: More than 4 hours

Notes:
- If the issue is too ambiguous to solve at all, please assume that the problem has been clarified sufficiently such that the high-level requirements for the solution are clear ("what"), but the specifics about the solution are left to the engineer to figure out ("how")
- Remember that a "solution" means a valid patch for the issue and nothing else.