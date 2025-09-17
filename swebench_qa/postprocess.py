# Experiment analysis

import re
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import mode  # To compute the mode

# Define paths
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent


def parse_score(raw: str) -> int:
    # *1.* remove <think> blocks that are found in thinking models like deepseek:r1
    cleaned = re.sub(r'<think>.*?</think>', '', raw, flags=re.S)
    # *2.* find first digit 0–3, since
    m = re.search(r'\b[0-3]\b', cleaned)
    if m:
        return int(m.group())
    raise ValueError(f"No valid score in: {raw!r}")


def to_wide_format(experiment_id):
    """Post-process the results of an experiment and convert them to a wide format (a.k.a., pivoting)."""

    # Load experiment result
    result_jsonl = root_dir / "results" / f"{experiment_id}.jsonl"

    # Read the results JSONL file into a DataFrame
    df = pd.read_json(result_jsonl, lines=True)

    # Override issue score
    df.loc[df['issue_score'] == 1, 'issue_score'] = 3

    # Modify the groupby operation to handle this
    def compute_scores_and_methods(group):
        results = {}
        for column in ["issue_score", "test_score", "difficulty_score"]:

            # Create "final_score" and "decision_method" columns
            series = group[column]

            # Discard bad data (-1 scores) from the series
            series = series[series != -1]

            mode_result = mode(series, keepdims=True)
            if mode_result.count[0] > 1:
                # Return the mode
                final_score, method = mode_result.mode[0], "majority"
            else:
                final_score, method = np.median(
                    series), "median"      # Fall back to median

            results[f"final_{column}"] = final_score  # Store the final score
            # Store how the decision was made
            results[f"{column}_decision_method"] = method

            # Add column indicating whether the final score was controversial
            # Check if the Series contains 0 or 1
            has_0_or_1 = series.isin([0, 1]).any()
            # Check if the Series contains 1 or 2
            has_1_or_2 = series.isin([2, 3]).any()
            results[f"controversial_{column}_decision"] = has_0_or_1 and has_1_or_2

            # Add column to indicate whether we got a good issue/test
            if column == "issue_score":
                results["good_issue"] = final_score <= 1
            elif column == "test_score":
                results["good_tests"] = final_score <= 1

        return pd.Series(results)

    # Transform repetition data into separate columns
    def transform_repetitions(group, labeller_col="repetition"):
        result = {}

        # Collect all scores into lists for issue, test, and difficulty
        result["issue_scores"] = group["issue_score"].tolist()
        result["test_scores"] = group["test_score"].tolist()
        result["difficulty_scores"] = group["difficulty_score"].tolist()

        for idx, (_, row) in enumerate(group.iterrows(), start=1):
            labeller_id = row[labeller_col]  # Get the repetition number
            # Add columns for issue
            result[f"issue_score_labeller_{idx}"] = row["issue_score"]
            result[f"issue_rationale_labeller_{idx}"] = f"Labeller {labeller_id}: {row['issue_rationale']}"
            # Add columns for test
            result[f"test_score_labeller_{idx}"] = row["test_score"]
            result[f"test_rationale_labeller_{idx}"] = f"Labeller {labeller_id}: {row['test_rationale']}"
            # Add columns for difficulty
            result[f"difficulty_score_labeller_{idx}"] = row["difficulty_score"]
            result[f"difficulty_rationale_labeller_{idx}"] = f"Labeller {labeller_id}: {row['difficulty_rationale']}"
        return pd.Series(result)

    # Group by instance_id and compute final scores
    grouped = df.groupby("instance_id")
    final_scores_with_methods = grouped.apply(compute_scores_and_methods)

    # Apply the transformation for repetition data
    transformed_repetitions = grouped.apply(
        lambda group: transform_repetitions(group, labeller_col="repetition"))

    # Combine final_scores and transformed_repetitions
    result = pd.concat(
        [final_scores_with_methods, transformed_repetitions], axis=1).reset_index()

    # Reorg columns
    result = result[['instance_id',
                    # Issue columns
                     'issue_scores', 'final_issue_score', 'issue_score_decision_method', 'controversial_issue_score_decision', 'good_issue',
                     'issue_score_labeller_1', 'issue_rationale_labeller_1', 'issue_score_labeller_2', 'issue_rationale_labeller_2', 'issue_score_labeller_3', 'issue_rationale_labeller_3',
                     # Test columns
                     'test_scores', 'final_test_score', 'test_score_decision_method', 'controversial_test_score_decision', 'good_tests',
                     'test_score_labeller_1', 'test_rationale_labeller_1', 'test_score_labeller_2', 'test_rationale_labeller_2', 'test_score_labeller_3', 'test_rationale_labeller_3',
                     # Difficulty columns
                     'difficulty_scores', 'final_difficulty_score', 'difficulty_score_decision_method', 'controversial_difficulty_score_decision',
                     'difficulty_score_labeller_1', 'difficulty_rationale_labeller_1', 'difficulty_score_labeller_2', 'difficulty_rationale_labeller_2', 'difficulty_score_labeller_3', 'difficulty_rationale_labeller_3'
                     ]]
    return result


def manual_verification(experiment_id):
    experiment_id = "swedata-labelround28-Group-B"
    post_processed_df = to_wide_format(experiment_id)

    # Prepare dataset for manual labelling
    post_processed_df.insert(6, 'good_issue_agree', "")
    post_processed_df.insert(7, 'good_issue_agree_why', "")
    post_processed_df.insert(19, 'good_tests_agree', "")
    post_processed_df.insert(20, 'good_tests_agree_why', "")
    post_processed_df.insert(29, 'difficulty_score_agree', "")
    post_processed_df.insert(30, 'difficulty_score_agree_why', "")

    root_dir = Path().resolve().parent
    post_processed_df.to_excel(
        root_dir / "results" / f"{experiment_id}.xlsx", index=False)


def deliver_to_pangu(experiment_id):

    df = to_wide_format(experiment_id)

    # Filter in non-controversial issues and tests
    filtered_df = df[(df['controversial_issue_score_decision'] == False) & (
        df['controversial_test_score_decision'] == False)]

    # Select only the necessary columns
    filtered_df = filtered_df[[
        'instance_id', 'final_issue_score', 'final_test_score', 'final_difficulty_score']]

    # Rename columns according to our current convention
    filtered_df.rename(columns={
        'instance_id': 'instance_id',
        'final_issue_score': 'task_score',
        'final_test_score': 'evaluation_score',
        'final_difficulty_score': 'difficulty_score'
    }, inplace=True)

    # Add the status column
    filtered_df['status'] = "Processed"

    # Save CSV
    filtered_df.to_csv(root_dir / "results" /
                       f"{experiment_id}-delivered-to-pangu.csv", index=False)


if __name__ == "__main__":
    experiment_id = "swedata-labelround29"
    deliver_to_pangu(experiment_id)
