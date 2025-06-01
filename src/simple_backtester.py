# src/simple_backtester.py
import pandas as pd
import numpy as np
from src import logger_setup
from src import config_manager
# from src import ai_analyzer # 暫時不直接依賴 AI Analyzer 獲取建議，在函數中接收建議列表

# 嘗試導入 yfinance，如果失敗則設置標誌
try:
    import yfinance as yf
    yfinance_available = True
    logger_temp = logger_setup.setup_logger() # 需要一個臨時 logger 實例來記錄導入成功
    logger_temp.info("成功導入 yfinance 套件 (用於 simple_backtester)。")
except ImportError:
    yfinance_available = False
    logger_temp = logger_setup.setup_logger()
    logger_temp.warning("警告：yfinance 套件未安裝或無法導入 (用於 simple_backtester)。")
    logger_temp.warning("回測器中獲取動態無風險利率和基準數據的功能將受限。")
    yf = None

# 獲取 logger
logger = logger_setup.setup_logger()

def get_risk_free_rate(start_date, end_date, symbol: str = None, fixed_rate_pct: float = None) -> pd.Series:
    """
    獲取無風險利率數據。
    優先使用 yfinance 從指定 symbol (例如 FRED 的國庫券代碼) 獲取。
    如果失敗或未提供 symbol，則使用固定的年化百分比利率。
    """
    if yfinance_available and symbol:
        try:
            # FRED 數據通常是以百分比形式提供的，例如 5.25 代表 5.25%
            # 我們需要日度數據，並轉換為日收益率 (例如 5.25 / 100 / 252)
            rf_data = yf.download(symbol, start=start_date, end=end_date, progress=False)['Adj Close']
            if rf_data.empty:
                logger.warning(f"從 yfinance 未能獲取到無風險利率數據 ({symbol})。")
            else:
                # 假設 FRED 的利率是年化百分比，轉換為日度小數
                daily_rf_rate = (rf_data / 100) / 252 # 假設一年252交易日
                logger.info(f"成功從 yfinance ({symbol}) 獲取並處理了無風險利率數據。平均年化: {(daily_rf_rate.mean()*252*100):.2f}%")
                return daily_rf_rate.reindex(pd.date_range(start=start_date, end=end_date), method='ffill')
        except Exception as e:
            logger.error(f"使用 yfinance ({symbol}) 獲取無風險利率數據時發生錯誤: {e}。將使用固定利率。", exc_info=True)

    # 如果 yfinance 失敗或未配置 symbol，則使用固定利率
    if fixed_rate_pct is None:
        fixed_rate_pct = config_manager.get_setting('backtester_settings', 'risk_free_rate_fixed_pct', 0.02) * 100 # 轉為百分比

    logger.warning(f"無法從 yfinance 獲取無風險利率，將使用固定的年化無風險利率: {fixed_rate_pct:.2f}%")
    daily_fixed_rf = (fixed_rate_pct / 100) / 252
    return pd.Series(daily_fixed_rf, index=pd.date_range(start=start_date, end=end_date))


def run_simple_backtest(symbol: str, historical_data_df: pd.DataFrame, ai_suggestions: list = None) -> dict:
    """
    對單一股票執行基於 AI (或模擬) 建議的簡單回測。

    參數:
        symbol (str): 股票代碼。
        historical_data_df (pd.DataFrame): 包含 'Open', 'Close' (至少) 的歷史價格數據，索引為 DatetimeIndex。
        ai_suggestions (list, optional): AI 生成的交易建議列表。每個建議是一個字典，
                                         例如: {"date": "YYYY-MM-DD", "symbol": "XYZ", "action": "BUY"|"SELL"|"HOLD", "reason": "..."}。
                                         如果為 None 或空，則使用內部模擬建議。

    返回:
        dict: 包含回測績效指標和每日投資組合價值的字典。
    """
    logger.info(f"[{symbol}] 開始執行簡單回測...")

    if historical_data_df is None or historical_data_df.empty:
        logger.error(f"[{symbol}] 歷史數據為空，無法執行回測。")
        return {"error": "歷史數據為空"}

    # 確保索引是 DatetimeIndex
    if not isinstance(historical_data_df.index, pd.DatetimeIndex):
        try:
            historical_data_df.index = pd.to_datetime(historical_data_df.index)
        except Exception as e:
            logger.error(f"[{symbol}] 轉換索引為 DatetimeIndex 失敗: {e}。回測中止。")
            return {"error": "索引轉換失敗"}

    # 從 config 讀取回測設定
    initial_capital = config_manager.get_setting('backtester_settings', 'initial_capital', 100000.0)
    trading_costs_pct = config_manager.get_setting('backtester_settings', 'default_trading_costs_pct', 0.001)
    rf_symbol = config_manager.get_setting('backtester_settings', 'risk_free_rate_symbol') # 可能為 None
    fixed_rf_rate_pct_annual = config_manager.get_setting('backtester_settings', 'risk_free_rate_fixed_pct', 0.02) * 100 # 轉為百分比

    # 準備數據
    data = historical_data_df.copy()
    if 'Open' not in data.columns or 'Close' not in data.columns: # 回測至少需要開盤或收盤價執行交易
        logger.error(f"[{symbol}] 歷史數據缺少 'Open' 或 'Close' 欄位。")
        return {"error": "數據欄位缺失"}

    # 獲取無風險利率 (日度 Series)
    rf_rate_series = get_risk_free_rate(data.index.min(), data.index.max(), symbol=rf_symbol, fixed_rate_pct=fixed_rf_rate_pct_annual)


    # 模擬 AI 建議 (如果未提供)
    if not ai_suggestions:
        logger.warning(f"[{symbol}] 未提供 AI 建議，將使用內部模擬建議進行回測。")
        # 確保索引存在且長度足夠
        if len(data.index) < 40: # 需要足夠間隔
             logger.error(f"[{symbol}] 數據長度 ({len(data.index)}) 過短，無法生成有意義的模擬建議。")
             mock_buy_date = data.index[0].strftime('%Y-%m-%d')
             mock_sell_date = data.index[-1].strftime('%Y-%m-%d')
        else:
            mock_buy_date = data.index[int(len(data)*0.25)].strftime('%Y-%m-%d')
            mock_sell_date = data.index[int(len(data)*0.50)].strftime('%Y-%m-%d')

        ai_suggestions = [
            {"date": mock_buy_date, "symbol": symbol, "action": "BUY", "reason": "模擬買入點 (25%處)"},
            {"date": mock_sell_date, "symbol": symbol, "action": "SELL", "reason": "模擬賣出點 (50%處)"},
        ]
        if len(data.index) >= 40: # 只有數據夠長才加第三個交易
            ai_suggestions.append({"date": data.index[int(len(data)*0.75)].strftime('%Y-%m-%d'), "symbol": symbol, "action": "BUY", "reason": "模擬再次買入點 (75%處)"})


    # 初始化投資組合
    cash = initial_capital
    shares = 0
    portfolio_value = []
    trade_log = [] # 記錄交易詳情

    # 回測循環
    position = "OUT" # 當前市場部位: "OUT", "IN"

    for date, row in data.iterrows():
        # 檢查是否有當日交易建議 (且與當前 symbol 匹配)
        todays_action = "HOLD" # 預設行為
        suggestion_reason = "無建議"

        for sugg in ai_suggestions:
            if sugg['date'] == date.strftime('%Y-%m-%d') and sugg['symbol'] == symbol:
                todays_action = sugg['action'].upper()
                suggestion_reason = sugg.get('reason', 'N/A')
                break # 只處理當日第一個相關建議

        # 執行交易 (假設使用當日開盤價 Open 執行交易)
        # 實際中，可以用前一日收盤價決定，當日開盤價執行，或更複雜邏輯
        trade_price = row['Open'] # 使用開盤價交易
        if pd.isna(trade_price): # 如果開盤價缺失，嘗試用收盤價
            trade_price = row['Close']
            if pd.isna(trade_price):
                logger.warning(f"[{symbol}] 日期 {date.strftime('%Y-%m-%d')} 開盤價和收盤價均缺失，跳過當日交易決策。")
                current_value = cash + (shares * row['Close'] if not pd.isna(row['Close']) else (shares * data['Close'].ffill().loc[date] if shares > 0 else 0))
                portfolio_value.append(current_value if not pd.isna(current_value) else (portfolio_value[-1] if portfolio_value else initial_capital))
                continue


        if todays_action == "BUY" and position == "OUT":
            shares_to_buy = cash / trade_price
            cost = shares_to_buy * trade_price * (1 + trading_costs_pct)
            if cost <= cash :
                shares = shares_to_buy
                cash -= cost
                position = "IN"
                trade_log.append({"date": date, "action": "BUY", "price": trade_price, "shares": shares, "cost": cost, "reason": suggestion_reason})
                logger.info(f"[{symbol}] {date.strftime('%Y-%m-%d')}: 買入 {shares:.2f} 股 @ {trade_price:.2f}。原因: {suggestion_reason}")
            else:
                logger.warning(f"[{symbol}] {date.strftime('%Y-%m-%d')}: 資金不足以買入。需要 {cost:.2f}，現金 {cash:.2f}。")

        elif todays_action == "SELL" and position == "IN":
            proceeds = shares * trade_price * (1 - trading_costs_pct)
            cash += proceeds
            sold_shares = shares
            shares = 0
            position = "OUT"
            trade_log.append({"date": date, "action": "SELL", "price": trade_price, "shares": sold_shares, "proceeds": proceeds, "reason": suggestion_reason})
            logger.info(f"[{symbol}] {date.strftime('%Y-%m-%d')}: 賣出 {sold_shares:.2f} 股 @ {trade_price:.2f}。原因: {suggestion_reason}")

        # 計算當日投資組合價值 (基於當日收盤價)
        current_close = row['Close']
        if pd.isna(current_close) and shares > 0: # 如果收盤價缺失但仍持股
            # 嘗試用最近的有效收盤價估值，或用當日開盤價（如果交易發生）
             current_close = data['Close'].ffill().loc[date] if date in data['Close'].ffill().index else trade_price

        if pd.isna(current_close) and shares > 0: # 如果還是NaN
             current_value = portfolio_value[-1] if portfolio_value else initial_capital # 維持前一日價值
             logger.warning(f"[{symbol}] 日期 {date.strftime('%Y-%m-%d')} 收盤價缺失，持股價值估算可能不準。")
        else:
             current_value = cash + (shares * current_close)

        portfolio_value.append(current_value)

    # 計算績效指標
    portfolio_ts = pd.Series(portfolio_value, index=data.index)
    portfolio_daily_returns = portfolio_ts.pct_change().fillna(0)

    total_return = (portfolio_ts.iloc[-1] / initial_capital) - 1
    num_years = (data.index[-1] - data.index[0]).days / 365.25
    annualized_return = (1 + total_return) ** (1 / num_years) - 1 if num_years > 0 else total_return

    annualized_volatility = portfolio_daily_returns.std() * np.sqrt(252) # 假設252交易日

    # 最大回撤 (MDD)
    cumulative_returns = (1 + portfolio_daily_returns).cumprod()
    peak = cumulative_returns.expanding(min_periods=1).max()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown = drawdown.min()

    # 夏普比率
    # 確保 rf_rate_series 與 portfolio_daily_returns 的索引對齊
    aligned_rf_rate = rf_rate_series.reindex(portfolio_daily_returns.index).fillna(0)
    excess_returns = portfolio_daily_returns - aligned_rf_rate
    sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() != 0 else 0.0

    # 勝率與盈虧比 (基於已完成的交易)
    wins = 0
    losses = 0
    total_profit = 0
    total_loss = 0
    last_buy_price = None
    completed_trades = 0

    for i in range(len(trade_log)):
        trade = trade_log[i]
        if trade['action'] == 'BUY':
            last_buy_price = trade['price'] # 記錄買入價格以計算該筆交易的盈虧
        elif trade['action'] == 'SELL' and last_buy_price is not None:
            completed_trades +=1
            profit = (trade['price'] - last_buy_price) * trade['shares'] - (trade_log[i-1]['cost'] * trading_costs_pct + trade['proceeds'] * trading_costs_pct) # 簡化成本估算
            if profit > 0:
                wins += 1
                total_profit += profit
            else:
                losses += 1
                total_loss += abs(profit)
            last_buy_price = None # 重置，等待下一次買入

    win_rate = wins / completed_trades if completed_trades > 0 else 0.0
    avg_profit_per_win = total_profit / wins if wins > 0 else 0.0
    avg_loss_per_loss = total_loss / losses if losses > 0 else 0.0
    profit_loss_ratio = avg_profit_per_win / avg_loss_per_loss if avg_loss_per_loss > 0 else float('inf')


    results = {
        "初始資本": initial_capital,
        "最終總資產": portfolio_ts.iloc[-1],
        "總回報率 (%)": total_return * 100,
        "年化回報率 (%)": annualized_return * 100,
        "年化波動率 (%)": annualized_volatility * 100,
        "最大回撤 (MDD) (%)": max_drawdown * 100,
        "夏普比率": sharpe_ratio,
        "交易次數 (買/賣對)": completed_trades,
        "勝率 (%)": win_rate * 100,
        "平均每筆盈利 ($)": avg_profit_per_win,
        "平均每筆虧損 ($)": avg_loss_per_loss,
        "盈虧比": profit_loss_ratio,
        "每日投資組合價值序列": portfolio_ts
    }
    logger.info(f"[{symbol}] 回測完成。總回報率: {total_return*100:.2f}%")
    return results

if __name__ == '__main__':
    logger.info("--- Simple Backtester 內部測試 ---")
    # 創建模擬歷史數據
    days = 252 * 2 # 兩年數據
    dates_sim = pd.to_datetime(['2022-01-01'] * days) + pd.to_timedelta(range(days), unit='D')
    data_sim = {
        'Open': np.random.normal(loc=100, scale=2, size=days).cumsum() + 100, # 模擬股價有趨勢
        'Close': np.random.normal(loc=100, scale=2, size=days).cumsum() + 100,
        'Volume': np.random.randint(100000, 500000, size=days)
    }
    data_sim['Open'] = np.maximum(1, data_sim['Open']) # 避免價格為0或負
    data_sim['Close'] = np.maximum(1, data_sim['Close'])
    mock_hist_df = pd.DataFrame(data_sim, index=dates_sim)

    test_sym = "MOCKSIM"
    logger.info(f"[{test_sym}] 模擬歷史數據長度: {len(mock_hist_df)}")

    # 模擬 AI 建議 (使用內部預設的，因為這裡沒有 ai_analyzer)
    backtest_results = run_simple_backtest(test_sym, mock_hist_df, ai_suggestions=None)

    if "error" not in backtest_results:
        logger.info(f"[{test_sym}] 回測績效指標:")
        for key, value in backtest_results.items():
            if key != "每日投資組合價值序列":
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")
        # logger.info(f"  每日價值序列 (前5): \n{backtest_results['每日投資組合價值序列'].head()}")
    else:
        logger.error(f"[{test_sym}] 回測執行失敗: {backtest_results['error']}")

    logger.info("--- Simple Backtester 內部測試結束 ---")
