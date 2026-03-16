"""
페르소나 관련 API 라우트
페르소나 CRUD 및 LLM 기반 자동 생성
"""

import traceback
from flask import request, jsonify

from . import persona_bp
from ..models.persona import PersonaManager
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

# 로거 가져오기
logger = get_logger('mirofish.api.persona')


# ============== 페르소나 목록 조회 ==============

@persona_bp.route('', methods=['GET'])
def list_personas():
    """
    모든 페르소나 목록 조회

    반환:
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        personas = PersonaManager.list_personas()

        return jsonify({
            "success": True,
            "data": personas,
            "count": len(personas)
        })

    except Exception as e:
        logger.error("페르소나 목록 조회 실패: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 페르소나 생성 ==============

@persona_bp.route('', methods=['POST'])
def create_persona():
    """
    새 페르소나 생성

    요청 (JSON):
        {
            "name": "김민수",
            "age": 28,
            "gender": "남성",
            "country": "대한민국",
            "mbti": "ENFP",
            "profession": "마케팅 매니저",
            "bio": "...",
            "persona": "...",
            "interested_topics": ["기술", "마케팅"],
            "opinion_bias": "진보적",
            "influence_level": "중간",
            "reaction_speed": "빠름"
        }

    반환:
        {
            "success": true,
            "data": { ... }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "요청 본문이 비어 있습니다"
            }), 400

        if not data.get('name'):
            return jsonify({
                "success": False,
                "error": "페르소나 이름(name)은 필수 항목입니다"
            }), 400

        persona = PersonaManager.create_persona(data)

        return jsonify({
            "success": True,
            "data": persona.to_dict()
        }), 201

    except Exception as e:
        logger.error("페르소나 생성 실패: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 페르소나 단일 조회 ==============

@persona_bp.route('/<persona_id>', methods=['GET'])
def get_persona(persona_id: str):
    """
    단일 페르소나 조회

    반환:
        {
            "success": true,
            "data": { ... }
        }
    """
    try:
        persona = PersonaManager.get_persona(persona_id)

        if not persona:
            return jsonify({
                "success": False,
                "error": f"페르소나를 찾을 수 없습니다: {persona_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": persona.to_dict()
        })

    except Exception as e:
        logger.error("페르소나 조회 실패 (%s): %s", persona_id, e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 페르소나 업데이트 ==============

@persona_bp.route('/<persona_id>', methods=['PUT'])
def update_persona(persona_id: str):
    """
    페르소나 업데이트

    요청 (JSON): 업데이트할 필드만 포함

    반환:
        {
            "success": true,
            "data": { ... }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "요청 본문이 비어 있습니다"
            }), 400

        persona = PersonaManager.update_persona(persona_id, data)

        if not persona:
            return jsonify({
                "success": False,
                "error": f"페르소나를 찾을 수 없습니다: {persona_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": persona.to_dict()
        })

    except Exception as e:
        logger.error("페르소나 업데이트 실패 (%s): %s", persona_id, e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 페르소나 삭제 ==============

@persona_bp.route('/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id: str):
    """
    페르소나 삭제

    반환:
        {
            "success": true,
            "message": "페르소나 삭제됨: persona_xxxx"
        }
    """
    try:
        success = PersonaManager.delete_persona(persona_id)

        if not success:
            return jsonify({
                "success": False,
                "error": f"페르소나를 찾을 수 없거나 삭제 실패: {persona_id}"
            }), 404

        return jsonify({
            "success": True,
            "message": f"페르소나 삭제됨: {persona_id}"
        })

    except Exception as e:
        logger.error("페르소나 삭제 실패 (%s): %s", persona_id, e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== LLM 기반 페르소나 자동 생성 ==============

@persona_bp.route('/generate', methods=['POST'])
def generate_persona():
    """
    자유 텍스트 설명을 기반으로 LLM이 페르소나 필드를 자동 생성

    요청 (JSON):
        {
            "description": "30대 초반 IT 스타트업 대표, 기술 트렌드에 민감하고 진보적 성향..."
        }

    반환:
        {
            "success": true,
            "data": {
                "name": "...",
                "age": 32,
                ...
            }
        }

    참고: 생성된 페르소나는 저장되지 않으며, 프론트엔드에서 검토 후 POST /api/personas로 저장
    """
    try:
        data = request.get_json()
        if not data or not data.get('description'):
            return jsonify({
                "success": False,
                "error": "페르소나 설명(description)을 입력해 주세요"
            }), 400

        description = data['description']
        logger.info("LLM 기반 페르소나 생성 요청: %s", description[:100])

        # LLM 클라이언트 생성
        llm = LLMClient()

        system_prompt = """당신은 한국 소셜 미디어 시뮬레이션을 위한 현실적인 페르소나 생성 전문가입니다.
사용자의 자유 텍스트 설명을 기반으로 상세하고 현실적인 한국인 소셜 미디어 사용자 페르소나를 생성합니다.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{
    "name": "한국식 실명 (예: 김민수, 이지영)",
    "age": 나이(숫자),
    "gender": "남성 또는 여성",
    "country": "대한민국",
    "mbti": "MBTI 유형 (예: ENFP, ISTJ)",
    "profession": "직업",
    "bio": "소셜 미디어 프로필에 표시될 간략한 자기소개 (1-2문장)",
    "persona": "이 사람의 성격, 가치관, 소셜 미디어 활동 패턴을 상세히 설명 (3-5문장)",
    "interested_topics": ["관심 주제1", "관심 주제2", "관심 주제3"],
    "opinion_bias": "정치/사회적 성향 (예: 진보적, 보수적, 중도, 무관심)",
    "influence_level": "영향력 수준 (예: 높음, 중간, 낮음)",
    "reaction_speed": "반응 속도 (예: 매우 빠름, 빠름, 보통, 느림)"
}

주의사항:
- 모든 필드를 한국어로 작성하세요
- 현실적이고 구체적인 페르소나를 생성하세요
- interested_topics는 3-7개 항목으로 구성하세요
- persona 필드에는 소셜 미디어 활동 특성을 반드시 포함하세요
- 사용자 설명에서 언급되지 않은 부분은 설명과 일관성 있게 창의적으로 채우세요"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 설명을 기반으로 소셜 미디어 페르소나를 생성해 주세요:\n\n{description}"}
        ]

        # LLM 호출 (JSON 형식 응답)
        result = llm.chat_json(
            messages=messages,
            temperature=0.7,
            max_tokens=2048
        )

        logger.info("LLM 페르소나 생성 완료: %s", result.get('name', '이름 없음'))

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error("LLM 페르소나 생성 실패: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
