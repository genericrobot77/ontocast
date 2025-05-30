from .validate import RDFGraphConnectivityValidator
from rdflib import URIRef, Literal
from aot_cast.onto import RDFGraph, PROV, Chunk
from rdflib.namespace import RDF, RDFS
from rapidfuzz import fuzz
from typing import Any

import logging


logger = logging.getLogger(__name__)


class EntityDisambiguator:
    """Disambiguates and aggregates entities across multiple chunk graphs"""

    def __init__(self, similarity_threshold: float = 85.0):
        self.similarity_threshold = similarity_threshold

    def extract_entity_labels(self, graph: RDFGraph) -> dict[URIRef, str]:
        """Extract labels for entities from graph"""
        labels = {}

        for subj, pred, obj in graph:
            if pred in [RDFS.label, RDFS.comment] and isinstance(obj, Literal):
                labels[subj] = str(obj)
            elif isinstance(subj, URIRef):
                # Use local name as fallback label
                local_name = subj.split("/")[-1].split("#")[-1]
                if subj not in labels:
                    labels[subj] = local_name

        return labels

    def find_similar_entities(
        self, entities_with_labels: dict[URIRef, str]
    ) -> list[list[URIRef]]:
        """Group similar entities based on string similarity"""
        entity_groups = []
        processed = set()

        entities_list = list(entities_with_labels.keys())

        for i, entity1 in enumerate(entities_list):
            if entity1 in processed:
                continue

            similar_group = [entity1]
            label1 = entities_with_labels[entity1]
            processed.add(entity1)

            for j, entity2 in enumerate(entities_list[i + 1 :], i + 1):
                if entity2 in processed:
                    continue

                label2 = entities_with_labels[entity2]
                similarity = fuzz.ratio(label1.lower(), label2.lower())

                if similarity >= self.similarity_threshold:
                    similar_group.append(entity2)
                    processed.add(entity2)

            if len(similar_group) > 1:
                entity_groups.append(similar_group)

        return entity_groups

    def create_canonical_iri(
        self, similar_entities: list[URIRef], doc_iri: str
    ) -> URIRef:
        """Create a canonical URI for a group of similar entities"""
        # Use the shortest URI or most common pattern as canonical
        canonical = min(similar_entities, key=lambda x: len(str(x)))

        # Create new canonical URI in document namespace
        local_name = canonical.split("/")[-1].split("#")[-1]
        return URIRef(f"{doc_iri}/entity/{local_name}")


class ChunkRDFGraphAggregator:
    """Main class for aggregating and disambiguating chunk graphs"""

    def __init__(self, doc_iri: str, similarity_threshold: float = 85.0):
        self.doc_iri = doc_iri
        self.disambiguator = EntityDisambiguator(similarity_threshold)

    def aggregate_graphs(self, chunks: dict[str, Chunk]) -> RDFGraph:
        """
        Aggregate multiple chunk graphs with entity disambiguation
        Args:
            chunks: dict[str, Chunk]
        Returns:
            Aggregated graph with disambiguated entities
        """
        aggregated_graph = RDFGraph()

        # Bind namespaces
        aggregated_graph.bind("prov", PROV)
        aggregated_graph.bind("doc", self.doc_iri)

        # Collect all entities and their labels across chunks
        all_entities_with_labels = {}
        chunk_entity_mapping = {}

        for chunk_id, chunk in chunks.items():
            entities_labels = self.disambiguator.extract_entity_labels(chunk.graph)
            chunk_entity_mapping[chunk_id] = entities_labels
            all_entities_with_labels.update(entities_labels)

        # Find similar entities across chunks
        similar_entity_groups = self.disambiguator.find_similar_entities(
            all_entities_with_labels
        )

        # Create entity mapping (original -> canonical)
        entity_mapping = {}
        for group in similar_entity_groups:
            canonical_uri = self.disambiguator.create_canonical_iri(group, self.doc_iri)
            for entity in group:
                entity_mapping[entity] = canonical_uri

        # Process each chunk graph
        for chunk_id, chunk in chunks.items():
            # chunk = chunk.graph
            chunk_iri = URIRef(chunk.iri)

            # Add provenance information
            aggregated_graph.add((chunk_iri, RDF.type, PROV.Entity))
            aggregated_graph.add((chunk_iri, PROV.wasPartOf, URIRef(self.doc_iri)))

            # Add triples with entity disambiguation
            for subj, pred, obj in chunk.graph:
                # Map entities to canonical URIs
                new_subj = entity_mapping.get(subj, subj)
                new_obj = (
                    entity_mapping.get(obj, obj) if isinstance(obj, URIRef) else obj
                )

                # Add the triple
                aggregated_graph.add((new_subj, pred, new_obj))

                # Add provenance: which chunk this triple came from
                if isinstance(new_subj, URIRef):
                    aggregated_graph.add((new_subj, PROV.wasGeneratedBy, chunk_iri))

        logger.info(
            f"Aggregated {len(chunks)} chunks into graph with {len(aggregated_graph)} triples"
        )
        return aggregated_graph

    def validate_aggregated_connectivity(
        self, aggregated_graph: RDFGraph
    ) -> dict[str, Any]:
        """Validate connectivity of the aggregated graph"""
        return RDFGraphConnectivityValidator(aggregated_graph).validate_connectivity()


# def process_document_chunks(
#     doc_id: str, chunks: dict[str, Chunk]
# ) -> RDFGraph:
#     """
#     Complete pipeline for processing document chunks
#     Args:
#         doc_id: Document identifier
#         chunks: dict[str, Chunk]
#     Returns:
#         Aggregated and validated graph
#     """
#     logger.debug(f"Processing document {doc_id} with {len(chunks)} chunks")
#
#     # Validate connectivity of each chunk and connect if needed
#     connected_chunks = {}
#     for chunk_id, chunk in chunks.items():
#         chunk = validate_and_connect_chunk(
#             chunk,
#             auto_connect=True,
#             connection_strategy="chunk_hub",
#         )
#         connected_chunks[chunk_id] = chunk
#
#     # Aggregate graphs (now using connected versions)
#     aggregator = ChunkRDFGraphAggregator(doc_id)
#     aggregated_graph = aggregator.aggregate_graphs(connected_chunks)
#
#     # Validate aggregated graph connectivity
#     connectivity_result = RDFGraphConnectivityValidator(aggregated_graph).validate_connectivity()
#
#     logger.debug("\n=== Final Aggregated RDFGraph Analysis ===")
#     logger.debug(f"Total triples: {len(aggregated_graph)}")
#     logger.debug(f"Fully connected: {connectivity_result['is_fully_connected']}")
#     logger.debug(f"Components: {connectivity_result['num_components']}")
#
#     return aggregated_graph
