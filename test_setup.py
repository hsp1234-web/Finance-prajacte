# test_setup.py
import sys
import os

# 將 src 目錄添加到 Python 路徑中，以便導入模組
# 這樣無論從哪個目錄執行 test_setup.py，都能找到 src 下的模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src import config_manager
    from src import logger_setup
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保 test_setup.py 與 src 目錄在同一層級，或者 src 目錄已正確添加到 PYTHONPATH。")
    sys.exit(1)

def run_tests():
    """
    執行設定模組和日誌模組的整合測試。
    """
    print("--- 開始執行整合測試 ---")

    # --- 測試 Config Manager ---
    print("\n[測試 Config Manager]")
    api_key = config_manager.get_api_key("google_gemini_api_key")
    if api_key:
        print(f"成功讀取 API 金鑰 (google_gemini_api_key): ...{api_key[-10:]}") # 只顯示部分金鑰
    else:
        print("未能讀取 API 金鑰 (google_gemini_api_key)。")

    market = config_manager.get_setting("market_settings", "default_stock_market")
    if market:
        print(f"成功讀取市場設定 (default_stock_market): {market}")
    else:
        print("未能讀取市場設定 (default_stock_market)。")

    log_dir_config = config_manager.get_setting("logging_settings", "log_file_directory")
    if log_dir_config:
        print(f"成功讀取日誌目錄設定 (log_file_directory): {log_dir_config}")
    else:
        print("未能讀取日誌目錄設定 (log_file_directory)。")

    # --- 測試 Logger Setup ---
    print("\n[測試 Logger Setup]")
    # 設定日誌記錄器
    try:
        logger = logger_setup.setup_logger()
        if logger:
            print("Logger 成功設定。")

            # 發送一些測試日誌訊息 (繁體中文)
            logger.debug("這是一條來自 test_setup.py 的 DEBUG 測試訊息。")
            logger.info("這是一條來自 test_setup.py 的 INFO 測試訊息。")
            logger.warning("這是一條來自 test_setup.py 的 WARNING 測試訊息。")
            logger.error("這是一條來自 test_setup.py 的 ERROR 測試訊息。")
            logger.critical("這是一條來自 test_setup.py 的 CRITICAL 測試訊息。")

            print(f"\n日誌訊息已發送。請檢查控制台輸出以及日誌檔案。")
            log_file_path_expected = os.path.join(
                log_dir_config or "MyFinancialSystem/logs/",
                (config_manager.get_setting("logging_settings", "log_file_name_prefix") or "financial_system_log") + ".log"
            )
            print(f"預期日誌檔案主檔案路徑 (可能會帶日期後綴): {log_file_path_expected}")

            # 檢查日誌檔案是否真的被創建 (簡易檢查)
            # 注意：TimedRotatingFileHandler 可能會立即加上日期後綴
            # 我們檢查基礎路徑下的任何匹配前綴的日誌檔案
            actual_log_dir = log_dir_config or "MyFinancialSystem/logs/"
            log_prefix = config_manager.get_setting("logging_settings", "log_file_name_prefix") or "financial_system_log"

            if os.path.exists(actual_log_dir):
                found_log_files = [f for f in os.listdir(actual_log_dir) if f.startswith(log_prefix) and f.endswith(".log")]
                if found_log_files:
                    print(f"在 '{actual_log_dir}' 中找到日誌檔案: {', '.join(found_log_files)}")
                else:
                    print(f"警告: 在 '{actual_log_dir}' 中未直接找到名為 '{log_prefix}.log' 的日誌檔案。TimedRotatingFileHandler 可能已添加日期後綴。")
                    # 列出所有檔案以供調試
                    all_files_in_log_dir = os.listdir(actual_log_dir)
                    if all_files_in_log_dir:
                         print(f"目錄 '{actual_log_dir}' 中的檔案: {', '.join(all_files_in_log_dir)}")
                    else:
                        print(f"目錄 '{actual_log_dir}' 為空。")

            else:
                print(f"警告: 日誌目錄 '{actual_log_dir}' 未找到。")


        else:
            print("錯誤：Logger 設定失敗。")
            # 如果 logger 設定失敗，後續的日誌相關檢查可能無意義

    except Exception as e:
        print(f"設定或使用 Logger 時發生嚴重錯誤: {e}")
        import traceback
        traceback.print_exc()


    print("\n--- 整合測試結束 ---")

if __name__ == "__main__":
    # 確保 config_manager 加載最新的配置
    # 這在模塊級別已經通過 _config = load_config() 完成了
    # 但如果我們希望在運行測試前強制重新加載（例如，如果配置文件可能已更改），
    # 則需要一個 reload_config() 函數。目前設計中不需要。

    run_tests()

    # 提示使用者檢查日誌檔案
    print("\n請手動檢查 'MyFinancialSystem/logs/' 目錄下的日誌檔案內容，")
    print("以及控制台的輸出，以確認日誌級別和格式是否正確。")
