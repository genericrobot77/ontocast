from rdflib import URIRef, Literal
from ontocast.onto import RDFGraph, PROV, Chunk
from rdflib.namespace import RDF, RDFS
from rapidfuzz import fuzz

import logging


logger = logging.getLogger(__name__)


class ChunkRDFGraphAggregator:
    """Main class for aggregating and disambiguating chunk graphs"""

    def __init__(self, similarity_threshold: float = 85.0):
        self.disambiguator = EntityDisambiguator(similarity_threshold)

    def aggregate_graphs(self, chunks: list[Chunk], doc_iri) -> RDFGraph:
        """
        Aggregate multiple chunk graphs with entity and predicate disambiguation
        Args:
            chunks: list[Chunk]
        Returns:
            Aggregated graph with disambiguated entities and predicates
        """

        aggregated_graph = RDFGraph()

        # Bind namespaces
        aggregated_graph.bind("prov", PROV)
        aggregated_graph.bind("cd", doc_iri)

        # Collect all entities and their labels across chunks
        all_entities_with_labels = {}
        chunk_entity_mapping = {}

        # Collect all predicates and their info across chunks
        all_predicates_with_info = {}
        chunk_predicate_mapping = {}

        for chunk_id, chunk in chunks:
            chunk_id = chunk.hid
            # Entity disambiguation
            entities_labels = self.disambiguator.extract_entity_labels(chunk.graph)
            chunk_entity_mapping[chunk_id] = entities_labels
            all_entities_with_labels.update(entities_labels)

            # Predicate disambiguation
            predicates_info = self.disambiguator.extract_predicate_info(chunk.graph)
            chunk_predicate_mapping[chunk_id] = predicates_info

            # Merge predicate info, preferring non-None values
            for pred, info in predicates_info.items():
                if pred not in all_predicates_with_info:
                    all_predicates_with_info[pred] = info
                else:
                    # Merge info, preferring non-None values
                    for key in ["label", "comment", "domain", "range"]:
                        if (
                            all_predicates_with_info[pred][key] is None
                            and info[key] is not None
                        ):
                            all_predicates_with_info[pred][key] = info[key]
                    # If either source has explicit property declaration, keep it
                    if info["is_explicit_property"]:
                        all_predicates_with_info[pred]["is_explicit_property"] = True

        # Find similar entities across chunks
        similar_entity_groups = self.disambiguator.find_similar_entities(
            all_entities_with_labels
        )

        # Find similar predicates across chunks
        similar_predicate_groups = self.disambiguator.find_similar_predicates(
            all_predicates_with_info
        )

        # Create entity mapping (original -> canonical)
        entity_mapping = {}
        for group in similar_entity_groups:
            canonical_uri = self.disambiguator.create_canonical_iri(group, doc_iri)
            for entity in group:
                entity_mapping[entity] = canonical_uri

        # Create predicate mapping (original -> canonical)
        predicate_mapping = {}
        for group in similar_predicate_groups:
            # Find the predicate with the most complete information
            best_pred = max(
                group,
                key=lambda p: sum(
                    1 for v in all_predicates_with_info[p].values() if v is not None
                ),
            )

            # Create canonical URI using the best predicate
            local_name = best_pred.split("/")[-1].split("#")[-1]
            canonical_uri = URIRef(f"{doc_iri}/predicate/{local_name}")

            # Map all predicates in the group to the canonical URI
            for predicate in group:
                predicate_mapping[predicate] = canonical_uri

        # Process each chunk graph
        for chunk in chunks:
            chunk_iri = URIRef(chunk.iri)

            # Add provenance information
            aggregated_graph.add((chunk_iri, RDF.type, PROV.Entity))
            aggregated_graph.add((chunk_iri, PROV.wasPartOf, URIRef(doc_iri)))

            # Add triples with entity and predicate disambiguation
            for subj, pred, obj in chunk.graph:
                # Map entities and predicates to canonical URIs
                new_subj = entity_mapping.get(subj, subj)
                new_pred = predicate_mapping.get(pred, pred)
                new_obj = (
                    entity_mapping.get(obj, obj) if isinstance(obj, URIRef) else obj
                )

                # Add the triple
                aggregated_graph.add((new_subj, new_pred, new_obj))

                # Add provenance: which chunk this triple came from
                if isinstance(new_subj, URIRef):
                    aggregated_graph.add((new_subj, PROV.wasGeneratedBy, chunk_iri))

        logger.info(
            f"Aggregated {len(chunks)} chunks into graph with {len(aggregated_graph)} triples"
        )
        return aggregated_graph


class EntityDisambiguator:
    """Disambiguate and aggregate entities across multiple chunk graphs"""

    def __init__(self, similarity_threshold: float = 85.0):
        self.similarity_threshold = similarity_threshold

    def extract_entity_labels(self, graph: RDFGraph) -> dict[URIRef, str]:
        """Extract labels for entities from graph"""
        labels = {}

        for subj, pred, obj in graph:
            if pred in [RDFS.label, RDFS.comment] and isinstance(obj, Literal):
                labels[subj] = str(obj)
            elif isinstance(subj, URIRef):
                local_name = subj.split("/")[-1].split("#")[-1]
                if subj not in labels:
                    labels[subj] = local_name

        return labels

    def extract_predicate_info(self, graph: RDFGraph) -> dict[URIRef, dict]:
        """Extract predicate information including labels, domains, and ranges"""
        predicate_info = {}

        # First pass: identify all predicates used in triples
        for _, pred, _ in graph:
            if isinstance(pred, URIRef) and pred not in predicate_info:
                predicate_info[pred] = {
                    "label": None,
                    "comment": None,
                    "domain": None,
                    "range": None,
                    "is_explicit_property": False,
                }

        # Second pass: collect metadata for predicates
        for subj, pred, obj in graph:
            if pred == RDF.type and obj == RDF.Property:
                # Mark as explicitly declared property
                if subj in predicate_info:
                    predicate_info[subj]["is_explicit_property"] = True
            elif pred in [RDFS.label, RDFS.comment] and isinstance(obj, Literal):
                if subj in predicate_info:
                    if pred == RDFS.label:
                        predicate_info[subj]["label"] = str(obj)
                    else:
                        predicate_info[subj]["comment"] = str(obj)
            elif pred == RDFS.domain:
                if subj in predicate_info:
                    predicate_info[subj]["domain"] = obj
            elif pred == RDFS.range:
                if subj in predicate_info:
                    predicate_info[subj]["range"] = obj

        # For predicates without labels, try to infer from URI
        for pred in predicate_info:
            if not predicate_info[pred]["label"]:
                local_name = pred.split("/")[-1].split("#")[-1]
                # Convert camelCase or snake_case to readable format
                label = " ".join(
                    word.lower() for word in local_name.replace("_", " ").split()
                )
                predicate_info[pred]["label"] = label

        return predicate_info

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

    def find_similar_predicates(
        self, predicates_with_info: dict[URIRef, dict]
    ) -> list[list[URIRef]]:
        """Group similar predicates based on string similarity and domain/range compatibility"""
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

                # Check label similarity
                if info1["label"] and info2["label"]:
                    label_similarity = fuzz.ratio(
                        info1["label"].lower(), info2["label"].lower()
                    )

                    # Check domain/range compatibility
                    domain_compatible = info1["domain"] == info2["domain"] or not (
                        info1["domain"] and info2["domain"]
                    )
                    range_compatible = info1["range"] == info2["range"] or not (
                        info1["range"] and info2["range"]
                    )

                    if (
                        label_similarity >= self.similarity_threshold
                        and domain_compatible
                        and range_compatible
                    ):
                        similar_group.append(pred_b)
                        processed.add(pred_b)

            if len(similar_group) > 1:
                predicate_groups.append(similar_group)

        return predicate_groups

    def create_canonical_iri(
        self, similar_entities: list[URIRef], doc_iri: str
    ) -> URIRef:
        """Create a canonical URI for a group of similar entities"""
        # Use the shortest URI or most common pattern as canonical
        canonical = min(similar_entities, key=lambda x: len(str(x)))

        # Create new canonical URI in document namespace
        local_name = canonical.split("/")[-1].split("#")[-1]
        return URIRef(f"{doc_iri}/entity/{local_name}")

    def create_canonical_predicate(
        self, similar_predicates: list[URIRef], doc_iri: str, graph: RDFGraph
    ) -> URIRef:
        """Create a canonical URI for a group of similar predicates"""
        # Use the predicate with the most complete information
        predicate_info = self.extract_predicate_info(graph)
        best_pred = max(
            similar_predicates,
            key=lambda p: sum(1 for v in predicate_info[p].values() if v is not None),
        )

        # Create new canonical URI in document namespace
        local_name = best_pred.split("/")[-1].split("#")[-1]
        return URIRef(f"{doc_iri}/predicate/{local_name}")
