from abc import ABC, abstractmethod
from swebench_qa.environment import Environment
import logging

# TODO: Standardize logging across the project and integrate Aider logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Labeller(ABC):

    def __init__(self):
        self.environment : Environment = None
        
    def __repr__(self):
        return f"{self.__class__.__name__}({self.__dict__})"

class IssueLabeller(Labeller):
    """Base class for issue labellers."""

    def __init__(self):
        super().__init__()

    def label_issue(self, issue_title:str, issue_body:str):
        try:
            score, rationale, has_solution = self._label_issue(issue_title, issue_body)
        except Exception as e:
            instance_id = self.environment.instance_id
            error_msg = f"Error labeling issue for instance {instance_id}: {e}"
            print(error_msg)
            score, rationale, has_solution = -1, error_msg, False
        return score, rationale, has_solution

    @abstractmethod
    def _label_issue(self, issue_title:str, issue_body:str):
        # Return a tuple with (score, rationale)
        pass

class StubIssueLabeller(IssueLabeller):

    def __init__(self):
        super().__init__()
    
    def _label_issue(self, issue_title:str, issue_body:str):
        score, rationale, has_solution = -1, "Stub Labeller", False
        return score, rationale, has_solution

        
class TestLabeller(Labeller):
    """
    Base class for test labellers.
    """

    def __init__(self):
        super().__init__()

    def label_test(self, issue_title:str, issue_body:str, patch:str, test_patch:str):
        try:
            score, rationale = self._label_test(issue_title, issue_body, patch, test_patch)
        except Exception as e:
            instance_id = self.environment.instance_id
            error_msg = f"Error labeling test for instance {instance_id}: {e}"
            print(error_msg)
            score, rationale = -1, error_msg
        return score, rationale
    
    @abstractmethod
    def _label_test(self, issue_title:str, issue_body:str, patch:str, test_patch:str):
        """
        Abstract method to be implemented by subclasses.
        
        Args:
            issue_title: Title of the issue
            issue_body: Body of the issue
            patch: The code patch
            test_patch: The test patch
            
        Returns:
            A tuple with (score, rationale)
        """
        pass

class StubTestLabeller(TestLabeller):

    def __init__(self):
        super().__init__()

    def _label_test(self, issue_title:str, issue_body:str, patch:str, test_patch:str):
        
        # Return a tuple with (score, rationale)
        return -1, "Stub Labeller"
    
class DifficultyLabeller(Labeller):

    def __init__(self):
        super().__init__()

    def label_difficulty(self, issue_title:str, issue_body:str, patch, test_patch):
        try:
            score, rationale = self._label_difficulty(issue_title, issue_body, patch, test_patch)
        except Exception as e:
            instance_id = self.environment.instance_id
            error_msg = f"Error labeling difficulty for instance {instance_id}: {e}"
            print(error_msg)
            score, rationale = -1, error_msg
        return score, rationale

    @abstractmethod
    def _label_difficulty(self, issue_title:str, issue_body:str, patch:str, test_patch:str):
        """
        Abstract method to be implemented by subclasses.
        
        Returns:
            A tuple with (score, rationale)
        """
        pass

class StubDifficultyLabeller(DifficultyLabeller):

    def __init__(self):
        super().__init__()

    def _label_difficulty(self, issue_title:str, issue_body:str, patch:str, test_patch:str):
        return -1, "Stub Labeller"

