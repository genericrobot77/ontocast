"""Graph aggregation tools for OntoCast.

This module provides functionality for aggregating and disambiguating RDF graphs
from multiple chunks, handling entity and predicate disambiguation, and ensuring
consistent namespace usage across the aggregated graph.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS

from ontocast.onto import PROV, Chunk, RDFGraph, derive_ontology_id

logger = logging.getLogger(__name__)


@dataclass
class EntityMetadata:
    """Metadata for an entity in the graph."""

    local_name: str
    label: Optional[str] = None
    comment: Optional[str] = None
    types: Set[URIRef] = field(default_factory=set)


@dataclass
class PredicateMetadata:
    """Metadata for a predicate in the graph."""

    local_name: str
    label: Optional[str] = None
    comment: Optional[str] = None
    domain: Optional[URIRef] = None
    range: Optional[URIRef] = None
    is_explicit_property: bool = False


class ChunkRDFGraphAggregator:
    """Main class for aggregating and disambiguating chunk graphs.

    This class provides functionality for combining RDF graphs from multiple chunks
    while handling entity and predicate disambiguation. It ensures consistent
    namespace usage and creates canonical URIs for similar entities and predicates.

    Attributes:
        disambiguator: Entity disambiguator instance for handling entity similarity.
    """

    def __init__(
        self, similarity_threshold: float = 85.0, semantic_threshold: float = 90.0
    ):
        """Initialize the chunk RDF graph aggregator.

        Args:
            similarity_threshold: Threshold for considering entities similar
                (default: 85.0).
            semantic_threshold: Higher threshold for semantic similarity
                (default: 90.0).
        """
        self.disambiguator = EntityDisambiguator(
            similarity_threshold, semantic_threshold
        )

    def aggregate_graphs(self, chunks: List[Chunk], doc_namespace: str) -> RDFGraph:
        """Aggregate multiple chunk graphs with entity and predicate disambiguation.

        This method combines multiple chunk graphs into a single graph while
        handling entity and predicate disambiguation. It creates canonical URIs
        for similar entities and predicates, and ensures consistent namespace usage.

        Args:
            chunks: List of chunks to aggregate.
            doc_namespace: The document IRI to use as base for canonical URIs.

        Returns:
            RDFGraph: Aggregated graph with disambiguated entities and predicates.
        """
        logger.info(f"Aggregating {len(chunks)} chunks for document {doc_namespace}")
        aggregated_graph = RDFGraph()

        # Ensure doc_namespace ends with appropriate separator
        if not doc_namespace.endswith(("/", "#")):
            doc_namespace = doc_namespace + "/"

        # Collect all namespaces from all chunks
        all_namespaces = {}
        for chunk in chunks:
            for prefix, uri in chunk.graph.namespaces():
                if prefix not in all_namespaces:
                    all_namespaces[prefix] = uri
                elif all_namespaces[prefix] != uri:
                    # If same prefix but different URI, create a new prefix
                    new_prefix = f"{prefix}_{len(all_namespaces)}"
                    all_namespaces[new_prefix] = uri

        # Bind all namespaces to the aggregated graph
        for prefix, uri in all_namespaces.items():
            aggregated_graph.bind(prefix, uri)
        aggregated_graph.bind("prov", PROV)
        aggregated_graph.bind("cd", doc_namespace)

        # Create a mapping of URIs to their canonical form
        uri_mapping = {}
        for prefix, uri in all_namespaces.items():
            uri_mapping[uri] = uri  # Preserve external namespaces

        # Collect all entities and their labels across chunks
        all_entities_with_labels: Dict[URIRef, EntityMetadata] = {}
        chunk_entity_mapping = {}

        # Collect all predicates and their info across chunks
        all_predicates_with_info: Dict[URIRef, PredicateMetadata] = {}
        chunk_predicate_mapping = {}

        # Track entity-type relationships for better disambiguation
        entity_types = defaultdict(set)

        # First pass: collect all entities and predicates
        for chunk in chunks:
            chunk_id = chunk.hid
            logger.info(f"Processing chunk {chunk_id} with namespace {chunk.namespace}")

            # Entity disambiguation
            entities_labels = self.disambiguator.extract_entity_labels(chunk.graph)
            chunk_entity_mapping[chunk_id] = entities_labels
            all_entities_with_labels.update(entities_labels)

            # Collect type information for entities
            for subj, pred, obj in chunk.graph:
                if (
                    pred == RDF.type
                    and isinstance(subj, URIRef)
                    and isinstance(obj, URIRef)
                ):
                    entity_types[subj].add(obj)

            # Predicate disambiguation
            predicates_info = self.disambiguator.extract_predicate_info(chunk.graph)
            chunk_predicate_mapping[chunk_id] = predicates_info

            # Merge predicate info, preferring more complete information
            for pred, info in predicates_info.items():
                if pred not in all_predicates_with_info:
                    all_predicates_with_info[pred] = info
                else:
                    # Merge info, preferring non-None values and more complete data
                    existing_info = all_predicates_with_info[pred]
                    for key in ["label", "comment", "domain", "range"]:
                        if (
                            getattr(existing_info, key) is None
                            and getattr(info, key) is not None
                        ):
                            setattr(existing_info, key, getattr(info, key))
                        elif (
                            getattr(existing_info, key) is not None
                            and getattr(info, key) is not None
                            and isinstance(getattr(info, key), str)
                            and len(str(getattr(info, key)))
                            > len(str(getattr(existing_info, key)))
                        ):
                            # Prefer longer, more descriptive values
                            setattr(existing_info, key, getattr(info, key))

                    # If either source has explicit property declaration, keep it
                    if info.is_explicit_property:
                        existing_info.is_explicit_property = True

        # Enhanced similarity detection with type information
        similar_entity_groups = self.disambiguator.find_similar_entities(
            all_entities_with_labels, entity_types
        )

        # Find similar predicates across chunks
        similar_predicate_groups = self.disambiguator.find_similar_predicates(
            all_predicates_with_info
        )

        # Create entity mapping (original -> canonical) with document namespace
        entity_mapping = {}
        canonical_entities = set()

        for group in similar_entity_groups:
            canonical_uri = self.disambiguator.create_canonical_iri(
                group, doc_namespace, all_entities_with_labels
            )
            # Ensure uniqueness of canonical URIs
            base_canonical = canonical_uri
            counter = 1
            while canonical_uri in canonical_entities:
                local_name = str(base_canonical).split(doc_namespace)[-1]
                canonical_uri = URIRef(f"{doc_namespace}{local_name}_{counter}")
                counter += 1

            canonical_entities.add(canonical_uri)
            for entity in group:
                entity_mapping[entity] = canonical_uri

        # Create predicate mapping (original -> canonical) with document namespace
        predicate_mapping = {}
        canonical_predicates = set()

        for group in similar_predicate_groups:
            canonical_uri = self.disambiguator.create_canonical_predicate(
                group, doc_namespace, all_predicates_with_info
            )
            # Ensure uniqueness of canonical URIs
            base_canonical = canonical_uri
            counter = 1
            while canonical_uri in canonical_predicates:
                local_name = str(base_canonical).split(doc_namespace)[-1]
                canonical_uri = URIRef(f"{doc_namespace}{local_name}_{counter}")
                counter += 1

            canonical_predicates.add(canonical_uri)
            for predicate in group:
                predicate_mapping[predicate] = canonical_uri

        # Add canonical entity and predicate metadata to the graph
        self._add_canonical_metadata(
            aggregated_graph,
            entity_mapping,
            predicate_mapping,
            all_entities_with_labels,
            all_predicates_with_info,
            entity_types,
        )

        # Process each chunk graph
        for chunk in chunks:
            chunk_iri = URIRef(chunk.iri)
            logger.debug(f"Processing triples from chunk {chunk_iri}")

            # Add provenance information
            aggregated_graph.add((chunk_iri, RDF.type, PROV.Entity))
            aggregated_graph.add(
                (chunk_iri, PROV.wasPartOf, URIRef(doc_namespace.rstrip("#/")))
            )

            # Add triples with entity and predicate disambiguation
            for subj, pred, obj in chunk.graph:
                # Skip if the subject is the chunk IRI itself
                if subj == chunk_iri:
                    continue

                # Map entities and predicates to canonical URIs
                new_subj = entity_mapping.get(subj, subj)
                new_pred = predicate_mapping.get(pred, pred)
                new_obj = (
                    entity_mapping.get(obj, obj) if isinstance(obj, URIRef) else obj
                )

                # Add the triple
                aggregated_graph.add((new_subj, new_pred, new_obj))

                # Add provenance: which chunk this triple came from
                if isinstance(new_subj, URIRef) and str(new_subj).startswith(
                    doc_namespace
                ):
                    aggregated_graph.add((new_subj, PROV.wasGeneratedBy, chunk_iri))

        logger.info(
            f"Aggregated {len(chunks)} chunks into graph "
            f"with {len(aggregated_graph)} triples, "
            f"{len(entity_mapping)} entity mappings, "
            f"{len(predicate_mapping)} predicate mappings"
        )
        return aggregated_graph

    def _add_canonical_metadata(
        self,
        graph: RDFGraph,
        entity_mapping: Dict[URIRef, URIRef],
        predicate_mapping: Dict[URIRef, URIRef],
        entity_labels: Dict[URIRef, EntityMetadata],
        predicate_info: Dict[URIRef, PredicateMetadata],
        entity_types: Dict[URIRef, Set[URIRef]],
    ) -> None:
        """Add metadata for canonical entities and predicates."""
        # Process mapped entities (those that had similar counterparts)
        canonical_to_originals = defaultdict(list)
        for original, canonical in entity_mapping.items():
            canonical_to_originals[canonical].append(original)

        for canonical, originals in canonical_to_originals.items():
            # Use the best label from the group
            best_label = self._get_best_label(
                [entity_labels.get(orig) for orig in originals]
            )
            if best_label:
                graph.add((canonical, RDFS.label, Literal(best_label)))

            # Add type information
            all_types = set()
            for orig in originals:
                all_types.update(entity_types.get(orig, set()))
            for type_uri in all_types:
                graph.add((canonical, RDF.type, type_uri))

        # Process unique entities (those that didn't have similar counterparts)
        processed_entities = set(entity_mapping.keys())

        # Get all unique entities from both labels and types
        all_entities = set(entity_labels.keys()) | set(entity_types.keys())

        for entity in all_entities:
            if entity not in processed_entities:
                # Add label if available
                if entity in entity_labels and entity_labels[entity].label is not None:
                    graph.add(
                        (entity, RDFS.label, Literal(entity_labels[entity].label))
                    )
                # Add type information
                if entity in entity_types:
                    for type_uri in entity_types[entity]:
                        graph.add((entity, RDF.type, type_uri))

        # Process mapped predicates (those that had similar counterparts)
        canonical_pred_to_originals = defaultdict(list)
        for original, canonical in predicate_mapping.items():
            # Only process predicates that use our document namespace
            if str(canonical).startswith(graph.namespace_manager.store.namespace("cd")):
                canonical_pred_to_originals[canonical].append(original)

        for canonical, originals in canonical_pred_to_originals.items():
            # Merge the best information from all original predicates
            merged_info = self._merge_predicate_info(
                [predicate_info.get(orig) for orig in originals]
            )

            if merged_info.label:
                graph.add((canonical, RDFS.label, Literal(merged_info.label)))
            if merged_info.comment:
                graph.add((canonical, RDFS.comment, Literal(merged_info.comment)))
            if merged_info.domain:
                graph.add((canonical, RDFS.domain, merged_info.domain))
            if merged_info.range:
                graph.add((canonical, RDFS.range, merged_info.range))
            if merged_info.is_explicit_property:
                graph.add((canonical, RDF.type, RDF.Property))

        # Process unique predicates (those that didn't have similar counterparts)
        processed_predicates = set(predicate_mapping.keys())
        for predicate, info in predicate_info.items():
            # Only process predicates that use our document namespace
            if str(predicate).startswith(graph.namespace_manager.store.namespace("cd")):
                if predicate not in processed_predicates:
                    if info.label:
                        graph.add((predicate, RDFS.label, Literal(info.label)))
                    if info.comment:
                        graph.add((predicate, RDFS.comment, Literal(info.comment)))
                    if info.domain:
                        graph.add((predicate, RDFS.domain, info.domain))
                    if info.range:
                        graph.add((predicate, RDFS.range, info.range))
                    if info.is_explicit_property:
                        graph.add((predicate, RDF.type, RDF.Property))

    def _get_best_label(
        self, label_dicts: List[Optional[EntityMetadata]]
    ) -> Optional[str]:
        """Get the best label from a list of label dictionaries."""
        labels = [d.label for d in label_dicts if d is not None and d.label is not None]
        if not labels:
            return None
        # Return the longest, most descriptive label
        return max(labels, key=len)

    def _merge_predicate_info(
        self, info_dicts: List[Optional[PredicateMetadata]]
    ) -> PredicateMetadata:
        """Merge predicate information from multiple sources."""
        merged = PredicateMetadata(local_name="", is_explicit_property=False)

        for info in info_dicts:
            if info is None:
                continue
            for key in ["label", "comment", "domain", "range"]:
                current_value = getattr(merged, key)
                new_value = getattr(info, key)
                if current_value is None and new_value is not None:
                    setattr(merged, key, new_value)
                elif (
                    current_value is not None
                    and new_value is not None
                    and isinstance(new_value, str)
                    and len(new_value) > len(str(current_value))
                ):
                    setattr(merged, key, new_value)
            if info.is_explicit_property:
                merged.is_explicit_property = True

        return merged


class EntityDisambiguator:
    """Disambiguate and aggregate entities across multiple chunk graphs.

    This class provides functionality for identifying and resolving similar
    entities across different chunks of text, using string similarity and
    semantic information.

    Attributes:
        similarity_threshold: Threshold for considering entities similar.
        semantic_threshold: Higher threshold for semantic similarity.
    """

    def __init__(
        self, similarity_threshold: float = 85.0, semantic_threshold: float = 90.0
    ):
        """Initialize the entity disambiguator.

        Args:
            similarity_threshold: Threshold for considering entities similar
                (default: 85.0).
            semantic_threshold: Higher threshold for semantic similarity
                (default: 90.0).
        """
        self.similarity_threshold = similarity_threshold
        self.semantic_threshold = semantic_threshold

    def normalize_uri(self, uri: URIRef, namespaces: Dict[str, str]) -> Tuple[str, str]:
        """Normalize a URI by expanding any prefixed names.

        Args:
            uri: The URI to normalize.
            namespaces: Dictionary of namespace prefixes to URIs.

        Returns:
            tuple[str, str]: The full URI and local name.
        """
        uri_str = str(uri)
        for prefix, namespace in namespaces.items():
            if uri_str.startswith(f"{prefix}:"):
                full_uri = uri_str.replace(f"{prefix}:", str(namespace))
                return full_uri, derive_ontology_id(URIRef(full_uri))
        return uri_str, derive_ontology_id(uri)

    def extract_entity_labels(self, graph: RDFGraph) -> Dict[URIRef, EntityMetadata]:
        """Extract labels for entities from graph, including their local names.

        Args:
            graph: The RDF graph to process.

        Returns:
            Dict[URIRef, EntityMetadata]: Dictionary mapping entity URIs to their
                metadata.
        """
        labels = {}
        namespaces = dict(graph.namespaces())

        # First pass: collect explicit labels and comments
        for subj, pred, obj in graph:
            if (
                pred in [RDFS.label, RDFS.comment]
                and isinstance(obj, Literal)
                and isinstance(subj, URIRef)
            ):
                full_uri, local_name = self.normalize_uri(subj, namespaces)
                uri_ref = URIRef(full_uri)
                if uri_ref not in labels:
                    labels[uri_ref] = EntityMetadata(local_name=local_name)

                if pred == RDFS.label:
                    labels[uri_ref].label = str(obj)
                elif pred == RDFS.comment:
                    labels[uri_ref].comment = str(obj)

        # Second pass: collect all entities and use local name as fallback
        for subj, pred, obj in graph:
            for entity in [subj, obj]:
                if isinstance(entity, URIRef):
                    full_uri, local_name = self.normalize_uri(entity, namespaces)
                    uri_ref = URIRef(full_uri)
                    if uri_ref not in labels:
                        labels[uri_ref] = EntityMetadata(local_name=local_name)
        return labels

    def find_similar_entities(
        self,
        entities_with_labels: Dict[URIRef, EntityMetadata],
        entity_types: Dict[URIRef, Set[URIRef]] = None,
    ) -> List[List[URIRef]]:
        """Group similar entities based on string similarity, local names, and types.

        Args:
            entities_with_labels: Dictionary mapping entity URIs to their metadata.
            entity_types: Optional dictionary mapping entities to their types.

        Returns:
            List[List[URIRef]]: Groups of similar entities.
        """
        if entity_types is None:
            entity_types = {}

        entity_groups = []
        processed = set()
        entities_list = list(entities_with_labels.keys())

        for i, entity1 in enumerate(entities_list):
            if entity1 in processed:
                continue

            similar_group = [entity1]
            info1 = entities_with_labels[entity1]
            types1 = entity_types.get(entity1, set())
            processed.add(entity1)

            for j, entity2 in enumerate(entities_list[i + 1 :], i + 1):
                if entity2 in processed:
                    continue

                info2 = entities_with_labels[entity2]
                types2 = entity_types.get(entity2, set())

                # Check type compatibility - entities should share at least one type
                #                                   or have no conflicting types
                type_compatible = (
                    not types1
                    or not types2  # One has no type info
                    or bool(types1.intersection(types2))  # They share at least one type
                )

                if not type_compatible:
                    continue

                # Exact local name match (highest priority)
                if info1.local_name.lower() == info2.local_name.lower():
                    similar_group.append(entity2)
                    processed.add(entity2)
                    continue

                # Label similarity check
                label1 = info1.label.lower() if info1.label is not None else ""
                label2 = info2.label.lower() if info2.label is not None else ""

                if label1 and label2:
                    similarity = fuzz.ratio(label1, label2)

                    # Use higher threshold if entities share types
                    threshold = (
                        self.semantic_threshold
                        if types1.intersection(types2)
                        else self.similarity_threshold
                    )

                    if similarity >= threshold:
                        similar_group.append(entity2)
                        processed.add(entity2)

            if len(similar_group) > 1:
                entity_groups.append(similar_group)

        return entity_groups

    def create_canonical_iri(
        self,
        similar_entities: List[URIRef],
        doc_namespace: str,
        entity_labels: Dict[URIRef, EntityMetadata],
    ) -> URIRef:
        """Create a canonical URI for a group of similar entities.

        Args:
            similar_entities: List of similar entity URIs.
            doc_namespace: The document namespace to use.
            entity_labels: Dictionary mapping entities to their metadata.

        Returns:
            URIRef: The canonical URI for the group.
        """
        # Choose the entity with the best label (longest, most descriptive)
        best_entity = max(
            similar_entities,
            key=lambda e: len(
                entity_labels.get(e, EntityMetadata(local_name="")).label or ""
            ),
        )

        best_info = entity_labels.get(
            best_entity, EntityMetadata(local_name=derive_ontology_id(best_entity))
        )
        local_name = best_info.local_name

        # Clean the local name for use in URI
        clean_local_name = self._clean_local_name(local_name)
        return URIRef(f"{doc_namespace}{clean_local_name}")

    def create_canonical_predicate(
        self,
        similar_predicates: List[URIRef],
        doc_namespace: str,
        predicate_info: Dict[URIRef, PredicateMetadata],
    ) -> URIRef:
        """Create a canonical URI for a group of similar predicates.

        Args:
            similar_predicates: List of similar predicate URIs.
            doc_namespace: The document namespace to use.
            predicate_info: Dictionary mapping predicate URIs to their metadata.

        Returns:
            URIRef: The canonical URI for the group.
        """
        # Use the predicate with the most complete information
        best_pred = max(
            similar_predicates,
            key=lambda p: sum(
                1
                for v in [
                    predicate_info.get(p, PredicateMetadata(local_name="")).label,
                    predicate_info.get(p, PredicateMetadata(local_name="")).comment,
                    predicate_info.get(p, PredicateMetadata(local_name="")).domain,
                    predicate_info.get(p, PredicateMetadata(local_name="")).range,
                ]
                if v is not None
            ),
        )

        # Create new canonical URI in document namespace
        best_info = predicate_info.get(
            best_pred, PredicateMetadata(local_name=derive_ontology_id(best_pred))
        )
        local_name = best_info.local_name

        # Clean the local name for use in URI
        clean_local_name = self._clean_local_name(local_name)
        return URIRef(f"{doc_namespace}{clean_local_name}")

    def _clean_local_name(self, local_name: str) -> str:
        """Clean a local name for use in URIs."""
        # Remove or replace problematic characters
        import re

        # Replace spaces and special characters with underscores
        cleaned = re.sub(r"[^\w\-.]", "_", local_name)
        # Remove consecutive underscores
        cleaned = re.sub(r"_+", "_", cleaned)
        # Remove leading/trailing underscores
        cleaned = cleaned.strip("_")
        return cleaned or "entity"  # Fallback if empty

    def extract_predicate_info(
        self, graph: RDFGraph
    ) -> Dict[URIRef, PredicateMetadata]:
        """Extract predicate information including labels, domains, and ranges.

        Args:
            graph: The RDF graph to process.

        Returns:
            Dict[URIRef, PredicateMetadata]: Dictionary mapping predicate URIs to
                their metadata.
        """
        predicate_info = {}
        namespaces = dict(graph.namespaces())

        # First pass: identify all predicates used in triples
        for _, pred, _ in graph:
            if isinstance(pred, URIRef):
                full_uri, local_name = self.normalize_uri(pred, namespaces)
                uri_ref = URIRef(full_uri)
                if uri_ref not in predicate_info:
                    predicate_info[uri_ref] = PredicateMetadata(local_name=local_name)

        # Second pass: collect metadata for predicates
        for subj, pred, obj in graph:
            if isinstance(subj, URIRef):
                full_subj_uri, _ = self.normalize_uri(subj, namespaces)
                norm_subj = URIRef(full_subj_uri)

                if pred == RDF.type and obj == RDF.Property:
                    if norm_subj in predicate_info:
                        predicate_info[norm_subj].is_explicit_property = True
                elif pred in [RDFS.label, RDFS.comment] and isinstance(obj, Literal):
                    if norm_subj in predicate_info:
                        if pred == RDFS.label:
                            predicate_info[norm_subj].label = str(obj)
                        else:
                            predicate_info[norm_subj].comment = str(obj)
                elif pred == RDFS.domain and norm_subj in predicate_info:
                    predicate_info[norm_subj].domain = obj
                elif pred == RDFS.range and norm_subj in predicate_info:
                    predicate_info[norm_subj].range = obj
        return predicate_info

    def find_similar_predicates(
        self, predicates_with_info: Dict[URIRef, PredicateMetadata]
    ) -> List[List[URIRef]]:
        """Group similar predicates based on string similarity and domain/range
        compatibility.

        Args:
            predicates_with_info: Dictionary mapping predicate URIs to their metadata.

        Returns:
            List[List[URIRef]]: Groups of similar predicates.
        """
        predicate_groups = []
        processed = set()
        predicates_list = list(predicates_with_info.keys())

        for i, pred_a in enumerate(predicates_list):
            if pred_a in processed:
                continue

            similar_group = [pred_a]
            info1 = predicates_with_info[pred_a]
            processed.add(pred_a)

            for j, pred_b in enumerate(predicates_list[i + 1 :], i + 1):
                if pred_b in processed:
                    continue

                info2 = predicates_with_info[pred_b]

                # Exact local name match
                if info1.local_name.lower() == info2.local_name.lower():
                    # Still check domain/range compatibility for exact matches
                    if self._check_domain_range_compatibility(info1, info2):
                        similar_group.append(pred_b)
                        processed.add(pred_b)
                    continue

                # Check label similarity
                if info1.label is not None and info2.label is not None:
                    label_similarity = fuzz.ratio(
                        info1.label.lower(), info2.label.lower()
                    )

                    # Check domain/range compatibility
                    domain_range_compatible = self._check_domain_range_compatibility(
                        info1, info2
                    )

                    if (
                        label_similarity >= self.similarity_threshold
                        and domain_range_compatible
                    ):
                        similar_group.append(pred_b)
                        processed.add(pred_b)

            if len(similar_group) > 1:
                predicate_groups.append(similar_group)

        return predicate_groups

    def _check_domain_range_compatibility(
        self, info1: PredicateMetadata, info2: PredicateMetadata
    ) -> bool:
        """Check if two predicates have compatible domains and ranges."""
        # Compatible if they match or one is None (not specified)
        domain_compatible = (
            info1.domain == info2.domain or info1.domain is None or info2.domain is None
        )
        range_compatible = (
            info1.range == info2.range or info1.range is None or info2.range is None
        )
        return domain_compatible and range_compatible
