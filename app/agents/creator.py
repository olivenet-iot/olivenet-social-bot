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
from app.video_styles import get_style_config, get_style_prefix, get_character_descriptions, get_voice_type
import random

# Comment Engagement CTA Tipleri - Psikolojik tetikleyiciler
COMMENT_CTA_TYPES = {
    "poll": {
        "templates": [
            "🅰️ {option_a} mı, 🅱️ {option_b} mi? Yorumlara yaz 👇",
            "{option_a} vs {option_b} — Sen hangisini tercih edersin? 👇",
            "A) {option_a}\nB) {option_b}\nHangisi? Tek harf yaz 👇"
        ],
        "trigger": "choice",
        "expected_boost": 2.5
    },
    "fill_blank": {
        "templates": [
            "Bizim sektörde en büyük sorun ____. Tamamla 👇",
            "IoT olmadan ____ yapamam. Sen ne yazardın? 👇",
            "Bir sensör alacak olsam ____ alırdım. Cevabın? 👇"
        ],
        "trigger": "completion",
        "expected_boost": 2.0
    },
    "number_game": {
        "templates": [
            "1-10 arası: {topic} bilgin kaç puan? Yaz bakalım 👇",
            "0-100 arası tahmin et: {question}? 👇",
            "Kaç yıldır bu sektördesin? Sayıyla yaz 👇"
        ],
        "trigger": "number",
        "expected_boost": 1.8
    },
    "tag_someone": {
        "templates": [
            "{persona} birini etiketle, teşekkür edecek 👇",
            "Bunu görmesi gereken birini etiketle 👇",
            "{persona} arkadaşını etiketle, birlikte öğrenin 👇"
        ],
        "trigger": "tag",
        "expected_boost": 3.0
    },
    "hot_take": {
        "templates": [
            "Tartışmalı fikir: {claim}. Katılıyor musun? 👇",
            "Cesur iddia: {claim}. Karşı çıkan var mı? 👇",
            "{claim} — Doğru mu yanlış mı? Fikrini yaz 👇"
        ],
        "trigger": "opinion",
        "expected_boost": 2.2
    },
    "experience": {
        "templates": [
            "Sen de yaşadın mı? Yorumlarda anlat 👇",
            "Benzer bir deneyimin var mı? Merak ediyorum 👇",
            "Sende de böyle oldu mu? Paylaş 👇"
        ],
        "trigger": "story",
        "expected_boost": 1.5
    },
    "prediction": {
        "templates": [
            "2025'te {topic} nasıl olacak? Tahminini yaz 👇",
            "Bu trend devam eder mi? Ne düşünüyorsun? 👇",
            "5 yıl sonra {topic}... Tahminin ne? 👇"
        ],
        "trigger": "future",
        "expected_boost": 1.7
    },
    "confession": {
        "templates": [
            "İtiraf: Biz de başta {mistake} yaptık. Sen? 👇",
            "Herkes yapar: {common_mistake}. Sende de oldu mu? 👇",
            "Utanılacak bir şey değil: {topic}. Paylaş 👇"
        ],
        "trigger": "vulnerability",
        "expected_boost": 2.0
    }
}

# Content type'a göre en uygun CTA tipleri
CONTENT_TYPE_CTA_MAP = {
    "reels": ["poll", "number_game", "hot_take", "experience"],
    "carousel": ["fill_blank", "tag_someone", "prediction"],
    "post": ["poll", "fill_blank", "hot_take", "confession"],
    "video": ["poll", "experience", "number_game"],
    "flux": ["poll", "fill_blank", "hot_take", "confession"],
    "infographic": ["fill_blank", "tag_someone", "prediction"]
}

# Persona mapping (tag_someone için)
PERSONA_EXAMPLES = [
    "sera sahibi",
    "fabrika müdürü",
    "enerji yöneticisi",
    "IoT meraklısı",
    "tarım teknolojisi ile ilgilenen",
    "elektrik faturasından şikayetçi",
    "teknik ekip lideri"
]

# Save Trigger Tipleri - Psikolojik kaydetme tetikleyicileri
SAVE_TRIGGER_TYPES = {
    "urgency": {
        "templates": [
            "📌 Bu bilgi 3 ay sonra lazım olacak. ŞİMDİ kaydet!",
            "🔖 Scroll'da kaybolmasın — KAYDET!",
            "💾 Kaydetmezsen 10 dakikaya unutursun. Emin misin?",
            "⏰ Şimdi okuyamıyorsan KAYDET, sonra teşekkür edersin."
        ],
        "psychology": "scarcity + future_need",
        "best_for": ["carousel", "post"],
        "expected_save_boost": 1.8
    },
    "value_proposition": {
        "templates": [
            "📌 Bu tablo başka yerde yok. Kaydet.",
            "🔖 Bunu aramakla bulamazsın — kaydet şimdi.",
            "💎 Ücretsiz danışmanlık değerinde bilgi. Kaydet!",
            "📊 Bu veriyi toplamak 2 hafta sürdü. Senin için KAYDET."
        ],
        "psychology": "perceived_value",
        "best_for": ["carousel", "post"],
        "expected_save_boost": 2.0
    },
    "social_proof": {
        "templates": [
            "📌 1000+ kişi kaydetti. Sen de kaydet!",
            "🔖 En çok kaydedilen içeriklerimizden. Kaydet!",
            "💾 Herkes soruyor, bir kere açıklıyorum. KAYDET."
        ],
        "psychology": "social_validation",
        "best_for": ["reels", "post"],
        "expected_save_boost": 1.5
    },
    "practical_use": {
        "templates": [
            "📌 Müdürüne/patronuna göstermek için kaydet.",
            "🔖 Toplantıda lazım olacak — şimdi kaydet.",
            "💼 Proje teklifine ekle. Önce KAYDET.",
            "📁 Referans olarak kaydet, karşılaştırmada kullan."
        ],
        "psychology": "practical_value",
        "best_for": ["carousel", "post", "reels"],
        "expected_save_boost": 1.7
    },
    "fomo": {
        "templates": [
            "📌 Rakiplerin bunu çoktan kaydetti. Sen?",
            "🔖 Bu bilgiyi bilen %3'e katıl. KAYDET.",
            "⚡ Kaydeden kazanır, geçen kaybeder.",
            "🎯 Pro'lar kaydeder, amatörler scroll'lar."
        ],
        "psychology": "fear_of_missing_out",
        "best_for": ["reels", "video"],
        "expected_save_boost": 1.6
    },
    "checklist": {
        "templates": [
            "✅ Checklist olarak kaydet, adım adım uygula.",
            "📋 Yapılacaklar listene ekle — KAYDET.",
            "🗂️ Koleksiyonuna ekle: {topic_short}"
        ],
        "psychology": "organization",
        "best_for": ["carousel"],
        "expected_save_boost": 2.2
    },
    "future_reference": {
        "templates": [
            "📌 6 ay sonra 'neredeydi bu?' dememek için KAYDET.",
            "🔖 İhtiyacın olduğunda bulamazsın. Şimdi kaydet.",
            "🗃️ Arşivine at, lazım olduğunda hazır olsun."
        ],
        "psychology": "future_self",
        "best_for": ["post", "carousel"],
        "expected_save_boost": 1.5
    },
    "challenge": {
        "templates": [
            "📌 Kaydetme cesareti var mı? 😏",
            "🔖 Kaydedip uygulayanı görelim!",
            "💪 Kaydet ve 1 hafta içinde uygula. Kabul mü?"
        ],
        "psychology": "challenge_response",
        "best_for": ["reels", "video"],
        "expected_save_boost": 1.4
    }
}

# Content type'a göre en uygun save trigger tipleri
CONTENT_TYPE_SAVE_MAP = {
    "reels": ["fomo", "social_proof", "challenge", "practical_use"],
    "carousel": ["checklist", "value_proposition", "urgency", "future_reference"],
    "post": ["value_proposition", "practical_use", "urgency", "future_reference"],
    "video": ["fomo", "challenge", "social_proof"],
    "flux": ["value_proposition", "practical_use", "urgency"],
    "infographic": ["checklist", "value_proposition", "future_reference"]
}

# Topic category'ye göre özelleştirilmiş save trigger'lar
CATEGORY_SAVE_TRIGGERS = {
    "tarim": {
        "practical_templates": [
            "📌 Sera sezonunda lazım olacak. Kaydet!",
            "🌱 Hasat öncesi tekrar bak — KAYDET."
        ]
    },
    "enerji": {
        "practical_templates": [
            "📌 Fatura geldiğinde hatırlayacaksın. Kaydet!",
            "⚡ Enerji tasarrufu planına ekle — KAYDET."
        ]
    },
    "fabrika": {
        "practical_templates": [
            "📌 Bakım planlamasında kullan. Kaydet!",
            "🏭 Üretim toplantısına götür — KAYDET."
        ]
    },
    "lorawan": {
        "practical_templates": [
            "📌 Deployment'ta referans olarak kaydet.",
            "📡 Kurulum sırasında lazım — KAYDET."
        ]
    },
    "edge_ai": {
        "practical_templates": [
            "📌 Proje geliştirmede referans. Kaydet!",
            "🤖 POC hazırlarken kullan — KAYDET."
        ]
    }
}


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
        elif action == "create_conversation_content":
            return await self.create_conversation_content(input_data)
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

    def generate_comment_cta(
        self,
        content_type: str,
        topic: str,
        topic_category: str,
        hook_type: str = None
    ) -> dict:
        """
        Icerik tipine ve konuya gore guclu comment CTA uret.

        Args:
            content_type: Visual/content type (reels, carousel, post, flux, etc.)
            topic: Post konusu
            topic_category: Konu kategorisi (tarim, enerji, fabrika, lorawan, edge_ai)
            hook_type: Kullanilan hook tipi (optional)

        Returns:
            {
                "cta_type": "poll",
                "cta_text": "🅰️ Sera mi, 🅱️ Fabrika mi? Yorumlara yaz 👇",
                "expected_boost": 2.5,
                "needs_ai_completion": False
            }
        """
        # Content type'a uygun CTA tiplerini al
        suitable_types = CONTENT_TYPE_CTA_MAP.get(content_type, ["poll", "fill_blank"])

        # Hook type'a gore onceliklendirme
        if hook_type == "question":
            suitable_types = ["poll", "hot_take"] + [t for t in suitable_types if t not in ["poll", "hot_take"]]
        elif hook_type == "statistic":
            suitable_types = ["number_game", "prediction"] + [t for t in suitable_types if t not in ["number_game", "prediction"]]
        elif hook_type == "problem":
            suitable_types = ["experience", "confession"] + [t for t in suitable_types if t not in ["experience", "confession"]]

        # Rastgele ama agirlikli secim (ilk tipler daha olasi)
        weights = [3, 2, 1.5, 1] + [0.5] * max(0, len(suitable_types) - 4)
        weights = weights[:len(suitable_types)]

        selected_type = random.choices(suitable_types, weights=weights, k=1)[0]
        cta_config = COMMENT_CTA_TYPES.get(selected_type, COMMENT_CTA_TYPES["poll"])

        # Template sec ve doldur
        template = random.choice(cta_config["templates"])

        # Placeholder'lari doldur
        cta_text = template

        # {topic} varsa degistir
        cta_text = cta_text.replace("{topic}", topic[:30] if len(topic) > 30 else topic)

        # {persona} varsa degistir
        if "{persona}" in cta_text:
            # Topic category'ye gore persona sec
            persona_map = {
                "tarim": "sera sahibi",
                "enerji": "enerji yöneticisi",
                "fabrika": "fabrika müdürü",
                "lorawan": "IoT meraklısı",
                "edge_ai": "teknik ekip lideri"
            }
            persona = persona_map.get(topic_category, random.choice(PERSONA_EXAMPLES))
            cta_text = cta_text.replace("{persona}", persona)

        # Poll icin option_a/option_b (AI'a birak flag)
        needs_ai = False
        if "{option_a}" in cta_text or "{option_b}" in cta_text:
            cta_text = f"[AI_GENERATE_POLL_OPTIONS: {topic}]"
            needs_ai = True

        # Diger placeholder'lar icin flag
        for placeholder in ["{claim}", "{question}", "{mistake}", "{common_mistake}"]:
            if placeholder in cta_text:
                cta_text = f"[AI_GENERATE: {selected_type} for {topic}]"
                needs_ai = True
                break

        return {
            "cta_type": selected_type,
            "cta_text": cta_text,
            "expected_boost": cta_config["expected_boost"],
            "needs_ai_completion": needs_ai
        }

    def generate_save_trigger(
        self,
        content_type: str,
        topic: str,
        topic_category: str,
        is_educational: bool = False,
        is_data_heavy: bool = False
    ) -> dict:
        """
        Icerik tipine ve konuya gore guclu save trigger uret.

        Args:
            content_type: reels, carousel, post, video, flux, infographic
            topic: Icerik konusu
            topic_category: tarim, enerji, fabrika, lorawan, edge_ai
            is_educational: Egitici icerik mi?
            is_data_heavy: Veri/istatistik agirlikli mi?

        Returns:
            {
                "trigger_type": "value_proposition",
                "trigger_text": "📌 Bu tablo baska yerde yok. Kaydet.",
                "expected_save_boost": 2.0,
                "psychology": "perceived_value"
            }
        """
        # Content type'a uygun trigger tiplerini al
        suitable_types = CONTENT_TYPE_SAVE_MAP.get(content_type, ["urgency", "practical_use"])

        # Icerik ozelliklerine gore onceliklendirme
        if is_educational:
            # Egitici icerik icin checklist ve value_proposition one cik
            suitable_types = ["checklist", "value_proposition", "future_reference"] + suitable_types

        if is_data_heavy:
            # Veri agirlikli icerik icin value_proposition ve practical_use
            suitable_types = ["value_proposition", "practical_use"] + suitable_types

        if content_type == "carousel":
            # Carousel icin checklist cok etkili
            suitable_types = ["checklist"] + suitable_types

        # Unique list (sirayi koru)
        seen = set()
        suitable_types = [x for x in suitable_types if not (x in seen or seen.add(x))]

        # Agirlikli rastgele secim (ilk tipler daha olasi)
        weights = [3, 2.5, 2, 1.5] + [1] * max(0, len(suitable_types) - 4)
        weights = weights[:len(suitable_types)]

        selected_type = random.choices(suitable_types, weights=weights, k=1)[0]
        trigger_config = SAVE_TRIGGER_TYPES.get(selected_type, SAVE_TRIGGER_TYPES["urgency"])

        # Template sec
        templates = list(trigger_config["templates"])

        # Category-specific template var mi kontrol et
        category_config = CATEGORY_SAVE_TRIGGERS.get(topic_category)
        if category_config and random.random() < 0.4:  # %40 ihtimalle category-specific
            category_templates = category_config.get("practical_templates", [])
            if category_templates:
                templates = category_templates + templates

        template = random.choice(templates)

        # Placeholder'lari doldur
        trigger_text = template
        if "{topic_short}" in trigger_text:
            topic_short = topic[:20] + "..." if len(topic) > 20 else topic
            trigger_text = trigger_text.replace("{topic_short}", topic_short)

        return {
            "trigger_type": selected_type,
            "trigger_text": trigger_text,
            "expected_save_boost": trigger_config["expected_save_boost"],
            "psychology": trigger_config["psychology"]
        }

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

        # Comment Engagement CTA olustur
        top_hook_type = top_hooks[0][0] if top_hooks else None
        comment_cta = self.generate_comment_cta(
            content_type=visual_type,
            topic=topic,
            topic_category=category,
            hook_type=top_hook_type
        )

        # CTA instruction olustur
        if comment_cta["needs_ai_completion"]:
            cta_example = f"Bu CTA tipi icin icerige uygun bir versiyon uret: {comment_cta['cta_type']}"
        else:
            cta_example = f"Ornek: {comment_cta['cta_text']}"

        # Save trigger olustur
        save_trigger = self.generate_save_trigger(
            content_type=visual_type,
            topic=topic,
            topic_category=category,
            is_educational=category in ["lorawan", "edge_ai"],
            is_data_heavy="istatistik" in topic.lower() or "veri" in topic.lower() or "%" in topic
        )

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
- 8-12 hashtag (ZORUNLU: #Olivenet #KKTC #IoT + 5-9 sektörel/genel)
- MARKDOWN KULLANMA: **bold**, *italic*, `code` YASAK (Instagram desteklemiyor)
- Vurgu için BÜYÜK HARF veya emoji kullan

### SAVE TETIKLEYICI (ZORUNLU!)
Caption'da MUTLAKA guclu bir kaydetme tetikleyicisi olmali (Comment CTA'dan ONCE).

**Onerilen Trigger Tipi:** {save_trigger['trigger_type'].upper()}
**Ornek:** {save_trigger['trigger_text']}
**Psikoloji:** {save_trigger['psychology']}

**SAVE TETIKLEYICI KURALLARI:**
1. **URGENCY (Aciliyet)** - "📌 Bu bilgi 3 ay sonra lazim olacak. SIMDI kaydet!"
2. **VALUE (Deger)** - "📌 Bu tablo baska yerde yok. Kaydet."
3. **FOMO (Kacirma Korkusu)** - "📌 Rakiplerin bunu coktan kaydetti. Sen?"
4. **PRACTICAL (Pratik Kullanim)** - "📌 Mudurune gostermek icin kaydet."
5. **CHECKLIST (Liste)** - "✅ Checklist olarak kaydet, adim adim uygula."

**YASAK SAVE IFADELERI:**
- "Kaydet 📌" (cok kisa, zayif)
- "Begen ve kaydet" (generic)
- "Isine yararsa kaydet" (pasif)

### COMMENT ENGAGEMENT CTA (ZORUNLU!)
Caption'in MUTLAKA guclu bir comment tetikleyici ile bitmeli (hashtaglardan ONCE, Save trigger'dan SONRA).

Onerilen CTA tipi: **{comment_cta['cta_type'].upper()}**
{cta_example}

**CTA TIPLERI VE KURALLARI:**
1. **POLL (A/B Secim)** - "🅰️ Manuel mi, 🅱️ Otomatik mi? Yorumlara yaz 👇"
2. **FILL_BLANK (Bosluk Doldur)** - "IoT olmadan ____ yapamam. Tamamla 👇"
3. **NUMBER_GAME (Sayi/Puan)** - "1-10 arasi IoT bilgin kac? 👇"
4. **TAG_SOMEONE (Etiketleme)** - "Sera sahibi birini etiketle 👇"
5. **HOT_TAKE (Tartismali Fikir)** - "Manuel sulama tarihe karismali. Katiliyor musun? 👇"
6. **EXPERIENCE (Deneyim)** - "Sen de yasadin mi? Anlat 👇"

**ZORUNLU:** Caption'in son satiri (hashtaglardan once) MUTLAKA yukaridaki tiplerden biri olmali.
**YASAK:** Sadece "Yorumlara yaz", "Ne dusunuyorsun?" gibi ZAYIF CTA'lar YASAK.

### ÖRNEK FORMAT
🌱 [Dikkat çekici hook]

[Ana mesaj - kısa ve öz]

- Madde 1
- Madde 2

📌 [SAVE TRIGGER - guclu kaydetme tetikleyicisi]

[COMMENT CTA - yorum tetikleyici soru/poll] 👇

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
- 8-12 hashtag (ZORUNLU: #Olivenet #KKTC #IoT + sektörel)

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
            "ig_word_count": ig_words,
            "comment_cta": {
                "type": comment_cta["cta_type"],
                "expected_boost": comment_cta["expected_boost"]
            },
            "save_trigger": {
                "type": save_trigger["trigger_type"],
                "text": save_trigger["trigger_text"],
                "expected_boost": save_trigger["expected_save_boost"]
            }
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
        visual_style = input_data.get("visual_style", "cinematic_4k")
        style_prefix = get_style_prefix(visual_style)

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

### Görsel Stil
Seçilen stil: {visual_style}
Tüm video prompt'larının BAŞINA şu stil prefix'ini ekle: "{style_prefix}"

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
    "hashtags": ["#Olivenet", "#KKTC", "#IoT", "#AkıllıTarım", "...8-12 adet toplam"],
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
8. HASHTAG: 8-12 adet (ZORUNLU: #Olivenet #KKTC #IoT + 5-9 sektörel)

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
        visual_style = input_data.get("visual_style", "cinematic_4k")

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

                # Her zaman kullanıcının seçtiği stili uygula (LLM'in hardcoded değerini override et)
                result["style_prefix"] = get_style_prefix(visual_style)

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

    def _build_segment_structure(self, segment_count: int, segment_duration: int, words_per_segment: int) -> str:
        """Segment sayısına göre dinamik yapı oluştur."""

        if segment_count == 2:
            # 2 segment: HOOK + RESOLUTION
            return f"""
[BÖLÜM 1 - HOOK (0-{segment_duration}s, ~{words_per_segment} kelime)]:
Problem/dikkat çekici açılış. İzleyiciyi durduracak soru veya iddia.

[BÖLÜM 2 - RESOLUTION ({segment_duration}-{segment_duration*2}s, ~{words_per_segment} kelime)]:
Çözüm tanıtımı ve CTA. Takip et, kaydet veya düşündürücü soru.
"""

        elif segment_count == 3:
            # 3 segment: HOOK + DEVELOPMENT + RESOLUTION
            return f"""
[BÖLÜM 1 - HOOK (0-{segment_duration}s, ~{words_per_segment} kelime)]:
Problem/dikkat çekici açılış. İzleyiciyi durduracak soru veya iddia.

[BÖLÜM 2 - DEVELOPMENT ({segment_duration}-{segment_duration*2}s, ~{words_per_segment} kelime)]:
Çözüm tanıtımı. Ürün/hizmetin faydası.

[BÖLÜM 3 - RESOLUTION ({segment_duration*2}-{segment_duration*3}s, ~{words_per_segment} kelime)]:
Sonuç ve CTA. Takip et, kaydet veya düşündürücü soru.
"""

        else:  # 4+ segment
            # HOOK + N-2 DEVELOPMENT + RESOLUTION
            lines = [f"""
[BÖLÜM 1 - HOOK (0-{segment_duration}s, ~{words_per_segment} kelime)]:
Problem/dikkat çekici açılış. İzleyiciyi durduracak soru veya iddia.
"""]

            for i in range(2, segment_count):  # DEVELOPMENT bölümleri
                start = segment_duration * (i - 1)
                end = segment_duration * i
                lines.append(f"""
[BÖLÜM {i} - DEVELOPMENT ({start}-{end}s, ~{words_per_segment} kelime)]:
Detay {i-1}: Çözümün bir yönü veya faydası.
""")

            # Son bölüm: RESOLUTION
            start = segment_duration * (segment_count - 1)
            end = segment_duration * segment_count
            lines.append(f"""
[BÖLÜM {segment_count} - RESOLUTION ({start}-{end}s, ~{words_per_segment} kelime)]:
Sonuç ve CTA. Takip et, kaydet veya düşündürücü soru.
""")

            return "".join(lines)

    async def create_speech_script(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instagram Reels için Türkçe voiceover scripti üret.

        ElevenLabs TTS ile seslendirilecek metin oluşturur.
        Süre bazlı kelime hedefi ile çalışır (~1.9 kelime/saniye - ElevenLabs ölçümü).

        Args:
            input_data: {
                "topic": str - Konu
                "target_duration": int - Hedef süre (12, 15, veya 20 saniye)
                "tone": str - Ses tonu (professional, friendly, energetic)
                "post_id": int (opsiyonel) - Güncellenecek post ID
                "segment_count": int (opsiyonel) - Video segment sayısı (long video için)
                "segment_duration": int (opsiyonel) - Her segment süresi (long video için)
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
            # Fallback: süre bazlı hesapla (~1.9 kelime/saniye - ElevenLabs gerçek ölçümü)
            target_words = int(target_duration * 1.9)

        # Long video için segment bilgisi (opsiyonel)
        segment_count = input_data.get("segment_count")
        segment_duration = input_data.get("segment_duration")

        company_profile = self.load_context("company-profile.md")

        # Ton açıklamaları
        tone_descriptions = {
            "professional": "Profesyonel, güvenilir, bilgilendirici. Kurumsal ama soğuk değil.",
            "friendly": "Samimi, sıcak, konuşma dili. Sanki bir arkadaşla sohbet.",
            "energetic": "Enerjik, heyecanlı, motive edici. Dikkat çekici ve dinamik."
        }
        tone_desc = tone_descriptions.get(tone, tone_descriptions["friendly"])

        # Segment-aware yapı (long video) veya standart yapı (short reels)
        if segment_count and segment_duration:
            words_per_segment = target_words // segment_count
            segment_structure = self._build_segment_structure(segment_count, segment_duration, words_per_segment)
            structure_section = f"""### SEGMENT YAPISI ({segment_count} bölüm, her biri {segment_duration}s):
{segment_structure}

**ÖNEMLİ**: Her bölüm TAM OLARAK belirtilen kelime sayısına yakın olmalı!
Bölümler arasında doğal geçiş olmalı ama her bölüm video segmentiyle senkronize olacak."""
        else:
            # Kısa reels için standart yapı
            structure_section = f"""### YAPI (3 BÖLÜM):
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
   - Düşündürücü soru"""

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

{structure_section}

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
- 8-12 adet (önemli!)
- ZORUNLU: #Olivenet #KKTC #IoT
- Sektörel: 5-9 adet konu bazlı (#AkıllıTarım, #SeraOtomasyonu, #EndüstriyelIoT, #Teknoloji vb.)

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

    async def create_conversation_content(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate conversational dialog content for Conversational Reels.

        Creates a dialog between two characters:
        - Male: Presents problem/asks questions (curious, concerned)
        - Female: Provides solution (confident, knowledgeable)

        Args:
            input_data: {
                "topic": str - Main topic
                "category": str - Content category (egitici, tanitim)
                "target_duration": int - Target dialog duration in seconds (6-10s)
            }

        Returns:
            {
                "success": bool,
                "dialog_lines": [{"speaker": "male"/"female", "text": "..."}],
                "video_prompt": str,      # Two-person conversation video prompt
                "broll_prompt": str,      # B-roll video prompt
                "broll_voiceover": str,   # Voiceover for B-roll segment
                "caption": str,           # Instagram caption
                "hashtags": list
            }
        """
        self.log("Conversational dialog oluşturuluyor...")

        topic = input_data.get("topic", "")
        category = input_data.get("category", "egitici")
        target_duration = input_data.get("target_duration", 8)
        visual_style = input_data.get("visual_style", "cinematic_4k")
        style_prefix = get_style_prefix(visual_style)
        style_config = get_style_config(visual_style)
        char_desc = get_character_descriptions(visual_style)
        voice_type = get_voice_type(visual_style)

        # Load context
        company_profile = self.load_context("company-profile.md")
        brand_voice = self.load_context("social-media-expert.md")

        # Calculate word targets for Sora native speech
        # Sora konuşmayı daha yavaş üretir, 4 saniye buffer bırak
        effective_dialog_duration = target_duration - 4  # 12s video için 8s dialog
        dialog_words = int(effective_dialog_duration * 1.7)  # ~1.7 kelime/saniye

        # Dynamic B-roll word limit based on expected video duration
        # Default: 8s video, 1.5s delay, 0.5s buffer = 6s available
        expected_broll_duration = input_data.get("expected_broll_duration", 8)
        broll_delay = 1.5  # Standard silence at start
        broll_buffer = 0.5  # End buffer
        available_broll_duration = expected_broll_duration - broll_delay - broll_buffer
        broll_words = int(available_broll_duration * 1.7)  # ~1.7 kelime/saniye

        prompt = f"""
## GOREV: Konusmali Instagram Reels Icerigi Uret

### KONU
{topic}

### KATEGORI
{category}

### SIRKET PROFILI
{company_profile[:1500]}

### MARKA SESI
{brand_voice[:800]}

### GÖRSEL STİL
Seçilen stil: {visual_style} ({style_config.get('description', '')})
Stil prefix: "{style_prefix}"
Ses tipi: {voice_type}

---

## FORMAT KURALLARI:

**DIALOG YAPISI (ZORUNLU):**
- ERKEK (speaker: "male"): Problem/soru sorar (merakli, endiseli)
- KADIN (speaker: "female"): Cozum sunar (guvenli, bilgili)
- 3-4 satir dialog (alternating male/female ile basla) - KISA TUT
- Toplam MAKSIMUM {dialog_words} kelime ({effective_dialog_duration} saniye içinde)
- Her satir çok kısa: 3-8 kelime (uzun cümleler YASAK)
- Dogal konusma dili, EMOJI KULLANMA

**TIMING (ÇOK ÖNEMLİ - MUTLAKA UYULMALI):**
- Video süresi: {target_duration} saniye
- Dialog MUTLAKA {effective_dialog_duration}. saniyede BİTMELİ
- Son 4 saniye: Doğal kapanış - baş sallama, gülümseme, el hareketi
- Dialog ASLA {effective_dialog_duration}. saniyeden sonra devam ETMEMELİ
- Son replik kısa ve net olmalı (örn: "Teşekkürler!", "Anladım.", "Harika!")

**KARAKTER TON:**
- ERKEK: Merakli, problem odakli, samimi, endiseli
- KADIN: Cozum odakli, guvenli, bilgili, sakin

---

## VIDEO PROMPT KURALLARI (SORA İÇİN - DİNAMİK STİL)

**ZORUNLU KURALLAR:**
1. Prompt TAMAMEN İNGİLİZCE yaz (Sora İngilizce anlıyor)
2. "TURKISH language" ve "speaking Turkish" ifadelerini MUTLAKA kullan
3. Her karakter için "speaking Turkish" tekrarla
4. "All dialogue in Turkish" cümlesini başa ekle
5. Audio bölümünde "Clear Turkish dialogue" yaz
6. "clear lip movements synchronized with Turkish speech" ekle

**STİL-BAZLI KARAKTER TANIMLARI (BUNU KULLAN!):**

SAHNE:
{char_desc['scene']}

KARAKTER 1 - ERKEK:
{char_desc['male']}
- Speaking Turkish {char_desc['tone_male']}
- Clear lip movements synchronized with Turkish speech

KARAKTER 2 - KADIN:
{char_desc['female']}
- Speaking Turkish {char_desc['tone_female']}
- Clear lip movements synchronized with Turkish speech

**VIDEO PROMPT ŞABLONU:**
---
{style_prefix}vertical video (9:16), {target_duration} seconds.

LANGUAGE: TURKISH (All dialogue MUST be in Turkish language)

SCENE: {char_desc['scene']}

CHARACTER 1 - MALE:
{char_desc['male']}
Speaking Turkish {char_desc['tone_male']} about the problem.
Clear lip movements synchronized with Turkish speech.

CHARACTER 2 - FEMALE:
{char_desc['female']}
Speaking Turkish {char_desc['tone_female']}, explaining the solution.
Clear lip movements synchronized with Turkish speech.

DIALOGUE FLOW:
- Natural Turkish conversation - male speaks first about problem
- Female responds with IoT solution, both speaking fluent Turkish
- Conversation MUST conclude naturally by second {target_duration - 2}
- Final exchange should be a clear conclusion (not mid-thought)
- Last 2 seconds: satisfied nods, smiles, or natural reaction shot
- Final 0.5 seconds: static hold on the final expressions

AUDIO: Clear Turkish dialogue, ambient sounds matching the scene, natural silence at end.

CAMERA: Medium two-shot showing both characters, professional composition.
---

**B-ROLL PROMPT:**
- Stil prefix ile başla: {style_prefix}
- Sahne ortamı referansı: {char_desc['scene']}
- IoT sensörleri, ekipmanları veya teknoloji detayları göster
- Konuşan kişi OLMAMALI (sadece objeler/ortam)
- 9:16 format, ~10 saniye için uygun
- Tamamı İngilizce yaz
- Smooth ending - abrupt kesme olmasın

**B-ROLL VOICEOVER:**
- MAKSIMUM {broll_words} kelime (~{available_broll_duration:.0f} saniye)
- B-roll video {expected_broll_duration}s, başta {broll_delay}s delay var - KISA TUT!
- CTA icermeli: "Takip et", "Kaydet" veya soru
- Tek ses (narrator)
- Turkce

**INSTAGRAM CAPTION:**
- MAX 80 KELİME
- Hook ile başla (dikkat çekici soru veya istatistik)
- 2-3 cümle ana mesaj
- Kapanışta soru veya "📌 Kaydet!"
- 8-12 hashtag (ZORUNLU: #Olivenet #KKTC #IoT + sektörel)

---

## CIKTI FORMATI (JSON):
```json
{{
    "dialog_lines": [
        {{"speaker": "male", "text": "Ilk soru/problem..."}},
        {{"speaker": "female", "text": "Ilk cozum..."}},
        {{"speaker": "male", "text": "Ikinci soru..."}},
        {{"speaker": "female", "text": "Ikinci cozum/kapanış..."}}
    ],
    "video_prompt": "BU ALANI DOLDUR: Yukarıdaki VIDEO PROMPT ŞABLONUNU kullan. Stil prefix ({style_prefix}) ile başla, karakter tanımlarını ve sahne tanımını aynen kullan. Tamamı İngilizce.",
    "broll_prompt": "BU ALANI DOLDUR: Stil prefix ({style_prefix}) ile başla, sahne ortamına uygun IoT sensör/ekipman close-up. İngilizce, 9:16, insan yok.",
    "broll_voiceover": "Turkce ~8 kelime CTA. Ornek: Olivenet IoT ile seraniz 7/24 guvende. Takip et!",
    "caption": "Instagram caption (max 80 kelime, hook ile basla)",
    "hashtags": ["#Olivenet", "#KKTC", "#IoT", "...sektorel taglar..."]
}}
```

ÖNEMLİ: video_prompt ve broll_prompt alanlarını yukarıdaki ŞABLONLARI ve KARAKTERLERİ kullanarak DOLDUR. Placeholder bırakma!

Sadece JSON döndür.
"""

        try:
            response = await self.call_claude(prompt, timeout=120)
            result = json.loads(self._clean_json_response(response))

            # Validate dialog structure
            dialog_lines = result.get("dialog_lines", [])
            if len(dialog_lines) < 3:
                self.log(f"Dialog cok kisa: {len(dialog_lines)} satir")
                return {
                    "success": False,
                    "error": f"Insufficient dialog lines: {len(dialog_lines)}, minimum 3 required"
                }

            # Style prefix validation - video_prompt için
            video_prompt = result.get("video_prompt", "")
            if video_prompt and style_prefix:
                if not video_prompt.lower().startswith(style_prefix[:20].lower()):
                    self.log(f"[CONV] video_prompt stil prefix ile başlamıyor, ekleniyor...")
                    result["video_prompt"] = style_prefix + video_prompt

            # Style prefix validation - broll_prompt için
            broll_prompt = result.get("broll_prompt", "")
            if broll_prompt and style_prefix:
                if not broll_prompt.lower().startswith(style_prefix[:20].lower()):
                    self.log(f"[CONV] broll_prompt stil prefix ile başlamıyor, ekleniyor...")
                    result["broll_prompt"] = style_prefix + broll_prompt

            # Log action
            log_agent_action(
                agent_name=self.name,
                action="create_conversation_content",
                input_data={"topic": topic, "target_duration": target_duration},
                output_data={"line_count": len(dialog_lines)},
                success=True
            )

            self.log(f"Conversation content olusturuldu: {len(dialog_lines)} dialog satiri")

            return {
                "success": True,
                "dialog_lines": dialog_lines,
                "video_prompt": result.get("video_prompt", ""),
                "broll_prompt": result.get("broll_prompt", ""),
                "broll_voiceover": result.get("broll_voiceover", ""),
                "caption": result.get("caption", ""),
                "hashtags": result.get("hashtags", ["#Olivenet", "#KKTC", "#IoT"]),
                "topic": topic
            }

        except json.JSONDecodeError as e:
            self.log(f"JSON parse hatasi: {e}")
            log_agent_action(
                agent_name=self.name,
                action="create_conversation_content",
                input_data={"topic": topic},
                success=False,
                error_message=f"JSON parse error: {e}"
            )
            return {
                "success": False,
                "error": f"JSON parse error: {e}",
                "raw_response": response[:500] if response else ""
            }

        except Exception as e:
            self.log(f"Conversation content hatasi: {e}")
            log_agent_action(
                agent_name=self.name,
                action="create_conversation_content",
                input_data={"topic": topic},
                success=False,
                error_message=str(e)
            )
            return {
                "success": False,
                "error": str(e)
            }
