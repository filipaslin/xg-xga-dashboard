import pandas as pd
import numpy as np
import requests
import bs4 as bs
import matplotlib.pyplot as plt

from dash import Dash, html, dcc, Input, Output, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import *

leagues = ["Premier-League", "La-Liga", "Ligue-1", "Bundesliga", "Serie-A", "Eredivisie", "Primeira-Liga", "Championship"]
league_ids = {"Premier-League": "9", "La-Liga": "12", "Ligue-1": "13", "Bundesliga": "20", "Serie-A": "11", 
            "Eredivisie": "23", "Primeira-Liga": "32", "Championship": "10"}
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
    Output('players', 'options'),
    Output('players', 'value'),
    Output('loader', 'children')],
    Input('teams', 'value'),
)
def get_games(url):
    if url == "":
        return pd.DataFrame().to_dict(), [], [], [], [], ""
    dfs = [None for s in seasons]
    for i, s in enumerate(seasons):
        u = url.split("/")
        response = requests.get('/'.join(u[:-1]+[s]+u[-1:]))
        soup = bs.BeautifulSoup(response.text, 'html.parser')
        tmp_df = pd.read_html(str(soup.find_all("div", {"id": "all_matchlogs"})[0]))[0]
        tmp_df['Season'] = s
        dfs[i] = tmp_df

    play_links = {p.find_all("a", href=True)[0].get_text(): "https://fbref.com/"+p.find_all("a", href=True)[-1]['href'] for p in soup.find("div", {"id": "all_stats_standard"}).find_all("tr") if len(p.find_all("a", href=True)) > 2}
    df = pd.concat(dfs, axis=0, ignore_index=True)
    xg_df = df[~df.xG.isna()]
    comps = xg_df.Comp.unique()
    players = sorted([{"label": p, "value": play_links[p]} for p in play_links], key=lambda d: d['label'])
    return xg_df.to_dict(), comps, comps, players, [], ""

@app.callback(
    [Output('players-memory', 'data'),
    Output('players-comps', 'options'),
    Output('players-comps', 'value'),
    Output('players-metrics', 'options'),
    Output('players-metrics', 'value'),
    Output('players-loader', 'children')],
    Input('players', 'value'),
)
def get_player_games(url):
    if (url == "") or (url == []) or (url == None):
        return pd.DataFrame().to_dict(), [], [], [], "", ""
    dfs = [None for s in seasons]
    for i, s in enumerate(seasons):
        try:
            u = url.split("/")
            tmp_df = pd.read_html('/'.join(u[:-3]+[s]+u[-2:]))[0]
            tmp_df['Season'] = s
            dfs[i] = tmp_df
        except:
            print("No data for the player was found for season", s)

    df = pd.concat(dfs, axis=0, ignore_index=True)
    df.columns = [c[0]+": "+c[1] if ("Unnamed" not in c[0]) else c[1] for c in df.columns]    
    df = df[[c for c in df.columns if (":" in c) or ("Comp" in c) or ("Date" in c)]]
    df = df[(~df.Comp.isna()) & (~df['Expected: xG'].isna())]
    df = df[df['Expected: xG'] != "On matchday squad, but did not play"]
    comps = df.Comp.unique()
    metrics = sorted([m for m in df.columns if m not in ["Season: ", "Comp", "Date"]])
    return df.to_dict(), comps, comps, metrics, ['Expected: xG'], ""

@app.callback(
    Output('output', 'children'),
    [Input('memory', 'data'),
    Input('comps', 'value'),
    Input('checklist-season', 'value'),
    Input('checklist-window', 'value')],
)
def create_team_fig(data, comp, selected_seasons, window):
    xg_df = pd.DataFrame.from_dict(data)
    if xg_df.empty:
        return {}
    xg_df = xg_df[(xg_df.Comp.isin(comp)) & (xg_df.Season.isin(selected_seasons))]
    if xg_df.empty:
        return {}
    xg_df["xG Rolling Average"] = xg_df.xG.rolling(window, center=False).mean()
    xg_df["xGA Rolling Average"] = xg_df.xGA.rolling(window, center=False).mean()
    xg_df["Month"] = xg_df["Date"].apply(lambda x: x[:7])
    layout = Layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    fig2 = px.line(xg_df, x=xg_df.index, y=["xG Rolling Average", "xGA Rolling Average"])
    fig2.update_traces(mode="markers+lines", hoverinfo="y", hovertemplate=None, hoverlabel={"bgcolor": "black"})
    fig2.update_layout(hovermode="x unified", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
     legend=dict(font=dict(size=15)), xaxis_title="Time", yaxis_title="Value")
    ticks = xg_df.reset_index().groupby("Month").first()
    fig2.update_xaxes(tickvals=ticks['index'], ticktext=ticks.index, showgrid=False, showline=True)
    fig2.update_yaxes(showgrid=False, showline=True)
    return dcc.Graph(figure=fig2, config={'displayModeBar': False})

@app.callback(
    Output('players-output', 'children'),
    [Input('players-memory', 'data'),
    Input('players-comps', 'value'),
    Input('players-metrics', 'value'),
    Input('players-checklist-season', 'value'),
    Input('players-checklist-window', 'value')],
)
def create_player_fig(data, comp, metrics, selected_seasons, window):
    xg_df = pd.DataFrame.from_dict(data)
    if (xg_df.empty) or (metrics == []) or (metrics == None):
        return {}
    xg_df = xg_df[(xg_df.Comp.isin(comp)) & (xg_df["Season: "].isin(selected_seasons))].reset_index()
    if xg_df.empty:
        return {}
    for metric in metrics:
        xg_df[metric+" Rolling Average"] = xg_df[metric].rolling(window, center=False).mean()
    xg_df["Month"] = xg_df["Date"].apply(lambda x: x[:7])
    layout = Layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    fig2 = px.line(xg_df, x=xg_df.index, y=[str(metric+" Rolling Average") for metric in metrics])
    fig2.update_traces(mode="markers+lines", hoverinfo="y", hovertemplate=None)
    fig2.update_layout(hovermode="x unified", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
     legend=dict(font=dict(size=15)), xaxis_title="Time", yaxis_title="Value")
    ticks = xg_df.reset_index().groupby("Month").first()
    fig2.update_xaxes(tickvals=ticks['level_0'], ticktext=ticks.index, showgrid=False, showline=True)
    fig2.update_yaxes(showgrid=False, showline=True)
    return dcc.Graph(figure=fig2, config={'displayModeBar': False})


dropdown_style = {"color": "black"}

app.layout = html.Div(children=[
        dcc.Store(id='memory'),
        dcc.Store(id='players-memory'),
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
            dbc.Label("Nr of Games to include in rolling average:"),
            dbc.RadioItems(
                options=[{"label": s, "value": s} for s in [5, 10, 15]],
                value=10,
                id="checklist-window",
                inline=True
            ),
        ]),
        dcc.Loading(html.Div([html.Div(id='loader', hidden=True), html.Div(id="output")])),
        html.Div(children=[html.H2("Player Metrics-moving averages")]),
        dbc.Row(
            [
                dbc.Col(html.H3("Select Player:")),
                dbc.Col(html.H3("Select Competitions:")),
                dbc.Col(html.H3("Select Metrics:")),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Dropdown(id="players", clearable=False, style=dropdown_style, placeholder="Select a Team to load players")),
                dbc.Col(dcc.Dropdown(id="players-comps", multi=True, clearable=False, style=dropdown_style)),
                dbc.Col(dcc.Dropdown(id="players-metrics", multi=True, clearable=False, style=dropdown_style))
            ]
        ),
        html.Div([
            dbc.Label("Seasons:"),
            dbc.Checklist(
                options=[{"label": s,"value": s} for s in seasons],
                value=seasons[-3:],
                id="players-checklist-season",
                inline=True
            ),
        ]),
        html.Div([
            dbc.Label("Nr of Games to include in rolling average:"),
            dbc.RadioItems(
                options=[{"label": s, "value": s} for s in [5, 10, 15]],
                value=10,
                id="players-checklist-window",
                inline=True
            ),
        ]),
        dcc.Loading(html.Div([html.Div(id='players-loader', hidden=True), html.Div(id="players-output")])),
], style={"margin": "5%"})

debug=False
app.run_server(debug=debug)