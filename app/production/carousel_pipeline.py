"""
Carousel Pipeline - Instagram carousel içerik üretim pipeline'ı.
ContentPipeline.run_carousel_pipeline'dan extract edildi.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, escape_md
from app.database import save_prompt
from app.database.crud import update_post
from app.validators.text_validator import validate_html_content, fix_common_issues


class CarouselPipeline(BasePipeline):
    """Instagram Carousel üretim pipeline'ı."""

    def __init__(self, telegram_callback=None):
        super().__init__("carousel", telegram_callback)

    async def run(self, topic=None, dry_run=False, carousel_type="nano_banana", manual_topic=None,
                  carousel_style="tech_blue", carousel_layout="storytelling", slide_count=5,
                  opportunity=None, content_tone="educational") -> Dict[str, Any]:
        """
        Instagram Carousel içerik üretim pipeline'ı.

        Akış:
        1. Konu seçimi (opsiyonel)
        2. Carousel içerik oluşturma (Creator)
        3. Her slide için görsel üretimi (HTML veya Nano Banana)
        4. Kalite kontrolü (Reviewer)
        5. Instagram'a paylaşım (Publisher)

        Args:
            topic: Carousel konusu (None ise Planner'dan al)
            dry_run: True ise paylaşım yapmadan dur
            carousel_type: Görsel tipi ("html" veya "nano_banana")
            manual_topic: Manuel konu (topic yerine kullanılır)

        Returns:
            Pipeline sonucu
        """
        # Manual topic varsa onu kullan
        if manual_topic:
            topic = manual_topic

        type_name = "Nano Banana AI" if carousel_type == "nano_banana" else "HTML Template"
        self.log(f"🎠 Carousel Pipeline başlatılıyor... (Tip: {type_name})")
        self.state = PipelineState.CREATING_CONTENT

        result = {
            "success": False,
            "stages_completed": [],
            "content_type": "carousel",
            "dry_run": dry_run
        }

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if not topic:
                self.log("[CAROUSEL] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({
                    "action": "suggest_topic",
                    "content_type": "carousel",
                    "category": "egitici"
                })
                topic = topic_result.get("topic", "LoRaWAN Temel Kavramlar")
                result["topic_suggestion"] = topic_result

            result["topic"] = topic
            result["stages_completed"].append("topic_selection")
            self.log(f"[CAROUSEL] Konu: {topic}")

            # ========== AŞAMA 2: Carousel İçerik Oluştur ==========
            self.log("[CAROUSEL] Aşama 2: İçerik oluşturuluyor...")

            carousel_content = await self.creator.execute({
                "action": "create_carousel_content",
                "topic": topic,
                "slide_count": slide_count,
                "category": "egitici",
                "content_tone": content_tone,
                "news_context": self._build_news_context(opportunity) if opportunity else None,
            })

            if not carousel_content.get("success"):
                raise Exception(f"Creator error: {carousel_content.get('error')}")

            result["post_id"] = carousel_content.get("post_id")
            result["caption"] = carousel_content.get("caption")
            result["slides"] = carousel_content.get("slides")
            result["hashtags"] = carousel_content.get("hashtags")
            result["slide_count"] = carousel_content.get("slide_count", 0)
            result["stages_completed"].append("content_created")

            # Persist tone to DB
            if carousel_content.get("post_id") and content_tone:
                update_post(carousel_content["post_id"], tone=content_tone)

            # ========== Carousel İçerik Validasyonu ==========
            self.log("[CAROUSEL] İçerik validasyonu yapılıyor...")
            validation = self.reviewer.validate_carousel_content(carousel_content)

            if not validation.get("valid"):
                self.log(f"[CAROUSEL] ⚠️ Validasyon uyarıları: {validation.get('issues')}")

            if validation.get("issues"):
                # Auto-fix uygula
                fixed_content = validation.get("auto_fixed", carousel_content)
                if fixed_content != carousel_content:
                    self.log("[CAROUSEL] 🔧 Otomatik düzeltmeler uygulandı")
                    carousel_content = fixed_content
                    result["caption"] = fixed_content.get("caption", result["caption"])
                    result["slides"] = fixed_content.get("slides", result["slides"])

            result["validation"] = validation

            # SON KONTROL: Cover'da hala KAYDET var mı?
            slides = carousel_content.get("slides", [])
            if slides:
                cover_str = str(slides[0]).lower()
                if "kaydet" in cover_str:
                    self.log("[CAROUSEL] ⚠️ UYARI: Cover'da hala KAYDET var! Zorla temizleniyor...")
                    carousel_content = self.reviewer._clean_cover_slide(carousel_content)
                    result["slides"] = carousel_content.get("slides", result["slides"])
                    self.log("[CAROUSEL] ✅ Cover slide zorla temizlendi")

            result["stages_completed"].append("content_validated")

            # Carousel slide prompt'larını kaydet
            post_id = carousel_content.get("post_id")
            if post_id:
                for i, slide in enumerate(carousel_content.get("slides", [])):
                    image_prompt = slide.get("image_prompt", "")
                    if image_prompt:
                        save_prompt(
                            post_id=post_id,
                            prompt_text=image_prompt,
                            prompt_type='image',
                            style=f'carousel_slide_{i+1}'
                        )
                self.log(f"[CAROUSEL] {len(carousel_content.get('slides', []))} slide prompt'u kaydedildi")

            self.log(f"[CAROUSEL] {result['slide_count']} slide oluşturuldu")

            if dry_run:
                self.log("[CAROUSEL] Dry-run modu - görsel üretimi atlanıyor")
                result["success"] = True
                result["final_state"] = "dry_run_completed"
                return result

            # ========== AŞAMA 3: Görsel Üretimi ==========
            self.state = PipelineState.CREATING_VISUAL
            from app.instagram_helper import upload_image_to_cdn
            from datetime import datetime

            image_urls = []
            slides = carousel_content.get("slides", [])
            total_slides = len(slides)

            # Nano Banana AI Carousel
            if carousel_type == "nano_banana":
                self.log("[CAROUSEL] Aşama 3: Görseller Nano Banana ile üretiliyor...")
                from app.nano_banana_helper import generate_carousel_infographics

                # Build rich style string with design parameters
                from app.agents.brain import CAROUSEL_STYLES
                style_info = CAROUSEL_STYLES.get(carousel_style, CAROUSEL_STYLES["tech_blue"])
                rich_style = (
                    f"modern | Palette: {style_info['palette']} | "
                    f"Mood: {style_info['mood']} | Layout: {carousel_layout}"
                )
                nano_result = await generate_carousel_infographics(
                    topic=topic,
                    slides=slides,
                    style=rich_style,
                    language="tr"
                )

                if nano_result.get("success"):
                    # Nano Banana başarılı - görselleri CDN'e yükle
                    image_paths = nano_result.get("image_paths", [])
                    for i, image_path in enumerate(image_paths):
                        slide_num = i + 1
                        self.log(f"[CAROUSEL] Slide {slide_num}/{total_slides} CDN'e yükleniyor...")
                        cdn_url = await upload_image_to_cdn(image_path)
                        if cdn_url:
                            image_urls.append(cdn_url)
                        else:
                            self.log(f"[CAROUSEL] ⚠️ Slide {slide_num} CDN yükleme hatası")
                else:
                    # Nano Banana başarısız - HTML'e fallback
                    self.log(f"[CAROUSEL] Nano Banana hatası: {nano_result.get('error')}, HTML'e fallback...")
                    carousel_type = "html"  # Fallback

            # HTML Template Carousel (veya fallback)
            if carousel_type == "html":
                self.log("[CAROUSEL] Aşama 3: Görseller HTML ile üretiliyor...")
                from app.claude_helper import generate_carousel_slide_html
                from app.renderer import render_html_to_png

            # HTML rendering loop (sadece html tipi için çalışır)
            if carousel_type == "html":
                for i, slide in enumerate(slides):
                    slide_num = i + 1
                    self.log(f"[CAROUSEL] Slide {slide_num}/{total_slides} HTML üretiliyor...")

                    # Retry mekanizması
                    for attempt in range(2):
                        try:
                            # HTML oluştur
                            html_content = await generate_carousel_slide_html(
                                slide_data=slide,
                                slide_number=slide_num,
                                total_slides=total_slides,
                                topic=topic
                            )

                            # Text validation - typo kontrolü
                            validation = validate_html_content(html_content)
                            if not validation["can_render"]:
                                self.log(f"[CAROUSEL] Slide {slide_num} yazım hatası tespit edildi")
                                for issue in validation["issues"]:
                                    if issue["severity"] == "high":
                                        self.log(f"  - '{issue['found']}' -> '{issue['expected']}'")

                                # Otomatik düzelt
                                html_content, fixes = fix_common_issues(html_content)
                                if fixes:
                                    self.log(f"[CAROUSEL] Otomatik düzeltmeler: {fixes}")

                                # Tekrar doğrula
                                validation = validate_html_content(html_content)
                                if not validation["can_render"]:
                                    self.log(f"[CAROUSEL] Slide {slide_num} hala hatalı, yeniden üretiliyor...")
                                    html_content = await generate_carousel_slide_html(
                                        slide_data=slide,
                                        slide_number=slide_num,
                                        total_slides=total_slides,
                                        topic=topic
                                    )

                            # PNG'ye render et
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            output_path = f"outputs/carousel_{timestamp}_{slide_num}.png"
                            image_path = await render_html_to_png(
                                html_content=html_content,
                                output_path=output_path,
                                width=1080,
                                height=1080
                            )

                            if image_path:
                                # CDN'e yükle - retry logic ile
                                cdn_url = None
                                for upload_attempt in range(3):
                                    cdn_url = await upload_image_to_cdn(image_path)
                                    if cdn_url:
                                        break
                                    elif upload_attempt < 2:
                                        self.log(f"[CAROUSEL] Slide {slide_num} CDN upload retry {upload_attempt + 1}...")
                                        await asyncio.sleep(2)

                                if cdn_url:
                                    image_urls.append(cdn_url)
                                    self.log(f"[CAROUSEL] Slide {slide_num} OK")
                                    break
                                else:
                                    self.log(f"[CAROUSEL] Slide {slide_num} CDN upload başarısız (3 deneme)")
                            else:
                                self.log(f"[CAROUSEL] Slide {slide_num} render hatası, retry...")

                        except Exception as e:
                            self.log(f"[CAROUSEL] Slide {slide_num} hata: {e}")
                            if attempt == 1:
                                self.log(f"[CAROUSEL] Slide {slide_num} atlanıyor")

            result["image_urls"] = image_urls
            result["images_generated"] = len(image_urls)
            result["stages_completed"].append("visuals_created")

            # Minimum 5 görsel gerekli (tüm slide'lar zorunlu)
            if len(image_urls) < 5:
                raise Exception(f"Yetersiz görsel üretildi: {len(image_urls)}/5 - Tüm slide'lar gerekli")

            self.log(f"[CAROUSEL] {len(image_urls)} görsel hazır")

            # ========== AŞAMA 4: Kalite Kontrolü ==========
            self.log("[CAROUSEL] Aşama 4: Kalite kontrolü...")
            self.state = PipelineState.REVIEWING

            MAX_CAROUSEL_RETRIES = 2
            MIN_CAROUSEL_SCORE = 6.5

            for attempt in range(MAX_CAROUSEL_RETRIES + 1):
                review_result = await self.reviewer.execute({
                    "action": "review_post",
                    "post_text": carousel_content.get("caption", ""),
                    "content_type": "carousel",
                    "slide_count": len(image_urls),
                    "topic": topic,
                    "content_tone": content_tone,
                    "news_context": self._build_news_context(opportunity) if opportunity else None
                })

                score = review_result.get("total_score", 7)
                feedback = review_result.get("feedback", "")
                weaknesses = review_result.get("weaknesses", [])
                suggestions = review_result.get("revision_suggestions", [])

                result["review_score"] = score
                result["review_feedback"] = feedback
                result["stages_completed"].append("review")

                self.log(f"[CAROUSEL] Review score: {score}/10 (Deneme {attempt + 1}/{MAX_CAROUSEL_RETRIES + 1})")

                if feedback:
                    self.log(f"[CAROUSEL] Feedback: {feedback[:200]}...")
                if weaknesses:
                    self.log(f"[CAROUSEL] Zayıf yönler: {', '.join(weaknesses[:3])}")

                if score >= MIN_CAROUSEL_SCORE:
                    self.log(f"[CAROUSEL] Kalite onaylandı: {score}/10")
                    break  # Yeterli puan, devam et

                if attempt < MAX_CAROUSEL_RETRIES:
                    # Düşük puan - caption'ı revize et
                    self.log(f"[CAROUSEL] Düşük puan ({score}/10), caption revize ediliyor...")

                    revision_feedback = feedback or "Daha kısa, etkili ve dikkat çekici yaz"
                    if suggestions:
                        revision_feedback += f". Öneriler: {', '.join(suggestions[:2])}"

                    revision_result = await self.creator.execute({
                        "action": "revise_post",
                        "post_text": carousel_content.get("caption", ""),
                        "feedback": revision_feedback,
                        "post_id": carousel_content.get("post_id")
                    })

                    if revision_result.get("revised_post"):
                        carousel_content["caption"] = revision_result.get("revised_post")
                        self.log("[CAROUSEL] Caption revize edildi, tekrar değerlendiriliyor...")
                else:
                    # Son deneme de başarısız
                    self.log(f"[CAROUSEL] {MAX_CAROUSEL_RETRIES + 1} deneme sonrası hala düşük puan: {score}/10")

                    # Admin'e detaylı bildirim gönder
                    feedback_msg = f"❌ *CAROUSEL* - Düşük Kalite Puanı\n\n"
                    feedback_msg += f"📝 Konu: {topic[:50]}...\n"
                    feedback_msg += f"⭐ Puan: {score}/10\n"
                    feedback_msg += f"🔄 Deneme: {MAX_CAROUSEL_RETRIES + 1}\n\n"
                    if feedback:
                        feedback_msg += f"📋 *Feedback:*\n{feedback[:300]}\n\n"
                    if weaknesses:
                        feedback_msg += f"⚠️ *Zayıf Yönler:*\n• " + "\n• ".join(weaknesses[:3]) + "\n\n"
                    if suggestions:
                        feedback_msg += f"💡 *Öneriler:*\n• " + "\n• ".join(suggestions[:3])

                    await self.notify_telegram(
                        message=feedback_msg,
                        data={"score": score, "feedback": feedback},
                        buttons=[]
                    )

                    result["error"] = f"Kalite skoru düşük: {score}/10 - {feedback[:100] if feedback else 'Detay yok'}"
                    result["final_state"] = "review_failed"
                    return result

            # ========== AŞAMA 5: Instagram'a Paylaş ==========
            self.log("[CAROUSEL] Aşama 5: Instagram'a paylaşılıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish_carousel",
                "post_id": carousel_content.get("post_id"),
                "caption": carousel_content.get("caption", ""),
                "image_urls": image_urls,
                "hashtags": carousel_content.get("hashtags", []),
                "visual_type": "carousel"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log("[CAROUSEL] Başarıyla yayınlandı!")

                await self.notify_telegram(
                    message=f"🎠 *CAROUSEL* - Yayınlandı!\n\n"
                    f"📝 Konu: {escape_md(topic[:50])}...\n"
                    f"📸 Slide sayısı: {len(image_urls)}\n"
                    f"⭐ Puan: {score}/10\n"
                    f"📱 Platform: Instagram",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[CAROUSEL] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[CAROUSEL] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *CAROUSEL* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
