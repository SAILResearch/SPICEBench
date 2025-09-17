import pandas as pd
import math
from pathlib import Path

data_dir = Path(__file__).resolve().parent.parent / 'data'
swebench_annotated_path = data_dir / 'ensembled_annotations_public.csv'
swebench_test_path = data_dir / 'test-00000-of-00001.parquet'

swebench_annotated_full = data_dir / 'swebench-annotated-full.parquet'
swebench_annotated_sample = data_dir / 'swebench-annotated-sample.parquet'
swebench_annotated_micro = data_dir / 'swebench-annotated-micro.parquet'


# Sample size calculation function
def calculate_sample_size(population_size, margin_of_error=0.05, p=0.5):
    z = 1.96  # Z-score for 95% confidence
    e = margin_of_error
    n = (z**2 * p * (1 - p)) / (e**2)
    n_adj = n / (1 + ((n - 1) / population_size))
    return math.ceil(n_adj)


def create_datasets():

    # Load labelled dataset
    swebench_annotated = pd.read_csv(swebench_annotated_path)
    print(swebench_annotated.head())

    # Filter in rows where there was some consensus on task difficulty
    swebench_annotated = swebench_annotated[swebench_annotated['difficulty_ensemble_decision_procedure'] == 'majority']

    # Load test split of full swebench dataset
    swebench_testsplit = pd.read_parquet(swebench_test_path)

    # Now let's do an inner join with the two dfs
    merged_df = pd.merge(swebench_annotated, swebench_testsplit, on='instance_id')
    print(len(merged_df))
    print(merged_df.head())

    # Let's save it
    # merged_df.to_parquet(swebench_annotated_full, index = False)

    # Number of instances per repo
    instances_per_prj = merged_df.groupby('repo').size().reset_index(name='counts').sort_values('counts', ascending=False)

    print(instances_per_prj)

    # Draw a statistically representative sample
    stat_sample_df = (
        merged_df.groupby('repo')[merged_df.columns]
        .apply(lambda x: x.sample(n=calculate_sample_size(len(x)), random_state=666))
        .reset_index(drop=True)
    )

    print(len(stat_sample_df))
    stat_sample_df.to_parquet(swebench_annotated_sample, index = False)

    # Draw a maximum of 10 samples
    micro_sample_df = (
        merged_df.groupby('repo')[merged_df.columns]
        .apply(lambda x: x.sample(n=min(10, len(x)), random_state=666))
        .reset_index(drop=True)
    )

    print(len(micro_sample_df))
    micro_sample_df.to_parquet(swebench_annotated_micro, index = False)

if __name__ == "__main__":
    create_datasets()


# Instances used for test criteria examples:
# ['django__django-10097', 'django__django-16667', 'django__django-11905', 'django__django-14399']
