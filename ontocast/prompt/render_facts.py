ontology_instruction = """
Use the following ontology <{ontology_iri}>:

```ttl
{ontology_str}
```
"""


template_prompt = """
Generate semantic triples representing facts (not abstract entities) in turtle (ttl) format from the text below.

{ontology_instruction}

Follow the instructions:

- use commonly known ontologies (RDFS, OWL, schema etc) and the provided ontology <{ontology_namespace}> to place (define) entities/classes/types and relationships between them that can be inferred from the document.
- for facts from the document, use <{current_doc_namespace}> namespace with prefix `cd:` as `@prefix cd: {current_doc_namespace} .`
- all entities identified by <{current_doc_namespace}> namespace (facts, less abstract entities) must be linked to entities from either domain ontology <{ontology_namespace}> or basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
- all facts should form a connect graph with respect to <{current_doc_namespace}> namespace
- (IMPORTANT) define all prefixes for all namespaces used in the ontology, etc rdf, rdfs, owl, schema, etc
- all facts representing numeric values, dates etc should not be kept in literal strings: expand them into triple and use xsd:integer, xsd:decimal, xsd:float, xsd:date for dates, ISO for currencies, etc, assign correct units and define correct relations
- pay attention to correct formatting of literals, e.g. dates, currencies. Numeric literals should be formatted using double quotes, when they are typed with `^^`, for example `fsec:hasRevenue "13"^^xsd:decimal ;`
- make semantic representation of facts as atomic (!!!) as possible
- to extract data from tables, use CSV on the Web (CSVW) to describe tables

Here is the document:
```
{text}
```

{failure_instruction}

{format_instructions}
"""
