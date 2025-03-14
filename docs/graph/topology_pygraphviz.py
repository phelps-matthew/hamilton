import yaml
import pygraphviz as pgv

# Parse the YAML configuration
with open("../routing-manifest.yaml", "r") as file:
    routing_manifest = yaml.safe_load(file)

# Create a new directed graph
graph = pgv.AGraph(strict=False, directed=True)

# Keep track of the previous exchange node
previous_exchange_node = None

# Loop through the exchanges in the manifest and add them to the graph
for exchange in routing_manifest['exchanges']:
    exchange_name = exchange['name']
    # Add exchange nodes
    graph.add_node(exchange_name, shape='box', style='filled', fillcolor='lightgrey')

    # Add bindings and publishings as directed edges
    for binding in exchange.get('bindings', []):
        service = binding['service']
        graph.add_node(service, shape='ellipse', style='filled', fillcolor='white')
        for routing_key in binding['routing_keys']:
            graph.add_edge(service, exchange_name, label=routing_key)

    for publishing in exchange.get('publishings', []):
        service = publishing['service']
        rpc_label = "(RPC)" if publishing['rpc'] else ""
        for routing_key in publishing['routing_keys']:
            graph.add_edge(exchange_name, service, label=f"{routing_key} {rpc_label}")

    # Connect exchange nodes with invisible edges to enforce vertical layout
    if previous_exchange_node:
        graph.add_edge(previous_exchange_node, exchange_name, style='invis')

    # Update the previous exchange node
    previous_exchange_node = exchange_name

# Layout and render the graph
graph.layout(prog='dot')
graph.draw('routing_topology.png', format='png')
exit()


# Set graph attributes to encourage a vertical layout
graph.graph_attr.update(
    {
        "rankdir": "TB",
        "nodesep": "1.0",
        "ranksep": "2.0",
    }
)

# Layout and render the graph
layouts = ["neato", "sfdp", "twopi", "circo", "dot"]
for layout in layouts:
    graph.layout(prog=layout)
    graph.draw(f"routing_topology_{layout}.png", format="png")

    print(f"Graph has been generated and saved as 'routing_topology_{layout}.png'")
