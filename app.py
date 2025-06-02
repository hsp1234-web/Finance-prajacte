from flask import Flask, render_template, jsonify
import main_app_builder # 導入我們修改後的模組
import pandas as pd # Flask 路由中可能需要處理 DataFrame
import numpy as np # 同上
import logging
from datetime import datetime # For current year in footer
import os # For port environment variable

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Pre-computation of data on app startup ---
logger.info("Flask 應用程式：開始預先計算初始數據...")
PRECOMPUTED_AAPL_TEXT, PRECOMPUTED_AAPL_PLOTLY_JSON = ("", "") # Initialize
try:
    PRECOMPUTED_AAPL_TEXT, PRECOMPUTED_AAPL_PLOTLY_JSON = main_app_builder.analyze_stock_options("AAPL")
    logger.info(f"Flask 應用程式：成功預計算 AAPL 選擇權數據。")
except Exception as e:
    logger.error(f"Flask 應用程式：預計算 AAPL 選擇權數據失敗: {e}", exc_info=True)
    PRECOMPUTED_AAPL_TEXT = "錯誤：無法加載 AAPL 選擇權分析數據。"
    PRECOMPUTED_AAPL_PLOTLY_JSON = ""

latest_vix_value_str_init = "--"
vix_df_init = pd.DataFrame()
try:
    vix_data_map_init = main_app_builder.get_yfinance_data(['^VIX'], period="5d")
    vix_df_init = vix_data_map_init.get('^VIX', pd.DataFrame())
    if not vix_df_init.empty:
        latest_vix_close = vix_df_init['Close'].iloc[-1]
        latest_vix_value_str_init = f"{latest_vix_close:.2f}"
        logger.info(f"Flask 應用程式：成功預計算 VIX 指數: {latest_vix_value_str_init}")
    else:
        logger.warning("Flask 應用程式：預計算 VIX 指數時獲得空 DataFrame。")
except Exception as e:
    logger.error(f"Flask 應用程式：預計算 VIX 指數失敗: {e}", exc_info=True)

stress_index_value_str_init = "--"; stress_index_status_str_init = "數據不足 (啟動時)"
try:
    data_for_stress_index_init = pd.DataFrame()
    if not vix_df_init.empty:
        data_for_stress_index_init['VIX_Close'] = vix_df_init['Close']
    stress_index_value_str_init, stress_index_status_str_init = main_app_builder.calculate_dealer_stress_index(data_for_stress_index_init)
    logger.info(f"Flask 應用程式：成功預計算壓力指數: {stress_index_value_str_init}, 狀態: {stress_index_status_str_init}")
except Exception as e:
    logger.error(f"Flask 應用程式：預計算壓力指數失敗: {e}", exc_info=True)
logger.info("Flask 應用程式：初始數據預計算完成。")

@app.route('/')
@app.route('/dashboard')
def dashboard():
    template_data = {
        "title": "金融市場分析與風險評估系統 MVP",
        "current_year": datetime.now().year,
        "initial_vix_value": latest_vix_value_str_init,
        "initial_stress_index_value": stress_index_value_str_init,
        "initial_stress_index_status": stress_index_status_str_init,
        "aapl_analysis_text": PRECOMPUTED_AAPL_TEXT,
        "aapl_plotly_json": PRECOMPUTED_AAPL_PLOTLY_JSON,
    }
    logger.info("渲染儀表板模板...")
    return render_template('dashboard.html', **template_data)

@app.route('/api/stock_options/<string:ticker_symbol>')
def api_stock_options(ticker_symbol):
    logger.info(f"API請求：開始為 {ticker_symbol} 分析選擇權...")
    if not ticker_symbol:
        logger.warning("API請求：未提供股票代號。")
        return jsonify({"error": "未提供股票代號"}), 400

    try:
        analysis_text, plotly_json_str = main_app_builder.analyze_stock_options(ticker_symbol.upper())

        response_data = {
            "analysis_text": analysis_text,
            "plotly_json": plotly_json_str if plotly_json_str else ""
        }

        if "錯誤：" in analysis_text or not plotly_json_str:
            logger.warning(f"API請求：為 {ticker_symbol} 分析選擇權時返回部分錯誤或無圖表: {analysis_text[:200]}")
            if "錯誤：" in analysis_text and not plotly_json_str :
                 response_data["error_message"] = analysis_text
            elif not plotly_json_str:
                 response_data["warning_message"] = "成功獲取分析文字，但無法生成圖表。"

        logger.info(f"API請求：成功為 {ticker_symbol} 生成選擇權分析。")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"API請求：為 {ticker_symbol} 分析選擇權時發生嚴重錯誤：{e}", exc_info=True)
        return jsonify({"error": f"處理 {ticker_symbol} 請求時發生未預期錯誤。", "analysis_text": f"處理 {ticker_symbol} 請求時發生未預期錯誤: {str(e)}", "plotly_json":"" }), 500

if __name__ == '__main__':
    # 從環境變數獲取端口，預設為 5000 (與 run_colab_app.py 中一致)
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Flask 應用程式直接通過 app.py 啟動，將在 0.0.0.0:{port} 上運行。")
    # 使用 host='0.0.0.0' 使其在 Colab 或其他容器環境中可被外部訪問
    # debug=False 是生產環境或共享環境的更安全選擇
    app.run(debug=False, host='0.0.0.0', port=port)
