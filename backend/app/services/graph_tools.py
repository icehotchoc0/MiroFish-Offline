"""
그래프 검색 도구 서비스
그래프 검색, 노드 읽기, 엣지 쿼리 등의 도구를 캡슐화하여 Report Agent에 제공

Replaces zep_tools.py — all Zep Cloud calls replaced by GraphStorage.

핵심 검색 도구 (최적화 후):
1. InsightForge (심층 인사이트 검색) - 가장 강력한 하이브리드 검색, 자동 하위 질문 생성 및 다차원 검색
2. PanoramaSearch (광범위 검색) - 만료된 콘텐츠 포함 전체 조회
3. QuickSearch (간단 검색) - 빠른 검색
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..storage import GraphStorage

logger = get_logger('mirofish.graph_tools')


@dataclass
class SearchResult:
    """검색 결과"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }

    def to_text(self) -> str:
        """텍스트 형식으로 변환, LLM 이해용"""
        text_parts = [f"검색 쿼리: {self.query}", f"{self.total_count}건의 관련 정보 발견"]

        if self.facts:
            text_parts.append("\n### 관련 사실:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")

        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """노드 정보"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }

    def to_text(self) -> str:
        """텍스트 형식으로 변환"""
        entity_type = next((la for la in self.labels if la not in ["Entity", "Node"]), "알 수 없는 유형")
        return f"엔티티: {self.name} (유형: {entity_type})\n요약: {self.summary}"


@dataclass
class EdgeInfo:
    """엣지 정보"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # 시간 정보 (may be absent in Neo4j — kept for interface compat)
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }

    def to_text(self, include_temporal: bool = False) -> str:
        """텍스트 형식으로 변환"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"관계: {source} --[{self.name}]--> {target}\n사실: {self.fact}"

        if include_temporal:
            valid_at = self.valid_at or "알 수 없음"
            invalid_at = self.invalid_at or "현재까지"
            base_text += f"\n유효기간: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (만료됨: {self.expired_at})"

        return base_text

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        """실효 여부"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    심층 인사이트 검색 결과 (InsightForge)
    여러 하위 질문의 검색 결과 및 종합 분석 포함
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]

    # 각 차원별 검색 결과
    semantic_facts: List[str] = field(default_factory=list)
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)
    relationship_chains: List[str] = field(default_factory=list)

    # 통계 정보
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }

    def to_text(self) -> str:
        """상세 텍스트 형식으로 변환, LLM 이해용"""
        text_parts = [
            f"## 미래 예측 심층 분석",
            f"분석 질문: {self.query}",
            f"예측 시나리오: {self.simulation_requirement}",
            f"\n### 예측 데이터 통계",
            f"- 관련 예측 사실: {self.total_facts}건",
            f"- 관련 엔티티: {self.total_entities}개",
            f"- 관계 체인: {self.total_relationships}건"
        ]

        if self.sub_queries:
            text_parts.append(f"\n### 분석 하위 질문")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")

        if self.semantic_facts:
            text_parts.append(f"\n### 【핵심 사실】(보고서에서 이 원문을 인용하세요)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.entity_insights:
            text_parts.append(f"\n### 【핵심 엔티티】")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', '알 수 없음')}** ({entity.get('type', '엔티티')})")
                if entity.get('summary'):
                    text_parts.append(f"  요약: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  관련 사실: {len(entity.get('related_facts', []))}건")

        if self.relationship_chains:
            text_parts.append(f"\n### 【관계 체인】")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")

        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    광범위 검색 결과 (Panorama)
    만료된 콘텐츠를 포함한 모든 관련 정보
    """
    query: str

    all_nodes: List[NodeInfo] = field(default_factory=list)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    active_facts: List[str] = field(default_factory=list)
    historical_facts: List[str] = field(default_factory=list)

    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }

    def to_text(self) -> str:
        """텍스트 형식으로 변환 (전체 버전, 잘리지 않음)"""
        text_parts = [
            f"## 광범위 검색 결과 (미래 파노라마 뷰)",
            f"쿼리: {self.query}",
            f"\n### 통계 정보",
            f"- 총 노드 수: {self.total_nodes}",
            f"- 총 엣지 수: {self.total_edges}",
            f"- 현재 유효 사실: {self.active_count}건",
            f"- 이력/만료 사실: {self.historical_count}건"
        ]

        if self.active_facts:
            text_parts.append(f"\n### 【현재 유효 사실】(시뮬레이션 결과 원문)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.historical_facts:
            text_parts.append(f"\n### 【이력/만료 사실】(변천 과정 기록)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.all_nodes:
            text_parts.append(f"\n### 【관련 엔티티】")
            for node in self.all_nodes:
                entity_type = next((la for la in node.labels if la not in ["Entity", "Node"]), "엔티티")
                text_parts.append(f"- **{node.name}** ({entity_type})")

        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """단일 Agent 인터뷰 결과"""
    agent_name: str
    agent_role: str
    agent_bio: str
    question: str
    response: str
    key_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_소개: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**핵심 인용:**\n"
            for quote in self.key_quotes:
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    인터뷰 결과 (Interview)
    여러 시뮬레이션 Agent의 인터뷰 응답 포함
    """
    interview_topic: str
    interview_questions: List[str]

    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    interviews: List[AgentInterview] = field(default_factory=list)

    selection_reasoning: str = ""
    summary: str = ""

    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }

    def to_text(self) -> str:
        """상세 텍스트 형식으로 변환, LLM 이해 및 보고서 인용용"""
        text_parts = [
            "## 심층 인터뷰 보고서",
            f"**인터뷰 주제:** {self.interview_topic}",
            f"**인터뷰 인원:** {self.interviewed_count} / {self.total_agents}명의 시뮬레이션 Agent",
            "\n### 인터뷰 대상 선정 이유",
            self.selection_reasoning or "(자동 선정)",
            "\n---",
            "\n### 인터뷰 기록",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### 인터뷰 #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(인터뷰 기록 없음)\n\n---")

        text_parts.append("\n### 인터뷰 요약 및 핵심 관점")
        text_parts.append(self.summary or "(요약 없음)")

        return "\n".join(text_parts)


class GraphToolsService:
    """
    그래프 검색 도구 서비스 (via GraphStorage / Neo4j)

    【핵심 검색 도구 - 최적화 후】
    1. insight_forge - 심층 인사이트 검색 (가장 강력, 자동 하위 질문 생성, 다차원 검색)
    2. panorama_search - 광범위 검색 (만료된 콘텐츠 포함 전체 조회)
    3. quick_search - 간단 검색 (빠른 검색)
    4. interview_agents - 심층 인터뷰 (시뮬레이션 Agent 인터뷰, 다각도 관점 확보)

    【기본 도구】
    - search_graph - 그래프 시맨틱 검색
    - get_all_nodes - 그래프의 모든 노드 조회
    - get_all_edges - 그래프의 모든 엣지 조회 (시간 정보 포함)
    - get_node_detail - 노드 상세 정보 조회
    - get_node_edges - 노드 관련 엣지 조회
    - get_entities_by_type - 유형별 엔티티 조회
    - get_entity_summary - 엔티티의 관계 요약 조회
    """

    def __init__(self, storage: GraphStorage, llm_client: Optional[LLMClient] = None):
        self.storage = storage
        self._llm_client = llm_client
        logger.info("GraphToolsService 초기화 완료")

    @property
    def llm(self) -> LLMClient:
        """LLM 클라이언트 지연 초기화"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    # ========== 기본 도구 ==========

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        그래프 시맨틱 검색 (hybrid: vector + BM25 via Neo4j)

        Args:
            graph_id: 그래프 ID
            query: 검색 쿼리
            limit: 반환 결과 수
            scope: 검색 범위, "edges" 또는 "nodes" 또는 "both"

        Returns:
            SearchResult
        """
        logger.info(f"그래프 검색: graph_id={graph_id}, query={query[:50]}...")

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query,
                limit=limit,
                scope=scope,
            )

            facts = []
            edges = []
            nodes = []

            # Parse edge results
            if hasattr(search_results, 'edges'):
                edge_list = search_results.edges
            elif isinstance(search_results, dict) and 'edges' in search_results:
                edge_list = search_results['edges']
            else:
                edge_list = []

            for edge in edge_list:
                if isinstance(edge, dict):
                    fact = edge.get('fact', '')
                    if fact:
                        facts.append(fact)
                    edges.append({
                        "uuid": edge.get('uuid', ''),
                        "name": edge.get('name', ''),
                        "fact": fact,
                        "source_node_uuid": edge.get('source_node_uuid', ''),
                        "target_node_uuid": edge.get('target_node_uuid', ''),
                    })

            # Parse node results
            if hasattr(search_results, 'nodes'):
                node_list = search_results.nodes
            elif isinstance(search_results, dict) and 'nodes' in search_results:
                node_list = search_results['nodes']
            else:
                node_list = []

            for node in node_list:
                if isinstance(node, dict):
                    nodes.append({
                        "uuid": node.get('uuid', ''),
                        "name": node.get('name', ''),
                        "labels": node.get('labels', []),
                        "summary": node.get('summary', ''),
                    })
                    summary = node.get('summary', '')
                    if summary:
                        facts.append(f"[{node.get('name', '')}]: {summary}")

            logger.info(f"검색 완료: {len(facts)}건의 관련 사실 발견")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )

        except Exception as e:
            logger.warning(f"그래프 검색 실패, 로컬 검색으로 대체: {str(e)}")
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        로컬 키워드 매칭 검색 (대체 방안)
        """
        logger.info(f"로컬 검색 사용: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            if not text:
                return 0
            text_lower = text.lower()
            if query_lower in text_lower:
                return 100
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                all_edges = self.storage.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.get("fact", "")) + match_score(edge.get("name", ""))
                    if score > 0:
                        scored_edges.append((score, edge))

                scored_edges.sort(key=lambda x: x[0], reverse=True)

                for score, edge in scored_edges[:limit]:
                    fact = edge.get("fact", "")
                    if fact:
                        facts.append(fact)
                    edges_result.append({
                        "uuid": edge.get("uuid", ""),
                        "name": edge.get("name", ""),
                        "fact": fact,
                        "source_node_uuid": edge.get("source_node_uuid", ""),
                        "target_node_uuid": edge.get("target_node_uuid", ""),
                    })

            if scope in ["nodes", "both"]:
                all_nodes = self.storage.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.get("name", "")) + match_score(node.get("summary", ""))
                    if score > 0:
                        scored_nodes.append((score, node))

                scored_nodes.sort(key=lambda x: x[0], reverse=True)

                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.get("uuid", ""),
                        "name": node.get("name", ""),
                        "labels": node.get("labels", []),
                        "summary": node.get("summary", ""),
                    })
                    summary = node.get("summary", "")
                    if summary:
                        facts.append(f"[{node.get('name', '')}]: {summary}")

            logger.info(f"로컬 검색 완료: {len(facts)}건의 관련 사실 발견")

        except Exception as e:
            logger.error(f"로컬 검색 실패: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """그래프의 모든 노드 조회"""
        logger.info(f"그래프 {graph_id}의 모든 노드 조회 중...")

        raw_nodes = self.storage.get_all_nodes(graph_id)

        result = []
        for node in raw_nodes:
            result.append(NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            ))

        logger.info(f"{len(result)}개 노드 조회 완료")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """그래프의 모든 엣지 조회 (시간 정보 포함)"""
        logger.info(f"그래프 {graph_id}의 모든 엣지 조회 중...")

        raw_edges = self.storage.get_all_edges(graph_id)

        result = []
        for edge in raw_edges:
            edge_info = EdgeInfo(
                uuid=edge.get("uuid", ""),
                name=edge.get("name", ""),
                fact=edge.get("fact", ""),
                source_node_uuid=edge.get("source_node_uuid", ""),
                target_node_uuid=edge.get("target_node_uuid", "")
            )

            if include_temporal:
                edge_info.created_at = edge.get("created_at")
                edge_info.valid_at = edge.get("valid_at")
                edge_info.invalid_at = edge.get("invalid_at")
                edge_info.expired_at = edge.get("expired_at")

            result.append(edge_info)

        logger.info(f"{len(result)}개 엣지 조회 완료")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """단일 노드의 상세 정보 조회"""
        logger.info(f"노드 상세 조회: {node_uuid[:8]}...")

        try:
            node = self.storage.get_node(node_uuid)
            if not node:
                return None

            return NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            )
        except Exception as e:
            logger.error(f"노드 상세 조회 실패: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        노드 관련 모든 엣지 조회

        Optimized: uses storage.get_node_edges() (O(degree) Cypher)
        instead of loading ALL edges and filtering.
        """
        logger.info(f"노드 {node_uuid[:8]}...의 관련 엣지 조회")

        try:
            raw_edges = self.storage.get_node_edges(node_uuid)

            result = []
            for edge in raw_edges:
                result.append(EdgeInfo(
                    uuid=edge.get("uuid", ""),
                    name=edge.get("name", ""),
                    fact=edge.get("fact", ""),
                    source_node_uuid=edge.get("source_node_uuid", ""),
                    target_node_uuid=edge.get("target_node_uuid", ""),
                    created_at=edge.get("created_at"),
                    valid_at=edge.get("valid_at"),
                    invalid_at=edge.get("invalid_at"),
                    expired_at=edge.get("expired_at"),
                ))

            logger.info(f"노드 관련 {len(result)}개 엣지 발견")
            return result

        except Exception as e:
            logger.warning(f"노드 엣지 조회 실패: {str(e)}")
            return []

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str
    ) -> List[NodeInfo]:
        """유형별 엔티티 조회"""
        logger.info(f"{entity_type} 유형의 엔티티 조회 중...")

        # Use optimized label-based query from storage
        raw_nodes = self.storage.get_nodes_by_label(graph_id, entity_type)

        result = []
        for node in raw_nodes:
            result.append(NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            ))

        logger.info(f"{entity_type} 유형 엔티티 {len(result)}개 발견")
        return result

    def get_entity_summary(
        self,
        graph_id: str,
        entity_name: str
    ) -> Dict[str, Any]:
        """지정된 엔티티의 관계 요약 조회"""
        logger.info(f"엔티티 {entity_name}의 관계 요약 조회 중...")

        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )

        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break

        related_edges = []
        if entity_node:
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)

        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """그래프 통계 정보 조회"""
        logger.info(f"그래프 {graph_id}의 통계 정보 조회 중...")

        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)

        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1

        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }

    def get_simulation_context(
        self,
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """시뮬레이션 관련 컨텍스트 정보 조회"""
        logger.info(f"시뮬레이션 컨텍스트 조회: {simulation_requirement[:50]}...")

        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )

        stats = self.get_graph_statistics(graph_id)

        all_nodes = self.get_all_nodes(graph_id)

        entities = []
        for node in all_nodes:
            custom_labels = [la for la in node.labels if la not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })

        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],
            "total_entities": len(entities)
        }

    # ========== 핵심 검색 도구 (최적화 후) ==========

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        【InsightForge - 심층 인사이트 검색】

        가장 강력한 하이브리드 검색 함수, 자동으로 질문을 분해하여 다차원 검색:
        1. LLM을 사용하여 질문을 여러 하위 질문으로 분해
        2. 각 하위 질문에 대해 시맨틱 검색 수행
        3. 관련 엔티티 추출 및 상세 정보 조회
        4. 관계 체인 추적
        5. 모든 결과를 통합하여 심층 인사이트 생성
        """
        logger.info(f"InsightForge 심층 인사이트 검색: {query[:50]}...")

        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )

        # Step 1: LLM을 사용하여 하위 질문 생성
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"{len(sub_queries)}개 하위 질문 생성")

        # Step 2: 각 하위 질문에 대해 시맨틱 검색 수행
        all_facts = []
        all_edges = []
        seen_facts = set()

        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )

            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)

            all_edges.extend(search_result.edges)

        # 원본 질문에 대해서도 검색 수행
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # Step 3: 엣지에서 관련 엔티티 UUID 추출
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)

        # 관련 엔티티 상세 정보 조회
        entity_insights = []
        node_map = {}

        for uuid in list(entity_uuids):
            if not uuid:
                continue
            try:
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((la for la in node.labels if la not in ["Entity", "Node"]), "엔티티")

                    related_facts = [
                        f for f in all_facts
                        if node.name.lower() in f.lower()
                    ]

                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts
                    })
            except Exception as e:
                logger.debug(f"노드 {uuid} 조회 실패: {e}")
                continue

        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        # Step 4: 관계 체인 구축
        relationship_chains = []
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')

                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]

                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)

        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)

        logger.info(f"InsightForge 완료: {result.total_facts}건 사실, {result.total_entities}개 엔티티, {result.total_relationships}건 관계")
        return result

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """LLM을 사용하여 하위 질문 생성"""
        system_prompt = """당신은 전문적인 질문 분석 전문가입니다. 당신의 임무는 복잡한 질문을 시뮬레이션 세계에서 독립적으로 관찰할 수 있는 여러 하위 질문으로 분해하는 것입니다.

요구사항:
1. 각 하위 질문은 충분히 구체적이어야 하며, 시뮬레이션 세계에서 관련 Agent 행동이나 이벤트를 찾을 수 있어야 합니다
2. 하위 질문은 원래 질문의 다양한 차원을 커버해야 합니다 (예: 누가, 무엇을, 왜, 어떻게, 언제, 어디서)
3. 하위 질문은 시뮬레이션 시나리오와 관련되어야 합니다
4. JSON 형식으로 반환: {"sub_queries": ["하위 질문1", "하위 질문2", ...]}"""

        user_prompt = f"""시뮬레이션 요구사항 배경:
{simulation_requirement}

{f"보고서 컨텍스트: {report_context[:500]}" if report_context else ""}

다음 질문을 {max_queries}개의 하위 질문으로 분해해 주세요:
{query}

JSON 형식의 하위 질문 목록을 반환하세요."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            sub_queries = response.get("sub_queries", [])
            return [str(sq) for sq in sub_queries[:max_queries]]

        except Exception as e:
            logger.warning(f"하위 질문 생성 실패: {str(e)}, 기본 하위 질문 사용")
            return [
                query,
                f"{query}의 주요 참여자",
                f"{query}의 원인과 영향",
                f"{query}의 전개 과정"
            ][:max_queries]

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        【PanoramaSearch - 광범위 검색】

        만료된 콘텐츠와 이력 정보를 포함한 전체 조회.
        """
        logger.info(f"PanoramaSearch 광범위 검색: {query[:50]}...")

        result = PanoramaResult(query=query)

        # 모든 노드 조회
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        # 모든 엣지 조회 (시간 정보 포함)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        # 사실 분류
        active_facts = []
        historical_facts = []

        for edge in all_edges:
            if not edge.fact:
                continue

            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]

            is_historical = edge.is_expired or edge.is_invalid

            if is_historical:
                valid_at = edge.valid_at or "알 수 없음"
                invalid_at = edge.invalid_at or edge.expired_at or "알 수 없음"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                active_facts.append(edge.fact)

        # 쿼리 기반 관련성 정렬
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score

        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        logger.info(f"PanoramaSearch 완료: {result.active_count}건 유효, {result.historical_count}건 이력")
        return result

    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        【QuickSearch - 간단 검색】
        빠르고 경량의 검색 도구.
        """
        logger.info(f"QuickSearch 간단 검색: {query[:50]}...")

        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )

        logger.info(f"QuickSearch 완료: {result.total_count}건 결과")
        return result

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        【InterviewAgents - 심층 인터뷰】

        실제 OASIS 인터뷰 API를 호출하여 시뮬레이션에서 실행 중인 Agent를 인터뷰.
        This method does NOT use GraphStorage — it calls SimulationRunner
        and reads agent profiles from disk.
        """
        from .simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents 심층 인터뷰 (실제 API): {interview_requirement[:50]}...")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )

        # Step 1: 프로필 파일 읽기
        profiles = self._load_agent_profiles(simulation_id)

        if not profiles:
            logger.warning(f"시뮬레이션 {simulation_id}의 프로필 파일을 찾을 수 없음")
            result.summary = "인터뷰 가능한 Agent 프로필 파일을 찾을 수 없습니다"
            return result

        result.total_agents = len(profiles)
        logger.info(f"{len(profiles)}개 Agent 프로필 로드 완료")

        # Step 2: LLM을 사용하여 인터뷰할 Agent 선정
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"{len(selected_agents)}개 Agent를 인터뷰 대상으로 선정: {selected_indices}")

        # Step 3: 인터뷰 질문 생성
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"{len(result.interview_questions)}개 인터뷰 질문 생성")

        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])

        INTERVIEW_PROMPT_PREFIX = (
            "당신은 인터뷰를 받고 있습니다. 당신의 페르소나, 모든 과거 기억과 행동을 결합하여 "
            "순수 텍스트로 다음 질문에 직접 답변해 주세요.\n"
            "답변 요구사항:\n"
            "1. 자연어로 직접 답변하고, 어떤 도구도 호출하지 마세요\n"
            "2. JSON 형식이나 도구 호출 형식을 반환하지 마세요\n"
            "3. Markdown 제목 (예: #, ##, ###)을 사용하지 마세요\n"
            "4. 질문 번호순으로 하나씩 답변하고, 각 답변은 「질문X:」로 시작하세요 (X는 질문 번호)\n"
            "5. 각 질문의 답변 사이에 빈 줄을 넣으세요\n"
            "6. 답변에 실질적인 내용을 포함하고, 각 질문에 최소 2-3문장으로 답변하세요\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        # Step 4: 실제 인터뷰 API 호출
        try:
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt
                })

            logger.info(f"배치 인터뷰 API 호출 (듀얼 플랫폼): {len(interviews_request)}개 Agent")

            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,
                timeout=180.0
            )

            logger.info(f"인터뷰 API 반환: {api_result.get('interviews_count', 0)}개 결과, success={api_result.get('success')}")

            if not api_result.get("success", False):
                error_msg = api_result.get("error", "알 수 없는 오류")
                logger.warning(f"인터뷰 API 반환 실패: {error_msg}")
                result.summary = f"인터뷰 API 호출 실패: {error_msg}. OASIS 시뮬레이션 환경 상태를 확인하세요."
                return result

            # Step 5: API 반환 결과 파싱
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "알 수 없음")
                agent_bio = agent.get("bio", "")

                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                twitter_text = twitter_response if twitter_response else "(해당 플랫폼에서 응답을 받지 못함)"
                reddit_text = reddit_response if reddit_response else "(해당 플랫폼에서 응답을 받지 못함)"
                response_text = f"【Twitter 플랫폼 답변】\n{twitter_text}\n\n【Reddit 플랫폼 답변】\n{reddit_text}"

                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'질문\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', '질문'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except ValueError as e:
            logger.warning(f"인터뷰 API 호출 실패 (환경 미실행?): {e}")
            result.summary = f"인터뷰 실패: {str(e)}. 시뮬레이션 환경이 종료되었을 수 있습니다. OASIS 환경이 실행 중인지 확인하세요."
            return result
        except Exception as e:
            logger.error(f"인터뷰 API 호출 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"인터뷰 과정 중 오류 발생: {str(e)}"
            return result

        # Step 6: 인터뷰 요약 생성
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        logger.info(f"InterviewAgents 완료: {result.interviewed_count}개 Agent 인터뷰 완료 (듀얼 플랫폼)")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Agent 응답에서 JSON 도구 호출 래핑을 정리하고 실제 내용 추출"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """시뮬레이션의 Agent 프로필 파일 로드"""
        import os
        import csv

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        profiles = []

        # Reddit JSON 형식 우선 읽기 시도
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"reddit_profiles.json에서 {len(profiles)}개 프로필 로드 완료")
                return profiles
            except Exception as e:
                logger.warning(f"reddit_profiles.json 읽기 실패: {e}")

        # Twitter CSV 형식 읽기 시도
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "알 수 없음"
                        })
                logger.info(f"twitter_profiles.csv에서 {len(profiles)}개 프로필 로드 완료")
                return profiles
            except Exception as e:
                logger.warning(f"twitter_profiles.csv 읽기 실패: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """LLM을 사용하여 인터뷰할 Agent 선정"""

        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "알 수 없음"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)

        system_prompt = """당신은 전문적인 인터뷰 기획 전문가입니다. 당신의 임무는 인터뷰 요구사항에 따라 시뮬레이션 Agent 목록에서 인터뷰에 가장 적합한 대상을 선정하는 것입니다.

선정 기준:
1. Agent의 신원/직업이 인터뷰 주제와 관련됨
2. Agent가 독특하거나 가치 있는 관점을 가질 수 있음
3. 다양한 시각을 선정 (예: 지지측, 반대측, 중립측, 전문가 등)
4. 사건과 직접 관련된 역할을 우선 선정

JSON 형식으로 반환:
{
    "selected_indices": [선정된 Agent의 인덱스 목록],
    "reasoning": "선정 이유 설명"
}"""

        user_prompt = f"""인터뷰 요구사항:
{interview_requirement}

시뮬레이션 배경:
{simulation_requirement if simulation_requirement else "제공되지 않음"}

선택 가능한 Agent 목록 (총 {len(agent_summaries)}개):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

최대 {max_agents}개의 인터뷰에 가장 적합한 Agent를 선정하고, 선정 이유를 설명해 주세요."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "관련성 기반 자동 선정")

            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)

            return selected_agents, valid_indices, reasoning

        except Exception as e:
            logger.warning(f"LLM Agent 선정 실패, 기본 선정 사용: {e}")
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "기본 선정 전략 사용"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """LLM을 사용하여 인터뷰 질문 생성"""

        agent_roles = [a.get("profession", "알 수 없음") for a in selected_agents]

        system_prompt = """당신은 전문적인 기자/인터뷰어입니다. 인터뷰 요구사항에 따라 3-5개의 심층 인터뷰 질문을 생성하세요.

질문 요구사항:
1. 개방형 질문, 상세한 답변 유도
2. 다른 역할에 따라 다른 답변이 가능
3. 사실, 의견, 감정 등 여러 차원 포괄
4. 자연스러운 언어, 실제 인터뷰처럼
5. 각 질문은 50자 이내로 간결하게
6. 직접 질문, 배경 설명이나 접두어 불포함

JSON 형식으로 반환: {"questions": ["질문1", "질문2", ...]}"""

        user_prompt = f"""인터뷰 요구사항: {interview_requirement}

시뮬레이션 배경: {simulation_requirement if simulation_requirement else "제공되지 않음"}

인터뷰 대상 역할: {', '.join(agent_roles)}

3-5개의 인터뷰 질문을 생성해 주세요."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )

            return response.get("questions", [f"{interview_requirement}에 대해 어떻게 생각하시나요?"])

        except Exception as e:
            logger.warning(f"인터뷰 질문 생성 실패: {e}")
            return [
                f"{interview_requirement}에 대한 당신의 관점은 무엇인가요?",
                "이 일이 당신이나 당신이 대표하는 집단에 어떤 영향을 미치나요?",
                "이 문제를 어떻게 해결하거나 개선해야 한다고 생각하시나요?"
            ]

    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """인터뷰 요약 생성"""

        if not interviews:
            return "완료된 인터뷰가 없습니다"

        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"【{interview.agent_name} ({interview.agent_role})】\n{interview.response[:500]}")

        system_prompt = """당신은 전문적인 뉴스 편집자입니다. 여러 인터뷰 대상자의 답변을 바탕으로 인터뷰 요약을 생성해 주세요.

요약 요구사항:
1. 각 측의 주요 관점 요약
2. 관점의 합의와 차이점 지적
3. 가치 있는 인용구 부각
4. 객관적이고 중립적, 어느 쪽에도 편향되지 않음
5. 1000자 이내

형식 제약 (반드시 준수):
- 순수 텍스트 단락 사용, 빈 줄로 다른 부분 구분
- Markdown 제목 (예: #, ##, ###) 사용 금지
- 구분선 (예: ---, ***) 사용 금지
- 인터뷰 대상자 원문 인용 시 따옴표 「」 사용
- **굵게** 표시로 키워드를 강조할 수 있지만, 다른 Markdown 문법은 사용 금지"""

        user_prompt = f"""인터뷰 주제: {interview_requirement}

인터뷰 내용:
{"".join(interview_texts)}

인터뷰 요약을 생성해 주세요."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary

        except Exception as e:
            logger.warning(f"인터뷰 요약 생성 실패: {e}")
            return f"총 {len(interviews)}명의 인터뷰 대상자를 인터뷰했습니다: " + ", ".join([i.agent_name for i in interviews])
