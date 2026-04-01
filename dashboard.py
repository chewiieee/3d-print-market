import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, ".")

# ───────────────────────────────────────────────
# 页面配置
# ───────────────────────────────────────────────
st.set_page_config(
    page_title="3D打印选品分析",
    page_icon="🖨️",
    layout="wide",
)

# ───────────────────────────────────────────────
# 初始化数据库（首次打开时建表）
# ───────────────────────────────────────────────
try:
    from db import init_db
    init_db()
except Exception:
    # 云端可能是只读文件系统，初始化失败时直接走 CSV 回退
    pass

# ───────────────────────────────────────────────
# 数据加载（带缓存，60秒内不重复查询）
# ───────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    # 优先读 SQLite；云端部署没有 db 文件时回退到 CSV
    try:
        from db import get_taobao_products, get_xhs_notes, get_stats
        tb = get_taobao_products()
        xhs = get_xhs_notes()
        stats = get_stats()
        if tb.empty and xhs.empty:
            raise FileNotFoundError("db empty")
    except Exception:
        import pandas as pd, os
        tb_path = os.path.join(os.path.dirname(__file__), "data", "taobao_export.csv")
        xhs_path = os.path.join(os.path.dirname(__file__), "data", "xhs_export.csv")
        tb = pd.read_csv(tb_path, encoding="utf-8-sig") if os.path.exists(tb_path) else pd.DataFrame()
        xhs = pd.read_csv(xhs_path, encoding="utf-8-sig") if os.path.exists(xhs_path) else pd.DataFrame()
        last = tb["crawled_at"].max() if not tb.empty and "crawled_at" in tb.columns else "从未爬取"
        stats = {
            "taobao_total": len(tb),
            "xhs_total": len(xhs),
            "last_crawled": last,
        }
    return tb, xhs, stats

tb_df, xhs_df, stats = load_data()

no_taobao = tb_df.empty
no_xhs = xhs_df.empty

# ───────────────────────────────────────────────
# 侧栏：过滤器 + 导出
# ───────────────────────────────────────────────
with st.sidebar:
    st.title("🖨️ 3D打印选品分析")
    st.caption("数据来源：淘宝 · 小红书")
    st.divider()

    st.subheader("📊 数据统计")
    st.metric("淘宝商品", f"{stats['taobao_total']} 条")
    st.metric("小红书笔记", f"{stats['xhs_total']} 条")
    if stats["last_crawled"] != "从未爬取":
        st.caption(f"最近更新：{stats['last_crawled'][:19]}")
    else:
        st.caption("尚未爬取数据，请先运行 `bash run.sh`")

    st.divider()
    st.subheader("🔍 过滤器")

    # 关键词过滤
    all_keywords_tb = sorted(tb_df["keyword"].unique().tolist()) if not no_taobao else []
    all_keywords_xhs = sorted(xhs_df["keyword"].unique().tolist()) if not no_xhs else []

    selected_keywords_tb = st.multiselect(
        "淘宝关键词",
        options=all_keywords_tb,
        default=all_keywords_tb,
    )
    selected_keywords_xhs = st.multiselect(
        "小红书关键词",
        options=all_keywords_xhs,
        default=all_keywords_xhs,
    )

    # 价格范围
    if not no_taobao and tb_df["price"].notna().any():
        price_min = float(tb_df["price"].min())
        price_max = float(tb_df["price"].max())
        if price_max > price_min:
            price_range = st.slider(
                "价格区间（元）",
                min_value=price_min,
                max_value=price_max,
                value=(price_min, price_max),
            )
        else:
            price_range = (price_min, price_max)
    else:
        price_range = (0.0, 99999.0)

    st.divider()
    st.subheader("💾 导出数据")
    if not no_taobao:
        csv_tb = tb_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ 导出淘宝数据 CSV", csv_tb, "淘宝3D打印.csv", "text/csv")
    if not no_xhs:
        csv_xhs = xhs_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ 导出小红书数据 CSV", csv_xhs, "小红书3D打印.csv", "text/csv")

# ───────────────────────────────────────────────
# 数据过滤
# ───────────────────────────────────────────────
if not no_taobao:
    tb_filtered = tb_df[
        tb_df["keyword"].isin(selected_keywords_tb) &
        tb_df["price"].between(price_range[0], price_range[1])
    ].copy()
else:
    tb_filtered = pd.DataFrame()

if not no_xhs:
    xhs_filtered = xhs_df[xhs_df["keyword"].isin(selected_keywords_xhs)].copy()
else:
    xhs_filtered = pd.DataFrame()

# ───────────────────────────────────────────────
# 空数据提示
# ───────────────────────────────────────────────
if no_taobao and no_xhs:
    st.title("📭 暂无数据")
    st.info(
        "数据库还是空的。请打开终端，进入项目文件夹，运行：\n\n"
        "```bash\nbash run.sh\n```\n\n"
        "爬取完成后刷新此页面即可看到图表。"
    )
    st.stop()

# ───────────────────────────────────────────────
# Tab 布局
# ───────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 市场概览", "🛒 淘宝分析", "📕 小红书趋势", "📋 数据明细", "🧠 选品总结"])

# ══════════════════════════════════════════════
# Tab 1：市场概览
# ══════════════════════════════════════════════
with tab1:
    st.header("📈 市场概览")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("淘宝商品总数", len(tb_filtered) if not tb_filtered.empty else 0)
    with col2:
        if not tb_filtered.empty and tb_filtered["price"].notna().any():
            avg_price = tb_filtered["price"][tb_filtered["price"] > 0].mean()
            st.metric("淘宝均价", f"¥{avg_price:.1f}")
        else:
            st.metric("淘宝均价", "—")
    with col3:
        if not tb_filtered.empty and tb_filtered["monthly_sales"].notna().any():
            total_sales = tb_filtered["monthly_sales"].sum()
            st.metric("淘宝月销量合计", f"{int(total_sales):,} 件")
        else:
            st.metric("淘宝月销量合计", "—")
    with col4:
        st.metric("小红书笔记数", len(xhs_filtered) if not xhs_filtered.empty else 0)

    st.divider()
    col_left, col_right = st.columns(2)

    # 各关键词商品数量对比
    with col_left:
        if not tb_filtered.empty:
            kw_count = tb_filtered.groupby("keyword").size().reset_index(name="商品数")
            fig = px.bar(
                kw_count, x="keyword", y="商品数",
                title="各品类搜索词商品数量",
                color="keyword",
                labels={"keyword": "搜索词"},
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("淘宝数据尚未爬取")

    # 各关键词小红书笔记热度（均点赞数）
    with col_right:
        if not xhs_filtered.empty:
            kw_likes = xhs_filtered.groupby("keyword")["likes"].mean().reset_index()
            kw_likes.columns = ["keyword", "平均点赞"]
            fig2 = px.bar(
                kw_likes, x="keyword", y="平均点赞",
                title="各品类小红书平均点赞数",
                color="keyword",
                labels={"keyword": "搜索词"},
            )
            fig2.update_layout(showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("小红书数据尚未爬取")

# ══════════════════════════════════════════════
# Tab 2：淘宝分析
# ══════════════════════════════════════════════
with tab2:
    st.header("🛒 淘宝商品分析")

    if tb_filtered.empty:
        st.info("淘宝数据尚未爬取，请先运行 `bash run.sh`")
    else:
        # 去掉价格为 0 的数据（未解析到的）
        tb_valid = tb_filtered[tb_filtered["price"] > 0].copy()

        row1_left, row1_right = st.columns(2)

        # 价格分布直方图
        with row1_left:
            fig = px.histogram(
                tb_valid, x="price", nbins=30,
                title="商品价格分布",
                color_discrete_sequence=["#FF6B6B"],
                labels={"price": "价格（元）", "count": "商品数量"},
            )
            fig.update_layout(bargap=0.1)
            st.plotly_chart(fig, use_container_width=True)

        # 各品类月销量箱线图
        with row1_right:
            tb_sales = tb_valid[tb_valid["monthly_sales"].notna()].copy()
            if not tb_sales.empty:
                fig2 = px.box(
                    tb_sales, x="keyword", y="monthly_sales",
                    title="各品类月销量分布（箱线图）",
                    color="keyword",
                    labels={"keyword": "搜索词", "monthly_sales": "月销量（件）"},
                )
                fig2.update_layout(showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("暂无月销量数据")

        st.divider()

        # 价格 × 月销量散点图（找爆款甜蜜区间）
        st.subheader("🎯 价格 × 月销量甜蜜区间")
        st.caption("气泡越大代表评价数越多，找右上方的密集区就是值得切入的价格带")
        tb_scatter = tb_valid[tb_valid["monthly_sales"].notna()].copy()
        if not tb_scatter.empty:
            # review_count 用于气泡大小，空值填 5
            tb_scatter["bubble_size"] = tb_scatter["review_count"].fillna(5).clip(lower=1)
            fig3 = px.scatter(
                tb_scatter,
                x="price", y="monthly_sales",
                color="keyword",
                size="bubble_size",
                hover_data=["title", "shop_name"],
                title="价格 vs 月销量（气泡大小=评价数）",
                labels={
                    "price": "价格（元）",
                    "monthly_sales": "月销量（件）",
                    "keyword": "品类",
                },
                opacity=0.7,
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("需要月销量数据才能显示甜蜜区间图")

        st.divider()

        # 各品类均价对比
        st.subheader("💰 各品类均价对比")
        price_by_kw = tb_valid.groupby("keyword")["price"].agg(["mean", "min", "max"]).reset_index()
        price_by_kw.columns = ["品类", "均价", "最低价", "最高价"]
        price_by_kw = price_by_kw.round(2)

        fig4 = go.Figure()
        fig4.add_trace(go.Bar(name="均价", x=price_by_kw["品类"], y=price_by_kw["均价"], marker_color="#4ECDC4"))
        fig4.add_trace(go.Scatter(name="最低价", x=price_by_kw["品类"], y=price_by_kw["最低价"], mode="markers", marker=dict(color="green", size=10)))
        fig4.add_trace(go.Scatter(name="最高价", x=price_by_kw["品类"], y=price_by_kw["最高价"], mode="markers", marker=dict(color="red", size=10)))
        fig4.update_layout(title="各品类价格区间（均价 + 最低/最高）", xaxis_title="品类", yaxis_title="价格（元）")
        st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════
# Tab 3：小红书趋势
# ══════════════════════════════════════════════
with tab3:
    st.header("📕 小红书内容趋势")

    if xhs_filtered.empty:
        st.info("小红书数据尚未爬取，请先运行 `bash run.sh`")
    else:
        row1_left, row1_right = st.columns(2)

        # 各关键词互动总量对比（点赞+评论+收藏）
        with row1_left:
            xhs_filtered["总互动"] = xhs_filtered["likes"] + xhs_filtered["comments"] + xhs_filtered["collects"]
            kw_interact = xhs_filtered.groupby("keyword")[["likes", "comments", "collects"]].sum().reset_index()
            kw_interact_melted = kw_interact.melt(id_vars="keyword", var_name="类型", value_name="数量")
            type_map = {"likes": "点赞", "comments": "评论", "collects": "收藏"}
            kw_interact_melted["类型"] = kw_interact_melted["类型"].map(type_map)
            fig = px.bar(
                kw_interact_melted, x="keyword", y="数量", color="类型",
                title="各品类互动量对比（点赞/评论/收藏）",
                barmode="group",
                labels={"keyword": "搜索词"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # 点赞数分布
        with row1_right:
            fig2 = px.histogram(
                xhs_filtered, x="likes", nbins=30,
                color="keyword",
                title="笔记点赞数分布",
                labels={"likes": "点赞数", "count": "笔记数"},
                barmode="overlay",
                opacity=0.7,
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        # 热门笔记 TOP 20
        st.subheader("🔥 互动量 TOP 20 笔记")
        top_notes = xhs_filtered.nlargest(20, "总互动")[
            ["keyword", "title", "likes", "comments", "collects", "author", "url"]
        ].copy()
        top_notes.columns = ["品类", "标题", "点赞", "评论", "收藏", "作者", "链接"]
        top_notes.index = range(1, len(top_notes) + 1)
        st.dataframe(top_notes, use_container_width=True)

        st.divider()

        # 互动量散点图：点赞 vs 收藏（衡量内容质量）
        st.subheader("❤️ 点赞 vs 收藏（内容质量象限）")
        st.caption("右上角：高点赞+高收藏 = 最值得参考的爆款内容方向")
        fig3 = px.scatter(
            xhs_filtered, x="likes", y="collects",
            color="keyword",
            hover_data=["title", "author"],
            title="点赞数 vs 收藏数",
            labels={"likes": "点赞数", "collects": "收藏数", "keyword": "品类"},
            opacity=0.7,
        )
        st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════════════
# Tab 4：数据明细
# ══════════════════════════════════════════════
with tab4:
    st.header("📋 数据明细")

    subtab1, subtab2 = st.tabs(["淘宝商品", "小红书笔记"])

    with subtab1:
        if tb_filtered.empty:
            st.info("暂无淘宝数据")
        else:
            # 排序选项
            sort_col = st.selectbox("排序字段", ["monthly_sales", "price", "review_count"], index=0, key="tb_sort")
            tb_show = tb_filtered[tb_filtered["price"] > 0].sort_values(sort_col, ascending=False, na_position="last")
            tb_cols = ["keyword", "title", "price", "monthly_sales", "review_count", "shop_name"]
            tb_col_names = ["品类", "商品标题", "价格", "月销量", "评价数", "店铺名"]
            if "shipping_time" in tb_show.columns:
                tb_cols.append("shipping_time")
                tb_col_names.append("发货时间")
            if "has_video" in tb_show.columns:
                tb_cols += ["has_video"]
                tb_col_names += ["有视频"]
            tb_cols += ["crawled_at", "url"]
            tb_col_names += ["爬取时间", "链接"]
            tb_show = tb_show[tb_cols]
            tb_show.columns = tb_col_names
            tb_show.index = range(1, len(tb_show) + 1)
            st.dataframe(tb_show, use_container_width=True)
            st.caption(f"共 {len(tb_show)} 条商品")

    with subtab2:
        if xhs_filtered.empty:
            st.info("暂无小红书数据")
        else:
            sort_col2 = st.selectbox("排序字段", ["likes", "comments", "collects"], index=0, key="xhs_sort")
            xhs_show = xhs_filtered.sort_values(sort_col2, ascending=False)
            xhs_cols = ["keyword", "title", "likes", "comments", "collects", "author"]
            xhs_col_names = ["品类", "笔记标题", "点赞", "评论", "收藏", "作者"]
            if "purchase_intent" in xhs_show.columns:
                xhs_cols.append("purchase_intent")
                xhs_col_names.append("购买意愿")
            xhs_cols += ["crawled_at", "url"]
            xhs_col_names += ["爬取时间", "链接"]
            xhs_show = xhs_show[xhs_cols]
            xhs_show.columns = xhs_col_names
            xhs_show.index = range(1, len(xhs_show) + 1)
            st.dataframe(xhs_show, use_container_width=True)
            st.caption(f"共 {len(xhs_show)} 条笔记")

# ══════════════════════════════════════════════
# Tab 5：选品总结
# ══════════════════════════════════════════════
with tab5:
    st.header("🧠 选品总结")
    st.caption("基于已爬取数据自动生成，数据越多结论越准确")

    if tb_filtered.empty and xhs_filtered.empty:
        st.info("暂无数据，请先运行爬虫")
    else:
        tb_valid = tb_filtered[tb_filtered["price"] > 0].copy() if not tb_filtered.empty else pd.DataFrame()
        has_sales = not tb_valid.empty and tb_valid["monthly_sales"].notna().any()

        # ── 1. 核心指标速览 ──────────────────────────
        st.subheader("📊 核心指标速览")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if not tb_valid.empty:
                st.metric("淘宝商品数", len(tb_valid))
        with c2:
            if has_sales:
                top_kw = tb_valid.groupby("keyword")["monthly_sales"].sum().idxmax()
                st.metric("月销量最高品类", top_kw)
        with c3:
            if not xhs_filtered.empty:
                xhs_top_kw = xhs_filtered.groupby("keyword")["likes"].mean().idxmax()
                st.metric("小红书最热品类", xhs_top_kw)
        with c4:
            if not xhs_filtered.empty and "purchase_intent" in xhs_filtered.columns:
                intent_rate = xhs_filtered["purchase_intent"].mean() * 100
                st.metric("笔记购买意愿率", f"{intent_rate:.1f}%",
                          help="评论/标题含'在哪买''求链接'等关键词的笔记占比")

        st.divider()

        col_l, col_r = st.columns(2)

        # ── 2. 价格甜蜜区间 ──────────────────────────
        with col_l:
            st.subheader("💰 价格甜蜜区间")
            if has_sales:
                tb_s = tb_valid[tb_valid["monthly_sales"].notna()].copy()
                # 按价格分桶（20元一档）
                tb_s["价格段"] = (tb_s["price"] // 20 * 20).astype(int).astype(str) + "-" + \
                                  ((tb_s["price"] // 20 * 20 + 20).astype(int).astype(str)) + "元"
                bucket = tb_s.groupby("价格段").agg(
                    商品数=("price", "count"),
                    月销量合计=("monthly_sales", "sum"),
                    均价=("price", "mean")
                ).reset_index().sort_values("月销量合计", ascending=False)

                best = bucket.iloc[0]
                st.success(f"月销量最集中价格段：**{best['价格段']}**  "
                           f"（月销 {int(best['月销量合计']):,} 件，共 {int(best['商品数'])} 款商品）")

                fig = px.bar(bucket.head(8), x="价格段", y="月销量合计",
                             color="商品数", color_continuous_scale="Oranges",
                             title="各价格段月销量合计（Top 8）",
                             labels={"月销量合计": "月销量（件）", "价格段": "价格区间"})
                fig.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("需要月销量数据")

        # ── 3. 竞争强度分析 ──────────────────────────
        with col_r:
            st.subheader("⚔️ 各品类竞争强度")
            if not tb_valid.empty:
                comp = tb_valid.groupby("keyword").agg(
                    商品数=("price", "count"),
                    均价=("price", "mean"),
                    月销量均值=("monthly_sales", "mean"),
                ).reset_index().round(1)
                comp.columns = ["品类", "商品数", "均价（元）", "月销均值"]

                # 竞争强度 = 商品数越多越激烈，月销均值越高越有市场
                if comp["月销均值"].notna().any():
                    comp["市场潜力"] = (comp["月销均值"].fillna(0) / comp["月销均值"].max() * 100).round(1)
                    comp["竞争强度"] = (comp["商品数"] / comp["商品数"].max() * 100).round(1)
                    # 机会分 = 市场潜力 - 竞争强度（越高越值得切入）
                    comp["机会分"] = (comp["市场潜力"] - comp["竞争强度"]).round(1)
                    comp = comp.sort_values("机会分", ascending=False)

                    best_opp = comp.iloc[0]
                    st.success(f"机会最大品类：**{best_opp['品类']}**  "
                               f"（机会分 {best_opp['机会分']}，均价 ¥{best_opp['均价（元）']}）")

                comp.index = range(1, len(comp) + 1)
                st.dataframe(comp, use_container_width=True)
            else:
                st.info("需要淘宝数据")

        st.divider()

        col_l2, col_r2 = st.columns(2)

        # ── 4. 发货时间分布 ──────────────────────────
        with col_l2:
            st.subheader("🚚 发货时间分布")
            if not tb_valid.empty and "shipping_time" in tb_valid.columns:
                ship = tb_valid["shipping_time"].dropna()
                if not ship.empty:
                    ship_vc = ship.value_counts().reset_index()
                    ship_vc.columns = ["发货时间", "数量"]
                    fig = px.pie(ship_vc, names="发货时间", values="数量",
                                 title="各发货时效占比")
                    st.plotly_chart(fig, use_container_width=True)
                    # 判断定制比例
                    custom_keywords = ["定制", "7天", "10天", "15天", "工作日"]
                    custom_count = ship.apply(lambda x: any(k in str(x) for k in custom_keywords)).sum()
                    if custom_count / len(ship) > 0.3:
                        st.warning(f"⚠️ {custom_count/len(ship)*100:.0f}% 的商品为定制/长周期发货，"
                                   f"库存压力低但履约周期长，差评风险需控制")
                    else:
                        st.info(f"✅ 以快速发货商品为主，适合测款")
                else:
                    st.info("发货时间字段暂未采集到数据（下次爬取后显示）")
            else:
                st.info("发货时间字段暂未采集到数据（下次爬取后显示）")

        # ── 5. 小红书购买意愿热门内容 ──────────────────
        with col_r2:
            st.subheader("🛒 小红书高购买意愿笔记")
            if not xhs_filtered.empty and "purchase_intent" in xhs_filtered.columns:
                intent_notes = xhs_filtered[xhs_filtered["purchase_intent"] == 1].copy()
                if not intent_notes.empty:
                    intent_notes["总互动"] = intent_notes["likes"] + intent_notes["comments"] + intent_notes["collects"]
                    top_intent = intent_notes.nlargest(10, "总互动")[
                        ["keyword", "title", "likes", "comments", "collects", "url"]
                    ].copy()
                    top_intent.columns = ["品类", "标题", "点赞", "评论", "收藏", "链接"]
                    top_intent.index = range(1, len(top_intent) + 1)
                    st.dataframe(top_intent, use_container_width=True)
                    st.caption(f"共 {len(intent_notes)} 篇笔记含购买意愿信号")
                else:
                    st.info("暂未检测到含购买意愿关键词的笔记")
            else:
                st.info("购买意愿字段暂未采集到数据（下次爬取后显示）")

        st.divider()

        # ── 6. 文字总结建议 ──────────────────────────
        st.subheader("📝 选品建议")
        advice = []

        if has_sales and not tb_valid.empty:
            best_kw = tb_valid.groupby("keyword")["monthly_sales"].sum().idxmax()
            best_price = tb_valid[tb_valid["keyword"] == best_kw]["price"].median()
            advice.append(f"**① 主推品类**：`{best_kw}` 月销量合计最高，建议优先切入，"
                          f"参考定价在 ¥{best_price:.0f} 附近（中位数价格）。")

        if not tb_valid.empty:
            low_comp_kw = tb_valid.groupby("keyword").size().idxmin()
            advice.append(f"**② 低竞争机会**：`{low_comp_kw}` 搜索结果商品数最少，"
                           f"若需求存在（小红书有热度），可作为差异化切入点。")

        if not xhs_filtered.empty:
            xhs_top = xhs_filtered.groupby("keyword")["likes"].mean().idxmax()
            advice.append(f"**③ 内容营销方向**：小红书上 `{xhs_top}` 品类笔记平均点赞最高，"
                           f"建议优先为该品类制作种草内容。")

        if not tb_valid.empty and "has_video" in tb_valid.columns:
            video_rate = tb_valid["has_video"].mean() * 100
            if video_rate < 30:
                advice.append(f"**④ 主图视频机会**：目前仅 {video_rate:.0f}% 的竞品有视频主图，"
                               f"制作高质量视频主图可形成差异化优势。")
            else:
                advice.append(f"**④ 主图视频**：{video_rate:.0f}% 的竞品已有视频主图，"
                               f"不上视频将处于劣势。")

        if advice:
            for item in advice:
                st.markdown(f"- {item}")
        else:
            st.info("数据不足，爬取更多数据后自动生成建议")

        st.caption("⚠️ 以上建议基于规则自动生成，仅供参考，请结合实际供应链情况判断。")
