# src/logger_setup.py
import logging
import logging.handlers
import os
from src import config_manager # 恢復導入 config_manager

_logger_configured_prefix = None # 用於跟蹤 logger 是否已按特定前綴配置

def setup_logger(force_reconfigure=False):
    """
    設定並返回一個日誌記錄器 (logger)。

    日誌記錄器會根據 config/strategy_config.yaml 中的設定，
    將日誌同時輸出到控制台和按日期滾動的檔案。
    檔案會存放在設定中指定的模擬路徑下。

    返回:
        logging.Logger: 配置好的日誌記錄器物件。
    """
    global _logger_configured_prefix

    # 從 config_manager 獲取日誌設定
    log_dir = config_manager.get_setting('logging_settings', 'log_file_directory', 'MyFinancialSystem/logs/')
    log_prefix = config_manager.get_setting('logging_settings', 'log_file_name_prefix', 'financial_system_log')
    console_level_str = config_manager.get_setting('logging_settings', 'console_log_level', 'INFO')
    file_level_str = config_manager.get_setting('logging_settings', 'file_log_level', 'DEBUG')

    current_logger = logging.getLogger(log_prefix)

    # 如果 logger 已按此前綴配置過，並且不是強制重新配置，則直接返回現有 logger
    if _logger_configured_prefix == log_prefix and current_logger.hasHandlers() and not force_reconfigure:
        return current_logger

    # 清理該 logger 上可能已存在的 handlers，以防重複（特別是 force_reconfigure 時）
    if current_logger.hasHandlers():
        for handler in current_logger.handlers[:]: # 使用副本進行迭代和移除
            current_logger.removeHandler(handler)
            handler.close()

    # 將日誌級別字串轉換為 logging 模組的常數
    console_level = getattr(logging, console_level_str.upper(), logging.INFO)
    file_level = getattr(logging, file_level_str.upper(), logging.DEBUG)

    # 確保日誌目錄存在
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
            print(f"日誌目錄 {log_dir} 已創建 (by logger_setup)。") # 初始創建時可用 print
        except Exception as e:
            print(f"創建日誌目錄 {log_dir} 失敗: {e}。將使用當前目錄。")
            log_dir = "."

    current_logger.setLevel(logging.DEBUG) # 設定 logger 的最低處理級別為 DEBUG

    # 設定日誌格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(message)s (%(filename)s:%(lineno)d)'
    )

    # 設定控制台處理器 (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    current_logger.addHandler(console_handler)

    # 設定檔案處理器 (TimedRotatingFileHandler)
    log_file_path = os.path.join(log_dir, f"{log_prefix}.log")

    try:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file_path,
            when='D',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d"
        current_logger.addHandler(file_handler)
    except Exception as e:
        current_logger.error(f"設定檔案日誌處理器到 '{log_file_path}' 失敗: {e}", exc_info=True)

    _logger_configured_prefix = log_prefix
    current_logger.info(f"日誌系統已為前綴 '{log_prefix}' 設定。控制台級別: {console_level_str}, 檔案級別: {file_level_str}。日誌檔案路徑: {log_file_path}")

    return current_logger

if __name__ == '__main__':
    # 簡單測試 logger_setup
    print("--- Logger Setup (恢復使用 config_manager) 測試 ---")

    # 首次設定 logger
    logger_instance = setup_logger(force_reconfigure=True) # 強制重新配置

    if logger_instance:
        logger_instance.debug("這是一條 DEBUG 資訊。 (應寫入檔案)")
        logger_instance.info("這是一條 INFO 資訊。 (應寫入檔案和控制台)")
        logger_instance.warning("這是一條 WARNING 資訊。 (應寫入檔案和控制台)")

        # 測試重複獲取
        logger_instance_again = setup_logger()
        if logger_instance_again is logger_instance:
            logger_instance.info("再次調用 setup_logger() 返回了同一個 logger 實例。")
            if len(logger_instance.handlers) == 2: # 假設 console + file handler
                logger_instance.info("Handler 數量符合預期 (2)。")
            else:
                logger_instance.warning(f"Handler 數量 ({len(logger_instance.handlers)}) 不符合預期 (應為 2)。")
        else:
            logger_instance.error("再次調用 setup_logger() 未返回同一個 logger 實例！")

        # 從 config_manager 獲取路徑以提示檢查 (如果 config_manager 可用)
        try:
            log_dir_check = config_manager.get_setting('logging_settings', 'log_file_directory')
            log_prefix_check = config_manager.get_setting('logging_settings', 'log_file_name_prefix')
            print(f"\n請檢查控制台輸出以及位於 '{log_dir_check}' 目錄下的日誌檔案。")
            print(f"預期日誌檔案名稱類似: {log_prefix_check}.log 或帶有日期後綴。")
        except Exception as e:
            print(f"無法從 config_manager 獲取日誌路徑進行檢查提示: {e}")
            print(f"請手動檢查 'MyFinancialSystem/logs/' 目錄。")

    else:
        print("Logger 設定失敗。")

    print("\n--- Logger Setup (恢復使用 config_manager) 測試結束 ---")
