import abc
import os
from typing import Optional

from pydantic import Field
from rdflib import Graph

from ontocast.onto import Ontology
from ontocast.tool import Tool


class TripleStoreManager(Tool):
    """Base class for managing RDF triple stores.

    This class defines the interface for triple store management operations,
    including fetching and storing ontologies and their graphs.

    """

    def __init__(self, **kwargs):
        """Initialize the triple store manager.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)

    @abc.abstractmethod
    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch all available ontologies.

        Returns:
            list[Ontology]: List of available ontologies.
        """
        return []

    @abc.abstractmethod
    def serialize_ontology(self, o: Ontology, **kwargs):
        """Store an ontology in the triple store.

        Args:
            o: The ontology to store.
            **kwargs: Additional keyword arguments for serialization.
        """
        pass

    @abc.abstractmethod
    def serialize_facts(self, g: Graph, **kwargs):
        """Store a graph with a given name.

        Args:
            g: The graph to store.
            **kwargs: Additional keyword arguments for serialization.
        """
        pass


class TripleStoreManagerWithAuth(TripleStoreManager):
    uri: Optional[str] = Field(default=None, description="Triple store connection URI")
    auth: Optional[tuple] = Field(
        default=None, description="Triple store authentication tuple (user, password)"
    )

    def __init__(self, uri=None, auth=None, env_uri=None, env_auth=None, **kwargs):
        # Use env vars if not provided
        uri = uri or (os.getenv(env_uri) if env_uri else None)
        auth_env = auth or (os.getenv(env_auth) if env_auth else None)
        if auth_env and not isinstance(auth_env, tuple):
            if "/" in auth_env:
                user, password = auth_env.split("/", 1)
                auth = (user, password)
            else:
                raise ValueError(
                    f"{env_auth or 'TRIPLESTORE_AUTH'} must be in 'user/password' format"
                )
        elif isinstance(auth_env, tuple):
            auth = auth_env
        # else: auth remains None
        super().__init__(uri=uri, auth=auth, **kwargs)
