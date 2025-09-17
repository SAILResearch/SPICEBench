from datetime import datetime
from swebench_qa.aider.aider import Aider
from unidiff import PatchSet
from io import StringIO
from pathlib import Path

class AiderLabellingUtils():
    '''Utilities method meant to support labelling with Aider.'''

    @staticmethod
    def get_Aider(strong_model, instance_id, repo_path, log_dir) -> Aider:

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]  # Trim microseconds to milliseconds
        log_dir = Path(log_dir)
        log_file = log_dir / f'{instance_id}-aider-chat-history-{timestamp}.md'
        
        aider = Aider(
            model = strong_model,
            git_dname = repo_path,
            chat_history_file = log_file,
            verbose = False,
            stream = False,
            auto_commits = False, # don't bother auto-commiting
            yes_always = False, # always answer 'no' ('yes' is too dangerous, since it could end up adding a huge file or trying to open a web URL. in the future, we could (i) have it answer 'yes' to everything except predefined questions and (ii) check whether the file that it wants to add would fit the context window)
            detect_urls = False, # do not try to detect and scrape URLs
        )

        return aider

    @staticmethod
    def add_files_to_Aider(aider:Aider, patch:str, test_patch:str, instruction:str, threshold = 0.8):
        """
        Adds as many files as possible to Aider's context without blowing the context window
        """

        # Retrieve file names from patches
        patch_files = []
        parsed_patch = PatchSet(StringIO(patch))        
        for file in parsed_patch:
            if not file.is_added_file:
                patch_files.append(file.source_file.removeprefix('a/')) 

        test_patch_files = []
        parsed_test_patch = PatchSet(StringIO(test_patch))
        for file in parsed_test_patch:
            if not file.is_added_file:
                test_patch_files.append(file.source_file.removeprefix('a/')) 

        candidate_files = patch_files + test_patch_files
        
        # Estimate how many tokens each file will burn and put in a sorted list
        candidate_file_token_tuples = []
        for candidate_file in candidate_files:
            tokens = aider.estimate_file_token_usage(candidate_file, relative=True)
            candidate_file_token_tuples.append((candidate_file, tokens))
        candidate_file_token_tuples.sort(key=lambda item: item[1])

        # Compute some limits
        ctx_window_tks = aider.estimate_context_window_token_usage()
        
        instruction_tks = aider.estimate_message_token_usage(instruction)
        total_tks_so_far = ctx_window_tks['total_tokens'] + instruction_tks
        
        ctx_window_size = ctx_window_tks['context_window_size']        
        limit = ctx_window_size * threshold

        # Now let's add as many files as we can
        files_to_add = []
        while candidate_file_token_tuples:
            candidate_file, tokens = candidate_file_token_tuples.pop(0)
            total_tks_so_far += tokens
            if total_tks_so_far <= limit:
                files_to_add.append(candidate_file)
            else:
                print(f"Warning: failed to add all gold/test patch files. File {candidate_file} is likely too large with {tokens} tokens")
                break
         
        files_to_add = " ".join(files_to_add)
        command = f"/read-only {files_to_add}"
        aider.run(command)