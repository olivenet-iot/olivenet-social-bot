"""
Reviewer Agent - Kalite kontrol
İçeriği denetler, onaylar veya revizyon ister
"""

import json
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

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""
## GÖREV: Post Kalite Kontrolü

### Şirket Profili
{company_profile}

### İçerik Stratejisi
{content_strategy}

### Denetlenecek Post
Konu: {topic}

{post_text}

---

Bu post'u aşağıdaki kriterlere göre değerlendir (1-10 puan):

1. **Hook Etkisi** (hook_score): İlk cümle dikkat çekiyor mu?
2. **Değer Önerisi** (value_score): Okuyucuya ne fayda sağlıyor?
3. **Marka Uyumu** (brand_score): Şirket tonu ve kimliğine uyuyor mu?
4. **Netlik** (clarity_score): Mesaj anlaşılır mı?
5. **CTA** (cta_score): Aksiyon çağrısı etkili mi?

Toplam Puan Hesaplama:
- 7+ = ONAYLA (approve)
- 5-7 = REVİZYON İSTE (revise)
- <5 = REDDET (reject)

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
