import numpy as np
import nxneo4j
import neo4j
import networkx as nx
from collections import defaultdict

# for Spinner
import sys
import time
import threading

import ipdb

from comptox_ai.cypher import queries

from comptox_ai.utils import execute_cypher_transaction


class Spinner(object):
    """See https://stackoverflow.com/a/39504463/1730417
    """
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\':
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay): self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False


class Graph:
    """
    Base class for a knowledge graph used in ComptoxAI.

    This is essentially a connection to a Neo4j graph database plus a plethora
    of convenience methods for interacting with that graph database. Currently,
    graph algorithms (or procedure calls to Neo4j that trigger
    externally-defined graph algorithms) are defined _here_. In the future, this
    is planned to change - a separate class will be built for all graph
    algorithms, and this class will interact with the Graph class to execute
    queries and consume the results.
    """
    def __init__(self, driver, **kwargs):
        """[summary]Initialize a ComptoxAI knowledge graph supported by a Neo4j
        graph database instance.
        
        Parameters
        ----------
        driver : neo4j.Driver
            A Neo4j driver object that will maintain an active connection to a
            Neo4j database server containing ComptoxAI data.
        """

        self.driver_connected = False

        self.driver = driver
        self.test_driver

        # If node_labels is the empty list, we don't filter on node type
        self.node_mask = kwargs.get("node_mask", [])
        if isinstance(self.node_mask, str):
            self.node_labels = [self.node_labels]

    # GRAPH LIFECYCLE METHODS

    def __del__(self):
        self.close_connection()

    def test_driver(self):
        if isinstance(self.driver, neo4j.DirectDriver):
            self.driver_connected = True
        else:
            self.driver_connected = False

    def close_connection(self):
        """Manually close the driver linking `self.graph` to a Neo4j
        graph database.
        """
        if self.driver_connected:
            self.driver.close()
        else:
            print("Error: Connection to Neo4j is not currently active")

    def open_connection(self,
                        username,
                        password,
                        uri="bolt://localhost:7687"):
        """Open a new connection to a Neo4j graph database.

        If a connection to a graph database already exists, it will be replaced.
        
        Parameters
        ----------
        username : str
            Neo4j database username
        password : str
            Neo4j database password
        uri : str, optional
            URI to a Bolt server that points at the graph database of interest,
            by default "bolt://localhost:7687"
        """
        if not self.driver_connected:
            try:
                self.driver = GraphDatabase.driver(self.uri,
                                                   auth=(self.username,
                                                         self.password))
                self.driver_connected = True
            except:
                print("Error opening connection to Neo4j")
                self.driver_connected = False
        else:
            print("Error: Connection to Neo4j is already active")
            print("       (Use `.close_connection()` and try again)")

    def _validate_connection_status(self):
        """Internal test for whether a connection to a Neo4j graph
        database currently exists and is active.

        Returns
        -------
        bool
            True if a valid, active connection to a graph database exists,
            RuntimeError raised otherwise
        """
        if not self.driver_connected:
            raise RuntimeError("Attempted to query Neo4j without an active \
                                database connection")
        return True

    # NODE RETRIEVAL METHODS

    def fetch_ontology_class_labels(self, populated_only=True,
                                    include_counts=True):
        """Get all classes from the Comptox AI that are present in the graph
        database.

        Parameters
        ----------
        populated_only : bool, optional
            Whether to only include classes that have 1 or more named
            individual, by default True.
        include_counts : bool, optional
            Whether to include counts for each label, by default True. If
            False, the return value will be a list rather than dict.

        Returns
        -------
        list or dict
        """
        if populated_only:
            self.template = queries.NODE_COUNTS_BY_LABEL
            self.query = self.template.format()

            query_response = self.run_query_in_session(self.query)

            nodes_of_type = defaultdict(int)
            for label_set in query_response:
                ct = label_set['count']
                labels = label_set['labels']

                if ct == 0:
                    continue

                if 'owl__NamedIndividual' not in labels:
                    continue

                for label in label_set['labels']:
                    prefix = label.split('__')[0]
                    suffix = label.split('__')[-1]
                    if prefix == 'ns0':
                        nodes_of_type[suffix] += ct

            if include_counts:
                return dict(nodes_of_type)
            else:
                return list(nodes_of_type.keys())

    def get_node_degrees(self, node_type=None):
        """Retrieve a list of URIs and their corresponding degrees.

        Parameters
        ----------
        node_type : str, optional
            Ontology class corresponding to the desired node type, by default
            None.

        Returns
        -------
        list of (str, int)
            Each returned element is a tuple containing a node's URI and that
            node's degree.
        """
        if node_type is None:
            self.template = queries.FETCH_ALL_NODE_DEGREES
            self.query = self.template
        else:
            self.template = queries.FETCH_NODE_DEGREES_FOR_CLASS
            self.query = self.template.format(node_type)

        query_response = self.run_query_in_session(self.query)

        if len(query_response) == 0:
            return None
        else:
            return [(x['uri'], x['degree']) for x in query_response]

    def fetch_node_by_uri(self, uri):
        """Retrieve a node from Neo4j matching the given URI.

        Parameters
        ----------
        uri : str
            URI of the node to fetch.

        Returns
        -------
        neo4j.Record
            Node corresponding to the provided URI.
        """
        if uri is None:
            print("No URI given -- aborting")
        else:
            self.template = queries.FETCH_INDIVIDUAL_NODE_BY_URI
            self.query = self.template.format(uri)

            query_response = self.run_query_in_session(self.query)

            if len(query_response) == 0:
                return None
            else:
                assert len(query_response) == 1
                return query_response[0]

    def fetch_nodes_by_label(self, label):
        """
        Fetch all nodes of a given label from the graph.

        The returned object is a list of Neo4j `Record`s, each
        containing a node `n` that has the queried label. Note that
        Neo4j allows multiple labels per node, so other labels may be
        present in the query results as well.

        Parameters
        ----------
        label: string
               Ontology class name corresponding to
               the type of node desired
        """
        if label is None:
            print("No label provided -- skipping")
        else:
            self.template = queries.FETCH_NODES_BY_LABEL
            self.query = self.template.format(label)

            query_response = self.run_query_in_session(self.query)

            return(query_response)

    def fetch_neighbors_by_uri(self, uri):
        """[summary]Fetch nodes corresponding to neighbors of a node represented by a
        given URI.
        
        Parameters
        ----------
        uri : str
            URI for a single node in the graph (including namespace)
        
        Returns
        -------
        list of neo4j.Record or None
            List of graph database records that represent the neighbors of
            `uri`. If the URI is invalid, `None` will be returned.
        """
        if uri is None:
            print("No URI given -- aborting")
        else:
            self.template = queries.FETCH_NEIGHBORS_BY_URI
            self.query = self.template.format(uri)

        query_response = self.run_query_in_session(self.query)

        if len(query_response) == 0:
            return None
        else:
            return query_response

    # NODE/GRAPH MODIFICATION METHODS

    # GRAPH I/O

    def to_networkx_graph(self):
        """Construct a NetworkX graph object from the data in the
        connected Neo4j graph database.

        Returns
        -------
        networkx.graph
        """

        # Fetch all triples
        self.template = queries.FETCH_ALL_TRIPLES
        self.query = self.template.format()

        print("Fetching all triples for named individuals - this may take a"
              "while...")
        with Spinner():
            query_response = self.run_query_in_session(self.query)

        print("All triples received, now processing them...")
        edges = []

        for triple in query_response:
            n = triple['n'].get('uri').split('#')[-1]
            r = triple['type(r)']
            m = triple['m'].get('uri').split('#')[-1]
            edges.append((n, r, m))

        G = nx.DiGraph()

        for n, r, m in edges:
            G.add_edge(u_of_edge=n, v_of_edge=m, edge_label=r)

        return(G)

    def to_graphml(self, G=None, edges=None, edge_labels=None):
        if not all([G, edges, edge_labels]):
            print("Incomplete network data given; calculating via"
                  "to_networkx_graph()...")
            G, edges, edge_labels = self.to_networkx_graph()
            print("...done")

    def build_adjacency_matrix(self, sparse=True):
        """Construct an adjacency matrix of individuals in the
        ontology graph.

        The adjacency matrix is a square matrix where each row and
        each column corresponds to one of the nodes in the graph. The
        value of cell $(i,j)$ is 1 if a directed edge goes from
        $\textrm{Node}_i$ to $\textrm{Node}_j$, and is $-1$ if an edge
        goes from $\textrm{Node}_j$ to $\textrm{Node}_i$.

        In the case of an undirected graph, the adjacency matrix is
        symmetric.

        Parameters
        ----------
        sparse : bool (default: `True`)
                 Whether to return the value as a Scipy sparse matrix
                 (default behavior) or a dense Numpy `ndarray`.

        """
        A = np.array()

        G = nxneo4j.Graph(self.driver)

        return A

    def build_incidence_matrix(self, sparse=True):
        """Construct an incidence matrix of individuals in the
        ontology graph.
        """
        B = np.array()

        return B

    # UTILITY METHODS

    def run_query_in_session(self, query):
        """Submit a cypher query transaction to the connected graph database
        driver and return the response to the calling function.

        Parameters
        ----------
        query : str
                String representation of the cypher query to be executed.

        Returns
        -------
        list of neo4j.Record
        """
        with self.driver.session() as session:
            query_response = session.read_transaction(
                execute_cypher_transaction,
                query
            )
        return(query_response)


class Path(object):
    """A sequence of graph database nodes representing a directed path.
    """
    def __init__(self, node_list):
        assert len(node_list) >= 1

        self.nodes = node_list

        self.start_node = self.nodes[0]
        self.end_node = self.nodes[-1]

    def __repr__(self):
        repr_str = "< 'Path' object of nodes with the following URI suffixes:"\
                   "\n\t["
        for x in self.nodes:
            repr_str += " {0},\n\t".format(x['uri'].split("#")[-1])
        repr_str = repr_str[:-3]
        repr_str += " ] >"
        return repr_str

    def __iter__(self):
        return (x for x in self.nodes)

    def get_uri_sequence(self):
        uris = []
        for node in self.nodes:
            uris.append(node['uri'])
        return uris