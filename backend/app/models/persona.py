"""
페르소나 관리
JSON 파일 기반 페르소나 CRUD 및 라이브러리 인덱스 관리
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.persona')


@dataclass
class Persona:
    """페르소나 데이터 모델"""
    id: str
    name: str
    age: int
    gender: str
    country: str
    mbti: str
    profession: str
    bio: str
    persona: str
    interested_topics: List[str]
    opinion_bias: str
    influence_level: str
    reaction_speed: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "country": self.country,
            "mbti": self.mbti,
            "profession": self.profession,
            "bio": self.bio,
            "persona": self.persona,
            "interested_topics": self.interested_topics,
            "opinion_bias": self.opinion_bias,
            "influence_level": self.influence_level,
            "reaction_speed": self.reaction_speed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Persona':
        """딕셔너리에서 생성"""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            age=data.get('age', 0),
            gender=data.get('gender', ''),
            country=data.get('country', ''),
            mbti=data.get('mbti', ''),
            profession=data.get('profession', ''),
            bio=data.get('bio', ''),
            persona=data.get('persona', ''),
            interested_topics=data.get('interested_topics', []),
            opinion_bias=data.get('opinion_bias', ''),
            influence_level=data.get('influence_level', ''),
            reaction_speed=data.get('reaction_speed', ''),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


class PersonaManager:
    """페르소나 관리자 — 페르소나의 영속 저장 및 검색 담당"""

    # 페르소나 저장 디렉토리
    PERSONAS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'personas')
    # 라이브러리 인덱스 파일 경로
    LIBRARY_PATH = os.path.join(Config.UPLOAD_FOLDER, 'personas', 'library.json')

    @classmethod
    def _ensure_personas_dir(cls):
        """페르소나 디렉토리 존재 확인 및 생성"""
        os.makedirs(cls.PERSONAS_DIR, exist_ok=True)

    @classmethod
    def _load_library(cls) -> List[Dict[str, Any]]:
        """라이브러리 인덱스 로드"""
        cls._ensure_personas_dir()

        if not os.path.exists(cls.LIBRARY_PATH):
            return []

        try:
            with open(cls.LIBRARY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            logger.error("라이브러리 인덱스 로드 실패: %s", e)
            return []

    @classmethod
    def _save_library(cls, library: List[Dict[str, Any]]) -> None:
        """라이브러리 인덱스 저장"""
        cls._ensure_personas_dir()

        with open(cls.LIBRARY_PATH, 'w', encoding='utf-8') as f:
            json.dump(library, f, ensure_ascii=False, indent=2)

    @classmethod
    def _get_persona_path(cls, persona_id: str) -> str:
        """개별 페르소나 JSON 파일 경로"""
        return os.path.join(cls.PERSONAS_DIR, f"{persona_id}.json")

    @classmethod
    def _generate_id(cls) -> str:
        """페르소나 ID 생성 (persona_ + hex)"""
        return f"persona_{uuid.uuid4().hex[:12]}"

    @classmethod
    def list_personas(cls) -> List[Dict[str, Any]]:
        """
        모든 페르소나 목록 조회

        Returns:
            페르소나 딕셔너리 목록
        """
        library = cls._load_library()
        logger.debug("페르소나 목록 조회: %d건", len(library))
        return library

    @classmethod
    def get_persona(cls, persona_id: str) -> Optional[Persona]:
        """
        단일 페르소나 조회

        Args:
            persona_id: 페르소나 ID

        Returns:
            Persona 객체, 존재하지 않으면 None
        """
        persona_path = cls._get_persona_path(persona_id)

        if not os.path.exists(persona_path):
            logger.warning("페르소나를 찾을 수 없음: %s", persona_id)
            return None

        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Persona.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("페르소나 파일 읽기 실패 (%s): %s", persona_id, e)
            return None

    @classmethod
    def create_persona(cls, data: Dict[str, Any]) -> Persona:
        """
        새 페르소나 생성

        Args:
            data: 페르소나 필드 데이터

        Returns:
            생성된 Persona 객체
        """
        cls._ensure_personas_dir()

        now = datetime.now().isoformat()
        persona_id = cls._generate_id()

        persona = Persona(
            id=persona_id,
            name=data.get('name', ''),
            age=data.get('age', 0),
            gender=data.get('gender', ''),
            country=data.get('country', '대한민국'),
            mbti=data.get('mbti', ''),
            profession=data.get('profession', ''),
            bio=data.get('bio', ''),
            persona=data.get('persona', ''),
            interested_topics=data.get('interested_topics', []),
            opinion_bias=data.get('opinion_bias', ''),
            influence_level=data.get('influence_level', ''),
            reaction_speed=data.get('reaction_speed', ''),
            created_at=now,
            updated_at=now,
        )

        # 개별 페르소나 JSON 파일 저장
        persona_path = cls._get_persona_path(persona_id)
        with open(persona_path, 'w', encoding='utf-8') as f:
            json.dump(persona.to_dict(), f, ensure_ascii=False, indent=2)

        # 라이브러리 인덱스 업데이트
        library = cls._load_library()
        library.append(persona.to_dict())
        cls._save_library(library)

        logger.info("페르소나 생성 완료: %s (%s)", persona.name, persona_id)
        return persona

    @classmethod
    def update_persona(cls, persona_id: str, data: Dict[str, Any]) -> Optional[Persona]:
        """
        페르소나 업데이트

        Args:
            persona_id: 페르소나 ID
            data: 업데이트할 필드 데이터

        Returns:
            업데이트된 Persona 객체, 존재하지 않으면 None
        """
        existing = cls.get_persona(persona_id)
        if not existing:
            return None

        now = datetime.now().isoformat()

        # 기존 데이터에 새 데이터 병합
        updated_data = existing.to_dict()
        for key in [
            'name', 'age', 'gender', 'country', 'mbti', 'profession',
            'bio', 'persona', 'interested_topics', 'opinion_bias',
            'influence_level', 'reaction_speed'
        ]:
            if key in data:
                updated_data[key] = data[key]
        updated_data['updated_at'] = now

        persona = Persona.from_dict(updated_data)

        # 개별 파일 저장
        persona_path = cls._get_persona_path(persona_id)
        with open(persona_path, 'w', encoding='utf-8') as f:
            json.dump(persona.to_dict(), f, ensure_ascii=False, indent=2)

        # 라이브러리 인덱스 업데이트
        library = cls._load_library()
        library = [p for p in library if p.get('id') != persona_id]
        library.append(persona.to_dict())
        cls._save_library(library)

        logger.info("페르소나 업데이트 완료: %s (%s)", persona.name, persona_id)
        return persona

    @classmethod
    def delete_persona(cls, persona_id: str) -> bool:
        """
        페르소나 삭제

        Args:
            persona_id: 페르소나 ID

        Returns:
            삭제 성공 여부
        """
        persona_path = cls._get_persona_path(persona_id)

        if not os.path.exists(persona_path):
            logger.warning("삭제 대상 페르소나를 찾을 수 없음: %s", persona_id)
            return False

        # 개별 파일 삭제
        os.remove(persona_path)

        # 라이브러리 인덱스에서 제거
        library = cls._load_library()
        library = [p for p in library if p.get('id') != persona_id]
        cls._save_library(library)

        logger.info("페르소나 삭제 완료: %s", persona_id)
        return True
