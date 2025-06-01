# src/stock_screener.py
import os
import pandas as pd
from src import logger_setup
from src import config_manager
from src.data_fetchers import yfinance_fetcher
from src import data_processor
from src import indicator_engine
from src import risk_models

# 獲取 logger 和 config
logger = logger_setup.setup_logger()

def get_market_type_from_symbol(symbol: str) -> str:
    """根據股票代碼的後綴判斷市場類型。"""
    if symbol.endswith(".TW"):
        return "tw_stocks"
    # 預設為美股或其他國際市場 (可根據需要擴展)
    return "us_stocks"

def load_or_fetch_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """
    嘗試從 Parquet 檔案加載已處理數據，如果失敗或檔案不存在，則重新獲取並處理。
    """
    market_type = get_market_type_from_symbol(symbol)
    base_dir = config_manager.get_setting('data_storage_settings', 'base_market_data_directory')
    subdir_key = f"{market_type}_subdir"
    market_subdir = config_manager.get_setting('data_storage_settings', subdir_key)

    if not base_dir or not market_subdir:
        logger.error(f"[{symbol}] 無法從設定檔獲取 Parquet 儲存路徑。")
        return None

    safe_symbol_filename = symbol.replace(".", "_")
    file_name = f"{safe_symbol_filename}_ohlcv.parquet"
    parquet_file_path = os.path.join(base_dir, market_subdir, file_name)

    # 嘗試加載 Parquet 檔案
    if os.path.exists(parquet_file_path):
        try:
            logger.info(f"[{symbol}] 找到已儲存的 Parquet 檔案，嘗試加載: {parquet_file_path}")
            df = pd.read_parquet(parquet_file_path)
            # 簡易檢查：確保索引是 DatetimeIndex (data_processor 儲存時會處理)
            if isinstance(df.index, pd.DatetimeIndex):
                logger.info(f"[{symbol}] 從 Parquet 檔案成功加載數據，形狀: {df.shape}")
                return df
            else:
                logger.warning(f"[{symbol}] Parquet 檔案索引非 DatetimeIndex，將重新獲取數據。")
        except Exception as e:
            logger.error(f"[{symbol}] 加載 Parquet 檔案 '{parquet_file_path}' 失敗: {e}。將嘗試重新獲取數據。")

    # 如果加載失敗或檔案不存在，則獲取、處理並儲存新數據
    logger.info(f"[{symbol}] 未找到有效的本地數據或加載失敗，開始從 API 獲取數據。")
    raw_df = yfinance_fetcher.fetch_ohlcv(symbol, start_date, end_date)
    if raw_df is None or raw_df.empty:
        logger.error(f"[{symbol}] 無法從 yfinance_fetcher 獲取原始數據。")
        return None

    processed_df = data_processor.process_ohlcv_data(raw_df, symbol)
    if processed_df is None or processed_df.empty:
        logger.error(f"[{symbol}] 數據處理失敗。")
        return None

    # 儲存新處理的數據
    saved_path = data_processor.save_data_to_parquet(processed_df, symbol, market_type=market_type)
    if saved_path:
        logger.info(f"[{symbol}] 新獲取的數據已處理並儲存到: {saved_path}")
    else:
        logger.warning(f"[{symbol}] 新獲取的數據處理後未能成功儲存。")

    return processed_df


def screen_stocks() -> dict:
    """
    遍歷設定檔中定義的股票池，評估每支股票的風險。

    返回:
        dict: 一個字典，鍵為高風險股票的代碼，值為該股票觸發的風險描述列表。
    """
    logger.info("--- 開始執行股票篩選與風險評估 ---")

    us_pool = config_manager.get_setting("market_settings", "us_stock_pool", [])
    tw_pool = config_manager.get_setting("market_settings", "tw_stock_pool", [])
    stock_pool = list(set(us_pool + tw_pool)) # 合併並去重

    if not stock_pool:
        logger.warning("股票池為空，沒有股票可供篩選。")
        return {}

    logger.info(f"待篩選股票池: {', '.join(stock_pool)}")

    high_risk_stocks = {}

    # 風險模型閾值 (從設定檔讀取，提供預設值)
    rsi_low_thresh = config_manager.get_setting('risk_model_settings', 'rsi_low_threshold', 30)
    vol_period = config_manager.get_setting('risk_model_settings', 'volatility_period_days', 20)
    vol_thresh_pct = config_manager.get_setting('risk_model_settings', 'historical_volatility_threshold_pct', 60.0)

    # 數據獲取的時間範圍 (可考慮配置化)
    # 為了計算 SMA200，至少需要約一年的數據
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    start_date = (pd.Timestamp.now() - pd.DateOffset(years=1, days=90)).strftime('%Y-%m-%d') # 約1年又3個月，確保數據充足

    for symbol in stock_pool:
        logger.info(f"---正在處理股票: {symbol} ---")

        # 1. 數據準備 (加載或獲取)
        df = load_or_fetch_data(symbol, start_date, end_date)
        if df is None or df.empty:
            logger.warning(f"[{symbol}] 無法獲取或加載有效數據，跳過此股票的風險評估。")
            continue

        # 2. 指標計算
        logger.debug(f"[{symbol}] 開始計算技術指標...")
        df_with_indicators = indicator_engine.calculate_technical_indicators(df)
        if df_with_indicators is None or df_with_indicators.empty:
            logger.warning(f"[{symbol}] 技術指標計算失敗，跳過此股票的風險評估。")
            continue
        logger.info(f"[{symbol}] 技術指標計算完成。")

        # 3. 風險評估
        symbol_risks = []

        # 技術面風險
        logger.debug(f"[{symbol}] 開始評估技術面風險...")
        is_volatile, desc_vol = risk_models.check_high_historical_volatility(df_with_indicators, symbol, period=vol_period, threshold_pct=vol_thresh_pct)
        if is_volatile: symbol_risks.append(desc_vol)

        is_downtrend, desc_dt = risk_models.check_major_downtrend(df_with_indicators, symbol)
        if is_downtrend: symbol_risks.append(desc_dt)

        is_weak, desc_weak = risk_models.check_relative_strength_weak(df_with_indicators, symbol, rsi_threshold=rsi_low_thresh)
        if is_weak: symbol_risks.append(desc_weak)

        is_breaking_support, desc_support = risk_models.check_breaking_support(df_with_indicators, symbol)
        if is_breaking_support: symbol_risks.append(desc_support)

        # 模擬基本面風險 (為每個股票都調用，但它們目前返回無風險)
        logger.debug(f"[{symbol}] 開始評估模擬基本面風險...")
        is_high_debt, desc_debt = risk_models.check_high_debt_to_equity_ratio(symbol)
        if is_high_debt: symbol_risks.append(desc_debt)

        is_neg_earn, desc_earn = risk_models.check_negative_earnings_trend(symbol)
        if is_neg_earn: symbol_risks.append(desc_earn)

        is_low_margin, desc_margin = risk_models.check_low_profit_margins(symbol)
        if is_low_margin: symbol_risks.append(desc_margin)

        if symbol_risks:
            logger.warning(f"[{symbol}] 被識別為潛在高風險股票。風險列表: {symbol_risks}")
            high_risk_stocks[symbol] = symbol_risks
        else:
            logger.info(f"[{symbol}] 未觸發顯著風險指標。")

    logger.info(f"--- 股票篩選與風險評估結束 ---")
    if high_risk_stocks:
        logger.info(f"共篩選出 {len(high_risk_stocks)} 支潛在高風險股票。")
    else:
        logger.info("未篩選出顯著高風險的股票。")

    return high_risk_stocks


if __name__ == '__main__':
    logger.info("--- Stock Screener 內部測試 ---")
    # 確保 API 快取已設定 (如果 fetcher 需要)
    from src import db_cache_manager
    db_cache_manager.setup_global_cache()

    risky_ones = screen_stocks()

    if risky_ones:
        print("\n--- 篩選出的高風險股票及其原因 ---")
        for symbol, reasons in risky_ones.items():
            print(f"\n股票: {symbol}")
            for reason in reasons:
                print(f"  - {reason}")
    else:
        print("\n--- 未篩選出高風險股票 ---")

    logger.info("--- Stock Screener 內部測試結束 ---")
