# Agent Template
# Based on app/agents/base_agent.py pattern

from abc import ABC, abstractmethod
from typing import Dict, Any
from app.agents.base_agent import BaseAgent, retry_with_backoff
import json


class ExampleAgent(BaseAgent):
    """Template for creating new agents"""

    def __init__(self):
        # Agent name - must match persona file name
        # Looks for: context/personas/example.md
        super().__init__("example")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method - called by pipeline

        Args:
            input_data: {
                "action": "action_name",
                ...other params
            }

        Returns:
            Result dictionary
        """
        action = input_data.get("action", "default")

        if action == "suggest_topic":
            return await self._suggest_topic(input_data)
        elif action == "create_content":
            return await self._create_content(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def _suggest_topic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Topic suggestion example"""

        # Load context files
        company_profile = self.load_context("company-profile.md")
        topics = self.load_context("topics.md")

        # Build prompt
        prompt = f"""
Based on the following context, suggest a topic for today's post.

## Company Profile
{company_profile}

## Available Topics
{topics}

## Requirements
- Return valid JSON only
- Include topic, category, reasoning

## Output Format
{{
    "topic": "Topic title",
    "category": "Category name",
    "reasoning": "Why this topic",
    "suggested_hooks": ["Hook 1", "Hook 2"]
}}
"""

        # Call Claude with retry
        response = await self.call_claude_with_retry(
            prompt=prompt,
            timeout=120,
            max_retries=3
        )

        try:
            result = json.loads(response)
            self.log(f"Topic suggested: {result.get('topic')}")
            return result
        except json.JSONDecodeError:
            self.log(f"JSON parse error: {response[:100]}", level="error")
            return {"error": "Invalid JSON response"}

    async def _create_content(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Content creation example"""

        topic = input_data.get("topic", "")
        category = input_data.get("category", "")

        # Load brand guidelines
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""
Create an Instagram post about: {topic}
Category: {category}

## Guidelines
{content_strategy}

## Requirements
- MAX 120 words
- Include emoji (5-7 max)
- Strong hook
- No hard selling

## Output Format
{{
    "post_text": "The complete post text",
    "hook_used": "Hook type used",
    "word_count": 85,
    "emoji_count": 6
}}
"""

        response = await self.call_claude_with_retry(prompt=prompt)

        try:
            result = json.loads(response)

            # Log the action
            self.log_action(
                action="content_created",
                message=f"Created post for {topic}",
                word_count=result.get("word_count"),
                hook=result.get("hook_used")
            )

            return result
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response"}


# ============ USAGE ============

# In pipeline:
# agent = ExampleAgent()
# result = await agent.execute({
#     "action": "suggest_topic"
# })

# With retry decorator on custom methods:
# @retry_with_backoff(max_retries=3, base_delay=2.0)
# async def my_retryable_method(self):
#     pass


# ============ LOGGING ============

# Standard log:
# self.log("Message here")
# self.log("Warning!", level="warning")
# self.log("Error!", level="error")

# Structured log:
# self.log_action("action_name", "message", key=value, ...)


# ============ CONTEXT LOADING ============

# Load persona (from context/personas/{name}.md):
# persona = self.load_persona()

# Load context file:
# content = self.load_context("filename.md")

# Context directory: settings.context_dir


# ============ CLAUDE CALL ============

# Without retry:
# response = await self.call_claude(prompt, timeout=120)

# With retry (recommended):
# response = await self.call_claude_with_retry(
#     prompt=prompt,
#     timeout=120,
#     max_retries=3
# )

# The call_claude_with_retry handles:
# - Exponential backoff (2s, 4s, 8s...)
# - Timeout errors
# - Connection errors
# - JSON cleanup (removes markdown code blocks)
