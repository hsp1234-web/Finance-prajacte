# 金融市場分析與風險評估系統 MVP

本專案是一個最小可行性產品 (MVP)，旨在提供一個基礎的金融市場分析與風險評估儀表板。使用者可以在 Google Colab 環境中輕鬆啟動此應用程式，並透過網頁瀏覽器進行互動。

## 特色功能

*   **核心儀表板：** 顯示（模擬的）核心壓力指數、殖利率曲線快照（佔位符）、VIX 指數（來自 yfinance）等關鍵指標。
*   **宏觀環境分析：** 提供全球經濟展望、美國主要經濟數據（GDP、CPI等）的卡片展示，並在數據無法自動獲取時提供查閱建議。
*   **美股選擇權籌碼分析：**
    *   允許使用者輸入美股代號進行分析。
    *   計算並顯示最近到期日的預估最大痛點、成交量 P/C Ratio、未平倉量 P/C Ratio。
    *   使用 Plotly 生成可交互的堆疊式選擇權未平倉量 (OI) 與成交量分佈圖 (近月、次近月、遠月)。
    *   預載 AAPL 的分析結果作為範例。
*   **主題切換：** 支援亮色與暗色模式。
*   **API 金鑰處理：** 在缺少 Alpha Vantage 和 FRED API 金鑰的情況下仍能穩定運行，並提供相應提示。
*   **Colab 部署：** 可通過執行 Python 腳本在 Colab 中啟動，並使用 ngrok 生成公開訪問網址。

---

## (繁體中文) 如何在 Google Colab 中運行

請依照以下步驟在 Google Colab 中啟動本應用程式：

1.  **準備 Colab 環境：**
    *   打開 Google Colab ([colab.research.google.com](https://colab.research.google.com)) 並登入您的 Google 帳戶。
    *   建議使用具有足夠 RAM 的執行階段 (可在「執行階段」->「變更執行階段類型」中查看)。

2.  **上傳並解壓縮專案檔案：**
    *   從 GitHub (或其他來源) 下載本專案的 ZIP 壓縮檔。
    *   在 Colab Notebook 的儲存格中，上傳此 ZIP 檔到 Colab 的臨時儲存空間。您可以使用以下程式碼片段：
        ```python
        from google.colab import files
        uploaded = files.upload()
        for fn in uploaded.keys():
          print(f'使用者上傳了檔案 "{fn}"，長度為 {len(uploaded[fn])} bytes')
          zip_filename = fn # 假設只上傳一個 ZIP 檔
        ```
    *   解壓縮該 ZIP 檔案。假設 ZIP 檔案名為 `financial_project.zip`，且您希望將其內容解壓縮到名為 `project_files` 的資料夾：
        ```python
        import zipfile
        import os
        zip_extract_path = "project_files"
        if 'zip_filename' in locals() and os.path.exists(zip_filename):
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(zip_extract_path)
            print(f"已將 {zip_filename} 解壓縮到 {zip_extract_path} 資料夾。")
            # 假設主啟動腳本 run_colab_app.py 在解壓後的根目錄
            # 或者在某個特定子目錄，例如 project_files/financial_project/run_colab_app.py
            # 您需要根據實際的 ZIP 結構調整下面的 cd 命令路徑
            # %cd project_files
            # 或者 %cd project_files/your_project_main_folder_name_in_zip
        else:
            print("錯誤：找不到 ZIP 檔案或 'zip_filename' 未定義。請先上傳檔案。")
        ```
        **重要：** 執行完解壓縮後，請確保您使用 `%cd` 命令進入到包含 `run_colab_app.py` 和 `app.py` 等核心檔案的**正確資料夾**。如果 ZIP 包含一個頂層資料夾，您需要 `cd` 進入該資料夾。

3.  **執行啟動腳本：**
    *   在一個新的 Colab 儲存格中，執行以下命令來啟動應用程式：
        ```bash
        !python run_colab_app.py
        ```
    *   此腳本會自動安裝必要的 Python 依賴包，然後啟動 Flask Web 伺服器，並使用 ngrok 生成一個公開的 URL。

4.  **訪問應用程式：**
    *   腳本執行後，請留意控制台輸出。當 ngrok 隧道成功建立時，會打印出一個類似 `https://xxxx-xx-xxx-xxx-xx.ngrok-free.app` 的公開 URL。
    *   複製此 URL 並在您的網頁瀏覽器中打開，即可開始使用「金融市場分析與風險評估系統」。
    *   **注意：** ngrok 的免費方案有一些限制，例如隧道可能會有時效性或並發連接數限制。

5.  **使用說明：**
    *   **主題切換：** 點擊導航欄右上角的模式切換按鈕，可以在亮色和暗色主題之間切換。
    *   **數據更新時間：** 頁面頂部會顯示當前數據的（模擬）更新時間。
    *   **美股選擇權分析：**
        *   頁面預設顯示 AAPL 的選擇權分析結果和圖表。
        *   您可以在「美股選擇權籌碼分析」區塊的輸入框中輸入其他美股代號 (例如 TSLA, MSFT)，然後點擊「分析」按鈕。
        *   系統將嘗試獲取該股票的選擇權數據，並更新分析文本和圖表。請耐心等待數據加載。
        *   如果數據獲取失敗或分析出錯，將會顯示提示信息。
    *   **其他區塊：** 核心儀表板和宏觀環境分析區塊的數據主要為靜態佔位符或依賴模擬/降級數據，因本 MVP 未配置實際的 API 金鑰。市場結構分析區塊預設為隱藏。

6.  **停止應用程式：**
    *   要停止在 Colab 中運行的應用程式和 ngrok 隧道，您可以中斷 (Interrupt) 執行 `!python run_colab_app.py` 的儲存格 (通常是點擊執行按鈕旁邊的停止圖示，或使用 Ctrl+C/Cmd+C，然後選擇中斷執行)。

## (可選) 備份您的專案 (如果使用 Google Drive)

如果您希望將專案檔案（例如您修改過的 `main_app_builder.py` 或 `app.py`）保存到 Google Drive 並進行備份，可以參考以下步驟：

1.  **掛載 Google Drive：**
    在 Colab Notebook 的一個儲存格中執行：
    ```python
    from google.colab import drive
    drive.mount('/content/drive')
    ```
2.  **設定專案路徑：**
    假設您的專案根目錄名稱為 `MyFinancialApp`，您想將主要工作檔案放在 `MyDrive/MyFinancialApp/main`，備份則存於 `MyDrive/MyFinancialApp/backup`。
    ```python
    import os
    DRIVE_PROJECT_ROOT = '/content/drive/MyDrive/MyFinancialApp'
    MAIN_APP_DIR_ON_DRIVE = os.path.join(DRIVE_PROJECT_ROOT, 'main')
    BACKUP_ROOT_ON_DRIVE = os.path.join(DRIVE_PROJECT_ROOT, 'backup')

    # 確保這些目錄存在
    os.makedirs(MAIN_APP_DIR_ON_DRIVE, exist_ok=True)
    os.makedirs(BACKUP_ROOT_ON_DRIVE, exist_ok=True)

    # 將您當前 Colab 環境中的專案檔案 (例如 app.py, main_app_builder.py, templates/, static/, backup_utils.py)
    # 複製到 MAIN_APP_DIR_ON_DRIVE
    # 例如，如果您已將專案解壓縮到 /content/project_files:
    # !cp -r /content/project_files/* "$MAIN_APP_DIR_ON_DRIVE/"
    # (請根據您的實際解壓縮路徑調整)
    print(f"請確保您的專案檔案已位於: {MAIN_APP_DIR_ON_DRIVE}")
    ```
3.  **執行備份：**
    將 `backup_utils.py` 檔案與您的主應用程式檔案放在一起（例如，都在解壓縮後的資料夾中）。
    然後，您可以在 Colab Notebook 的儲存格中執行類似如下的程式碼來備份 `MAIN_APP_DIR_ON_DRIVE`：
    ```python
    # 假設 backup_utils.py 與此 Notebook 在同一檔案層級或已在 sys.path 中
    # 如果 backup_utils.py 在 MAIN_APP_DIR_ON_DRIVE (或其他路徑)
    # 您可能需要先將該路徑添加到 sys.path
    # import sys
    # sys.path.append(MAIN_APP_DIR_ON_DRIVE) # 如果 backup_utils.py 在 main 資料夾內

    try:
        from backup_utils import backup_directory # 確保 backup_utils.py 可被導入

        # 執行備份
        source_to_backup = MAIN_APP_DIR_ON_DRIVE
        backup_location = BACKUP_ROOT_ON_DRIVE

        print(f"準備備份 '{source_to_backup}' 到 '{backup_location}'...")
        success, backup_path = backup_directory(source_to_backup, backup_location, backup_prefix="financial_app_backup")

        if success:
            print(f"備份成功完成！備份檔案位於：{backup_path}")
        else:
            print("備份過程中發生錯誤。請查看日誌。")
    except ImportError:
        print("錯誤：無法導入 backup_utils。請確保 backup_utils.py 檔案存在且路徑正確。")
    except NameError:
        print("錯誤：MAIN_APP_DIR_ON_DRIVE 或 BACKUP_ROOT_ON_DRIVE 未定義。請先執行路徑設定儲存格。")

    ```

---
---

# Financial Market Analysis & Risk Assessment System MVP

This project is a Minimum Viable Product (MVP) designed to provide a basic financial market analysis and risk assessment dashboard. Users can easily launch this application in a Google Colab environment and interact with it via a web browser.

## Features

*   **Core Dashboard:** Displays a (simulated) core stress index, yield curve snapshot (placeholder), VIX index (from yfinance), and other key indicators.
*   **Macro Environment Analysis:** Provides cards for global economic outlook, key U.S. economic data (GDP, CPI, etc.), with suggestions for further reading if data cannot be fetched automatically.
*   **U.S. Stock Options Analysis:**
    *   Allows users to input a U.S. stock ticker for analysis.
    *   Calculates and displays estimated Max Pain price, Volume P/C Ratio, and Open Interest P/C Ratio for the nearest expiration date.
    *   Generates an interactive stacked Plotly chart for Open Interest (OI) and Volume distribution (near-term, +1 week, +1 month). All chart elements are in Traditional Chinese.
    *   Preloads analysis for AAPL as an example.
*   **Theme Switching:** Supports light and dark modes.
*   **API Key Handling:** Designed to run stably without Alpha Vantage and FRED API keys, providing appropriate user prompts.
*   **Colab Deployment:** Can be launched in Colab by executing a Python script, using ngrok to generate a publicly accessible URL.

---

## (English) How to Run in Google Colab

Follow these steps to launch the application in Google Colab:

1.  **Prepare Colab Environment:**
    *   Open Google Colab ([colab.research.google.com](https://colab.research.google.com)) and sign in to your Google account.
    *   A runtime with sufficient RAM is recommended (check via "Runtime" > "Change runtime type").

2.  **Upload and Extract Project Files:**
    *   Download the project's ZIP file from GitHub (or your source).
    *   In a Colab Notebook cell, upload this ZIP file to Colab's temporary storage. You can use the following code snippet:
        ```python
        from google.colab import files
        uploaded = files.upload()
        for fn in uploaded.keys():
          print(f'User uploaded file "{fn}" with length {len(uploaded[fn])} bytes')
          zip_filename = fn # Assuming only one ZIP file is uploaded
        ```
    *   Extract the ZIP file. Assuming the ZIP file is named `financial_project.zip` and you want to extract its contents to a folder named `project_files`:
        ```python
        import zipfile
        import os
        zip_extract_path = "project_files"
        if 'zip_filename' in locals() and os.path.exists(zip_filename):
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(zip_extract_path)
            print(f"Successfully extracted {zip_filename} to {zip_extract_path} folder.")
            # IMPORTANT: Navigate to the correct directory containing run_colab_app.py
            # This depends on your ZIP file structure.
            # e.g., if run_colab_app.py is at the root of the extracted files:
            # %cd project_files
            # Or if it's inside another folder within the zip:
            # %cd project_files/your_project_main_folder_name_in_zip
        else:
            print("Error: ZIP file not found or 'zip_filename' is not defined. Please upload the file first.")
        ```
        **Important:** After extraction, ensure you use the `%cd` magic command to navigate into the **correct directory** that contains `run_colab_app.py`, `app.py`, etc. If your ZIP file contains a top-level folder, you'll need to `cd` into that folder.

3.  **Execute the Launch Script:**
    *   In a new Colab cell, run the following command to start the application:
        ```bash
        !python run_colab_app.py
        ```
    *   This script will automatically install necessary Python dependencies, start the Flask web server, and use ngrok to generate a public URL.

4.  **Access the Application:**
    *   Monitor the console output after running the script. When the ngrok tunnel is successfully established, a public URL similar to `https://xxxx-xx-xxx-xxx-xx.ngrok-free.app` will be printed.
    *   Copy this URL and open it in your web browser to start using the "Financial Market Analysis & Risk Assessment System."
    *   **Note:** ngrok's free plan has limitations, such as session timeouts or concurrent tunnel limits.

5.  **User Guide:**
    *   **Theme Toggle:** Click the mode toggle button in the top-right of the navigation bar to switch between light and dark themes.
    *   **Data Freshness:** The (simulated) update time of the data is displayed at the top of the page.
    *   **U.S. Stock Options Analysis:**
        *   The page defaults to showing the options analysis for AAPL.
        *   You can enter another U.S. stock ticker (e.g., TSLA, MSFT) in the input field under the "美股選擇權籌碼分析" (U.S. Stock Options Analysis) section and click the "分析" (Analyze) button.
        *   The system will attempt to fetch options data for the ticker and update the analysis text and chart. Please be patient while the data loads.
        *   If data fetching or analysis fails, a notification message will be displayed.
    *   **Other Sections:** Data in the Core Dashboard and Macro Environment Analysis sections are primarily static placeholders or rely on simulated/fallback data, as this MVP is not configured with live API keys. The Market Structure Analysis section is hidden by default.

6.  **Stopping the Application:**
    *   To stop the application and the ngrok tunnel running in Colab, interrupt the execution of the cell running `!python run_colab_app.py` (usually by clicking the stop icon next to the play button or using Ctrl+C/Cmd+C and then choosing to interrupt).

## (Optional) Backing Up Your Project (if using Google Drive)

If you wish to save your project files (e.g., modified `main_app_builder.py` or `app.py`) to Google Drive and create backups, follow these steps:

1.  **Mount Google Drive:**
    In a Colab Notebook cell, execute:
    ```python
    from google.colab import drive
    drive.mount('/content/drive')
    ```
2.  **Set Project Paths on Drive:**
    Assuming your project root on Drive will be `MyFinancialApp`, with main working files in `MyDrive/MyFinancialApp/main` and backups in `MyDrive/MyFinancialApp/backup`.
    ```python
    import os
    DRIVE_PROJECT_ROOT = '/content/drive/MyDrive/MyFinancialApp'
    MAIN_APP_DIR_ON_DRIVE = os.path.join(DRIVE_PROJECT_ROOT, 'main')
    BACKUP_ROOT_ON_DRIVE = os.path.join(DRIVE_PROJECT_ROOT, 'backup')

    # Ensure these directories exist
    os.makedirs(MAIN_APP_DIR_ON_DRIVE, exist_ok=True)
    os.makedirs(BACKUP_ROOT_ON_DRIVE, exist_ok=True)

    # Copy your current project files from Colab's temporary storage
    # (e.g., /content/project_files after extraction) to MAIN_APP_DIR_ON_DRIVE.
    # Example:
    # !cp -r /content/project_files/* "$MAIN_APP_DIR_ON_DRIVE/"
    # (Adjust the source path based on where you extracted your ZIP.)
    print(f"Please ensure your project files are located in: {MAIN_APP_DIR_ON_DRIVE}")
    ```
3.  **Perform Backup:**
    Ensure `backup_utils.py` is in a location where Python can import it (e.g., alongside your main application files in `MAIN_APP_DIR_ON_DRIVE`, or add its path to `sys.path`).
    Then, in a Colab Notebook cell, you can run code similar to this to back up `MAIN_APP_DIR_ON_DRIVE`:
    ```python
    # Assuming backup_utils.py is importable
    # If backup_utils.py is in MAIN_APP_DIR_ON_DRIVE, you might need:
    # import sys
    # sys.path.append(MAIN_APP_DIR_ON_DRIVE)

    try:
        from backup_utils import backup_directory # Ensure backup_utils.py is importable

        source_to_backup = MAIN_APP_DIR_ON_DRIVE
        backup_location = BACKUP_ROOT_ON_DRIVE

        print(f"Preparing to backup '{source_to_backup}' to '{backup_location}'...")
        success, backup_path = backup_directory(source_to_backup, backup_location, backup_prefix="financial_app_backup")

        if success:
            print(f"Backup completed successfully! Backup stored at: {backup_path}")
        else:
            print("An error occurred during the backup process. Please check the logs.")
    except ImportError:
        print("Error: Could not import backup_utils. Please ensure backup_utils.py is accessible.")
    except NameError:
        print("Error: MAIN_APP_DIR_ON_DRIVE or BACKUP_ROOT_ON_DRIVE is not defined. Please run the path setup cell first.")
    ```
