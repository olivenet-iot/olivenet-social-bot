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

# İçerik tonu seçenekleri
VALID_CONTENT_TONES = ["news_commentary", "educational", "showcase", "thought_leadership"]

# Günlük limitler
MAX_DAILY_POSTS = int(os.getenv("BRAIN_MAX_DAILY_POSTS", "2"))
MIN_POST_INTERVAL_HOURS = int(os.getenv("BRAIN_MIN_POST_INTERVAL_HOURS", "4"))
MIN_SCORE_TO_PRODUCE = float(os.getenv("BRAIN_MIN_SCORE_PRODUCE", "60"))

# Optimal paylaşım saatleri (KKTC UTC+3)
OPTIMAL_HOURS = [10, 14, 19]

# Brain'in varsayılan model tercihleri
MODEL_DEFAULTS = {
    "news_reels": "kling-3.0-pro",
    "voice_reels": "sora-2-pro",
    "reels": "kling-3.0-pro",
    "long_video": "kling-3.0-pro",
    "conversational": "sora-2-pro",
    "carousel": None,
    "post": None,
}

VALID_MODELS = ["sora-2", "sora-2-pro", "veo-3.1", "kling-3.0-pro"]
VALID_VISUAL_STYLES = ["cinematic_4k", "3d_render", "neon_cyberpunk", "anime", "minimalist"]
VALID_HOOK_TYPES = ["question", "statistic", "bold_claim", "problem", "value", "fear", "before_after", "list", "comparison", "local"]

CAROUSEL_STYLES = {
    "tech_blue": {"palette": "deep blue, electric cyan, white", "mood": "professional, tech-forward"},
    "energy_green": {"palette": "emerald, lime, dark gray", "mood": "sustainable, fresh, eco"},
    "warm_industrial": {"palette": "orange, steel gray, warm white", "mood": "industrial, hands-on, practical"},
    "dark_premium": {"palette": "black, gold, white", "mood": "premium, executive, high-end"},
    "clean_minimal": {"palette": "white, light gray, single accent color", "mood": "minimal, data-focused, clean"},
}

CAROUSEL_LAYOUTS = ["data_heavy", "storytelling", "comparison", "step_by_step", "tips_list"]


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
            creative = {k: input_data[k] for k in ("model_id", "visual_style", "hook_type") if k in input_data}
            return await self.force_produce(opp_id, content_type, decision=creative or None)
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
                    get_opportunity(opp_id), content_type, decision=decision
                )
                decision["production_result"] = result

        elif decision.get("action") == "produce" and self._dry_run:
            extra = ""
            if decision.get("content_type") == "carousel":
                extra = (f", carousel_style={decision.get('carousel_style')}, "
                         f"layout={decision.get('carousel_layout')}, slides={decision.get('slide_count')}")
            self.log(f"[DRY-RUN] Would produce: opp={decision.get('opportunity_id')}, "
                     f"type={decision.get('content_type')}, model={decision.get('model_id')}, "
                     f"style={decision.get('visual_style')}, reason={decision.get('reason')}{extra}")

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
            f"  #{o['id']}: {o['title']} (score: {o['score']}, type: {o['suggestion']}, source: {o['source']}, hook: {o.get('hook', 'N/A')})"
            for o in top_opps
        ]) or "  Hazır fırsat yok"

        # Son kullanılan konular
        recent = state.get("recent_topics_14d", [])
        recent_text = ", ".join(recent[:10]) if recent else "Yok"

        # Son 24 saatte seçilen fırsatlar (tekrar seçimi önle)
        recently_selected = pool.get("recently_selected", [])
        recently_selected_text = "\n".join([
            f"  #{r['id']}: {r['title']}"
            for r in recently_selected
        ]) or "  Yok"

        prompt = f"""Sen Olivenet Social Bot'un stratejik beynisin. Otonom içerik üretim kararları veriyorsun.

MEVCUT DURUM:
- Tarih/Saat: {state['current_time']} ({state['day_of_week']})
- Son paylaşımdan bu yana: {state['hours_since_last_post']:.1f} saat
- Aktif üretim var mı: {state['is_production_active']}

HAFTALIK İLERLEME:
{json.dumps(weekly, indent=2, default=str)}

HAFTALIK REHBER (hedef değil, rehber — sen karar ver):
- Haftada toplam 8-14 içerik üret (duruma göre ayarla)
- Çeşitlilik önemli: tek formata takılma
- Haber yoğun haftalarda news_reels ve carousel ağırlıklı ol
- Haber az ise evergreen reels ve post'lara ağırlık ver
- Performans verisine göre adapte ol: hangi format daha iyi engagement alıyorsa ona yönel
- Her gün en az 1, en fazla 3 içerik

HAZIR FIRSATLAR (Top 5):
{opp_text}

SON 24 SAATTE SEÇİLEN FIRSATLAR (tekrar seçme):
{recently_selected_text}

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

İÇERİK TONU (zorunlu — content_tone alanını MUTLAKA doldur):
- "news_commentary": Haber bazlı. Kaynağı referans ver, ne olduğunu anlat, Olivenet perspektifinden yorumla. ASLA pazarlama tonu kullanma.
  Örnek: "AT&T, Cisco ve NVIDIA edge computing için güçlerini birleştirdi. Bu, endüstriyel IoT sektörü için önemli bir sinyal..."
- "educational": Eğitici. Bir konuyu öğret, teknik detay ver. Bilgi paylaşımı tonu.
  Örnek: "Edge AI nedir? Veriyi buluta göndermeden yerinde işlemek demek. İşte 4 temel avantajı..."
- "showcase": Olivenet'in yaptığı işleri göster. Sadece gerçek projeler ve deneyimler.
  Örnek: "KKTC'de sera otomasyonu projemizden bir kesit. LoRaWAN sensörlerle nem ve sıcaklığı izliyoruz."
- "thought_leadership": Sektör yorumu, trend analizi. Kişisel görüş ve vizyon.
  Örnek: "Endüstriyel IoT'nin geleceği edge'de. İşte neden böyle düşünüyorum..."
KURAL: source='rss' olan fırsatlar için content_tone MUTLAKA 'news_commentary' olmalı.
Evergreen fırsatlar için 'educational' veya 'showcase' kullan.

YARATICI PARAMETRELER:
- model_id: Video model seçimi. İçeriğe göre aktif seçim yap.
  MODEL SEÇİMİ REHBERİ:
  - kling-3.0-pro: Hızlı üretim (2-3 dk), 15s'e kadar, ambient ses destekli. Endüstriyel, gerçekçi sahneler için ideal. Kling Direct API.
  - sora-2: Yüksek sinematik kalite, 12s max, yavaş (5-8 dk). Yaratıcı ve artistik sahneler için. Sesli reels'te iyi sonuç verir.
  - sora-2-pro: Sora 2'nin premium versiyonu, native speech destekli. Conversational ve voice reels için en iyi seçim.
  - veo-3.1: Google'ın modeli, 8s max, native speech destekli. Hızlı ve kaliteli, doğa/açık alan sahneleri için güçlü.

  Modeli içeriğe göre seç:
  - Haber bazlı acil içerik → kling-3.0-pro (hızlı)
  - Sinematik showcase → sora-2 veya veo-3.1
  - Sesli anlatım → sora-2-pro
  - Conversational diyalog → sora-2-pro
  - Teknik demo → kling-3.0-pro veya veo-3.1
  Mevcut modeller: {', '.join(VALID_MODELS)}
- visual_style: Görsel stil. Seçenekler: {', '.join(VALID_VISUAL_STYLES)}. Varsayılan: cinematic_4k
  Stil rehberi:
  - Haber bazlı içerik → cinematic_4k
  - Teknik/ürün odaklı → 3d_render
  - Eğitici/dikkat çekici → anime
  - Futuristik/trend → neon_cyberpunk
  - İnfografik tarzı/clean → minimalist
- hook_type: Sadece reels için. Seçenekler: {', '.join(VALID_HOOK_TYPES)}. Fırsatın hook önerisini dikkate al.
- voice_mode: Sesli içerik mi? voice_reels/news_reels/conversational→true, diğerleri→false

CAROUSEL PARAMETRELERİ (sadece content_type=carousel ise):
- carousel_style: Renk paleti. Seçenekler: {', '.join(CAROUSEL_STYLES.keys())}
  IoT/teknoloji haberi → tech_blue
  Enerji/sürdürülebilirlik → energy_green
  Endüstriyel/fabrika → warm_industrial
  Genel profesyonel → dark_premium
  Veri/istatistik ağırlıklı → clean_minimal
- carousel_layout: Sunum tarzı. Seçenekler: {', '.join(CAROUSEL_LAYOUTS)}
- slide_count: 4-8 arası (kısa haber: 4, detaylı analiz: 6-8)

KARAR VER ve JSON formatında yanıt ver:
{{
    "action": "produce" | "wait",
    "reason": "Kararın sebebi (Türkçe, 1-2 cümle)",
    "opportunity_id": null | <fırsat ID>,
    "content_type": null | "reels" | "voice_reels" | "news_reels" | "carousel" | "post",
    "content_tone": null | "news_commentary" | "educational" | "showcase" | "thought_leadership",
    "weekly_strategy_note": "Bu hafta neden bu formatı seçtim (1 cümle)",
    "urgency": "low" | "medium" | "high",
    "model_id": null | "<model ID>",
    "visual_style": null | "<stil>",
    "hook_type": null | "<hook tipi>",
    "voice_mode": null | true | false,
    "carousel_style": null | "<style>",
    "carousel_layout": null | "<layout>",
    "slide_count": null | 4-8
}}"""

        try:
            response = await self.call_claude_with_retry(prompt, timeout=60, max_retries=2)
            result = json.loads(response)

            # Doğrulama
            if result.get("action") not in ("produce", "wait", "adjust_strategy"):
                result["action"] = "wait"
                result["reason"] = result.get("reason", "Invalid action from LLM")

            # Creative parameter defaults
            content_type = result.get("content_type")
            if content_type and result.get("action") == "produce":
                if not result.get("model_id") or result.get("model_id") not in VALID_MODELS:
                    result["model_id"] = MODEL_DEFAULTS.get(content_type)
                if not result.get("visual_style"):
                    result["visual_style"] = "cinematic_4k"
                if content_type != "reels":
                    result["hook_type"] = None
                if result.get("voice_mode") is None:
                    result["voice_mode"] = content_type in ("voice_reels", "news_reels", "conversational")

                # Carousel parameter defaults
                if content_type == "carousel":
                    if not result.get("carousel_style") or result.get("carousel_style") not in CAROUSEL_STYLES:
                        result["carousel_style"] = "tech_blue"
                    if not result.get("carousel_layout") or result.get("carousel_layout") not in CAROUSEL_LAYOUTS:
                        result["carousel_layout"] = "storytelling"
                    slide_count = result.get("slide_count")
                    if not isinstance(slide_count, int) or slide_count < 4 or slide_count > 8:
                        result["slide_count"] = 5
                    else:
                        result["slide_count"] = max(4, min(8, slide_count))

                # Content tone validation
                tone = result.get("content_tone")
                if not tone or tone not in VALID_CONTENT_TONES:
                    opp = get_opportunity(result.get("opportunity_id"))
                    if opp and opp.get("source_type") == "rss":
                        result["content_tone"] = "news_commentary"
                    else:
                        result["content_tone"] = "educational"

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

    async def trigger_production(self, opportunity: Dict, content_type: str, decision: Dict = None) -> Dict:
        """Uygun production pipeline'ı tetikle."""
        if not opportunity:
            return {"error": "Opportunity not found"}

        opp_id = opportunity["id"]

        # Fırsatı 'producing' olarak işaretle
        update_opportunity(opp_id, status="producing", selected_at=datetime.utcnow().isoformat())

        # State manager'a bildir
        pipeline_key = f"{content_type}_{opp_id}"
        self.state_manager.register_production(pipeline_key)

        creative = decision or {}
        model_id = creative.get("model_id")
        visual_style = creative.get("visual_style", "cinematic_4k")
        hook_type = creative.get("hook_type")
        content_tone = creative.get("content_tone", "educational")

        self.log(f"Triggering production: type={content_type}, opp={opp_id}, "
                 f"model={model_id}, style={visual_style}, title={opportunity['title'][:50]}")

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

                if content_type == "news_reels":
                    kwargs = {"opportunity": opportunity, "autonomous": True, "content_tone": content_tone}
                    if model_id:
                        kwargs["model_id"] = model_id
                    if visual_style:
                        kwargs["visual_style"] = visual_style
                    result = await pipeline.run(**kwargs)

                elif content_type == "reels":
                    kwargs = {"topic": opportunity.get("title", ""), "opportunity": opportunity, "content_tone": content_tone}
                    if model_id:
                        kwargs["force_model"] = model_id  # ReelsPipeline uses force_model
                    if visual_style:
                        kwargs["visual_style"] = visual_style
                    if hook_type:
                        kwargs["hook_type"] = hook_type
                    result = await pipeline.run(**kwargs)

                elif content_type == "voice_reels":
                    kwargs = {"topic": opportunity.get("title", ""), "opportunity": opportunity, "content_tone": content_tone}
                    if model_id:
                        kwargs["model_id"] = model_id
                    if visual_style:
                        kwargs["visual_style"] = visual_style
                    result = await pipeline.run(**kwargs)

                elif content_type in ("long_video", "conversational"):
                    kwargs = {"topic": opportunity.get("title", ""), "opportunity": opportunity, "content_tone": content_tone}
                    if model_id:
                        kwargs["model_id"] = model_id
                    if visual_style:
                        kwargs["visual_style"] = visual_style
                    result = await pipeline.run(**kwargs)

                elif content_type == "carousel":
                    kwargs = {
                        "topic": opportunity.get("title", ""),
                        "opportunity": opportunity,
                        "content_tone": content_tone,
                        "carousel_type": "nano_banana",
                        "carousel_style": creative.get("carousel_style", "tech_blue"),
                        "carousel_layout": creative.get("carousel_layout", "storytelling"),
                        "slide_count": creative.get("slide_count", 5),
                    }
                    result = await pipeline.run(**kwargs)

                else:  # post — no video/carousel params
                    result = await pipeline.run(topic=opportunity.get("title", ""), opportunity=opportunity, content_tone=content_tone)

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

    async def force_produce(self, opp_id: int, content_type: str, decision: Dict = None) -> Dict:
        """Telegram /force komutu ile belirli bir fırsatı hemen üret."""
        opp = get_opportunity(opp_id)
        if not opp:
            return {"error": f"Opportunity {opp_id} not found"}

        if decision is None:
            decision = {"model_id": MODEL_DEFAULTS.get(content_type), "visual_style": "cinematic_4k"}

        self.log(f"Force producing: opp={opp_id}, type={content_type}, model={decision.get('model_id')}")
        return await self.trigger_production(opp, content_type, decision=decision)

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
