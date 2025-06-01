# run_web_app.py
from src.web_app_interface import app, server # 導入 app 和 server
from src.logger_setup import setup_logger
from src.db_cache_manager import setup_global_cache # 確保快取在應用啟動前設定
from src.config_manager import get_setting # 用於讀取應用設定

if __name__ == '__main__':
    logger = setup_logger()

    logger.info("初始化全域 API 快取 (如果尚未進行)...")
    setup_global_cache() # 初始化快取，以防未來頁面需要即時獲取數據

    logger.info("從設定檔讀取 Dash 應用程式設定...")
    app_host = get_setting('dash_app_settings', 'host', '0.0.0.0')
    # get_setting 返回的值可能是字串，포트需要是整數
    app_port_str = get_setting('dash_app_settings', 'port', '8050')
    try:
        app_port = int(app_port_str)
    except ValueError:
        logger.error(f"設定檔中的 dash_app_settings.port ('{app_port_str}') 不是一個有效的整數，將使用預設值 8050。")
        app_port = 8050

    # debug_mode 應該是布林值
    # get_setting 會直接返回 YAML 中定義的布林值 (例如 True/False)
    # 或者如果未定義，則返回預設值 (此處設為 True)
    debug_mode = get_setting('dash_app_settings', 'debug_mode', True)
    if not isinstance(debug_mode, bool):
        # 如果設定檔中意外地寫了字串如 "true" 或 "false"
        logger.warning(f"設定檔中的 dash_app_settings.debug_mode ('{debug_mode}') 不是標準的布林值。將嘗試轉換。")
        debug_mode = str(debug_mode).lower() in ['true', '1', 't', 'yes']

    logger.info(f"準備啟動 Dash Plotly 前端伺服器於 http://{app_host}:{app_port}/")
    logger.info(f"除錯模式 (Debug Mode): {debug_mode}")

    try:
        app.run(debug=debug_mode, host=app_host, port=app_port) # Dash 2.x+ 使用 app.run()
    except Exception as e:
        logger.error(f"啟動 Dash 伺服器時發生錯誤: {e}", exc_info=True)
        # 在某些環境 (如 Colab 或受限的 Docker)，直接綁定 0.0.0.0 可能會失敗
        # 或者端口已被占用
        if "Address already in use" in str(e) or "cannot assign requested address" in str(e):
            logger.warning("端口可能已被佔用或地址無法綁定。請檢查端口狀態或嘗試其他端口。")
        raise # 重新拋出錯誤，以便外部可以看到失敗原因
