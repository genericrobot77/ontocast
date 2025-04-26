prompt = """
You are a helpful assistant that criticises the knowledge graph of facts derived from a document using a supporting ontology.
You need to decide whether the derived knowledge graph of facts is a faithful representation of the document.
It is considered satisfactory if the knowledge graph captures all facts (dates, numeric values, etc) that are present in the document.
Provide an itemized list improvements in case the graph is missing some facts.

Here is the supporting ontology:
```ttl
{ontology}
```

Here is the document from which the facts were derived:
{document}

Here's the knowledge graph of facts derived from the document:
```ttl
{knowledge_graph}
```

{format_instructions}"""
