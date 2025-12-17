"""
Base Agent Class - Tüm agent'ların temel sınıfı
"""

import asyncio
import subprocess
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

            return stdout.decode('utf-8').strip()

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
