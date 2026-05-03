import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# 页面配置
st.set_page_config(page_title="2x2 多维期限结构监控", layout="wide")


@st.cache_data
def load_data():
    # 读取数据并转换日期
    df = pd.read_csv('data.csv')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp')
    return df


def calculate_derivatives(data_row, cols):
    """
    根据用户需求计算衍生指标：
    1. Outright: 原始价格
    2. Spread: P1 - P2
    3. Fly: P1 - 2*P2 + P3
    4. Combo: P1 - 3*P2 + 3*P3 - P4
    """
    prices = data_row[cols].values
    spreads = prices[:-1] - prices[1:]
    flies = prices[:-2] - 2*prices[1:-1] + prices[2:]
    combos = prices[:-3] - 3*prices[1:-2] + 3*prices[2:-1] - prices[3:]
    return spreads, flies, combos


try:
    df = load_data()
    # 自动识别以 CO 开头的合约列
    contract_cols = [col for col in df.columns if col.startswith('CO')]

    # 定义 4 个维度的 X 轴标签
    labels_map = {
        "Outright": contract_cols,
        "Spread": [f"S{i+1}" for i in range(len(contract_cols)-1)],
        "Fly": [f"F{i+1}" for i in range(len(contract_cols)-2)],
        "Combo": [f"C{i+1}" for i in range(len(contract_cols)-3)]
    }

    # 侧边栏控制
    st.sidebar.header("控制台")
    date_range = st.sidebar.slider("日期选择", df['Timestamp'].min().date(), df['Timestamp'].max().date(),
                                   (df['Timestamp'].min().date(), df['Timestamp'].max().date()))
    speed = st.sidebar.slider("播放速度", 0.01, 0.5, 0.1)
    start_btn = st.sidebar.button("开始实时演化 🚀")

    # 数据过滤
    start_dt, end_dt = pd.to_datetime(
        date_range[0]), pd.to_datetime(date_range[1])
    f_df = df.loc[(df['Timestamp'] >= start_dt) & (
        df['Timestamp'] <= end_dt)].reset_index(drop=True)

    if f_df.empty:
        st.warning("所选日期范围内没有数据。")
    else:
        base_row = f_df.iloc[0]
        plot_spot = st.empty()

        def create_2x2_plot(idx):
            curr_row = f_df.iloc[idx]
            # 获取前一日数据用于计算“当日变动”
            prev_row = f_df.iloc[max(0, idx-1)]

            # 计算衍生值
            curr_s, curr_fl, curr_cb = calculate_derivatives(
                curr_row, contract_cols)
            base_s, base_fl, base_cb = calculate_derivatives(
                base_row, contract_cols)
            prev_s, prev_fl, prev_cb = calculate_derivatives(
                prev_row, contract_cols)

            # 修正后的 4 组数据结构 [格式: 当前, 基准, 前日, 标签, 标题]
            groups = [
                (curr_row[contract_cols].values, base_row[contract_cols].values,
                 prev_row[contract_cols].values, labels_map["Outright"], "1. Outright"),
                (curr_s, base_s, prev_s,
                 labels_map["Spread"], "2. Spread (P1-P2)"),
                (curr_fl, base_fl, prev_fl,
                 labels_map["Fly"], "3. Fly (P1-2P2+P3)"),
                (curr_cb, base_cb, prev_cb,
                 labels_map["Combo"], "4. Combo (P1-3P2+3P3-P4)")
            ]

            # 创建 4行2列 的网格，用于实现 2x2 的“上下堆叠”组
            fig = make_subplots(
                rows=4, cols=2,
                row_heights=[0.35, 0.15, 0.35, 0.15],
                vertical_spacing=0.08,
                horizontal_spacing=0.06,
                subplot_titles=[
                    "Outright 结构与累积变化", "Spread 结构与累积变化",
                    "Outright 当日变动", "Spread 当日变动",
                    "Fly 结构与累积变化", "Combo 结构与累积变化",
                    "Fly 当日变动", "Combo 当日变动"
                ]
            )

            # 对应 4 个功能块的起始位置
            positions = [(1, 1), (1, 2), (3, 1), (3, 2)]

            for i, (curr, base, prev, labels, title) in enumerate(groups):
                r_start, col = positions[i]

                # --- A. 曲线主图 (当前实线 vs 基准虚线 + 累积变动柱) ---
                cum_diff = curr - base
                cum_colors = ['rgba(38, 166, 154, 0.3)' if x >=
                              0 else 'rgba(239, 83, 80, 0.3)' for x in cum_diff]

                # 累积柱 (从基准价格延伸到当前价格)
                fig.add_trace(go.Bar(x=labels, y=cum_diff, base=base,
                              marker_color=cum_colors, showlegend=False), row=r_start, col=col)
                # 基准虚线
                fig.add_trace(go.Scatter(x=labels, y=base, mode='lines', line=dict(
                    color='gray', dash='dash', width=1), showlegend=False), row=r_start, col=col)
                # 当前实线
                fig.add_trace(go.Scatter(x=labels, y=curr, mode='lines+markers', line=dict(
                    color='#1f77b4', width=2), marker=dict(size=4), showlegend=False), row=r_start, col=col)

                # --- B. 当日变动图 (紧贴在主图下方) ---
                day_chg = curr - prev
                day_colors = ['#26a69a' if x >=
                              0 else '#ef5350' for x in day_chg]
                fig.add_trace(go.Bar(x=labels, y=day_chg, marker_color=day_colors,
                              showlegend=False), row=r_start+1, col=col)

            fig.update_layout(
                height=950,
                template="plotly_white",
                title_text=f"多维期限结构全景监控 | 日期: {curr_row['Timestamp'].strftime('%Y-%m-%d')}",
                title_x=0.5
            )
            return fig

        # 初始显示
        if not start_btn:
            plot_spot.plotly_chart(
                create_2x2_plot(0), use_container_width=True)

        # 播放动画
        if start_btn:
            for i in range(len(f_df)):
                plot_spot.plotly_chart(
                    create_2x2_plot(i), use_container_width=True)
                time.sleep(speed)

except Exception as e:
    st.error(f"分析运行出错: {e}")
