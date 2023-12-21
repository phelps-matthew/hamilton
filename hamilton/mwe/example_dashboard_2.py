import json

from dash import Dash, dcc, html, dash_table, no_update, callback_context
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

# external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


styles = {"pre": {"border": "thin lightgrey solid", "overflowX": "scroll"}}

data = {
    "Satellite1": {"az": 70, "el": 30, "az-rate": 0.1, "el-rate": 0.1},
    "Satellite2": {"az": 50, "el": 20, "az-rate": 0.2, "el-rate": 0.2},
    "Satellite3": {"az": 30, "el": 40, "az-rate": 0.3, "el-rate": 0.3},
    "Satellite4": {"az": 20, "el": 50, "az-rate": 0.4, "el-rate": 0.4},
}


df = (
    pd.DataFrame.from_dict(data, orient="index")
    .reset_index()
    .rename(columns={"index": "Satellite"})
)

fig = px.scatter(
    df, x="az", y="el", text="Satellite", hover_data=["az", "el", "az-rate", "el-rate"]
)
# fig2 = px.scatter(df, x="x", y="y", color="fruit", custom_data=["customdata"])

fig.update_layout(clickmode="select+event")

fig.update_traces(marker_size=20)

app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dcc.Graph(id="az_el_plot", figure=fig),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Pre(id="json_output", style=styles["pre"]),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        dcc.Graph(id="asdf", figure=fig),
                    ],
                    width=6,
                ),
            ]
        ),
        dbc.Row(
            [
                dash_table.DataTable(
                    df.to_dict("records"),
                    [{"name": i, "id": i} for i in df.columns],
                    id="tbl",
                    row_selectable="single",  # enable single row selection
                    selected_rows=[],
                ),
            ]
        ),
        dcc.Store(id="store-table", data=[]),
        dcc.Store(id="store-graph", data=[]),
        dcc.Store(id="store", data={"table_selected": [0], "graph_selected": [0]}),
    ]
)


@app.callback(
    Output("store-table", "data"), [Input("tbl", "selected_rows")], [State("store-graph", "data")]
)
def update_store_table(selected_rows, graph_selected):
    print(f"update_store_table: {graph_selected}")
    return selected_rows if graph_selected != selected_rows else no_update


@app.callback(
    Output("store-graph", "data"),
    [Input("az_el_plot", "selectedData")],
    [State("store-table", "data")],
)
def update_store_graph(selectedData, table_selected):
    print(f"update_store_graph: {table_selected}")
    point_index = selectedData["points"][0]["pointIndex"] if selectedData else None
    return [point_index] if table_selected != [point_index] else no_update


@app.callback(Output("tbl", "selected_rows"), [Input("store-table", "data")])
def update_table_selection(selected_rows):
    print(f"update_table_selection: {selected_rows}")
    return selected_rows if selected_rows is not None else []


@app.callback(Output("az_el_plot", "selectedData"), [Input("store-graph", "data")])
def update_graph_selection(selectedData):
    print(f"update_graph_selection: {selectedData}")
    if selectedData is not None and selectedData:
        return {"points": [{"pointIndex": selectedData[0]}]}
    else:
        print("returning no_update")
        return no_update


@app.callback(Output("tbl", "style_data_conditional"), Input("tbl", "selected_rows"))
def display_selected_rows(selected_rows):
    print(f"display_selected_rows: {selected_rows}")
    non_selected_band_color = "rgb(229, 236, 246)"
    selected_band_color = "#98c21f"
    return [
        {"if": {"row_index": "odd"}, "backgroundColor": non_selected_band_color},
        {"if": {"row_index": "even"}, "backgroundColor": "white"},
        {
            "if": {"row_index": selected_rows},
            "backgroundColor": selected_band_color,
            "fontWeight": "bold",
            "color": "white",
        },
    ]


@app.callback(
    Output("json_output", "children"),
    [Input("store-table", "data"), Input("store-graph", "data")],
)
def display_selected_data(selected_rows, selectedData):
    print(f"display_selected_data: {(selected_rows, selectedData)}")
    if selectedData is not None and selectedData:
        idx = selectedData[0]
        return json.dumps(df.iloc[idx].to_dict(), indent=2)
    elif selected_rows is not None and selected_rows:
        return json.dumps(df.iloc[selected_rows[0]].to_dict(), indent=2)
    else:
        return no_update


# @app.callback(Output("tbl", "selected_rows"), [Input("store", "data")])
# def update_table_selection(store_data):
#    table_selected = store_data.get("table_selected", None)
#    return [table_selected] if table_selected is not None else []

# @app.callback(Output("az_el_plot", "selectedData"), [Input("store", "data")])
# def update_graph_selection(store_data):
#    graph_selected = store_data.get("graph_selected", None)
#    if graph_selected is not None:
#        return {"points": [{"pointIndex": graph_selected}]}
#    else:
#        return no_update


# @app.callback(
#    Output("store", "data"),
#    [Input("tbl", "selected_rows"), Input("az_el_plot", "selectedData")],
#    [State("store", "data")],
# )
# def store_data_update(selected_rows, selectedData, store_data):
#    ctx = callback_context
#    if not ctx.triggered:
#        return no_update
#    else:
#        input_id = ctx.triggered[0]["prop_id"].split(".")[0]
#
#        if input_id == "tbl":
#            if selected_rows is not None:
#                selected_row = selected_rows[0] if selected_rows else None
#                return {
#                    "table_selected": selected_row,
#                    "graph_selected": store_data.get("graph_selected", None),
#                }
#        elif input_id == "az_el_plot":
#            if selectedData is not None:
#                idx = selectedData["points"][0]["pointIndex"]
#                return {
#                    "table_selected": store_data.get("table_selected", None),
#                    "graph_selected": idx,
#                }
#
#    return no_update


# @app.callback(Output("tbl", "style_data_conditional"), Input("tbl", "selected_rows"))
# def highlight_selected_rows(selected_rows):
#    non_selected_band_color = "rgb(229, 236, 246)"
#    selected_band_color = "#98c21f"
#    return [
#        {"if": {"row_index": "odd"}, "backgroundColor": non_selected_band_color},
#        {"if": {"row_index": "even"}, "backgroundColor": "white"},
#        {
#            "if": {"row_index": selected_rows},
#            "backgroundColor": selected_band_color,
#            "fontWeight": "bold",
#            "color": "white",
#        },
#    ]
#
#
# @app.callback(Output("json_output", "children"), Input("az_el_plot", "selectedData"))
# def display_selected_data(selectedData):
#    if selectedData is not None:
#        idx = selectedData["points"][0]["pointIndex"]
#        print(json.dumps(df.iloc[idx].to_dict(), indent=2))
#    return json.dumps(selectedData, indent=2)


if __name__ == "__main__":
    app.run_server(debug=True)
