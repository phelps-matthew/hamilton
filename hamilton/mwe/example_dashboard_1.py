import dash
from dash import html, dcc, dash_table
import plotly.graph_objects as go
import pandas as pd
from dash.dependencies import Input, Output, State

data = {
    "Satellite1": {"az": 70, "el": 30, "az-rate": 0.1, "el-rate": 0.1},
    "Satellite2": {"az": 50, "el": 20, "az-rate": 0.2, "el-rate": 0.2},
    "Satellite3": {"az": 30, "el": 40, "az-rate": 0.3, "el-rate": 0.3},
    "Satellite4": {"az": 20, "el": 50, "az-rate": 0.4, "el-rate": 0.4},
}

# Create DataFrame from the dictionary
df = (
    pd.DataFrame.from_dict(data, orient="index")
    .reset_index()
    .rename(columns={"index": "Satellite"})
)

# Initialize the app
app = dash.Dash(__name__)

# Define the app layout
app.layout = html.Div(
    children=[
        html.H1(children="Satellite Tracking Dashboard"),
        # Single track button
        html.Button("Track", id="track-button", n_clicks=0),
        dcc.Graph(
            id="live-update-graph",
            animate=True,
            config={
                "displayModeBar": False,
            },
        ),
        dash_table.DataTable(
            id="satellite-data",
            columns=[{"name": i, "id": i} for i in df.columns],
            data=df.to_dict("records"),
            row_selectable="single",
            selected_rows=[],
            style_data_conditional=[
                {
                    "if": {"state": "selected"},
                    "backgroundColor": "inherit !important",
                    "border": "inherit !important",
                }
            ],
            css=[
                {"selector": ".dash-cell.focused", "rule": "background-color: #D3D3D3 !important;"}
            ],
        ),
        dcc.Interval(id="interval-component", interval=1 * 1000, n_intervals=0),  # in milliseconds
    ]
)


# Update the graph every second
@app.callback(
    Output("live-update-graph", "figure"),
    [Input("interval-component", "n_intervals"), Input("satellite-data", "selected_rows")],
)
def update_graph_live(n, selected_rows):
    selected_row = selected_rows[0] if selected_rows else None
    fig = go.Figure()
    for i, row in df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["az"]],
                y=[row["el"]],
                mode="markers+text",
                text=[row["Satellite"]],
                textposition="bottom center",
                marker=dict(color="red" if i == selected_row else "blue"),
            )
        )
    return fig


# Handle row selections in the DataTable
@app.callback(Output("live-update-graph", "selectedData"), Input("satellite-data", "selected_rows"))
def display_selected_data(selected_rows):
    if selected_rows:
        return {"points": [{"pointIndex": selected_rows[0]}]}
    return {"points": []}


# Handle point selections in the graph
@app.callback(Output("satellite-data", "selected_rows"), Input("live-update-graph", "selectedData"))
def select_row(selectedData):
    if selectedData:
        return [selectedData["points"][0]["pointIndex"]]
    return []


# Handle track button click
@app.callback(
    Output("track-button", "disabled"),
    Input("track-button", "n_clicks"),
    State("satellite-data", "selected_rows"),
)
def track_satellite(n_clicks, selected_rows):
    if n_clicks > 0:
        if selected_rows:
            print(f"Tracking satellite {df.loc[selected_rows[0], 'Satellite']}")
            return True
    return False


if __name__ == "__main__":
    app.run_server(debug=True)
