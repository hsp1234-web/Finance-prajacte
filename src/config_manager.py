# src/config_manager.py
import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'strategy_config.yaml')

def load_config():
    """
    載入設定檔 strategy_config.yaml。

    返回:
        dict: 包含設定值的字典。
        None: 如果檔案不存在或解析失敗。
    """
    if not os.path.exists(CONFIG_PATH):
        print(f"錯誤：設定檔 {CONFIG_PATH} 不存在。")
        return None
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"錯誤：解析 YAML 設定檔 {CONFIG_PATH} 失敗：{e}")
        return None
    except Exception as e:
        print(f"載入設定檔時發生未預期錯誤：{e}")
        return None

_config = load_config()

def get_setting(section, key, default=None):
    """
    從載入的設定中獲取特定設定值。

    參數:
        section (str): 設定檔中的區域名稱。
        key (str): 該區域內的鍵名稱。
        default (any, optional): 如果找不到鍵時返回的預設值。預設為 None。

    返回:
        any: 請求的設定值，如果找不到則返回預設值。
    """
    if _config is None:
        print("錯誤：設定尚未載入。")
        return default
    return _config.get(section, {}).get(key, default)

def get_api_key(service_name):
    """
    獲取指定服務的 API 金鑰。

    此函數設計為優先從 Colab Secrets 讀取金鑰。
    在此模擬環境中，它會先嘗試從 strategy_config.yaml 的 api_keys 部分讀取，
    並印出提示訊息說明其應從 Colab Secrets 獲取。

    參數:
        service_name (str): 服務名稱 (例如 'google_gemini_api_key')。

    返回:
        str: API 金鑰。
        None: 如果找不到金鑰。
    """
    # 模擬從 Colab Secrets 讀取 (實際 Colab 環境中應替換此部分)
    # from google.colab import userdata
    # try:
    #     api_key = userdata.get(service_name)
    #     if api_key:
    #         print(f"提示：已從 Colab Secrets 成功讀取 '{service_name}'。")
    #         return api_key
    # except ImportError:
    #     print("提示：非 Colab 環境，無法從 Colab Secrets 讀取。")
    # except Exception as e:
    #     print(f"從 Colab Secrets 讀取 '{service_name}' 時發生錯誤：{e}")

    # 優先順序 2: 從環境變數讀取
    # service_name 可能類似 'google_gemini_api_key' 或 'google_gemini'
    # 我們將其轉換為大寫並加上 "_API_KEY" 後綴作為標準環境變數名稱
    env_var_name = service_name.upper()
    if not env_var_name.endswith("_API_KEY"):
        env_var_name += "_API_KEY"

    api_key_from_env = os.getenv(env_var_name)
    if api_key_from_env:
        print(f"提示：已從環境變數 '{env_var_name}' 成功讀取 API 金鑰。")
        return api_key_from_env

    # 優先順序 3: 從 strategy_config.yaml 的 api_keys 部分讀取 (作為備援或提示)
    # 此處 service_name 應與 YAML 中的鍵名一致，例如 'google_gemini_api_key'
    api_key_from_config = get_setting('api_keys', service_name) # 直接使用原始 service_name
    if api_key_from_config and api_key_from_config != "YOUR_GEMINI_API_KEY_FROM_COLAB_SECRETS_OR_ENV" and api_key_from_config != "YOUR_GEMINI_API_KEY_HERE":
        print(f"提示：從 strategy_config.yaml 的 'api_keys.{service_name}' 讀取 API 金鑰。")
        print(f"重要警告：不建議將實際 API 金鑰直接寫在設定檔中。請優先使用 Colab Secrets (若適用) 或環境變數。")
        return api_key_from_config

    print(f"警告：未能從 Colab Secrets、環境變數 ('{env_var_name}') 或有效的設定檔條目中找到 API 金鑰 '{service_name}'。")
    print(f"請確保已設定 '{env_var_name}' 環境變數，或在 Colab 中設定相應的 Secret，或更新 strategy_config.yaml 中的預留值。")
    return None

# 在模組加載時嘗試加載 .env (如果 python-dotenv 已安裝)
# 這使得環境變數在 get_api_key 被調用時已經可用
try:
    from dotenv import load_dotenv
    if load_dotenv():
        print("提示: .env 檔案已加載。環境變數已更新 (如果 .env 檔案存在且包含變數)。")
    else:
        # load_dotenv() 在 .env 不存在時返回 False
        print("提示: 未找到 .env 檔案，或 .env 為空。將僅依賴已設定的環境變數或 Colab Secrets。")
except ImportError:
    print("提示: python-dotenv 套件未安裝。無法從 .env 檔案加載環境變數。請考慮安裝 'pip install python-dotenv' (主要用於本地開發)。")
except Exception as e:
    print(f"加載 .env 檔案時發生錯誤: {e}")


if __name__ == '__main__':
    # 簡單測試
    print("--- Config Manager 測試 ---")

    # 測試載入整個設定
    if _config:
        print("設定檔載入成功。")
    else:
        print("設定檔載入失敗。")

    # 測試 get_setting
    print(f"\n測試 get_setting:")
    print(f"市場設定 -> 預設關注市場: {get_setting('market_settings', 'default_stock_market', 'N/A')}")
    print(f"AI分析 -> mock_api_calls: {get_setting('ai_analyzer_settings', 'mock_api_calls', 'N/A')}")


    # 測試 get_api_key
    # 為了測試 get_api_key 的不同來源，您可能需要：
    # 1. 在 Colab 中設定 Secret 'google_gemini_api_key'
    # 2. 設定環境變數 GOOGLE_GEMINI_API_KEY
    # 3. 修改 config/strategy_config.yaml 中的 api_keys.google_gemini_api_key 為一個非預留值
    # 4. 創建 .env 檔案並在其中設定 GOOGLE_GEMINI_API_KEY
    print(f"\n測試 get_api_key (google_gemini_api_key):")
    # 使用 'google_gemini_api_key' 作為 service_name，與 YAML 中的鍵名一致
    gemini_key = get_api_key('google_gemini_api_key')
    if gemini_key:
        # 為安全起見，不要在日誌中完整打印金鑰
        print(f"獲取的 Google Gemini API Key (部分): ...{gemini_key[-6:] if len(gemini_key) > 6 else '******'}")
    else:
        print("未能獲取 Google Gemini API Key。")

    print(f"\n測試 get_api_key (使用 'google_gemini' 作為 service_name，應查找 GOOGLE_GEMINI_API_KEY 環境變數):")
    gemini_key_short_name = get_api_key('google_gemini')
    if gemini_key_short_name:
        print(f"獲取的 Google Gemini API Key (來自 'google_gemini' service_name) (部分): ...{gemini_key_short_name[-6:] if len(gemini_key_short_name) > 6 else '******'}")
    else:
        print("未能透過 'google_gemini' service_name 獲取 API Key。")

    # 測試一個不存在的 API Key
    print(f"\n測試 get_api_key (non_existent_service):")
    non_existent_key = get_api_key('non_existent_service')
    if non_existent_key is None:
       print("成功處理不存在的 API Key (預期結果：返回 None)。")

    print("\n--- Config Manager 測試結束 ---")
