from swebench_qa.core import SWEbenchLabeller
from pathlib import Path
import argparse

current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent

def parse_key_value_list(param_list):
    param_dict = {}
    for item in param_list:
        if '=' not in item:
            raise argparse.ArgumentTypeError(f"Invalid param format: {item}")
        key, value = item.split('=', 1)
        param_dict[key] = value
    return param_dict


def run():
    # Command line argument parsing
    parser = argparse.ArgumentParser(description='SWEbench Verifier')
    
    # Experiment required parameters
    parser.add_argument('--input', '-i', dest='swebench_path', type=str, required=True,                        help='Absolute path to the SWEbench-like input dataset file in parquet format')
    parser.add_argument('--experiment-id', '-e', dest='experiment_id', type=str, required=True,
                       help='Identifier for the experiment (reusing an ID will resume the experiment)')
    parser.add_argument('--experiment-desc', '-d', dest='experiment_description', type=str, required=True,
                       help='Description of the experiment being run')
    
    # Experiment optional parameters
    parser.add_argument('--skip-instances', '-s', dest='instances_to_skip', default=None, 
                        type=lambda s: [item.strip() for item in s.split(',')], 
                        help="Comma-separated list of strings to skip.")
    
    # Labeller parameters
    parser.add_argument('--issue-labeler', choices=['default', 'stub'], default='default')
    parser.add_argument('--issue-labeler-param', action='append', default=[], help='key=value', type=str)
    parser.add_argument('--test-labeler', choices=['default', 'stub'], default='default')
    parser.add_argument('--test-labeler-param', action='append', default=[], help='key=value', type=str)
    parser.add_argument('--difficulty-labeler', choices=['default', 'stub'], default='default')
    parser.add_argument('--difficulty-labeler-param', action='append', default=[], help='key=value', type=str)
    
    # Parallel processing parameters
    parser.add_argument('--parallel', action='store_true', default=False,
                       help='Enable repo-parallel processing (recommended for faster execution)')
    parser.add_argument('--max-workers', type=int, default=30,
                       help='Maximum number of repos to process in parallel (default: 30)')

    args = parser.parse_args()

    # Convert lists of key=value (labeller params) into dictionaries
    issue_params = parse_key_value_list(args.issue_labeler_param)
    test_params = parse_key_value_list(args.test_labeler_param)
    difficulty_params = parse_key_value_list(args.difficulty_labeler_param)

    label_result_dir = root_dir / 'results'

    swebench_labeller = SWEbenchLabeller(
        experiment_id = args.experiment_id,
        experiment_description=args.experiment_description,
        swebench_path=args.swebench_path,
        label_result_dir=label_result_dir,
        issue_labeller=args.issue_labeler,
        issue_labeller_params=issue_params,
        test_labeller=args.test_labeler,
        test_labeller_params=test_params,
        difficulty_labeller=args.difficulty_labeler,
        difficulty_labeller_params=difficulty_params,
        instances_to_skip=args.instances_to_skip,
        repetitions = 3, 
    )
    
    # Choose between parallel and sequential processing
    if args.parallel:
        print(f"Using repo-parallel processing with max_workers={args.max_workers}")
        swebench_labeller.label_parallel_by_repo(max_workers=args.max_workers)
    else:
        print("Using sequential processing")
        swebench_labeller.label()

if __name__ == "__main__":
    run()