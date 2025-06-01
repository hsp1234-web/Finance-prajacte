# test_processor.py
import sys
import os
import pandas as pd
import numpy as np # 用於創建 NaN

# 將 src 目錄添加到 Python 路徑中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.data_fetchers import yfinance_fetcher
    from src import data_processor
    from src import logger_setup
    from src import config_manager
    from src import db_cache_manager # 用於設定全域快取
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保 test_processor.py 與 src 目錄在同一層級，或 src 目錄已正確添加到 PYTHONPATH。")
    sys.exit(1)

# 設定 logger
logger = logger_setup.setup_logger()

def create_mock_dataframe_with_nan(symbol: str) -> pd.DataFrame:
    """創建一個包含缺失數據和待清洗數據的模擬 DataFrame。"""
    dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06'])
    data = {
        'Open': [np.nan, 101, 102, 103, 104, 105],
        'High': [100, 102, 103, 104, 105, 106],
        'Low': [98, 100, 101, np.nan, 103, 104],
        'Close': [99, 101, np.nan, 103, 104, 105],
        'Volume': [1000, 0, 500, 2000, np.nan, 3000] # 包含 0 和 NaN
    }
    df = pd.DataFrame(data, index=dates)
    logger.info(f"[{symbol}] 創建的模擬 DataFrame (含缺失值):\n{df}")
    return df

def run_processor_tests():
    """
    執行數據處理和儲存功能的整合測試。
    """
    logger.info("--- 開始執行 Processor 整合測試 ---")

    # 步驟 0: 啟用 API 快取 (如果 yfinance_fetcher 需要它)
    db_cache_manager.setup_global_cache()
    logger.info("全域 API 快取已啟用。")

    # --- 測試案例 1: 使用真實數據 (AAPL) ---
    logger.info("\n--- 測試案例 1: 使用 AAPL 的真實數據 ---")
    symbol_real = config_manager.get_setting("market_settings", "us_stock_pool", ["AAPL"])[1] # AAPL
    start_date = "2023-03-01"
    end_date = "2023-03-10"

    # 1. 獲取原始數據
    logger.info(f"[{symbol_real}] 步驟 1: 獲取原始 OHLCV 數據從 {start_date} 到 {end_date}。")
    raw_df_real = yfinance_fetcher.fetch_ohlcv(symbol_real, start_date, end_date)

    if raw_df_real is None or raw_df_real.empty:
        logger.error(f"[{symbol_real}] 無法獲取真實數據進行測試，跳過測試案例 1。")
    else:
        logger.info(f"[{symbol_real}] 原始數據獲取成功，形狀: {raw_df_real.shape}")
        logger.debug(f"[{symbol_real}] 原始數據預覽:\n{raw_df_real.head()}")

        # 2. 處理數據
        logger.info(f"[{symbol_real}] 步驟 2: 處理 OHLCV 數據。")
        processed_df_real = data_processor.process_ohlcv_data(raw_df_real, symbol_real)

        if processed_df_real is None or processed_df_real.empty:
            logger.error(f"[{symbol_real}] 數據處理失敗或返回空 DataFrame，無法繼續測試案例 1。")
        else:
            logger.info(f"[{symbol_real}] 數據處理成功，處理後形狀: {processed_df_real.shape}")
            logger.info(f"[{symbol_real}] 檢查處理後數據是否有 NaN:\n{processed_df_real.isnull().sum()}")
            assert not processed_df_real.isnull().values.any(), f"[{symbol_real}] 處理後的數據仍包含 NaN 值！"
            assert 'Symbol' in processed_df_real.columns, f"[{symbol_real}] 處理後的數據缺少 'Symbol' 欄位。"
            assert processed_df_real['Symbol'].iloc[0] == symbol_real, f"[{symbol_real}] 'Symbol' 欄位內容不正確。"
            logger.debug(f"[{symbol_real}] 處理後數據預覽:\n{processed_df_real.head()}")

            # 3. 儲存處理後的數據
            logger.info(f"[{symbol_real}] 步驟 3: 儲存處理後的數據到 Parquet。")
            # market_type 應從設定或股票代碼格式判斷，此處假設為 "us_stocks"
            file_path_real = data_processor.save_data_to_parquet(processed_df_real, symbol_real, market_type="us_stocks")

            if file_path_real and os.path.exists(file_path_real):
                logger.info(f"[{symbol_real}] 數據成功儲存到: {file_path_real}")

                # 4. 驗證儲存的檔案
                logger.info(f"[{symbol_real}] 步驟 4: 讀回 Parquet 檔案並驗證。")
                try:
                    read_df_real = pd.read_parquet(file_path_real)
                    logger.info(f"[{symbol_real}] 從 Parquet 檔案讀回的數據形狀: {read_df_real.shape}")
                    # 比較時要注意索引和欄位順序可能導致的差異
                    # processed_df_real 在存儲前索引可能是 DatetimeIndex 名稱為 'Date'
                    # read_df_real 讀回時索引可能也是 DatetimeIndex 名稱為 'Date'
                    pd.testing.assert_frame_equal(processed_df_real, read_df_real, check_dtype=True)
                    logger.info(f"[{symbol_real}] 成功驗證：讀回的數據與處理後的數據一致。")
                except pd.errors.ParserError as pe: # Parquet-specific read error
                    logger.error(f"[{symbol_real}] 讀取 Parquet 檔案 '{file_path_real}' 時發生 Parquet 解析錯誤: {pe}", exc_info=True)
                except AssertionError as ae:
                    logger.error(f"[{symbol_real}] 驗證失敗：讀回的數據與處理後的數據不一致: {ae}", exc_info=True)
                    logger.debug(f"Processed DF:\n{processed_df_real}\nRead DF:\n{read_df_real}")
                except Exception as e:
                    logger.error(f"[{symbol_real}] 讀取或驗證 Parquet 檔案時發生其他錯誤: {e}", exc_info=True)
            else:
                logger.error(f"[{symbol_real}] 數據儲存失敗或檔案未找到。")

    # --- 測試案例 2: 使用模擬的包含缺失和待清洗數據的 DataFrame ---
    logger.info("\n--- 測試案例 2: 使用模擬數據測試清洗邏輯 ---")
    symbol_mock = "MOCKDATA"
    mock_df = create_mock_dataframe_with_nan(symbol_mock)

    # 1. 處理數據
    logger.info(f"[{symbol_mock}] 步驟 1: 處理模擬的 OHLCV 數據。")
    processed_mock_df = data_processor.process_ohlcv_data(mock_df, symbol_mock)

    if processed_mock_df is None:
        logger.error(f"[{symbol_mock}] 模擬數據處理失敗，返回 None。")
    elif processed_mock_df.empty:
        logger.warning(f"[{symbol_mock}] 模擬數據處理後返回空 DataFrame。")
        # 根據 create_mock_dataframe_with_nan 的數據，Volume=0 的行會被移除
        # Open 的 NaN 會被填充，Close 的 NaN 會被填充
        # Volume 的 NaN 會被移除
        # 預期結果應該不是空的
        logger.error(f"[{symbol_mock}] 錯誤：模擬數據處理後不應為空。檢查 process_ohlcv_data 中的清洗邏輯。")
        logger.debug(f"[{symbol_mock}] 處理結果:\n{processed_mock_df}")

    else:
        logger.info(f"[{symbol_mock}] 模擬數據處理成功，處理後形狀: {processed_mock_df.shape}")
        logger.info(f"[{symbol_mock}] 檢查處理後數據是否有 NaN:\n{processed_mock_df.isnull().sum()}")

        # 預期 Volume=0 和 Volume=NaN 的行被移除 (共2行被移除)
        # 原始6行 - 2行 = 4行
        expected_rows = 4
        assert len(processed_mock_df) == expected_rows, \
            f"[{symbol_mock}] 處理後行數 ({len(processed_mock_df)}) 與預期 ({expected_rows}) 不符。"

        # 預期 OHLC 欄位沒有 NaN
        ohlc_cols = ['Open', 'High', 'Low', 'Close']
        for col in ohlc_cols:
            assert not processed_mock_df[col].isnull().any(), \
                f"[{symbol_mock}] 處理後的 '{col}' 欄位仍包含 NaN 值！"

        assert 'Symbol' in processed_mock_df.columns, f"[{symbol_mock}] 處理後的數據缺少 'Symbol' 欄位。"
        assert processed_mock_df['Symbol'].iloc[0] == symbol_mock, f"[{symbol_mock}] 'Symbol' 欄位內容不正確。"
        logger.info(f"[{symbol_mock}] 模擬數據處理邏輯符合預期。")
        logger.debug(f"[{symbol_mock}] 處理後模擬數據預覽:\n{processed_mock_df}")

        # 2. 儲存處理後的模擬數據 (可選，但有助於完整流程測試)
        logger.info(f"[{symbol_mock}] 步驟 2: 儲存處理後的模擬數據到 Parquet。")
        file_path_mock = data_processor.save_data_to_parquet(processed_mock_df, symbol_mock, market_type="us_stocks") # 存到 us_stocks 子目錄

        if file_path_mock and os.path.exists(file_path_mock):
            logger.info(f"[{symbol_mock}] 模擬數據成功儲存到: {file_path_mock}")
            # 可選: 讀回並驗證
            try:
                read_df_mock = pd.read_parquet(file_path_mock)
                pd.testing.assert_frame_equal(processed_mock_df, read_df_mock)
                logger.info(f"[{symbol_mock}] 成功驗證：讀回的模擬數據與處理後的數據一致。")
                # os.remove(file_path_mock) # 清理測試檔案
                # logger.info(f"[{symbol_mock}] 已清理模擬數據檔案: {file_path_mock}")
            except Exception as e:
                logger.error(f"[{symbol_mock}] 讀取或驗證模擬數據 Parquet 檔案時發生錯誤: {e}", exc_info=True)
        else:
            logger.error(f"[{symbol_mock}] 模擬數據儲存失敗或檔案未找到。")


    logger.info("\n--- Processor 整合測試結束 ---")

if __name__ == "__main__":
    run_processor_tests()
    logger.info("\n測試完成。請檢查上面的日誌輸出以確認行為是否符合預期。")
    base_data_dir = config_manager.get_setting('data_storage_settings', 'base_market_data_directory')
    logger.info(f"儲存的 Parquet 檔案應位於 '{base_data_dir}' 下的相應子目錄中。")
