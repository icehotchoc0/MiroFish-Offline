"""
MiroFish Backend - Flask 애플리케이션 팩토리
"""

import os
import warnings

# multiprocessing resource_tracker 경고 억제 (transformers 등 서드파티 라이브러리에서 발생)
# 다른 모든 import 전에 설정 필요
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask 애플리케이션 팩토리 함수"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # JSON 인코딩 설정: 비ASCII 문자 직접 표시 보장 (\uXXXX 형식 대신)
    # Flask >= 2.3은 app.json.ensure_ascii 사용, 이전 버전은 JSON_AS_ASCII 설정 사용
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 로그 설정
    logger = setup_logger('mirofish')
    
    # reloader 하위 프로세스에서만 시작 정보 출력 (debug 모드에서 두 번 출력 방지)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish-Offline Backend 시작 중...")
        logger.info("=" * 50)
    
    # CORS 활성화
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- Neo4jStorage 싱글톤 초기화 (DI via app.extensions) ---
    from .storage import Neo4jStorage
    try:
        neo4j_storage = Neo4jStorage()
        app.extensions['neo4j_storage'] = neo4j_storage
        if should_log_startup:
            logger.info("Neo4jStorage 초기화 완료 (연결: %s)", Config.NEO4J_URI)
    except Exception as e:
        logger.error("Neo4jStorage 초기화 실패: %s", e)
        # Store None so endpoints can return 503 gracefully
        app.extensions['neo4j_storage'] = None
    
    # 시뮬레이션 프로세스 정리 함수 등록 (서버 종료 시 모든 시뮬레이션 프로세스 종료 보장)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("시뮬레이션 프로세스 정리 함수 등록됨")
    
    # 요청 로그 미들웨어
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"요청: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"요청 본문: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"응답: {response.status_code}")
        return response
    
    # 블루프린트 등록
    from .api import graph_bp, simulation_bp, report_bp, persona_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(persona_bp, url_prefix='/api/personas')
    
    # 헬스 체크
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish-Offline Backend'}
    
    if should_log_startup:
        logger.info("MiroFish-Offline Backend 시작 완료")
    
    return app

