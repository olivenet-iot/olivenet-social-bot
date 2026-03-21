---
name: recent-changes
description: v2 migrasyonu degisiklik logu. Check when debugging or understanding v2 architecture changes.
---

# Recent Changes — v2 Architecture Migration

## v2 Mimari Degisiklikler

### Brain Agent (Otonom Karar Motoru)
- `app/agents/brain.py` — Her 2 saatte Claude API ile karar verir
- content_opportunities havuzundan en uygun firsati secer
- Creative parametreler: model_id, visual_style, hook_type, carousel_style
- Dry-run mode: `BRAIN_DRY_RUN=true` (uretim yapilmaz, loglanir)
- `main.py`'de dogrudan import edilir (`agents/__init__.py`'den degil)

### Feed System (10 RSS Feed)
- `app/sources/feed_aggregator.py` — RSS → enrich → score → pool
- `app/sources/feed_config.py` — 10 feed (IoT Now, RAKwireless, Hackaday, LoRa Alliance, Embedded Computing, TechCrunch AI, MIT Tech Review, CleanTechnica, Renewable Energy World, AgFunder)
- Opportunity lifecycle: discovered → enriched → scored → ready → producing → used/expired

### v2 Engine Layer
- `app/engine/scheduler.py` — V2Scheduler (feed 30m, brain 120m, expiry 6h)
- `app/engine/state.py` — SystemState (production tracking, pause state)
- `app/engine/event_bus.py` — EventBus (async pub/sub)

### 7 Production Pipelines
- `app/production/` — post, reels, carousel, voice_reels, long_video, news_reels, conversational
- Brain Agent PIPELINE_MAP ile dinamik tetikleme
- BasePipeline temel sinif

### Kling via fal.ai
- fal.ai queue API (`fal-ai/kling-video/v3/pro/text-to-video`)
- Auth: `FAL_API_KEY` (shared with nano-banana and lip-sync)
- `app/kling_helper.py` — KlingHelper sinifi (same class, fal.ai backend)
- Model: kling-v3 (Kling 3.0 Pro), 5/10/15s, native audio

### Nano Banana (HTML Template Yerine)
- ~~11 HTML template~~ → fal-ai/nano-banana-pro (via fal.ai) ile infographic uretimi
- `app/nano_banana_helper.py` — generate_infographic, generate_carousel_slides
- %94 text rendering dogrulugu
- renderer.py hala carousel slide rendering icin mevcut (template dosyalari olmadan)

### Silinen Dosyalar
- `app/fal_helper.py` — Kling fal.ai'ye geri dondu, eski fal_helper gereksiz
- `app/gemini_helper.py` — Nano banana ile degistirildi
- `templates/*.html` — 11 HTML template silindi
- 5 olü video model (minimax, wan, hailuo, kling-2, kling_2)

### Yeni Telegram Komutlari
- `/pool` — Icerik firsati havuzu durumu
- `/brain` — Brain Agent son kararlari
- `/feeds` — Feed aggregator durumu
- `/pause` — Sistemi duraklat
- `/resume` — Sistemi devam ettir
- `/force` — Belirli bir firsati hemen uret

### Yeni Veritabani Tablolari
- `content_opportunities` — v2 icerik firsatlari havuzu (11. tablo)
- `story_boosts` — Story promosyon takibi (12. tablo)

## Onemli Dosyalar

| Dosya | Aciklama |
|-------|----------|
| app/main.py | v2 entry point |
| app/agents/brain.py | Brain Agent |
| app/engine/scheduler.py | V2Scheduler |
| app/sources/feed_aggregator.py | Feed pipeline |
| app/kling_helper.py | Kling via fal.ai |
| app/nano_banana_helper.py | fal.ai nano-banana-pro infographic |
| app/video_models.py | 4 video model config |
| app/video_styles.py | 10 gorsel stil |

## Deep Links

- `ARCHITECTURE.md` — Sistem mimarisi
- `API_INTEGRATIONS.md` — API detaylari
- `TROUBLESHOOTING.md` — Sorun giderme
