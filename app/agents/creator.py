"""
Creator Agent - İçerik üretici
Post metni ve görsel prompt'u üretir
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from app.database import create_post, update_post, log_agent_action

class CreatorAgent(BaseAgent):
    """İçerik üretici - post metni ve görsel üretir"""

    def __init__(self):
        super().__init__("creator")
        self.persona_path = self.context_dir / "social-media-expert.md"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "create_post")

        if action == "create_post":
            return await self.create_post(input_data)
        elif action == "create_visual_prompt":
            return await self.create_visual_prompt(input_data)
        elif action == "revise_post":
            return await self.revise_post(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def create_post(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post metni oluştur"""
        self.log("Post metni oluşturuluyor...")

        topic = input_data.get("topic", "")
        category = input_data.get("category", "egitici")
        hooks = input_data.get("suggested_hooks", [])
        visual_type = input_data.get("visual_type", "flux")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""
## GÖREV: Facebook Post Metni Oluştur

### Şirket Profili
{company_profile}

### İçerik Stratejisi
{content_strategy}

### Post Detayları
- Konu: {topic}
- Kategori: {category}
- Görsel tipi: {visual_type}

### Önerilen Hook'lar
{json.dumps(hooks, ensure_ascii=False)}

---

Yukarıdaki bilgilere dayanarak etkili bir Facebook post metni yaz.

KURALLAR:
1. İlk cümle (hook) çok dikkat çekici olmalı
2. Değer önerisi net olmalı
3. Emoji kullanımı dengeli (3-5 emoji)
4. CTA (aksiyon çağrısı) olmalı
5. Hashtag'ler en sonda olmalı
6. Uzunluk: 150-300 kelime arası
7. Paragraflar kısa olmalı (2-3 cümle)

ÇIKTI FORMATI (JSON):
```json
{{
  "post_text": "Post metni buraya...",
  "hook_used": "Kullanılan hook",
  "cta": "Kullanılan CTA",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "word_count": 180,
  "emoji_count": 4,
  "tone": "professional|friendly|urgent|educational",
  "key_message": "Ana mesaj özeti"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            result = json.loads(response)

            # Database'e kaydet
            post_id = create_post(
                topic=topic,
                post_text=result.get("post_text", ""),
                visual_type=visual_type
            )
            result["post_id"] = post_id

            log_agent_action(
                agent_name=self.name,
                action="create_post",
                input_data={"topic": topic, "category": category},
                output_data=result,
                success=True
            )

            self.log(f"Post oluşturuldu (ID: {post_id})")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="create_post",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def create_visual_prompt(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Görsel için prompt oluştur"""
        self.log("Görsel prompt'u oluşturuluyor...")

        post_text = input_data.get("post_text", "")
        topic = input_data.get("topic", "")
        visual_type = input_data.get("visual_type", "flux")
        post_id = input_data.get("post_id")

        visual_guidelines = self.load_context("visual-guidelines.md")

        # Görsel tipine göre farklı prompt rehberi
        if visual_type == "flux":
            prompt_guide = self.load_context("flux-prompting-guide.md")
            model_instructions = """
FLUX.2 Pro için İngilizce prompt yaz.
Framework: Subject + Action + Style + Context
Marka renkleri: olive green (#4a7c4a), sky blue (#38bdf8)
40-80 kelime arası, pozitif ifadeler kullan.
"""
        elif visual_type == "video":
            prompt_guide = ""
            model_instructions = """
Veo 3 video için İngilizce prompt yaz.
Kamera hareketi + Sahne + Işık + Renk paleti + Atmosfer
5 saniyelik video için uygun, tek sahne.
"""
        else:  # gemini, infographic
            prompt_guide = ""
            model_instructions = """
Gemini için İngilizce prompt yaz.
Fotorealistik, profesyonel fotoğraf tarzı.
IoT/teknoloji temalı, temiz ve modern.
"""

        prompt = f"""
## GÖREV: {visual_type.upper()} Görsel Prompt'u Oluştur

### Görsel Rehberi
{visual_guidelines}

{prompt_guide}

### Post Metni (Türkçe)
{post_text}

### Konu
{topic}

### Model Talimatları
{model_instructions}

---

ÇIKTI FORMATI (JSON):
```json
{{
  "visual_prompt": "İngilizce prompt...",
  "style": "photorealistic|artistic|infographic|cinematic",
  "mood": "professional|warm|energetic|calm",
  "key_elements": ["element1", "element2"],
  "color_palette": ["#4a7c4a", "#38bdf8"],
  "composition_notes": "Kompozisyon notları"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            result = json.loads(response)

            # Post'u güncelle
            if post_id:
                update_post(post_id, visual_prompt=result.get("visual_prompt", ""))

            log_agent_action(
                agent_name=self.name,
                action="create_visual_prompt",
                input_data={"topic": topic, "visual_type": visual_type},
                output_data=result,
                success=True
            )

            self.log(f"Görsel prompt oluşturuldu ({visual_type})")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}

    async def revise_post(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post'u revizyonla"""
        self.log("Post revize ediliyor...")

        post_text = input_data.get("post_text", "")
        feedback = input_data.get("feedback", "")
        post_id = input_data.get("post_id")

        prompt = f"""
## GÖREV: Post Revizyonu

### Mevcut Post
{post_text}

### Geri Bildirim
{feedback}

---

Geri bildirime göre post'u revize et.
Orijinal mesajı ve tonu koru, sadece belirtilen sorunları düzelt.

ÇIKTI FORMATI (JSON):
```json
{{
  "revised_post": "Revize edilmiş post metni...",
  "changes_made": ["Değişiklik 1", "Değişiklik 2"],
  "feedback_addressed": true
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=60)

        try:
            result = json.loads(response)

            # Post'u güncelle
            if post_id:
                from app.database import get_post
                current_post = get_post(post_id)
                revision_count = (current_post.get('revision_count', 0) or 0) + 1
                update_post(
                    post_id,
                    post_text=result.get("revised_post", ""),
                    revision_count=revision_count
                )

            log_agent_action(
                agent_name=self.name,
                action="revise_post",
                input_data={"feedback": feedback},
                output_data=result,
                success=True
            )

            self.log("Post revize edildi")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}
