# **LABELING SPICE**

![SPICE](photos/spice_melange_dune_2021.png)


## **Introduction**

### **Dataset Requirements**
The input dataset must contain the following columns:
- **`instance_id`**: A unique identifier for each instance.
- **`repo`**: The repository name in the format `<owner>/<repo>`.
- **`base_commit`**: The commit hash used to set the repository's state.
- **`problem_statement`**: A textual description of the issue, comprising a title and body separated by a newline.
- **`patch`**: The code patch addressing the issue.
- **`test_patch`**: The test cases associated with the patch.

### **Objective**
For each instance in the dataset, this project will:
1. Assign a **score** to:
   - **Issue quality** (i.e., how clear the issue is)
   - **Test quality**  (i.e., how faithful the tests are too the issue as well as how coupled they are to the gold patch)
   - **Difficulty level**  (i.e., how hard it is to solve the issue)
2. Provide a detailed **rationale** for each score.

### **Scoring Framework**
The scoring process aligns with the same guidelines used for creating [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/), ensuring consistency with established benchmarking standards.

## **Implementation**

Scoring of the issues is done with a local model running on top of Ollama on a Huawei internal server.
Scoring of tests and difficulty are done with the help of a thin wrapper around [Aider](https://aider.chat/) and OpenAI gpt-4o (strong model) and gpt-4o-mini (weak model)


## **How to run SPICE**

- Install poetry and the project's dependencies with `poetry install`
- Add your `OPENAI_API_KEY` to `env-vars.sh`
- Source the environment variables: `source ./env-vars.sh`
- Run `python -m swebench_qa.app --help` for the CLI instructions.