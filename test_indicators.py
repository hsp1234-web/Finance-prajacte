# test_indicators.py
import sys
import os
import pandas as pd

# 將 src 目錄添加到 Python 路徑中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.data_fetchers import yfinance_fetcher
    from src import data_processor
    from src import indicator_engine
    from src import logger_setup
    from src import config_manager
    from src import db_cache_manager # 用於設定全域快取
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保 test_indicators.py 與 src 目錄在同一層級，或 src 目錄已正確添加到 PYTHONPATH。")
    sys.exit(1)

# 設定 logger
logger = logger_setup.setup_logger()

def run_indicator_tests():
    """
    執行技術指標計算功能的整合測試。
    """
    logger.info("--- 開始執行 Indicator Engine 整合測試 ---")

    # 步驟 0: 啟用 API 快取
    db_cache_manager.setup_global_cache()
    logger.info("全域 API 快取已啟用。")

    # 測試參數
    # 從設定檔獲取測試股票代碼，如果沒有則使用預設值 "AAPL"
    us_stock_pool = config_manager.get_setting("market_settings", "us_stock_pool", ["SPY", "AAPL", "MSFT"])
    # 確保至少有一個股票代碼，且選擇一個常用於測試的，例如 AAPL
    symbol_to_test = "AAPL"
    if isinstance(us_stock_pool, list) and len(us_stock_pool) > 1:
        symbol_to_test = us_stock_pool[1] # 通常 AAPL 在第二位
    elif isinstance(us_stock_pool, list) and len(us_stock_pool) > 0:
        symbol_to_test = us_stock_pool[0]

    start_date = "2023-01-01" # 需要足夠數據來計算較長週期的 SMA (例如 200 天)
    end_date = "2023-12-31"   # 一整年的數據

    logger.info(f"將使用股票代碼 '{symbol_to_test}' 進行指標計算測試，數據期間: {start_date} 至 {end_date}。")

    # 1. 獲取原始數據
    logger.info(f"[{symbol_to_test}] 步驟 1: 獲取原始 OHLCV 數據。")
    raw_df = yfinance_fetcher.fetch_ohlcv(symbol_to_test, start_date, end_date)

    if raw_df is None or raw_df.empty:
        logger.error(f"[{symbol_to_test}] 無法獲取 OHLCV 數據進行測試，測試中止。")
        return

    logger.info(f"[{symbol_to_test}] 原始數據獲取成功，形狀: {raw_df.shape}")

    # 2. 處理數據
    logger.info(f"[{symbol_to_test}] 步驟 2: 處理 OHLCV 數據。")
    processed_df = data_processor.process_ohlcv_data(raw_df, symbol_to_test)

    if processed_df is None or processed_df.empty:
        logger.error(f"[{symbol_to_test}] 數據處理失敗或返回空 DataFrame，測試中止。")
        return

    logger.info(f"[{symbol_to_test}] 數據處理成功，處理後形狀: {processed_df.shape}")
    # data_processor 處理後，欄位名應為首字母大寫，例如 'Open', 'Close'

    # 3. 計算技術指標
    logger.info(f"[{symbol_to_test}] 步驟 3: 計算技術指標。")
    # indicator_engine.calculate_technical_indicators 期望欄位名為小寫
    # 但其內部會轉換。我們傳遞 data_processor 的輸出。
    indicators_df = indicator_engine.calculate_technical_indicators(processed_df)

    if indicators_df is None or indicators_df.empty:
        logger.error(f"[{symbol_to_test}] 技術指標計算失敗或返回空 DataFrame，測試中止。")
        return

    logger.info(f"[{symbol_to_test}] 技術指標計算成功，計算後形狀: {indicators_df.shape}")

    # 預期新增的欄位 (pandas_ta 會自動命名，通常是大寫加下劃線和週期)
    # SMA_20, SMA_50, SMA_200, RSI_14, OBV, MFI_14
    # 由於 indicator_engine 內部會將原始欄位轉小寫，pandas_ta 生成的欄位名也是基於小寫的
    # 例如，SMA_20, RSI_14。 OBV 通常就是 OBV。
    expected_indicator_columns = ['sma_20', 'sma_50', 'sma_200', 'rsi_14', 'obv', 'mfi_14']

    logger.info(f"[{symbol_to_test}] DataFrame 的最後幾行 (包含指標):")
    print(indicators_df.tail()) # 使用 print 方便直接查看表格

    # 檢查指標欄位是否存在
    actual_columns_lower = [col.lower() for col in indicators_df.columns]
    missing_cols = []
    for expected_col_lower in expected_indicator_columns:
        # pandas_ta 可能會添加額外的前後綴，這裡做一個基本的部分匹配檢查
        # 例如，OBV 可能被命名為 OBV，MFI_14 可能被命名為 MFI_14
        # SMA_20 可能被命名為 SMA_20
        # RSI_14 可能被命名為 RSI_14
        # 我們的 calculate_technical_indicators 函數中的 calculated_indicators 列表更可靠
        # 但這裡我們檢查 test_indicators.py 中預期的欄位

        # 由於 pandas_ta 的命名可能很精確 (e.g., SMA_20, RSI_14)
        # 直接檢查小寫版本是否存在於轉換後的小寫欄位列表中
        if expected_col_lower not in actual_columns_lower:
            # 嘗試更寬鬆的檢查：如果 expected_col_lower 是 'sma_20'，檢查是否有任何以 'sma_20' 開頭的
            # 這對於像 OBV 這樣可能被命名為 OBV_volume 的情況可能不夠用
            # 但對於 SMA, RSI, MFI，pandas_ta 的命名通常是固定的

            # 檢查是否存在一個實際欄位，其小寫版本與預期的小寫版本匹配
            # pandas_ta 0.3.14b 生成的欄位名就是 SMA_20, RSI_14, MFI_14, OBV (全大寫)
            # 所以我們應該在 indicators_df.columns 中查找大寫版本
            if expected_col_lower.upper() not in indicators_df.columns:
                 missing_cols.append(expected_col_lower)


    if not missing_cols:
        logger.info(f"[{symbol_to_test}] 所有預期的指標欄位 ({', '.join(expected_indicator_columns)}) 已在 DataFrame 中找到 (可能大小寫不同)。")
    else:
        logger.error(f"[{symbol_to_test}] 以下預期的指標欄位未找到: {', '.join(missing_cols)}")
        logger.debug(f"[{symbol_to_test}] DataFrame 實際欄位: {list(indicators_df.columns)}")

    # 簡單檢查指標數值是否合理 (例如，RSI 在 0-100 之間)
    if 'RSI_14' in indicators_df.columns: # pandas_ta 會生成大寫的 RSI_14
        rsi_values = indicators_df['RSI_14'].dropna()
        if not rsi_values.empty:
            if rsi_values.between(0, 100).all():
                logger.info(f"[{symbol_to_test}] RSI_14 指標數值在預期範圍 (0-100) 內。")
            else:
                logger.warning(f"[{symbol_to_test}] RSI_14 指標數值超出了預期範圍 (0-100)。異常值示例:\n{rsi_values[~rsi_values.between(0,100)]}")
        else:
            logger.warning(f"[{symbol_to_test}] RSI_14 指標全部為 NaN (可能是數據不足)。")
    else:
        logger.warning(f"[{symbol_to_test}] 未找到 'RSI_14' 欄位 (可能是命名問題或計算失敗)。")


    logger.info("\n--- Indicator Engine 整合測試結束 ---")

if __name__ == "__main__":
    run_indicator_tests()
    logger.info("\n測試完成。請檢查上面的日誌輸出以確認指標計算是否符合預期。")
    logger.info("注意：由於窗口期的原因，指標欄位的開頭部分為 NaN 是正常的。")
