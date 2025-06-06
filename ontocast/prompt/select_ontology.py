template_prompt = """
You are a helpful assistant that decides which ontology to use for a given document.
You are given a list of ontologies and a document.
You need to decide which ontology can be used for the document to create a semantic graph.
Here is the list of ontologies:
{ontologies_desc}

Here is an excerpt from the document:
{excerpt}

{format_instructions}
"""
