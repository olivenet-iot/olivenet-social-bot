"""
Base Agent Class - Tüm agent'ların temel sınıfı

Retry logic ile exponential backoff destekli.
"""

import asyncio
import subprocess
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
from functools import wraps

from app.config import settings
from app.utils.logger import AgentLoggerAdapter, PerformanceTimer


# ============ RETRY DECORATOR ============

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exponential: bool = True
):
    """
    Async function için retry decorator.
    Exponential backoff ile yeniden dener.

    Args:
        max_retries: Maksimum deneme sayısı
        base_delay: İlk bekleme süresi (saniye)
        max_delay: Maksimum bekleme süresi
        exponential: True ise 2^n backoff, False ise sabit delay
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            self_arg = args[0] if args else None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except asyncio.TimeoutError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt if exponential else 1), max_delay)
                        if self_arg and hasattr(self_arg, 'log'):
                            self_arg.log(f"Timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...", level="warning")
                        await asyncio.sleep(delay)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt if exponential else 1), max_delay)
                        if self_arg and hasattr(self_arg, 'log'):
                            self_arg.log(f"Error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}, retrying in {delay}s...", level="warning")
                        await asyncio.sleep(delay)

            # Tüm denemeler başarısız
            if self_arg and hasattr(self_arg, 'log'):
                self_arg.log(f"All {max_retries} retries failed: {str(last_exception)[:200]}", level="error")
            raise last_exception

        return wrapper
    return decorator


class BaseAgent(ABC):
    """Tüm agent'lar için temel sınıf"""

    def __init__(self, name: str):
        self.name = name
        self.persona_path = settings.get_persona_file(name)
        self.context_dir = settings.context_dir
        self.logger = AgentLoggerAdapter(name)

    def load_persona(self) -> str:
        """Agent persona'sını yükle"""
        if self.persona_path.exists():
            return self.persona_path.read_text()
        return ""

    def load_context(self, filename: str) -> str:
        """Context dosyasını yükle"""
        path = self.context_dir / filename
        if path.exists():
            return path.read_text()
        return ""

    def _fix_json_control_chars(self, text: str) -> str:
        """JSON string içindeki control karakterleri düzelt"""
        result = []
        in_string = False
        escape_next = False

        for char in text:
            if escape_next:
                result.append(char)
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                result.append(char)
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                continue

            # String içindeyken control karakterleri escape et
            if in_string:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                elif ord(char) < 32:  # Diğer control karakterler
                    result.append(f'\\u{ord(char):04x}')
                else:
                    result.append(char)
            else:
                result.append(char)

        return ''.join(result)

    def _clean_json_response(self, text: str) -> str:
        """Claude yanıtından JSON'u çıkar - markdown code block'ları temizle"""
        if not text:
            return text

        text = text.strip()

        # 1. Markdown code block formatları (esnek pattern)
        patterns = [
            r'```json\s*\n?([\s\S]*?)\n?```',        # JSON code block (öncelikli)
            r'```(?:json)?\s*\n?([\s\S]*?)\n?```',   # Standard code block
            r'```\s*([\s\S]*?)```',                   # Generic code block
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                if extracted.startswith('{'):
                    # Trailing text varsa temizle
                    extracted = self._extract_complete_json(extracted)
                    if extracted:
                        return self._fix_json_control_chars(extracted)

        # 2. Code block yok - direkt JSON bul (balanced brace matching)
        extracted = self._extract_complete_json(text)
        if extracted:
            return self._fix_json_control_chars(extracted)

        # 3. Basit regex fallback
        json_match = re.search(r'(\{[\s\S]*\})', text)
        if json_match:
            extracted = json_match.group(1).strip()
            return self._fix_json_control_chars(extracted)

        return text

    def _extract_complete_json(self, text: str) -> Optional[str]:
        """Balanced braces ile tam JSON objesini çıkar"""
        brace_count = 0
        start_idx = -1
        in_string = False
        escape_next = False

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    return text[start_idx:i+1]

        return None

    async def call_claude(self, prompt: str, timeout: int = 120) -> str:
        """Claude Code CLI çağır (retry olmadan)"""
        full_prompt = f"""
{self.load_persona()}

---

{prompt}
"""

        cmd = ["claude", "-p", full_prompt, "--print"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            output = stdout.decode('utf-8').strip()

            # Markdown code block'larını temizle
            output = self._clean_json_response(output)

            return output

        except asyncio.TimeoutError:
            return '{"error": "Timeout"}'
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    async def call_claude_with_retry(
        self,
        prompt: str,
        timeout: int = 120,
        max_retries: int = 3
    ) -> str:
        """
        Claude Code CLI çağır - Retry logic ile.
        Exponential backoff: 2s, 4s, 8s...

        Args:
            prompt: Claude'a gönderilecek prompt
            timeout: Her deneme için timeout (saniye)
            max_retries: Maksimum deneme sayısı

        Returns:
            Claude yanıtı veya hata JSON'ı
        """
        full_prompt = f"""
{self.load_persona()}

---

{prompt}
"""

        cmd = ["claude", "-p", full_prompt, "--print"]
        last_error = None

        for attempt in range(max_retries):
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                output = stdout.decode('utf-8').strip()

                # Markdown code block'larını temizle
                output = self._clean_json_response(output)

                # Başarılı - hemen dön
                return output

            except asyncio.TimeoutError:
                last_error = "Timeout"
                if attempt < max_retries - 1:
                    delay = 2 ** (attempt + 1)  # 2, 4, 8 saniye
                    self.log(f"Claude timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...", level="warning")
                    await asyncio.sleep(delay)

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    delay = 2 ** (attempt + 1)
                    self.log(f"Claude error (attempt {attempt + 1}/{max_retries}): {last_error[:100]}, retrying in {delay}s...", level="warning")
                    await asyncio.sleep(delay)

        # Tüm denemeler başarısız
        self.log(f"All {max_retries} Claude retries failed: {last_error}", level="error")
        return f'{{"error": "{last_error}", "retries_exhausted": true}}'

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent'ın ana görevi - her agent implement etmeli"""
        pass

    def log(self, message: str, level: str = "info"):
        """Structured logging"""
        if level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.info(message)

    def log_action(self, action: str, message: str, **kwargs):
        """Log an agent action with structured data"""
        self.logger.log_action(action, message, **kwargs)
