"""
LLM 클라이언트 래퍼
OpenAI 형식 호출 통합 사용
Ollama num_ctx 파라미터 지원으로 프롬프트 잘림 방지
"""

import json
import os
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


class LLMClient:
    """LLM 클라이언트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 300.0
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 미설정")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

        # Ollama context window size — prevents prompt truncation.
        # Read from env OLLAMA_NUM_CTX, default 8192 (Ollama default is only 2048).
        self._num_ctx = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))

    def _is_ollama(self) -> bool:
        """Check if we're talking to an Ollama server."""
        return '11434' in (self.base_url or '')

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
