from dataclasses import asdict
import json
from pathlib import Path
import pandas as pd
import asyncio
import concurrent.futures
import threading
from typing import Dict, Any, Tuple, Optional
from tqdm import tqdm
from swebench_qa.environment import Environment
from swebench_qa.base_labellers import IssueLabeller, StubIssueLabeller, TestLabeller, StubTestLabeller, DifficultyLabeller, StubDifficultyLabeller
from swebench_qa.issue_labeller.issue_labeller import DefaultIssueLabeller, IssueLabellerConfig
from swebench_qa.test_labeller.test_labeller import AiderTestLabeller
from swebench_qa.difficulty_labeller.difficulty_labeller import AiderDifficultyLabeller
from swebench_qa.vcs import GitUtils

current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent

# ---- General Notes ----
# TODO: Ideally should just pass the model in args or better yet, a config file.


class ThreadSafeResultWriter:
    """Thread-safe result writer to prevent race conditions when writing results."""
    
    def __init__(self, result_filepath: Path):
        self.result_filepath = result_filepath
        self._lock = threading.Lock()
    
    def write_result(self, result: Dict[str, Any]) -> None:
        """Thread-safe method to write a single result to the file."""
        with self._lock:
            with open(self.result_filepath, "a") as f:
                json.dump(result, f)
                f.write("\n")


class LabellerFactory:

    @classmethod
    def get_issue_model(cls):
        """Get issue model from environment or use fallback"""
        return os.environ.get("SPICE_MODEL_ISSUE", "deepseek/deepseek-reasoner")
    
    @classmethod
    def get_test_model_strong(cls):
        """Get strong test model from environment or use fallback"""
        return os.environ.get("SPICE_MODEL_STRONG", "deepseek/deepseek-reasoner")
    
    @classmethod
    def get_test_model_weak(cls):
        """Get weak test model from environment or use fallback"""
        return os.environ.get("SPICE_MODEL_WEAK", "deepseek/deepseek-reasoner")
    
    @classmethod
    def get_difficulty_model_strong(cls):
        """Get strong difficulty model from environment or use fallback"""
        return os.environ.get("SPICE_MODEL_DIFFICULTY_STRONG", "stub")
    
    @classmethod
    def get_difficulty_model_weak(cls):
        """Get weak difficulty model from environment or use fallback"""
        return os.environ.get("SPICE_MODEL_DIFFICULTY_WEAK", "stub")
    
    @classmethod
    def create_issue_labeller(cls, name, params):
        if name == "default":
            params.setdefault("strategy", "naive")
            params.setdefault("model", cls.get_issue_model())
            params.setdefault("provider", "litellm")
            return DefaultIssueLabeller(config=IssueLabellerConfig(**params))
        elif name == "stub":
            return StubIssueLabeller()
        else:
            raise ValueError(f"Unknown issue labeller: {name}")

    @classmethod
    def create_test_labeller(cls, name, params):
        if name == "default":
            params.setdefault("strong_model", cls.get_test_model_strong())
            params.setdefault("weak_model", cls.get_test_model_weak())
            return AiderTestLabeller(**params)
        elif name == "stub":
            return StubTestLabeller()
        else:
            raise ValueError(f"Unknown test labeller: {name}")

    @classmethod
    def create_difficulty_labeller(cls, name, params):
        if name == "default":
            params.setdefault("strong_model", cls.get_difficulty_model_strong())
            params.setdefault("weak_model", cls.get_difficulty_model_weak())
            return AiderDifficultyLabeller(**params)
        elif name == "stub":
            return StubDifficultyLabeller()
        else:
            raise ValueError(f"Unknown difficulty labeller: {name}")


class SWEbenchLabeller:

    def __init__(self, experiment_id, experiment_description, swebench_path, label_result_dir, issue_labeller, issue_labeller_params, test_labeller, test_labeller_params, difficulty_labeller, difficulty_labeller_params, instances_to_skip=None, repetitions=3):
        # swebench_path: swebench-like dataset with the following columns instance_id, repo, base_commit, problem_statement (issue title and description/body are separated by a line break), patch, test_patch

        self.experiment_id = experiment_id
        self.experiment_description = experiment_description
        self.swebench_path = Path(swebench_path)

        
        if instances_to_skip is None:
            # Default to empty list - users can provide their own skip list
            self.instances_to_skip = []
        else:
            self.instances_to_skip = instances_to_skip
        print(f"\n\n====== Skipped {len(self.instances_to_skip)} instances! =======\n\n")
        self.repetitions = repetitions

        # Check that swebench data exists
        if not self.swebench_path.is_file():
            raise FileNotFoundError(
                f"SWEbench-like dataset not found at {self.swebench_path}")

        # Set up log dirs for labellers
        self.experiment_logs_base_dir = root_dir / "logs" / self.experiment_id
        self.experiment_logs_base_dir.mkdir(parents=True, exist_ok=True)

        self.issue_labeller_logs_dir = self.experiment_logs_base_dir / "issue_labelling"
        self.test_labeller_logs_dir = self.experiment_logs_base_dir / "test_labelling"
        self.difficulty_labeller_logs_dir = self.experiment_logs_base_dir / "difficulty_labelling"
        self.issue_labeller_logs_dir.mkdir(parents=True, exist_ok=True)
        self.test_labeller_logs_dir.mkdir(parents=True, exist_ok=True)
        self.difficulty_labeller_logs_dir.mkdir(parents=True, exist_ok=True)

        # Instantiate labellers
        self.issue_labeller_name = issue_labeller
        self.issue_labeller_params = issue_labeller_params
        self.issue_labeller: IssueLabeller = LabellerFactory.create_issue_labeller(
            name=issue_labeller, params=issue_labeller_params)

        self.test_labeller_name = test_labeller
        self.test_labeller_params = test_labeller_params
        self.test_labeller: TestLabeller = LabellerFactory.create_test_labeller(
            name=test_labeller, params=test_labeller_params)

        self.difficulty_labeller_name = difficulty_labeller
        self.difficulty_labeller_params = difficulty_labeller_params
        self.difficulty_labeller: DifficultyLabeller = LabellerFactory.create_difficulty_labeller(
            name=difficulty_labeller, params=difficulty_labeller_params)

        # Workspace path
        self.workspace_path = root_dir / 'workspace'

        # Label result path
        label_result_dir = Path(label_result_dir)
        label_result_dir.mkdir(parents=True, exist_ok=True)
        self.label_result_filepath = label_result_dir / \
            f'{experiment_id}.jsonl'
        
        # Initialize thread-safe result writer
        self.result_writer = ThreadSafeResultWriter(self.label_result_filepath)

    def setup_repo(self, repo, base_commit: str):
        clone_url = f"https://github.com/{repo}.git"
        repo_path = self.workspace_path / repo

        # Clone the repo in case we haven't done it yet
        if not repo_path.exists():
            GitUtils.clone_repo(clone_url=clone_url, to_path=repo_path)

        GitUtils.checkout_commit(repo_path, base_commit)

        return repo_path

    def _create_labeller_instances(self, instance_id: str, repo_path: Path) -> Tuple[IssueLabeller, TestLabeller, DifficultyLabeller]:
        """Create fresh instances of labellers for parallel processing to avoid race conditions."""
        
        # Create new instances to avoid shared state issues
        issue_labeller = LabellerFactory.create_issue_labeller(
            name=self.issue_labeller_name, params=self.issue_labeller_params.copy())
        test_labeller = LabellerFactory.create_test_labeller(
            name=self.test_labeller_name, params=self.test_labeller_params.copy())
        difficulty_labeller = LabellerFactory.create_difficulty_labeller(
            name=self.difficulty_labeller_name, params=self.difficulty_labeller_params.copy())
        
        # Set up environments for each labeller
        issue_labeller.environment = Environment(
            instance_id=instance_id, repo_path=repo_path, log_dir=self.issue_labeller_logs_dir)
        test_labeller.environment = Environment(
            instance_id=instance_id, repo_path=repo_path, log_dir=self.test_labeller_logs_dir)
        difficulty_labeller.environment = Environment(
            instance_id=instance_id, repo_path=repo_path, log_dir=self.difficulty_labeller_logs_dir)
        
        return issue_labeller, test_labeller, difficulty_labeller

    

    def _process_instance_sequential(self, row, repo_path: Path, nrows: int) -> None:
        """Process a single instance sequentially (safe for shared repo state)."""

        print(f"Processing row {row.Index}/{nrows-1}: {row.instance_id}")

        # Break down issue into title and body
        issue = row.problem_statement
        issue_title, issue_body = issue.split('\n', 1) if '\n' in issue else issue.split('\r\n', 1)

        for i in range(self.repetitions):
            try:
                # Use fresh labeller instances for isolation
                issue_labeller, test_labeller, difficulty_labeller = self._create_labeller_instances(
                    row.instance_id, repo_path
                )

                # Run labelers SEQUENTIALLY to avoid repo FS contention (Aider)
                issue_score, issue_rationale, issue_has_solution = issue_labeller.label_issue(
                    issue_title=issue_title, issue_body=issue_body
                )

                test_score, test_rationale = test_labeller.label_test(
                    issue_title=issue_title, issue_body=issue_body, patch=row.patch, test_patch=row.test_patch
                )

                difficulty_score, difficulty_rationale = difficulty_labeller.label_difficulty(
                    issue_title=issue_title, issue_body=issue_body, patch=row.patch, test_patch=row.test_patch
                )

                instance_label_result = {
                    "instance_id": row.instance_id,
                    "repetition": (i + 1),
                    "issue_score": issue_score,
                    "issue_rationale": issue_rationale,
                    "issue_has_solution": issue_has_solution,
                    "test_score": test_score,
                    "test_rationale": test_rationale,
                    "difficulty_score": difficulty_score,
                    "difficulty_rationale": difficulty_rationale,
                }

                # Thread-safe write
                self.result_writer.write_result(instance_label_result)
                print(f"Completed repetition {i+1} for instance {row.instance_id}")

            except Exception as e:
                print(f"Error in sequential processing for instance {row.instance_id}, rep {i+1}: {e}")

    def _process_repo_group(self, repo: str, group_df: 'pd.DataFrame', nrows: int, pbar=None) -> None:
        """Process all instances for a single repo sequentially to avoid disk overlap."""

        print(f"Starting repo {repo} with {len(group_df)} instances")

        for row in group_df.itertuples():
            if row.instance_id in self.instances_to_skip:
                print(f"Skipping {row.Index}: {row.instance_id} (either by request or already processed)")
                if pbar is not None:
                    pbar.update(1)
                continue

            # Setup/checkout for this specific instance commit
            repo_path = self.setup_repo(row.repo, row.base_commit)

            # Process instance sequentially (incl. all repetitions)
            self._process_instance_sequential(row, repo_path, nrows)

            # Update overall instance progress
            if pbar is not None:
                pbar.update(1)
        
        print(f"Finished repo {repo}")

    def store_experiment_settings(self):

        experiment_settings = {
            "experiment_id": self.experiment_id,
            "experiment_description": self.experiment_description,
            "dataset":  str(self.swebench_path.absolute()),
            "issue_labeller": self.issue_labeller_name,
            "issue_labeller_params": self.issue_labeller_params,
            "test_labeller": self.test_labeller_name,
            "test_labeller_params": self.test_labeller_params,
            "difficulty_labeller": self.difficulty_labeller_name,
            "difficulty_labeller_params": self.difficulty_labeller_params,
            "skipped_instances": self.instances_to_skip,
            "repetitions": self.repetitions,
        }

        experiment_settings_json = self.experiment_logs_base_dir / \
            f"{self.experiment_id}.json"

        with open(experiment_settings_json, "w") as f:  # "a" for append mode
            json.dump(experiment_settings, f)


    def label_parallel_by_repo(self, max_workers: int = 4):
        """
        Parallelize across repositories to avoid workspace checkout conflicts.

        Runs one thread per repo (up to max_workers). Within a repo, instances
        (and their labelers) are processed sequentially to prevent disk overlap
        when using tools like Aider that modify the repo.
        """

        print(f"Starting repo-parallel labeling with max_workers={max_workers}")

        # Log the experimental settings for traceability
        self.store_experiment_settings()

        # If no instances to skip, just create an empty vector
        if self.instances_to_skip is None:
            self.instances_to_skip = []

        # Resume support: add already processed instances to skip list
        if self.label_result_filepath.is_file():
            df_existing = pd.read_json(self.label_result_filepath, lines=True)
            if not df_existing.empty and "instance_id" in df_existing.columns:
                processed_instances = df_existing["instance_id"].unique()
                self.instances_to_skip.extend(processed_instances)

        # Load the swebench data
        df = pd.read_parquet(self.swebench_path)
        nrows = len(df)

        # Group by repo
        try:
            grouped = df.groupby("repo")
        except KeyError:
            raise KeyError("Input dataset missing required 'repo' column for repo-parallel labeling")

        # Prepare groups (as concrete DataFrames) to submit to executor
        repo_groups = [(repo, group.copy()) for repo, group in grouped]
        print(f"Found {len(repo_groups)} repos to process")

        # Total instances across all repos
        total_instances = sum(len(group_df) for _, group_df in repo_groups)
        instance_pbar = tqdm(total=total_instances, desc="Processing instances (parallel)", unit="instance")

        # Process repos in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(self._process_repo_group, repo, group_df, nrows, instance_pbar): repo
                for repo, group_df in repo_groups
            }

            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    future.result()
                    print(f"Successfully completed repo {repo}")
                except Exception as e:
                    print(f"Error processing repo {repo}: {e}")
        instance_pbar.close()
        print("Repo-parallel labeling completed!")

    def label(self):
        """
        Original sequential version of the label method for backward compatibility.
        """

        # Log the experimental settings for traceability
        self.store_experiment_settings()

        # If no instances to skip, just create an empty vector
        if self.instances_to_skip is None:
            self.instances_to_skip = []

        # Check if we are resuming an experiment (e.g., due to crash). If yes, add already processed entries to instances_to_skip
        if self.label_result_filepath.is_file():
            df = pd.read_json(self.label_result_filepath, lines=True)
            if not df.empty:
                processed_instances = df["instance_id"].unique()
                self.instances_to_skip.extend(processed_instances)

        # Load the swebench data
        df = pd.read_parquet(self.swebench_path)
        nrows = len(df)

        # Progress bar for instances
        pbar = tqdm(total=nrows, desc="Processing instances", unit="instance")

        # Label each data instance (row)
        for row in df.itertuples():

            if row.instance_id in self.instances_to_skip:
                print(
                    f"Skipping {row.Index}: {row.instance_id} (either by request or already processed)")
                pbar.update(1)
                continue

            print(f"Processing row {row.Index}/{nrows-1}: {row.instance_id}")

            # Setup repo at base commit
            repo_path = self.setup_repo(row.repo, row.base_commit)

            # Setup environment for labellers
            self.issue_labeller.environment = Environment(
                instance_id=row.instance_id, repo_path=repo_path, log_dir=self.issue_labeller_logs_dir)
            self.test_labeller.environment = Environment(
                instance_id=row.instance_id, repo_path=repo_path, log_dir=self.test_labeller_logs_dir)
            self.difficulty_labeller.environment = Environment(
                instance_id=row.instance_id, repo_path=repo_path, log_dir=self.difficulty_labeller_logs_dir)

            # Break down issue into title and body
            issue = row.problem_statement
            issue_title, issue_body = issue.split(
                '\n', 1) if '\n' in issue else issue.split('\r\n', 1)

            for i in range(self.repetitions):

                # Label issue, test, and difficulty
                issue_score, issue_rationale, issue_has_solution = self.issue_labeller.label_issue(
                    issue_title=issue_title, issue_body=issue_body)

                test_score, test_rationale = self.test_labeller.label_test(
                    issue_title=issue_title, issue_body=issue_body, patch=row.patch, test_patch=row.test_patch)

                difficulty_score, difficulty_rationale = self.difficulty_labeller.label_difficulty(
                    issue_title=issue_title, issue_body=issue_body, patch=row.patch, test_patch=row.test_patch)

                instance_label_result = {
                    "instance_id": row.instance_id,
                    "repetition": (i+1),
                    "issue_score": issue_score,
                    "issue_rationale": issue_rationale,
                    "issue_has_solution": issue_has_solution,
                    "test_score": test_score,
                    "test_rationale": test_rationale,
                    "difficulty_score": difficulty_score,
                    "difficulty_rationale": difficulty_rationale,
                }

                with open(self.label_result_filepath, "a") as f:
                    json.dump(instance_label_result, f)
                    f.write("\n")

            # Update progress once per instance after all repetitions
            pbar.update(1)

        pbar.close()
