"""
엔티티 읽기 및 필터링 서비스
Neo4j 그래프에서 노드를 읽어 사전 정의된 엔티티 유형에 부합하는 노드를 필터링

Replaces zep_entity_reader.py — all Zep Cloud calls replaced by GraphStorage.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from ..storage import GraphStorage

logger = get_logger('mirofish.entity_reader')


@dataclass
class EntityNode:
    """엔티티 노드 데이터 구조"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # 관련 엣지 정보
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # 관련 기타 노드 정보
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        """엔티티 유형 조회 (기본 Entity 레이블 제외)"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """필터링된 엔티티 집합"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class EntityReader:
    """
    엔티티 읽기 및 필터링 서비스 (via GraphStorage / Neo4j)

    주요 기능:
    1. 그래프에서 모든 노드 읽기
    2. 사전 정의된 엔티티 유형에 부합하는 노드 필터링 (Labels가 Entity만이 아닌 노드)
    3. 각 엔티티의 관련 엣지 및 연관 노드 정보 조회
    """

    def __init__(self, storage: GraphStorage):
        self.storage = storage

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 모든 노드 조회

        Args:
            graph_id: 그래프 ID

        Returns:
            노드 목록
        """
        logger.info(f"그래프 {graph_id}의 모든 노드 조회 중...")
        nodes = self.storage.get_all_nodes(graph_id)
        logger.info(f"총 {len(nodes)}개 노드 조회 완료")
        return nodes

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 모든 엣지 조회

        Args:
            graph_id: 그래프 ID

        Returns:
            엣지 목록
        """
        logger.info(f"그래프 {graph_id}의 모든 엣지 조회 중...")
        edges = self.storage.get_all_edges(graph_id)
        logger.info(f"총 {len(edges)}개 엣지 조회 완료")
        return edges

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        지정된 노드의 모든 관련 엣지 조회

        Args:
            node_uuid: 노드 UUID

        Returns:
            엣지 목록
        """
        try:
            return self.storage.get_node_edges(node_uuid)
        except Exception as e:
            logger.warning(f"노드 {node_uuid}의 엣지 조회 실패: {str(e)}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        사전 정의된 엔티티 유형에 부합하는 노드 필터링

        필터링 로직:
        - 노드의 Labels가 "Entity" 하나뿐이면, 사전 정의된 유형에 부합하지 않으므로 건너뜀
        - 노드의 Labels에 "Entity"와 "Node" 이외의 레이블이 포함되어 있으면, 사전 정의된 유형에 부합하므로 유지

        Args:
            graph_id: 그래프 ID
            defined_entity_types: 사전 정의된 엔티티 유형 목록 (선택사항, 제공 시 해당 유형만 유지)
            enrich_with_edges: 각 엔티티의 관련 엣지 정보를 조회할지 여부

        Returns:
            FilteredEntities: 필터링된 엔티티 집합
        """
        logger.info(f"그래프 {graph_id}의 엔티티 필터링 시작...")

        # 모든 노드 조회
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        # 모든 엣지 조회 (이후 연관 검색용)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []

        # 노드 UUID에서 노드 데이터로의 매핑 구축
        node_map = {n["uuid"]: n for n in all_nodes}

        # 조건에 부합하는 엔티티 필터링
        filtered_entities = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])

            # 필터링 로직: Labels에 "Entity"와 "Node" 이외의 레이블이 포함되어야 함
            custom_labels = [la for la in labels if la not in ["Entity", "Node"]]

            if not custom_labels:
                # 기본 레이블만 있으므로 건너뜀
                continue

            # 사전 정의된 유형이 지정된 경우 일치 여부 확인
            if defined_entity_types:
                matching_labels = [la for la in custom_labels if la in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            # 엔티티 노드 객체 생성
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {}),
            )

            # 관련 엣지 및 노드 조회
            if enrich_with_edges:
                related_edges = []
                related_node_uuids: Set[str] = set()

                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge.get("fact", ""),
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge.get("fact", ""),
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges

                # 연관 노드의 기본 정보 조회
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node.get("labels", []),
                            "summary": related_node.get("summary", ""),
                        })

                entity.related_nodes = related_nodes

            filtered_entities.append(entity)

        logger.info(f"필터링 완료: 총 노드 {total_count}, 조건 부합 {len(filtered_entities)}, "
                     f"엔티티 유형: {entity_types_found}")

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        단일 엔티티 및 전체 컨텍스트 조회 (엣지 및 연관 노드)

        Optimized: uses get_node() + get_node_edges() instead of loading ALL nodes.
        Only fetches related nodes individually as needed.

        Args:
            graph_id: 그래프 ID
            entity_uuid: 엔티티 UUID

        Returns:
            EntityNode 또는 None
        """
        try:
            # Get the node directly by UUID (O(1) lookup)
            node = self.storage.get_node(entity_uuid)
            if not node:
                return None

            # Get edges for this node (O(degree) via Cypher)
            edges = self.storage.get_node_edges(entity_uuid)

            # Process related edges and collect related node UUIDs
            related_edges = []
            related_node_uuids: Set[str] = set()

            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge.get("fact", ""),
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge.get("fact", ""),
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])

            # Fetch related nodes individually (avoids loading ALL nodes)
            related_nodes = []
            for related_uuid in related_node_uuids:
                related_node = self.storage.get_node(related_uuid)
                if related_node:
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node.get("labels", []),
                        "summary": related_node.get("summary", ""),
                    })

            return EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {}),
                related_edges=related_edges,
                related_nodes=related_nodes,
            )

        except Exception as e:
            logger.error(f"엔티티 {entity_uuid} 조회 실패: {str(e)}")
            return None

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        지정된 유형의 모든 엔티티 조회

        Args:
            graph_id: 그래프 ID
            entity_type: 엔티티 유형 (예: "Student", "PublicFigure" 등)
            enrich_with_edges: 관련 엣지 정보 조회 여부

        Returns:
            엔티티 목록
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
