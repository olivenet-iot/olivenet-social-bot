"""
Base Agent Class - Tüm agent'ların temel sınıfı
"""

import asyncio
import subprocess
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

class BaseAgent(ABC):
    """Tüm agent'lar için temel sınıf"""

    def __init__(self, name: str):
        self.name = name
        self.persona_path = Path(f"/opt/olivenet-social-bot/context/agent-personas/{name}.md")
        self.context_dir = Path("/opt/olivenet-social-bot/context")

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
            r'```(?:json)?\s*\n?([\s\S]*?)\n?```',  # Standard code block
            r'```json\s*([\s\S]*?)```',              # Inline json code block
            r'```\s*([\s\S]*?)```',                  # Generic code block
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                if extracted.startswith('{') and extracted.endswith('}'):
                    # Control karakterleri düzelt
                    return self._fix_json_control_chars(extracted)

        # 2. Code block yok - direkt JSON bul
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    extracted = text[start_idx:i+1]
                    return self._fix_json_control_chars(extracted)

        # 3. Basit regex fallback
        json_match = re.search(r'(\{[\s\S]*\})', text)
        if json_match:
            extracted = json_match.group(1).strip()
            return self._fix_json_control_chars(extracted)

        return text

    async def call_claude(self, prompt: str, timeout: int = 120) -> str:
        """Claude Code CLI çağır"""
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

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent'ın ana görevi - her agent implement etmeli"""
        pass

    def log(self, message: str):
        """Basit loglama"""
        print(f"[{self.name.upper()}] {message}")
