# **SPICE TOOL and SPICE-bench🌶️** (*A SWE-Bench-verified–style labeling tool and benchmark for evaluating the software engineering capabilities of foundation models*) 
This is the official repository accompanying our paper: [**SPICE : An Automated SWE-Bench Labeling Pipeline for Issue Clarity, Test Coverage, and Effort Estimation**](https://arxiv.org/pdf/2507.09108)

# **How to cite our paper**
```
@article{oliva2025spice,
  title={SPICE: An Automated SWE-Bench Labeling Pipeline for Issue Clarity, Test Coverage, and Effort Estimation},
  author={Oliva, Gustavo A and Rajbahadur, Gopi Krishnan and Bhatia, Aaditya and Zhang, Haoxiang and Chen, Yihao and Chen, Zhilong and Leung, Arthur and Lin, Dayi and Chen, Boyuan and Hassan, Ahmed E},
  booktitle={Proceedings of the 40th IEEE/ACM International Conference on Automated Software Engineering (ASE)},
  year={2025}
}
```

# **SPICE-bench🌶️**

A curated dataset of 6,802 automatically labeled (with our SPICE tool) instances drawn from 291 real-world open-source projects in [SWE-Gym](https://arxiv.org/abs/2412.21139). This is the largest known collection of *solvable* SWE-bench-like tasks, and is over 13 times larger than SWEBench-Verified's human-labeled subset. SPICE-bench provides a rich resource for fine-tuning, benchmarking, and training SE-focused foundation models.

The dataset is available under `data` directory.

The data labels for `Issue quality`, `Test quality` and `Difficulty level` are available with the keys `task_score`, `evaluation_score` and `difficulty_score`  per instance. The data is provided as a `.jsonl` file for ease of use.

# **SPICE Tool🌶️ - A Tool for creating your own SPICE-bench**

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
