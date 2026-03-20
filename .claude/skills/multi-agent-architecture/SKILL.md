---
name: multi-agent-architecture
description: Multi-agent sistem mimarisi referansi. Use when working with agents, pipelines, engine layer, or understanding the v2 content generation workflow.
---

# Multi-Agent Architecture (v2)

## Agent Overview

| Agent | Role | Key Action | Dosya |
|-------|------|------------|-------|
| **BrainAgent** | Otonom karar motoru | `decide()`, `force_produce()` | `agents/brain.py` |
| Orchestrator | Koordinasyon | `plan_week()`, `daily_check()` | `agents/orchestrator.py` |
| Planner | Konu secimi | `suggest_topic()` | `agents/planner.py` |
| Creator | Icerik uretimi | `create_post()`, `create_reels_prompt()` | `agents/creator.py` |
| Reviewer | Kalite kontrol | `review_post()` (score 1-10) | `agents/reviewer.py` |
| Publisher | Platform yayin | `publish()` | `agents/publisher.py` |
| Analytics | Performans takip | `fetch_metrics()` | `agents/analytics.py` |
| BaseAgent | Temel sinif | `call_claude_with_retry()` | `agents/base_agent.py` |

## v2 Engine Layer

### V2Scheduler (`app/engine/scheduler.py`)
Feed aggregation + Brain karar donguleri. v1 scheduler ile paralel calisir.

```python
from app.engine.scheduler import V2Scheduler

scheduler = V2Scheduler(brain_agent=brain, feed_aggregator=aggregator, event_bus=bus)
await scheduler.start()  # Feed loop (30m) + Brain loop (120m) + Expiry loop (6h)
```

### SystemState (`app/engine/state.py`)
Aktif production tracking, pause state, pool status.

```python
from app.engine.state import SystemState

state = SystemState()
state.is_paused                    # Sistem duraklatilmis mi?
state.is_production_active()       # Aktif uretim var mi?
state.get_full_state()             # Tum durum bilgisi (Brain icin)
state.register_production(key)     # Uretim baslat
state.complete_production(key, t)  # Uretim tamamla
```

### EventBus (`app/engine/event_bus.py`)
Async pub/sub bilesenleri arasinda loose coupling.

```python
from app.engine.event_bus import EventBus

bus = EventBus()
bus.subscribe("brain_decision", callback)
await bus.publish("feed_updated", {"active_count": 42})
```

## BrainAgent (Otonom Karar Motoru)

Her 2 saatte bir calisir. Claude API ile karar verir.

```python
from app.agents.brain import BrainAgent

brain = BrainAgent()
brain.event_bus = event_bus  # main.py'de set edilir (agents/__init__.py'den degil)

# Karar dongusu
decision = await brain.decide()
# -> {"action": "produce"|"wait", "reason": "...",
#     "opportunity_id": 123, "content_type": "reels",
#     "model_id": "kling-3.0-pro", "visual_style": "cinematic_4k",
#     "hook_type": "question", "voice_mode": false}

# Telegram /force komutu
result = await brain.force_produce(opp_id=42, content_type="reels")

# Son kararlar (Telegram /brain icin)
decisions = brain.get_last_decisions(limit=5)

# Dry-run mode (env: BRAIN_DRY_RUN=true)
brain.is_dry_run  # True = kararlar loglanir, uretim yapilmaz
```

### Brain Karar Sureci
1. Sistem durumu toplanir (SystemState)
2. Quick checks (gece saati, min interval, havuz durumu)
3. Claude API ile karar (produce/wait)
4. Uygun production pipeline tetiklenir

### Brain Creative Parameters
- `model_id`: sora-2, sora-2-pro, veo-3.1, kling-3.0-pro
- `visual_style`: cinematic_4k, 3d_render, neon_cyberpunk, anime, minimalist
- `hook_type`: question, statistic, bold_claim, problem, value, fear, before_after, list, comparison, local
- `carousel_style`: tech_blue, energy_green, warm_industrial, dark_premium, clean_minimal
- `carousel_layout`: data_heavy, storytelling, comparison, step_by_step, tips_list

## Feed System

10 RSS feed'den icerik firsatlari toplanir, skorlanir, havuza eklenir.

```python
from app.sources.feed_aggregator import FeedAggregator

aggregator = FeedAggregator()
result = await aggregator.run_feed_pipeline()
```

### Feed -> Opportunity Lifecycle
```
RSS Feed → discovered → enriched → scored → ready → selected → producing → used
                                                        ↓
                                                     expired (72h)
```

### content_opportunities Tablosu
- `source_type`: rss, evergreen, calendar, manual
- `combined_score`: relevance + timeliness + virality potential
- `content_type_suggestion`: reels, carousel, post, voice_reels
- Brain Agent `ready` durumundaki en yuksek skorlu firsati secer

## v2 Production Pipelines (7 pipeline)

| Pipeline | Dosya | Default Model |
|----------|-------|---------------|
| post | `production/post_pipeline.py` | - |
| reels | `production/reels_pipeline.py` | kling-3.0-pro |
| carousel | `production/carousel_pipeline.py` | - |
| voice_reels | `production/voice_reels_pipeline.py` | sora-2-pro |
| long_video | `production/long_video_pipeline.py` | kling-3.0-pro |
| news_reels | `production/news_reels_pipeline.py` | kling-3.0-pro |
| conversational | `production/conversational_pipeline.py` | sora-2-pro |

Brain Agent dinamik olarak pipeline tetikler:
```python
# BrainAgent.PIPELINE_MAP
pipeline_info = brain.PIPELINE_MAP[content_type]
# -> ("app.production.reels_pipeline", "ReelsPipeline")
```

## v1 Pipeline (hala aktif, paralel calisir)

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline(telegram_callback=callback)
await pipeline.run_daily_content()      # Telegram onayli
await pipeline.run_autonomous_content() # Otomatik
await pipeline.run_reels_content()      # Video
```

### v1 Pipeline States
```
IDLE → PLANNING → AWAITING_TOPIC_APPROVAL →
CREATING_CONTENT → AWAITING_CONTENT_APPROVAL →
CREATING_VISUAL → AWAITING_VISUAL_APPROVAL →
REVIEWING → AWAITING_FINAL_APPROVAL →
PUBLISHING → COMPLETED | ERROR
```

## System Startup (main.py)

```
python3 app/main.py
  1. Database init
  2. EventBus olustur
  3. v2: FeedAggregator + BrainAgent + V2Scheduler
  4. v1: ContentPipeline + Scheduler (paralel)
  5. Telegram bot baslat (brain_agent + feed_aggregator global set)
```

## BaseAgent Pattern

```python
from app.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("myagent")  # Loads persona from context/agent-personas/

    async def execute(self, input_data):
        response = await self.call_claude_with_retry(prompt="...", timeout=120, max_retries=3)
        return json.loads(response)
```

## Deep Links

- `app/agents/brain.py` - Brain Agent (otonom karar)
- `app/engine/scheduler.py` - V2Scheduler (feed + brain loops)
- `app/engine/state.py` - SystemState
- `app/engine/event_bus.py` - EventBus (pub/sub)
- `app/sources/feed_aggregator.py` - Feed pipeline
- `app/sources/feed_config.py` - 10 RSS feed
- `app/production/` - 7 production pipeline
- `app/scheduler/pipeline.py` - v1 pipeline (paralel calisir)
- `app/agents/base_agent.py` - Base class
- `app/main.py` - v2 entry point
