#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import threading
import time
from pyngrok import ngrok, conf
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

def install_dependencies():
    """安裝專案所需的 Python 依賴包。"""
    dependencies = [
        "Flask", "yfinance", "pandas", "numpy",
        "plotly", "requests", "pyngrok", "openpyxl" # Added openpyxl for NYFed Excel
    ]
    logger.info(f"開始安裝依賴：{', '.join(dependencies)}")
    try:
        for dep in dependencies:
            logger.info(f"正在安裝 {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", dep])
        logger.info("所有依賴項安裝成功。")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安裝依賴 {e.cmd} 時發生錯誤。返回碼: {e.returncode}")
        # Try to decode stderr, but don't fail if it's not decodable or None
        stderr_output = 'N/A'
        if e.stderr:
            try:
                stderr_output = e.stderr.decode()
            except Exception:
                stderr_output = '(無法解碼的錯誤輸出)'
        logger.error(f"錯誤輸出: {stderr_output}")
        return False
    except Exception as e:
        logger.error(f"安裝依賴時發生未預期錯誤: {e}")
        return False

def start_flask_app(host='127.0.0.1', port=5000):
    """在一個單獨的線程中啟動 Flask 應用程式。"""
    logger.info(f"準備在 {host}:{port} 啟動 Flask 應用程式...")

    if not os.path.exists("app.py"):
        logger.error("錯誤：找不到 app.py 檔案。無法啟動 Flask 應用。")
        return None

    flask_env = os.environ.copy()
    # FLASK_APP is not strictly necessary if app.py is structured to run itself
    # flask_env["FLASK_APP"] = "app:app"
    # FLASK_ENV is deprecated, FLASK_DEBUG=1 is preferred for development mode
    # flask_env["FLASK_DEBUG"] = "1"

    # It's better if app.py itself sets host='0.0.0.0' when run directly.
    # This function assumes app.py when executed will listen on the correct interface for ngrok.

    def run_server():
        logger.info("Flask 應用程式線程已啟動。")
        try:
            # Execute app.py, which should have `app.run(host='0.0.0.0', port=port)`
            # in its `if __name__ == '__main__':` block.
            proc = subprocess.Popen([sys.executable, "app.py"], env=flask_env)
            proc.wait() # Wait for the process to complete (e.g., if server stops or crashes)
            logger.info(f"Flask 應用程式進程已結束，返回碼: {proc.returncode}")
        except Exception as e_flask:
            logger.error(f"啟動或運行 Flask 伺服器時出錯: {e_flask}", exc_info=True)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info("Flask 應用程式啟動請求已發送至背景線程。")
    time.sleep(5) # Give Flask some time to start up
    return thread

def start_ngrok_tunnel(port=5000, authtoken=None):
    """啟動 ngrok 隧道並返回公開 URL。"""
    logger.info(f"準備為本地端口 {port} 啟動 ngrok 隧道...")
    try:
        if authtoken:
            ngrok.set_auth_token(authtoken)
            logger.info("已設置 ngrok 認證令牌。")

        # Disconnect any existing tunnels and kill ngrok processes
        for tunnel in ngrok.get_tunnels():
            ngrok.disconnect(tunnel.public_url)
            logger.info(f"已關閉現有的 ngrok 隧道: {tunnel.public_url}")
        ngrok.kill() # Ensure all ngrok processes are terminated
        logger.info("所有現有 ngrok 進程已嘗試終止。")
        time.sleep(2) # Brief wait to ensure resources are freed

        # Configure ngrok (e.g., region)
        # Note: conf.set_default() is a global configuration.
        # If running multiple ngrok instances with different configs, manage conf objects carefully.
        pyngrok_conf = conf.PyngrokConfig(region='jp') # Example: 'us', 'eu', 'ap', 'au', 'sa', 'jp', 'in'
        conf.set_default(pyngrok_conf)
        logger.info(f"ngrok 區域已嘗試設置為: {conf.get_default().region}")

        # Connect to ngrok
        public_url = ngrok.connect(port, proto="http", bind_tls=True).public_url
        logger.info(f"ngrok 隧道已成功建立！公開 URL: {public_url}")
        return public_url
    except Exception as e_ngrok:
        logger.error(f"啟動 ngrok 隧道時發生錯誤: {e_ngrok}", exc_info=True)
        error_str = str(e_ngrok).lower()
        if " limitada de conexões simultâneas" in error_str or \
           "account may not run more than 1 tunnel" in error_str or \
           "err_ngrok_108" in error_str or \
           "tunnel session failed: Your account is limited to 1 simultaneous ngrok agent session" in error_str:
            logger.error("ngrok 錯誤提示：您的 ngrok 帳戶可能達到了免費方案的並發隧道/代理會話限制。請檢查您的 ngrok 儀表板 (dashboard.ngrok.com) 並確保沒有其他正在運行的 ngrok 實例。")
        return None

def main():
    logger.info("=== Colab 應用程式啟動器開始 ===")

    # 步驟 1: 安裝依賴
    if not install_dependencies():
        logger.error("依賴安裝失敗。啟動中止。")
        print("\n❌ 依賴安裝失敗，請檢查日誌。啟動程序已中止。")
        return

    # 步驟 2: 啟動 Flask 應用
    flask_port = 5000 # Flask app should listen on this port on 0.0.0.0
    flask_thread = start_flask_app(port=flask_port) # Host is managed by app.py's app.run

    if not flask_thread or not flask_thread.is_alive():
        logger.error("Flask 應用程式未能成功啟動或線程未存活。啟動中止。")
        print("\n❌ Flask 應用程式啟動失敗，請檢查 app.py 是否配置為在 0.0.0.0 上監聽，以及是否有其他錯誤。啟動程序已中止。")
        # Attempt to clean up ngrok if it somehow started
        for tunnel in ngrok.get_tunnels(): ngrok.disconnect(tunnel.public_url)
        ngrok.kill()
        return

    logger.info(f"等待 Flask 應用程式在端口 {flask_port} 上啟動...")
    # Check if Flask is accessible locally (optional, advanced check)
    # For now, the time.sleep(5) in start_flask_app should be sufficient for startup.

    # 步驟 3: 啟動 ngrok 隧道
    ngrok_authtoken = os.environ.get("NGROK_AUTHTOKEN")
    if not ngrok_authtoken:
        logger.warning("未找到 NGROK_AUTHTOKEN 環境變數。如果您遇到 ngrok 連線問題或限制，請考慮設置此令牌。")
        # print("\n提示：如果您有 ngrok Authtoken，建議將其設置為環境變數 NGROK_AUTHTOKEN 以獲得更穩定的服務。")
        # print("您可以在 ngrok 儀表板 (https://dashboard.ngrok.com/get-started/your-authtoken) 找到您的 Authtoken。")
        # print("在 Colab 中，您可以使用左側的「密鑰」圖標添加名為 NGROK_AUTHTOKEN 的密鑰。\n")

    public_url = start_ngrok_tunnel(port=flask_port, authtoken=ngrok_authtoken)

    if public_url:
        border = "="*70
        print(f"\n{border}")
        print("✅ 應用程式已成功啟動！")
        print(f"🌐 公開訪問 URL (HTTPS): {public_url}")
        print(f"🏠 Flask 應用程式應在本地 http://127.0.0.1:{flask_port}/dashboard 運行")
        print(border)
        print("\n注意：")
        print("  - 此 ngrok 隧道將在 Colab 會話結束時關閉。")
        print("  - Flask 應用程式正在背景線程中運行。")
        print("  - 要停止所有服務，請中斷此儲存格的執行 (通常是點擊停止按鈕)。")

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("偵測到用戶中斷 (KeyboardInterrupt)。正在關閉服務...")
        finally:
            logger.info("正在關閉 ngrok 隧道...")
            try:
                if public_url: ngrok.disconnect(public_url)
                ngrok.kill()
                logger.info("ngrok 隧道已關閉。")
            except Exception as e_ngrok_close:
                logger.error(f"關閉 ngrok 時發生錯誤: {e_ngrok_close}")
            logger.info("Flask 應用程式線程 (守護線程) 將隨主線程結束。")
    else:
        logger.error("未能獲取 ngrok 公開 URL。請檢查 ngrok 相關日誌。")
        print("\n❌ 啟動 ngrok 隧道失敗。無法提供公開 URL。請檢查日誌。")
        print("   可能的原因包括：")
        print("   - ngrok 服務本身的問題或區域不可用。")
        print("   - 網路連線問題或防火牆限制。")
        print("   - ngrok 免費帳戶的並發隧道/代理會話限制 (通常為1個)。")
        print("     請檢查 ngrok.com 上的帳戶狀態，並確保沒有其他 ngrok 實例正在運行。")
        print("   - 如果之前有運行的 ngrok 實例未正確關閉，也可能導致問題。")

    logger.info("=== Colab 應用程式啟動器結束 ===")

if __name__ == "__main__":
    main()
