# src/data_fetchers/yfinance_fetcher.py
import yfinance as yf
import pandas as pd
from src import db_cache_manager
from src import logger_setup
from src import config_manager # 用於獲取市場設定等 (如果需要)

# 獲取 logger
logger = logger_setup.setup_logger()

# 設定全域 API 快取
# 這將使得 yfinance (如果其內部使用標準 requests) 的請求被快取
db_cache_manager.setup_global_cache()

def fetch_ohlcv(symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """
    使用 yfinance 獲取指定股票代碼的 OHLCV (開盤價, 最高價, 最低價, 收盤價, 成交量) 數據。
    數據請求會通過 db_cache_manager 配置的快取 session 進行。

    參數:
        symbol (str): 股票代碼 (例如 "AAPL", "0050.TW")。
        start_date (str): 開始日期，格式 "YYYY-MM-DD"。
        end_date (str): 結束日期，格式 "YYYY-MM-DD"。

    返回:
        pd.DataFrame: 包含 OHLCV 數據的 Pandas DataFrame，索引為日期。
                      如果發生錯誤或找不到數據，則返回 None 或空的 DataFrame。
    """
    logger.info(f"開始為股票代碼 '{symbol}' 獲取從 {start_date} 到 {end_date} 的 OHLCV 數據。")

    try:
        # yfinance 現在建議讓其自行管理 session
        # 全域安裝的 requests_cache 應該會自動攔截 yfinance 內部的 requests 調用 (如果有的話)
        ticker_obj = yf.Ticker(symbol)

        # 下載歷史數據
        history_data = ticker_obj.history(start=start_date, end=end_date)

        if history_data.empty:
            logger.warning(f"股票代碼 '{symbol}' 在日期範圍 {start_date} 到 {end_date} 內沒有返回數據。可能是代碼錯誤、下市或該時段無交易。")
            return pd.DataFrame() # 返回空的 DataFrame

        logger.info(f"成功獲取股票代碼 '{symbol}' 的 {len(history_data)} 筆數據。")

        # 快取狀態的確認現在依賴於 requests_cache 的日誌 (如果啟用 DEBUG 級別)
        # 或者通過比較重複請求的時間來間接判斷

        return history_data

    except Exception as e:
        # yfinance 可能會針對無效股票代碼拋出各種錯誤，或者網路問題
        logger.error(f"為股票代碼 '{symbol}' 獲取數據時發生錯誤: {e}", exc_info=True)
        return None


if __name__ == '__main__':
    # 簡單測試 yfinance_fetcher
    print("--- YFinance Fetcher (使用全域快取) 測試 ---")
    logger.info("開始測試 YFinance Fetcher (設定為使用全域快取)。")

    # 測試參數
    test_symbol_valid = config_manager.get_setting("market_settings", "us_stock_pool", ["AAPL"])[0]
    test_symbol_invalid = "NONEXISTENTSTOCKXYZ"
    start_date = "2023-01-01"
    end_date = "2023-01-10"

    # 首次獲取有效股票數據
    logger.info(f"\n--- 第一次獲取 '{test_symbol_valid}' (應從網路) ---")
    data_first_fetch = fetch_ohlcv(test_symbol_valid, start_date, end_date)
    if data_first_fetch is not None and not data_first_fetch.empty:
        logger.info(f"'{test_symbol_valid}' 數據獲取成功 (首次): \n{data_first_fetch.head()}")
    elif data_first_fetch is not None and data_first_fetch.empty:
        logger.warning(f"'{test_symbol_valid}' 首次獲取返回空 DataFrame。")
    else:
        logger.error(f"'{test_symbol_valid}' 數據獲取失敗 (首次)。")

    # 再次獲取相同股票數據 (應從快取)
    logger.info(f"\n--- 第二次獲取 '{test_symbol_valid}' (應從快取) ---")
    data_second_fetch = fetch_ohlcv(test_symbol_valid, start_date, end_date)
    if data_second_fetch is not None and not data_second_fetch.empty:
        logger.info(f"'{test_symbol_valid}' 數據獲取成功 (第二次): \n{data_second_fetch.head()}")
    elif data_second_fetch is not None and data_second_fetch.empty:
        logger.warning(f"'{test_symbol_valid}' 第二次獲取返回空 DataFrame。")
    else:
        logger.error(f"'{test_symbol_valid}' 數據獲取失敗 (第二次)。")

    # 比較兩次獲取的數據是否一致 (如果都成功)
    if data_first_fetch is not None and data_second_fetch is not None and \
       not data_first_fetch.empty and not data_second_fetch.empty:
        if pd.DataFrame.equals(data_first_fetch, data_second_fetch):
            logger.info(f"'{test_symbol_valid}' 首次和第二次獲取的數據一致。")
        else:
            logger.error(f"'{test_symbol_valid}' 首次和第二次獲取的數據不一致！數據源可能在兩次請求間發生了極小變動。")


    # 獲取無效股票數據
    logger.info(f"\n--- 獲取無效股票 '{test_symbol_invalid}' ---")
    data_invalid = fetch_ohlcv(test_symbol_invalid, start_date, end_date)
    if data_invalid is None:
        logger.info(f"'{test_symbol_invalid}' 數據獲取按預期失敗 (返回 None)。")
    elif data_invalid.empty:
        logger.info(f"'{test_symbol_invalid}' 數據獲取按預期失敗 (返回空 DataFrame)。")
    else:
        logger.error(f"'{test_symbol_invalid}' 數據獲取未按預期失敗，反而獲取到數據: \n{data_invalid.head()}")

    # 檢查快取檔案
    db_file = config_manager.get_setting('cache_settings', 'api_cache_database_path')
    if db_file and os.path.exists(db_file):
        logger.info(f"快取資料庫檔案 {db_file} 存在。檔案大小: {os.path.getsize(db_file)} bytes.")
        # 可以用 sqlite3 CLI 工具打開此檔案查看內容
        # 例如: sqlite3 MyFinancialSystem/main_data/api_cache/api_cache.sqlite ".schema" "SELECT * FROM responses LIMIT 5;"
    elif db_file:
        logger.warning(f"快取資料庫檔案 {db_file} 未找到。")

    logger.info("YFinance Fetcher (使用全域快取) 測試結束。")
    print("--- YFinance Fetcher (使用全域快取) 測試結束 ---")
