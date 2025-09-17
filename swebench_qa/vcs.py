import giturlparse
from pathlib import Path
from tqdm import tqdm
from git import Repo
from git.util import RemoteProgress

class GitUtils:
    
    @staticmethod
    def clone_url_parser(clone_url):
        return giturlparse.parse(clone_url)

    @staticmethod
    def clone_repo(clone_url, to_path):

        class CloneProgress(RemoteProgress):
            def __init__(self):
                super().__init__()
                self.pbar = tqdm()

            def update(self, op_code, cur_count, max_count=None, message=''):
                self.pbar.total = max_count
                self.pbar.n = cur_count
                self.pbar.refresh()

        # Path where the repo will be cloned
        to_path = Path(to_path)

        print(f"Cloning git repo at {clone_url} to {to_path}")
        repo = Repo.clone_from(
            url = clone_url, 
            to_path= to_path,
            progress=CloneProgress()
        )        
        repo.close()

        return to_path


    @staticmethod
    def checkout_commit(repo_path, commit):
        print(f"Checking out commit {commit}")
        repo = Repo(repo_path)        
        repo.git.checkout(commit)
        repo.close()