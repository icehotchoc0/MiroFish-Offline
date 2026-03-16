"""
그래프 메모리 업데이트 서비스
시뮬레이션 중 Agent 활동을 Neo4j 그래프에 동적으로 업데이트

Replaces zep_graph_memory_updater.py — Zep client replaced by GraphStorage.
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from ..config import Config
from ..utils.logger import get_logger
from ..storage import GraphStorage

logger = get_logger('mirofish.graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent 활동 기록"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """
        활동을 자연어 텍스트 설명으로 변환

        자연어 설명 형식을 채택하여 NER 추출기가 엔티티와 관계를 추출할 수 있도록 함
        """
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()

        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"게시물을 작성했습니다:「{content}」"
        return "게시물을 작성했습니다"

    def _describe_like_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"{post_author}의 게시물에 좋아요를 눌렀습니다:「{post_content}」"
        elif post_content:
            return f"게시물에 좋아요를 눌렀습니다:「{post_content}」"
        elif post_author:
            return f"{post_author}의 게시물에 좋아요를 눌렀습니다"
        return "게시물에 좋아요를 눌렀습니다"

    def _describe_dislike_post(self) -> str:
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if post_content and post_author:
            return f"{post_author}의 게시물에 싫어요를 눌렀습니다:「{post_content}」"
        elif post_content:
            return f"게시물에 싫어요를 눌렀습니다:「{post_content}」"
        elif post_author:
            return f"{post_author}의 게시물에 싫어요를 눌렀습니다"
        return "게시물에 싫어요를 눌렀습니다"

    def _describe_repost(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        if original_content and original_author:
            return f"{original_author}의 게시물을 리포스트했습니다:「{original_content}」"
        elif original_content:
            return f"게시물을 리포스트했습니다:「{original_content}」"
        elif original_author:
            return f"{original_author}의 게시물을 리포스트했습니다"
        return "게시물을 리포스트했습니다"

    def _describe_quote_post(self) -> str:
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        base = ""
        if original_content and original_author:
            base = f"{original_author}의 게시물을 인용했습니다「{original_content}」"
        elif original_content:
            base = f"게시물을 인용했습니다「{original_content}」"
        elif original_author:
            base = f"{original_author}의 게시물을 인용했습니다"
        else:
            base = "게시물을 인용했습니다"
        if quote_content:
            base += f", 그리고 댓글을 달았습니다:「{quote_content}」"
        return base

    def _describe_follow(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"사용자「{target_user_name}」를 팔로우했습니다"
        return "사용자를 팔로우했습니다"

    def _describe_create_comment(self) -> str:
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        if content:
            if post_content and post_author:
                return f"{post_author}의 게시물「{post_content}」에 댓글을 달았습니다:「{content}」"
            elif post_content:
                return f"게시물「{post_content}」에 댓글을 달았습니다:「{content}」"
            elif post_author:
                return f"{post_author}의 게시물에 댓글을 달았습니다:「{content}」"
            return f"댓글을 달았습니다:「{content}」"
        return "댓글을 작성했습니다"

    def _describe_like_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"{comment_author}의 댓글에 좋아요를 눌렀습니다:「{comment_content}」"
        elif comment_content:
            return f"댓글에 좋아요를 눌렀습니다:「{comment_content}」"
        elif comment_author:
            return f"{comment_author}의 댓글에 좋아요를 눌렀습니다"
        return "댓글에 좋아요를 눌렀습니다"

    def _describe_dislike_comment(self) -> str:
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        if comment_content and comment_author:
            return f"{comment_author}의 댓글에 싫어요를 눌렀습니다:「{comment_content}」"
        elif comment_content:
            return f"댓글에 싫어요를 눌렀습니다:「{comment_content}」"
        elif comment_author:
            return f"{comment_author}의 댓글에 싫어요를 눌렀습니다"
        return "댓글에 싫어요를 눌렀습니다"

    def _describe_search(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"「{query}」를 검색했습니다" if query else "검색을 수행했습니다"

    def _describe_search_user(self) -> str:
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"사용자「{query}」를 검색했습니다" if query else "사용자를 검색했습니다"

    def _describe_mute(self) -> str:
        target_user_name = self.action_args.get("target_user_name", "")
        if target_user_name:
            return f"사용자「{target_user_name}」를 차단했습니다"
        return "사용자를 차단했습니다"

    def _describe_generic(self) -> str:
        return f"{self.action_type} 작업을 수행했습니다"


class GraphMemoryUpdater:
    """
    그래프 메모리 업데이터 (via GraphStorage / Neo4j)

    시뮬레이션의 actions 로그 파일을 모니터링하고, 새로운 agent 활동을 그래프에 실시간 업데이트.
    플랫폼별로 그룹화하여 BATCH_SIZE개 활동이 누적될 때마다 그래프에 배치 전송.
    """

    BATCH_SIZE = 5

    PLATFORM_DISPLAY_NAMES = {
        'twitter': '월드1',
        'reddit': '월드2',
    }

    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, graph_id: str, storage: GraphStorage):
        """
        업데이터 초기화

        Args:
            graph_id: 그래프 ID
            storage: GraphStorage instance (injected)
        """
        self.graph_id = graph_id
        self.storage = storage

        self._activity_queue: Queue = Queue()

        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

        logger.info(f"GraphMemoryUpdater 초기화 완료: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _get_platform_display_name(self, platform: str) -> str:
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        """백그라운드 워커 스레드 시작"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"GraphMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"GraphMemoryUpdater 시작됨: graph_id={self.graph_id}")

    def stop(self):
        """백그라운드 워커 스레드 정지"""
        self._running = False

        self._flush_remaining()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

        logger.info(f"GraphMemoryUpdater 정지됨: graph_id={self.graph_id}, "
                     f"total_activities={self._total_activities}, "
                     f"batches_sent={self._total_sent}, "
                     f"items_sent={self._total_items_sent}, "
                     f"failed={self._failed_count}, "
                     f"skipped={self._skipped_count}")

    def add_activity(self, activity: AgentActivity):
        """agent 활동을 큐에 추가"""
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return

        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"활동을 큐에 추가: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """딕셔너리 데이터에서 활동 추가"""
        if "event_type" in data:
            return

        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )

        self.add_activity(activity)

    def _worker_loop(self):
        """백그라운드 워커 루프 - 플랫폼별로 활동을 그래프에 배치 전송"""
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)

                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)

                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            self._send_batch_activities(batch, platform)
                            time.sleep(self.SEND_INTERVAL)

                except Empty:
                    pass

            except Exception as e:
                logger.error(f"워커 루프 오류: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        활동을 그래프에 배치 전송 (하나의 텍스트로 합쳐서 add_text를 통해 NER 트리거)
        """
        if not activities:
            return

        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)

        for attempt in range(self.MAX_RETRIES):
            try:
                self.storage.add_text(self.graph_id, combined_text)

                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"{len(activities)}개 {display_name} 활동을 그래프 {self.graph_id}에 배치 전송 성공")
                logger.debug(f"배치 내용 미리보기: {combined_text[:200]}...")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"그래프 배치 전송 실패 (시도 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"그래프 배치 전송 실패, {self.MAX_RETRIES}회 재시도 완료: {e}")
                    self._failed_count += 1

    def _flush_remaining(self):
        """큐 및 버퍼에 남아 있는 활동 전송"""
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"{display_name} 플랫폼의 남은 {len(buffer)}개 활동 전송")
                    self._send_batch_activities(buffer, platform)
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 조회"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}

        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class GraphMemoryManager:
    """
    여러 시뮬레이션의 그래프 메모리 업데이터 관리

    각 시뮬레이션은 자체 업데이터 인스턴스를 가질 수 있음.
    NOTE: create_updater() requires a GraphStorage instance — must be passed in.
    """

    _updaters: Dict[str, GraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(
        cls, simulation_id: str, graph_id: str, storage: GraphStorage
    ) -> GraphMemoryUpdater:
        """
        시뮬레이션용 그래프 메모리 업데이터 생성

        Args:
            simulation_id: 시뮬레이션 ID
            graph_id: 그래프 ID
            storage: GraphStorage instance
        """
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()

            updater = GraphMemoryUpdater(graph_id, storage)
            updater.start()
            cls._updaters[simulation_id] = updater

            logger.info(f"그래프 메모리 업데이터 생성: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[GraphMemoryUpdater]:
        """시뮬레이션의 업데이터 조회"""
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        """시뮬레이션의 업데이터 정지 및 제거"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"그래프 메모리 업데이터 정지됨: simulation_id={simulation_id}")

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        """모든 업데이터 정지"""
        if cls._stop_all_done:
            return
        cls._stop_all_done = True

        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"업데이터 정지 실패: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("모든 그래프 메모리 업데이터 정지됨")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """모든 업데이터의 통계 정보 조회"""
        return {
            sim_id: updater.get_stats()
            for sim_id, updater in cls._updaters.items()
        }
