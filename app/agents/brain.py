"""
Brain Agent - Otonom karar motoru

Ne zaman, ne tür, hangi konuda içerik üretileceğine karar verir.
OrchestratorAgent'ın evrimleşmiş halidir.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.agents.base_agent import BaseAgent
from app.utils.logger import get_logger
from app.engine.state import SystemState
from app.database.crud import (
    get_kktc_now, update_opportunity, get_opportunity,
    log_agent_action
)

logger = get_logger("brain")

# Haftalık hedefler
WEEKLY_TARGETS = {
    "reels": 7,
    "carousel": 2,
    "post": 3,
}

# Günlük limitler
MAX_DAILY_POSTS = int(os.getenv("BRAIN_MAX_DAILY_POSTS", "2"))
MIN_POST_INTERVAL_HOURS = int(os.getenv("BRAIN_MIN_POST_INTERVAL_HOURS", "4"))
MIN_SCORE_TO_PRODUCE = float(os.getenv("BRAIN_MIN_SCORE_PRODUCE", "60"))

# Optimal paylaşım saatleri (KKTC UTC+3)
OPTIMAL_HOURS = [10, 14, 19]


class BrainAgent(BaseAgent):
    """
    Otonom karar motoru.

    Her 2 saatte bir çalışır:
    1. Sistem durumunu toplar
    2. Claude API ile karar verir (produce/wait/adjust_strategy)
    3. Kararı uygular veya loglar (dry-run modunda)
    """

    def __init__(self):
        super().__init__("brain")
        self.state_manager = SystemState()
        self.event_bus = None  # main.py tarafından set edilir
        self._last_decisions: List[Dict] = []  # Son 5 karar (Telegram /brain için)
        self._dry_run = os.getenv("BRAIN_DRY_RUN", "true").lower() == "true"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent dispatcher."""
        action = input_data.get("action", "decide")
        if action == "decide":
            return await self.decide()
        elif action == "gather_state":
            return self.state_manager.get_full_state()
        elif action == "force_produce":
            opp_id = input_data.get("opportunity_id")
            content_type = input_data.get("content_type", "reels")
            return await self.force_produce(opp_id, content_type)
        return {"error": f"Unknown action: {action}"}

    async def decide(self) -> Dict[str, Any]:
        """
        Ana karar döngüsü. Brain Agent'ın çekirdek metodu.
        """
        # Sistem duraklatılmış mı?
        if self.state_manager.is_paused:
            decision = {"action": "wait", "reason": "System is paused"}
            self._record_decision(decision)
            return decision

        # Aktif üretim var mı?
        if self.state_manager.is_production_active():
            decision = {"action": "wait", "reason": "Production already active"}
            self._record_decision(decision)
            return decision

        # Durum bilgilerini topla
        state = self.state_manager.get_full_state()

        # Quick checks (Claude API çağırmadan)
        quick_decision = self._quick_checks(state)
        if quick_decision:
            self._record_decision(quick_decision)
            return quick_decision

        # Claude API ile karar ver
        decision = await self._ask_claude_for_decision(state)

        # Kararı kaydet
        self._record_decision(decision)

        # Log to database
        log_agent_action(
            agent_name="brain",
            action="decide",
            input_data=json.dumps({
                "hour": state["hour"],
                "pool_active": state["pool_status"].get("active_count", 0),
                "hours_since_last": state["hours_since_last_post"]
            }),
            output_data=json.dumps(decision),
            success="error" not in decision
        )

        # Kararı uygula
        if decision.get("action") == "produce" and not self._dry_run:
            opp_id = decision.get("opportunity_id")
            content_type = decision.get("content_type", "reels")

            if opp_id:
                result = await self.trigger_production(
                    get_opportunity(opp_id), content_type
                )
                decision["production_result"] = result

        elif decision.get("action") == "produce" and self._dry_run:
            self.log(f"[DRY-RUN] Would produce: opp={decision.get('opportunity_id')}, "
                     f"type={decision.get('content_type')}, reason={decision.get('reason')}")

        # Event bus'a bildir
        if self.event_bus:
            await self.event_bus.publish("brain_decision", decision)

        return decision

    def _quick_checks(self, state: Dict) -> Optional[Dict]:
        """Claude API çağırmadan yapılabilecek hızlı kontroller."""
        now_hour = state["hour"]

        # Gece saati (23:00 - 07:00 arası üretim yapma)
        if now_hour >= 23 or now_hour < 7:
            return {"action": "wait", "reason": f"Night hours ({now_hour}:00)"}

        # Son paylaşımdan çok az zaman geçmiş
        hours_since = state["hours_since_last_post"]
        if hours_since < MIN_POST_INTERVAL_HOURS:
            return {
                "action": "wait",
                "reason": f"Too soon since last post ({hours_since:.1f}h < {MIN_POST_INTERVAL_HOURS}h)"
            }

        # Havuzda hazır fırsat yok
        pool = state["pool_status"]
        if not pool.get("top_opportunities"):
            return {"action": "wait", "reason": "No ready opportunities in pool"}

        return None

    async def _ask_claude_for_decision(self, state: Dict) -> Dict:
        """Claude API ile karar ver."""
        # Haftalık hedefler ve ilerleme
        weekly = state.get("weekly_stats", {})
        pool = state.get("pool_status", {})

        # Top opportunities summary
        top_opps = pool.get("top_opportunities", [])
        opp_text = "\n".join([
            f"  #{o['id']}: {o['title']} (score: {o['score']}, type: {o['suggestion']}, source: {o['source']})"
            for o in top_opps
        ]) or "  Hazır fırsat yok"

        # Son kullanılan konular
        recent = state.get("recent_topics_14d", [])
        recent_text = ", ".join(recent[:10]) if recent else "Yok"

        prompt = f"""Sen Olivenet Social Bot'un stratejik beynisin. Otonom içerik üretim kararları veriyorsun.

MEVCUT DURUM:
- Tarih/Saat: {state['current_time']} ({state['day_of_week']})
- Son paylaşımdan bu yana: {state['hours_since_last_post']:.1f} saat
- Aktif üretim var mı: {state['is_production_active']}

HAFTALIK İLERLEME:
{json.dumps(weekly, indent=2, default=str)}

HAFTALIK HEDEFLER:
- Reels: {WEEKLY_TARGETS['reels']}/hafta
- Carousel: {WEEKLY_TARGETS['carousel']}/hafta
- Post: {WEEKLY_TARGETS['post']}/hafta

HAZIR FIRSATLAR (Top 5):
{opp_text}

SON 14 GÜNDE KULLANILAN KONULAR:
{recent_text}

KURALLAR:
1. Günde max {MAX_DAILY_POSTS} paylaşım
2. Paylaşımlar arası min {MIN_POST_INTERVAL_HOURS} saat
3. Haber bazlı içerik 48 saatten eski olmamalı
4. Aynı konu 14 gün içinde tekrarlanmamalı
5. Haftalık mix: ~%50 haber bazlı, ~%25 uzmanlık, ~%25 eğitici
6. Optimal saatler: {OPTIMAL_HOURS}
7. Min skor: {MIN_SCORE_TO_PRODUCE}

KARAR VER ve JSON formatında yanıt ver:
{{
    "action": "produce" | "wait",
    "reason": "Kararın sebebi (Türkçe, 1-2 cümle)",
    "opportunity_id": null | <fırsat ID>,
    "content_type": null | "reels" | "voice_reels" | "news_reels" | "carousel" | "post",
    "urgency": "low" | "medium" | "high"
}}"""

        try:
            response = await self.call_claude_with_retry(prompt, timeout=60, max_retries=2)
            result = json.loads(response)

            # Doğrulama
            if result.get("action") not in ("produce", "wait", "adjust_strategy"):
                result["action"] = "wait"
                result["reason"] = result.get("reason", "Invalid action from LLM")

            return result

        except json.JSONDecodeError:
            logger.error("Brain decision JSON parse error")
            return {"action": "wait", "reason": "Decision parse error", "error": "json_parse"}
        except Exception as e:
            logger.error(f"Brain decision error: {e}")
            return {"action": "wait", "reason": f"Error: {str(e)}", "error": str(e)}

    # Content type -> (module_path, class_name) mapping
    PIPELINE_MAP = {
        "reels": ("app.production.reels_pipeline", "ReelsPipeline"),
        "voice_reels": ("app.production.voice_reels_pipeline", "VoiceReelsPipeline"),
        "news_reels": ("app.production.news_reels_pipeline", "NewsReelsPipeline"),
        "carousel": ("app.production.carousel_pipeline", "CarouselPipeline"),
        "post": ("app.production.post_pipeline", "PostPipeline"),
        "long_video": ("app.production.long_video_pipeline", "LongVideoPipeline"),
        "conversational": ("app.production.conversational_pipeline", "ConversationalPipeline"),
    }

    async def trigger_production(self, opportunity: Dict, content_type: str) -> Dict:
        """Uygun production pipeline'ı tetikle."""
        if not opportunity:
            return {"error": "Opportunity not found"}

        opp_id = opportunity["id"]

        # Fırsatı 'producing' olarak işaretle
        update_opportunity(opp_id, status="producing", selected_at=datetime.utcnow().isoformat())

        # State manager'a bildir
        pipeline_key = f"{content_type}_{opp_id}"
        self.state_manager.register_production(pipeline_key)

        self.log(f"Triggering production: type={content_type}, opp={opp_id}, title={opportunity['title'][:50]}")

        try:
            pipeline_info = self.PIPELINE_MAP.get(content_type)

            if not pipeline_info:
                self.log(f"Content type '{content_type}' pipeline bulunamadi")
                update_opportunity(opp_id, status="ready")
                result = {"success": False, "reason": f"Unknown content type: {content_type}"}
            else:
                import importlib
                module_path, class_name = pipeline_info
                module = importlib.import_module(module_path)
                PipelineClass = getattr(module, class_name)
                pipeline = PipelineClass()

                # news_reels has opportunity-based interface
                if content_type in ("news_reels",):
                    result = await pipeline.run(opportunity=opportunity, autonomous=True)
                else:
                    # Other pipelines use topic-based interface
                    topic = opportunity.get("title", "")
                    result = await pipeline.run(topic=topic)

        except Exception as e:
            self.log(f"Production error: {e}")
            update_opportunity(opp_id, status="ready")
            result = {"success": False, "error": str(e)}

        finally:
            self.state_manager.complete_production(pipeline_key, content_type)

        return {
            "triggered": True,
            "content_type": content_type,
            "opportunity_id": opp_id,
            "production_result": result
        }

    async def force_produce(self, opp_id: int, content_type: str) -> Dict:
        """Telegram /force komutu ile belirli bir fırsatı hemen üret."""
        opp = get_opportunity(opp_id)
        if not opp:
            return {"error": f"Opportunity {opp_id} not found"}

        self.log(f"Force producing: opp={opp_id}, type={content_type}")
        return await self.trigger_production(opp, content_type)

    def _record_decision(self, decision: Dict):
        """Son kararları tut (Telegram /brain komutu için)."""
        decision["timestamp"] = datetime.utcnow().isoformat()
        self._last_decisions.insert(0, decision)
        self._last_decisions = self._last_decisions[:10]  # Max 10 karar tut

        action = decision.get("action", "unknown")
        reason = decision.get("reason", "")
        self.log(f"Decision: {action} — {reason}")

    def get_last_decisions(self, limit: int = 5) -> List[Dict]:
        """Son N kararı döner."""
        return self._last_decisions[:limit]

    async def check_prediction_accuracy(self) -> Dict[str, Any]:
        """
        Yayınlanmış içeriklerin tahmin doğruluğunu kontrol et.
        Opportunity skorları vs gerçek performans karşılaştırması.
        """
        from app.database.crud import get_published_posts, get_opportunity_stats

        self.log("Prediction accuracy check başlatılıyor...")

        try:
            # Son 7 gün yayınlanmış postları al
            published = get_published_posts(days=7)
            if not published:
                self.log("Son 7 günde yayınlanmış post yok")
                return {"checked": 0, "message": "No published posts"}

            comparisons = []
            for post in published:
                post_id = post.get("id")
                ig_engagement = post.get("ig_engagement_rate", 0) or 0
                ig_saves = post.get("ig_saves", 0) or 0
                ig_shares = post.get("ig_shares", 0) or 0

                # Skip posts without metrics
                if ig_engagement == 0 and ig_saves == 0:
                    continue

                # Performance skoru hesapla (basit weighted)
                actual_score = (ig_engagement * 100) + (ig_saves * 0.5) + (ig_shares * 1.0)

                comparisons.append({
                    "post_id": post_id,
                    "topic": post.get("topic", "")[:50],
                    "actual_engagement": ig_engagement,
                    "actual_saves": ig_saves,
                    "actual_shares": ig_shares,
                    "actual_score": round(actual_score, 1),
                })

            if not comparisons:
                self.log("Metrik verisi olan post yok")
                return {"checked": 0, "message": "No posts with metrics"}

            # Log results
            avg_score = sum(c["actual_score"] for c in comparisons) / len(comparisons)

            log_agent_action(
                agent_name="brain",
                action="prediction_check",
                input_data={"post_count": len(comparisons)},
                output_data={
                    "avg_actual_score": round(avg_score, 1),
                    "sample_size": len(comparisons),
                    "top_performer": max(comparisons, key=lambda x: x["actual_score"])
                },
                success=True
            )

            self.log(f"Prediction check: {len(comparisons)} post, avg_score={avg_score:.1f}")

            return {
                "checked": len(comparisons),
                "avg_actual_score": round(avg_score, 1),
                "comparisons": comparisons[:5]  # Top 5
            }

        except Exception as e:
            self.log(f"Prediction check error: {e}")
            log_agent_action(
                agent_name="brain",
                action="prediction_check",
                success=False,
                error_message=str(e)
            )
            return {"error": str(e)}

    @property
    def is_dry_run(self) -> bool:
        return self._dry_run

    def set_dry_run(self, value: bool):
        self._dry_run = value
        self.log(f"Dry-run mode: {value}")
