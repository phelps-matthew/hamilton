import json
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objs as go
from dash import Dash, Input, Output, State, callback_context, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dash_bootstrap_templates import load_figure_template
from passive_rf.space_object_tracker import SpaceObjectTracker


SELECTED_ROW_COLOR = "#e5ecf6"

so_tracker = SpaceObjectTracker()
data = so_tracker.get_all_obs_params()
root_sat_db = so_tracker._root_sat_db
orbits = so_tracker.orbits


def create_dataframe(data: dict):
    # initialize the dataframe
    df = (
        pd.DataFrame.from_dict(
            data,
            orient="index",
        )
        .reset_index()
        .rename(columns={"index": "Satellite"})
        .reindex(
            columns=[
                "Satellite",
                "name",
                "norad_id",
                "az",
                "el",
                "az_rate",
                "el_rate",
                "range",
                "rel_vel",
                "time",
                "aos",
                "tca",
                "los",
            ],
        )
    )
    df = df.drop(["time"], axis=1)
    df["aos"] = df["aos"].dt.strftime("%m-%d %H:%M:%S")
    df["tca"] = df["tca"].dt.strftime("%m-%d %H:%M:%S")
    df["los"] = df["los"].dt.strftime("%m-%d %H:%M:%S")
    return df


def render_polar_graph(fig, orbit, az, el, customdata):
    aos_az = orbit["az"][0] if orbit["az"] else []
    aos_el = orbit["el"][0] if orbit["el"] else []
    los_az = orbit["az"][-1] if orbit["az"] else []
    los_el = orbit["el"][-1] if orbit["el"] else []

    if aos_az and aos_el and los_az and los_el:
        if aos_az < los_az:
            clockwise = True
        if 0 <= aos_az <= 90:
            aos_quad = 1
        elif 90 < aos_az <= 180:
            aos_quad = 2
        elif 180 < aos_az <= 270:
            aos_quad = 3
        else:
            aos_quad = 4
        if 0 <= los_az <= 90:
            los_quad = 1
        elif 90 < los_az <= 180:
            los_quad = 2
        elif 180 < los_az <= 270:
            los_quad = 3
        else:
            los_quad = 4

        text_str = ""
        if orbit["time"]:
            text_str = f"AOS: {orbit['time'][0]}<br>LOS: {orbit['time'][-1]}"

        fig.add_trace(
            go.Scatterpolar(
                r=orbit["el"],
                theta=orbit["az"],
                mode="lines",
                name="orbit",
                line={"color": "gray"},
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatterpolar(
                r=[aos_el, los_el],
                theta=[aos_az, los_az],
                mode="markers+text",
                marker=dict(size=10, color="gray"),
                text=["AOS", "LOS"],
                textposition="middle left",
                hovertemplate="<b>%{text}</b>"
                + "<br><b>az</b>: %{theta}"
                + "<br><b>el</b>: %{r}"
                + "<extra></extra>",
            )
        )
        fig.update_layout(
            annotations=[
                go.layout.Annotation(
                    text=text_str,
                    align="left",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=1.0,
                    y=1.05,
                    bordercolor="black",
                    borderwidth=1,
                    borderpad=4,
                    bgcolor="white",
                    opacity=0.8,
                )
            ],
            margin=dict(l=40, r=40, t=40, b=40),
        )
    fig.add_trace(
        go.Scatterpolar(
            r=[el],
            theta=[az],
            mode="markers",
            marker=dict(size=10, color="red"),
            customdata=customdata,
            hovertemplate="<b>%{customdata[0]}</b>"
            + "<br>%{customdata[1]}"
            + "<br><b>az</b>: %{theta}"
            + "<br><b>el</b>: %{r}"
            + "<extra></extra>",
        )
    )


# initialize the dataframe
df = create_dataframe(data)

styles = {
    "pre": {
        "border": "thin lightgrey solid",
        "overflowX": "scroll",
        "overflowY": "scroll",
        # "height": "400px",
    }
}

datatable_columns = [
    {"id": "Satellite", "name": "Satellite"},
    {"id": "name", "name": "Name"},
    {"id": "norad_id", "name": "NORAD ID", "type": "numeric"},
    {"id": "az", "name": "AZ (deg)", "type": "numeric", "format": {"specifier": ".6f"}},
    {"id": "el", "name": "EL (deg)", "type": "numeric", "format": {"specifier": ".6f"}},
    {"id": "az_rate", "name": "AZ Rate (deg/s)", "type": "numeric", "format": {"specifier": ".6f"}},
    {"id": "el_rate", "name": "EL Rate (deg/s)", "type": "numeric", "format": {"specifier": ".6f"}},
    {"id": "range", "name": "Range (km)", "type": "numeric", "format": {"specifier": ".6f"}},
    {
        "id": "rel_vel",
        "name": "Range Rate (km/s)",
        "type": "numeric",
        "format": {"specifier": ".6f"},
    },
    {"id": "aos", "name": "AOS", "type": "text"},
    {"id": "tca", "name": "TCA", "type": "text"},
    {"id": "los", "name": "LOS", "type": "text"},
]


# loads the "sketchy" template and sets it as the default
# load_figure_template("darkly")
app = Dash(external_stylesheets=[dbc.themes.LUX])
# app = Dash(external_stylesheets=[dbc.themes.GRID])


app.layout = dbc.Container(
    [
        dbc.Row(
            html.H1("Space Object Tracker", style={"textAlign": "center"}),
            align="end",
            className="p-2",
        ),
        dbc.Row(
            dcc.Graph(
                id="graph",
                config={"displayModeBar": False, "displaylogo": False},
            ),
            justify="center",
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Pre(id="json_output", style={**styles["pre"], "height": "35vh"}),
                    width=6,
                    align="center",
                ),
                dbc.Col(
                    dcc.Graph(
                        id="polar-graph",
                        config={"displayModeBar": False, "displaylogo": False},
                        style={"height": "40vh"},
                    ),
                    width=6,
                    align="start",
                ),
            ],
            # className="g-0",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dash_table.DataTable(
                            id="table",
                            columns=datatable_columns,
                            data=df.to_dict("records"),
                            row_selectable="single",
                            cell_selectable=False,
                            filter_options={"case": "insensitive"},
                            filter_action="native",
                            sort_action="native",
                            sort_mode="multi",
                            style_table={"width": "100%", "maxWidth": "100%"},
                            style_cell={
                                "height": "auto",  # set height of the cell
                                "minWidth": "0",  # minimum width of the cell
                                "maxWidth": "100%",  # maximum width of the cell
                                "whiteSpace": "normal",  # tell the text to wrap inside the cell
                                "textAlign": "center",
                                "font_size": "10px",  # adjust the font size
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "rgb(248, 248, 248)",
                                },
                            ],
                        )
                    ],
                    # className="dbc dbc-row-selectable",
                    width=12,
                ),
            ],
            justify="start",
        ),
        dcc.Interval(
            id="interval-component",
            interval=5 * 1000,  # in milliseconds (5000ms = 5s)
            n_intervals=0,
        ),
        dcc.Store(id="df-store", data=df.to_dict("records")),
        dcc.Store(id="root-sat-db-store", data=root_sat_db),
        dcc.Store(id="orbits-store", data=orbits),
    ],
    # fluid=True,
    # className="dbc dbc-row-selectable",
)


@app.callback(
    Output("df-store", "data"),
    Output("orbits-store", "data"),
    [Input("interval-component", "n_intervals")],
)
def update_data(n):
    """Update and store observational params by calling tracker API."""
    # propagate TLEs forward, computing observational params
    so_tracker.update_all_observational_params()
    data = so_tracker.get_all_obs_params()
    orbits = so_tracker.orbits
    df = create_dataframe(data)
    return df.to_dict("records"), so_tracker.orbits


@app.callback(
    Output("table", "selected_rows"),
    # Output("table", "derived_virtual_selected_rows"),
    Output("table", "data"),
    Output("graph", "figure"),
    Output("table", "style_data_conditional"),
    [
        Input("table", "selected_rows"),
        Input("table", "derived_virtual_selected_rows"),
        Input("graph", "clickData"),
        Input("interval-component", "n_intervals"),
    ],
    [State("df-store", "data")],
)
def update_point_or_row_selection(
    selected_rows, derived_selected_rows, clickData, n_intervals, data
):
    """
    Plot and tabulate observational params, allowing selection of data point to
    highlight corresponding table row and vice versa.
    """
    ctx = callback_context

    # re-compute the dataframe from the df-store
    df = pd.DataFrame(data)

    # form new figure based on updated dataframe
    fig = go.Figure(
        data=go.Scatter(
            x=df["az"],
            y=df["el"],
            mode="markers",
            marker=dict(size=10, color="rgba(0, 0, 0, 1)"),
            hovertemplate="<b>%{customdata[0]}</b>"
            + "<br>%{customdata[1]}"
            + "<br><b>az</b>: %{x}"
            + "<br><b>el</b>: %{y}"
            + "<extra></extra>",
            text=df["Satellite"],
            customdata=df[["name", "norad_id"]].values,
        ),
        # template="darkly",
    )
    fig.update_layout(
        xaxis_range=[-5, 365],
        yaxis_range=[-100, 100],
        xaxis_title="Azimuth",
        yaxis_title="Elevation",
        hovermode="closest",
        margin=dict(l=20, r=20, t=20, b=20),
    )

    # for all callback triggers, we will update the table and graph with new dataframe

    # initialization call
    if not ctx.triggered:
        return no_update, df.to_dict("records"), fig, no_update

    # choose action based on input id
    input_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if input_id == "interval-component":
        if selected_rows:
            selected_id = df.iloc[selected_rows[0]]["Satellite"]
            # update figure
            fig["data"][0]["marker"]["color"] = [
                "rgba(217, 0, 0, 1)" if id == selected_id else "rgba(0, 0, 0, 0.5)"
                for id in df["Satellite"]
            ]

            # update table selected rows based on clickData
            selected_row_index = df[df["Satellite"] == selected_id].index[0]

            # account for table filtering by providing derived row
            selected_rows_rel = selected_rows
            if selected_rows != derived_selected_rows:
                selected_rows_rel = derived_selected_rows

            # update row selection color
            tbl_style_data = [
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "rgb(248, 248, 248)",
                },
                {
                    "if": {"row_index": selected_rows_rel},
                    "backgroundColor": SELECTED_ROW_COLOR,
                    "fontWeight": "bold",
                    # "color": "blac",
                },
            ]
            return [selected_row_index], df.to_dict("records"), fig, tbl_style_data

        return no_update, df.to_dict("records"), fig, no_update

    elif input_id == "table":
        if selected_rows:
            selected_id = df.iloc[selected_rows[0]]["Satellite"]
            # update figure
            fig["data"][0]["marker"]["color"] = [
                "rgba(217, 0, 0, 1)" if id == selected_id else "rgba(0, 0, 0, 0.5)"
                for id in df["Satellite"]
            ]

            # update table selected rows based on clickData
            selected_row_index = df[df["Satellite"] == selected_id].index[0]

            # account for table filtering by providing derived row
            selected_rows_rel = selected_rows
            if selected_rows != derived_selected_rows:
                selected_rows_rel = derived_selected_rows

            # update row selection color
            tbl_style_data = [
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "rgb(248, 248, 248)",
                },
                {
                    "if": {"row_index": selected_rows_rel},
                    "backgroundColor": SELECTED_ROW_COLOR,
                    "fontWeight": "bold",
                    # "color": "white",
                },
            ]
            return [selected_row_index], df.to_dict("records"), fig, tbl_style_data
        return no_update, df.to_dict("records"), fig, no_update

    elif input_id == "graph":
        if clickData is None:
            raise PreventUpdate
        else:
            selected_id = clickData["points"][0]["text"]
            # update figure
            fig["data"][0]["marker"]["color"] = [
                "rgba(217, 0, 0, 1)" if id == selected_id else "rgba(0, 0, 0, 0.5)"
                for id in df["Satellite"]
            ]
            # update table selected rows based on clickData
            selected_row_index = df[df["Satellite"] == selected_id].index[0]

            # account for table filtering by providing derived row
            selected_rows_rel = selected_row_index
            if selected_row_index != derived_selected_rows:
                selected_rows_rel = derived_selected_rows

            # update row selection color
            tbl_style_data = [
                {
                    "if": {"row_index": "odd"},
                    "backgroundColor": "rgb(248, 248, 248)",
                },
                {
                    "if": {"row_index": selected_rows_rel},
                    "backgroundColor": SELECTED_ROW_COLOR,
                    "fontWeight": "bold",
                    # "color": "white",
                },
            ]
            return [selected_row_index], df.to_dict("records"), fig, tbl_style_data


@app.callback(
    Output("polar-graph", "figure"),
    [
        Input("table", "selected_rows"),
        Input("graph", "clickData"),
        Input("interval-component", "n_intervals"),
    ],
    [State("df-store", "data")],
    [State("orbits-store", "data")],
)
def update_polar_plot(selected_rows, clickData, n_intervals, data, orbits):
    # re-compute the dataframe from the df-store
    df = pd.DataFrame(data)

    ctx = callback_context
    r, theta = [], []

    fig = go.Figure(
        data=go.Scatterpolar(
            r=r,
            theta=theta,
            mode="markers",
            marker=dict(size=10, color="red"),
            customdata=["hello", "world"],
            hovertemplate="<b>%{customdata[0]}</b>"
            + "<br>%{customdata[1]}"
            + "<br><b>az</b>: %{theta}"
            + "<br><b>el</b>: %{r}"
            + "<extra></extra>",
        )
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[90, 0]),
            angularaxis=dict(
                visible=True,
                rotation=90,
                direction="clockwise",
                period=360,
            ),
        ),
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40),
    )

    # initialization call
    if not ctx.triggered:
        fig.add_trace(
            go.Scatterpolar(r=r, theta=theta, mode="markers", marker=dict(size=10, color="red"))
        )
        return fig

    # choose action based on input id
    input_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if input_id == "interval-component":
        if selected_rows is not None:
            selected_id = df.iloc[selected_rows[0]]["Satellite"]
            orbit = orbits[selected_id]
            az = df.iloc[selected_rows[0]]["az"].item()
            el = df.iloc[selected_rows[0]]["el"].item()
            # print(az, el)
            customdata = df.iloc[[selected_rows[0]]][["name", "norad_id"]].values
            render_polar_graph(fig, orbit, az, el, customdata)
            return fig

    elif input_id == "table":
        if selected_rows is None:
            raise PreventUpdate
        else:
            selected_id = df.iloc[selected_rows[0]]["Satellite"]
            orbit = orbits[selected_id]
            az = df.iloc[selected_rows[0]]["az"].item()
            el = df.iloc[selected_rows[0]]["el"].item()
            customdata = df.iloc[[selected_rows[0]]][["name", "norad_id"]].values
            # customdata = (selected_df[["name", "norad_id"]].values,)
            render_polar_graph(fig, orbit, az, el, customdata)
            return fig

    elif input_id == "graph":
        if clickData is None:
            raise PreventUpdate
        else:
            selected_id = clickData["points"][0]["text"]
            selected_df = df[df["Satellite"] == selected_id]
            orbit = orbits[selected_id]
            az = selected_df["az"].item()
            el = selected_df["el"].item()
            customdata = selected_df[["name", "norad_id"]].values
            render_polar_graph(fig, orbit, az, el, customdata)
            return fig

    else:
        return no_update


@app.callback(
    Output("json_output", "children"),
    [Input("table", "selected_rows"), Input("graph", "clickData")],
    [State("df-store", "data"), State("root-sat-db-store", "data")],
)
def display_selection_as_json(selected_rows, clickData, data, root_sat_db):
    default_return = "{Select a space object to see properties}"

    ctx = callback_context
    # initialization call
    if not ctx.triggered:
        return default_return

    # choose action based on input id
    input_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # re-compute the dataframe from the df-store
    df = pd.DataFrame(data)

    if input_id == "table":
        if selected_rows is None:
            raise PreventUpdate
        else:
            selected_id = df.iloc[selected_rows[0]]["Satellite"]
            properties = root_sat_db[selected_id]
            return json.dumps(properties, indent=2)

    elif input_id == "graph":
        if clickData is None:
            raise PreventUpdate
        else:
            selected_id = clickData["points"][0]["text"]
            properties = root_sat_db[selected_id]
            return json.dumps(properties, indent=2)

    else:
        return no_update


if __name__ == "__main__":
    app.run_server(debug=True)
