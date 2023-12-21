from dash import Dash, Input, Output, State, callback_context, dash_table, dcc, html, no_update
import pandas as pd
import dash_bootstrap_components as dbc

#df_final = pd.read_csv(
#    "http://mlr.cs.umass.edu/ml/machine-learning-databases/" "abalone/abalone.data"
#)
data = {
    "Satellite1": {"az": 70, "el": 30, "az-rate": 0.1, "el-rate": 0.1},
    "Satellite2": {"az": 50, "el": 20, "az-rate": 0.2, "el-rate": 0.2},
    "Satellite3": {"az": 30, "el": 40, "az-rate": 0.3, "el-rate": 0.3},
    "Satellite4": {"az": 20, "el": 50, "az-rate": 0.4, "el-rate": 0.4},
}


df_final = (
    pd.DataFrame.from_dict(data, orient="index")
    .reset_index()
    .rename(columns={"index": "Satellite"})
)
colnames = df_final.columns
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

t = dash_table.DataTable(
    id="modeling-table",
    columns=[{"name": i, "id": j} for i, j in zip(colnames, df_final.columns)],
    data=df_final.to_dict("records"),
    style_table={"maxHeight": "600px", "overflowY": "scroll"},
    sort_action="native",
    sort_mode="multi",
)

app.layout = html.Div(
    dbc.Row(
        [
            dbc.Col([html.H1("My Table"), html.Hr(), t], width=12, xl="auto"),
            dbc.Col(
                [html.H1("Other data"), html.Hr()],
                style={"border": "black 1px solid"},
            ),
        ]
    ),
    className="p-5",
)

if __name__ == "__main__":
    app.run_server(debug=True)
