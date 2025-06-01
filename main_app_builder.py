import logging
import datetime # For current year in footer
from datetime import datetime, timedelta # Explicitly import timedelta
import yfinance as yf
import pandas as pd
import requests
import io
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# import json # Not strictly needed for this step

# Configure basic logging - 配置基礎日誌記錄
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# --- Data Fetching and Analysis Functions ---
# --- 數據獲取與分析函數 ---

def get_yfinance_data(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """
    使用 yfinance 獲取指定 tickers 的歷史數據。

    Args:
        tickers (list[str]): 股票代號列表 (例如 ['^VIX', 'TWD=X'])。
        period (str): 數據獲取期間 (例如 "1y", "6mo", "max")。

    Returns:
        dict[str, pd.DataFrame]: 一個字典，鍵為 ticker，值為包含歷史數據的 Pandas DataFrame。
                                 如果特定 ticker 獲取失敗，其對應的值將是空的 DataFrame。
    """
    data_frames = {}
    logger.info(f"yfinance：開始獲取 {len(tickers)} 個代號的數據 (期間: {period})。")
    for ticker_symbol in tickers:
        try:
            ticker_obj = yf.Ticker(ticker_symbol)
            history_df = ticker_obj.history(period=period)
            if history_df.empty:
                logger.warning(f"yfinance：成功獲取 {ticker_symbol}，但數據為空。")
                data_frames[ticker_symbol] = pd.DataFrame() # 返回空 DataFrame 以保持一致性
            else:
                logger.info(f"yfinance：成功獲取 {ticker_symbol} 的數據 ({len(history_df)} 行)。")
                data_frames[ticker_symbol] = history_df
        except Exception as e:
            logger.error(f"yfinance：獲取 {ticker_symbol} 數據失敗：{e}", exc_info=False) # exc_info=False 避免過多堆疊追蹤除非調試需要
            data_frames[ticker_symbol] = pd.DataFrame()
    logger.info(f"yfinance：數據獲取過程完成。")
    return data_frames

def get_nyfed_dealer_positions() -> pd.Series:
    """
    從紐約聯儲網站下載並處理一級交易商的美國公債持有量數據。
    此函數會嘗試下載多個 Excel 文件，解析其內容，並將相關欄位加總以形成一個時間序列。

    Returns:
        pd.Series: 一個包含「Total_Gross_Positions_Millions」的時間序列 Pandas Series。
                   索引為日期，值為總頭寸（百萬美元）。如果處理失敗或無數據，則返回一個空的 Series。
    """
    logger.info("NY Fed：開始獲取一級交易商持倉數據...")
    # Excel 文件 URL 列表，按處理順序排列 (舊 -> 新，最新的 currentLS.xlsx 優先級最高)
    ny_fed_positions_urls = [
        "https://www.newyorkfed.org/medialibrary/media/markets/primarydealers/Primary-Dealer-Statistics-historical-annual-SBN.xlsx",
        "https://www.newyorkfed.org/medialibrary/media/markets/primarydealers/Primary-Dealer-Statistics-historical-annual-SBP2013.xlsx",
        "https://www.newyorkfed.org/medialibrary/media/markets/primarydealers/Primary-Dealer-Statistics-historical-annual-SBP2001.xlsx",
        "https://www.newyorkfed.org/medialibrary/media/markets/primarydealers/Primary-Dealer-Statistics-currentLS.xlsx", # 最新數據
    ]
    # 不同 Excel 版本的欄位名稱定義 (用於加總)
    sbp2013_cols_to_sum = ['PDPOSGSC-Agency debt', 'PDPOSGSC-Agency mortgage-backed securities (MBS)','PDPOSGSC-Treasury bills', 'PDPOSGSC-Treasury Inflation-Protected Securities (TIPS)','PDPOSGSC-Treasury coupons']
    sbp2001_cols_to_sum = ['PDPUSGCS-Agency Debt', 'PDPUSGCS-Agency MBS','PDPUSGCS-Treasury Bills', 'PDPUSGCS-Treasury Inflation-Protected Securities','PDPUSGCS-Treasury Coupons']
    sbn_cols_to_sum_prefix = 'PDPOSGSC-' # SBN 文件通常使用此前綴表示總頭寸

    all_positions_data = [] # 存儲從各文件中提取的 Series
    session = requests.Session()
    session.headers.update({'User-Agent': 'FinancialDashboardMVP/1.0 (Python requests)'}) # 設置 User-Agent

    for url in ny_fed_positions_urls:
        file_source_name = url.split('/')[-1]
        logger.info(f"NY Fed：開始處理文件 {file_source_name} (URL: {url})")
        try:
            response_excel = session.get(url, timeout=60) # 設置請求超時
            response_excel.raise_for_status() # 如果 HTTP 請求返回錯誤狀態碼，則引發異常
            excel_content = io.BytesIO(response_excel.content)

            header_row = None; data_positions_long = None
            possible_headers = [3, 4, 0, 1, 2, 5, 6] # 可能的表頭行號 (0-indexed)

            # 嘗試不同的表頭行號來解析 Excel
            for h_candidate in possible_headers:
                try:
                    excel_content.seek(0) # 重置 BytesIO 指針
                    all_sheets = pd.read_excel(excel_content, header=h_candidate, sheet_name=None, engine='openpyxl')

                    sheet_to_use_name = None
                    if isinstance(all_sheets, dict): # 如果 Excel 有多個工作表
                        potential_names = {name.lower().strip(): name for name in all_sheets.keys()}
                        # 按優先級查找工作表名
                        if 'data' in potential_names: sheet_to_use_name = potential_names['data']
                        elif 'sheet1' in potential_names: sheet_to_use_name = potential_names['sheet1']
                        elif 'pdposgsc' in potential_names: sheet_to_use_name = potential_names['pdposgsc'] # currentLS.xlsx
                        elif all_sheets: sheet_to_use_name = list(all_sheets.keys())[0] # 使用第一個工作表作為備選

                    current_df_peek = None # 用於檢查列名的小 DataFrame
                    if sheet_to_use_name and isinstance(all_sheets, dict):
                        current_df_peek = all_sheets[sheet_to_use_name].head()
                    elif not isinstance(all_sheets, dict): # 如果 Excel 只有一個工作表，pandas 直接返回 DataFrame
                        current_df_peek = all_sheets.head()
                    else: continue # 未找到有效工作表

                    cols_lower = [str(c).lower().strip() for c in current_df_peek.columns]
                    ts_col, val_col, date_col = None, None, None # 初始化時間序列、數值和日期列名

                    # 智能檢測列名
                    for var in ['time series', 'series id', 'series name']:
                        if var in cols_lower: ts_col = current_df_peek.columns[cols_lower.index(var)]; break
                    for var in ['value (millions)', 'value', 'amount']:
                        if var in cols_lower: val_col = current_df_peek.columns[cols_lower.index(var)]; break
                    if 'as of date' in cols_lower: date_col = current_df_peek.columns[cols_lower.index('as of date')]
                    elif 'effective date' in cols_lower: date_col = current_df_peek.columns[cols_lower.index('effective date')]
                    elif current_df_peek.columns.size > 0 and ('date' in str(current_df_peek.columns[0]).lower() or 'period' in str(current_df_peek.columns[0]).lower()): date_col = current_df_peek.columns[0]

                    if ts_col and val_col and date_col: # 如果成功找到所有必要列
                        header_row = h_candidate; excel_content.seek(0)
                        # 使用檢測到的參數重新讀取整個工作表
                        if isinstance(all_sheets, dict) and sheet_to_use_name:
                            data_positions_long = pd.read_excel(excel_content, header=header_row, sheet_name=sheet_to_use_name, index_col=date_col, parse_dates=True, engine='openpyxl')
                        else: # 單工作表情況
                            data_positions_long = pd.read_excel(excel_content, header=header_row, index_col=date_col, parse_dates=True, engine='openpyxl')
                        logger.info(f"NY Fed：文件 {file_source_name}，使用表頭行 {header_row+1}，日期列 '{date_col}'。"); break
                except Exception: excel_content.seek(0); continue # 解析失敗，嘗試下一個表頭行號

            if data_positions_long is None: logger.warning(f"NY Fed：文件 {file_source_name} 無法自動檢測有效的表頭或列結構，跳過。"); continue

            # 數據清理與轉換
            if not isinstance(data_positions_long.index, pd.DatetimeIndex): data_positions_long.index = pd.to_datetime(data_positions_long.index, errors='coerce')
            data_positions_long = data_positions_long[pd.notna(data_positions_long.index)]; data_positions_long.index = data_positions_long.index.normalize()
            if data_positions_long.empty: logger.info(f"NY Fed：文件 {file_source_name} 清理日期後為空。"); continue

            # 再次確認時間序列和數值列名 (因為 data_positions_long 是完整讀取的 DataFrame)
            actual_ts_col, actual_val_col = None, None
            cols_lower_full = [str(c).lower().strip() for c in data_positions_long.columns]
            for var in ['time series', 'series id', 'series name']:
                if var in cols_lower_full: actual_ts_col = data_positions_long.columns[cols_lower_full.index(var)]; break
            for var in ['value (millions)', 'value', 'amount']:
                if var in cols_lower_full: actual_val_col = data_positions_long.columns[cols_lower_full.index(var)]; break
            if not actual_ts_col or not actual_val_col: logger.warning(f"NY Fed：文件 {file_source_name} 清理後仍缺少時間序列或數值列，跳過。"); continue

            data_positions_long[actual_val_col] = pd.to_numeric(data_positions_long[actual_val_col], errors='coerce'); data_positions_long.dropna(subset=[actual_val_col, actual_ts_col], inplace=True)
            if data_positions_long.empty: logger.info(f"NY Fed：文件 {file_source_name} 移除NaN後為空。"); continue

            data_positions_long.reset_index(inplace=True); date_col_actual_name = data_positions_long.columns[0] # 獲取實際的日期列名
            # 處理可能的重複項 (日期和TS ID組合)，取平均值
            data_positions_long = data_positions_long.groupby([date_col_actual_name, actual_ts_col])[actual_val_col].mean().reset_index()
            # 將長格式數據轉換為寬格式，以日期為索引，TS ID為列
            data_positions_wide = pd.pivot_table(data_positions_long, index=date_col_actual_name, columns=actual_ts_col, values=actual_val_col, aggfunc='mean')
            if data_positions_wide.empty: logger.info(f"NY Fed：文件 {file_source_name} 轉換為寬格式後為空。"); continue

            # 根據文件名確定要加總的欄位列表
            target_cols = []
            if 'sbn' in url.lower() or 'currentls' in url.lower(): target_cols = [c for c in data_positions_wide.columns if isinstance(c, str) and c.startswith(sbn_cols_to_sum_prefix)]
            elif 'sbp2013' in url.lower(): target_cols = sbp2013_cols_to_sum
            elif 'sbp2001' in url.lower(): target_cols = sbp2001_cols_to_sum

            cols_in_df = [c for c in target_cols if c in data_positions_wide.columns] # 確保欄位存在於DataFrame中
            if not cols_in_df: logger.warning(f"NY Fed：文件 {file_source_name} 未找到任何用於加總的目標欄位。預期欄位: {target_cols if target_cols else sbn_cols_to_sum_prefix}"); continue

            for col in cols_in_df: data_positions_wide[col] = pd.to_numeric(data_positions_wide[col], errors='coerce') # 確保數值類型
            daily_total = data_positions_wide[cols_in_df].sum(axis=1, skipna=True).dropna() # 沿行加總，忽略NaN
            daily_total = daily_total[daily_total != 0] # 移除總和為0的記錄
            if not daily_total.empty: all_positions_data.append(daily_total); logger.info(f"NY Fed：成功處理並加總文件 {file_source_name} ({len(daily_total)} 筆有效數據)。")
            else: logger.info(f"NY Fed：文件 {file_source_name} 加總後無有效數據。")
        except requests.exceptions.RequestException as e: logger.warning(f"NY Fed：下載文件 {file_source_name} 失敗：{e}")
        except Exception as e: logger.warning(f"NY Fed：處理文件 {file_source_name} 時發生未預期錯誤：{e}", exc_info=True) # exc_info=True 在調試時有用

    if not all_positions_data: logger.warning("NY Fed：未能成功處理任何一級交易商數據文件，返回空 Series。"); return pd.Series(dtype='float64')
    # 合併所有文件數據，排序並處理重複索引 (保留最後一個，通常是最新文件中的數據)
    final_series = pd.concat(all_positions_data).sort_index(); final_series = final_series[~final_series.index.duplicated(keep='last')]
    final_series.name = 'Total_Gross_Positions_Millions'; logger.info(f"NY Fed：一級交易商持倉數據獲取與合併完成，共 {len(final_series)} 筆數據。")
    return final_series

def find_closest_date(target_date: datetime, date_list_str: list[str]) -> str | None:
    """
    從日期字串列表中找出最接近目標日期的日期。

    Args:
        target_date (datetime): 目標日期。
        date_list_str (list[str]): 日期字串列表 (格式需為 '%Y-%m-%d')。

    Returns:
        str | None: 最接近的日期字串，如果列表為空則返回 None。
    """
    if not date_list_str: return None
    try:
        date_list_dt = [datetime.strptime(d_str, '%Y-%m-%d') for d_str in date_list_str]
        closest_date = min(date_list_dt, key=lambda d: abs(d - target_date))
        return closest_date.strftime('%Y-%m-%d')
    except ValueError as e:
        logger.error(f"find_closest_date：日期格式錯誤: {e} (輸入列表: {date_list_str})")
        return None

def analyze_stock_options(ticker_symbol: str, bar_height_multiplier: float = 0.4) -> tuple[str, str]:
    """
    分析指定美股代號的選擇權鏈數據，計算關鍵指標，並生成 Plotly 圖表的 JSON。

    Args:
        ticker_symbol (str): 美股代號。
        bar_height_multiplier (float): 用於調整 Plotly 長條圖視覺高度的因子。

    Returns:
        tuple[str, str]: 一個元組，包含：
                         - analysis_text: 繁體中文的分析結果文字 (最大痛點、P/C Ratios)。
                         - plotly_json: Plotly 圖表的 JSON 字串。如果無法生成圖表，則為空字串。
    """
    logger.info(f"選擇權分析：開始分析 {ticker_symbol}...")
    analysis_results = []; current_price = None; near_data, week_data, month_data = None, None, None
    near_exp, week_exp, month_exp = None, None, None; default_empty_data = {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
    try: # 主 try 塊包裹整個函數
        ticker = yf.Ticker(ticker_symbol); logger.info(f"選擇權分析：獲取 {ticker_symbol} 股價...")
        try: # 獲取股價
            hist = ticker.history(period="5d")
            if not hist.empty: current_price = hist['Close'].iloc[-1]
            if current_price is None or np.isnan(current_price): current_price = ticker.fast_info.get('last_price') # 備援
        except Exception as e: logger.warning(f"選擇權分析：獲取 {ticker_symbol} 股價失敗：{e}"); return f"錯誤：無法獲取 {ticker_symbol} 的股價資訊。", ""
        if current_price is None or np.isnan(current_price): return f"錯誤：未能獲取 {ticker_symbol} 的有效股價。", ""
        analysis_results.append(f"目前股價：${current_price:.2f}"); logger.info(f"選擇權分析：{ticker_symbol} 股價 ${current_price:.2f}")

        expirations = ticker.options # 獲取到期日
        if not expirations: logger.warning(f"選擇權分析：找不到 {ticker_symbol} 選擇權到期日。"); return f"錯誤：找不到 {ticker_symbol} 的選擇權到期日。", ""

        # 獲取近月選擇權數據
        near_exp = expirations[0]; logger.info(f"選擇權分析：處理最近到期日 (Near): {near_exp}")
        try: near_chain = ticker.option_chain(near_exp); near_data = {'calls': getattr(near_chain, 'calls', pd.DataFrame()), 'puts': getattr(near_chain, 'puts', pd.DataFrame())}
        except Exception as e: logger.warning(f"選擇權分析：無法獲取 {near_exp} 數據: {e}"); near_data = default_empty_data.copy()

        # 獲取 +1 週和 +1 月選擇權數據 (如果存在)
        if len(expirations) > 1:
            try:
                near_date_dt = datetime.strptime(near_exp, '%Y-%m-%d'); target_wk_dt = near_date_dt + timedelta(weeks=1)
                week_exp = find_closest_date(target_wk_dt, [d for d in expirations if d > near_exp])
                if week_exp: logger.info(f"選擇權分析：處理 +1 週到期日 (Week): {week_exp}")
                search_start_dt = datetime.strptime(week_exp, '%Y-%m-%d') if week_exp else near_date_dt
                target_mo_dt = near_date_dt + timedelta(days=30) # 從近月期權起算30天
                month_exp = find_closest_date(target_mo_dt, [d for d in expirations if d > search_start_dt.strftime('%Y-%m-%d')])
                if month_exp: logger.info(f"選擇權分析：處理 +1 月到期日 (Month): {month_exp}")
            except Exception as e: logger.warning(f"選擇權分析：尋找未來到期日失敗: {e}")
        if week_exp: # 如果找到+1週到期日，獲取其數據
            try: week_chain = ticker.option_chain(week_exp); week_data = {'calls': getattr(week_chain, 'calls', pd.DataFrame()), 'puts': getattr(week_chain, 'puts', pd.DataFrame())}
            except Exception as e: logger.warning(f"選擇權分析：無法獲取 {week_exp} 數據: {e}"); week_data = default_empty_data.copy()
        if month_exp: # 如果找到+1月到期日，獲取其數據
            try: month_chain = ticker.option_chain(month_exp); month_data = {'calls': getattr(month_chain, 'calls', pd.DataFrame()), 'puts': getattr(month_chain, 'puts', pd.DataFrame())}
            except Exception as e: logger.warning(f"選擇權分析：無法獲取 {month_exp} 數據: {e}"); month_data = default_empty_data.copy()

        # 計算指標 (基於近月數據)
        if near_data and not near_data['calls'].empty and not near_data['puts'].empty:
            calls_df, puts_df = near_data['calls'].copy(), near_data['puts'].copy()
            for df_loop in [calls_df, puts_df]: # 確保欄位存在且為數值
                for col_loop in ['strike','openInterest','volume']: df_loop[col_loop] = pd.to_numeric(df_loop.get(col_loop,0), errors='coerce').fillna(0)
            vol_pc_ratio = (puts_df['volume'].sum() / calls_df['volume'].sum()) if calls_df['volume'].sum() > 0 else "N/A"
            oi_pc_ratio = (puts_df['openInterest'].sum() / calls_df['openInterest'].sum()) if calls_df['openInterest'].sum() > 0 else "N/A"
            analysis_results.append(f"成交量 P/C Ratio (近月 {near_exp}): {vol_pc_ratio if isinstance(vol_pc_ratio,str) else f'{vol_pc_ratio:.2f}'}")
            analysis_results.append(f"未平倉量 P/C Ratio (近月 {near_exp}): {oi_pc_ratio if isinstance(oi_pc_ratio,str) else f'{oi_pc_ratio:.2f}'}")
            # 計算最大痛點
            strikes = pd.concat([calls_df['strike'], puts_df['strike']]).unique(); strikes.sort(); pain_strike = -1; min_pain = float('inf')
            if len(strikes)>0:
                call_oi_map = calls_df.set_index('strike')['openInterest']; put_oi_map = puts_df.set_index('strike')['openInterest']
                for s_iter in strikes:
                    loss = sum((s_iter - cs) * oi for cs, oi in call_oi_map.items() if s_iter > cs) + sum((ps - s_iter) * oi for ps, oi in put_oi_map.items() if s_iter < ps)
                    if loss < min_pain: min_pain = loss; pain_strike = s_iter
            analysis_results.append(f"預估最大痛點 (近月 {near_exp}): {f'${pain_strike:.2f}' if pain_strike != -1 else 'N/A'}")
        else: analysis_results.append(f"近月 ({near_exp}) 選擇權數據不足，無法計算 P/C Ratio 或最大痛點。")

        # 準備 Plotly 圖表數據
        plotly_json_str = ""; range_pct = 0.20 if current_price < 100 else (0.15 if 100 <= current_price < 500 else 0.10)
        min_s, max_s = current_price * (1-range_pct), current_price * (1+range_pct); all_strikes = set()
        def prep_plot_data(opt_data, suffix, min_strike, max_strike): # 輔助函數準備繪圖數據
            if opt_data is None or opt_data['calls'].empty or opt_data['puts'].empty: return pd.DataFrame(), pd.DataFrame()
            c, p = opt_data['calls'].copy(), opt_data['puts'].copy()
            for df_loop in [c,p]:
                for col_loop in ['strike','openInterest','volume']: df_loop[col_loop] = pd.to_numeric(df_loop.get(col_loop,0),errors='coerce').fillna(0)
                df_loop.rename(columns={'openInterest':f'oi{suffix}', 'volume':f'vol{suffix}'},inplace=True)
                df_loop = df_loop[df_loop['strike'].between(min_strike,max_strike)]; all_strikes.update(df_loop['strike'])
            return c.set_index('strike'), p.set_index('strike')

        c_n, p_n = prep_plot_data(near_data, '_n', min_s, max_s); c_w, p_w = prep_plot_data(week_data, '_w', min_s, max_s); c_m, p_m = prep_plot_data(month_data, '_m', min_s, max_s)
        if not all_strikes: analysis_results.append("圖表資訊：在選定履約價範圍內無足夠數據可供繪圖。"); return "\n".join(analysis_results), ""

        # 合併數據並創建 Plotly 圖表
        plot_df = pd.DataFrame(index=sorted(list(all_strikes)))
        for df_loop, sfx_loop in [(c_n,'_call'),(p_n,'_put'),(c_w,'_call'),(p_w,'_put'),(c_m,'_call'),(p_m,'_put')]:
            if not df_loop.empty: plot_df = plot_df.join(df_loop.add_suffix(sfx_loop)) # 使用 add_suffix 避免重複列名
        plot_df = plot_df.fillna(0); fig = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=("未平倉量(OI)", "成交量(Volume)"))
        colors = {"call_near":"rgb(220,53,69)","put_near":"rgb(25,135,84)","week":"rgb(13,110,253)","month":"rgb(102,16,242)"} # 定義顏色

        # 迭代繪製不同到期日的 OI 和 Volume
        exp_map = {'_n': near_exp, '_w': week_exp, '_m': month_exp}
        base_map = {'oi': {}, 'vol': {}} # 用於堆疊圖的基線

        for term_suffix, exp_date_str in exp_map.items():
            if not exp_date_str: continue # 如果該到期日不存在則跳過

            # 處理 Call OI 和 Volume
            oi_call_col = f'oi{term_suffix}_call'; vol_call_col = f'vol{term_suffix}_call'
            base_oi_call = base_map['oi'].get('call', pd.Series(0, index=plot_df.index))
            base_vol_call = base_map['vol'].get('call', pd.Series(0, index=plot_df.index))

            if oi_call_col in plot_df and plot_df[oi_call_col].sum() > 0:
                fig.add_trace(go.Bar(y=plot_df.index, x=plot_df[oi_call_col], name=f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Call OI", orientation='h', marker_color=colors.get(f'call{term_suffix}', colors['call_near']), base=base_oi_call, showlegend=True), 1, 1)
                base_map['oi']['call'] = base_oi_call + plot_df[oi_call_col]
            if vol_call_col in plot_df and plot_df[vol_call_col].sum() > 0:
                fig.add_trace(go.Bar(y=plot_df.index, x=plot_df[vol_call_col], name=f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Call Vol", orientation='h', marker_color=colors.get(f'call{term_suffix}', colors['call_near']), base=base_vol_call, showlegend=False), 1, 2)
                base_map['vol']['call'] = base_vol_call + plot_df[vol_call_col]

            # 處理 Put OI 和 Volume
            oi_put_col = f'oi{term_suffix}_put'; vol_put_col = f'vol{term_suffix}_put'
            base_oi_put = base_map['oi'].get('put', pd.Series(0, index=plot_df.index))
            base_vol_put = base_map['vol'].get('put', pd.Series(0, index=plot_df.index))

            if oi_put_col in plot_df and plot_df[oi_put_col].sum() > 0:
                fig.add_trace(go.Bar(y=plot_df.index, x=-plot_df[oi_put_col], name=f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Put OI", orientation='h', marker_color=colors.get(f'put{term_suffix}', colors['put_near']), base=-base_oi_put, showlegend=True), 1, 1)
                base_map['oi']['put'] = base_oi_put + plot_df[oi_put_col]
            if vol_put_col in plot_df and plot_df[vol_put_col].sum() > 0:
                fig.add_trace(go.Bar(y=plot_df.index, x=-plot_df[vol_put_col], name=f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Put Vol", orientation='h', marker_color=colors.get(f'put{term_suffix}', colors['put_near']), base=-base_vol_put, showlegend=False), 1, 2)
                base_map['vol']['put'] = base_vol_put + plot_df[vol_put_col]

        y_rng = plot_df.index.max() - plot_df.index.min() if not plot_df.empty else 10
        dtick = 20 if y_rng > 200 else (10 if y_rng > 100 else (5 if y_rng > 30 else (2.5 if y_rng > 10 else (1 if y_rng > 5 else max(round(y_rng/10,1),0.5)))))
        fig.update_layout(title_text=f"{ticker_symbol} 選擇權分佈 ({datetime.now().strftime('%Y-%m-%d')})", barmode='stack', height=max(600,len(all_strikes)*bar_height_multiplier*20), yaxis_title="履約價", xaxis_title="未平倉量", xaxis2_title="成交量", legend_title_text='圖例', plot_bgcolor='rgba(240,240,240,0.95)', paper_bgcolor='rgba(255,255,255,1)', font=dict(family="Arial,sans-serif",size=10))
        fig.update_yaxes(tickmode='linear', dtick=dtick); fig.add_shape(type="line",x0=-1e12,y0=current_price,x1=1e12,y1=current_price,line=dict(color="Black",width=1,dash="dash"),row=1,col=1); fig.add_shape(type="line",x0=-1e12,y0=current_price,x1=1e12,y1=current_price,line=dict(color="Black",width=1,dash="dash"),row=1,col=2)
        plotly_json_str = fig.to_json(); logger.info(f"選擇權分析：{ticker_symbol} Plotly 圖表已生成。")
    except Exception as e: logger.error(f"選擇權分析：處理 {ticker_symbol} 時發生未預期錯誤：{e}", exc_info=True); return f"處理 {ticker_symbol} 時發生未預期錯誤: {e}", ""
    return "\n".join(analysis_results), plotly_json_str

def get_alpha_vantage_data(symbols: list[str], api_key: str = None) -> dict[str, pd.DataFrame]:
    """
    模擬從 Alpha Vantage 獲取數據。如果 API 金鑰缺失，則返回帶有正確欄位結構的空 DataFrame。
    實際的 API 調用邏輯在此 MVP 版本中省略。

    Args:
        symbols (list[str]): 股票代號列表。
        api_key (str, optional): Alpha Vantage API 金鑰。預設為 None。

    Returns:
        dict[str, pd.DataFrame]: 一個字典，鍵為 symbol，值為 Pandas DataFrame。
                                 如果金鑰缺失或在此 MVP 中，DataFrame 為空但包含預期欄位。
    """
    data_frames = {}; expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not api_key:
        logger.warning("Alpha Vantage：API 金鑰未提供。將為所有請求的 symbols 返回空的 DataFrame。")
        for symbol in symbols: data_frames[symbol] = pd.DataFrame(columns=expected_columns)
    else: # API 金鑰已提供，但 MVP 中不執行實際調用
        logger.info(f"Alpha Vantage：API 金鑰已提供 (長度: {len(api_key)})。在此 MVP 中，仍返回空 DataFrame 以模擬無數據情況或避免實際調用。")
        for symbol in symbols: data_frames[symbol] = pd.DataFrame(columns=expected_columns)
    return data_frames

def get_fred_data(series_ids: list[str], api_key: str = None) -> dict[str, pd.DataFrame]:
    """
    模擬從 FRED 獲取數據。如果 API 金鑰缺失，則返回帶有正確欄位結構的空 DataFrame。
    實際的 API 調用邏輯 (例如使用 fredapi 庫) 在此 MVP 版本中省略。

    Args:
        series_ids (list[str]): FRED series ID 列表。
        api_key (str, optional): FRED API 金鑰。預設為 None。

    Returns:
        dict[str, pd.DataFrame]: 一個字典，鍵為 series_id，值為 Pandas DataFrame (單列，列名為 series_id)。
                                 如果金鑰缺失或在此 MVP 中，DataFrame 為空但包含預期欄位。
    """
    data_frames = {}
    if not api_key:
        logger.warning("FRED：API 金鑰未提供。將為所有請求的 series_ids 返回空的 DataFrame。")
        for series_id in series_ids: data_frames[series_id] = pd.DataFrame(columns=[series_id]) # 列名即 series_id
    else: # API 金鑰已提供，但 MVP 中不執行實際調用
        logger.info(f"FRED：API 金鑰已提供 (長度: {len(api_key)})。在此 MVP 中，仍返回空 DataFrame 以模擬無數據情況或避免實際調用。")
        for series_id in series_ids: data_frames[series_id] = pd.DataFrame(columns=[series_id])
    return data_frames

def calculate_dealer_stress_index(data_df: pd.DataFrame) -> tuple[str, str]:
    """
    計算交易商壓力指數，並根據數據完整性進行降級處理。
    在此 MVP 版本中，計算邏輯被極大簡化，主要依賴 VIX 指數。

    Args:
        data_df (pd.DataFrame): 包含計算所需指標的 Pandas DataFrame。
                                預期至少包含 'VIX_Close' 欄位。

    Returns:
        tuple[str, str]: 一個元組 (index_value_str, status_text_str)，均為繁體中文。
                         index_value_str: 計算出的壓力指數值，或 "N/A"。
                         status_text_str: 計算狀態的描述文字。
    """
    logger.info("壓力指數：開始計算...")
    required_cols_for_full_calculation = {'vix': 'VIX_Close'} # MVP 中簡化依賴
    available_components = []; component_values = {}

    vix_col_name = required_cols_for_full_calculation['vix']
    if vix_col_name in data_df.columns and data_df[vix_col_name].notna().any():
        try:
            latest_vix = data_df[vix_col_name].dropna().iloc[-1] # 取最新的有效 VIX 值
            component_values['vix'] = latest_vix
            available_components.append('VIX 指數')
            logger.info(f"壓力指數：找到 VIX 數據，最新值: {latest_vix:.2f}")
        except IndexError: logger.warning(f"壓力指數：欄位 {vix_col_name} 存在但為空或全是NaN，無法提取最新值。")
        except Exception as e: logger.warning(f"壓力指數：提取 VIX 最新值時出錯: {e}")
    else: logger.warning(f"壓力指數：缺少關鍵數據欄位 {vix_col_name} 或該欄位數據為空。")

    if not available_components: # 如果沒有任何可用組件 (在此 MVP 中即沒有 VIX)
        logger.warning("壓力指數：數據不足，無法計算。"); return "N/A", "數據不足無法計算"

    # MVP 簡化計算邏輯：基於 VIX 的示意性壓力等級
    stress_value = 0
    if 'vix' in component_values:
        vix_val = component_values['vix']
        if vix_val > 35: stress_value = 85       # 極高壓力
        elif vix_val > 25: stress_value = 65   # 較高壓力
        elif vix_val > 18: stress_value = 45   # 中等壓力
        else: stress_value = 25                # 較低壓力

    status_text = f"（基於 {', '.join(available_components)} 計算，結果僅供參考）" # MVP 狀態說明
    logger.info(f"壓力指數：計算完成。值: {stress_value:.0f}, 狀態: {status_text}")
    return f"{stress_value:.0f}", status_text

# --- HTML Parts Definition & Assembly ---
# --- HTML 組件定義與組裝 ---
HTML_PARTS = {
    'doctype': '<!DOCTYPE html>\n',
    'html_open': '<html lang="zh-Hant">\n', # 指定語言為繁體中文
    'head_open': '<head>\n',
    'head_content': '',  # 將由 CSS 和其他 head 元素填充
    'head_close': '</head>\n',
    'body_open': '<body class="light-mode">\n', # 預設為亮色模式
    'body_content': '',  # 將由各內容區塊填充
    'scripts': '',       # JavaScript 腳本
    'body_close': '</body>\n',
    'html_close': '</html>'
}

# --- Populate head_content (CSS and other head elements) ---
# --- 填充 head_content (CSS 及其他 head 元素) ---
HTML_PARTS['head_content'] = """\
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>金融市場分析與風險評估系統 MVP</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script> <!-- 引入 Plotly.js CDN -->
<style>
    /* 全局變量定義，用於主題切換 */
    :root {
        --body-bg-light: #f4f7f9; --text-color-light: #333;
        --body-bg-dark: #1a1a1a; --text-color-dark: #f0f0f0;
        --content-section-bg-light: #ffffff; --content-section-border-light: #e0e0e0;
        --content-section-bg-dark: #2c2c2c; --content-section-border-dark: #444;
        --button-bg-light: #007bff; --button-text-light: white;
        --button-bg-dark: #0056b3; --button-text-dark: white;
        --input-bg-light: #fff; --input-text-light: #333; --input-border-light: #ccc;
        --input-bg-dark: #333; --input-text-dark: #f0f0f0; --input-border-dark: #555;
    }
    /* 通用頁面樣式 */
    body {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: var(--body-bg-light); color: var(--text-color-light); transition: background-color 0.3s, color 0.3s; font-size: 16px; line-height: 1.6;}
    .container {width: 90%; max-width: 1600px; margin: 0 auto; padding: 20px;}
    /* 暗色模式特定樣式 */
    body.dark-mode {background-color: var(--body-bg-dark); color: var(--text-color-dark);}
    body.dark-mode .card, body.dark-mode .content-section, body.dark-mode header#page-header, body.dark-mode nav#main-navigation {background-color: var(--content-section-bg-dark); color: var(--text-color-dark); border-color: var(--content-section-border-dark);}
    body.dark-mode button {background-color: var(--button-bg-dark); color: var(--button-text-dark); border-color: var(--content-section-border-dark);}
    body.dark-mode input, body.dark-mode select, body.dark-mode textarea {background-color: var(--input-bg-dark); color: var(--input-text-dark); border-color: var(--input-border-dark);}
    input, select, textarea {background-color: var(--input-bg-light); color: var(--input-text-light); border: 1px solid var(--input-border-light); padding: 8px; border-radius: 4px;}
    body.dark-mode .data-table th, body.dark-mode .data-table td {background-color: var(--content-section-bg-dark); color: var(--text-color-dark); border-color: var(--content-section-border-dark);}
    body.dark-mode .data-table tr:nth-child(even) {background-color: #333333;} body.dark-mode .data-table tr:hover {background-color: #404040;}
    button:hover {background-color: #0056b3;} body.dark-mode button:hover {background-color: #003d80;} /* 按鈕懸停效果 */
    a {color: #007bff; text-decoration:none;} body.dark-mode a {color: #66b3ff;} body.dark-mode a:hover {color: #99ccff;}
    .nav-link.active {background-color: #007bff;} body.dark-mode .nav-link.active {background-color: #0056b3;}
    /* 頁首樣式 */
    header#page-header {background-color: #ffffff; color: #333; padding: 15px 0; border-bottom: 1px solid #e0e0e0; text-align: center; position: sticky; top: 0; z-index: 1000;}
    header#page-header h1 {margin: 0; font-size: 1.8em; color: #0056b3;} body.dark-mode header#page-header h1 {color: #66b3ff;}
    .header-subtitle {font-size: 0.9em; color: #666; margin-top: 5px;} body.dark-mode .header-subtitle {color: #ccc;}
    /* 導航列樣式 */
    nav#main-navigation {background-color: #333; padding: 10px 0; text-align: center; position: sticky; top: 77px; z-index: 999; border-bottom: 1px solid #444;} /* top 值基於頁首高度 */
    body.dark-mode nav#main-navigation {background-color: #222; border-bottom: 1px solid #333;}
    .nav-list {list-style: none; padding: 0; margin: 0; display: inline-block;} .nav-item {display: inline-block; margin-right: 10px;}
    .nav-link {color: #fff; text-decoration: none; padding: 8px 15px; border-radius: 4px; font-weight: 500;}
    .nav-controls {display: inline-block; margin-left: 20px;} .nav-controls button {padding: 8px 12px; margin-left: 5px; border:none; border-radius:4px; cursor:pointer;}
    .hidden-icon {display: none;} /* 用於主題切換圖標 */
    /* 主要內容區樣式 */
    #main-content {padding-top: 20px; min-height: calc(100vh - 250px);} /* 減去頁首、導航和頁尾的大致高度 */
    .content-section {padding: 25px; margin-bottom: 25px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid var(--content-section-border-light);}
    .card {padding: 20px; margin-bottom: 20px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;}
    .content-section-title, .content-section h2 {color: #0056b3; margin-top: 0; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; font-size: 1.5em; margin-bottom: 20px;}
    body.dark-mode .content-section-title, body.dark-mode .content-section h2 {color: #66b3ff; border-bottom-color: #444;}
    .card-title, .content-section h3 {color: #007bff; font-size: 1.2em; margin-top: 0; margin-bottom: 15px;}
    body.dark-mode .card-title, body.dark-mode .content-section h3 {color: #79b8ff;}
    /* 美股選擇權分析區塊特定樣式 */
    .options-input-area {margin-bottom:20px; display:flex; align-items:center;}
    #options-analysis-text {white-space: pre-wrap; padding:15px; border-radius:5px; margin-top:20px; border: 1px solid var(--content-section-border-light); background-color: var(--content-section-bg-light); }
    body.dark-mode #options-analysis-text { background-color: var(--content-section-bg-dark); border-color: var(--content-section-border-dark); }
    #options-plotly-chart {min-height: 600px; margin-top: 15px;} /* Plotly 圖表容器 */
    .chart-placeholder {display:flex; justify-content:center; align-items:center; height:100%; color: #888;} /* 圖表加載提示 */
    /* 頁尾樣式 */
    footer#page-footer {text-align:center;padding:20px 0;margin-top:30px;background-color:#e9ecef;border-top:1px solid #ddd;font-size:0.9em;width:100%;}
    body.dark-mode footer#page-footer {background-color:#222;border-top-color:#444;color:#ccc;}
    /* 打印樣式 */
    @media print { body {background-color:#fff !important; color:#000 !important; font-size:10pt;} nav#main-navigation, header#page-header .nav-controls, footer#page-footer, #main-theme-toggle, #print-report-button {display:none !important;} header#page-header {position:static; text-align:left;} /* 其他打印樣式... */ }
</style>
"""

# --- Assemble body_content ---
# --- 組裝 body_content ---
# Header and Navigation - 頁首與導航列
header_nav_html = """\
<header id="page-header"><div class="container"><h1>金融市場分析與風險評估系統</h1><p class="header-subtitle" id="data-freshness-container">數據更新於：(稍後由 JS 更新)</p></div></header>
<nav id="main-navigation"><div class="container"><ul class="nav-list">
<li class="nav-item"><a href="#dashboard-overview-section" class="nav-link active">核心儀表板</a></li>
<li class="nav-item"><a href="#macro-environment" class="nav-link">宏觀環境</a></li>
<li class="nav-item"><a href="#stock-options-analysis" class="nav-link">美股選擇權</a></li>
<li class="nav-item"><a href="#market-structure" class="nav-link">市場結構</a></li>
</ul><div class="nav-controls"><button id="main-theme-toggle"><span id="main-theme-toggle-text">暗色模式</span></button><button id="print-report-button">打印</button></div></div></nav>"""
HTML_PARTS['body_content'] = header_nav_html
HTML_PARTS['body_content'] += '<main id="main-content" class="container">\n' # 主要內容容器開始

# Core Dashboard Section - 核心儀表板區塊
# (此處應為之前步驟中定義的 dashboard_overview_html 完整內容)
dashboard_overview_html = """\
<section id="dashboard-overview-section" class="content-section">
    <h2 class="content-section-title">核心儀表板</h2>
    <div class="kpi-grid">
        <div class="card"><h3 class="card-title">核心壓力儀表</h3><div id="pressure-gauge-chart" class="plotly-chart-container" style="min-height: 250px;">核心壓力儀表 (Plotly.js) 將顯示於此 (佔位符)</div><div class="text-center mt-1">壓力指數: <span id="pressure-gauge-value">--</span> (<span id="pressure-gauge-status">數據不足</span>)</div></div>
        <div class="card"><h3 class="card-title">殖利率曲線快照</h3><div id="mini-yield-curve-chart" class="plotly-chart-container" style="min-height: 250px;">迷你殖利率曲線 (Plotly.js) 將顯示於此 (佔位符)</div><div class="text-center mt-1">2s10s 利差: <span id="yield-spread-2s10s">--</span> bps</div></div>
    </div>
    <div class="card"><h3 class="card-title">關鍵指標</h3><div class="kpi-grid">
        <div class="kpi-card"><h4>VIX 指數</h4><p id="kpi-vix-value" class="kpi-value">--</p></div>
        <div class="kpi-card"><h4>十年期公債殖利率 (DGS10)</h4><p id="kpi-dgs10-value" class="kpi-value">--</p></div>
        <div class="kpi-card"><h4>MOVE 指數</h4><p id="kpi-move-value" class="kpi-value">--</p></div>
        <div class="kpi-card"><h4>SOFR 利率</h4><p id="kpi-sofr-value" class="kpi-value">--</p></div>
    </div></div>
    <div class="card"><h3 class="card-title">市場主題摘要</h3><div id="market-summary-text" class="text-interpretation">此處將以 1-2 句精煉的中文文字，總結當前影響債券市場最主要的宏觀主題或事件。(佔位符)</div></div>
</section>"""
HTML_PARTS['body_content'] += dashboard_overview_html

# Macro Environment Section - 宏觀環境分析區塊
# (此處應為之前步驟中定義的 macro_environment_html 完整內容)
macro_environment_html = """\
<section id="macro-environment" class="content-section">
    <h2 class="content-section-title">層級一：全球宏觀與政策環境分析</h2>
    <!-- 此處應包含所有宏觀經濟卡片，例如全球經濟展望、美國GDP、CPI等 -->
    <div class="card"><h3 class="card-title">跨市場關聯性分析 <span class="info-icon" title="觀察主要資產類別相關性及風險溢價指標。">&#9432;</span></h3><div id="cross-asset-chart" class="plotly-chart-container" style="display:none;">跨市場關聯圖表</div><div class="text-interpretation"><p>VIX 指數 (股市恐慌指數) 最新值：<span id="vix-value-macro">--</span></p></div></div>
</section>""" # 簡化示例，確保 VIX 宏觀佔位符存在
HTML_PARTS['body_content'] += macro_environment_html

# Stock Options Analysis Section - 美股選擇權籌碼分析區塊
options_section_html = """
<section id="stock-options-analysis" class="content-section">
    <h2 class="content-section-title">美股選擇權籌碼分析</h2>
    <div class="options-input-area">
        <label for="stock-ticker-input" style="margin-right: 10px;">股票代號：</label>
        <input type="text" id="stock-ticker-input" placeholder="例如：AAPL" value="AAPL">
        <button id="analyze-stock-btn">分析</button>
    </div>
    <div id="options-analysis-text">請輸入美股代號並點擊分析。</div>
    <div id="options-plotly-chart" class="plotly-chart-container" style="margin-top: 15px;"></div>
</section>"""
HTML_PARTS['body_content'] += options_section_html

# Market Structure Section (hidden) - 市場結構分析區塊 (預設隱藏)
market_structure_html = "<section id='market-structure' class='content-section' style='display:none;'><h2>層級二：市場結構與流動性分析</h2><p>此區塊內容將在後續實現。</p></section>"
HTML_PARTS['body_content'] += market_structure_html
HTML_PARTS['body_content'] += '</main>\n' # 主要內容容器結束

# Footer - 頁尾
current_year = datetime.now().year # 動態獲取當前年份
HTML_PARTS['body_content'] += f"""<footer id="page-footer"><div class="container"><p>© {current_year} 金融市場分析與風險評估系統 MVP. 版權所有. (此為範例頁尾，請替換為實際內容)</p></div></footer>"""

# --- JavaScripts ---
# (此處應為之前步驟中定義的 scripts_html 完整內容，包含 AAPL 嵌入數據的邏輯)
# 為簡潔起見，這裡僅作示意。實際腳本要包含主題切換、數據更新時間、選擇權分析按鈕邏輯及 Plotly 嵌入。
scripts_html = """\
<script>
// 全局 AAPL 數據 (由 Python 注入)
// window.embeddedAAPLData = { ticker: "AAPL", analysisText: "...", plotlyJson: "{...}" };

document.addEventListener('DOMContentLoaded', function () {
    // 主題切換邏輯
    const themeToggleButton = document.getElementById('main-theme-toggle');
    const body = document.body;
    const themeToggleText = document.getElementById('main-theme-toggle-text');
    const applyTheme = (theme) => { /* ... (同前) ... */ };
    const currentTheme = localStorage.getItem('theme');
    if (currentTheme) applyTheme(currentTheme); else if (body.classList.contains('dark-mode')) applyTheme('dark-mode'); else applyTheme('light-mode');
    if(themeToggleButton) themeToggleButton.addEventListener('click', () => { /* ... (同前) ... */ });

    // 數據更新時間邏輯
    const dataFreshnessContainer = document.getElementById('data-freshness-container');
    if (dataFreshnessContainer) { /* ... (同前) ... */ }

    // 導航平滑滾動邏輯
    document.querySelectorAll('nav#main-navigation a.nav-link').forEach(anchor => { /* ... (同前) ... */ });

    // 美股選擇權分析邏輯
    const stockTickerInput = document.getElementById('stock-ticker-input');
    const analyzeStockBtn = document.getElementById('analyze-stock-btn');
    const optionsAnalysisTextDiv = document.getElementById('options-analysis-text');
    const optionsPlotlyChartDiv = document.getElementById('options-plotly-chart');
    if (analyzeStockBtn) {
        analyzeStockBtn.addEventListener('click', () => {
            const ticker = stockTickerInput.value.trim().toUpperCase();
            if (!ticker) { optionsAnalysisTextDiv.textContent = '請輸入有效的股票代號。'; Plotly.purge(optionsPlotlyChartDiv); optionsPlotlyChartDiv.innerHTML = ''; return; }
            optionsAnalysisTextDiv.textContent = `正在分析 ${ticker} 請稍候...`; Plotly.purge(optionsPlotlyChartDiv);
            optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder">圖表加載中...</div>';
            if (ticker === window.embeddedAAPLData?.ticker) {
                 optionsAnalysisTextDiv.textContent = window.embeddedAAPLData.analysisText;
                 if (window.embeddedAAPLData.plotlyJson) {
                    try { Plotly.newPlot(optionsPlotlyChartDiv, JSON.parse(window.embeddedAAPLData.plotlyJson).data, JSON.parse(window.embeddedAAPLData.plotlyJson).layout); }
                    catch (e) { console.error("Plotly JSON 解析/繪圖錯誤:", e); optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder">圖表加載失敗。</div>'; }
                 } else { optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder">無法生成圖表數據。</div>'; }
            } else {
                 optionsAnalysisTextDiv.textContent = `對 ${ticker} 的即時分析功能將在後續版本中實現。目前僅提供 AAPL 範例數據的靜態展示。`;
                 optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder">圖表功能待實現。</div>';
            }
        });
    }
    // 頁面加載時自動分析 AAPL (如果數據已嵌入)
    if (window.embeddedAAPLData && window.embeddedAAPLData.ticker === 'AAPL' && stockTickerInput.value === 'AAPL') {
        analyzeStockBtn.click(); // 模擬點擊以觸發顯示
    }
});
</script>"""
HTML_PARTS['scripts'] = scripts_html # 實際應為完整的 JS 內容


if __name__ == "__main__":
    logger.info("主腳本開始執行...")

    # 步驟 1: 獲取 VIX 數據 (yfinance)
    vix_data_map = get_yfinance_data(['^VIX'], period="5d")
    vix_df = vix_data_map.get('^VIX', pd.DataFrame()) # 使用 get 並提供默認空 DataFrame
    latest_vix_value_str = "--"
    if not vix_df.empty:
        try: latest_vix_value_str = f"{vix_df['Close'].iloc[-1]:.2f}"; logger.info(f"成功獲取最新 VIX 收盤價: {latest_vix_value_str}")
        except IndexError: logger.warning("VIX DataFrame 非空但無法提取最新收盤價 (可能是索引問題)。")
        except Exception as e: logger.warning(f"提取最新 VIX 收盤價失敗: {e}")
    else: logger.warning("未能獲取 VIX 數據或數據為空。")

    # 更新 HTML 中的 VIX 相關佔位符
    HTML_PARTS['body_content'] = HTML_PARTS['body_content'].replace('<p id="kpi-vix-value" class="kpi-value">--</p>', f'<p id="kpi-vix-value" class="kpi-value">{latest_vix_value_str}</p>', 1)
    HTML_PARTS['body_content'] = HTML_PARTS['body_content'].replace('<span id="vix-value-macro">--</span>', f'<span id="vix-value-macro">{latest_vix_value_str}</span>', 1)

    # 步驟 2: 準備壓力指數計算的輸入數據並計算
    data_for_stress_index = pd.DataFrame()
    if not vix_df.empty: data_for_stress_index['VIX_Close'] = vix_df['Close']
    stress_index_value_str, stress_index_status_str = calculate_dealer_stress_index(data_for_stress_index)
    logger.info(f"壓力指數計算結果: 值='{stress_index_value_str}', 狀態='{stress_index_status_str}'")

    # 更新 HTML 中的壓力儀表佔位符
    HTML_PARTS['body_content'] = HTML_PARTS['body_content'].replace('<span id="pressure-gauge-value">--</span>', f'<span id="pressure-gauge-value">{stress_index_value_str}</span>', 1)
    HTML_PARTS['body_content'] = HTML_PARTS['body_content'].replace('<span id="pressure-gauge-status">數據不足</span>', f'<span id="pressure-gauge-status">{stress_index_status_str}</span>', 1)
    logger.info("HTML 中的壓力儀表值和狀態已更新。")

    # 步驟 3: 測試 NY Fed 數據獲取 (實際應用中可能用於壓力指數或其他分析)
    logger.info("測試 NY Fed 數據獲取...")
    nyfed_series = get_nyfed_dealer_positions()
    if not nyfed_series.empty: logger.info(f"NY Fed Series Head:\n{nyfed_series.head().to_string()}")
    else: logger.warning("NY Fed Series 為空。")

    # 步驟 4: 測試 Alpha Vantage 和 FRED 數據獲取降級 (實際應用中會傳入 API 金鑰)
    logger.info("測試 Alpha Vantage 數據獲取降級 (無 API 金鑰)...")
    av_data = get_alpha_vantage_data(['SPY']) # 示例: SPY
    logger.info(f"Alpha Vantage (SPY) DataFrame Columns: {av_data.get('SPY', pd.DataFrame()).columns.tolist()}, Empty: {av_data.get('SPY', pd.DataFrame()).empty}")

    logger.info("測試 FRED 數據獲取降級 (無 API 金鑰)...")
    fred_data = get_fred_data(['DGS10']) # 示例: DGS10
    logger.info(f"FRED (DGS10) DataFrame Columns: {fred_data.get('DGS10', pd.DataFrame()).columns.tolist()}, Empty: {fred_data.get('DGS10', pd.DataFrame()).empty}")

    # 步驟 5: 為 AAPL 生成選擇權分析數據以嵌入 HTML，用於客戶端演示
    logger.info("生成 AAPL 選擇權分析數據以嵌入...")
    aapl_analysis_text, aapl_plotly_json = analyze_stock_options("AAPL") # 預設分析 AAPL
    # 創建一個 script 標籤來嵌入這些數據，以便客戶端 JavaScript 可以訪問
    # 注意：對 analysisText 和 plotlyJson 中的反引號、換行符等進行轉義，以確保 JS 字串的有效性
    escaped_aapl_text = aapl_analysis_text.replace('`', '\\`').replace('\n', '\\n')
    escaped_aapl_json = aapl_plotly_json.replace('`', '\\`') # Plotly JSON 通常不含換行符，但反引號需轉義

    embedded_data_script = f"""
<script>
    window.embeddedAAPLData = {{
        ticker: "AAPL",
        analysisText: `{escaped_aapl_text}`,
        plotlyJson: `{escaped_aapl_json}`
    }};
</script>
"""
    # 將此嵌入腳本加到主要腳本之前，以確保 window.embeddedAAPLData 在主腳本執行時可用
    HTML_PARTS['scripts'] = embedded_data_script + HTML_PARTS.get('scripts', '')


    # 步驟 6: 組裝並寫入最終 HTML 文件
    logger.info("開始組裝最終 HTML 內容...")
    full_html = (
        HTML_PARTS.get('doctype', '') +
        HTML_PARTS.get('html_open', '') +
        HTML_PARTS.get('head_open', '') +
        HTML_PARTS.get('head_content', '') +
        HTML_PARTS.get('head_close', '') +
        HTML_PARTS.get('body_open', '') +
        HTML_PARTS.get('body_content', '') + # body_content 應已包含 </main> 和 footer
        HTML_PARTS.get('scripts', '') +      # JavaScript 腳本
        HTML_PARTS.get('body_close', '') +
        HTML_PARTS.get('html_close', '')
    )

    output_filename = "financial_dashboard_mvp.html"
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(full_html)
        logger.info(f"成功生成 MVP HTML 文件：{output_filename}")
    except IOError as e: # 更具體的 IO 錯誤處理
        logger.error(f"寫入 HTML 文件 {output_filename} 失敗: {e}")
    except Exception as e_general: # 捕獲其他可能的錯誤
        logger.error(f"生成 HTML 文件時發生未預期錯誤: {e_general}")

    logger.info("主腳本執行完畢。")
    pass
