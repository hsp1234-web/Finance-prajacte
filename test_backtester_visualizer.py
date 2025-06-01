# test_backtester_visualizer.py
import sys
import os
import pandas as pd
import json # 用於處理可能的 AI JSON 回應

# 將 src 目錄添加到 Python 路徑中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.data_fetchers import yfinance_fetcher
    from src import data_processor
    from src import indicator_engine
    from src import strategy_visualizer
    from src import simple_backtester
    from src import logger_setup
    from src import config_manager
    from src import db_cache_manager
    from src import ai_analyzer # 主要用於獲取模擬建議
except ImportError as e:
    print(f"導入模組時發生錯誤: {e}")
    print("請確保所有必要的 src 模組存在且 Python 環境配置正確。")
    sys.exit(1)

# 設定 logger
logger = logger_setup.setup_logger()

def run_tests():
    """
    執行策略可視化和簡單回測器的整合測試。
    """
    logger.info("--- 開始執行 Visualizer 與 Backtester 整合測試 ---")

    # 步驟 0: 初始化設定和快取
    db_cache_manager.setup_global_cache()
    logger.info("全域 API 快取已啟用。")

    # 測試參數
    symbol_to_test = config_manager.get_setting("market_settings", "us_stock_pool", ["AAPL"])[1] # AAPL
    start_date = "2022-01-01" # 至少需要一年以上的數據以計算 SMA200 和進行有意義的回測
    end_date = "2023-12-31"   # 兩年數據

    logger.info(f"將使用股票代碼 '{symbol_to_test}'，數據期間: {start_date} 至 {end_date}。")

    # 1. 準備數據 (獲取 -> 處理 -> 計算指標)
    logger.info(f"[{symbol_to_test}] 步驟 1: 準備數據...")
    raw_df = yfinance_fetcher.fetch_ohlcv(symbol_to_test, start_date, end_date)
    if raw_df is None or raw_df.empty:
        logger.error(f"[{symbol_to_test}] 無法獲取 OHLCV 數據，中止測試。")
        return

    processed_df = data_processor.process_ohlcv_data(raw_df, symbol_to_test)
    if processed_df is None or processed_df.empty:
        logger.error(f"[{symbol_to_test}] 數據處理失敗，中止測試。")
        return

    df_with_indicators = indicator_engine.calculate_technical_indicators(processed_df)
    if df_with_indicators is None or df_with_indicators.empty:
        logger.error(f"[{symbol_to_test}] 技術指標計算失敗，中止測試。")
        return
    logger.info(f"[{symbol_to_test}] 數據準備完成，包含指標的 DataFrame 形狀: {df_with_indicators.shape}")


    # 2. 測試 Strategy Visualizer
    logger.info(f"\n[{symbol_to_test}] 步驟 2: 測試 Strategy Visualizer...")
    if strategy_visualizer.plotly_available:
        indicators_to_plot = ['SMA_20', 'SMA_50', 'SMA_200', 'RSI_14'] # 確保這些指標已在 indicator_engine 中計算
        # 篩選出實際存在於 DataFrame 中的指標進行繪圖
        plot_cols = [col for col in indicators_to_plot if col in df_with_indicators.columns]

        fig = strategy_visualizer.plot_ohlcv_with_indicators(df_with_indicators, symbol_to_test, indicators_to_plot=plot_cols)
        if fig:
            logger.info(f"[{symbol_to_test}] plot_ohlcv_with_indicators 成功生成 Plotly Figure 物件。")
            try:
                # 嘗試將圖表保存為 HTML (在無頭環境中無法直接 show)
                html_file = f"{symbol_to_test}_plot_test.html"
                fig.write_html(html_file)
                logger.info(f"[{symbol_to_test}] 圖表已成功保存為 HTML 檔案: {html_file}")
                # 注意：在某些受限環境中，寫檔案可能失敗。
            except Exception as e:
                logger.error(f"[{symbol_to_test}] 保存圖表到 HTML 失敗: {e}", exc_info=True)
        else:
            logger.error(f"[{symbol_to_test}] plot_ohlcv_with_indicators 未能生成 Figure 物件。")
    else:
        logger.warning(f"[{symbol_to_test}] Plotly 套件不可用，跳過可視化測試。")

    # 3. 測試 Simple Backtester
    logger.info(f"\n[{symbol_to_test}] 步驟 3: 測試 Simple Backtester...")

    # 獲取模擬 AI 建議
    # ai_analyzer 設定為 mock_api_calls=True
    logger.info(f"[{symbol_to_test}] 從 ai_analyzer (模擬模式) 獲取交易建議...")
    # 這裡的 prompt 內容不重要，因為是模擬回應
    mock_prompt_for_suggestions = f"請為股票 {symbol_to_test} 生成交易建議。"
    ai_response_str = ai_analyzer.generate_text_from_prompt(mock_prompt_for_suggestions)

    simulated_suggestions = []
    if ai_response_str and "模擬成功回應" in ai_response_str:
        try:
            # 提取 JSON 部分並解析
            json_part_str = ai_response_str.split(" - ", 1)[1]
            response_data = json.loads(json_part_str)
            # 假設模擬回應的 trading_suggestions 是一個列表
            if "trading_suggestions" in response_data and isinstance(response_data["trading_suggestions"], list):
                # 需要將模擬建議轉換為 backtester 期望的格式
                # {"date": "YYYY-MM-DD", "symbol": "XYZ", "action": "BUY"|"SELL"|"HOLD", "reason": "..."}
                # 模擬的回應可能沒有日期和股票代碼，或者格式不完全匹配，這裡需要適配或使用內部模擬
                logger.warning(f"[{symbol_to_test}] AI Analyzer 模擬回應的建議格式可能與回測器不完全匹配，將使用回測器內部模擬建議。")
                # simulated_suggestions = convert_ai_response_to_backtest_format(response_data["trading_suggestions"], symbol_to_test, df_with_indicators.index)
                simulated_suggestions = [] # 置空，觸發回測器內部模擬邏輯
            else:
                logger.warning(f"[{symbol_to_test}] AI Analyzer 模擬回應中未找到有效的 'trading_suggestions' 列表，將使用回測器內部模擬建議。")
        except Exception as e:
            logger.error(f"[{symbol_to_test}] 解析 AI Analyzer 模擬回應失敗: {e}。將使用回測器內部模擬建議。")
            simulated_suggestions = [] # 置空以使用內部模擬
    else:
        logger.warning(f"[{symbol_to_test}] 未能從 AI Analyzer 獲取有效的模擬回應，將使用回測器內部模擬建議。")

    # 如果 simulated_suggestions 為空，simple_backtester 會使用其內部的硬編碼模擬建議
    backtest_results = simple_backtester.run_simple_backtest(symbol_to_test, df_with_indicators, ai_suggestions=simulated_suggestions)

    if backtest_results and "error" not in backtest_results:
        logger.info(f"[{symbol_to_test}] Simple Backtester 執行完成。績效指標:")
        print(f"\n--- [{symbol_to_test}] 回測績效摘要 ---")
        for key, value in backtest_results.items():
            if key != "每日投資組合價值序列": # 不打印整個 Series
                print(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")
        # 可以選擇將每日價值序列保存到檔案或繪圖 (如果 plotly 可用)
        # portfolio_ts = backtest_results.get("每日投資組合價值序列")
        # if plotly_available and portfolio_ts is not None:
        #     fig_portfolio = go.Figure(go.Scatter(x=portfolio_ts.index, y=portfolio_ts, name="投資組合價值"))
        #     fig_portfolio.update_layout(title=f"{symbol_to_test} 投資組合價值變化", xaxis_title="日期", yaxis_title="價值")
        #     portfolio_html_file = f"{symbol_to_test}_portfolio_test.html"
        #     fig_portfolio.write_html(portfolio_html_file)
        #     logger.info(f"[{symbol_to_test}] 投資組合價值圖表已保存到: {portfolio_html_file}")

    elif backtest_results and "error" in backtest_results:
        logger.error(f"[{symbol_to_test}] Simple Backtester 執行出錯: {backtest_results['error']}")
    else:
        logger.error(f"[{symbol_to_test}] Simple Backtester 未返回結果。")

    logger.info("\n--- Visualizer 與 Backtester 整合測試結束 ---")

if __name__ == "__main__":
    run_tests()
    logger.info("\n測試腳本執行完畢。請檢查控制台輸出和日誌檔案。")
    logger.info("如果 Plotly 可用，應已生成 HTML 圖表檔案 (例如 AAPL_plot_test.html)。")
