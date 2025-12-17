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
        else:
            return {"error": f"Unknown action: {action}"}

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
            result = json.loads(response)

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
            result = json.loads(response)

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
