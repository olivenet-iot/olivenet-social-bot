"""
Quality Gate - Merkezi kalite kontrol mekanizması
"""

from typing import Dict, Any

from app.utils.logger import get_logger

logger = get_logger("quality_gate")

# Varsayılan eşikler
DEFAULT_MIN_SCORE = 7.0
AUTONOMOUS_MIN_SCORE = 7.0
REVISION_MIN_SCORE = 5.0


class QualityGate:
    """
    İçerik kalite kontrolü.
    ReviewerAgent'ı çağırır ve skor eşiklerine göre karar verir.
    """

    def __init__(
        self,
        min_score: float = DEFAULT_MIN_SCORE,
        autonomous_min: float = AUTONOMOUS_MIN_SCORE,
        max_revisions: int = 2
    ):
        self.min_score = min_score
        self.autonomous_min = autonomous_min
        self.max_revisions = max_revisions

    async def check(
        self,
        reviewer,
        post_text: str,
        topic: str,
        is_autonomous: bool = False
    ) -> Dict[str, Any]:
        """
        İçeriği review et ve sonuç döner.

        Returns:
            {
                "passed": bool,
                "score": float,
                "decision": str,
                "feedback": str,
                "review": dict
            }
        """
        threshold = self.autonomous_min if is_autonomous else self.min_score

        review_result = await reviewer.execute({
            "action": "review_post",
            "post_text": post_text,
            "topic": topic
        })

        score = review_result.get("total_score", 0)
        decision = review_result.get("decision", "reject")
        feedback = review_result.get("feedback", "")

        passed = score >= threshold or decision == "approve"

        logger.info(
            f"Quality gate: score={score}, threshold={threshold}, "
            f"passed={passed}, decision={decision}"
        )

        return {
            "passed": passed,
            "score": score,
            "decision": decision,
            "feedback": feedback,
            "review": review_result,
            "can_revise": decision == "revise" and score >= REVISION_MIN_SCORE
        }

    async def review_and_revise(
        self,
        reviewer,
        creator,
        post_text: str,
        topic: str,
        is_autonomous: bool = False
    ) -> Dict[str, Any]:
        """
        Review + otomatik revision döngüsü.
        max_revisions kadar deneme yapar.
        """
        current_text = post_text

        for attempt in range(self.max_revisions + 1):
            result = await self.check(reviewer, current_text, topic, is_autonomous)

            if result["passed"]:
                result["post_text"] = current_text
                result["revision_count"] = attempt
                return result

            if attempt < self.max_revisions and result["can_revise"]:
                logger.info(f"Revising (attempt {attempt + 1}): {result['feedback'][:80]}")

                revise_result = await creator.execute({
                    "action": "revise_post",
                    "original_text": current_text,
                    "feedback": result["feedback"],
                    "topic": topic
                })
                current_text = revise_result.get("revised_text", current_text)
            else:
                break

        # Son deneme başarısız
        result["post_text"] = current_text
        result["revision_count"] = self.max_revisions
        return result
