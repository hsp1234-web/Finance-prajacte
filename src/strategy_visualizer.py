# src/strategy_visualizer.py
import pandas as pd
from src import logger_setup

# 獲取 logger
logger = logger_setup.setup_logger()

# 嘗試導入 Plotly
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    plotly_available = True
    logger.info("成功導入 Plotly 套件。")
except ImportError:
    plotly_available = False
    logger.warning("警告：Plotly 套件未安裝或無法導入。")
    logger.warning("策略可視化功能將受限。請考慮安裝 'pip install plotly'")
    go = None
    make_subplots = None

def plot_ohlcv_with_indicators(df: pd.DataFrame, symbol: str, indicators_to_plot: list = None) -> go.Figure | None:
    """
    創建包含 K 線圖和指定技術指標的 Plotly 圖表。

    參數:
        df (pd.DataFrame): 包含 OHLCV 數據以及可能的指標數據的 DataFrame。
                           索引應為 DatetimeIndex。
        symbol (str): 股票代碼，用於圖表標題。
        indicators_to_plot (list, optional): 一個包含要在圖表上繪製的指標欄位名稱的列表。
                                             例如: ['SMA_20', 'SMA_50', 'RSI_14']。

    返回:
        plotly.graph_objects.Figure | None: 生成的 Plotly Figure 物件，如果 Plotly 不可用則返回 None。
    """
    if not plotly_available:
        logger.error("Plotly 套件不可用，無法創建圖表。")
        return None

    if df is None or df.empty:
        logger.warning(f"[{symbol}] 輸入的 DataFrame 為空，無法繪製圖表。")
        return None

    # 檢查必要的 OHLC 欄位是否存在
    ohlc_cols = ['Open', 'High', 'Low', 'Close'] # 假設欄位名是標準化的首字母大寫
    if not all(col in df.columns for col in ohlc_cols):
        logger.error(f"[{symbol}] DataFrame 缺少必要的 OHLC 欄位 ({', '.join(ohlc_cols)})。")
        return None

    # 處理指標繪製
    has_rsi = False
    rsi_col_name = None
    if indicators_to_plot:
        for indicator in indicators_to_plot:
            if "RSI" in indicator.upper() and indicator in df.columns:
                has_rsi = True
                rsi_col_name = indicator
                break # 假設只繪製第一個找到的RSI類型指標

    # 創建子圖佈局 (如果需要為 RSI 創建額外子圖)
    if has_rsi:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])
        main_chart_row, rsi_chart_row = 1, 2
    else:
        fig = make_subplots(rows=1, cols=1) # 只有主圖
        main_chart_row = 1

    # 1. 繪製 K 線圖
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df['Open'],
                                 high=df['High'],
                                 low=df['Low'],
                                 close=df['Close'],
                                 name=f"{symbol} K線"),
                  row=main_chart_row, col=1)

    # 2. 繪製疊加指標 (例如 SMA)
    if indicators_to_plot:
        for indicator in indicators_to_plot:
            if indicator in df.columns:
                if "SMA" in indicator.upper() or "EMA" in indicator.upper(): # 均線類
                    fig.add_trace(go.Scatter(x=df.index, y=df[indicator], mode='lines', name=indicator),
                                  row=main_chart_row, col=1)
                # 其他類型指標可以在此處添加邏輯，例如布林帶等

    # 3. 繪製 RSI (如果存在且需要)
    if has_rsi and rsi_col_name:
        fig.add_trace(go.Scatter(x=df.index, y=df[rsi_col_name], mode='lines', name=rsi_col_name),
                      row=rsi_chart_row, col=1)
        # 為 RSI 子圖添加水平線
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=rsi_chart_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=rsi_chart_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=rsi_chart_row, col=1)


    # 更新圖表佈局
    fig.update_layout(
        title=f"{symbol} K線圖與技術指標",
        xaxis_title="日期",
        yaxis_title="價格",
        xaxis_rangeslider_visible=False, # 主圖的範圍滑塊 (RSI圖不需要)
        legend_title_text="圖例",
        template="plotly_white", # 使用簡潔的白色主題
        font=dict(family="Noto Sans TC, Roboto, sans-serif") # 使用 custom.css 中定義的字體
    )

    if has_rsi:
        fig.update_layout(xaxis_rangeslider_visible=False, row=main_chart_row, col=1)


    logger.info(f"[{symbol}] 成功生成包含指標的 Plotly 圖表。")
    return fig

def plot_spread_series(): # 佔位符
    """(佔位符) 繪製價差序列圖。"""
    logger.warning("plot_spread_series 功能尚未實現。")
    if not plotly_available: return None
    # fig = go.Figure()
    # fig.update_layout(title_text="價差序列圖 (未實現)")
    # return fig
    return None

def plot_option_strategy_pnl(): # 佔位符
    """(佔位符) 繪製期權策略損益圖。"""
    logger.warning("plot_option_strategy_pnl 功能尚未實現。")
    if not plotly_available: return None
    # fig = go.Figure()
    # fig.update_layout(title_text="期權策略損益圖 (未實現)")
    # return fig
    return None

if __name__ == '__main__':
    logger.info("--- Strategy Visualizer 內部測試 ---")
    if not plotly_available:
        logger.error("Plotly 未安裝，無法執行 Strategy Visualizer 的內部測試。")
    else:
        # 創建一個模擬的 DataFrame
        days = 100
        np_data = {
            'Open': np.random.normal(loc=100, scale=2, size=days),
            'High': np.random.normal(loc=103, scale=2, size=days),
            'Low': np.random.normal(loc=98, scale=2, size=days),
            'Close': np.random.normal(loc=101, scale=2, size=days),
            'Volume': np.random.randint(100000, 500000, size=days)
        }
        # 確保 High 是最高的，Low 是最低的
        np_data['High'] = np.maximum(np_data['High'], np_data['Open'])
        np_data['High'] = np.maximum(np_data['High'], np_data['Close'])
        np_data['Low'] = np.minimum(np_data['Low'], np_data['Open'])
        np_data['Low'] = np.minimum(np_data['Low'], np_data['Close'])

        mock_dates = pd.to_datetime(['2023-01-01'] * days) + pd.to_timedelta(range(days), unit='D')
        mock_df_viz = pd.DataFrame(np_data, index=mock_dates)

        # 模擬指標
        mock_df_viz['SMA_20'] = mock_df_viz['Close'].rolling(window=20).mean()
        mock_df_viz['SMA_50'] = mock_df_viz['Close'].rolling(window=50).mean()
        # 模擬 RSI
        delta = mock_df_viz['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        mock_df_viz['RSI_14'] = 100 - (100 / (1 + rs))
        mock_df_viz['RSI_14'] = np.where(loss == 0, 100, mock_df_viz['RSI_14'])


        logger.info(f"內部測試：原始模擬數據 (前3行):\n{mock_df_viz.head(3)}")

        fig_ohlcv = plot_ohlcv_with_indicators(mock_df_viz, "MOCKVIS", indicators_to_plot=['SMA_20', 'SMA_50', 'RSI_14', 'NonExistentInd'])

        if fig_ohlcv:
            logger.info("內部測試：plot_ohlcv_with_indicators 已成功生成 Figure 物件。")
            # 在非交互式環境中，我們不調用 fig.show()
            # 可以考慮保存為 HTML 進行驗證 (如果檔案系統可寫)
            # try:
            #     fig_ohlcv.write_html("temp_mock_plot.html")
            #     logger.info("內部測試：圖表已保存到 temp_mock_plot.html")
            # except Exception as e:
            #     logger.error(f"內部測試：保存圖表到 HTML 失敗: {e}")
        else:
            logger.error("內部測試：plot_ohlcv_with_indicators未能生成 Figure 物件。")

    logger.info("--- Strategy Visualizer 內部測試結束 ---")
