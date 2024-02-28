import yaml
import pygraphviz as pgv

# Parse the YAML configuration
routing_manifest = yaml.safe_load("../routing-manifest.yaml")

# Create a new directed graph
graph = pgv.AGraph(strict=False, directed=True)

# Loop through the exchanges in the manifest and add them to the graph
for exchange in routing_manifest['exchanges']:
    exchange_name = exchange['name']
    graph.add_node(exchange_name, shape='box', color='black')  # Exchanges are boxes
    
    # Add bindings (consumers)
    for binding in exchange.get('bindings', []):
        service = binding['service']
        graph.add_node(service, shape='ellipse', color='blue')  # Services are ellipses
        
        for routing_key in binding['routing_keys']:
            # Edges from service to exchange (consumer bindings)
            graph.add_edge(service, exchange_name, label=routing_key)
    
    # Add publishings (producers)
    for publishing in exchange.get('publishings', []):
        service = publishing['service']
        rpc_label = "(RPC)" if publishing['rpc'] else ""
        
        for routing_key in publishing['routing_keys']:
            # Edges from exchange to service (producer publishings)
            # The style is dashed for RPC calls
            graph.add_edge(exchange_name, service, label=f"{routing_key} {rpc_label}", style='dashed' if publishing['rpc'] else 'solid')

# Layout and render the graph
graph.layout(prog='dot')
graph.draw('routing_topology.png', format='png')

print("Graph has been generated and saved as 'routing_topology.png'")
