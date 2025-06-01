# src/ai_analyzer.py
import os
import json
from src import config_manager
from src import logger_setup

# 獲取 logger
logger = logger_setup.setup_logger()

# 嘗試導入 Google Generative AI SDK
try:
    import google.generativeai as genai
    google_ai_sdk_available = True
    logger.info("成功導入 Google Generative AI SDK。")
except ImportError:
    google_ai_sdk_available = False
    logger.warning("警告：Google Generative AI SDK (google-generativeai) 未安裝或無法導入。")
    logger.warning("AI 分析功能將受限或僅能使用模擬回應。請考慮安裝 'pip install google-generativeai'")
    genai = None # 將 genai 設為 None 以便後續檢查

_gemini_api_configured = False

def configure_gemini_api() -> bool:
    """
    配置 Google Gemini API 金鑰。

    從 config_manager 獲取 API 金鑰並配置 genai SDK。
    只應執行一次。

    返回:
        bool: 如果成功配置則返回 True，否則返回 False。
    """
    global _gemini_api_configured
    if _gemini_api_configured:
        logger.debug("Gemini API 已配置。")
        return True

    if not google_ai_sdk_available:
        logger.error("無法配置 Gemini API，因為 Google Generative AI SDK 不可用。")
        return False

    # service_name 'google_gemini' 會讓 config_manager 查找 GOOGLE_GEMINI_API_KEY 環境變數
    # 或 YAML 中的 'api_keys.google_gemini_api_key' (如果 get_api_key 中如此處理)
    # 我們在 config_manager 中將 service_name 'google_gemini_api_key' 映射到環境變數 GOOGLE_GEMINI_API_KEY
    # 這裡我們使用 'google_gemini_api_key' 作為 service name 傳給 config_manager
    api_key = config_manager.get_api_key('google_gemini_api_key')

    if not api_key or "YOUR_GEMINI_API_KEY" in api_key or "DUMMY_ENV_API_KEY" in api_key: # 檢查是否為預留值或測試值
        logger.critical(f"未能獲取有效的 Google Gemini API 金鑰。獲取到的金鑰 (或其一部分): '...{api_key[-10:] if api_key else 'N/A'}'")
        logger.critical("請確保 'GOOGLE_GEMINI_API_KEY' 環境變數已設定，或在 Colab Secrets 中提供，或在 .env 檔案中設定。")
        _gemini_api_configured = False # 明確標記配置失敗
        return False

    try:
        genai.configure(api_key=api_key)
        _gemini_api_configured = True
        logger.info("成功配置 Google Gemini API 金鑰。")
        return True
    except Exception as e:
        logger.error(f"配置 Google Gemini API 時發生錯誤: {e}", exc_info=True)
        _gemini_api_configured = False
        return False

# 在模組加載時嘗試配置 API
# configure_gemini_api() # 或者推遲到第一次調用 generate_text_from_prompt 時

def generate_text_from_prompt(prompt: str, model_name: str = None, temperature: float = None) -> str | None:
    """
    使用指定的 Prompt 通過 Gemini API 生成文本。

    參數:
        prompt (str): 要發送給模型的 Prompt。
        model_name (str, optional): 要使用的模型名稱。如果為 None，則從設定檔讀取預設模型。
        temperature (float, optional): 生成溫度。如果為 None，則從設定檔讀取預設溫度。

    返回:
        str | None: 模型生成的回應文本。如果發生錯誤或 API 未配置/不可用，則返回 None。
    """
    global _gemini_api_configured

    # 檢查是否啟用模擬 API 調用
    mock_api_calls = config_manager.get_setting('ai_analyzer_settings', 'mock_api_calls', False)
    if mock_api_calls:
        logger.info("模擬 API 調用已啟用。返回固定的模擬回應。")
        # 返回一個符合預期格式的模擬 JSON 字串或純文本
        mock_response_data = {
            "analysis_summary": "模擬市場分析：市場情緒謹慎，指數在區間波動。",
            "key_observations": ["模擬觀察點1：波動率指數VIX略有上升。", "模擬觀察點2：大型科技股表現平平。"],
            "outlook": "模擬展望：短期內可能持續盤整，需關注下周聯準會會議紀要。",
            "trading_suggestions": [
                {"suggestion_type": "觀望", "confidence": "中", "reasoning": "模擬理由：市場方向不明朗。"}
            ]
        }
        # return json.dumps(mock_response_data, ensure_ascii=False, indent=2)
        return f"模擬成功回應 for prompt: '{prompt[:50]}...' - {json.dumps(mock_response_data, ensure_ascii=False)}"


    if not google_ai_sdk_available:
        logger.error("無法生成文本，因為 Google Generative AI SDK 不可用。")
        return None

    if not _gemini_api_configured:
        logger.info("Gemini API 尚未配置，嘗試進行配置...")
        if not configure_gemini_api(): # 嘗試配置，如果失敗則返回
            logger.error("Gemini API 配置失敗，無法生成文本。")
            return None

    model_to_use = model_name or config_manager.get_setting('ai_analyzer_settings', 'default_model', "gemini-1.5-flash-latest")
    temp_to_use = temperature if temperature is not None else config_manager.get_setting('ai_analyzer_settings', 'suggestion_temperature', 0.7)

    logger.info(f"使用模型 '{model_to_use}' 和溫度 {temp_to_use} 生成文本...")
    logger.debug(f"完整 Prompt (前200字符):\n{prompt[:200]}...")

    try:
        model = genai.GenerativeModel(model_to_use)

        # 安全設定 (非常寬鬆，僅供測試，生產環境應更嚴格)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        generation_config = genai.types.GenerationConfig(temperature=temp_to_use)

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            logger.error(f"Prompt 被 API 拒絕，原因: {response.prompt_feedback.block_reason}")
            if response.prompt_feedback.safety_ratings:
                 for rating in response.prompt_feedback.safety_ratings:
                     logger.error(f"  安全回饋 - 類別: {rating.category}, 機率: {rating.probability}")
            return None

        # 檢查是否有 parts，以及 parts 中是否有 text
        if response.parts:
            all_text_parts = [part.text for part in response.parts if hasattr(part, 'text') and part.text]
            if all_text_parts:
                full_text = "".join(all_text_parts)
                logger.info("成功從 Gemini API 獲取文本回應。")
                logger.debug(f"Gemini API 回應 (前200字符): {full_text[:200]}...")
                return full_text
            else:
                logger.warning("Gemini API 回應中沒有有效的文本內容 (parts 不含 text)。")
                logger.debug(f"完整回應對象: {response}")
                return None # 或者可以返回一個空字串或特定錯誤訊息
        else: # 兼容舊版 API 或 text 直接在 response 上的情況 (雖然 generate_content 通常返回 GenerateContentResponse)
             if hasattr(response, 'text') and response.text:
                logger.info("成功從 Gemini API 獲取文本回應 (直接從 response.text)。")
                logger.debug(f"Gemini API 回應 (前200字符): {response.text[:200]}...")
                return response.text
             else:
                logger.warning("Gemini API 回應中沒有有效的文本內容 (parts 為空且 response.text 為空或不存在)。")
                logger.debug(f"完整回應對象: {response}")
                return None


    except Exception as e:
        logger.error(f"調用 Gemini API 時發生錯誤: {e}", exc_info=True)
        return None

# --- Prompt 模板與填充函數 ---

def get_market_analysis_prompt(market_data: dict, market_type: str = "美股", user_preferences: str = "關注中長期趨勢和價值投資機會") -> str:
    """
    生成市場總體分析的 Prompt。

    參數:
        market_data (dict): 包含關鍵市場指標的字典。
                            範例: {"S&P 500": "5250 (+0.5%)", "VIX": "13.5 (-2%)", "美國十年期公債殖利率": "4.25% (+0.02%)"}
        market_type (str): 市場類型，例如 "美股", "台股", "全球市場"。
        user_preferences (str): 用戶的投資偏好或關注點。

    返回:
        str: 填充好的 Prompt 字串。
    """
    market_data_str = "\n".join([f"- {key}: {value}" for key, value in market_data.items()])

    prompt = f"""
作為一名專業的金融市場分析師，請基於以下最新的市場數據和用戶偏好，提供一份關於「{market_type}」市場的總體分析報告。

**最新市場數據觀察：**
{market_data_str}

**用戶投資偏好：**
{user_preferences}

**分析報告應包含以下部分 (請使用繁體中文回答，並以 Markdown 格式組織您的回答)：**

1.  **市場總體評價與情緒分析：**
    *   目前市場的整體評價 (例如：樂觀、謹慎樂觀、中性、謹慎悲觀、悲觀)。
    *   主要的市場情緒驅動因素是什麼？
    *   根據VIX指數等情緒指標，市場當前的主要情緒是什麼？

2.  **關鍵數據點解讀：**
    *   逐點分析提供的「最新市場數據觀察」中的每個指標，它們各自揭示了市場的何種狀態或趨勢？
    *   這些數據點之間是否存在任何互相強化或矛盾的信號？

3.  **近期主要趨勢與潛在轉折點：**
    *   當前市場的主要趨勢是什麼 (例如：上升、下降、盤整)？哪些板塊或風格表現突出？
    *   是否存在任何可能導致當前趨勢發生轉變的潛在催化劑或風險因素 (例如：經濟數據發布、政策變動、地緣政治事件)？

4.  **根據用戶偏好的簡明策略建議：**
    *   基於對市場的分析和「{user_preferences}」的用戶偏好，目前應採取何種總體投資策略 (例如：積極增持、逢低買入、保持觀望、適度減倉、避險為主)？
    *   有哪些值得關注的總體市場機會或應規避的風險？

請確保您的分析客觀、數據驅動，並提供清晰、可操作的見解。語言風格請保持專業且易於理解。
"""
    logger.debug(f"生成的市場分析 Prompt (前100字符): {prompt[:100]}...")
    return prompt

def get_stock_suggestion_prompt(stock_symbol: str, stock_data: dict, risk_assessment: list, user_preferences: str = "風險承受度中等，偏好成長型股票，期望一年以上投資期") -> str:
    """
    生成個股分析與操作建議的 Prompt。

    參數:
        stock_symbol (str): 股票代碼。
        stock_data (dict): 包含該股票的技術指標和基本面摘要。
                           範例: {{"Close": 175.00, "SMA_20": 172, "SMA_50": 170, "RSI_14": 55, "Volume": 2500000, "P/E Ratio": 25, "EPS": 7.0}}
        risk_assessment (list): 由 stock_screener 生成的風險描述列表。
                               範例: ["[AAPL] 歷史波動率正常: 22.50% (閾值: 60.0%)。", "[AAPL] 未處於主要下跌趨勢。"]
        user_preferences (str): 用戶的投資偏好。

    返回:
        str: 填充好的 Prompt 字串。
    """
    stock_data_str = "\n".join([f"- {key}: {value}" for key, value in stock_data.items()])
    risk_assessment_str = "\n".join([f"- {risk}" for risk in risk_assessment]) if risk_assessment else "無特別風險標記。"

    prompt = f"""
作為一名資深的股票分析師，請針對股票「{stock_symbol}」提供詳細的分析與具體的操作建議。

**股票基本數據與技術指標：**
{stock_data_str}

**系統風險評估摘要：**
{risk_assessment_str}

**用戶投資偏好：**
{user_preferences}

**請基於以上所有資訊，提供以下分析 (請使用繁體中文回答，並以 Markdown 格式組織您的回答)：**

1.  **技術面分析：**
    *   根據提供的技術指標 (如移動平均線、RSI等)，評價「{stock_symbol}」當前的技術形態 (強勢、弱勢、盤整、超買、超賣等)。
    *   成交量呈現何種趨勢？是否支持當前的價格行為？
    *   是否有明顯的支撐位或壓力位？

2.  **基本面簡評 (若有數據)：**
    *   (若 stock_data 中包含 P/E, EPS 等基本面數據) 根據提供的基本面數據，簡要評價其估值水平或成長性。
    *   如果缺乏詳細基本面數據，可以註明「基本面數據不完整，此處僅作參考」。

3.  **風險因素考量：**
    *   結合「系統風險評估摘要」，指出投資「{stock_symbol}」當前最主要的風險是什麼？
    *   這些風險對短期和中長期股價走勢的潛在影響如何？

4.  **綜合操作建議 (買入/賣出/持有/觀望)：**
    *   綜合技術面、基本面(若有)及風險評估，並考慮到「{user_preferences}」的用戶偏好，對「{stock_symbol}」給出明確的操作建議 (例如：建議在 XXX 價位附近買入，目標價 YYY；或建議持有並觀察 ZZZ 指標；或建議規避風險，暫時觀望)。
    *   請說明給出此建議的主要理由和前提條件。
    *   設定一個合理的止損點位或出場策略建議。

請確保您的分析邏輯清晰，建議具有可操作性，並充分考慮風險。
"""
    logger.debug(f"生成的個股建議 Prompt ({stock_symbol}) (前100字符): {prompt[:100]}...")
    return prompt


if __name__ == '__main__':
    logger.info("--- AI Analyzer 內部測試 ---")

    # 模擬設定 mock_api_calls = True (假設已在 config 中設定)
    logger.info(f"AI分析 -> mock_api_calls: {config_manager.get_setting('ai_analyzer_settings', 'mock_api_calls', 'N/A')}")

    # 測試 API 配置 (如果 SDK 可用且金鑰有效，則會嘗試配置)
    # 注意：如果沒有有效的 API 金鑰，configure_gemini_api() 預期會返回 False (或打印錯誤)
    # 並且 generate_text_from_prompt 在非模擬模式下會因此返回 None。
    # 在模擬模式下，configure_gemini_api 的結果不影響模擬回應的返回。
    logger.info("嘗試配置 Gemini API (如果 SDK 可用)...")
    is_configured = configure_gemini_api()
    logger.info(f"Gemini API 配置狀態: {is_configured}")

    # 測試 get_market_analysis_prompt
    logger.info("\n--- 測試市場分析 Prompt 生成 ---")
    sample_market_data = {"S&P 500": "5250 (+0.5%)", "VIX": "13.5 (-2%)", "美國十年期公債殖利率": "4.25% (+0.02%)"}
    market_prompt = get_market_analysis_prompt(sample_market_data, market_type="美國股市")
    # print(f"市場分析 Prompt:\n{market_prompt}")
    assert "美國股市" in market_prompt
    assert "5250 (+0.5%)" in market_prompt
    logger.info("市場分析 Prompt 生成成功。")

    # 測試 get_stock_suggestion_prompt
    logger.info("\n--- 測試個股建議 Prompt 生成 ---")
    sample_stock_data = {"Close": 175.00, "SMA_20": 172, "SMA_50": 170, "RSI_14": 55, "Volume": 2500000, "P/E Ratio": 25, "EPS": 7.0}
    sample_risks = ["[AAPL] 歷史波動率正常: 22.50%", "[AAPL] 未處於主要下跌趨勢。"]
    stock_prompt = get_stock_suggestion_prompt("AAPL", sample_stock_data, sample_risks)
    # print(f"個股建議 Prompt (AAPL):\n{stock_prompt}")
    assert "AAPL" in stock_prompt
    assert "RSI_14: 55" in stock_prompt
    assert "[AAPL] 歷史波動率正常" in stock_prompt
    logger.info("個股建議 Prompt 生成成功。")

    # 測試 generate_text_from_prompt (應使用模擬回應)
    logger.info("\n--- 測試文本生成 (模擬模式) ---")
    simulated_response = generate_text_from_prompt("這是一個測試 Prompt。")
    if simulated_response:
        logger.info(f"獲取到模擬回應 (部分): {simulated_response[:100]}...")
        assert "模擬成功回應" in simulated_response # 根據模擬回應的內容調整
    else:
        logger.error("未能獲取模擬回應。")
        if not google_ai_sdk_available:
            logger.warning("可能原因：Google AI SDK 未安裝。")
        elif not is_configured and not config_manager.get_setting('ai_analyzer_settings', 'mock_api_calls', False):
            logger.warning("可能原因：API 未成功配置且未啟用模擬調用。")


    # 嘗試在非模擬模式下調用 (如果 API Key 有效且 SDK 已安裝)
    # 注意：這部分只應在確認 API Key 有效且願意進行實際調用的情況下取消註解
    # current_mock_setting = config_manager.get_setting('ai_analyzer_settings', 'mock_api_calls')
    # if google_ai_sdk_available and is_configured and not current_mock_setting:
    #     logger.info("\n--- 測試文本生成 (實際 API 調用 - 如有配置) ---")
    #     # 確保 API Key 是有效的，否則會失敗
    #     # 僅在確認金鑰有效且 SDK 安裝成功時才執行此部分
    #     if os.getenv("ALLOW_ACTUAL_API_CALLS_FOR_TESTING") == "true": # 再加一層保護
    #         actual_response = generate_text_from_prompt("請用繁體中文簡要介紹一下什麼是移動平均線 (SMA)。", model_name="gemini-1.5-flash-latest")
    #         if actual_response:
    #             logger.info(f"從實際 API 獲取的回應:\n{actual_response}")
    #         else:
    #             logger.error("未能從實際 API 獲取回應。請檢查 API 金鑰和網路連線。")
    #     else:
    #         logger.info("跳過實際 API 調用測試 (未設定 ALLOW_ACTUAL_API_CALLS_FOR_TESTING 環境變數為 true)。")
    # elif not current_mock_setting:
    #     logger.warning("跳過實際 API 調用測試，因為 API SDK 不可用、未配置或模擬調用被禁用。")


    logger.info("--- AI Analyzer 內部測試結束 ---")
