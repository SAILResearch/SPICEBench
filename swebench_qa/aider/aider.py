from datetime import datetime
from pathlib import Path
from aider.utils import is_image_file
from aider.commands import SwitchCoder
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from aider.repo import GitRepo
from pathlib import Path

# Define StrPath as a shorthand for string and Path
StrPath = str | Path

class Aider:
    """
    A minimalist API for Aider. Aims to follow the same CLI defaults with the following exceptions:
    -  yes_always defaults to None in CLI, so we set it to False here. Compatible with Aider 0.82.2
    """

    def __init__(self, model, git_dname, chat_history_file = None, input_history_file = None, fnames = None, verbose = False, stream = True, map_tokens = None, map_multiplier_no_files = 2, auto_commits = True, yes_always = False, map_refresh = "auto", cache_prompts = False, cache_keepalive_pings = 0, detect_urls = True):

        # Written based on aider/main.py/main() (Aider v0.82.2)
        # TODO: Refactor to reuse main() by passing return_coder=True for better maintainability

        if cache_prompts and map_refresh == "auto":
            map_refresh = "files"

        # fnames should be relative to git repo. Here we build the absolute path
        if fnames:
            fnames = [Path(git_dname) / fname for fname in fnames]

        # Init model and figure out the appropriate number of repo map tokens 
        # for the chosen model
        model = Model(model, verbose = verbose)
        if map_tokens is None:
            map_tokens = model.get_repo_map_tokens() 

        # IO with sensible default
        self.io = InputOutput(
            yes=yes_always,  
            chat_history_file=chat_history_file,  
            input_history_file=input_history_file,
        )

        # Init the git repo
        repo = GitRepo(self.io,  fnames=None, git_dname=git_dname, models=model.commit_message_models())

        self.coder = Coder.create(
            main_model=model,
            io=self.io,
            repo=repo,
            fnames=fnames,
            map_tokens=map_tokens,
            map_refresh=map_refresh,
            verbose=verbose,
            stream = stream,
            auto_commits = auto_commits,
            map_mul_no_files = map_multiplier_no_files,
            detect_urls = detect_urls
        )
       
        # Internal parameters that can also be changed
        # coder.temperature = some_temp
        # coder.max_reflections = 4

        # Add announcement lines to the markdown chat log
        self.coder.show_announcements()

        # Set up cache warming
        self.cache_keepalive_pings = cache_keepalive_pings
        self.coder.ok_to_warm_cache = bool(cache_keepalive_pings)

        # TODO: Implement progress message display for API usage
        # CLI verbose mode shows more messages than this API implementation

    def estimate_context_window_token_usage(self):
        # Written based on aider/commands.py/cmd_tokens (Aider v0.82.2)
        
        res = {}
        res['total_tokens'] = 0

        self.coder.choose_fence()

        # system messages
        main_sys = self.coder.fmt_system_prompt(self.coder.gpt_prompts.main_system)
        main_sys += "\n" + self.coder.fmt_system_prompt(self.coder.gpt_prompts.system_reminder)
        msgs = [
            dict(role="system", content=main_sys),
            dict(
                role="system",
                content=self.coder.fmt_system_prompt(self.coder.gpt_prompts.system_reminder),
            ),
        ]

        tokens = self.coder.main_model.token_count(msgs)
        res['system_messages'] = tokens
        res['total_tokens'] += tokens

        # chat history
        msgs = self.coder.done_messages + self.coder.cur_messages
        if msgs:
            tokens = self.coder.main_model.token_count(msgs)
            res['chat_history'] = tokens
            res['total_tokens'] += tokens
        else:
            res['chat_history'] = 0

        # repo map
        other_files = set(self.coder.get_all_abs_files()) - set(self.coder.abs_fnames)
        if self.coder.repo_map:
            repo_content = self.coder.repo_map.get_repo_map(self.coder.abs_fnames, other_files)
            if repo_content:
                tokens = self.coder.main_model.token_count(repo_content)
                res['repo_map'] = tokens
                res['total_tokens'] += tokens

        # TODO: Standardize image handling between files and read-only files
        # TODO: Clarify image file naming requirements
        # files
        fence = "`" * 3
        res['files'] = []
        
        for fname in self.coder.abs_fnames:
            relative_fname = self.coder.get_rel_fname(fname)
            content = self.io.read_text(fname)
            if is_image_file(relative_fname):
                tokens = self.coder.main_model.token_count_for_image(fname)
            else:
                # approximate
                content = f"{relative_fname}\n{fence}\n" + content + "{fence}\n"
                tokens = self.coder.main_model.token_count(content)
            
            res['files'].append({f"{relative_fname}": tokens})
            res['total_tokens'] += tokens

        # read-only files
        res['read_only_files'] = []
        for fname in self.coder.abs_read_only_fnames:
            relative_fname = self.coder.get_rel_fname(fname)
            content = self.io.read_text(fname)
            if content is not None and not is_image_file(relative_fname):
                # approximate
                content = f"{relative_fname}\n{fence}\n" + content + "{fence}\n"
                tokens = self.coder.main_model.token_count(content)
                res['read_only_files'].append({f"{relative_fname}": tokens})
                res['total_tokens'] += tokens

        # Calculate token summary
        res['context_window_size'] = self.coder.main_model.info.get("max_input_tokens")
        res['remaining_tokens'] = res['context_window_size'] - res['total_tokens']
        
        # Return a dictionary like this
        return res

    def estimate_message_token_usage(self, message):
        tokens = self.coder.main_model.token_count(message)
        return tokens

    def estimate_file_token_usage(self, file_path:StrPath, relative = False):
        # file_path must exist and live inside the repo that Aider's working with
        # TODO: Refactor to eliminate code duplication with estimate_context_window_token_usage()

        if relative:
            abs_file_path = self.coder.abs_root_path(file_path)
            relative_fname = file_path
        else:
            abs_file_path = file_path
            relative_fname = self.coder.get_rel_fname(abs_file_path)

        fence = "`" * 3
        content = self.io.read_text(abs_file_path)
        if is_image_file(relative_fname):
            tokens = self.coder.main_model.token_count_for_image(abs_file_path)
        else:
            # approximate
            content = f"{relative_fname}\n{fence}\n" + content + "{fence}\n"
            tokens = self.coder.main_model.token_count(content)
        
        return tokens

    def run(self, with_message = None, preproc = True) -> str:

        # Written based on while true loop in aider/main.py/main() 
        # (Aider v0.82.2)

        try:
            self.coder.run(with_message, preproc)
        
        except SwitchCoder as switch:
            # This is not a real error. According to ChatGPT (GPT 4.5):
            # "This exception is not an error in the traditional sense. Rather, it's a control-flow mechanism used internally by Aider to switch between different coder instances or states after command execution. Specifically, it signals Aider to update its active coder state with the changes or results produced by the temporary coder instance that executed your command."            
            
            self.coder.ok_to_warm_cache = False

            # Set the placeholder if provided
            if hasattr(switch, "placeholder") and switch.placeholder is not None:
                self.io.placeholder = switch.placeholder

            kwargs = dict(io=self.io, from_coder=self.coder)
            kwargs.update(switch.kwargs)
            if "show_announcements" in kwargs:
                del kwargs["show_announcements"]

            self.coder = Coder.create(**kwargs)

            if switch.kwargs.get("show_announcements") is not False:
                self.coder.show_announcements()

            output = switch.kwargs['from_coder'].partial_response_content
            self.coder.ok_to_warm_cache = bool(self.cache_keepalive_pings)
            return output
        
        finally:
            # log end of operation to chat history
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # append to the MD log file
            if getattr(self.io, 'chat_history_file', None):
                with open(self.io.chat_history_file, 'a') as fh:
                    fh.write(f"\n\n**Operation ended at {end_time}**\n")
