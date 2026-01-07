"""
Creator Agent - İçerik üretici
Post metni ve görsel prompt'u üretir
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from app.database import (
    create_post, update_post, log_agent_action,
    get_hook_weights_for_selection, get_underperforming_hooks,
    check_duplicate_prompt
)
from app.config import settings

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
        elif action == "create_post_multiplatform":
            return await self.create_post_multiplatform(input_data)
        elif action == "create_visual_prompt":
            return await self.create_visual_prompt(input_data)
        elif action == "create_reels_prompt":
            return await self.create_reels_prompt(input_data)
        elif action == "create_carousel_content":
            return await self.create_carousel_content(input_data)
        elif action == "revise_post":
            return await self.revise_post(input_data)
        elif action == "create_ab_variants":
            return await self.create_ab_variants(input_data)
        elif action == "create_speech_script":
            return await self.create_speech_script(input_data)
        elif action == "process_manual_topic":
            return await self.process_manual_topic(input_data)
        elif action == "create_multi_scene_prompts":
            return await self.create_multi_scene_prompts(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    def _should_avoid_text_in_visual(self, visual_type: str) -> bool:
        """
        Check if text should be avoided in this visual type.

        AI-generated visuals (FLUX, Veo, Sora, Gemini) cannot reliably render text.
        HTML-rendered visuals (infographic, carousel) can include text.
        """
        # HTML render = text OK, AI generation = avoid text
        return visual_type.lower() not in ["infographic", "html", "carousel"]

    async def create_ab_variants(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        A/B Testing: Aynı konu için 2 farklı variant oluştur.

        Her variant farklı:
        - Hook tipi
        - Ton
        - CTA yaklaşımı

        Reviewer agent bu iki variant'ı karşılaştırmalı skorlayacak.
        """
        self.log("A/B test variantları oluşturuluyor...")

        topic = input_data.get("topic", "")
        category = input_data.get("category", "egitici")
        visual_type = input_data.get("visual_type", "flux")
        platform = input_data.get("platform", "instagram")  # instagram veya facebook

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        # 10 hook type tanımları
        hook_types = {
            "statistic": "İstatistik/rakam ile başla",
            "question": "Merak uyandıran soru ile başla",
            "bold_claim": "Cesur/tartışmalı bir iddia ile başla",
            "problem": "Problem/acı noktası ile başla",
            "value": "Somut fayda/değer ile başla",
            "fear": "Korku/FOMO unsuru ile başla",
            "before_after": "Öncesi-sonrası karşılaştırması ile başla",
            "list": "Sayısal liste ile başla (3 yol, 5 ipucu gibi)",
            "comparison": "Karşılaştırma ile başla (A vs B)",
            "local": "KKTC/yerel referans ile başla"
        }

        # Performance-based weighted selection
        import random
        hook_weights = get_hook_weights_for_selection(platform=platform)
        underperforming = set(get_underperforming_hooks(threshold_viral=settings.hook_underperformance_threshold))

        # Düşük performanslı hook'ları filtrele (ama minimum 5 hook kalsın)
        available_hooks = [h for h in hook_types.keys() if h not in underperforming]
        if len(available_hooks) < 5:
            available_hooks = list(hook_types.keys())

        # Weighted random selection (2 farklı hook)
        weights = [hook_weights.get(h, 0.05) for h in available_hooks]
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]

        # İlk hook'u seç
        first_hook = random.choices(available_hooks, weights=weights, k=1)[0]

        # İkinci hook için ilk hook'u çıkar
        remaining_hooks = [h for h in available_hooks if h != first_hook]
        remaining_weights = [hook_weights.get(h, 0.05) for h in remaining_hooks]
        total_remaining = sum(remaining_weights)
        if total_remaining > 0:
            remaining_weights = [w / total_remaining for w in remaining_weights]
        second_hook = random.choices(remaining_hooks, weights=remaining_weights, k=1)[0]

        selected_hooks = [
            (first_hook, hook_types[first_hook]),
            (second_hook, hook_types[second_hook])
        ]

        self.log(f"Hook weights: top={first_hook}({hook_weights.get(first_hook, 0):.2f}), second={second_hook}({hook_weights.get(second_hook, 0):.2f})")

        max_words = 120 if platform == "instagram" else 300

        prompt = f"""
## GÖREV: A/B Test İçin 2 Variant Oluştur

### Şirket Profili
{company_profile[:1500]}

### İçerik Stratejisi Özeti
{content_strategy[:1500]}

### Konu
- Konu: {topic}
- Kategori: {category}
- Platform: {platform}
- Max kelime: {max_words}

---

## A/B TEST KURALLARI:

**VARIANT A:**
- Hook tipi: {selected_hooks[0][0]} - {selected_hooks[0][1]}
- Ton: Profesyonel, bilgilendirici
- CTA: Yumuşak (soru sorma formatı)

**VARIANT B:**
- Hook tipi: {selected_hooks[1][0]} - {selected_hooks[1][1]}
- Ton: Samimi, konuşma dili
- CTA: Doğrudan (DM at, bio linki)

Her iki variant da:
1. Aynı ana mesajı iletmeli
2. Marka değerlerine uygun olmalı
3. Platform kurallarına uymalı (Instagram: max {max_words} kelime)
4. Emoji kullanımı dengeli (3-5)
5. Hashtag'ler aynı olabilir

ÇIKTI FORMATI (JSON):
```json
{{
  "variant_a": {{
    "post_text": "Variant A metni...",
    "hook_type": "{selected_hooks[0][0]}",
    "hook_text": "İlk cümle",
    "tone": "professional",
    "cta_type": "soft",
    "word_count": 95,
    "emoji_count": 4,
    "key_differentiator": "Bu variant neden farklı?"
  }},
  "variant_b": {{
    "post_text": "Variant B metni...",
    "hook_type": "{selected_hooks[1][0]}",
    "hook_text": "İlk cümle",
    "tone": "friendly",
    "cta_type": "direct",
    "word_count": 88,
    "emoji_count": 5,
    "key_differentiator": "Bu variant neden farklı?"
  }},
  "shared": {{
    "topic": "{topic}",
    "hashtags": ["#Olivenet", "#KKTC", "#IoT", "..."],
    "core_message": "Her iki variant'ın ortak ana mesajı"
  }},
  "ab_test_hypothesis": "Bu A/B testle neyi öğrenmeyi hedefliyoruz?"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            result = json.loads(self._clean_json_response(response))

            # Metadata ekle
            result["metadata"] = {
                "created_at": datetime.now().isoformat(),
                "platform": platform,
                "visual_type": visual_type,
                "selected_hook_types": [h[0] for h in selected_hooks]
            }

            log_agent_action(
                agent_name=self.name,
                action="create_ab_variants",
                input_data={"topic": topic, "platform": platform},
                output_data={"variants_created": 2, "hook_types": [h[0] for h in selected_hooks]},
                success=True
            )

            self.log(f"A/B variantları oluşturuldu: {selected_hooks[0][0]} vs {selected_hooks[1][0]}")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="create_ab_variants",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

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
            result = json.loads(self._clean_json_response(response))

            # Database'e kaydet
            post_id = create_post(
                topic=topic,
                post_text=result.get("post_text", ""),
                visual_type=visual_type,
                topic_category=category,
                hook_type=result.get("hook_type")
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

    async def create_post_multiplatform(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Her platform için özel içerik üret (Instagram kısa, Facebook uzun)"""
        import random
        self.log("Çoklu platform içeriği oluşturuluyor...")

        topic = input_data.get("topic", "")
        category = input_data.get("category", "egitici")
        visual_type = input_data.get("visual_type", "flux")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        # Hook performance verisini al
        hook_weights = get_hook_weights_for_selection(platform="instagram")
        top_hooks = sorted(hook_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        underperforming = get_underperforming_hooks(threshold_viral=settings.hook_underperformance_threshold)

        # Hook önerisi oluştur
        hook_hint = f"ÖNCELİKLİ HOOK TİPLERİ (performansa göre): {', '.join([h[0] for h in top_hooks])}"
        if underperforming:
            hook_hint += f"\nKAÇINILMASI GEREKEN: {', '.join(underperforming[:3])}"

        # CTA kararı (her 3 posttan 1'inde)
        use_cta = random.randint(1, 3) == 1
        cta_instruction = "Soft CTA ekle: 'DM at' veya 'Bio linki'" if use_cta else "CTA KOYMA - sadece düşündürücü bir soru ile bitir"

        # Instagram içeriği (kısa)
        ig_prompt = f"""
## GÖREV: Instagram Post Yaz

### Konu
{topic}

### Kategori
{category}

### Şirket Profili
{company_profile[:1500]}

### HOOK STRATEJİSİ
{hook_hint}

### INSTAGRAM FORMATI (ÇOK ÖNEMLİ!)
- MAX 80 KELİME (kesinlikle aşma!)
- Hook ile başla (yukarıdaki öncelikli tiplerden birini kullan)
- 2-3 cümle ana mesaj (kısa ve öz)
- {cta_instruction}
- 5-8 hashtag (sabit: #Olivenet #KKTC #IoT + rotasyonlu)
- MARKDOWN KULLANMA: **bold**, *italic*, `code` YASAK (Instagram desteklemiyor)
- Vurgu için BÜYÜK HARF veya emoji kullan

### ENGAGEMENT OPTİMİZASYONU
- Her 3-4 posttan birinde: "📌 Kaydet!" veya "🔖 Yer imi ekle!" ekle
- Konu uygunsa: "📲 Bu bilgiyi ihtiyacı olan biriyle paylaş" ekle
- Caption sonunda soru sor (yorum tetikler)

### ÖRNEK FORMAT
🌱 [Dikkat çekici hook]

[Ana mesaj - kısa ve öz]

- Madde 1
- Madde 2

[Kapanış: Soru veya "📌 Kaydet, lazım olduğunda kullan!"]

#Olivenet #KKTC #IoT #AkıllıTarım ...

Sadece post metnini yaz, başka açıklama ekleme.
"""

        ig_response = await self.call_claude(ig_prompt, timeout=60)
        ig_text = ig_response.strip()

        # Instagram caption uzunluk kontrolü
        max_words = self._get_max_caption_length("post")
        ig_word_count = len(ig_text.split())
        if ig_word_count > max_words * 1.2:  # %20 tolerans
            self.log(f"⚠️ IG caption çok uzun ({ig_word_count} kelime), kısaltılıyor...")
            ig_text = await self._shorten_caption(ig_text, max_words)

        # Facebook içeriği (uzun)
        fb_prompt = f"""
## GÖREV: Facebook Post Yaz

### Konu
{topic}

### Kategori
{category}

### Şirket Profili
{company_profile[:2000]}

### FACEBOOK FORMATI
- 200-300 kelime (daha detaylı)
- Problem → Çözüm → Fayda yapısı
- Profesyonel ama samimi ton
- Detaylı açıklama ve değer önerisi
- CTA ile bitir (iletişim bilgisi: info@olivenet.io)
- 6-8 hashtag

Sadece post metnini yaz, başka açıklama ekleme.
"""

        fb_response = await self.call_claude(fb_prompt, timeout=60)
        fb_text = fb_response.strip()

        # Text-based prompt, hook_type çıkarılamıyor
        hook_type = None

        # Database'e kaydet
        post_id = create_post(
            topic=topic,
            post_text_ig=ig_text,
            post_text_fb=fb_text,
            visual_type=visual_type,
            topic_category=category,
            hook_type=hook_type
        )

        ig_words = len(ig_text.split())
        fb_words = len(fb_text.split())

        self.log(f"Post oluşturuldu (ID: {post_id})")
        self.log(f"IG: {ig_words} kelime, FB: {fb_words} kelime")

        log_agent_action(
            agent_name=self.name,
            action="create_post_multiplatform",
            input_data={"topic": topic, "category": category},
            output_data={"post_id": post_id, "ig_words": ig_words, "fb_words": fb_words},
            success=True
        )

        return {
            "success": True,
            "post_id": post_id,
            "post_text": fb_text,  # Backward compatibility
            "post_text_ig": ig_text,
            "post_text_fb": fb_text,
            "topic": topic,
            "word_count": fb_words,
            "ig_word_count": ig_words
        }

    async def create_visual_prompt(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Görsel için prompt oluştur"""
        self.log("Görsel prompt'u oluşturuluyor...")

        post_text = input_data.get("post_text", "")
        topic = input_data.get("topic", "")
        visual_type = input_data.get("visual_type") or "flux"  # None-safe
        post_id = input_data.get("post_id")

        visual_guidelines = self.load_context("visual-guidelines.md")

        # No-text suffix for AI-generated visuals
        no_text_suffix = ""
        if self._should_avoid_text_in_visual(visual_type):
            no_text_suffix = """

VISUAL STYLE - CRITICAL:
- NO TEXT or written words in the image
- Use visual metaphors and icons instead
- Focus on photorealistic imagery without labels
"""

        # Görsel tipine göre farklı prompt rehberi
        if visual_type == "flux":
            prompt_guide = self.load_context("flux-prompting-guide.md")
            model_instructions = f"""
FLUX.2 Pro için İngilizce prompt yaz.
Framework: Subject + Action + Style + Context
Marka renkleri: olive green (#4a7c4a), sky blue (#38bdf8)
40-80 kelime arası, pozitif ifadeler kullan.
{no_text_suffix}"""
        elif visual_type == "video":
            prompt_guide = ""
            model_instructions = f"""
Veo 3 video için İngilizce prompt yaz.
Kamera hareketi + Sahne + Işık + Renk paleti + Atmosfer
5 saniyelik video için uygun, tek sahne.
{no_text_suffix}"""
        else:  # gemini, infographic
            prompt_guide = ""
            model_instructions = f"""
Gemini için İngilizce prompt yaz.
Fotorealistik, profesyonel fotoğraf tarzı.
IoT/teknoloji temalı, temiz ve modern.
{no_text_suffix}"""

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
            result = json.loads(self._clean_json_response(response))

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
            result = json.loads(self._clean_json_response(response))

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

    async def create_reels_prompt(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instagram Reels için profesyonel video prompt üret
        Sora 2 ve Veo 3 formatlarını destekler
        """
        self.log("Reels video prompt'u oluşturuluyor...")

        topic = input_data.get("topic", "")
        category = input_data.get("category", "tanitim")
        post_text = input_data.get("post_text", "")
        post_id = input_data.get("post_id")
        speech_structure = input_data.get("speech_structure", [])
        voice_mode = input_data.get("voice_mode", False)

        # Context yükle
        reels_guide = self.load_context("reels-prompts.md")
        company_profile = self.load_context("company-profile.md")

        # Speech-Video senkronizasyon rehberi (voice_mode için)
        sync_guide = ""
        if voice_mode and speech_structure:
            sync_guide = """

### 🎙️ SPEECH-VIDEO SENKRONİZASYONU
Bu video TTS voiceover ile birleştirilecek. Her shot, aşağıdaki speech içeriğine UYGUN görsel içermeli:

"""
            for shot in speech_structure:
                sync_guide += f"**[{shot['time']}]**: \"{shot['concept']}\"\n"
                if shot.get('keywords'):
                    sync_guide += f"   → Keywords: {', '.join(shot['keywords'])}\n"
                sync_guide += "\n"

            sync_guide += """
⚠️ ÖNEMLİ KURALLAR (Voice Mode):
- Video'da KONUŞAN İNSAN olmamalı (voiceover dışarıdan eklenecek)
- Lip sync / dudak hareketi YOK
- Her shot'ın görseli, o anda söylenen kavrama uygun olmalı
- Örnek: "Sensörler..." denirken → sensör close-up göster
"""

        prompt = f"""
## GÖREV: Instagram Reels için Profesyonel Video Prompt Oluştur

### Konu
{topic}

### Kategori
{category}

### Post Metni (varsa)
{post_text[:300] if post_text else "Yok"}

### Şirket Bilgisi
{company_profile[:800]}

### Profesyonel Prompting Rehberi
{reels_guide[:1500]}
{sync_guide}
---

## ÇIKTI FORMATI (JSON)
```json
{{
    "video_prompt_sora": "SORA 2 formatında detaylı İngilizce prompt (sahne + cinematography + lighting + actions + sound)",
    "video_prompt_veo": "VEO 3 timestamp formatında İngilizce prompt ([00:00-00:02] format)",
    "video_prompt_kling": "KLING formatında kısa İngilizce prompt (Subject + Movement + Scene + Camera + Lighting + Atmosphere, virgülle ayrılmış, max 200 karakter)",
    "video_prompt_hailuo": "HAILUO formatında dinamik İngilizce prompt (Camera Motion + Subject + Action + Scene + Lighting + Style, aksiyon odaklı, max 200 karakter)",
    "video_prompt_wan": "WAN formatında multi-shot sinematik prompt (Global style + Shot timing brackets [0-5s] + Camera action, max 600 karakter)",
    "complexity": "low|medium|high",
    "recommended_model": "veo3|sora-2|sora-2-pro|kling_pro|hailuo_pro|wan_26",
    "recommended_duration": 5,
    "hook_description": "İlk 2 saniyede ne görünecek (Türkçe)",
    "caption_ig": "Instagram Reels caption (Türkçe, max 50 kelime, hook+değer+CTA formatı, emoji'li)",
    "hashtags": ["Olivenet", "KKTC", "IoT", "..."],
    "camera_movement": "static|dolly|pan|arc|reveal",
    "mood": "professional|calm|energetic|inspirational"
}}
```

### ÖNEMLİ KURALLAR:
1. video_prompt_sora, video_prompt_veo, video_prompt_kling, video_prompt_hailuo ve video_prompt_wan İNGİLİZCE olmalı
2. 9:16 dikey format belirt (720x1280)
3. Süre 5-6 saniye hedefle (Kling için 10 saniyeye kadar olabilir)
4. İlk 2 saniye HOOK olmalı - dikkat çekici
5. Olivenet renkleri: Yeşil (#2E7D32), Mavi (#38bdf8)
6. Tek sahne, akıcı hareket
7. Gerçekçi ve üretilebilir prompt yaz

### KLING FORMAT KURALLARI (video_prompt_kling):
- Basit, virgülle ayrılmış İngilizce
- Formül: Subject + Description + Movement + Scene + Camera + Lighting + Atmosphere
- Max 200 karakter
- Sayı kullanma, "multiple" veya "several" yaz
- Karmaşık fiziksel hareket YOK (top sektirme, koşma vb.)
- Örnek: "Medium shot, bokeh background, a technician in safety helmet, checking sensor readings, industrial factory, warm ambient lighting, professional documentary style."

### HAILUO FORMAT KURALLARI (video_prompt_hailuo):
- Dinamik kamera hareketleri: tracking shot, dolly, pan
- Aksiyon fiilleri: running, spinning, transforming, flowing
- Formül: [Camera Motion] + [Subject + Action] + [Scene] + [Lighting] + [Style]
- Max 200 karakter
- 6 saniyelik içerik için optimize et
- Örnek: "Tracking shot, technician running through factory, sparks flying, industrial lighting, energetic cinematic style."

### WAN FORMAT KURALLARI (video_prompt_wan):
- İlk cümlede global stil (Photoreal, 4K, cinematic lighting)
- Multi-shot için timing bracket: [0-5s], [5-10s], [10-15s]
- Kamera hareketleri: push, pull, pan, track, orbit
- Max 600 karakter
- 15 saniyeye kadar içerik
- Örnek: "Industrial facility. Cinematic, 4K. Shot 1 [0-5s] Wide establishing shot of factory exterior at dawn. Shot 2 [5-10s] Camera tracks through control room, engineers at dashboards. Shot 3 [10-15s] Close-up of IoT sensor with pulsing LED."

### COMPLEXITY KURALLARI:
- LOW: Tek sahne, statik/basit hareket → veo3 veya kling_pro
- MEDIUM: Kamera takibi, 2-3 element → sora-2 veya hailuo_pro (dinamik sahneler için)
- HIGH: Dönüşüm, kompleks hareket → sora-2-pro veya hailuo_pro

Sadece JSON döndür, başka açıklama ekleme.
"""

        # Agresif logging - LLM çağrısı öncesi
        self.log(f"[REELS PROMPT] LLM cagriliyior - voice_mode: {voice_mode}, shots: {len(speech_structure)}")
        self.log(f"[REELS PROMPT] Prompt: {len(prompt)} chars")

        # Retry mekanizması - boş JSON için de retry yap
        MAX_RETRIES = 3
        response = None
        result = None
        video_prompt = None
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.call_claude_with_retry(prompt, timeout=90, max_retries=2)
                self.log(f"[REELS PROMPT] Attempt {attempt + 1}/{MAX_RETRIES} - Response: {len(response) if response else 0} chars")

                if not response or not response.strip() or response.strip() == "{}":
                    last_error = "Empty or {} response"
                    self.log(f"[REELS PROMPT] Bos response, retry...")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(3)  # 3 saniye bekle
                    continue

                # JSON parse
                result = json.loads(self._clean_json_response(response))

                # Video prompt var mı kontrol et
                video_prompt = result.get("video_prompt_sora") or result.get("video_prompt_veo") or result.get("video_prompt_wan", "")

                if video_prompt and video_prompt.strip():
                    self.log(f"[REELS PROMPT] Basarili! Video prompt: {len(video_prompt)} chars")
                    break  # Başarılı
                else:
                    last_error = f"Video prompt bos, keys: {list(result.keys())}"
                    self.log(f"[REELS PROMPT] {last_error}, retry...")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(3)

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
                self.log(f"[REELS PROMPT] {last_error}")
                self.log(f"[REELS PROMPT] Raw response: {response[:500] if response else 'EMPTY'}...")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(3)

            except Exception as e:
                last_error = f"Exception: {type(e).__name__}: {e}"
                self.log(f"[REELS PROMPT] {last_error}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(3)

        # Tüm denemeler başarısız
        if not video_prompt or not video_prompt.strip():
            self.log(f"WARNING: Tum {MAX_RETRIES} deneme basarisiz: {last_error}")
            self.log(f"[DEBUG] Result keys: {list(result.keys()) if result else 'None'}")
            self.log(f"[DEBUG] Raw response preview: {response[:300] if response else 'EMPTY'}...")
            return {"success": False, "error": f"LLM failed after {MAX_RETRIES} retries: {last_error}", "raw_response": response[:500] if response else "EMPTY"}

        # Başarılı - Post'u güncelle
        if post_id:
            update_post(post_id, visual_prompt=video_prompt)

        complexity = result.get("complexity", "medium")
        model = result.get("recommended_model", "veo3")

        self.log(f"Reels prompt oluşturuldu")
        self.log(f"   Complexity: {complexity}")
        self.log(f"   Model: {model}")
        self.log(f"   Duration: {result.get('recommended_duration', 5)}s")

        log_agent_action(
            agent_name=self.name,
            action="create_reels_prompt",
            input_data={"topic": topic, "category": category},
            output_data={"complexity": complexity, "model": model},
            success=True
        )

        return {
            "success": True,
            **result
        }

    async def create_multi_scene_prompts(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Multi-segment video için tutarlı sahne promptları üret.

        Her segment için ayrı video prompt oluşturur, tüm segmentler arasında
        görsel tutarlılık sağlamak için ortak stil prefix'i kullanır.

        Args:
            input_data: {
                "topic": str - Video konusu
                "segment_count": int - Segment sayısı (2-6)
                "segment_duration": int - Her segment'in süresi (saniye)
                "speech_structure": List[Dict] - Shot structure (opsiyonel)
                "model_id": str - Video modeli (opsiyonel)
            }

        Returns:
            {
                "success": bool,
                "style_prefix": str - Tüm segmentlere eklenecek stil
                "scenes": List[Dict] - Her segment için sahne bilgisi
                "narrative_arc": str - Hikaye yapısı
            }
        """
        self.log("Multi-scene promptlar oluşturuluyor...")

        topic = input_data.get("topic", "")
        segment_count = input_data.get("segment_count", 3)
        segment_duration = input_data.get("segment_duration", 10)
        speech_structure = input_data.get("speech_structure", [])
        model_id = input_data.get("model_id", "kling-2.6-pro")

        # Segment sayısı sınırla
        segment_count = max(2, min(6, segment_count))

        # Toplam süre
        total_duration = segment_count * segment_duration

        # Speech structure'dan zaman aralıklarını oluştur
        time_ranges = []
        for i in range(segment_count):
            start = i * segment_duration
            end = (i + 1) * segment_duration
            time_ranges.append(f"{start}-{end}s")

        # Speech structure'dan içerik ipuçlarını al
        speech_hints = ""
        if speech_structure:
            for i, shot in enumerate(speech_structure[:segment_count]):
                shot_concept = shot.get("concept", "")
                shot_keywords = shot.get("keywords", [])
                speech_hints += f"\n[{time_ranges[i]}] İçerik: {shot_concept}"
                if shot_keywords:
                    speech_hints += f" | Anahtar kelimeler: {', '.join(shot_keywords)}"

        # Dinamik narrative arc (segment sayısına göre)
        if segment_count == 2:
            narrative_arc_text = """### NARRATİF ARC (2 Segment - 20s):
- Sahne 1 (0-10s): HOOK + PROBLEM - Dikkat çekici açılış, problem tanıtımı
- Sahne 2 (10-20s): SOLUTION + CTA - Çözüm, faydalar, call-to-action"""
            narrative_arc_json = "hook+problem -> solution+cta"
            example_roles = ["hook+problem", "solution+cta"]
        elif segment_count == 3:
            narrative_arc_text = """### NARRATİF ARC (3 Segment - 30s):
- Sahne 1 (0-10s): HOOK - Dikkat çekici açılış, problem tanıtımı
- Sahne 2 (10-20s): DEVELOPMENT - Çözümün açıklanması, detaylar
- Sahne 3 (20-30s): RESOLUTION - Faydalar, sonuç, call-to-action"""
            narrative_arc_json = "hook -> development -> resolution"
            example_roles = ["hook", "development", "resolution"]
        else:  # 4+ segment
            narrative_arc_text = f"""### NARRATİF ARC ({segment_count} Segment):
- Sahne 1: HOOK - Dikkat çekici açılış
- Sahneler 2-{segment_count-1}: DEVELOPMENT - Ana içerik, detaylar
- Son sahne: RESOLUTION - Sonuç, çözüm gösterimi"""
            narrative_arc_json = "hook -> development -> resolution"
            example_roles = ["hook"] + ["development"] * (segment_count - 2) + ["resolution"]

        prompt = f"""
## GÖREV: Multi-Segment Video Sahne Planlaması

Aşağıdaki konu için {segment_count} adet tutarlı video sahnesi oluştur.
Her sahne {segment_duration} saniye sürecek, toplam {total_duration} saniye.

### KONU:
{topic}

### SES YAPISI (varsa):
{speech_hints if speech_hints else "Ses yapısı belirtilmedi."}

### TUTARLILIK GEREKSİNİMLERİ:
- Tüm sahnelerde AYNI ışık kalitesi (profesyonel stüdyo ışığı)
- Tüm sahnelerde AYNI renk paleti (Olivenet: yeşil #2E7D32, mavi #38bdf8, beyaz)
- Tüm sahnelerde AYNI kamera stili (4K sinematik)
- Sahneler arası görsel geçiş uyumu
- NO TEXT - hiçbir sahnede yazı olmamalı

{narrative_arc_text}

### ÇIKTI FORMATI (JSON):
```json
{{
    "style_prefix": "4K cinematic, professional studio lighting, color palette: olive green (#2E7D32), sky blue (#38bdf8), clean white background, no text or labels, ",
    "narrative_arc": "{narrative_arc_json}",
    "scenes": [
        {{
            "segment_index": 0,
            "time_range": "{time_ranges[0]}",
            "narrative_role": "{example_roles[0]}",
            "visual_concept": "Kısa açıklama",
            "camera_movement": "Kamera hareketi (dolly, pan, zoom, etc.)",
            "prompt": "Detaylı video prompt (İngilizce, 50-80 kelime)"
        }},
        ...
    ]
}}
```

### VIDEO MODEL BİLGİSİ:
Model: {model_id}
- Promptlar İngilizce olmalı
- Her prompt 50-80 kelime arası olmalı
- Kamera hareketini açıkça belirt
- Sahne detaylarını (nesne, eylem, ortam) açıkla

Sadece JSON döndür.
"""

        MAX_RETRIES = 3
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.call_claude(prompt, timeout=90)
                result = json.loads(self._clean_json_response(response))

                # Validasyon
                if "scenes" not in result:
                    last_error = "scenes key eksik"
                    continue

                scenes = result.get("scenes", [])
                if len(scenes) < segment_count:
                    last_error = f"Yetersiz sahne: {len(scenes)}/{segment_count}"
                    continue

                # Scenes'i segment_count'a kırp
                result["scenes"] = scenes[:segment_count]

                # Style prefix yoksa varsayılan ekle
                if not result.get("style_prefix"):
                    result["style_prefix"] = (
                        "4K cinematic, professional studio lighting, "
                        "color palette: olive green, sky blue, clean white background, "
                        "no text or labels, smooth camera movement, "
                    )

                self.log(f"Multi-scene promptlar oluşturuldu")
                self.log(f"   Segment sayısı: {len(result['scenes'])}")
                self.log(f"   Narrative arc: {result.get('narrative_arc', 'N/A')}")

                log_agent_action(
                    agent_name=self.name,
                    action="create_multi_scene_prompts",
                    input_data={"topic": topic, "segment_count": segment_count},
                    output_data={"scene_count": len(result["scenes"])},
                    success=True
                )

                return {
                    "success": True,
                    **result
                }

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
                self.log(f"[MULTI-SCENE] Attempt {attempt + 1}: {last_error}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)

            except Exception as e:
                last_error = str(e)
                self.log(f"[MULTI-SCENE] Attempt {attempt + 1}: {last_error}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)

        # Tüm denemeler başarısız
        log_agent_action(
            agent_name=self.name,
            action="create_multi_scene_prompts",
            success=False,
            error_message=last_error
        )

        return {
            "success": False,
            "error": f"Multi-scene prompt generation failed: {last_error}"
        }

    async def create_speech_script(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instagram Reels için Türkçe voiceover scripti üret.

        ElevenLabs TTS ile seslendirilecek metin oluşturur.
        Süre bazlı kelime hedefi ile çalışır (~2.5 kelime/saniye).

        Args:
            input_data: {
                "topic": str - Konu
                "target_duration": int - Hedef süre (12, 15, veya 20 saniye)
                "tone": str - Ses tonu (professional, friendly, energetic)
                "post_id": int (opsiyonel) - Güncellenecek post ID
            }

        Returns:
            {
                "success": bool,
                "speech_script": str - Voiceover metni
                "word_count": int - Kelime sayısı
                "estimated_duration": float - Tahmini süre
                "hook": str - İlk cümle
                "key_points": List[str] - Ana noktalar
                "cta": str - Kapanış çağrısı
            }
        """
        self.log("Voiceover scripti oluşturuluyor...")

        topic = input_data.get("topic", "")
        target_duration = input_data.get("target_duration", 15)
        tone = input_data.get("tone", "friendly")  # Samimi ton varsayılan
        post_id = input_data.get("post_id")

        # Pipeline'dan gelen target_words'u kullan (varsa)
        target_words = input_data.get("target_words")
        if not target_words:
            # Fallback: süre bazlı hesapla (~3.0 kelime/saniye - ElevenLabs gerçek hızı)
            target_words = int(target_duration * 3.0)

        company_profile = self.load_context("company-profile.md")

        # Ton açıklamaları
        tone_descriptions = {
            "professional": "Profesyonel, güvenilir, bilgilendirici. Kurumsal ama soğuk değil.",
            "friendly": "Samimi, sıcak, konuşma dili. Sanki bir arkadaşla sohbet.",
            "energetic": "Enerjik, heyecanlı, motive edici. Dikkat çekici ve dinamik."
        }
        tone_desc = tone_descriptions.get(tone, tone_descriptions["friendly"])

        prompt = f"""
## GÖREV: Instagram Reels Voiceover Scripti Yaz

### Konu
{topic}

### Hedefler
- Süre: {target_duration} saniye
- Kelime sayısı: ~{target_words} kelime (ASLA AŞMA!)
- Ton: {tone} - {tone_desc}

### Şirket Bilgisi
{company_profile[:1500]}

---

## VOICEOVER SCRIPT KURALLARI:

### YAPI (3 BÖLÜM):
1. **HOOK (0-3 saniye)**: Dikkat çekici açılış
   - Merak uyandıran soru VEYA
   - Şaşırtıcı istatistik VEYA
   - Cesur bir iddia

2. **ANA İÇERİK ({target_duration-6} saniye)**: Değer sun
   - 2-3 kısa nokta
   - Somut fayda veya bilgi
   - Pratik uygulama

3. **CTA (son 3 saniye)**: Aksiyon çağrısı
   - "Takip et" VEYA
   - "Kaydet" VEYA
   - Düşündürücü soru

### FORMAT KURALLARI:
- DOĞAL konuşma dili kullan (yazı dili değil!)
- KISA cümleler (max 10-12 kelime)
- Emoji KULLANMA (sesli okunacak)
- Türkçe karakterler: ı, ş, ğ, ü, ö, ç
- Sayıları YAZI ile yaz ("3" değil "üç")
- Kısaltma KULLANMA (IoT → "ay o ti" veya "nesnelerin interneti")
- Noktalama işaretleri doğru (virgül = kısa duraklama, nokta = uzun duraklama)

### YASAK İFADELER:
- "Merhaba", "Selam" (vakit kaybı)
- "Bu videoda" (belli zaten)
- Aşırı uzun cümleler
- Jargon ve teknik terimler (basitleştir)

### TON: {tone.upper()}
{tone_desc}

---

## ÇIKTI FORMATI (JSON):
```json
{{
    "speech_script": "Tam voiceover metni. Cümleler arası doğal akış. Hook ile başla, CTA ile bitir.",
    "hook": "İlk cümle (3 saniye içinde söylenecek)",
    "key_points": ["Nokta 1", "Nokta 2", "Nokta 3"],
    "cta": "Kapanış cümlesi",
    "word_count": {target_words},
    "estimated_duration": {target_duration},
    "tone_used": "{tone}"
}}
```

### ÖNEMLİ:
- word_count {target_words}'i AŞMAMALI
- speech_script TAM ve AKICI olmalı (copy-paste ile TTS'e verilebilir)
- Her cümle sesli okunduğunda doğal duyulmalı

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=60)

        try:
            result = json.loads(self._clean_json_response(response))

            # Kelime sayısı kontrolü
            script = result.get("speech_script", "")
            actual_words = len(script.split())

            if actual_words > target_words * 1.3:  # %30 tolerans
                self.log(f"⚠️ Script çok uzun ({actual_words} kelime), kısaltılıyor...")
                script = await self._shorten_speech_script(script, target_words)
                result["speech_script"] = script
                result["word_count"] = len(script.split())

            # Süre tahmini güncelle
            result["estimated_duration"] = len(script.split()) / 2.5

            # Post'u güncelle
            if post_id:
                update_post(post_id, speech_script=script)

            log_agent_action(
                agent_name=self.name,
                action="create_speech_script",
                input_data={"topic": topic, "target_duration": target_duration},
                output_data={
                    "word_count": result.get("word_count"),
                    "estimated_duration": result.get("estimated_duration")
                },
                success=True
            )

            self.log(f"Voiceover scripti oluşturuldu")
            self.log(f"   Kelime: {result.get('word_count')}")
            self.log(f"   Süre: ~{result.get('estimated_duration'):.1f}s")

            return {
                "success": True,
                **result
            }

        except json.JSONDecodeError as e:
            self.log(f"JSON parse hatası: {e}")
            log_agent_action(
                agent_name=self.name,
                action="create_speech_script",
                success=False,
                error_message=f"JSON parse error: {e}"
            )
            return {"success": False, "error": f"JSON parse error: {e}", "raw_response": response[:500]}

    async def _shorten_speech_script(self, script: str, target_words: int) -> str:
        """
        Voiceover scriptini kısalt.

        Args:
            script: Kısaltılacak script
            target_words: Hedef kelime sayısı

        Returns:
            Kısaltılmış script
        """
        prompt = f"""
Aşağıdaki voiceover scriptini {target_words} kelimeye kısalt.

KURALLAR:
- Hook'u (ilk cümleyi) koru
- Ana mesajı koru
- CTA'yı (son cümleyi) koru
- Gereksiz tekrarları çıkar
- Doğal akışı bozma

SCRIPT:
{script}

Sadece kısaltılmış scripti döndür, başka bir şey ekleme.
"""

        response = await self.call_claude(prompt, timeout=30)
        return response.strip()

    async def create_carousel_content(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instagram Carousel için çoklu görsel içeriği üret.

        Args:
            input_data: {
                "topic": str - Ana konu
                "slide_count": int - Slide sayısı (default 5)
                "category": str - Kategori (egitici, showcase, vb.)
            }

        Returns:
            {
                "post_id": int,
                "caption": str,
                "slides": List[Dict],
                "hashtags": List[str],
                "slide_count": int
            }
        """
        self.log("Carousel içeriği oluşturuluyor...")

        topic = input_data.get("topic", "")
        slide_count = input_data.get("slide_count", 5)
        category = input_data.get("category", "egitici")

        # Slide sayısı sınırlaması
        slide_count = max(3, min(slide_count, 7))

        company_profile = self.load_context("company-profile.md")
        visual_guidelines = self.load_context("visual-guidelines.md")

        prompt = f"""
## GÖREV: Instagram Carousel İçeriği Oluştur

### ⚠️ MARKA BİLGİSİ (KRİTİK!)
- Instagram: @olivenet.io (DİKKAT: olivenetplus, olivaborplus vb. DEĞİL!)
- Website: olivenet.io
- Email: info@olivenet.io

### Şirket Profili
{company_profile[:1500]}

### Görsel Rehberi
{visual_guidelines[:1000]}

### Carousel Detayları
- Konu: {topic}
- Slide sayısı: {slide_count}
- Kategori: {category}

---

## TALİMATLAR

Eğitici ve görsel açıdan tutarlı bir carousel oluştur.

### Slide Yapısı ve Tipleri:
1. **Slide 1 (cover)**: Dikkat çekici kısa başlık + merak uyandıran soru/istatistik
2. **Slide 2-{slide_count-1} (content/stats)**: Ana bilgiler, adımlar veya karşılaştırmalar
3. **Slide {slide_count} (cta)**: "📌 Kaydet & Takip Et!" + CTA

### SLIDE TİPLERİ (ZORUNLU):
- **cover**: İlk slide, dikkat çekici hook (KAYDET KULLANMA!)
- **content**: Bullet point'ler, numaralı liste
- **stats**: Büyük rakamlar, istatistikler
- **comparison**: Yan yana karşılaştırma
- **cta**: Son slide, kaydet/takip et çağrısı

### ⛔ COVER SLIDE KURALLARI (KRİTİK):
- Cover'da "KAYDET" kelimesi KULLANMA
- Cover'da 📌 veya 🔖 emojileri KULLANMA
- Cover sadece dikkat çekici başlık içermeli (5-8 kelime)
- "KAYDET" SADECE son slide'da (CTA) kullanılabilir!

### SAVE-OPTİMİZE İÇERİK:
- Son slide kaydetmeye teşvik etmeli (📌 emojisi)
- İçerik referans değeri taşımalı (checklist, adımlar, karşılaştırma)

### Her Slide İçin:
- slide_type: cover, content, stats, comparison veya cta
- title: Kısa başlık (max 5 kelime)
- content: Ana metin (max 30 kelime, bullet point'ler tercih edilir)

### Caption (KISA ve SAVE-FOCUSED):
- MAX 30 KELİME (bilgi slide'larda, caption minimal!)
- Tek satır hook veya soru ile başla
- "📌 Kaydet!" veya "🔖 Yer imi ekle!" ile bitir
- Slide içeriğini caption'da TEKRARLAMA

### Hashtag'ler:
- 6-8 adet
- Sabit: #Olivenet #KKTC #IoT
- Konu bazlı eklemeler

---

## ÇIKTI FORMATI (JSON):
```json
{{
    "caption": "Instagram caption metni...",
    "slides": [
        {{
            "slide_type": "cover",
            "title": "Enerji Faturanızı %40 Düşürün",
            "content": "Sera sahibi misiniz? Bu 3 yöntem ile tasarruf edin!"
        }},
        {{
            "slide_type": "content",
            "title": "Adım 1",
            "content": "- Madde 1\\n- Madde 2\\n- Madde 3"
        }},
        {{
            "slide_type": "stats",
            "title": "Rakamlarla",
            "content": "%75 verimlilik artışı\\n%50 maliyet düşüşü"
        }},
        {{
            "slide_type": "cta",
            "title": "📌 Kaydet!",
            "content": "Daha fazlası için takip et\\n@olivenet.io"
        }}
    ],
    "hashtags": ["#Olivenet", "#KKTC", "#IoT", ...]
}}
```

### ÖNEMLİ:
1. Her slide'da slide_type zorunlu (cover, content, stats, comparison, cta)
2. İlk slide: cover, son slide: cta olmalı
3. Slides dizisi tam {slide_count} element içermeli
4. Title ve content Türkçe olmalı

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            result = json.loads(self._clean_json_response(response))

            # Database'e kaydet
            caption = result.get("caption", "")
            hashtags = result.get("hashtags", [])

            # Carousel caption uzunluk kontrolü
            max_words = self._get_max_caption_length("carousel")
            caption_word_count = len(caption.split())
            if caption_word_count > max_words * 1.2:  # %20 tolerans
                self.log(f"⚠️ Carousel caption çok uzun ({caption_word_count} kelime), kısaltılıyor...")
                caption = await self._shorten_caption(caption, max_words)
                result["caption"] = caption

            post_id = create_post(
                topic=topic,
                post_text=caption,
                post_text_ig=caption,
                visual_type="carousel",
                platform="instagram",
                topic_category=category,
                hook_type=result.get("hook_type")
            )

            slides = result.get("slides", [])

            log_agent_action(
                agent_name=self.name,
                action="create_carousel_content",
                input_data={"topic": topic, "slide_count": slide_count},
                output_data={"post_id": post_id, "slide_count": len(slides)},
                success=True
            )

            self.log(f"Carousel oluşturuldu (ID: {post_id}, {len(slides)} slide)")

            return {
                "success": True,
                "post_id": post_id,
                "caption": caption,
                "slides": slides,
                "hashtags": hashtags,
                "slide_count": len(slides),
                "topic": topic
            }

        except json.JSONDecodeError as e:
            self.log(f"JSON parse hatası: {e}")
            log_agent_action(
                agent_name=self.name,
                action="create_carousel_content",
                success=False,
                error_message=f"JSON parse error: {e}"
            )
            return {"success": False, "error": f"JSON parse error: {e}", "raw_response": response[:500]}

    def _get_max_caption_length(self, content_type: str) -> int:
        """
        İçerik tipine göre max caption uzunluğu (kelime).

        Args:
            content_type: İçerik tipi (reels, carousel, post, image)

        Returns:
            Max kelime sayısı
        """
        limits = {
            "reels": 50,
            "carousel": 30,
            "post": 80,
            "image": 80
        }
        return limits.get(content_type.lower(), 60)

    async def _shorten_caption(self, caption: str, max_words: int) -> str:
        """
        Caption'ı AI ile kısalt.

        Args:
            caption: Kısaltılacak caption
            max_words: Hedef max kelime sayısı

        Returns:
            Kısaltılmış caption
        """
        self.log(f"Caption kısaltılıyor: {len(caption.split())} → {max_words} kelime")

        prompt = f"""
Aşağıdaki Instagram caption'ı {max_words} kelimeye kısalt.

KURALLAR:
- Ana mesajı koru
- Hook'u (ilk cümleyi) koru
- Hashtag'leri aynen koru
- Gereksiz açıklamaları çıkar
- Emoji'leri koru

CAPTION:
{caption}

Sadece kısaltılmış caption'ı döndür, başka bir şey ekleme.
"""

        response = await self.call_claude(prompt, timeout=30)
        shortened = response.strip()

        self.log(f"Caption kısaltıldı: {len(shortened.split())} kelime")
        return shortened

    def _detect_prompt_style(self, prompt: str) -> str:
        """
        Prompt'tan stil tespit et (basit keyword matching).

        Args:
            prompt: Görsel/video prompt metni

        Returns:
            Tespit edilen stil: 'aerial', 'pov', 'cinematic', 'documentary',
                               'timelapse', 'closeup', 'macro', 'general'
        """
        prompt_lower = prompt.lower()

        # Stil keyword'leri (öncelik sırasına göre)
        style_keywords = {
            'aerial': ['aerial', 'drone', 'bird\'s eye', 'overhead', 'from above'],
            'pov': ['pov', 'point of view', 'first person', 'subjective'],
            'cinematic': ['cinematic', 'film look', 'movie', 'widescreen', 'anamorphic'],
            'documentary': ['documentary', 'real world', 'authentic', 'behind the scenes'],
            'timelapse': ['timelapse', 'time-lapse', 'time lapse', 'hyperlapse'],
            'closeup': ['close-up', 'closeup', 'close up', 'detail shot', 'macro'],
            'macro': ['macro', 'extreme close', 'microscopic'],
            'reveal': ['reveal', 'unveil', 'emergence', 'transition'],
            'tracking': ['tracking', 'follow', 'dolly', 'steadicam'],
            'static': ['static', 'tripod', 'locked off', 'still frame']
        }

        for style, keywords in style_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                return style

        return 'general'

    async def _regenerate_with_different_style(
        self,
        topic: str,
        prompt_type: str,
        avoid_styles: list,
        original_context: dict
    ) -> Optional[str]:
        """
        Farklı bir tarzda prompt yeniden oluştur.

        Args:
            topic: Konu
            prompt_type: 'video' veya 'image'
            avoid_styles: Kaçınılması gereken stiller
            original_context: Orijinal bağlam verileri

        Returns:
            Yeni prompt veya None
        """
        avoid_hint = f"Şu stillerden KAÇIN: {', '.join(avoid_styles)}" if avoid_styles else ""

        if prompt_type == 'video':
            style_options = ['pov açısı', 'statik çekim', 'timelapse', 'drone çekimi', 'close-up detaylar']
        else:
            style_options = ['minimalist', 'documentary', 'abstract', 'studio çekimi', 'dış mekan']

        alternative_prompt = f"""
Konu: {topic}

ÖNCEKİ PROMPT'LARDAN FARKLI bir görsel yaklaşım kullan.
{avoid_hint}

Alternatif stil önerileri: {', '.join(style_options)}

Tamamen FARKLI bir görsel/sinematik yaklaşımla İngilizce prompt yaz.
Sadece prompt'u döndür, başka açıklama ekleme.
"""

        try:
            response = await self.call_claude(alternative_prompt, timeout=60)
            return response.strip() if response else None
        except Exception as e:
            self.log(f"Yeniden oluşturma hatası: {e}")
            return None

    async def process_manual_topic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kullanıcının ham input'unu profesyonel voice reels konusuna dönüştür.

        Ham input'u Olivenet marka sesine uygun, hook potansiyeli yüksek,
        profesyonel bir Instagram Reels başlığına çevirir.

        Input: "akıllı tarım solenoid vanaların uzaktan kontrolü"
        Output: {
            "processed_topic": "Akıllı Tarımda Solenoid Vana Kontrolü: Uzaktan Sulama Nasıl Çalışır?",
            "hook_suggestion": "Tarlaya gitmeden sulama yapmak mümkün mü?",
            "key_points": ["Uzaktan erişim", "Su tasarrufu", "LoRaWAN bağlantısı"]
        }
        """
        user_input = input_data.get("user_input", "")
        self.log(f"Manuel topic işleniyor: {user_input[:50]}...")

        # Load context
        company_profile = self.load_context("company-profile.md")
        brand_voice = self.load_context("social-media-expert.md")

        prompt = f"""
Kullanıcı şu konuda sesli Instagram Reels istiyor:
"{user_input}"

Bu ham input'u profesyonel bir Instagram Reels konusuna dönüştür.

OLIVENET PROFİLİ:
{company_profile[:1500]}

MARKA SESİ:
{brand_voice[:1000]}

KURALLAR:
1. Olivenet'in uzmanlık alanına uygun olmalı (IoT, sensörler, otomasyon, akıllı tarım)
2. Hook potansiyeli yüksek olmalı (soru formatı veya şaşırtıcı bilgi/istatistik)
3. 8-12 kelime arasında başlık
4. Somut değer/fayda içermeli
5. Türkçe ve profesyonel ton

ÖRNEK DÖNÜŞÜMLER:
- "sera sulama" → "Sera Sulama Otomasyonu: %40 Su Tasarrufu Nasıl Sağlanır?"
- "motor arıza" → "Motorunuz Arıza Yapmadan 2 Hafta Önce Sizi Uyarsa?"
- "sıcaklık takibi" → "Seranızda Sıcaklık 1°C Artınca Verim %15 Düşer mi?"
- "LoRaWAN sensör" → "LoRaWAN ile 10km Mesafeden Sensör Verisi Nasıl Alınır?"

JSON formatında yanıt ver:
{{
    "processed_topic": "Profesyonel başlık (8-12 kelime)",
    "hook_suggestion": "Video için önerilen hook cümlesi (dikkat çekici)",
    "key_points": ["Ana nokta 1", "Ana nokta 2", "Ana nokta 3"],
    "category": "egitici veya tanitim"
}}

Sadece JSON döndür.
"""

        try:
            response = await self.call_claude(prompt, timeout=60)
            result = json.loads(self._clean_json_response(response))

            self.log(f"Manuel topic işlendi: {result.get('processed_topic', '')[:50]}...")

            return {
                "success": True,
                "processed_topic": result.get("processed_topic", user_input),
                "hook_suggestion": result.get("hook_suggestion", ""),
                "key_points": result.get("key_points", []),
                "category": result.get("category", "egitici"),
                "original_input": user_input
            }

        except json.JSONDecodeError as e:
            self.log(f"JSON parse hatası: {e}")
            # Fallback: ham input'u kullan
            return {
                "success": True,
                "processed_topic": user_input,
                "hook_suggestion": "",
                "key_points": [],
                "category": "egitici",
                "original_input": user_input
            }
        except Exception as e:
            self.log(f"Manuel topic işleme hatası: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed_topic": user_input,
                "original_input": user_input
            }
