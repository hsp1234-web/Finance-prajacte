# test_fetchers.py
import sys
import os
import time
import pandas as pd

# 將 src 目錄添加到 Python 路徑中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.data_fetchers import yfinance_fetcher
    from src import logger_setup
    from src import config_manager
    from src import db_cache_manager # 主要用於檢查快取檔案路徑
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保 test_fetchers.py 與 src 目錄在同一層級，或 src 目錄已正確添加到 PYTHONPATH。")
    sys.exit(1)

# 設定 logger
logger = logger_setup.setup_logger()

def check_cache_file_exists():
    """檢查快取檔案是否存在並打印其狀態。"""
    cache_db_path = config_manager.get_setting('cache_settings', 'api_cache_database_path')
    if cache_db_path:
        if os.path.exists(cache_db_path):
            logger.info(f"快取資料庫檔案 '{cache_db_path}' 存在。檔案大小: {os.path.getsize(cache_db_path)} bytes.")
            return True
        else:
            logger.warning(f"快取資料庫檔案 '{cache_db_path}' 不存在。")
            return False
    else:
        logger.error("在設定中未找到 'api_cache_database_path'。")
        return False

def run_fetcher_tests():
    """
    執行數據獲取和快取功能的測試。
    """
    logger.info("--- 開始執行 Fetcher 整合測試 ---")

    # 從設定檔獲取測試股票代碼，如果沒有則使用預設值
    us_stock_pool = config_manager.get_setting("market_settings", "us_stock_pool", ["AAPL", "MSFT"])
    test_symbol_valid = us_stock_pool[0] if us_stock_pool else "AAPL"

    test_symbol_invalid = "NONEXISTENTSTOCKXYZ123" # 一個更可能無效的代碼
    start_date = "2023-02-01" # 使用一個較短且固定的區間以利快取測試
    end_date = "2023-02-10"

    logger.info(f"將使用股票代碼 '{test_symbol_valid}' 進行有效性測試。")
    logger.info(f"將使用股票代碼 '{test_symbol_invalid}' 進行無效性測試。")
    logger.info(f"測試數據區間: {start_date} 至 {end_date}。")

    # 步驟 1: 首次獲取數據 (應從網路，並建立快取)
    logger.info(f"\n--- 測試階段 1: 首次獲取 '{test_symbol_valid}' (應從網路) ---")
    start_time_first = time.time()
    data_first = yfinance_fetcher.fetch_ohlcv(test_symbol_valid, start_date, end_date)
    duration_first = time.time() - start_time_first
    logger.info(f"首次獲取 '{test_symbol_valid}' 耗時: {duration_first:.4f} 秒。")

    if data_first is not None and not data_first.empty:
        logger.info(f"成功獲取 '{test_symbol_valid}' 的數據 (首次): \n{data_first.head()}")
    elif data_first is not None and data_first.empty:
        logger.warning(f"'{test_symbol_valid}' 首次獲取返回空 DataFrame。可能是該時段無數據。")
    else:
        logger.error(f"'{test_symbol_valid}' 數據獲取失敗 (首次)。")

    check_cache_file_exists() # 檢查快取檔案是否已創建

    # 步驟 2: 再次獲取相同數據 (應從快取，速度應較快)
    logger.info(f"\n--- 測試階段 2: 再次獲取 '{test_symbol_valid}' (應從快取) ---")
    start_time_second = time.time()
    data_second = yfinance_fetcher.fetch_ohlcv(test_symbol_valid, start_date, end_date)
    duration_second = time.time() - start_time_second
    logger.info(f"再次獲取 '{test_symbol_valid}' 耗時: {duration_second:.4f} 秒。")

    if data_second is not None and not data_second.empty:
        logger.info(f"成功獲取 '{test_symbol_valid}' 的數據 (第二次): \n{data_second.head()}")
    elif data_second is not None and data_second.empty:
        logger.warning(f"'{test_symbol_valid}' 第二次獲取返回空 DataFrame。")
    else:
        logger.error(f"'{test_symbol_valid}' 數據獲取失敗 (第二次)。")

    # 比較兩次獲取的數據和耗時
    if data_first is not None and data_second is not None:
        if pd.DataFrame.equals(data_first, data_second):
            logger.info(f"數據一致性檢查: '{test_symbol_valid}' 首次和第二次獲取的數據內容相同。")
        else:
            logger.error(f"數據一致性檢查: '{test_symbol_valid}' 首次和第二次獲取的數據內容不同！")

        if duration_second < duration_first:
            logger.info(f"效能檢查: 第二次獲取速度 ({duration_second:.4f}s) 明顯快於第一次 ({duration_first:.4f}s)。快取可能已生效。")
        else:
            logger.warning(f"效能檢查: 第二次獲取速度 ({duration_second:.4f}s) 未明顯快於第一次 ({duration_first:.4f}s)。快取可能未生效或網路延遲極低。")
    elif data_first is None and data_second is not None:
        logger.warning("首次獲取失敗，但第二次獲取成功。可能是暫時性網路問題後快取了結果。")
    elif data_first is not None and data_second is None:
        logger.error("首次獲取成功，但第二次獲取失敗。這不符合預期。")


    # 步驟 3: 獲取一個不存在的股票代碼 (應返回 None 或空 DataFrame，並測試錯誤處理)
    logger.info(f"\n--- 測試階段 3: 獲取無效股票 '{test_symbol_invalid}' ---")
    start_time_invalid = time.time()
    data_invalid = yfinance_fetcher.fetch_ohlcv(test_symbol_invalid, start_date, end_date)
    duration_invalid = time.time() - start_time_invalid
    logger.info(f"獲取無效股票 '{test_symbol_invalid}' 耗時: {duration_invalid:.4f} 秒。")

    if data_invalid is None:
        logger.info(f"'{test_symbol_invalid}' 數據獲取按預期返回 None (錯誤處理成功)。")
    elif data_invalid.empty:
        logger.info(f"'{test_symbol_invalid}' 數據獲取按預期返回空 DataFrame (錯誤處理成功)。")
    else:
        logger.error(f"'{test_symbol_invalid}' 數據獲取未按預期處理錯誤，返回了數據: \n{data_invalid.head()}")

    # 步驟 4: 再次獲取無效股票代碼 (測試快取是否也處理了 "未找到" 的情況)
    # requests-cache 預設會快取 HTTP 404 等錯誤回應
    logger.info(f"\n--- 測試階段 4: 再次獲取無效股票 '{test_symbol_invalid}' (檢查快取) ---")
    start_time_invalid_cached = time.time()
    data_invalid_cached = yfinance_fetcher.fetch_ohlcv(test_symbol_invalid, start_date, end_date)
    duration_invalid_cached = time.time() - start_time_invalid_cached
    logger.info(f"再次獲取無效股票 '{test_symbol_invalid}' 耗時: {duration_invalid_cached:.4f} 秒。")

    if data_invalid_cached is None or data_invalid_cached.empty:
        logger.info(f"'{test_symbol_invalid}' 第二次數據獲取也按預期失敗或返回空。")
        if duration_invalid_cached < duration_invalid:
             logger.info(f"效能檢查 (無效股票): 第二次獲取 ({duration_invalid_cached:.4f}s) 快於第一次 ({duration_invalid:.4f}s)。表明錯誤回應可能也被快取。")
        else:
            logger.warning(f"效能檢查 (無效股票): 第二次獲取速度 ({duration_invalid_cached:.4f}s) 未明顯快於第一次 ({duration_invalid:.4f}s)。")
    else:
        logger.error(f"'{test_symbol_invalid}' 第二次數據獲取未按預期處理錯誤。")

    logger.info("\n--- Fetcher 整合測試結束 ---")
    check_cache_file_exists() # 最終檢查快取檔案

if __name__ == "__main__":
    run_fetcher_tests()
    logger.info("\n測試完成。請檢查上面的日誌輸出以確認行為是否符合預期。")
    logger.info(f"快取檔案應位於: {config_manager.get_setting('cache_settings', 'api_cache_database_path')}")
    logger.info("你可以使用 SQLite 工具 (例如 sqlite3 CLI 或 DB Browser for SQLite) 來檢查快取資料庫的內容。")
    logger.info("例如：`sqlite3 MyFinancialSystem/main_data/api_cache/api_cache.sqlite \"SELECT * FROM responses;\"`")
