import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go

st.set_page_config(page_title="黄金资产实时监控", layout="wide", page_icon="🪙")

# Defense Lines (International Gold Price)
L1 = 4600
L2 = 4560
L3 = 4450

@st.cache_data(ttl=60)
def get_current_price(ticker_symbol):
    """Fetch the latest available close price for a ticker."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        # First, try to get from fast_info (more robust for real-time prices)
        try:
            price = ticker.fast_info.last_price
            if price is not None and not pd.isna(price):
                return price
        except:
            pass
            
        # Fallback to history
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            # Fallback to daily
            data = ticker.history(period="5d")
        if not data.empty:
            return data['Close'].iloc[-1]
        return None
    except Exception as e:
        st.sidebar.error(f"Error fetching {ticker_symbol}: {e}")
        return None

@st.cache_data(ttl=60)
def get_history_data(ticker_symbol, period="1mo", interval="1d"):
    """Fetch historical data for plotting."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period=period, interval=interval)
        return data
    except Exception as e:
        return pd.DataFrame()

# Main Header
st.title("GOLD板板")
st.markdown("实时对比**市场实际股价**与**基于国际金价换算的理论价**，并监控三大防御线。")

# Fetch data
with st.spinner("获取实时数据中... (yfinance API)"):
    # Using GC=F (Gold Futures) as primary, fallback to XAUUSD=X
    gold_price = get_current_price("GC=F")
    if gold_price is None:
        gold_price = get_current_price("XAUUSD=X")
    
    # Using USDCNY=X for exchange rate
    usdcny = get_current_price("USDCNY=X")
    if usdcny is None:
         usdcny = get_current_price("CNY=X")
         
    iaum_price = get_current_price("IAUM")
    a518850_price = get_current_price("518850.SS")

if gold_price and usdcny and iaum_price and a518850_price:
    # ---------------------------------------------------------
    # Logic Calculations
    # ---------------------------------------------------------
    # IAUM Theoretical = Gold * 0.01 (1/100 ounce)
    iaum_theo = gold_price * 0.01
    # 518850 Theoretical = (Gold / 31.1035) * USDCNY * 0.01 (1 share = 0.01 gram)
    a518850_theo = (gold_price / 31.1035) * usdcny * 0.01
    
    # Premium = (Market / Theoretical) - 1
    iaum_premium = (iaum_price / iaum_theo) - 1
    a518850_premium = (a518850_price / a518850_theo) - 1

    # ---------------------------------------------------------
    # UI/UX Module 1: Metric Cards
    # ---------------------------------------------------------
    st.header("📊 实时看板")
    
    st.markdown(f"**当前国际金价**: `${gold_price:.2f}` &nbsp;&nbsp;|&nbsp;&nbsp; **美元兑人民币汇率**: `¥{usdcny:.4f}`")
    
    col1, col2 = st.columns(2)
    
    def format_premium(val):
        return f"{val * 100:.2f}%"
    
    with col1:
        st.subheader("IAUM")
        metric_cols = st.columns(3)
        metric_cols[0].metric("当前市场价", f"${iaum_price:.4f}")
        metric_cols[1].metric("理论公平价", f"${iaum_theo:.4f}")
        # Inverse color: higher premium is bad (red)
        metric_cols[2].metric("折溢价率", format_premium(iaum_premium), 
                              delta=format_premium(iaum_premium),
                              delta_color="inverse")
                              
    with col2:
        st.subheader("518850.SS")
        metric_cols = st.columns(3)
        metric_cols[0].metric("当前市场价", f"¥{a518850_price:.3f}")
        metric_cols[1].metric("理论公平价", f"¥{a518850_theo:.3f}")
        # Inverse color: higher premium is bad (red)
        metric_cols[2].metric("折溢价率", format_premium(a518850_premium), 
                              delta=format_premium(a518850_premium),
                              delta_color="inverse")

    st.divider()

    # ---------------------------------------------------------
    # UI/UX Module 2 & 3: Defense Lines & Distance Analysis
    # ---------------------------------------------------------
    st.header("🛡️ 三大防线计算器与距离分析")
    
    defense_lines = {
        "L1 (第一防线)": L1,
        "L2 (第二防线)": L2,
        "L3 (第三防线)": L3
    }
    
    # Calculate mapping and distance
    defense_data = []
    for name, level in defense_lines.items():
        # Target buy price should account for current premium/discount
        # This ensures the limit order is placed at the expected market price when gold hits the defense line
        iaum_target = iaum_price * (level / gold_price)
        a518850_target = a518850_price * (level / gold_price)
        
        # Calculate how much it needs to drop (percentage)
        # Drop % = (Current - Target) / Current
        gold_drop = (gold_price - level) / gold_price if gold_price > level else 0
        iaum_drop = (iaum_price - iaum_target) / iaum_price if iaum_price > iaum_target else 0
        a518850_drop = (a518850_price - a518850_target) / a518850_price if a518850_price > a518850_target else 0
        
        def format_drop(drop_val):
            if drop_val <= 0:
                return "🚨 已到价！"
            return f"需跌 {drop_val * 100:.2f}%"

        defense_data.append({
            "防线": name,
            "国际金价目标 ($)": f"{level:.2f}",
            "金价距离防线": format_drop(gold_drop),
            "IAUM 目标买入 ($)": f"{iaum_target:.4f}",
            "IAUM 距离防线": format_drop(iaum_drop),
            "518850 目标买入 (¥)": f"{a518850_target:.3f}",
            "518850 距离防线": format_drop(a518850_drop),
        })
        
    df_defense = pd.DataFrame(defense_data)
    
    def highlight_reached(val):
        if val == "🚨 已到价！":
            return 'color: #ff4b4b; font-weight: bold; background-color: rgba(255, 75, 75, 0.1);'
        return ''
        
    # Pandas >= 2.1.0 uses map, older versions use applymap
    try:
        styled_df = df_defense.style.map(highlight_reached)
    except AttributeError:
        styled_df = df_defense.style.applymap(highlight_reached)
        
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Trigger popups for reached lines
    for name, level in defense_lines.items():
        if gold_price <= level:
            st.toast(f"**警报**：国际金价已跌至或跌破 {name} (${level})！", icon="🚨")
    
    st.divider()

    # ---------------------------------------------------------
    # UI/UX Module 4: Interactive Charts
    # ---------------------------------------------------------
    st.header("📈 交互图表")
    tab1, tab2 = st.tabs(["国际金价走势 (含防线)", "标的实时分时图"])
    
    with tab1:
        gold_hist = get_history_data("GC=F", period="2y", interval="1d")
        if gold_hist.empty:
            gold_hist = get_history_data("XAUUSD=X", period="2y", interval="1d")
            
        if not gold_hist.empty:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=gold_hist.index, 
                open=gold_hist['Open'], 
                high=gold_hist['High'], 
                low=gold_hist['Low'], 
                close=gold_hist['Close'], 
                name='国际金价'
            ))
            
            # Add defense lines
            colors = ['#FF9900', '#FF6600', '#FF0000']
            for (name, level), color in zip(defense_lines.items(), colors):
                fig.add_hline(y=level, line_dash="dash", line_color=color, 
                              annotation_text=f"{name}: ${level}", 
                              annotation_position="bottom right")
                              
            fig.update_layout(
                title="国际金价最近2年走势与防线对比", 
                xaxis_title="日期", 
                yaxis_title="价格 ($)",
                height=500,
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                dragmode='pan',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
        else:
            st.warning("无法获取国际金价历史数据，图表暂不显示。")
            
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            iaum_hist = get_history_data("IAUM", period="1d", interval="5m")
            if not iaum_hist.empty:
                fig_iaum = go.Figure()
                fig_iaum.add_trace(go.Scatter(x=iaum_hist.index, y=iaum_hist['Close'], mode='lines', name='IAUM', line_color='#00BFFF', fill='tozeroy'))
                fig_iaum.update_layout(title="IAUM 今日分时图", xaxis_title="时间", yaxis_title="价格 ($)", template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), dragmode='pan', hovermode='x unified')
                st.plotly_chart(fig_iaum, use_container_width=True, config={'scrollZoom': True})
            else:
                 st.info("当前时间可能非交易时段，或无法获取 IAUM 分时数据。")
                 
        with col2:
            a518850_hist = get_history_data("518850.SS", period="1d", interval="5m")
            if not a518850_hist.empty:
                fig_a518850 = go.Figure()
                fig_a518850.add_trace(go.Scatter(x=a518850_hist.index, y=a518850_hist['Close'], mode='lines', name='518850.SS', line_color='#FF4500', fill='tozeroy'))
                fig_a518850.update_layout(title="518850.SS 今日分时图", xaxis_title="时间", yaxis_title="价格 (¥)", template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), dragmode='pan', hovermode='x unified')
                st.plotly_chart(fig_a518850, use_container_width=True, config={'scrollZoom': True})
            else:
                st.info("当前时间可能非交易时段，或无法获取 518850.SS 分时数据。")

else:
    st.error("获取基础数据失败，请检查网络（或代理设置）后刷新重试。")
    st.write("未能获取到的数据项:")
    if not gold_price: st.write("- 国际金价 (GC=F / XAUUSD=X)")
    if not usdcny: st.write("- 美元兑人民币汇率 (USDCNY=X)")
    if not iaum_price: st.write("- IAUM 实际价格")
    if not a518850_price: st.write("- 518850.SS 实际价格")
