# src/data_processor.py
import pandas as pd
import os
from src import logger_setup
from src import config_manager

# 獲取 logger
logger = logger_setup.setup_logger()

def process_ohlcv_data(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame | None:
    """
    處理從 yfinance 獲取的原始 OHLCV DataFrame。

    處理步驟包括：
    1. 檢查數據是否有效 (非 None 或空)。
    2. 移除成交量 (Volume) 為 0 或 NaN 的行。
    3. 使用 ffill 和 bfill 填充 OHLC 欄位的缺失值 (NaN)。
    4. 確保索引是 DatetimeIndex。
    5. 標準化欄位名稱 (通常 yfinance 已標準化，此處作檢查)。
    6. 增加 'Symbol' 欄位。

    參數:
        raw_df (pd.DataFrame): 從 yfinance_fetcher 獲取的原始 OHLCV 數據。
        symbol (str): 股票代碼。

    返回:
        pd.DataFrame: 處理後的 DataFrame。如果原始數據無效或處理後為空，則返回 None。
    """
    if raw_df is None:
        logger.error(f"[{symbol}] 接收到空的原始數據 (None)，無法處理。")
        return None
    if raw_df.empty:
        logger.warning(f"[{symbol}] 接收到的原始 DataFrame 為空，無需處理。")
        return pd.DataFrame() # 返回空的 DataFrame 而不是 None，以便調用者可以檢查 .empty

    logger.info(f"[{symbol}] 開始處理 OHLCV 數據。原始數據形狀: {raw_df.shape}")
    processed_df = raw_df.copy()

    # 1. 數據清洗：處理 Volume
    if 'Volume' not in processed_df.columns:
        logger.warning(f"[{symbol}] 數據中缺少 'Volume' 欄位。")
    else:
        original_rows = len(processed_df)
        # 移除 Volume 為 NaN 或 0 的行
        processed_df.dropna(subset=['Volume'], inplace=True)
        processed_df = processed_df[processed_df['Volume'] > 0]
        rows_removed = original_rows - len(processed_df)
        if rows_removed > 0:
            logger.info(f"[{symbol}] 移除了 {rows_removed} 行，因為其 'Volume' 為 NaN 或 0。")

    if processed_df.empty:
        logger.warning(f"[{symbol}] 移除成交量為0或NaN的行後，DataFrame 為空。")
        return pd.DataFrame()

    # 2. 數據清洗：處理 OHLC 欄位的缺失值
    ohlc_columns = ['Open', 'High', 'Low', 'Close']
    for col in ohlc_columns:
        if col not in processed_df.columns:
            logger.warning(f"[{symbol}] 數據中缺少 '{col}' 欄位，無法進行 NaN 填充。")
            continue
        if processed_df[col].isnull().any():
            logger.info(f"[{symbol}] 對欄位 '{col}' 使用 ffill 填充 NaN...")
            processed_df[col] = processed_df[col].ffill()
            if processed_df[col].isnull().any(): # 如果開頭仍有 NaN
                logger.info(f"[{symbol}] 對欄位 '{col}' 使用 bfill 填充剩餘 NaN (通常是開頭部分)...")
                processed_df[col] = processed_df[col].bfill()

    # 在填充 OHLC 後，再次檢查是否有任何行為空（例如，如果整個股票只有一行數據且是NaN）
    # processed_df.dropna(how='all', subset=ohlc_columns, inplace=True) # 如果OHLC都還是NaN，則移除該行
    # 改為非 inplace 操作以避免潛在的 SettingWithCopyWarning，儘管 dropna 通常較安全
    processed_df = processed_df.dropna(how='all', subset=ohlc_columns)
    if processed_df.empty:
        logger.warning(f"[{symbol}] 在填充 OHLC 的 NaN 並移除全 NaN 行後，DataFrame 為空。")
        return pd.DataFrame()

    # 3. 數據轉換：確保索引是 DatetimeIndex
    if not isinstance(processed_df.index, pd.DatetimeIndex):
        try:
            processed_df.index = pd.to_datetime(processed_df.index)
            logger.info(f"[{symbol}] DataFrame 索引已轉換為 DatetimeIndex。")
        except Exception as e:
            logger.error(f"[{symbol}] DataFrame 索引轉換為 DatetimeIndex 失敗: {e}。將不進行儲存。")
            return None

    # 4. 欄位標準化 (yfinance 通常已符合，但做個檢查)
    expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    # 轉換 API 回傳的欄位名稱 (例如 Adj Close -> Adj_Close)
    processed_df.columns = processed_df.columns.str.replace(' ', '_') # e.g. 'Adj Close' to 'Adj_Close'
    # 將欄位名稱統一為大寫開頭，其餘小寫 (如 Open, High)
    processed_df.columns = [col.capitalize() if col.lower() in [c.lower() for c in expected_columns] else col for col in processed_df.columns]

    # 確保標準欄位存在，如果不存在，可能需要記錄警告或錯誤
    for col in expected_columns:
        if col not in processed_df.columns:
            logger.warning(f"[{symbol}] 處理後的數據缺少標準欄位: '{col}'。")
            # 根據需求，這裡可以選擇創建一個空欄位或返回錯誤
            # processed_df[col] = pd.NA # 或者 np.nan

    # 增加 'Symbol' 欄位
    processed_df['Symbol'] = symbol
    logger.debug(f"[{symbol}] 已增加 'Symbol' 欄位。")

    logger.info(f"[{symbol}] 數據處理完成。處理後數據形狀: {processed_df.shape}")
    return processed_df

def save_data_to_parquet(processed_df: pd.DataFrame, symbol: str, market_type: str = "us_stocks") -> str | None:
    """
    將處理後的 DataFrame 儲存為 Parquet 格式檔案。

    檔案會根據 market_type 和 symbol 存放在設定檔中指定的路徑下。
    例如: MyFinancialSystem/main_data/market_data/us_stocks/AAPL_ohlcv.parquet

    參數:
        processed_df (pd.DataFrame): 經過 process_ohlcv_data 處理後的 DataFrame。
        symbol (str): 股票代碼。
        market_type (str): 市場類型，用於決定子目錄 (例如 "us_stocks", "tw_stocks")。
                           此字串應對應到 config_manager 中的子目錄鍵名。

    返回:
        str: 成功儲存的檔案的完整路徑。
        None: 如果儲存失敗或輸入的 DataFrame 無效。
    """
    if processed_df is None or processed_df.empty:
        logger.warning(f"[{symbol}] 接收到空的或無效的 DataFrame，不進行儲存。")
        return None

    base_dir = config_manager.get_setting('data_storage_settings', 'base_market_data_directory')

    # 根據 market_type 獲取對應的子目錄鍵名
    # 例如，如果 market_type 是 "us_stocks"，我們期望設定檔中有 "us_stocks_subdir"
    subdir_key = f"{market_type.lower()}_subdir" # e.g. "us_stocks_subdir"
    market_subdir = config_manager.get_setting('data_storage_settings', subdir_key)

    if not base_dir or not market_subdir:
        logger.error(f"[{symbol}] 無法從設定檔中獲取完整的數據儲存路徑。基礎目錄: '{base_dir}', 市場子目錄鍵: '{subdir_key}' -> '{market_subdir}'。")
        return None

    # 構造完整的目錄路徑
    storage_directory = os.path.join(base_dir, market_subdir)

    # 確保目標目錄存在
    try:
        os.makedirs(storage_directory, exist_ok=True)
        logger.debug(f"[{symbol}] 目標儲存目錄 '{storage_directory}' 已確認或創建。")
    except OSError as e:
        logger.error(f"[{symbol}] 創建儲存目錄 '{storage_directory}' 失敗: {e}。")
        return None

    # 構造檔案名稱和完整路徑
    # 清理 symbol 中的非法字元，例如用於檔案名稱的 ".TW" -> "_TW"
    safe_symbol_filename = symbol.replace(".", "_")
    file_name = f"{safe_symbol_filename}_ohlcv.parquet"
    file_path = os.path.join(storage_directory, file_name)

    logger.info(f"[{symbol}] 準備將處理後的數據儲存到: {file_path}")

    try:
        processed_df.to_parquet(file_path, engine='pyarrow', index=True) # index=True 以保留 DatetimeIndex
        logger.info(f"[{symbol}] 數據已成功儲存到 Parquet 檔案: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"[{symbol}] 將數據儲存到 Parquet 檔案 '{file_path}' 時發生錯誤: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # data_processor.py 的簡單內部測試 (通常更全面的測試會在 test_processor.py 中)
    logger.info("--- Data Processor 內部測試 ---")

    # 創建一個模擬的原始 DataFrame (模仿 yfinance 返回的數據)
    sample_data = {
        'Open': [150.0, 151.0, None, 153.0, 154.0],
        'High': [152.0, 152.5, 152.8, 154.0, 155.0],
        'Low': [149.0, 150.5, 150.0, 152.0, 153.0],
        'Close': [151.5, None, 152.0, 153.5, 154.5],
        'Adj Close': [151.0, 150.8, 151.5, 153.0, 154.0], # yfinance 可能有這個欄位
        'Volume': [100000, 120000, 0, 110000, None] # 包含 0 和 None
    }
    sample_dates = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05'])
    mock_raw_df = pd.DataFrame(sample_data, index=sample_dates)
    test_symbol = "TESTAAPL"

    logger.info(f"[{test_symbol}] 模擬原始數據:\n{mock_raw_df}")

    # 測試 process_ohlcv_data
    processed_df = process_ohlcv_data(mock_raw_df, test_symbol)

    if processed_df is not None and not processed_df.empty:
        logger.info(f"[{test_symbol}] 處理後數據:\n{processed_df}")
        logger.info(f"[{test_symbol}] 處理後數據是否有 NaN:\n{processed_df.isnull().sum()}")

        # 測試 save_data_to_parquet
        # 為了這個內部測試，我們假設 market_type 是 us_stocks
        # 注意：這個內部測試依賴於 config/strategy_config.yaml 中的設定是正確的
        # 且 MyFinancialSystem/main_data/... 目錄結構存在或可被創建

        # 在 GitHub Actions 或類似環境中，直接寫入根目錄下的模擬路徑可能更可靠
        # 如果 config_manager 正常工作，它會讀取正確的路徑
        saved_path = save_data_to_parquet(processed_df, test_symbol, market_type="us_stocks")
        if saved_path:
            logger.info(f"[{test_symbol}] 內部測試：數據成功儲存到 {saved_path}")
            # 可以嘗試讀回驗證
            try:
                read_df = pd.read_parquet(saved_path)
                logger.info(f"[{test_symbol}] 內部測試：從 {saved_path} 讀回的數據形狀: {read_df.shape}")
                if pd.DataFrame.equals(processed_df.reset_index(drop=True), read_df.reset_index(drop=True)): # 比較時可能需要重設索引
                     logger.info(f"[{test_symbol}] 內部測試：儲存和讀回的數據一致。")
                else:
                     logger.error(f"[{test_symbol}] 內部測試：儲存和讀回的數據不一致！")
            except Exception as e:
                logger.error(f"[{test_symbol}] 內部測試：讀回 Parquet 檔案時出錯: {e}")
            # 清理創建的測試檔案
            # os.remove(saved_path)
            # logger.info(f"[{test_symbol}] 內部測試：已清理測試檔案 {saved_path}")

        else:
            logger.error(f"[{test_symbol}] 內部測試：數據儲存失敗。")
    elif processed_df is not None and processed_df.empty:
        logger.warning(f"[{test_symbol}] 內部測試：數據處理後為空 DataFrame。")
    else:
        logger.error(f"[{test_symbol}] 內部測試：數據處理失敗，返回 None。")

    logger.info("--- Data Processor 內部測試結束 ---")
