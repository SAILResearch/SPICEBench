import re
import json
import markdown2
from pathlib import Path
from markdownify import markdownify as md_to_text
from swebench_qa.issue_labeller.model_provider import ModelProviderDirector


class LabellerUtils:
    ##################################
    # Markdown / Text Processing
    ##################################

    @staticmethod
    def strip_markdown(md_text: str) -> str:
        """Convert markdown to plain text."""
        if not md_text:
            return ""
        html = markdown2.markdown(md_text)
        return md_to_text(html).strip()

    @staticmethod
    def strip_think(text: str) -> str:
        """Remove <think>...</think> blocks from model output."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    ##################################
    # Label Mapping Utilities
    ##################################

    @staticmethod
    def binarize_score(label):
        """
        Convert textual/numeric label to binary value.
        Returns: 0 = well-specified, 1 = underspecified, or None
        """
        if isinstance(label, str):
            l = label.strip().lower()
            if l in ["well-specified", "well specified", "well"]:
                return 0
            elif l in ["underspecified", "under-specified", "under"]:
                return 1
        try:
            val = int(label)
            if val in [0, 1]:
                return 0
            elif val in [2, 3]:
                return 1
        except Exception:
            return None

    @staticmethod
    def label_text(binary_val: int) -> str:

        return "well-specified" if binary_val == 0 else "underspecified"

    ##################################
    # JSON Handling from LLM Output
    ##################################

    @staticmethod
    def extract_last_valid_json_block(text: str, required_keys=("explanation", "score", "candidate_solution")):
        """Scan backwards to find the last valid JSON block with required keys."""
        for end in reversed(range(len(text))):
            if text[end] != "}":
                continue
            for start in reversed(range(0, end)):
                if text[start] == "{":
                    candidate = text[start:end + 1]
                    if all(k in candidate for k in required_keys):
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            continue
        return None

    @staticmethod
    def recursive_normalize(obj):
        """Recursively strip whitespace from dictionary keys."""
        if isinstance(obj, dict):
            return {k.strip(): LabellerUtils.recursive_normalize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [LabellerUtils.recursive_normalize(elem) for elem in obj]
        return obj

    ##################################
    # Model Call via Strategy Pattern
    ##################################

    @staticmethod
    def load_prompt(task: str, strategy: str, stage: str = None) -> str:
        """
        Load prompt from structured directory.

        Example paths:
            [base_dir]/prompts/issue_labeller/naive/naive_prompt.txt
            [base_dir]/prompts/issue_labeller/actor_critique_judge/actor.txt

        Parameters:
            task (str): e.g., 'issue_labeler'
            strategy (str): e.g., 'naive' or 'actor_critique_judge'
            stage (str or None): e.g., 'actor', 'critique', 'judge', or None (for single-prompt strategies)

        Returns:
            str: the loaded prompt template
        """
        if stage:
            file_name = f"{stage}.txt"
        else:
            file_name = f"{strategy}_prompt.txt"

        base_dir = Path(__file__).resolve().parent.parent
        prompt_path = base_dir / "prompts" / task / strategy / file_name

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

        ##################################
        # Model Call via Strategy Pattern
        ##################################

    @staticmethod
    async def request_model(prompt: str, model: str, provider_name: str, max_retries: int = 3):
        """
        Delegates model calls to the correct provider strategy.
        On failure, returns a mock JSON with None values instead of raising an error.
        """

        provider = ModelProviderDirector.get_provider(provider_name)
        expected_keys = ["explanation", "score", "candidate_solution"]

        for attempt in range(max_retries):
            try:
                # TODO: Refactor reasoning model handling for better extensibility
                raw_content = await provider.request(prompt, model)
                raw_content = LabellerUtils.strip_think(raw_content)
                return LabellerUtils.extract_last_valid_json_block(raw_content)

            except Exception as e:
                if attempt < max_retries - 1:
                    print(
                        f"[Retry {attempt + 1}] {provider_name} model '{model}' failed: {e}")
                else:
                    print(
                        f"[WARNING] Final failure for model '{model}' using provider '{provider_name}': {e}")
                    # Return a fallback so the rest of the pipeline can continue
                    return {key: None for key in expected_keys}
