from abc import ABC, abstractmethod
from swebench_qa.base_labellers import IssueLabeller
from swebench_qa.issue_labeller.labeller_utils import LabellerUtils
from dataclasses import dataclass
import asyncio
from pathlib import Path
import logging
from logging import getLogger

############# Base Interface #############


class BasePipeline(ABC):
    @abstractmethod
    async def run(self, issue: dict, model: str, provider: str) -> dict:
        pass


############# NAIVE Pipeline #############

class NaivePipeline(BasePipeline):
    async def run(self, issue: dict, model: str, provider: str) -> dict:
        prompt_template = LabellerUtils.load_prompt("issue_labeller", "naive")
        title = LabellerUtils.strip_markdown(issue.get("title", ""))
        description = LabellerUtils.strip_markdown(
            issue.get("description", ""))
        prompt = prompt_template.format(title=title, description=description)
        logger = getLogger("litellm")
        logger.info(
            f"INSTANCE={issue['instance_id']}")  # title={title} description={description}")

        result = await LabellerUtils.request_model(prompt, model, provider)

        return {
            "actor_explanation": result.get("explanation"),
            "actor_score": LabellerUtils.binarize_score(result.get("score")),
            "actor_candidate_solution": result.get("candidate_solution"),
            "critique_feedback": None,
            "critique_suggested_score": None,
            "judge_final_explanation": result.get("explanation"),
            "judge_final_score": LabellerUtils.binarize_score(result.get("score")),
            "judge_candidate_solution": result.get("candidate_solution")
        }


############# ACTOR-CRITIQUE-JUDGE Pipeline #############

class ActorCritiqueJudgePipeline(BasePipeline):
    async def run(self, issue: dict, model: str, provider: str) -> dict:
        title = LabellerUtils.strip_markdown(issue.get("title", ""))
        description = LabellerUtils.strip_markdown(
            issue.get("description", ""))

        # ACTOR
        actor_prompt = LabellerUtils.load_prompt(
            "issue_labeller", "actor_critique_judge", "actor")
        actor_filled = actor_prompt.format(
            title=title, description=description)
        actor_result = LabellerUtils.recursive_normalize(
            await LabellerUtils.request_model(actor_filled, model, provider)
        )

        # CRITIQUE
        critique_prompt = LabellerUtils.load_prompt(
            "issue_llabeler", "actor_critique_judge", "critique")
        critique_filled = critique_prompt.format(
            title=title,
            description=description,
            actor_explanation=actor_result.get("explanation", ""),
            actor_score=actor_result.get("score", ""),
            actor_candidate_solution=actor_result.get("candidate_solution", "")
        )
        critique_result = LabellerUtils.recursive_normalize(
            await LabellerUtils.request_model(critique_filled, model, provider)
        )

        # JUDGE
        judge_prompt = LabellerUtils.load_prompt(
            "issue_labeller", "actor_critique_judge", "judge")
        judge_filled = judge_prompt.format(
            title=title,
            description=description,
            actor_explanation=actor_result.get("explanation", ""),
            actor_score=actor_result.get("score", ""),
            actor_candidate_solution=actor_result.get(
                "candidate_solution", ""),
            critique_feedback=critique_result.get("feedback", ""),
            critique_suggested_score=critique_result.get("suggested_score", "")
        )
        judge_result = LabellerUtils.recursive_normalize(
            await LabellerUtils.request_model(judge_filled, model, provider)
        )

        return {
            "actor_explanation": actor_result.get("explanation"),
            "actor_score": actor_result.get("score"),
            "actor_candidate_solution": actor_result.get("candidate_solution"),
            "critique_feedback": critique_result.get("feedback"),
            "critique_suggested_score": critique_result.get("suggested_score"),
            "judge_final_explanation": judge_result.get("final_explanation"),
            "judge_final_score": judge_result.get("final_score"),
            "judge_candidate_solution": judge_result.get("candidate_solution")
        }


############# Director #############

class PipelineDirector:
    _registry = {
        "naive": NaivePipeline(),
        "actor_critique_judge": ActorCritiqueJudgePipeline()
    }

    @classmethod
    def get_pipeline(cls, strategy_name: str) -> BasePipeline:
        if strategy_name not in cls._registry:
            raise ValueError(
                f"Unknown pipeline strategy '{strategy_name}'. "
                f"Available: {list(cls._registry.keys())}"
            )
        return cls._registry[strategy_name]

############# The issue labeller #############


@dataclass
class IssueLabellerConfig:
    strategy: str           # e.g., "naive" or "actor_critique_judge"
    model: str              # e.g., "gpt-4o-mini"
    provider: str           # e.g., "openai"
    task: str = "issue_labeler"  # Default task


class DefaultIssueLabeller(IssueLabeller):

    def __init__(self, config: IssueLabellerConfig):
        super().__init__()
        self.config = config
        self._litellm_logger = None    # placeholder

    # ← Override the public entrypoint, not the private _label_issue
    def label_issue(self, issue_title: str, issue_body: str):
        # 1) By now SWEbenchLabeller.loop has done:
        #    self.issue_labeller.environment = Environment(..., log_dir=...)
        # so self.environment.log_dir is valid
        if self._litellm_logger is None:
            log_path = Path(self.environment.log_dir) / "litellm.log"
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            logger = logging.getLogger("litellm")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            self._litellm_logger = logger

        # 2) Now call the base implementation, which calls _label_issue under the hood
        return super().label_issue(issue_title, issue_body)

    def _label_issue(self, issue_title: str, issue_body: str):
        try:
            issue = {
                "title": issue_title,
                "description": issue_body,
                "instance_id": self.environment.instance_id,
            }

            pipeline = PipelineDirector.get_pipeline(self.config.strategy)
            pipeline_result = asyncio.run(
                pipeline.run(issue, self.config.model, self.config.provider)
            )

            score = pipeline_result.get("judge_final_score")
            rationale = pipeline_result.get("judge_final_explanation")
            has_solution = pipeline_result.get("judge_candidate_solution")
            return (score, rationale, has_solution)

        except Exception as e:
            instance_id = getattr(self.environment, "instance_id", "UNKNOWN")
            error_msg = f"[DefaultIssueLabeller] Error for instance {instance_id}: {e}"
            print(error_msg)
            return (-1, error_msg, False)
