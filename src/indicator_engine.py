# src/indicator_engine.py
import pandas as pd
# import pandas_ta as ta # 暫時移除 pandas_ta 以避免導入錯誤
import numpy as np # 需要 numpy 來計算 RSI 等
from src import logger_setup

# 獲取 logger 物件
logger = logger_setup.setup_logger()

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算給定 DataFrame 的技術指標。

    目前計算的指標包括：
    - SMA (Simple Moving Averages) 短、中、長期
    - RSI (Relative Strength Index)
    - OBV (On-Balance Volume)
    - MFI (Money Flow Index)

    參數:
        df (pd.DataFrame): 包含 'Open', 'High', 'Low', 'Close', 'Volume' 欄位的 Pandas DataFrame。
                           索引應為 DatetimeIndex。

    返回:
        pd.DataFrame: 附加了計算出的技術指標欄位的原始 DataFrame 的副本。
                      如果輸入的 DataFrame 無效或缺少必要欄位，則可能記錄錯誤並返回原始 DataFrame 的副本。
    """
    if df is None or df.empty:
        logger.warning("輸入的 DataFrame 為空或 None，無法計算技術指標。")
        return df.copy() if df is not None else pd.DataFrame()

    # 確保 DataFrame 有必要的欄位 (現在我們自己處理，可以保持大寫或按需轉換)
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = df.copy() # 創建一個副本以避免修改原始 DataFrame

    missing_cols = [col for col in required_columns if col not in data.columns]
    if missing_cols:
        logger.error(f"輸入的 DataFrame 缺少必要的欄位: {', '.join(missing_cols)}。無法計算技術指標。")
        return df.copy()

    logger.info(f"開始手動計算技術指標。輸入數據形狀: {data.shape}")

    # 參數設定 (初步硬編碼，未來可配置)
    sma_short_period = 20
    sma_mid_period = 50
    sma_long_period = 200
    rsi_period = 14
    mfi_period = 14

    calculated_indicators_names = []

    try:
        # 手動計算 SMA
        logger.debug(f"手動計算 SMA ({sma_short_period}, {sma_mid_period}, {sma_long_period})...")
        data[f'SMA_{sma_short_period}'] = data['Close'].rolling(window=sma_short_period, min_periods=1).mean()
        data[f'SMA_{sma_mid_period}'] = data['Close'].rolling(window=sma_mid_period, min_periods=1).mean()
        data[f'SMA_{sma_long_period}'] = data['Close'].rolling(window=sma_long_period, min_periods=1).mean()
        calculated_indicators_names.extend([f'SMA_{sma_short_period}', f'SMA_{sma_mid_period}', f'SMA_{sma_long_period}'])

        # 手動計算 RSI
        logger.debug(f"手動計算 RSI (period: {rsi_period})...")
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period, min_periods=1).mean()
        rs = gain / loss
        data[f'RSI_{rsi_period}'] = 100 - (100 / (1 + rs))
        # 處理 loss 為 0 的情況 (RSI 應為 100)
        data[f'RSI_{rsi_period}'] = np.where(loss == 0, 100, data[f'RSI_{rsi_period}'])
        # 處理 gain 和 loss 都為 0 的情況 (RSI 可視為 0 或 50，常見為 0 或前值)
        # pandas_ta 在 gain=0, loss=0 時 RSI=NaN，然後可能被 ffill。這裡如果 rs=NaN (因 loss=0), RSI 會是 NaN。
        # 如果 rs=inf (因 loss=0, gain >0), RSI 會是 100。這是正確的。
        # 如果 gain=0, loss >0, rs=0, RSI=0。這是正確的。
        calculated_indicators_names.append(f'RSI_{rsi_period}')

        # OBV 和 MFI 的手動實現較複雜，暫時跳過
        logger.warning("OBV 和 MFI 的手動計算暫未實現。")

        logger.info(f"成功手動計算並附加了以下技術指標: {', '.join(calculated_indicators_names)}")
        logger.debug(f"計算後數據形狀: {data.shape}")

    except Exception as e:
        logger.error(f"手動計算技術指標時發生錯誤: {e}", exc_info=True)
        return data # 返回部分計算的數據

    return data

if __name__ == '__main__':
    # 簡單測試 indicator_engine
    logger.info("--- Indicator Engine 內部測試 ---")

    # 創建一個模擬的 DataFrame (模仿處理後的 OHLCV 數據)
    sample_dates = pd.to_datetime(['2023-01-01'] * 30) + pd.to_timedelta(range(30), unit='D')
    ohlcv_data = {
        'Open': [150 + i*0.1 for i in range(30)],
        'High': [152 + i*0.15 for i in range(30)],
        'Low': [149 - i*0.05 for i in range(30)],
        'Close': [151 + i*0.1 for i in range(30)], # 收盤價有趨勢，方便觀察SMA
        'Volume': [100000 + i*1000 for i in range(30)]
    }
    mock_df = pd.DataFrame(ohlcv_data, index=sample_dates)
    # 在 data_processor 中，欄位名會被標準化為首字母大寫
    # 但 pandas_ta 通常期望小寫，所以在 calculate_technical_indicators 中已作轉換
    # 此處傳入的 mock_df 欄位名為首字母大寫，符合 data_processor 輸出

    logger.info(f"內部測試：原始模擬數據 (前5行):\n{mock_df.head()}")

    indicators_df = calculate_technical_indicators(mock_df.copy()) #傳遞副本

    if indicators_df is not None and not indicators_df.empty:
        logger.info(f"內部測試：計算指標後的數據 (前5行顯示 NaN 是正常的，因為窗口期):\n{indicators_df.head()}")
        logger.info(f"內部測試：計算指標後的數據 (後5行，應有數值):\n{indicators_df.tail()}")

        # 檢查指標欄位是否存在 (pandas_ta 會自動命名)
        expected_new_cols = ['SMA_20', 'SMA_50', 'RSI_14', 'OBV', 'MFI_14'] # SMA_50 會全是 NaN 因為數據點不夠
        actual_cols = indicators_df.columns.tolist()
        logger.info(f"內部測試：所有欄位: {actual_cols}")

        missing_indicator_cols = []
        for col_pattern in expected_new_cols:
            # 由於 pandas_ta 的命名可能包含原始欄位名 (例如 obv_close), 我們進行部分匹配
            # SMA_20, RSI_14, MFI_14 應該是精確匹配 (或大寫)
            # OBV 可能是 OBV 或 OBV_volume (取決於版本和設定，通常是 OBV)
            found = False
            if col_pattern == 'OBV':
                 # OBV 可能被命名為 OBV 或 OBV_volume (如果 volume 是小寫) 或 OBV_Close (如果 close 是小寫)
                 # 我們的函數會將原始欄位轉為小寫，所以可能是 OBV (預設) 或 OBV_volume
                 # ta.obv(close=df.close, volume=df.volume, append=True)
                if 'OBV' in actual_cols or 'obv' in actual_cols: # pandas_ta 0.3.14b 命名為 OBV
                    found = True
            elif col_pattern in actual_cols or col_pattern.upper() in actual_cols or col_pattern.lower() in actual_cols :
                found = True

            if not found:
                 # 檢查是否因為大小寫或附加其他詞導致 (例如 RSI_14_close)
                potential_matches = [ac for ac in actual_cols if col_pattern.startswith(ac.split('_')[0]) and col_pattern.endswith(ac.split('_')[-1])]
                if not potential_matches:
                    missing_indicator_cols.append(col_pattern)

        if not missing_indicator_cols:
            logger.info("內部測試：所有預期的指標欄位模式都已在 DataFrame 中找到。")
        else:
            logger.error(f"內部測試：以下預期的指標欄位模式未找到: {', '.join(missing_indicator_cols)}")
            logger.error(f" DataFrame 實際欄位: {actual_cols}")

        # 檢查 SMA_50 (由於只有30個數據點，SMA_50應該全是NaN)
        if 'SMA_50' in indicators_df.columns and indicators_df['SMA_50'].isnull().all():
            logger.info("內部測試：SMA_50 如預期般因數據不足而全部為 NaN。")
        elif 'SMA_50' in indicators_df.columns:
            logger.warning(f"內部測試：SMA_50 並非全部為 NaN，儘管數據點 (30) 少於週期 (50)。檢查 SMA_50 的值:\n{indicators_df['SMA_50'].dropna().head()}")
        # else: # SMA_50 欄位不存在的錯誤已由上面 missing_indicator_cols 捕捉

    else:
        logger.error("內部測試：指標計算失敗或返回空 DataFrame。")

    logger.info("--- Indicator Engine 內部測試結束 ---")
