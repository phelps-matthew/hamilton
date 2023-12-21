import plotly.graph_objects as go

# Replace these with your actual coordinates
azimuth = 180
elevation = 45

fig = go.Figure()

fig.add_trace(go.Scatterpolar(
    r = [elevation],
    theta = [azimuth],
    mode = 'markers',
    marker=dict(size=10, color='red')
))

# Configure the layout of the plot
fig.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[90, 0]
        ),
        angularaxis=dict(
            visible=True,
            rotation=90,  # starts from the North (top)
            direction="clockwise",  # direction of azimuth increase
            period=360  # full circle
        )
    ),
    showlegend=False
)

fig.show()
