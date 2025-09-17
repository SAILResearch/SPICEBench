from pathlib import Path

class PromptUtils:
   
    @staticmethod
    def read_prompt(prompt_name: str, category: str = None) -> str:
        """Read prompt from markdown file.
        
        Args:
            prompt_name: Name of the prompt file without .md extension
            category: Optional subdirectory under prompts/
            
        Returns:
            String content of the prompt file
        """
        base_path = Path(__file__).parent
        if category:
            prompt_path = base_path / category / f"{prompt_name}.md"
        else:
            prompt_path = base_path / f"{prompt_name}.md"
            
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        with open(prompt_path) as f:
            return f.read()
    
    @staticmethod
    def format_prompt(prompt_text: str, **kwargs) -> str:
        """Format a prompt template with the given kwargs.
        
        Args:
            prompt_text: The template text with {placeholders}
            **kwargs: The values to replace placeholders with
            
        Returns:
            The formatted prompt text
        """
        try:
            return prompt_text.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required placeholder in prompt: {e}")