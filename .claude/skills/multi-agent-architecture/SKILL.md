---
name: multi-agent-architecture
description: Multi-agent sistem mimarisi referansi. Use when working with agents, pipelines, or understanding the content generation workflow.
---

# Multi-Agent Architecture

## System Overview

The Olivenet Social Bot uses a multi-agent architecture for content generation:

```
┌─────────────┐
│ Orchestrator│  ← Koordinasyon
└──────┬──────┘
       │
┌──────┴──────┐
│   Planner   │  ← Konu seçimi
└──────┬──────┘
       │
┌──────┴──────┐
│   Creator   │  ← İçerik üretimi
└──────┬──────┘
       │
┌──────┴──────┐
│  Reviewer   │  ← Kalite kontrol
└──────┬──────┘
       │
┌──────┴──────┐
│  Publisher  │  ← Instagram yayın
└──────┬──────┘
       │
┌──────┴──────┐
│  Analytics  │  ← Performans takip
└─────────────┘
```

## Agent Overview

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| Orchestrator | Pipeline koordinasyonu | Pipeline type | Agent calls |
| Planner | Konu ve strateji | Action request | Topic suggestion |
| Creator | İçerik üretimi | Topic + context | Post text + prompts |
| Reviewer | Kalite kontrol | Post text | Scores + decision |
| Publisher | Platform yayın | Content + media | Post IDs |
| Analytics | Performans takip | Post ID | Metrics |

## BaseAgent Pattern

All agents inherit from `BaseAgent`:

```python
from app.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("myagent")  # Loads persona from context/personas/myagent.md

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Load persona and context
        persona = self.load_persona()
        context = self.load_context("company-profile.md")

        # Call Claude via CLI
        response = await self.call_claude_with_retry(
            prompt=f"Your prompt with {context}",
            timeout=120,
            max_retries=3
        )

        return json.loads(response)
```

## Pipeline States

```python
class PipelineState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_TOPIC_APPROVAL = "awaiting_topic_approval"
    CREATING_CONTENT = "creating_content"
    AWAITING_CONTENT_APPROVAL = "awaiting_content_approval"
    CREATING_VISUAL = "creating_visual"
    AWAITING_VISUAL_APPROVAL = "awaiting_visual_approval"
    REVIEWING = "reviewing"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    ERROR = "error"
```

## Pipeline Types

| Type | Description | Telegram Approval |
|------|-------------|-------------------|
| daily | Günlük içerik | Yes (each stage) |
| autonomous | Tam otomatik | No (just notifications) |
| reels | Video Reels | Yes |
| carousel | Çoklu görsel | Yes |
| ab_test | A/B test | Yes |
| planned | Takvimden | Configurable |

## Daily Pipeline Flow

```
1. Planner → suggest_topic
2. Telegram → await topic approval
3. Creator → create_post
4. Telegram → await content approval
5. Creator → create_visual_prompt
6. Flux/Veo → generate visual
7. Telegram → await visual approval
8. Reviewer → review_post
9. Telegram → await final approval
10. Publisher → publish to Instagram
```

## Autonomous Pipeline Flow

```
1. Planner → suggest_topic
2. Creator → create_post (no approval)
3. Creator → create_visual_prompt
4. Flux/Veo → generate visual
5. Reviewer → review_post
6. IF score >= min_score:
   Publisher → publish
   ELSE:
   Skip publish
```

## Retry Logic

All agents support exponential backoff:

```python
@retry_with_backoff(
    max_retries=3,
    base_delay=2.0,      # 2s, 4s, 8s
    max_delay=30.0,
    exponential=True
)
async def my_function():
    pass
```

## Error Handling

Agents return errors in consistent format:

```python
# Success
{"success": True, "data": {...}}

# Error
{"error": "Error message", "details": {...}}
```

For more details, see [agent-template.py](agent-template.py) and [pipeline-flow.md](pipeline-flow.md).
