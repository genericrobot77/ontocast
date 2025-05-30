from collections import defaultdict, deque
from copy import deepcopy
from typing import Set, Any, Optional

from rdflib import URIRef, RDF, RDFS, Literal

from aot_cast.onto import Chunk, RDFGraph, PROV, SCHEMA

import logging


logger = logging.getLogger(__name__)


def validate_and_connect_chunk(
    chunk: Chunk,
    current_domain,
    auto_connect: bool = True,
) -> Chunk:
    """
    Utility function to validate and optionally connect a chunk graph

    Args:
        chunk: The RDF graph to validate
        auto_connect: Whether to automatically connect disconnected graphs
        connection_strategy: Strategy to use for connecting ("chunk_hub", "minimal_bridge", "semantic_bridge")

    Returns:
        Connected graph (original if already connected, or modified if auto_connect=True)
    """

    validator = RDFGraphConnectivityValidator(chunk.graph, current_domain)

    result = validator.validate_connectivity()

    logger.debug(f"\n=== Connectivity Analysis for Chunk {chunk.iri} ===")
    logger.debug(f"Fully connected: {result['is_fully_connected']}")
    logger.debug(f"Number of components: {result['num_components']}")
    logger.debug(f"Total entities: {result['total_entities']}")
    logger.debug(f"Largest component size: {result['largest_component_size']}")

    if result["isolated_entities"]:
        logger.debug(
            f"Isolated entities: {[str(e) for e in result['isolated_entities']]}"
        )

    final_graph = deepcopy(chunk.graph)

    if not result["is_fully_connected"] and auto_connect:
        final_graph = validator.make_graph_connected(chunk_iri=chunk.iri)

        # Re-validate
        new_validator = RDFGraphConnectivityValidator(final_graph, current_domain)
        new_result = new_validator.validate_connectivity()
        logger.debug(
            f"After connection - Components: {new_result['num_components']}, Triples: {len(final_graph)}"
        )
    chunk.graph = final_graph
    return chunk


class RDFGraphConnectivityValidator:
    """Validates that entities within a chunk graph are connected"""

    def __init__(self, graph: RDFGraph, current_domain):
        self.graph = graph
        self.current_domain = current_domain

    def get_all_entities(self) -> Set[URIRef]:
        """Extract all unique entities (subjects and objects) from the graph"""
        entities = set()

        for subj, _, obj in self.graph:
            if isinstance(subj, URIRef):
                entities.add(subj)
            if isinstance(obj, URIRef):
                entities.add(obj)

        return entities

    def build_adjacency_graph(self) -> dict[URIRef, Set[URIRef]]:
        """Build an adjacency representation of the RDF graph"""
        adjacency = defaultdict(set)

        for subj, _, obj in self.graph:
            if isinstance(subj, URIRef) and isinstance(obj, URIRef):
                adjacency[subj].add(obj)
                adjacency[obj].add(subj)  # Treat as undirected for connectivity

        return adjacency

    def find_connected_components(self) -> list[Set[URIRef]]:
        """Find all connected components using BFS"""
        entities = self.get_all_entities()
        adjacency = self.build_adjacency_graph()
        visited = set()
        components = []

        for entity in entities:
            if entity not in visited:
                component = set()
                queue = deque([entity])

                while queue:
                    current = queue.popleft()
                    if current not in visited:
                        visited.add(current)
                        component.add(current)

                        # Add neighbors to queue
                        for neighbor in adjacency.get(current, set()):
                            if neighbor not in visited:
                                queue.append(neighbor)

                if component:
                    components.append(component)

        return components

    def validate_connectivity(self) -> dict[str, Any]:
        """
        Validate graph connectivity and return detailed results
        Returns dict with connectivity info and isolated entities
        """
        components = self.find_connected_components()
        entities = self.get_all_entities()

        result = {
            "is_fully_connected": len(components) <= 1,
            "num_components": len(components),
            "total_entities": len(entities),
            "components": components,
            "isolated_entities": [],
            "largest_component_size": 0,
        }

        if components:
            result["largest_component_size"] = max(len(comp) for comp in components)

            # Find isolated entities (components of size 1)
            result["isolated_entities"] = [
                list(comp)[0] for comp in components if len(comp) == 1
            ]

        return result

    def get_path_between_entities(
        self, entity_a: URIRef, entity_b: URIRef
    ) -> Optional[list[URIRef]]:
        """Find the shortest path between two entities using BFS"""
        if entity_a == entity_b:
            return [entity_a]

        adjacency = self.build_adjacency_graph()
        visited = set()
        queue = deque([(entity_a, [entity_a])])

        while queue:
            current, path = queue.popleft()

            if current == entity_b:
                return path

            if current not in visited:
                visited.add(current)

                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        queue.append((neighbor, path + [neighbor]))

        return None  # No path found

    def make_graph_connected(self, chunk_iri) -> RDFGraph:
        """
        Make a disconnected graph connected by adding bridging relationships

        Args:

        Returns:
            New connected graph
        """
        components = self.find_connected_components()

        if len(components) <= 1:
            logger.info("RDFGraph is already connected")
            return self.graph

        # Create a new graph with all original triples
        connected_graph = RDFGraph()
        for triple in self.graph:
            connected_graph.add(triple)

        # Copy namespace bindings
        for prefix, namespace in self.graph.namespaces():
            connected_graph.bind(prefix, namespace)

        connected_graph = self._connect_via_chunk_hub(
            connected_graph, components, chunk_iri
        )

        logger.info(f"Connected {len(components)} components")
        return connected_graph

    def _connect_via_chunk_hub(
        self, graph: RDFGraph, components: list[Set[URIRef]], chunk_iri
    ) -> RDFGraph:
        """Connect components by creating a chunk hub entity"""
        # Create or use existing chunk URI
        hub_uri = URIRef(chunk_iri)

        # Add hub entity metadata

        graph.add((hub_uri, RDF.type, URIRef(f"{self.current_domain}TextChunk")))
        graph.add((hub_uri, RDFS.label, Literal("Document chunk")))

        # Connect hub to one representative entity from each component
        for i, component in enumerate(components):
            # Choose representative entity (could be improved with better heuristics)
            representative = self._choose_representative_entity(component, graph)

            # Add bidirectional connections
            graph.add((hub_uri, SCHEMA.hasPart, representative))
            graph.add((representative, PROV.wasQuotedFrom, hub_uri))

        return graph

    def _choose_representative_entity(
        self, component: Set[URIRef], graph: RDFGraph
    ) -> Optional[URIRef]:
        """Choose the best representative entity from a component"""
        if not component:
            return None

        # Heuristics for choosing representative:
        # 1. Entity with most connections (highest degree)
        # 2. Entity with a label
        # 3. First entity alphabetically

        entity_degrees = {}
        entities_with_labels = set()

        for entity in component:
            # Count connections
            degree = sum(1 for s, p, o in graph if s == entity or o == entity)
            entity_degrees[entity] = degree

            # Check if entity has a label
            for s, p, o in graph:
                if s == entity and p in [RDFS.label, RDFS.comment]:
                    entities_with_labels.add(entity)
                    break

        # Prefer entities with labels and high degree
        if entities_with_labels:
            return max(entities_with_labels, key=lambda e: entity_degrees.get(e, 0))
        else:
            return max(component, key=lambda e: entity_degrees.get(e, 0))
