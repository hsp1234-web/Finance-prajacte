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
# (All data fetching and analysis functions: get_yfinance_data, get_nyfed_dealer_positions,
# find_closest_date, analyze_stock_options, get_alpha_vantage_data, get_fred_data,
# calculate_dealer_stress_index remain as defined in the previous version of the file.
# For brevity, their full code is not repeated here in this thought block, but they are part of the file being written.)

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

            for h_candidate in possible_headers:
                try:
                    excel_content.seek(0)
                    all_sheets = pd.read_excel(excel_content, header=h_candidate, sheet_name=None, engine='openpyxl')
                    sheet_to_use_name = None
                    if isinstance(all_sheets, dict):
                        potential_names = {name.lower().strip(): name for name in all_sheets.keys()}
                        if 'data' in potential_names: sheet_to_use_name = potential_names['data']
                        elif 'sheet1' in potential_names: sheet_to_use_name = potential_names['sheet1']
                        elif 'pdposgsc' in potential_names: sheet_to_use_name = potential_names['pdposgsc']
                        elif all_sheets: sheet_to_use_name = list(all_sheets.keys())[0]
                    current_df_peek = all_sheets[sheet_to_use_name].head() if sheet_to_use_name and isinstance(all_sheets, dict) else (all_sheets.head() if not isinstance(all_sheets, dict) else None)
                    if current_df_peek is None: continue
                    cols_lower = [str(c).lower().strip() for c in current_df_peek.columns]; ts_col, val_col, date_col = None, None, None
                    for var in ['time series', 'series id', 'series name']:
                        if var in cols_lower: ts_col = current_df_peek.columns[cols_lower.index(var)]; break
                    for var in ['value (millions)', 'value', 'amount']:
                        if var in cols_lower: val_col = current_df_peek.columns[cols_lower.index(var)]; break
                    if 'as of date' in cols_lower: date_col = current_df_peek.columns[cols_lower.index('as of date')]
                    elif 'effective date' in cols_lower: date_col = current_df_peek.columns[cols_lower.index('effective date')]
                    elif current_df_peek.columns.size > 0 and ('date' in str(current_df_peek.columns[0]).lower() or 'period' in str(current_df_peek.columns[0]).lower()): date_col = current_df_peek.columns[0]
                    if ts_col and val_col and date_col:
                        header_row = h_candidate; excel_content.seek(0)
                        if isinstance(all_sheets, dict) and sheet_to_use_name:
                            data_positions_long = pd.read_excel(excel_content, header=header_row, sheet_name=sheet_to_use_name, index_col=date_col, parse_dates=True, engine='openpyxl')
                        else:
                            data_positions_long = pd.read_excel(excel_content, header=header_row, index_col=date_col, parse_dates=True, engine='openpyxl')
                        logger.info(f"NY Fed：文件 {file_source_name}，使用表頭行 {header_row+1}，日期列 '{date_col}'。"); break
                except Exception: excel_content.seek(0); continue
            if data_positions_long is None: logger.warning(f"NY Fed：文件 {file_source_name} 無法自動檢測有效的表頭或列結構，跳過。"); continue
            if not isinstance(data_positions_long.index, pd.DatetimeIndex): data_positions_long.index = pd.to_datetime(data_positions_long.index, errors='coerce')
            data_positions_long = data_positions_long[pd.notna(data_positions_long.index)]; data_positions_long.index = data_positions_long.index.normalize()
            if data_positions_long.empty: logger.info(f"NY Fed：文件 {file_source_name} 清理日期後為空。"); continue
            actual_ts_col, actual_val_col = None, None
            cols_lower_full = [str(c).lower().strip() for c in data_positions_long.columns]
            for var in ['time series', 'series id', 'series name']:
                if var in cols_lower_full: actual_ts_col = data_positions_long.columns[cols_lower_full.index(var)]; break
            for var in ['value (millions)', 'value', 'amount']:
                if var in cols_lower_full: actual_val_col = data_positions_long.columns[cols_lower_full.index(var)]; break
            if not actual_ts_col or not actual_val_col: logger.warning(f"NY Fed：文件 {file_source_name} 清理後仍缺少時間序列或數值列，跳過。"); continue
            data_positions_long[actual_val_col] = pd.to_numeric(data_positions_long[actual_val_col], errors='coerce'); data_positions_long.dropna(subset=[actual_val_col, actual_ts_col], inplace=True)
            if data_positions_long.empty: logger.info(f"NY Fed：文件 {file_source_name} 移除NaN後為空。"); continue
            data_positions_long.reset_index(inplace=True); date_col_actual_name = data_positions_long.columns[0]
            data_positions_long = data_positions_long.groupby([date_col_actual_name, actual_ts_col])[actual_val_col].mean().reset_index()
            data_positions_wide = pd.pivot_table(data_positions_long, index=date_col_actual_name, columns=actual_ts_col, values=actual_val_col, aggfunc='mean')
            if data_positions_wide.empty: logger.info(f"NY Fed：文件 {file_source_name} 轉換為寬格式後為空。"); continue
            target_cols = []
            if 'sbn' in url.lower() or 'currentls' in url.lower(): target_cols = [c for c in data_positions_wide.columns if isinstance(c, str) and c.startswith(sbn_cols_to_sum_prefix)]
            elif 'sbp2013' in url.lower(): target_cols = sbp2013_cols_to_sum
            elif 'sbp2001' in url.lower(): target_cols = sbp2001_cols_to_sum
            cols_in_df = [c for c in target_cols if c in data_positions_wide.columns]
            if not cols_in_df: logger.warning(f"NY Fed：文件 {file_source_name} 未找到任何用於加總的目標欄位。預期欄位: {target_cols if target_cols else sbn_cols_to_sum_prefix}"); continue
            for col in cols_in_df: data_positions_wide[col] = pd.to_numeric(data_positions_wide[col], errors='coerce')
            daily_total = data_positions_wide[cols_in_df].sum(axis=1, skipna=True).dropna(); daily_total = daily_total[daily_total != 0]
            if not daily_total.empty: all_positions_data.append(daily_total); logger.info(f"NY Fed：成功處理並加總文件 {file_source_name} ({len(daily_total)} 筆有效數據)。")
            else: logger.info(f"NY Fed：文件 {file_source_name} 加總後無有效數據。")
        except requests.exceptions.RequestException as e: logger.warning(f"NY Fed：下載文件 {file_source_name} 失敗：{e}")
        except Exception as e: logger.warning(f"NY Fed：處理文件 {file_source_name} 時發生未預期錯誤：{e}", exc_info=True)
    if not all_positions_data: logger.warning("NY Fed：未能成功處理任何一級交易商數據文件，返回空 Series。"); return pd.Series(dtype='float64')
    final_series = pd.concat(all_positions_data).sort_index(); final_series = final_series[~final_series.index.duplicated(keep='last')]
    final_series.name = 'Total_Gross_Positions_Millions'; logger.info(f"NY Fed：一級交易商持倉數據獲取與合併完成，共 {len(final_series)} 筆數據。")
    return final_series

def find_closest_date(target_date: datetime, date_list_str: list[str]) -> str | None:
    """ 從日期字串列表中找出最接近目標日期的日期。 """
    if not date_list_str: return None
    try:
        date_list_dt = [datetime.strptime(d_str, '%Y-%m-%d') for d_str in date_list_str]
        closest_date = min(date_list_dt, key=lambda d: abs(d - target_date))
        return closest_date.strftime('%Y-%m-%d')
    except ValueError as e: logger.error(f"find_closest_date：日期格式錯誤: {e} (輸入列表: {date_list_str})"); return None

def analyze_stock_options(ticker_symbol: str, bar_height_multiplier: float = 0.4) -> tuple[str, str]:
    """ 分析指定美股代號的選擇權鏈數據，計算關鍵指標，並生成 Plotly 圖表的 JSON。 """
    logger.info(f"選擇權分析：開始分析 {ticker_symbol}...")
    analysis_results = []; current_price = None; near_data, week_data, month_data = None, None, None
    near_exp, week_exp, month_exp = None, None, None; default_empty_data = {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
    try:
        ticker = yf.Ticker(ticker_symbol); logger.info(f"選擇權分析：獲取 {ticker_symbol} 股價...")
        try:
            hist = ticker.history(period="5d")
            if not hist.empty: current_price = hist['Close'].iloc[-1]
            if current_price is None or np.isnan(current_price): current_price = ticker.fast_info.get('last_price')
        except Exception as e: logger.warning(f"選擇權分析：獲取 {ticker_symbol} 股價失敗：{e}"); return f"錯誤：無法獲取 {ticker_symbol} 的股價資訊。", ""
        if current_price is None or np.isnan(current_price): return f"錯誤：未能獲取 {ticker_symbol} 的有效股價。", ""
        analysis_results.append(f"目前股價：${current_price:.2f}"); logger.info(f"選擇權分析：{ticker_symbol} 股價 ${current_price:.2f}")
        expirations = ticker.options;
        if not expirations: logger.warning(f"選擇權分析：找不到 {ticker_symbol} 選擇權到期日。"); return f"錯誤：找不到 {ticker_symbol} 的選擇權到期日。", ""
        near_exp = expirations[0]; logger.info(f"選擇權分析：近月到期日: {near_exp}")
        try: near_chain = ticker.option_chain(near_exp); near_data = {'calls': getattr(near_chain, 'calls', pd.DataFrame()), 'puts': getattr(near_chain, 'puts', pd.DataFrame())}
        except Exception as e: logger.warning(f"選擇權分析：無法獲取 {near_exp} 數據: {e}"); near_data = default_empty_data.copy()
        if len(expirations) > 1:
            try:
                near_date_dt = datetime.strptime(near_exp, '%Y-%m-%d'); target_wk_dt = near_date_dt + timedelta(weeks=1)
                week_exp = find_closest_date(target_wk_dt, [d for d in expirations if d > near_exp])
                if week_exp: logger.info(f"選擇權分析：+1週到期日: {week_exp}")
                search_start_dt = datetime.strptime(week_exp, '%Y-%m-%d') if week_exp else near_date_dt
                target_mo_dt = near_date_dt + timedelta(days=30)
                month_exp = find_closest_date(target_mo_dt, [d for d in expirations if d > search_start_dt.strftime('%Y-%m-%d')])
                if month_exp: logger.info(f"選擇權分析：+1月到期日: {month_exp}")
            except Exception as e: logger.warning(f"選擇權分析：尋找未來到期日失敗: {e}")
        if week_exp:
            try: week_chain = ticker.option_chain(week_exp); week_data = {'calls': getattr(week_chain, 'calls', pd.DataFrame()), 'puts': getattr(week_chain, 'puts', pd.DataFrame())}
            except Exception as e: logger.warning(f"選擇權分析：無法獲取 {week_exp} 數據: {e}"); week_data = default_empty_data.copy()
        if month_exp:
            try: month_chain = ticker.option_chain(month_exp); month_data = {'calls': getattr(month_chain, 'calls', pd.DataFrame()), 'puts': getattr(month_chain, 'puts', pd.DataFrame())}
            except Exception as e: logger.warning(f"選擇權分析：無法獲取 {month_exp} 數據: {e}"); month_data = default_empty_data.copy()
        if near_data and not near_data['calls'].empty and not near_data['puts'].empty:
            calls_df, puts_df = near_data['calls'].copy(), near_data['puts'].copy()
            for df_loop in [calls_df, puts_df]:
                for col_loop in ['strike','openInterest','volume']: df_loop[col_loop] = pd.to_numeric(df_loop.get(col_loop,0), errors='coerce').fillna(0)
            vol_pc_ratio = (puts_df['volume'].sum() / calls_df['volume'].sum()) if calls_df['volume'].sum() > 0 else "N/A"
            oi_pc_ratio = (puts_df['openInterest'].sum() / calls_df['openInterest'].sum()) if calls_df['openInterest'].sum() > 0 else "N/A"
            analysis_results.append(f"成交量 P/C Ratio (近月 {near_exp}): {vol_pc_ratio if isinstance(vol_pc_ratio,str) else f'{vol_pc_ratio:.2f}'}")
            analysis_results.append(f"未平倉量 P/C Ratio (近月 {near_exp}): {oi_pc_ratio if isinstance(oi_pc_ratio,str) else f'{oi_pc_ratio:.2f}'}")
            strikes = pd.concat([calls_df['strike'], puts_df['strike']]).unique(); strikes.sort(); pain_strike = -1; min_pain = float('inf')
            if len(strikes)>0:
                call_oi_map = calls_df.set_index('strike')['openInterest']; put_oi_map = puts_df.set_index('strike')['openInterest']
                for s_iter in strikes:
                    loss = sum((s_iter - cs) * oi for cs, oi in call_oi_map.items() if s_iter > cs) + sum((ps - s_iter) * oi for ps, oi in put_oi_map.items() if s_iter < ps)
                    if loss < min_pain: min_pain = loss; pain_strike = s_iter
            analysis_results.append(f"預估最大痛點 (近月 {near_exp}): {f'${pain_strike:.2f}' if pain_strike != -1 else 'N/A'}")
        else: analysis_results.append(f"近月 ({near_exp}) 選擇權數據不足。")
        plotly_json_str = ""; range_pct = 0.20 if current_price < 100 else (0.15 if 100 <= current_price < 500 else 0.10)
        min_s, max_s = current_price * (1-range_pct), current_price * (1+range_pct); all_strikes = set()
        def prep_plot_data(opt_data, suffix, min_strike, max_strike):
            if opt_data is None or opt_data['calls'].empty or opt_data['puts'].empty: return pd.DataFrame(), pd.DataFrame()
            c, p = opt_data['calls'].copy(), opt_data['puts'].copy()
            for df_loop in [c,p]:
                for col_loop in ['strike','openInterest','volume']: df_loop[col_loop] = pd.to_numeric(df_loop.get(col_loop,0),errors='coerce').fillna(0)
                df_loop.rename(columns={'openInterest':f'oi{suffix}', 'volume':f'vol{suffix}'},inplace=True)
                df_loop = df_loop[df_loop['strike'].between(min_strike,max_strike)]; all_strikes.update(df_loop['strike'])
            return c.set_index('strike'), p.set_index('strike')
        c_n,p_n=prep_plot_data(near_data,'_n',min_s,max_s); c_w,p_w=prep_plot_data(week_data,'_w',min_s,max_s); c_m,p_m=prep_plot_data(month_data,'_m',min_s,max_s)
        if not all_strikes: analysis_results.append("圖表資訊：選定範圍內無數據。"); return "\n".join(analysis_results), ""
        plot_df = pd.DataFrame(index=sorted(list(all_strikes)))
        for df_loop, sfx_loop in [(c_n,'_call'),(p_n,'_put'),(c_w,'_call'),(p_w,'_put'),(c_m,'_call'),(p_m,'_put')]:
            if not df_loop.empty: plot_df = plot_df.join(df_loop.add_suffix(sfx_loop))
        plot_df = plot_df.fillna(0); fig = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=("未平倉量(OI)", "成交量(Volume)"))
        colors = {"call_near":"rgb(220,53,69)","put_near":"rgb(25,135,84)","week":"rgb(13,110,253)","month":"rgb(102,16,242)"}
        exp_map = {'_n': near_exp, '_w': week_exp, '_m': month_exp}; base_map = {'oi': {}, 'vol': {}}
        for term_suffix, exp_date_str in exp_map.items():
            if not exp_date_str: continue
            oi_call_col=f'oi{term_suffix}_call'; vol_call_col=f'vol{term_suffix}_call'; oi_put_col=f'oi{term_suffix}_put'; vol_put_col=f'vol{term_suffix}_put'
            base_oi_call=base_map['oi'].get('call',pd.Series(0,index=plot_df.index)); base_vol_call=base_map['vol'].get('call',pd.Series(0,index=plot_df.index))
            base_oi_put=base_map['oi'].get('put',pd.Series(0,index=plot_df.index)); base_vol_put=base_map['vol'].get('put',pd.Series(0,index=plot_df.index))
            name_call,name_put = f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Call", f"{exp_date_str.split('-')[1]}-{exp_date_str.split('-')[2]} Put"
            color_c,color_p = (colors["call_near"] if term_suffix=="_n" else colors["week" if term_suffix=="_w" else "month"]), (colors["put_near"] if term_suffix=="_n" else colors["week" if term_suffix=="_w" else "month"])
            if oi_call_col in plot_df and plot_df[oi_call_col].sum()>0: fig.add_trace(go.Bar(y=plot_df.index,x=plot_df[oi_call_col],name=name_call,orientation='h',marker_color=color_c,base=base_oi_call,showlegend=True),1,1); base_map['oi']['call']=base_oi_call+plot_df[oi_call_col]
            if vol_call_col in plot_df and plot_df[vol_call_col].sum()>0: fig.add_trace(go.Bar(y=plot_df.index,x=plot_df[vol_call_col],name=name_call,orientation='h',marker_color=color_c,base=base_vol_call,showlegend=False),1,2); base_map['vol']['call']=base_vol_call+plot_df[vol_call_col]
            if oi_put_col in plot_df and plot_df[oi_put_col].sum()>0: fig.add_trace(go.Bar(y=plot_df.index,x=-plot_df[oi_put_col],name=name_put,orientation='h',marker_color=color_p,base=-base_oi_put,showlegend=True),1,1); base_map['oi']['put']=base_oi_put+plot_df[oi_put_col]
            if vol_put_col in plot_df and plot_df[vol_put_col].sum()>0: fig.add_trace(go.Bar(y=plot_df.index,x=-plot_df[vol_put_col],name=name_put,orientation='h',marker_color=color_p,base=-base_vol_put,showlegend=False),1,2); base_map['vol']['put']=base_vol_put+plot_df[vol_put_col]
        y_rng = plot_df.index.max()-plot_df.index.min() if not plot_df.empty else 10; dtick = 20 if y_rng > 200 else (10 if y_rng > 100 else (5 if y_rng > 30 else (2.5 if y_rng > 10 else (1 if y_rng > 5 else max(round(y_rng/10,1),0.5)))))
        fig.update_layout(title_text=f"{ticker_symbol} 選擇權分佈 ({datetime.now().strftime('%Y-%m-%d')})",barmode='stack',height=max(600,len(all_strikes)*bar_height_multiplier*20),yaxis_title="履約價",xaxis_title="未平倉量",xaxis2_title="成交量",legend_title_text='圖例',plot_bgcolor='rgba(240,240,240,0.95)',paper_bgcolor='rgba(255,255,255,1)',font=dict(family="Arial,sans-serif",size=10))
        fig.update_yaxes(tickmode='linear',dtick=dtick); fig.add_shape(type="line",x0=-1e12,y0=current_price,x1=1e12,y1=current_price,line=dict(color="Black",width=1,dash="dash"),row=1,col=1); fig.add_shape(type="line",x0=-1e12,y0=current_price,x1=1e12,y1=current_price,line=dict(color="Black",width=1,dash="dash"),row=1,col=2)
        plotly_json_str = fig.to_json(); logger.info(f"選擇權分析：{ticker_symbol} Plotly 圖表已生成。")
    except Exception as e: logger.error(f"選擇權分析：處理 {ticker_symbol} 時發生未預期錯誤：{e}", exc_info=True); return f"處理 {ticker_symbol} 時發生未預期錯誤: {e}", ""
    return "\n".join(analysis_results), plotly_json_str

def get_alpha_vantage_data(symbols: list[str], api_key: str = None) -> dict[str, pd.DataFrame]:
    """ 模擬從 Alpha Vantage 獲取數據。如果 API 金鑰缺失，則返回帶有正確欄位結構的空 DataFrame。 """
    data_frames = {}; expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not api_key:
        logger.warning("Alpha Vantage：API 金鑰未提供。將為所有請求的 symbols 返回空的 DataFrame。")
        for symbol in symbols: data_frames[symbol] = pd.DataFrame(columns=expected_columns)
    else:
        logger.info(f"Alpha Vantage：API 金鑰已提供 (長度: {len(api_key)})。在此 MVP 中，仍返回空 DataFrame。")
        for symbol in symbols: data_frames[symbol] = pd.DataFrame(columns=expected_columns)
    return data_frames

def get_fred_data(series_ids: list[str], api_key: str = None) -> dict[str, pd.DataFrame]:
    """ 模擬從 FRED 獲取數據。如果 API 金鑰缺失，則返回帶有正確欄位結構的空 DataFrame。 """
    data_frames = {}
    if not api_key:
        logger.warning("FRED：API 金鑰未提供。將為所有請求的 series_ids 返回空的 DataFrame。")
        for series_id in series_ids: data_frames[series_id] = pd.DataFrame(columns=[series_id])
    else:
        logger.info(f"FRED：API 金鑰已提供 (長度: {len(api_key)})。在此 MVP 中，仍返回空 DataFrame。")
        for series_id in series_ids: data_frames[series_id] = pd.DataFrame(columns=[series_id])
    return data_frames

def calculate_dealer_stress_index(data_df: pd.DataFrame) -> tuple[str, str]:
    """ 計算交易商壓力指數，並根據數據完整性進行降級處理。 """
    logger.info("壓力指數：開始計算...")
    required_cols_for_full_calculation = {'vix': 'VIX_Close'}
    available_components = []; component_values = {}
    vix_col_name = required_cols_for_full_calculation['vix']
    if vix_col_name in data_df.columns and data_df[vix_col_name].notna().any():
        try:
            latest_vix = data_df[vix_col_name].dropna().iloc[-1]
            component_values['vix'] = latest_vix
            available_components.append('VIX 指數')
            logger.info(f"壓力指數：找到 VIX 數據，最新值: {latest_vix:.2f}")
        except IndexError: logger.warning(f"壓力指數：欄位 {vix_col_name} 存在但為空或全是NaN。")
        except Exception as e: logger.warning(f"壓力指數：提取 VIX 最新值時出錯: {e}")
    else: logger.warning(f"壓力指數：缺少關鍵數據欄位 {vix_col_name} 或數據為空。")
    if not available_components: logger.warning("壓力指數：數據不足，無法計算。"); return "N/A", "數據不足無法計算"
    stress_value = 0
    if 'vix' in component_values:
        vix_val = component_values['vix']
        if vix_val > 35: stress_value = 85
        elif vix_val > 25: stress_value = 65
        elif vix_val > 18: stress_value = 45
        else: stress_value = 25
    status_text = f"（基於 {', '.join(available_components)} 計算，結果僅供參考）"
    logger.info(f"壓力指數：計算完成。值: {stress_value:.0f}, 狀態: {status_text}")
    return f"{stress_value:.0f}", status_text

# --- HTML Parts Definition & Assembly ---
# --- HTML 組件定義與組裝 ---
HTML_PARTS = {
    'doctype': '<!DOCTYPE html>\n',
    'html_open': '<html lang="zh-Hant">\n',
    'head_open': '<head>\n',
    'head_content': '',
    'head_close': '</head>\n',
    'body_open': '<body class="light-mode">\n',
    # body_content will be built by Flask templates now
    # scripts will also be primarily handled by Flask templates
    'scripts': '', # Kept for potential utility scripts if needed, or for embedded data
    'body_close': '</body>\n',
    'html_close': '</html>'
}

# --- Populate head_content (Minimal: meta tags and link to external CSS) ---
# --- 填充 head_content (最小化：meta 標籤和外部 CSS 連結) ---
HTML_PARTS['head_content'] = """\
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>金融市場分析與風險評估系統 MVP</title>
<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
"""
# Plotly CDN will be in the template

# --- JavaScripts (Mainly for embedded data now, core logic moves to main.js) ---
# --- JavaScript (主要用於嵌入數據，核心邏輯移至 main.js) ---
# The 'scripts' key in HTML_PARTS will be populated in the __main__ block if needed for embedded data.

if __name__ == "__main__":
    logger.info("main_app_builder.py 作為腳本執行 (主要用於測試模組功能)...")

    # 測試 yfinance 數據獲取
    # vix_data = get_yfinance_data(['^VIX'])
    # if vix_data and '^VIX' in vix_data and not vix_data['^VIX'].empty:
    #     logger.info(f"測試獲取 VIX data (DataFrame empty: False, Shape: {vix_data['^VIX'].shape})")
    # else:
    #     logger.info(f"測試獲取 VIX data (DataFrame empty or not found)")

    # 測試選擇權分析 (AAPL)
    # analysis_text_aapl, plotly_json_aapl = analyze_stock_options("AAPL")
    # logger.info(f"AAPL 分析文字:\n{analysis_text_aapl}")
    # logger.info(f"AAPL Plotly JSON (前100字符): {plotly_json_aapl[:100]}...")

    # 測試壓力指數計算 (使用模擬數據)
    # mock_stress_data = pd.DataFrame({'VIX_Close': [20, 22, 25, 28, 30]})
    # stress_val, stress_status = calculate_dealer_stress_index(mock_stress_data)
    # logger.info(f"模擬壓力指數: {stress_val}, 狀態: {stress_status}")

    logger.info("HTML_PARTS['head_content'] 預覽 (應包含 CSS 連結):")
    print(HTML_PARTS.get('head_content'))

    logger.info("main_app_builder.py 測試執行完畢。")

[end of main_app_builder.py]
