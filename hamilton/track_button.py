from dash import Dash, Input, Output, State, callback_context, dash_table, dcc, html, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


card_content = [
    dbc.Button("Track", id="track-button", n_clicks=0),
    html.Hr(),
    html.P(id="az-text"),
    html.P(id="el-text"),
]

app.layout = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(card_content, body=True, style={"max-width": "300px"}),
                    width={"size": 2, "offset": 5},
                )
            ]
        ),
        dcc.Interval(
            id='interval-component',
            interval=1*1000,  # in milliseconds
            n_intervals=0
        )
    ]
)
@app.callback(
    Output("track-button", "style"),
    Output("interval-component", "max_intervals"),
    Input("track-button", "n_clicks"),
)
def toggle_tracking(n_clicks):
    if n_clicks % 2 == 1:  # The button has been clicked an odd number of times
        button_style = {"opacity": 0.5}
        max_intervals = -1  # allow interval to continue indefinitely
    else:  # The button has been clicked zero or an even number of times
        button_style = {"opacity": 1.0}
        max_intervals = 0  # stop the interval
    return button_style, max_intervals

@app.callback(
    Output('az-text', 'children'),
    Output('el-text', 'children'),
    Input('interval-component', 'n_intervals'),
    Input('track-button', 'n_clicks'),
    #State('az-text', 'children'),
    #State('el-text', 'children'),
)
def update_metrics(n, n_clicks):
    ctx = callback_context
    # initialization call
    az, el = 0, 0
    print(f"update_metrics_entered: {n}")
    if not ctx.triggered:
        az = "AZ: <none>"
        el = "EL: <none>"
        return az, el
    #if ctx.triggered[0]['prop_id'] == 'track-button.n_clicks':
    #    if n_clicks % 2 == 1:  # The button has been clicked an odd number of times
    #        az = "AZ: 12.45"  # or any logic you want to implement
    #        el = "EL: 123.238"
    #    else:  # The button has been clicked zero or an even number of times
    #        az = "AZ: <none>"
    #        el = "EL: <none>"
    elif ctx.triggered[0]['prop_id'] == 'interval-component.n_intervals':
        if n_clicks % 2 == 1:  # The button has been clicked an odd number of times
            az = f'AZ: {n}'  # update value
            # implement your logic here to update 'el'
    else:
        raise PreventUpdate
    return az, el

if __name__ == "__main__":
    app.run_server(debug=True)