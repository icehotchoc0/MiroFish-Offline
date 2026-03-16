"""
LLM 클라이언트 래퍼
Ollama (OpenAI 형식) 및 Claude Code SDK 지원
.env의 LLM_PROVIDER 설정으로 전환 가능
"""

import asyncio
import json
import os
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


# Claude Code SDK 동시 호출 제한 세마포어
_claude_semaphore: Optional[asyncio.Semaphore] = None


def _get_claude_semaphore() -> asyncio.Semaphore:
    global _claude_semaphore
    if _claude_semaphore is None:
        _claude_semaphore = asyncio.Semaphore(Config.CLAUDE_MAX_CONCURRENT)
    return _claude_semaphore


class LLMClient:
    """LLM 클라이언트 — Ollama 또는 Claude Code SDK"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.provider = Config.LLM_PROVIDER.lower()
        self.model = model or Config.LLM_MODEL_NAME

        if self.provider == 'claude':
            # Claude Code SDK — API 키 불필요 (Max 구독 사용)
            pass
        else:
            # Ollama / OpenAI 호환
            self.api_key = api_key or Config.LLM_API_KEY
            self.base_url = base_url or Config.LLM_BASE_URL

            if not self.api_key:
                raise ValueError("LLM_API_KEY 미설정")

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
            )

            # Ollama context window size — prevents prompt truncation.
            self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return self.provider != 'claude' and '11434' in (self.base_url or '')

    def _claude_query_sync(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Claude Code SDK를 동기적으로 호출"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 이미 이벤트 루프가 실행 중이면 새 스레드에서 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._claude_query_async(messages, system_prompt)
                )
                return future.result()
        else:
            return asyncio.run(
                self._claude_query_async(messages, system_prompt)
            )

    async def _claude_query_async(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Claude Code SDK 비동기 호출"""
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        # messages를 하나의 프롬프트로 변환
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            else:
                prompt_parts.append(f"[{role}]: {content}")

        prompt = "\n\n".join(prompt_parts)

        options = ClaudeAgentOptions(
            max_turns=1,
            model=self.model if self.model else None,
        )

        if system_prompt:
            options.system_prompt = system_prompt

        result_text = ""
        sem = _get_claude_semaphore()

        async with sem:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_text += block.text

        if not result_text:
            raise ValueError("Claude Code SDK가 빈 응답을 반환했습니다")

        return result_text

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 요청 전송

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            response_format: 응답 형식 (예: JSON 모드)

        Returns:
            모델 응답 텍스트
        """
        if self.provider == 'claude':
            # system 메시지 추출
            system_prompt = None
            chat_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt = msg.get("content", "")
                else:
                    chat_messages.append(msg)

            # JSON 모드 요청 시 시스템 프롬프트에 JSON 지시 추가
            if response_format and response_format.get("type") == "json_object":
                json_instruction = "\n\n중요: 반드시 유효한 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요."
                if system_prompt:
                    system_prompt += json_instruction
                else:
                    system_prompt = json_instruction

            return self._claude_query_sync(chat_messages, system_prompt)

        # Ollama / OpenAI 호환 경로
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # For Ollama: pass num_ctx via extra_body to prevent prompt truncation
        if self._is_ollama() and self._num_ctx:
            kwargs["extra_body"] = {
                "options": {"num_ctx": self._num_ctx}
            }

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        # 일부 모델(예: MiniMax M2.5)이 content에 <think> 사고 내용을 포함하므로 제거 필요
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def _clean_json_response(self, response: str) -> str:
        """LLM 응답에서 JSON 부분만 추출"""
        cleaned = response.strip()
        # markdown 코드 블록 마커 제거
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        cleaned = cleaned.strip()
        # 응답에서 첫 번째 { ... } 또는 [ ... ] 블록 추출 시도
        if not cleaned.startswith(('{', '[')):
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
            if match:
                cleaned = match.group(1)
        return cleaned

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        채팅 요청을 전송하고 JSON 반환 (실패 시 재시도)

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            max_retries: 최대 재시도 횟수

        Returns:
            파싱된 JSON 객체
        """
        last_error = None

        for attempt in range(max_retries):
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )

            cleaned_response = self._clean_json_response(response)

            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                last_error = cleaned_response
                if attempt < max_retries - 1:
                    # 재시도 시 온도를 낮추고, JSON 형식을 다시 강조하는 메시지 추가
                    temperature = max(0.1, temperature - 0.1)
                    messages = messages + [
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": "위 응답이 유효한 JSON이 아닙니다. 반드시 유효한 JSON 형식으로만 응답해 주세요. 다른 텍스트 없이 JSON만 출력하세요."}
                    ]

        raise ValueError(f"LLM이 {max_retries}회 시도 후에도 유효한 JSON을 반환하지 못했습니다: {last_error}")
