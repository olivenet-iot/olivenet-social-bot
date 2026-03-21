"""
Reviewer Agent - Kalite kontrol
İçeriği denetler, onaylar veya revizyon ister
"""

import json
import re
from datetime import datetime
from typing import Dict, Any
from .base_agent import BaseAgent
from app.database import update_post, log_agent_action

class ReviewerAgent(BaseAgent):
    """Kalite kontrol - içeriği denetler ve onaylar"""

    def __init__(self):
        super().__init__("reviewer")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "review_post")

        if action == "review_post":
            return await self.review_post(input_data)
        elif action == "review_visual":
            return await self.review_visual(input_data)
        elif action == "final_approval":
            return await self.final_approval(input_data)
        elif action == "compare_ab_variants":
            return await self.compare_ab_variants(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def compare_ab_variants(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        A/B Test: İki variant'ı karşılaştırmalı skorla ve kazananı seç.

        Input:
            variant_a: Dict with post_text, hook_type, etc.
            variant_b: Dict with post_text, hook_type, etc.
            topic: str
            platform: str

        Output:
            winner: "A" or "B"
            scores: Detailed scores for both
            reasoning: Why the winner was chosen
        """
        self.log("A/B variantları karşılaştırılıyor...")

        variant_a = input_data.get("variant_a", {})
        variant_b = input_data.get("variant_b", {})
        topic = input_data.get("topic", "")
        platform = input_data.get("platform", "instagram")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""
## GÖREV: A/B Test Karşılaştırması

### Şirket Profili
{company_profile[:1000]}

### İçerik Stratejisi Özeti
{content_strategy[:1000]}

### Konu: {topic}
### Platform: {platform}

---

## VARIANT A
**Hook Type:** {variant_a.get('hook_type', 'unknown')}
**Ton:** {variant_a.get('tone', 'unknown')}
**Metin:**
{variant_a.get('post_text', 'N/A')}

---

## VARIANT B
**Hook Type:** {variant_b.get('hook_type', 'unknown')}
**Ton:** {variant_b.get('tone', 'unknown')}
**Metin:**
{variant_b.get('post_text', 'N/A')}

---

## DEĞERLENDİRME KRİTERLERİ (Her kriter 1-10)

1. **Hook Etkisi** - İlk cümle dikkat çekiyor mu?
2. **Değer Önerisi** - Okuyucuya ne fayda sağlıyor?
3. **Marka Uyumu** - Olivenet tonu ve kimliğine uyuyor mu?
4. **Netlik** - Mesaj anlaşılır mı?
5. **Engagement Potansiyeli** - Etkileşim alır mı? (yorum, save, share)
6. **Platform Uyumu** - {platform} için uygun mu?

ÇIKTI FORMATI (JSON):
```json
{{
  "variant_a_scores": {{
    "hook_score": 8,
    "value_score": 7,
    "brand_score": 8,
    "clarity_score": 9,
    "engagement_potential": 7,
    "platform_fit": 8,
    "total": 7.8
  }},
  "variant_b_scores": {{
    "hook_score": 7,
    "value_score": 8,
    "brand_score": 7,
    "clarity_score": 8,
    "engagement_potential": 9,
    "platform_fit": 8,
    "total": 7.8
  }},
  "winner": "A",
  "margin": 0.5,
  "confidence": "high|medium|low",
  "reasoning": "Neden bu variant kazandı? Detaylı açıklama...",
  "variant_a_strengths": ["Güçlü yön 1", "Güçlü yön 2"],
  "variant_a_weaknesses": ["Zayıf yön 1"],
  "variant_b_strengths": ["Güçlü yön 1", "Güçlü yön 2"],
  "variant_b_weaknesses": ["Zayıf yön 1"],
  "learning": "Bu A/B testten ne öğrendik?",
  "recommendation": "Gelecek içerikler için öneri"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            result = json.loads(self._clean_json_response(response))

            # Winning variant'ın detaylarını ekle
            winner = result.get("winner", "A")
            winning_variant = variant_a if winner == "A" else variant_b
            losing_variant = variant_b if winner == "A" else variant_a

            result["winning_variant"] = {
                "post_text": winning_variant.get("post_text"),
                "hook_type": winning_variant.get("hook_type"),
                "tone": winning_variant.get("tone")
            }

            result["test_metadata"] = {
                "topic": topic,
                "platform": platform,
                "variant_a_hook": variant_a.get("hook_type"),
                "variant_b_hook": variant_b.get("hook_type"),
                "compared_at": datetime.now().isoformat()
            }

            log_agent_action(
                agent_name=self.name,
                action="compare_ab_variants",
                input_data={
                    "topic": topic,
                    "variant_a_hook": variant_a.get("hook_type"),
                    "variant_b_hook": variant_b.get("hook_type")
                },
                output_data={
                    "winner": winner,
                    "margin": result.get("margin"),
                    "confidence": result.get("confidence")
                },
                success=True
            )

            self.log(f"A/B karşılaştırma tamamlandı: Kazanan={winner}, Fark={result.get('margin', 0)}")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="compare_ab_variants",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def review_post(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post metnini denetle"""
        self.log("Post denetleniyor...")

        post_text = input_data.get("post_text", "")
        topic = input_data.get("topic", "")
        post_id = input_data.get("post_id")
        content_tone = input_data.get("content_tone")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        # Tone-specific review guidance
        TONE_REVIEW_GUIDANCE = {
            "news_commentary": """
### İÇERİK TONU: HABER YORUMU
Bu post bir HABER ANALİZİ olarak yazılmıştır — pazarlama postu DEĞİLDİR.
Değerlendirme kriterleri buna göre ayarlanmalıdır:
- Hook: Haber başlığı veya çarpıcı bir istatistik ile açılmalı
- Değer: Sektörel farkındalık ve bilgi paylaşımı yeterlidir, ürün tanıtımı GEREKMEZ
- Marka Uyumu: Olivenet'in sektörel otorite sesini yansıtmalı, SATIŞ DİLİ OLMAMALI
- CTA: Yorum/tartışma daveti yeterlidir, "DM atın" gibi satış CTA'sı GEREKMEZ
- Netlik: Haber kaynağı belirtilmiş mi? Olivenet perspektifi eklenmiş mi?
NOT: Bu tür içeriğin LinkedIn tonunda olması NORMALDIR ve OLUMLU değerlendirilmelidir.""",

            "educational": """
### İÇERİK TONU: EĞİTİCİ
Bu post bir EĞİTİM İÇERİĞİ olarak yazılmıştır.
- Hook: Soru veya merak uyandırıcı ifade
- Değer: Öğretici bilgi, teknik detay
- Marka Uyumu: Bilgi paylaşımı tonu, satış dili yok
- CTA: "Kaydet" veya "Arkadaşını etiketle" gibi organik CTA yeterli
- Netlik: Teknik terimler açıklanmış mı?""",

            "showcase": """
### İÇERİK TONU: SHOWCASE
Bu post Olivenet'in GERÇEK DENEYİMİNİ anlatmaktadır.
- Hook: Proje detayı veya sonuç ile açılmalı
- Değer: Gerçek uygulama örneği gösterilmeli
- Marka Uyumu: Samimi, mütevazı, birinci şahıs
- CTA: Soru veya merak uyandırma yeterli
- Netlik: Proje detayları somut mu?""",

            "thought_leadership": """
### İÇERİK TONU: DÜŞÜNCE LİDERLİĞİ
Bu post bir SEKTÖR ANALİZİ olarak yazılmıştır.
- Hook: Güçlü bir tez veya provokatif soru
- Değer: Özgün bakış açısı, trend analizi
- Marka Uyumu: Kişisel/profesyonel görüş tonu
- CTA: Tartışma daveti yeterli
- Netlik: Argüman desteklenmiş mi?"""
        }

        tone_guidance_section = ""
        if content_tone and content_tone in TONE_REVIEW_GUIDANCE:
            tone_guidance_section = TONE_REVIEW_GUIDANCE[content_tone]

        prompt = f"""
## GÖREV: Post Kalite Kontrolü

### Şirket Profili
{company_profile}

### İçerik Stratejisi
{content_strategy}

### Denetlenecek Post
Konu: {topic}

{post_text}
{tone_guidance_section}

---

Bu post'u aşağıdaki kriterlere göre değerlendir (1-10 puan):

1. **Hook Etkisi** (hook_score): İlk cümle dikkat çekiyor mu?
2. **Değer Önerisi** (value_score): Okuyucuya ne fayda sağlıyor? (İçerik tonuna göre değerlendir)
3. **Marka Uyumu** (brand_score): İçerik tonuna uygun mu? (Her ton farklı değerlendirilir)
4. **Netlik** (clarity_score): Mesaj anlaşılır mı?
5. **CTA** (cta_score): İçerik tonuna uygun aksiyon çağrısı var mı?

Toplam Puan Hesaplama:
total_score = (hook_score × 0.25) + (value_score × 0.25) + (brand_score × 0.20) + (clarity_score × 0.20) + (cta_score × 0.10)
NOT: CTA ağırlığı düşük çünkü her içerik türü güçlü CTA gerektirmez.

Karar:
- total_score 7+ = ONAYLA (approve)
- total_score 5-7 = REVİZYON İSTE (revise)
- total_score <5 = REDDET (reject)

ÇIKTI FORMATI (JSON):
```json
{{
  "decision": "approve|revise|reject",
  "scores": {{
    "hook_score": 8,
    "value_score": 7,
    "brand_score": 9,
    "clarity_score": 8,
    "cta_score": 6
  }},
  "total_score": 7.6,
  "strengths": ["Güçlü yön 1", "Güçlü yön 2"],
  "weaknesses": ["Zayıf yön 1", "Zayıf yön 2"],
  "feedback": "Detaylı geri bildirim...",
  "revision_suggestions": ["Öneri 1", "Öneri 2"],
  "ready_to_publish": true
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            result = json.loads(self._clean_json_response(response))

            # Post durumunu güncelle
            if post_id:
                decision = result.get("decision", "revise")
                if decision == "approve":
                    status = "approved"
                elif decision == "reject":
                    status = "rejected"
                else:
                    status = "draft"  # Revizyon gerekli

                update_post(
                    post_id,
                    status=status,
                    reviewer_feedback=json.dumps(result, ensure_ascii=False)
                )

            log_agent_action(
                agent_name=self.name,
                action="review_post",
                input_data={"topic": topic, "post_id": post_id},
                output_data=result,
                success=True
            )

            self.log(f"Post denetlendi: {result.get('decision', 'N/A')} (Puan: {result.get('total_score', 0)})")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="review_post",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def review_visual(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Görsel prompt'unu denetle"""
        self.log("Görsel prompt denetleniyor...")

        visual_prompt = input_data.get("visual_prompt", "")
        visual_type = input_data.get("visual_type", "flux")
        topic = input_data.get("topic", "")

        visual_guidelines = self.load_context("visual-guidelines.md")

        prompt = f"""
## GÖREV: Görsel Prompt Kontrolü

### Görsel Rehberi
{visual_guidelines}

### Denetlenecek Prompt
Tip: {visual_type}
Konu: {topic}

{visual_prompt}

---

Bu görsel prompt'unu değerlendir:

1. Marka renklerine uygunluk (#4a7c4a, #38bdf8)
2. Konu ile uyum
3. Teknik doğruluk (model için uygun mu?)
4. Görsel kalite potansiyeli

ÇIKTI FORMATI (JSON):
```json
{{
  "decision": "approve|revise",
  "brand_compliance": true,
  "topic_relevance": true,
  "technical_quality": true,
  "feedback": "Geri bildirim...",
  "improved_prompt": "Varsa iyileştirilmiş prompt..."
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=60)

        try:
            result = json.loads(self._clean_json_response(response))

            log_agent_action(
                agent_name=self.name,
                action="review_visual",
                input_data={"visual_type": visual_type, "topic": topic},
                output_data=result,
                success=True
            )

            self.log(f"Görsel prompt denetlendi: {result.get('decision', 'N/A')}")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}

    async def final_approval(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Final onay - tüm içerik hazır mı?"""
        self.log("Final onay kontrolü...")

        post_id = input_data.get("post_id")
        post_text = input_data.get("post_text", "")
        visual_prompt = input_data.get("visual_prompt", "")
        scheduled_time = input_data.get("scheduled_time", "")

        checklist = {
            "has_post_text": bool(post_text and len(post_text) > 50),
            "has_visual_prompt": bool(visual_prompt and len(visual_prompt) > 20),
            "has_schedule": bool(scheduled_time),
            "text_length_ok": 100 <= len(post_text) <= 2000 if post_text else False,
        }

        all_passed = all(checklist.values())

        if post_id and all_passed:
            update_post(post_id, status="approved")

        result = {
            "decision": "approved" if all_passed else "incomplete",
            "checklist": checklist,
            "ready_to_publish": all_passed,
            "missing_items": [k for k, v in checklist.items() if not v]
        }

        log_agent_action(
            agent_name=self.name,
            action="final_approval",
            input_data={"post_id": post_id},
            output_data=result,
            success=True
        )

        self.log(f"Final onay: {'HAZIR' if all_passed else 'EKSİK'}")
        return result

    def validate_carousel_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carousel içeriğini doğrula ve hataları tespit et.

        Args:
            content: Carousel içeriği (slides, caption, hashtags)

        Returns:
            {
                "valid": bool,
                "issues": List[str],
                "auto_fixed": Dict - düzeltilmiş içerik
            }
        """
        issues = []

        content_str = str(content).lower()

        # 1. Yanlış marka adı kontrolü
        wrong_handles = ["olivenetplus", "olivaborplus", "olivenet_plus", "@oliveneet", "olivaborus", "olivarbus"]
        for wrong in wrong_handles:
            if wrong in content_str:
                issues.append(f"HATA: '{wrong}' yanlış, '@olivenet.io' olmalı")

        # 2. Doğru handle kontrolü
        if "@olivenet.io" not in content_str:
            issues.append("UYARI: @olivenet.io handle'ı bulunamadı")

        # 3. Kaydet tekrarı kontrolü
        kaydet_count = content_str.count("kaydet")
        if kaydet_count > 2:
            issues.append(f"UYARI: 'Kaydet' {kaydet_count} kez kullanılmış, fazla")

        # 4. Slide sayısı kontrolü
        slides = content.get("slides", [])
        if len(slides) < 3 or len(slides) > 7:
            issues.append(f"HATA: {len(slides)} slide var, 3-7 arası olmalı")

        # 5. Slide type kontrolü
        if slides:
            first_type = slides[0].get("slide_type", "")
            last_type = slides[-1].get("slide_type", "")
            if first_type != "cover":
                issues.append("UYARI: İlk slide 'cover' tipinde olmalı")
            if last_type not in ("cta", "summary"):
                issues.append("UYARI: Son slide 'cta' veya 'summary' tipinde olmalı")

        # 6. Cover'da "kaydet" OLMAMALI (sadece CTA'da olmalı)
        if slides and len(slides) > 0:
            first_slide_str = str(slides[0]).lower()
            first_slide_raw = str(slides[0])

            # Cover'da "kaydet" OLMAMALI
            if "kaydet" in first_slide_str:
                issues.append("HATA: Cover slide'da 'KAYDET' var - Cover'da olmamalı!")

            # Cover'da 📌 ve 🔖 emojileri de OLMAMALI
            if "📌" in first_slide_raw or "🔖" in first_slide_raw:
                issues.append("HATA: Cover slide'da save emojisi (📌/🔖) var - Cover'da olmamalı!")

            # Content slide'larda (2 to N-1) "kaydet" olmamalı
            for i, slide in enumerate(slides[1:-1], start=2):
                slide_str = str(slide).lower()
                if "kaydet" in slide_str:
                    issues.append(f"HATA: Slide {i}'de 'Kaydet' var - sadece CTA'da olmalı")

        self.log(f"Carousel validasyon: {len(issues)} sorun bulundu")

        return {
            "valid": len([i for i in issues if "HATA" in i]) == 0,
            "issues": issues,
            "auto_fixed": self._auto_fix_carousel(content) if issues else content
        }

    def _auto_fix_carousel(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Marka adı hatalarını ve kaydet yerleşimini otomatik düzelt."""
        content_str = json.dumps(content, ensure_ascii=False)

        # Yanlış handle'ları düzelt (@ olanlar önce, sonra @ olmayanlar)
        fixes = [
            # Önce @ ile başlayanlar
            ("@olivenetplus", "@olivenet.io"),
            ("@olivaborplus", "@olivenet.io"),
            ("@olivaborus", "@olivenet.io"),
            ("@olivarbus", "@olivenet.io"),
            ("@oliveneet", "@olivenet.io"),
            # Sonra @ olmadan
            ("olivenetplus", "olivenet.io"),
            ("olivaborplus", "olivenet.io"),
            ("olivaborus", "olivenet.io"),
            ("olivarbus", "olivenet.io"),
        ]
        for wrong, correct in fixes:
            content_str = content_str.replace(wrong, correct)

        try:
            fixed_content = json.loads(content_str)
            # 1. Cover slide'dan KAYDET'i temizle (EN ÖNCELİKLİ)
            fixed_content = self._clean_cover_slide(fixed_content)
            # 2. Content slide'larından kaydet'i temizle
            fixed_content = self._remove_kaydet_from_content_slides(fixed_content)
            return fixed_content
        except json.JSONDecodeError:
            return content

    def _clean_cover_slide(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Cover slide'dan KAYDET ve save emojilerini temizle - ZORUNLU"""
        slides = content.get("slides", [])
        if not slides:
            return content

        cover = slides[0]
        if not isinstance(cover, dict):
            return content

        def remove_kaydet_from_text(text: str) -> str:
            if not isinstance(text, str):
                return text
            # Tüm KAYDET varyasyonlarını kaldır
            patterns = [
                r'📌\s*KAYDET:?\s*',
                r'🔖\s*KAYDET:?\s*',
                r'📌\s*Kaydet:?\s*',
                r'🔖\s*Kaydet:?\s*',
                r'KAYDET:?\s*',
                r'Kaydet:?\s*',
            ]
            for pattern in patterns:
                text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            # Fazla boşlukları temizle
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        # Cover'daki tüm string alanları temizle
        for key in ["title", "heading", "content", "text", "subtitle"]:
            if key in cover and isinstance(cover[key], str):
                original = cover[key]
                cleaned = remove_kaydet_from_text(cover[key])
                if cleaned != original:
                    cover[key] = cleaned
                    self.log(f"Cover slide'dan KAYDET temizlendi: '{original[:30]}...' → '{cleaned[:30]}...'")

        slides[0] = cover
        content["slides"] = slides
        return content

    def _remove_kaydet_from_content_slides(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Content slide'larından (cover ve cta hariç) 'kaydet' kelimesini kaldır."""
        slides = content.get("slides", [])
        if len(slides) <= 2:
            return content

        # Slide 2 to N-1 (cover=0 ve cta=son hariç)
        for i in range(1, len(slides) - 1):
            slide = slides[i]
            if isinstance(slide, dict):
                for key in ["title", "content", "text", "heading", "subtitle"]:
                    if key in slide and isinstance(slide[key], str):
                        # 🔖 KAYDET: veya kaydet kelimesini temizle
                        original = slide[key]
                        cleaned = re.sub(r'🔖\s*KAYDET:?\s*', '', slide[key], flags=re.IGNORECASE)
                        cleaned = re.sub(r'\bkaydet\b', '', cleaned, flags=re.IGNORECASE)
                        cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # Fazla boşlukları temizle
                        if cleaned != original:
                            slide[key] = cleaned
                            self.log(f"Slide {i+1}'den 'kaydet' temizlendi")

        content["slides"] = slides
        return content
