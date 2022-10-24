import pandas as pd
import numpy as np
import requests
import bs4 as bs

from dash import Dash, html, dcc, Input, Output, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import *

leagues = ["Premier-League", "La-Liga", "Ligue-1", "Bundesliga", "Serie-A"]
league_ids = {"Premier-League": "9", "La-Liga": "12", "Ligue-1": "13", "Bundesliga": "20", "Serie-A": "11"}
seasons = ["20"+str(i)+"-20"+str(i+1) for i in range(17, 23)]

team_urls = {}

for l in leagues:
    r = requests.get("https://fbref.com/en/comps/"+league_ids[l]+"/"+l+"-Stats")
    soup = bs.BeautifulSoup(r.text, "html.parser")
    team_urls[l] = {p.find_all("a", href=True)[0].get_text(): "https://fbref.com/"+p.find_all("a", href=True)[0]['href'] for p in soup.find_all("td", {"class": "left", "data-stat": "team"})}

init_league = "Premier-League"

app = Dash(external_stylesheets=[dbc.themes.VAPOR])
server = app.server

@app.callback(
    [Output('teams', 'options'),
    Output('teams', 'value')],
    Input('leagues', 'value')
)
def update_teams(league):
    opts = [{'label': t, 'value':team_urls[league][t]} for t in team_urls[league]]
    return opts, ""

@app.callback(
    [Output('memory', 'data'),
    Output('comps', 'options'),
    Output('comps', 'value'),
    Output('loader', 'children')],
    Input('teams', 'value'),
)
def get_games(url):
    if url == "":
        return pd.DataFrame().to_dict(), [], [], ""
    dfs = [None for s in seasons]
    for i, s in enumerate(seasons):
        u = url.split("/")
        tmp_df = pd.read_html('/'.join(u[:-1]+[s]+u[-1:]))[1]
        tmp_df['Season'] = s
        dfs[i] = tmp_df
    df = pd.concat(dfs, axis=0, ignore_index=True)
    xg_df = df[~df.xG.isna()]
    comps = xg_df.Comp.unique()
    return xg_df.to_dict(), comps, comps, ""

@app.callback(
    Output('output', 'children'),
    [Input("memory", "data"),
    Input('comps', 'value'),
    Input('checklist-season', 'value'),
    Input('checklist-window', 'value')],
)
def create_figs(data, comp, selected_seasons, window):
    xg_df = pd.DataFrame.from_dict(data)
    if xg_df.empty:
        return {}, {}
    xg_df = xg_df[(xg_df.Comp.isin(comp)) & (xg_df.Season.isin(selected_seasons))]
    if xg_df.empty:
        return {}, {}
    xg_df["xG-rolling-avg"] = xg_df.xG.rolling(window, center=False).mean()
    xg_df["xGA-rolling-avg"] = xg_df.xGA.rolling(window, center=False).mean()
    xg_df["Month"] = xg_df["Date"].apply(lambda x: x[:7])
    layout = Layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    fig2 = px.line(xg_df, x=xg_df.index, y=["xG-rolling-avg", "xGA-rolling-avg"])
    fig2.update_traces(mode="markers+lines", hoverinfo="y", hovertemplate=None, hoverlabel={"bgcolor": "black"})
    fig2.update_layout(hovermode="x unified", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
     legend=dict(font=dict(size=15)), xaxis_title="Time", yaxis_title="Value")#, font_color="white")
    ticks = xg_df.reset_index().groupby("Month").first()
    fig2.update_xaxes(tickvals=ticks['index'], ticktext=ticks.index, showgrid=False, showline=True)
    fig2.update_yaxes(showgrid=False, showline=True)
    return dcc.Graph(figure=fig2, config={'displayModeBar': False})

dropdown_style = {"color": "black"}

app.layout = html.Div(children=[
        dcc.Store(id='memory'),
        html.Div(children=[html.H1("xG/xGA-moving averages")]),
        dbc.Row(
            [
                dbc.Col(html.H3("Select League:")),
                dbc.Col(html.H3("Select Team:")),
                dbc.Col(html.H3("Select Competitions:"))
            ]
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Dropdown(leagues, init_league, id="leagues", clearable=False, style=dropdown_style)),
                dbc.Col(dcc.Dropdown(id="teams", clearable=False, style=dropdown_style)),
                dbc.Col(dcc.Dropdown(id="comps", multi=True, clearable=False, style=dropdown_style))
            ]
        ),
        html.Div([
            dbc.Label("Seasons:"),
            dbc.Checklist(
                options=[{"label": s,"value": s} for s in seasons],
                value=seasons[-3:],
                id="checklist-season",
                inline=True
            ),
        ]),
        html.Div([
            dbc.Label("Window size for rolling average:"),
            dbc.RadioItems(
                options=[{"label": s, "value": s} for s in [5, 10, 15]],
                value=10,
                id="checklist-window",
                inline=True
            ),
        ]),
        dcc.Loading(html.Div([html.Div(id='loader', hidden=True), html.Div(id="output")])
    ),
], style={"margin": "5%"})

debug=False
if __name__ == '__main__':
    app.run_server(debug=debug)