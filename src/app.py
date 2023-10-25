from MetaTrader5 import *
from datetime import datetime
import pandas as pd
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import dash_auth
import warnings
from dash_table import DataTable
warnings.filterwarnings('ignore')


# Inicializar a conexão com o MetaTrader 5
if not initialize():
    print("Falha na inicialização do MetaTrader 5")
    shutdown()

# Autenticação
VALID_USERNAME_PASSWORD_PAIRS = {'Mar_Rog_Lima': 'Mar_Rog*9001#'}
app = dash.Dash(__name__)
server = app.server
auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIRS)


# Definir o layout da aplicação Dash
app.layout = html.Div([

    # Barra lateral
    html.Div([
        # Título acima dos filtros
        html.H1('Análise Estatística Financeira', style={'margin-bottom': '20px'}),
        dcc.Dropdown(
            id='selected-asset',
            options=[
                {'label': 'WIN$N', 'value': 'WIN$N'},
                {'label': 'WDO@N', 'value': 'WDO@N'}
            ],
            value='WIN$N',
            style={'margin-bottom': '20px'}
        ),
        dcc.Dropdown(
            id='selected-timeframe',
            options=[
                {'label': 'M1', 'value': TIMEFRAME_M1},
                {'label': 'M5', 'value': TIMEFRAME_M5},
                {'label': 'M15', 'value': TIMEFRAME_M15},
                {'label': 'M30', 'value': TIMEFRAME_M30},
                {'label': 'H1', 'value': TIMEFRAME_H1},
                {'label': 'H4', 'value': TIMEFRAME_H4},
                {'label': '1D', 'value': TIMEFRAME_D1}
            ],
            value=TIMEFRAME_M1,
            style={'margin-bottom': '20px'}
        ),
    ], style={'position': 'fixed', 'top': 0, 'bottom': 0, 'left': 0, 'width': '20%', 'padding': '20px', 'background-color': '#f4f4f4'}),
    
    # Conteúdo principal
    html.Div([
        html.Div(id='graph-container', style={'height': '85vh'}),
        html.Div(style={'padding-top': '10px'}),  # Espaço de 10 pixels
        html.Div(id='table-container'),
        dcc.Interval(
            id='interval-update',
            interval=0.1*1000,  # em milissegundos
            n_intervals=0
        ),
    ], style={'margin-left': '23%','margin-right': '0.12%', 'height': '100%'}),
])

def cor_candle_elefante(dados, fator_engulfing=1.5):
    elefantes = []
    for i in range(1, len(dados)):
        o_atual = dados['open'][i]
        c_atual = dados['close'][i]
        h_atual = dados['high'][i]
        l_atual = dados['low'][i]
        o_anterior = dados['open'][i - 1]
        c_anterior = dados['close'][i - 1]
        corpo_atual = abs(c_atual - o_atual)
        pavio_total_atual = h_atual - l_atual
        corpo_anterior = abs(c_anterior - o_anterior)
        direcao_atual = 'alta' if c_atual > o_atual else 'baixa'
        direcao_anterior = 'alta' if c_anterior > o_anterior else 'baixa'
        if direcao_atual != direcao_anterior and corpo_atual > corpo_anterior * fator_engulfing and corpo_atual >= 0.70 * pavio_total_atual:
            elefantes.append(dados['time'][i])
    return elefantes

def identificar_sinais_compra_venda(dados):
    compras = []
    vendas = []
    direcao_tendencia = []
    elefantes = cor_candle_elefante(dados)
    topo_do_dia = dados.groupby(dados['time'].dt.date)['high'].transform('max')
    fundo_do_dia = dados.groupby(dados['time'].dt.date)['low'].transform('min')
    dados['SMA200'] = dados['close'].rolling(window=200).mean()
    for elefante in elefantes:
        candle = dados.loc[dados['time'] == elefante]
        if not candle.empty:
            sma200 = candle['SMA200'].values[0]
            close_price = candle['close'].values[0]
            tendencia = "Favor" if close_price > sma200 else "Contra"
            if abs(candle['low'].values[0] - fundo_do_dia.loc[candle.index].values[0]) <= 0.001 * fundo_do_dia.loc[candle.index].values[0]:
                compras.append(elefante)
                direcao_tendencia.append({'Sinal': 'Compra', 'Tendencia': tendencia})
            elif abs(candle['high'].values[0] - topo_do_dia.loc[candle.index].values[0]) <= 0.001 * topo_do_dia.loc[candle.index].values[0]:
                vendas.append(elefante)
                direcao_tendencia.append({'Sinal': 'Venda', 'Tendencia': tendencia})
    return compras, vendas, direcao_tendencia   

@app.callback(
    Output('graph-container', 'children'),
    [Input('selected-asset', 'value'),
     Input('selected-timeframe', 'value'),
     Input('interval-update', 'n_intervals')]
)
def update_graph(selected_asset, selected_timeframe, n):
    rates = copy_rates_from(selected_asset, selected_timeframe, datetime.now(), 150)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    compras, vendas, direcao_tendencia = identificar_sinais_compra_venda(df)
    data_compra = [{'Sinal': 'Compra', 'Data e Hora': c, 'Close': df.loc[df['time'] == c, 'close'].iloc[0], 'Tendencia': d['Tendencia']} for c, d in zip(compras, direcao_tendencia) if d['Sinal'] == 'Compra']
    data_venda = [{'Sinal': 'Venda', 'Data e Hora': v, 'Close': df.loc[df['time'] == v, 'close'].iloc[0], 'Tendencia': d['Tendencia']} for v, d in zip(vendas, direcao_tendencia) if d['Sinal'] == 'Venda']
    data_tabela = data_compra + data_venda

    tabela_sinais = DataTable(
        id='table',
        columns=[
            {'name': 'Sinal', 'id': 'Sinal'},
            {'name': 'Data e Hora', 'id': 'Data e Hora'},
            {'name': 'Close', 'id': 'Close'},
            {'name': 'Tendência', 'id': 'Tendencia'}
        ],
        data=data_tabela,
        page_size=10,
        style_table={'overflowX': 'scroll'}
    )

    # Criar um trace para os sinais de compra e venda
    trace_compras = go.Scatter(
        x=compras,
        y=[df.loc[df['time'] == c, 'low'].iloc[0] for c in compras],
        mode='markers',
        name='Compras',
        marker=dict(
            size=12,
            color='white',
            symbol='triangle-up'
        )
    )
    
    trace_vendas = go.Scatter(
        x=vendas,
        y=[df.loc[df['time'] == v, 'high'].iloc[0] for v in vendas],
        mode='markers',
        name='Vendas',
        marker=dict(
            size=12,
            color='white',
            symbol='triangle-down'

        )
    )


    # Identificar os candles elefantes
    elefantes = cor_candle_elefante(df)
    
    # Criar um trace para os candles elefantes
    trace_elefantes = go.Scatter(
        x=elefantes,
        y=[df.loc[df['time'] == e, 'high'].iloc[0] for e in elefantes],
        mode='markers',
        name='Elefantes',
        marker=dict(
            size=10,
            color='yellow',
            symbol='diamond'
        )
    )

    # Calcular as Médias Móveis Simples e a Média Móvel Exponencial
    df['SMA1'] = df['close'].rolling(window=10).mean()
    df['SMA2'] = df['close'].rolling(window=20).mean()
    df['EMA'] = df['close'].ewm(span=14, adjust=False).mean()
    
    # Adicionar as linhas para as Médias Móveis
    trace_sma1 = go.Scatter(
        x=df['time'],
        y=df['SMA1'],
        mode='lines',
        name='SMA-10',
        line=dict(color='orange')
    )

    trace_sma2 = go.Scatter(
        x=df['time'],
        y=df['SMA2'],
        mode='lines',
        name='SMA-20',
        line=dict(color='green')
    )

    trace_ema = go.Scatter(
        x=df['time'],
        y=df['EMA'],
        mode='lines',
        name='EMA-14',
        line=dict(color='purple')
    )
    
    # Definir o design de candlestick
    trace_candle = go.Candlestick(
        x = df['time'],
        open = df['open'],
        high = df['high'],
        low = df['low'],
        close = df['close'],
        name = 'Candlesticks',
        line=dict(width=1),
        opacity=1,
        increasing_fillcolor='#24A06B',
        decreasing_fillcolor="#CC2E3C",
        increasing_line_color='#2EC886',
        decreasing_line_color='#FF3A4C'
    )

    # Calcular topo e fundo do dia
    topo_do_dia = df.groupby(df['time'].dt.date)['high'].transform('max')
    fundo_do_dia = df.groupby(df['time'].dt.date)['low'].transform('min')
    
    # Adicionar as linhas horizontais para o topo e fundo do dia
    trace_topo_do_dia = go.Scatter(
        x=df['time'],
        y=topo_do_dia,
        mode='lines',
        name='Topo do Dia',
        line=dict(color='yellow')
    )

    trace_fundo_do_dia = go.Scatter(
        x=df['time'],
        y=fundo_do_dia,
        mode='lines',
        name='Fundo do Dia',
        line=dict(color='red')
    )

    
    # Criar o layout do Plotly
    layout = go.Layout(
    title=f"{selected_asset} Live Graph",
    xaxis=dict(
        gridcolor="#1f292f",
        rangeslider=dict(visible=False),
        rangebreaks=[
            dict(bounds=['sat', 'mon']),
            dict(bounds=[17, 9], pattern="hour")
        ],
        nticks=20,
        uirevision='no reset of zoom'  # Adicionado para manter o estado do zoom
    ),
    yaxis=dict(
        gridcolor="#1f292f",
        uirevision='no reset of zoom'  # Adicionado para manter o estado do zoom
    ),
    paper_bgcolor="#2c303c",
    plot_bgcolor="#2c303c",
    font=dict(size=10, color="#e1e1e1")
)
    
    # Recriar o gráfico de candlestick com o novo design e novos dados
    fig = go.Figure(data=[trace_candle, trace_compras, trace_vendas, trace_topo_do_dia, trace_fundo_do_dia, trace_sma1, trace_sma2, trace_ema, trace_elefantes], layout=layout)
    
    return [dcc.Graph(id=f'live-graph-{selected_asset}-{selected_timeframe}', figure=fig), tabela_sinais]

# Executar a aplicação
if __name__ == '__main__':
    app.run_server(debug=True)

# Desconectar do MetaTrader 5 ao finalizar
shutdown()
