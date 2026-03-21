"""
Base Pipeline - Tüm production pipeline'larının temel sınıfı.
ContentPipeline'dan extract edilmiş ortak logic.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from app.utils.logger import get_logger
from app.production.utils import PipelineState

logger = get_logger("pipeline")


class BasePipeline(ABC):
    """
    Ortak pipeline logic.

    Her pipeline türü (reels, carousel, post, news_reels, vb.)
    bu sınıftan türer ve run() metodunu implement eder.
    """

    def __init__(self, pipeline_name: str, telegram_callback: Optional[Callable] = None):
        self.pipeline_name = pipeline_name
        self.state = PipelineState.IDLE
        self.current_data = {}
        self.telegram_callback = telegram_callback
        self.approval_event = asyncio.Event()
        self.approval_response = None

        # Agent'ları lazy-load et
        from app.agents import (
            PlannerAgent,
            CreatorAgent,
            ReviewerAgent,
            PublisherAgent
        )

        self.planner = PlannerAgent()
        self.creator = CreatorAgent()
        self.reviewer = ReviewerAgent()
        self.publisher = PublisherAgent()

    def log(self, message: str):
        """Pipeline log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{self.pipeline_name.upper()} {timestamp}] {message}")

    def _build_news_context(self, opportunity: Dict) -> str:
        """Opportunity dict'ten Creator için news_context string'i oluştur."""
        if not opportunity:
            return ""
        return (
            f"HABER: {opportunity.get('title', '')}\n"
            f"KAYNAK: {opportunity.get('source_name', '')}\n"
            f"OZET: {(opportunity.get('summary') or '')[:500]}\n"
            f"OLIVENET ACISI: {opportunity.get('olivenet_angle', '')}\n"
            f"HOOK ONERISI: {opportunity.get('hook_suggestion', '')}"
        )

    async def notify_telegram(self, message: str, data: Dict = None, buttons: list = None):
        """Telegram'a bildirim gönder"""
        if self.telegram_callback:
            try:
                await self.telegram_callback(message, data, buttons)
            except Exception as e:
                logger.error(f"Telegram notification error: {e}")

    async def wait_for_approval(self, timeout: int = 3600) -> Dict[str, Any]:
        """Kullanıcı onayı bekle (default 1 saat)"""
        self.approval_event.clear()
        self.approval_response = None

        try:
            await asyncio.wait_for(self.approval_event.wait(), timeout=timeout)
            return self.approval_response or {"action": "timeout"}
        except asyncio.TimeoutError:
            return {"action": "timeout"}

    def set_approval(self, response: Dict[str, Any]):
        """Onay yanıtını ayarla (Telegram'dan çağrılır)"""
        self.approval_response = response
        self.approval_event.set()

    @property
    def current_state(self) -> Dict[str, Any]:
        """Audit logging için current_data'dan state çıkar"""
        content = self.current_data.get("content", {})
        topic = self.current_data.get("topic_suggestion", {})
        visual = self.current_data.get("visual_result", {})

        return {
            "post_id": content.get("post_id"),
            "topic": topic.get("topic"),
            "visual_type": visual.get("visual_type", "post"),
            "pipeline": self.pipeline_name
        }

    async def select_topic(self, topic: str = None) -> Dict[str, Any]:
        """
        Ortak konu seçimi.
        topic verilmişse onu kullanır, yoksa Planner'dan önerir.
        """
        self.state = PipelineState.PLANNING

        if topic:
            self.log(f"Manual topic: {topic}")
            return {
                "topic": topic,
                "category": "manual",
                "suggested_visual": None,
                "reasoning": "Manual topic provided"
            }

        self.log("Planner'dan konu önerisi alınıyor...")
        result = await self.planner.execute({"action": "suggest_topic"})

        if result.get("error"):
            raise Exception(f"Planner error: {result['error']}")

        return result

    async def review_and_revise(
        self,
        post_text: str,
        topic: str,
        min_score: float = 7.0,
        max_revisions: int = 2
    ) -> Dict[str, Any]:
        """
        Ortak review + revision döngüsü.
        Reviewer skorlaması min_score altındaysa revize eder.
        """
        self.state = PipelineState.REVIEWING

        for attempt in range(max_revisions + 1):
            review_result = await self.reviewer.execute({
                "action": "review_post",
                "post_text": post_text,
                "topic": topic
            })

            score = review_result.get("total_score", 0)
            decision = review_result.get("decision", "reject")

            self.log(f"Review attempt {attempt + 1}: score={score}, decision={decision}")

            if score >= min_score or decision == "approve":
                return {
                    "approved": True,
                    "score": score,
                    "review": review_result,
                    "post_text": post_text
                }

            if attempt < max_revisions and decision == "revise":
                feedback = review_result.get("feedback", "")
                self.log(f"Revising post (feedback: {feedback[:100]}...)")

                revise_result = await self.creator.execute({
                    "action": "revise_post",
                    "original_text": post_text,
                    "feedback": feedback,
                    "topic": topic
                })
                post_text = revise_result.get("revised_text", post_text)
            else:
                break

        return {
            "approved": False,
            "score": score,
            "review": review_result,
            "post_text": post_text
        }

    async def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """Ortak hata yönetimi"""
        self.state = PipelineState.ERROR
        error_msg = f"[{self.pipeline_name}] Error in {context}: {str(error)}"
        self.log(error_msg)

        await self.notify_telegram(f"❌ Pipeline Error:\n{error_msg}")

        return {
            "success": False,
            "error": str(error),
            "pipeline": self.pipeline_name,
            "context": context
        }

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Her pipeline bu metodu implement eder.
        Returns: {"success": bool, "post_id": int, ...}
        """
        pass
