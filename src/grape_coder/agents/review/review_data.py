from dataclasses import dataclass, field
from typing import List, Dict, Any


# Reuse CategoryScore from reviewer.py
from .reviewer import CategoryScore, Task


@dataclass
class ReviewData:
    category_scores: List[CategoryScore] = field(default_factory=list)
    summary: str = ""
    tasks: List[Task] = field(default_factory=list)
    review_feedback: str = ""
    approved: bool = False
    iteration: int = 0
    raw_output: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_score(self, category: str) -> int:
        for score in self.category_scores:
            if score.name.lower() == category.lower():
                return score.score
        return 0

    def get_failed_categories(self, threshold: int = 15) -> List[str]:
        return [s.name for s in self.category_scores if s.score < threshold]

    def average_score(self) -> float:
        if not self.category_scores:
            return 0.0
        return sum(s.score for s in self.category_scores) / len(self.category_scores)
