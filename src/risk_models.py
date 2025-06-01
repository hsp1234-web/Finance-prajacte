# src/risk_models.py
import pandas as pd
import numpy as np
from src import logger_setup
from src import config_manager

# 獲取 logger 和 config
logger = logger_setup.setup_logger()
# config 不是直接在此處使用，而是在調用函數時傳入具體閾值，這些閾值由調用方 (如 stock_screener) 從 config_manager 獲取

# --- 基本面風險指標 (模擬) ---
def check_high_debt_to_equity_ratio(symbol: str, fundamental_data: dict = None) -> tuple[bool, str]:
    """
    (模擬) 檢查股票的股本負債比是否過高。
    實際應用中，fundamental_data 應包含從 API 或數據庫獲取的真實基本面數據。
    """
    logger.debug(f"[{symbol}] (模擬) 檢查高股本負債比。")
    # 模擬邏輯：始終返回低風險，因為沒有實際數據
    return False, f"[{symbol}] (模擬) 基本面資料未整合，此為模擬低股本負債比風險。"

def check_negative_earnings_trend(symbol: str, fundamental_data: dict = None) -> tuple[bool, str]:
    """
    (模擬) 檢查股票的盈利趨勢是否為負。
    """
    logger.debug(f"[{symbol}] (模擬) 檢查負盈利趨勢。")
    return False, f"[{symbol}] (模擬) 基本面資料未整合，此為模擬無負盈利趨勢風險。"

def check_low_profit_margins(symbol: str, fundamental_data: dict = None) -> tuple[bool, str]:
    """
    (模擬) 檢查股票的利潤率是否過低。
    """
    logger.debug(f"[{symbol}] (模擬) 檢查低利潤率。")
    return False, f"[{symbol}] (模擬) 基本面資料未整合，此為模擬正常利潤率。"

# --- 技術面風險指標 (基於已有數據) ---

def calculate_historical_volatility(df: pd.DataFrame, period: int = 20) -> float | None:
    """
    計算指定週期內收盤價的年化歷史波動率。

    參數:
        df (pd.DataFrame): 包含 'Close' 欄位的 DataFrame。
        period (int): 計算波動率的週期 (天)。

    返回:
        float | None: 年化波動率 (百分比表示，例如 30.5 代表 30.5%)。如果數據不足則返回 None。
    """
    if df is None or df.empty or 'Close' not in df.columns:
        logger.warning("計算歷史波動率所需的 'Close' 數據不足或無效。")
        return None
    if len(df) < period:
        logger.warning(f"數據點 ({len(df)}) 少於波動率計算週期 ({period})，無法計算。")
        return None

    # 計算日收益率的標準差，然後年化
    # 年化因子，通常假設一年有 252 個交易日
    annualization_factor = np.sqrt(252)
    try:
        # .pct_change() 在第一個元素會是 NaN
        # .std() 默認 skipna=True
        volatility = df['Close'].pct_change().rolling(window=period).std().iloc[-1] * annualization_factor
        return volatility * 100 # 以百分比形式返回
    except Exception as e:
        logger.error(f"計算歷史波動率時出錯: {e}", exc_info=True)
        return None

def check_high_historical_volatility(df: pd.DataFrame, symbol: str, period: int, threshold_pct: float) -> tuple[bool, str]:
    """
    檢查股票最近的歷史波動率是否高於閾值。

    參數:
        df (pd.DataFrame): 包含 'Close' 欄位的 DataFrame。
        symbol (str): 股票代碼。
        period (int): 計算波動率的週期。
        threshold_pct (float): 波動率閾值 (百分比，例如 50.0 代表 50%)。

    返回:
        tuple[bool, str]: (是否存在高波動率風險, 風險描述文字)
    """
    if df is None or df.empty or 'Close' not in df.columns :
        return False, f"[{symbol}] 數據不足，無法評估歷史波動率。"

    volatility = calculate_historical_volatility(df, period=period)
    if volatility is None:
        return False, f"[{symbol}] 無法計算歷史波動率。" # 不是風險，只是無法計算

    if volatility > threshold_pct:
        return True, f"[{symbol}] 歷史波動率偏高: {volatility:.2f}% (閾值: {threshold_pct:.1f}%)。"
    else:
        return False, f"[{symbol}] 歷史波動率正常: {volatility:.2f}% (閾值: {threshold_pct:.1f}%)。"

def check_major_downtrend(df: pd.DataFrame, symbol: str) -> tuple[bool, str]:
    """
    檢查股票是否處於主要下跌趨勢 (收盤價 < SMA200 且 SMA50 < SMA200)。

    參數:
        df (pd.DataFrame): 包含 'Close', 'SMA_50', 'SMA_200' 欄位的 DataFrame。
        symbol (str): 股票代碼。

    返回:
        tuple[bool, str]: (是否處於下跌趨勢, 描述文字)
    """
    required_cols = ['Close', 'SMA_50', 'SMA_200']
    if df is None or df.empty or not all(col in df.columns for col in required_cols):
        return False, f"[{symbol}] 缺少必要欄位 ({', '.join(required_cols)})，無法評估主要下跌趨勢。"

    # 確保有足夠的數據來獲取最後一行的值
    if len(df) < 1 or df[required_cols].iloc[-1].isnull().any():
        return False, f"[{symbol}] 最近一日的 SMA 數據不足，無法評估主要下跌趨勢。"

    last_close = df['Close'].iloc[-1]
    last_sma50 = df['SMA_50'].iloc[-1]
    last_sma200 = df['SMA_200'].iloc[-1]

    if pd.isna(last_close) or pd.isna(last_sma50) or pd.isna(last_sma200):
        return False, f"[{symbol}] 最近的收盤價或均線數據為 NaN，無法評估主要下跌趨勢。"

    if last_close < last_sma200 and last_sma50 < last_sma200:
        return True, f"[{symbol}] 處於主要下跌趨勢 (收盤價: {last_close:.2f} < SMA200: {last_sma200:.2f} 且 SMA50: {last_sma50:.2f} < SMA200)。"
    else:
        return False, f"[{symbol}] 未處於主要下跌趨勢。"

def check_relative_strength_weak(df: pd.DataFrame, symbol: str, rsi_threshold: int) -> tuple[bool, str]:
    """
    檢查股票的相對強度是否極弱 (RSI 低於閾值)。

    參數:
        df (pd.DataFrame): 包含 'RSI_14' 欄位的 DataFrame。
        symbol (str): 股票代碼。
        rsi_threshold (int): RSI 低閾值。

    返回:
        tuple[bool, str]: (RSI 是否極弱, 描述文字)
    """
    rsi_col = 'RSI_14' # 假設 RSI 欄位名稱固定
    if df is None or df.empty or rsi_col not in df.columns:
        return False, f"[{symbol}] 缺少 '{rsi_col}' 欄位，無法評估相對強度。"

    if len(df) < 1 or pd.isna(df[rsi_col].iloc[-1]):
        return False, f"[{symbol}] 最近一日的 RSI 數據不足，無法評估相對強度。"

    last_rsi = df[rsi_col].iloc[-1]
    if last_rsi < rsi_threshold:
        return True, f"[{symbol}] 相對強度指標過低 (RSI: {last_rsi:.2f} < {rsi_threshold})。"
    else:
        return False, f"[{symbol}] 相對強度指標正常 (RSI: {last_rsi:.2f} >= {rsi_threshold})。"

def check_breaking_support(df: pd.DataFrame, symbol: str) -> tuple[bool, str]:
    """
    (初步) 檢查股票是否跌破關鍵支撐 (例如 SMA200)。

    參數:
        df (pd.DataFrame): 包含 'Close', 'SMA_200' 欄位的 DataFrame。
        symbol (str): 股票代碼。

    返回:
        tuple[bool, str]: (是否跌破支撐, 描述文字)
    """
    required_cols = ['Close', 'SMA_200']
    if df is None or df.empty or not all(col in df.columns for col in required_cols):
        return False, f"[{symbol}] 缺少必要欄位 ({', '.join(required_cols)})，無法評估是否跌破支撐。"

    if len(df) < 1 or df[required_cols].iloc[-1].isnull().any():
        return False, f"[{symbol}] 最近一日的數據不足，無法評估是否跌破支撐。"

    last_close = df['Close'].iloc[-1]
    last_sma200 = df['SMA_200'].iloc[-1]

    if pd.isna(last_close) or pd.isna(last_sma200):
         return False, f"[{symbol}] 最近的收盤價或 SMA200 數據為 NaN，無法評估是否跌破支撐。"

    if last_close < last_sma200:
        return True, f"[{symbol}] 價格已跌破長期均線 SMA200 (收盤價: {last_close:.2f}, SMA200: {last_sma200:.2f})。"
    else:
        return False, f"[{symbol}] 價格位於長期均線 SMA200 之上或持平。"

# --- 其他未來可能實現的風險檢查函數 ---
# def check_liquidity_risk(symbol: str, avg_daily_volume: float, threshold: float) -> tuple[bool, str]: ...
# def check_market_sentiment_risk(general_market_index_trend: str) -> tuple[bool, str]: ...

if __name__ == '__main__':
    logger.info("--- Risk Models 內部測試 ---")
    # 創建一個模擬的 DataFrame
    sample_dates = pd.to_datetime(['2023-01-01'] * 50) + pd.to_timedelta(range(50), unit='D')
    data = {
        'Open': np.random.rand(50) * 10 + 100,
        'High': np.random.rand(50) * 10 + 105,
        'Low': np.random.rand(50) * 5 + 95,
        'Close': np.random.rand(50) * 10 + 100,
        'Volume': np.random.randint(10000, 100000, 50)
    }
    mock_df = pd.DataFrame(data, index=sample_dates)

    # 模擬指標計算 (通常由 indicator_engine 完成)
    mock_df['SMA_50'] = mock_df['Close'].rolling(window=50, min_periods=1).mean()
    mock_df['SMA_200'] = mock_df['Close'].rolling(window=200, min_periods=1).mean() # 在此數據長度下會有很多 NaN
    delta = mock_df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    mock_df['RSI_14'] = 100 - (100 / (1 + rs))
    mock_df['RSI_14'] = np.where(loss == 0, 100, mock_df['RSI_14'])


    test_symbol = "MOCKAAPL"
    logger.info(f"[{test_symbol}] 測試 DataFrame (最後5行):\n{mock_df.tail()}")

    # 測試基本面 (模擬)
    is_risk, desc = check_high_debt_to_equity_ratio(test_symbol)
    logger.info(f"基本面 - 高負債權益比: {is_risk}, {desc}")

    # 測試技術面
    vol_period = config_manager.get_setting('risk_model_settings', 'volatility_period_days', 20)
    vol_thresh = config_manager.get_setting('risk_model_settings', 'historical_volatility_threshold_pct', 60.0)
    is_risk, desc = check_high_historical_volatility(mock_df, test_symbol, period=vol_period, threshold_pct=vol_thresh)
    logger.info(f"技術面 - 高歷史波動率: {is_risk}, {desc}")

    is_risk, desc = check_major_downtrend(mock_df, test_symbol)
    logger.info(f"技術面 - 主要下跌趨勢: {is_risk}, {desc}")

    rsi_low_thresh = config_manager.get_setting('risk_model_settings', 'rsi_low_threshold', 30)
    is_risk, desc = check_relative_strength_weak(mock_df, test_symbol, rsi_threshold=rsi_low_thresh)
    logger.info(f"技術面 - 相對強度極弱: {is_risk}, {desc}")

    is_risk, desc = check_breaking_support(mock_df, test_symbol)
    logger.info(f"技術面 - 跌破支撐: {is_risk}, {desc}")

    logger.info("--- Risk Models 內部測試結束 ---")
