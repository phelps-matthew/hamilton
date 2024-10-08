import yaml
import pygraphviz as pgv

# Parse the YAML configuration
with open("../routing-manifest.yaml", "r") as file:
    routing_manifest = yaml.safe_load(file)

# Create a new directed graph
graph = pgv.AGraph(strict=False, directed=True)

# Loop through the exchanges in the manifest and add them to the graph
for exchange in routing_manifest["exchanges"]:
    exchange_name = exchange["name"]
    graph.add_node(exchange_name, shape="box", color="black")  # Exchanges are boxes

    # Add bindings (consumers)
    for binding in exchange.get("bindings", []):
        service = binding["service"]
        graph.add_node(service, shape="ellipse", color="blue")  # Services are ellipses

        for routing_key in binding["routing_keys"]:
            # Edges from service to exchange (consumer bindings)
            graph.add_edge(service, exchange_name, label=routing_key)

    # Add publishings (producers)
    for publishing in exchange.get("publishings", []):
        service = publishing["service"]
        rpc_label = "(RPC)" if publishing["rpc"] else ""

        for routing_key in publishing["routing_keys"]:
            # Edges from exchange to service (producer publishings)
            # The style is dashed for RPC calls
            graph.add_edge(
                exchange_name,
                service,
                label=f"{routing_key} {rpc_label}",
                style="dashed" if publishing["rpc"] else "solid",
            )
# Apply graph attributes for layout control
graph.graph_attr["ratio"] = "fill"  # Adjust as needed
#graph.graph_attr["size"] = "8,11!"  # Adjust as needed

# Layout and render the graph
layouts = ["neato", "fdp", "sfdp", "twopi", "circo", "dot"]
for layout in layouts:
    graph.layout(prog=layout)
    graph.draw(f"routing_topology_{layout}.png", format="png")

    print(f"Graph has been generated and saved as 'routing_topology_{layout}.png'")
