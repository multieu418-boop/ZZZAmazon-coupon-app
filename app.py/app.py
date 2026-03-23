import streamlit as st
import pandas as pd
import io
import re
from openpyxl import load_workbook
import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="Cupshe 亚马逊优惠券助手", layout="wide")

# --- 2. 状态初始化 ---
if 'coupon_pool' not in st.session_state:
    st.session_state.coupon_pool = []
if 'field_configs' not in st.session_state:
    st.session_state.field_configs = []

# --- 3. 核心工具函数 ---

def clean_asin_format(raw_text):
    """【需求】无论输入什么，输出必须是英文分号分隔"""
    if not raw_text: return "", 0
    tokens = re.split(r'[;；,，\s\n\r]+', str(raw_text).strip())
    clean_list = [t.strip().upper() for t in tokens if t.strip()]
    seen = set()
    final_list = [x for x in clean_list if not (x in seen or seen.add(x))]
    return ";".join(final_list), len(final_list)

def detect_date_format(sample_str):
    """【需求】自动识别第8/9行的日期格式"""
    if not sample_str or "/" not in str(sample_str):
        return "%m/%d/%Y" # 默认亚马逊最常用的美式格式
    
    parts = str(sample_str).split("/")
    if len(parts) == 3:
        # 如果第一部分大于12，那肯定是 日/月/年
        if int(parts[0]) > 12: return "%d/%m/%Y"
        # 如果中间部分大于12，那肯定是 月/日/年
        if int(parts[1]) > 12: return "%m/%d/%Y"
    return "%m/%d/%Y"

# --- 4. 侧边栏与模板解析 ---
st.sidebar.header("🛠️ 控制中心")
mode = st.sidebar.radio("选择操作阶段", ["第一阶段：需求录入", "第二阶段：校验与导出"])

template_file = st.sidebar.file_uploader("上传 Coupon 原始模板 (Excel)", type=['xlsx'])

if template_file and not st.session_state.field_configs:
    wb = load_workbook(template_file, data_only=True)
    ws = wb.active
    configs = []
    for col in range(1, 26):
        title = ws.cell(row=7, column=col).value
        hint = ws.cell(row=5, column=col).value
        # 抓取第8, 9行示例
        sample_8 = ws.cell(row=8, column=col).value
        sample_9 = ws.cell(row=9, column=col).value
        
        if title:
            is_drop = any(k in str(title) for k in ["折扣类型", "限购", "限制", "买家", "叠加", "类型"])
            date_fmt = None
            if any(k in str(title) for k in ["日期", "Date"]):
                # 自动从第8/9行检测格式
                date_fmt = detect_date_format(sample_8 or sample_9)
            
            configs.append({
                "col": col, "label": str(title).strip(), 
                "hint": str(hint).strip() if hint else "遵循亚马逊规则",
                "is_dropdown": is_drop, 
                "options": [str(sample_8), str(sample_9)] if is_drop else [],
                "date_format": date_fmt
            })
    st.session_state.field_configs = configs

# --- 5. 第一阶段：录入测试 ---
if mode == "第一阶段：需求录入":
    if not st.session_state.field_configs:
        st.info("👋 请先上传模板。")
    else:
        with st.form("entry_form", clear_on_submit=True):
            user_input = {}
            grid = st.columns(2)
            for i, cfg in enumerate(st.session_state.field_configs):
                with grid[i % 2]:
                    if cfg['is_dropdown']:
                        user_input[cfg['col']] = st.selectbox(cfg['label'], options=cfg['options'], help=cfg['hint'])
                    elif cfg['date_format']:
                        user_input[cfg['col']] = st.date_input(cfg['label'], help=f"输出格式将匹配模板: {cfg['date_format']}")
                    elif "ASIN" in cfg['label'].upper():
                        user_input[cfg['col']] = st.text_area(cfg['label'], help=cfg['hint'])
                    else:
                        user_input[cfg['col']] = st.text_input(cfg['label'], help=cfg['hint'])
            
            if st.form_submit_button("➕ 确认添加"):
                row = {}
                for c_idx, val in user_input.items():
                    cfg = next(c for c in st.session_state.field_configs if c['col'] == c_idx)
                    # 格式化日期
                    if cfg['date_format'] and isinstance(val, (datetime.date, datetime.datetime)):
                        row[c_idx] = val.strftime(cfg['date_format'])
                    # 格式化 ASIN
                    elif "ASIN" in cfg['label'].upper():
                        clean_str, _ = clean_asin_format(val)
                        row[c_idx] = clean_str
                    else:
                        row[c_idx] = str(val)
                st.session_state.coupon_pool.append(row)
                st.toast("已按照模板格式记录需求")

    if st.session_state.coupon_pool:
        st.subheader("📋 预览 (请检查日期和 ASIN 格式)")
        st.dataframe(pd.DataFrame(st.session_state.coupon_pool))
