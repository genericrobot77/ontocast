prompt_fresh = """You are a helpful assistant that criticises a newly proposed ontology.
You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.

{ontology_original_str}

Here is the document from which the ontology was derived:
{document}

Here is the proposed ontology:
```ttl
{ontology_update}
```

{format_instructions}
"""

prompt_update = """You are a helpful assistant that criticises an ontology update.
You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.

{ontology_original_str}

Here is the document from which the ontology update was derived:
{document}

Here is the ontology update:
```ttl
{ontology_update}
```

{format_instructions}
"""
