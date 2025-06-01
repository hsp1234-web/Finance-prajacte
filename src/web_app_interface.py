# src/web_app_interface.py
import dash
import dash_bootstrap_components as dbc
from dash import html
# from dash import dcc # 目前的靜態頁面尚未使用 dcc.Graph 等元件

from src import config_manager
from src import logger_setup
# from src.data_fetchers import yfinance_fetcher # 暫時註解，目前為靜態UI
# from src.stock_screener import screen_stocks # 暫時註解，目前為靜態UI

# 初始化 logger
logger = logger_setup.setup_logger()

# 從設定檔讀取應用程式標題
app_title_config = config_manager.get_setting('dash_app_settings', 'app_title', "金融分析戰情室")

# 初始化 Dash 應用
# Dash 會自動從 assets/ 目錄加載 CSS 和 JS 檔案
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], title=app_title_config)
server = app.server # Gunicorn 等 WSGI 伺服器會尋找這個 server 物件

# --- 組件定義函數 ---

def create_navbar() -> dbc.NavbarSimple:
    """創建頂部導航欄。"""
    navbar = dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("戰情室", href="/", active="exact")),
            dbc.NavItem(dbc.NavLink("詳細分析", href="/detailed-analysis", disabled=True)),
            dbc.NavItem(dbc.NavLink("AI 交易建議", href="/ai-suggestions", disabled=True)),
            dbc.DropdownMenu(
                children=[
                    dbc.DropdownMenuItem("更多連結", header=True),
                    dbc.DropdownMenuItem("設定", href="#", disabled=True),
                    dbc.DropdownMenuItem("登出", href="#", disabled=True),
                ],
                nav=True,
                in_navbar=True,
                label="選項",
                align_end=True, # 下拉選單靠右對齊
            ),
        ],
        brand="金融分析系統", # 系統名稱
        brand_href="/",
        color="primary", # 導航欄顏色主題
        dark=True, # 深色主題文字
        fluid=True, # 導航欄內容寬度自動填滿
        className="mb-4" # 底部增加一些間距
    )
    return navbar

def create_risk_dashboard_card() -> dbc.Card:
    """創建核心風險儀表卡片。"""
    # 模擬的風險狀態和描述
    risk_level = "中度風險"
    risk_color_class = "text-warning" # Bootstrap 顏色 class (黃色)
    risk_icon = "🟡" # Unicode icon
    risk_summary = "市場波動加劇，部分指標顯示潛在下行壓力。建議審慎操作，關注關鍵支撐位。"

    card_content = [
        dbc.CardHeader("核心風險儀表 (總體市場)", className="text-white bg-secondary"),
        dbc.CardBody(
            [
                html.H3(f"{risk_level} {risk_icon}", className=f"card-title {risk_color_class} text-center mb-3"),
                html.P(risk_summary, className="card-text text-center"),
                # 可以加入更多細節或圖表佔位符
                # dcc.Graph(figure=...) # 例如一個簡單的風險等級圖
            ]
        ),
        dbc.CardFooter("更新時間: 2024-05-30 10:00 AM", className="text-muted small")
    ]
    return dbc.Card(card_content, color="light", outline=False, className="h-100") # h-100 使卡片填滿列高度

def create_kpi_card() -> dbc.Card:
    """創建關鍵市場指標 KPI 卡片。"""
    # 模擬的 KPI 數據
    kpis = [
        {"label": "S&P 500 指數", "value": "5,280.50", "change": "+0.25%", "change_color": "success", "icon": "▲"},
        {"label": "台灣加權指數 (TSE)", "value": "21,550.75", "change": "-0.10%", "change_color": "danger", "icon": "▼"},
        {"label": "VIX 波動率指數", "value": "14.80", "change": "+1.50%", "change_color": "danger", "icon": "▲"}, # VIX 上升通常視為風險增加
        {"label": "美元指數 (DXY)", "value": "104.50", "change": "-0.05%", "change_color": "success", "icon": "▼"},
    ]

    list_group_items = []
    for kpi in kpis:
        list_group_items.append(
            dbc.ListGroupItem(
                [
                    html.Div(kpi["label"], className="fw-bold"), # fw-bold 加粗標籤
                    html.Div(
                        [
                            html.Span(kpi["value"], className="fs-5 me-2"), # fs-5 放大數值, me-2 右邊距
                            html.Span(f"{kpi['change']} {kpi['icon']}", className=f"text-{kpi['change_color']}")
                        ]
                    )
                ],
                className="d-flex justify-content-between align-items-center" # 左右對齊
            )
        )

    card_content = [
        dbc.CardHeader("關鍵市場指標", className="text-white bg-secondary"),
        dbc.CardBody(
            dbc.ListGroup(list_group_items, flush=True) # flush 移除邊框和圓角
        ),
        dbc.CardFooter("即時數據 (模擬)", className="text-muted small")
    ]
    return dbc.Card(card_content, color="light", outline=False, className="h-100")

def create_market_sentiment_card() -> dbc.Card:
    """創建市場情緒/寬度簡報卡片。"""
    # 模擬的市場情緒數據
    sentiment_summary = "目前市場情緒偏向謹慎，上漲股票家數略少於下跌家數。短期技術指標顯示多空分歧，需密切關注後續量能變化以判斷趨勢。"
    put_call_ratio = "0.85 (看跌/看漲期權比例)"
    fear_greed_index = "45 (恐懼)"

    card_content = [
        dbc.CardHeader("市場情緒與寬度指標", className="text-white bg-secondary"),
        dbc.CardBody(
            [
                html.H5("整體情緒摘要", className="card-title"),
                html.P(sentiment_summary, className="card-text mb-3"),
                html.Hr(),
                html.H6("關鍵情緒指標:", className="card-subtitle mb-2 text-muted"),
                html.Ul(
                    [
                        html.Li(f"Put/Call Ratio: {put_call_ratio}"),
                        html.Li(f"恐懼與貪婪指數: {fear_greed_index} (CNN Money)"),
                        html.Li("上漲/下跌家數比 (ADL): 45% (模擬)"),
                    ], className="list-unstyled" # list-unstyled 移除列表樣式
                )
            ]
        ),
         dbc.CardFooter("數據來源: 各大交易所, CNN (模擬)", className="text-muted small")
    ]
    return dbc.Card(card_content, color="light", outline=False)


# --- 設定應用程式佈局 ---
app.layout = dbc.Container(
    [
        create_navbar(),
        dbc.Row(
            [
                dbc.Col(create_risk_dashboard_card(), md=12, lg=5, className="mb-4"), # 中螢幕佔12欄，大螢幕佔5欄
                dbc.Col(create_kpi_card(), md=12, lg=7, className="mb-4"),
            ],
            # align="stretch" # 可選：讓同行的卡片等高
        ),
        dbc.Row(
            [
                dbc.Col(create_market_sentiment_card(), width=12, className="mb-4"),
            ]
        ),
        # 頁腳 (可選)
        html.Footer(
            dbc.Container(
                html.P(f"© 2024 {app_title_config}. All rights reserved.", className="text-center text-muted small py-3"),
                fluid=True
            ),
            className="mt-auto" # 將頁腳推到底部
        )
    ],
    fluid=True, # 主容器寬度自動填滿
    className="bg-light min-vh-100 d-flex flex-column" # 淺色背景，最小視窗高度，彈性列佈局
)

# --- 主執行區塊 (用於直接運行此檔案進行測試) ---
if __name__ == '__main__':
    logger.info("開始直接運行 src/web_app_interface.py 以測試 Dash 應用...")
    # 從 config_manager 獲取 Dash App 設定
    app_host = config_manager.get_setting('dash_app_settings', 'host', '0.0.0.0')
    app_port = config_manager.get_setting('dash_app_settings', 'port', 8050)
    debug_mode = config_manager.get_setting('dash_app_settings', 'debug_mode', True)

    logger.info(f"Dash 應用將在 http://{app_host}:{app_port}/ 上啟動 (除錯模式: {debug_mode})")
    app.run(debug=debug_mode, host=app_host, port=app_port) # Dash 2.x+ 使用 app.run()
