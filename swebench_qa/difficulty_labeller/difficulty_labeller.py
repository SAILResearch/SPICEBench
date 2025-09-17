import litellm
from swebench_qa.base_labellers import DifficultyLabeller
from swebench_qa.aider.aider_utils import AiderLabellingUtils
from swebench_qa.prompts.prompt import PromptUtils
from swebench_qa.postprocess import parse_score


class AiderDifficultyLabeller(DifficultyLabeller):

    def __init__(self, strong_model, weak_model):
        super().__init__()
        self.strong_model = strong_model
        self.weak_model = weak_model

    def _label_difficulty(self, issue_title: str, issue_body: str, patch: str, test_patch: str):

        # Obtain aider
        aider = AiderLabellingUtils.get_Aider(
            self.strong_model, self.environment.instance_id, self.environment.repo_path, self.environment.log_dir)

        # Read the prompts
        general_context = PromptUtils.read_prompt(
            'general_context', 'difficulty_labeller')
        task_template = PromptUtils.read_prompt(
            'task_template', 'difficulty_labeller')
        warning = PromptUtils.read_prompt('warning', 'difficulty_labeller')

        # Format the task template with values
        task = PromptUtils.format_prompt(task_template,
                                         issue_title=issue_title,                                  issue_body=issue_body,
                                         patch=patch,
                                         test_patch=test_patch)

        assembled_instruction = "\n\n".join([
            general_context,
            task,
            warning
        ])

        # Add files to Aider without blowing up the context window
        AiderLabellingUtils.add_files_to_Aider(
            aider, patch, test_patch, assembled_instruction, 0.8)

        # Ask it to label
        ask_label_cmd = f"/ask {assembled_instruction}"
        labelling_with_reasoning = aider.run(ask_label_cmd)

        # Now extract the score using a weak model
        score = self._extract_score(labelling_with_reasoning)

        return score, labelling_with_reasoning

    def _extract_score(self, labelling_with_reasoning) -> int:
        system_prompt = PromptUtils.read_prompt(
            'extract_score', 'difficulty_labeller')

        messages = [
            {"content": system_prompt, "role": "developer"},
            {"content": labelling_with_reasoning, "role": "user"}
        ]
        
        call_kwargs = {
            "model": self.weak_model,
            "messages": messages,
        }
        if self.weak_model.startswith("ollama/"):
            # Use environment variable for local model server
            local_server = os.environ.get("LOCAL_MODEL_SERVER", "localhost:11434")
            call_kwargs["api_base"] = f"http://{local_server}"
        # Note: For openrouter/ models, litellm automatically detects OPENAI_API_KEY and OPENAI_API_BASE from environment variables
        response = litellm.completion(**call_kwargs)
        raw_out = response['choices'][0]['message']['content']

        try:
            return parse_score(raw_out.strip())
        except ValueError:
            # *retry once*
            resp = litellm.completion(**call_kwargs)
            raw_out = resp['choices'][0]['message']['content']
            return parse_score(raw_out.strip())
