---
name: recent-changes
description: Son degisiklikler logu. Check when debugging or understanding recent fixes.
---

# Recent Changes

Son commit'ler ve onemli degisiklikler. Debugging ve context icin referans.

## 2024-12 Son Commit'ler

### Kapsamli Dokumantasyon Refaktoru (TBD)
**Degisiklikler:**
- 7 yeni dokumantasyon dosyasi eklendi
- Renk paleti tutarsizligi duzeltildi
- Facebook referanslari tamamen temizlendi
- Duplicate topic listeleri birlestirildi
- README.md tamamen yeniden yazildi
- .env.example kapsamli sekilde guncellendi

**Yeni Dosyalar:**
- `ARCHITECTURE.md` - Sistem mimarisi, agent workflow
- `DATABASE.md` - 11 tablo semasi ve ER diagram
- `API_INTEGRATIONS.md` - 10+ API entegrasyonu detaylari
- `CONFIGURATION.md` - Tum environment variables
- `QUICKSTART.md` - Kurulum ve ilk calistirma
- `USAGE_EXAMPLES.md` - Python API ornekleri
- `TROUBLESHOOTING.md` - Sik hatalar ve cozumler

**Guncellenen Dosyalar:**
- `.claude/skills/template-system/SKILL.md` - renk paleti fix
- `.claude/skills/database-patterns/schema.sql` - Facebook sutunlari kaldirildi
- `.claude/skills/olivenet-brand/topics.md` - context/topics.md'ye referans
- `context/schedule-strategy.md` - Facebook referanslari temizlendi
- `context/social-media-expert.md` - rakam catismasi duzeltildi

---

### KAYDET Sorunu Fix (f0d7d2f)
**Problem:** Carousel cover slide'da "KAYDET" button metni gorunuyordu.
**Cozum:** 4 katmanli savunma eklendi:
1. Claude prompt'a KAYDET yasagi
2. Creator'da regex temizleme
3. Reviewer'da validation
4. Telegram'da son kontrol

**Dosyalar:**
- `app/agents/creator.py` - regex cleanup
- `app/telegram_pipeline.py` - final validation

---

### Carousel Iyilestirmeleri (4c0894f)
**Eklenenler:**
- 5 yeni infographic template
- Slide validation + auto-fix
- Text length kontrol (her slide max 100 karakter)
- Cover slide ozel tasarim

**Dosyalar:**
- `templates/*.html` - yeni template'ler
- `app/agents/creator.py` - validation logic

---

### Revision Button Fix (3ece58a)
**Problem:** Telegram'da revizyon butonu calismiyor.
**Cozum:** Callback handler duzeltildi, feedback akisi iyilestirildi.

**Dosya:** `app/telegram_pipeline.py`

---

### Icerik Stratejisi Guncellemesi (ea63918)
**Degisiklikler:**
- Kalite kontrol kriterleri guncellendi
- Tasarim standartlari belirlendi
- Hook performance takibi iyilestirildi

**Dosyalar:**
- `context/content-strategy.md`
- `app/agents/reviewer.py`

---

### Prompt Tracking Sistemi (3ad6580)
**Yeni Ozellik:** Video/image prompt performans takibi.

**Yeni Tablo:** `prompt_history`
- prompt_type: video | image
- prompt_style: cinematic, documentary, pov, etc.
- prompt_hash: duplicate detection
- Performance metrics: reach, engagement, saves

**Dosyalar:**
- `app/database/models.py` - tablo ekleme
- `app/database/crud.py` - CRUD fonksiyonlari

---

### Facebook Temizlik (503642e)
**Degisiklik:** Tum Facebook referanslari kaldirildi.
- `facebook_helper.py` -> `facebook_helper.py.disabled`
- Platform secenekleri sadece Instagram

---

### None Hatalari Fix (bf522e2)
**Problem:** `.upper()` ve `.lower()` None degerlerinde hata.
**Cozum:** Null check eklendi.

```python
# Onceki
text.lower()

# Sonraki
(text or "").lower()
```

**Ek:** Timezone duzeltmeleri (KKTC UTC+2)

---

## Bilinen Sorunlar (Troubleshooting)

### Video Generation Timeout
**Belirti:** Sora/Veo 5 dakikadan uzun suruyor.
**Cozum:** `generate_video_smart()` kullan, otomatik fallback var.

### Carousel Upload Hatasi
**Belirti:** "All items must have same aspect ratio"
**Cozum:** Tum slide'lar 1080x1080 olmali.

### Telegram Parse Error
**Belirti:** "Can't parse entities"
**Cozum:** Markdown ozel karakterleri escape et veya parse_mode kaldir.

### Instagram Rate Limit
**Belirti:** "Application request limit reached"
**Cozum:** 0.3s delay ekle, batch islemlerde bekle.

---

## Onemli Dosyalar

| Dosya | Son Degisiklik |
|-------|----------------|
| app/agents/creator.py | KAYDET fix, carousel |
| app/telegram_pipeline.py | Revision button |
| app/database/models.py | prompt_history |
| context/content-strategy.md | Strateji |

---

## Git Komutlari

```bash
# Son 10 commit
git log --oneline -10

# Belirli dosyanin gecmisi
git log --oneline -5 -- app/agents/creator.py

# Commit detayi
git show f0d7d2f

# Degisiklikleri geri al
git checkout HEAD -- app/agents/creator.py
```
