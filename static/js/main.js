document.addEventListener('DOMContentLoaded', function () {
    // Theme Toggle Logic
    const themeToggleButton = document.getElementById('main-theme-toggle');
    const body = document.body;
    const themeToggleText = document.getElementById('main-theme-toggle-text');
    // Optional: Add icon elements if you have them in HTML
    // const moonIcon = document.getElementById('main-moon-icon');
    // const sunIcon = document.getElementById('main-sun-icon');

    const applyTheme = (theme) => {
        if (theme === 'dark-mode') {
            body.classList.add('dark-mode');
            body.classList.remove('light-mode');
            if (themeToggleText) themeToggleText.textContent = '亮色模式';
            // if (moonIcon) moonIcon.style.display = 'inline'; // Or use a class like 'hidden-icon'
            // if (sunIcon) sunIcon.style.display = 'none';
        } else {
            body.classList.add('light-mode');
            body.classList.remove('dark-mode');
            if (themeToggleText) themeToggleText.textContent = '暗色模式';
            // if (moonIcon) moonIcon.style.display = 'none';
            // if (sunIcon) sunIcon.style.display = 'inline';
        }
    };

    const currentTheme = localStorage.getItem('theme');
    if (currentTheme) {
        applyTheme(currentTheme);
    } else {
        // Default to light mode if body doesn't already have dark-mode (e.g. from OS preference via CSS)
        if (body.classList.contains('dark-mode')) {
             applyTheme('dark-mode');
        } else {
             applyTheme('light-mode');
        }
    }

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            let newTheme = 'light-mode';
            if (body.classList.contains('light-mode')) {
                newTheme = 'dark-mode';
            }
            applyTheme(newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    // Data Freshness Timestamp
    const dataFreshnessContainer = document.getElementById('data-freshness-container');
    if (dataFreshnessContainer) {
        const now = new Date();
        const year = now.getFullYear();
        const month = (now.getMonth() + 1).toString().padStart(2, '0');
        const day = now.getDate().toString().padStart(2, '0');
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        dataFreshnessContainer.textContent = `數據更新於：${year}-${month}-${day} ${hours}:${minutes} CST`;
    }

    // Smooth Scroll for Navigation Links
    document.querySelectorAll('nav#main-navigation a.nav-link').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const sectionId = this.getAttribute('href');
            if (sectionId && sectionId.startsWith('#')) {
                const section = document.querySelector(sectionId);
                if (section) {
                    e.preventDefault();
                    section.scrollIntoView({ behavior: 'smooth', block: 'start' });

                    // Update active class on nav links
                    document.querySelectorAll('nav#main-navigation a.nav-link').forEach(link => {
                        link.classList.remove('active');
                    });
                    this.classList.add('active');
                }
            }
        });
    });

    // Stock Options Analysis Logic
    const stockTickerInput = document.getElementById('stock-ticker-input');
    const analyzeStockBtn = document.getElementById('analyze-stock-btn');
    const optionsAnalysisTextDiv = document.getElementById('options-analysis-text');
    const optionsPlotlyChartDiv = document.getElementById('options-plotly-chart');

    const displayOptionsAnalysis = (analysisText, plotlyJsonStr) => {
        optionsAnalysisTextDiv.textContent = analysisText;
        Plotly.purge(optionsPlotlyChartDiv); // Clear previous chart

        if (plotlyJsonStr && plotlyJsonStr.trim() !== "") {
            try {
                const chartData = JSON.parse(plotlyJsonStr);
                Plotly.newPlot(optionsPlotlyChartDiv, chartData.data, chartData.layout);
            } catch (e) {
                console.error("Error parsing/plotting Plotly JSON:", e);
                optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder" style="padding:20px; text-align:center;">渲染圖表時發生錯誤。</div>';
            }
        } else if (analysisText && (analysisText.includes("錯誤：") || analysisText.includes("無法"))) {
             optionsPlotlyChartDiv.innerHTML = `<div class="chart-placeholder" style="padding:20px; text-align:center;">${analysisText}</div>`;
        } else if (!plotlyJsonStr && analysisText) {
             optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder" style="padding:20px; text-align:center;">無圖表數據可顯示。</div>';
        }
    };

    // On page load, if AAPL data is embedded and input is AAPL (or empty), display it.
    if (window.embeddedAAPLData && stockTickerInput) {
        if (stockTickerInput.value.trim().toUpperCase() === 'AAPL' || !stockTickerInput.value.trim()) {
            stockTickerInput.value = 'AAPL'; // Ensure AAPL is in the input box
            displayOptionsAnalysis(window.embeddedAAPLData.analysisText, window.embeddedAAPLData.plotlyJson);
        }
    } else if (stockTickerInput && stockTickerInput.value.trim().toUpperCase() === 'AAPL') {
        // If input is AAPL but no embedded data, prompt to click analyze
        optionsAnalysisTextDiv.textContent = '請點擊「分析」按鈕以載入 AAPL 的選擇權數據。';
        Plotly.purge(optionsPlotlyChartDiv);
        optionsPlotlyChartDiv.innerHTML = '';
    }


    if (analyzeStockBtn) {
        analyzeStockBtn.addEventListener('click', () => {
            const ticker = stockTickerInput.value.trim().toUpperCase();
            if (!ticker) {
                optionsAnalysisTextDiv.textContent = '請輸入有效的股票代號。';
                Plotly.purge(optionsPlotlyChartDiv);
                optionsPlotlyChartDiv.innerHTML = '';
                return;
            }

            optionsAnalysisTextDiv.textContent = `正在分析 ${ticker}，請稍候...`;
            Plotly.purge(optionsPlotlyChartDiv);
            optionsPlotlyChartDiv.innerHTML = '<div class="chart-placeholder" style="padding:20px; text-align:center;">圖表數據加載中...</div>';

            // If it's AAPL and we have embedded data, use it (avoids API call for default)
            if (ticker === 'AAPL' && window.embeddedAAPLData) {
                displayOptionsAnalysis(window.embeddedAAPLData.analysisText, window.embeddedAAPLData.plotlyJson);
                return;
            }

            // For other tickers, or if AAPL embedded data is missing, fetch from API
            fetch(`/api/stock_options/${ticker}`)
                .then(response => {
                    if (!response.ok) { // Check for HTTP errors like 404, 500
                        return response.json().then(errData => { // Try to parse error json from server
                            throw new Error(`網路回應錯誤: ${response.status} ${response.statusText}. ${errData.error || ''}`);
                        }).catch(() => { // If no json error body
                            throw new Error(`網路回應錯誤: ${response.status} ${response.statusText}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) { // Error from our API logic (e.g., yfinance problem)
                        displayOptionsAnalysis(data.analysis_text || `分析 ${ticker} 時發生錯誤：${data.error}`, data.plotly_json || "");
                    } else {
                        displayOptionsAnalysis(data.analysis_text, data.plotly_json);
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    let errorMsg = `請求分析 ${ticker} 時發生錯誤：${error.message}。請檢查網路連線或稍後再試。`;
                    displayOptionsAnalysis(errorMsg, "");
                });
        });
    }
});
