# src/db_cache_manager.py
import requests_cache
import os
from src import config_manager
from src import logger_setup

# 獲取 logger
logger = logger_setup.setup_logger() # 使用先前配置的 logger

_cache_installed = False

def setup_global_cache():
    """
    設定全域 requests 快取。

    此函數會從設定檔讀取快取設定，並使用 requests_cache.install_cache()
    來為所有使用標準 'requests' 庫的 HTTP 請求啟用快取。
    快取路徑的目錄將會被自動創建 (如果不存在)。

    快取設定從 config_manager 讀取:
    - cache_settings.api_cache_database_path: SQLite 資料庫檔案的路徑。
    - cache_settings.default_cache_duration_hours: 快取過期時間 (小時)。

    注意：此函數僅需執行一次。
    """
    global _cache_installed
    if _cache_installed:
        logger.debug("全域快取已經設定。")
        return

    logger.info("開始設定全域 API 快取。")

    # 從 config_manager 獲取快取設定
    db_path_setting = config_manager.get_setting('cache_settings', 'api_cache_database_path')
    duration_hours = config_manager.get_setting('cache_settings', 'default_cache_duration_hours', 12)

    if not db_path_setting:
        logger.error("錯誤：API 快取資料庫路徑 (api_cache_database_path) 未在設定中找到。無法設定全域快取。")
        return

    # 將小時轉換為秒
    expire_after_seconds = duration_hours * 60 * 60
    logger.info(f"API 快取有效期設定為: {duration_hours} 小時 ({expire_after_seconds} 秒)。")

    # 從路徑設定中提取目錄和檔案名稱，cache_name 不需要副檔名
    db_dir = os.path.dirname(db_path_setting)
    db_filename = os.path.basename(db_path_setting)
    cache_name_stem, _ = os.path.splitext(db_filename) # 去掉 .sqlite, e.g., 'api_cache'

    # requests_cache 的 cache_name 參數是檔案路徑去掉副檔名
    # 例如 MyFinancialSystem/main_data/api_cache/api_cache
    cache_name_with_dir = os.path.join(db_dir, cache_name_stem)

    logger.info(f"全域 API 快取資料庫路徑設定為: {db_path_setting} (cache_name for requests_cache: {cache_name_with_dir})")

    # 確保快取目錄存在
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"快取目錄 {db_dir} 已成功創建。")
        except Exception as e:
            logger.error(f"創建快取目錄 {db_dir} 失敗: {e}。全域快取可能無法正常工作。")
            return
    else:
        logger.debug(f"快取目錄 {db_dir} 已存在。")

    try:
        requests_cache.install_cache(
            cache_name=cache_name_with_dir, # 例如 'MyFinancialSystem/main_data/api_cache/api_cache'
            backend='sqlite',
            expire_after=expire_after_seconds,
            # match_headers=True, # 可選：如果 API 回應依賴請求頭，則設為 True
            # allowable_methods=['GET', 'POST'] # yfinance 主要用 GET
        )
        _cache_installed = True
        logger.info(f"全域 requests 快取已成功安裝。快取資料庫: {db_path_setting}")

        if requests_cache.is_installed():
            logger.info("requests_cache.is_installed() 確認快取已啟用。")
        else:
            logger.warning("requests_cache.is_installed() 指示快取未啟用，這不應該發生。")

    except Exception as e:
        logger.error(f"設定全域 requests_cache 時發生錯誤: {e}", exc_info=True)

if __name__ == '__main__':
    # 簡單測試 db_cache_manager
    print("--- DB Cache Manager (全域快取) 測試 ---")
    logger.info("開始測試 DB Cache Manager (全域快取設定)。")

    # 執行設定
    setup_global_cache()

    if _cache_installed and requests_cache.is_installed():
        logger.info("全域快取設定成功。")

        # 測試發送一個請求 (需要網路)
        # 注意：這裡需要導入 requests 才能測試，或者依賴其他使用 requests 的模組
        try:
            import requests
            test_url = 'https://httpbin.org/get'

            # 清除特定 URL 的快取 (如果存在)，以確保第一次是網路請求
            # requests_cache.remove_expired_responses() # 清除所有過期快取
            # 如果要確保 httpbin.org/get 被重新請求，可以這樣：
            # if hasattr(requests_cache.get_cache(), 'delete_url'):
            #     requests_cache.get_cache().delete_url(test_url)

            logger.info(f"第一次請求 URL (應從網路): {test_url}")
            response1 = requests.get(test_url)
            logger.info(f"請求1狀態: {response1.status_code}, 是否來自快取: {getattr(response1, 'from_cache', False)}")

            logger.info(f"第二次請求 URL (應從快取): {test_url}")
            response2 = requests.get(test_url)
            logger.info(f"請求2狀態: {response2.status_code}, 是否來自快取: {getattr(response2, 'from_cache', False)}")

            if response2.from_cache:
                logger.info("成功：第二次請求從快取中獲取。")
            else:
                logger.error("失敗：第二次請求未從快取中獲取。請檢查設定。")

        except ImportError:
            logger.warning("'requests' 模組未找到，無法執行基於 requests 的快取測試。")
        except Exception as e:
            logger.error(f"測試請求時發生錯誤: {e}")
    else:
        logger.error("全域快取設定失敗。")

    # 檢查快取檔案是否存在
    db_file_path = config_manager.get_setting('cache_settings', 'api_cache_database_path')
    if db_file_path and os.path.exists(db_file_path):
        logger.info(f"快取資料庫檔案 {db_file_path} 已存在。")
    elif db_file_path:
        logger.warning(f"快取資料庫檔案 {db_file_path} 未找到 (可能因請求未發生或設定失敗)。")

    logger.info("DB Cache Manager (全域快取) 測試結束。")
    print("--- DB Cache Manager (全域快取) 測試結束 ---")
