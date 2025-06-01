# test_screener.py
import sys
import os

# 將 src 目錄添加到 Python 路徑中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src import stock_screener
    from src import logger_setup
    from src import config_manager # 主要用於可能的配置讀取，雖然 screener 內部會做
    from src import db_cache_manager # 用於設定全域快取
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保 test_screener.py 與 src 目錄在同一層級，或 src 目錄已正確添加到 PYTHONPATH。")
    sys.exit(1)

# 設定 logger
logger = logger_setup.setup_logger()

def run_screener_test():
    """
    執行股票篩選器功能的測試。
    """
    logger.info("--- 開始執行 Stock Screener 測試腳本 ---")

    # 步驟 1: 啟用 API 快取 (確保 fetcher 和 screener 中的 load_or_fetch 能利用快取)
    logger.info("步驟 1: 設定全域 API 快取...")
    db_cache_manager.setup_global_cache()
    logger.info("全域 API 快取已啟用。")

    # 步驟 2: 執行股票篩選
    logger.info("步驟 2: 調用 stock_screener.screen_stocks()...")
    high_risk_stocks_report = stock_screener.screen_stocks()

    # 步驟 3: 打印篩選結果
    logger.info("步驟 3: 打印篩選結果...")
    if high_risk_stocks_report:
        print("\n--- 篩選出的潛在高風險股票及其原因 ---")
        for symbol, reasons in high_risk_stocks_report.items():
            print(f"\n股票代碼: {symbol}")
            for reason_idx, reason_desc in enumerate(reasons):
                print(f"  風險 {reason_idx + 1}: {reason_desc}")
    else:
        print("\n--- 未篩選出符合高風險條件的股票 ---")
        logger.info("篩選完成，未發現顯著高風險股票。")

    logger.info("--- Stock Screener 測試腳本結束 ---")

if __name__ == "__main__":
    run_screener_test()
    logger.info("\n測試腳本執行完畢。請檢查控制台輸出和日誌檔案 ('MyFinancialSystem/logs/') 以獲取詳細資訊。")
    logger.info("注意：首次運行時，數據獲取和處理可能需要較長時間。後續運行應利用快取。")
