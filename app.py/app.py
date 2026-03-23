import streamlit as st
import pandas as pd
import io
import re
from openpyxl import load_workbook
import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="Cupshe 亚马逊优惠券助手", layout="wide")

# --- 2. 状态初始化 (防止页面刷新数据丢失) ---
if 'coupon_pool' not in st.session_state:
    st.session_state.coupon_pool = []
if 'field_configs' not in st.session_state:
    st.session_state.field_configs = []
if 'inventory_db' not in st.session_state:
    st.session_state.inventory_db = None

# --- 3. 核心逻辑函数 ---

def clean_asin_format(raw_text):
    """【需求实现】无论输入什么格式，统一输出分号分隔"""
    if not raw_text: return "", 0
    # 匹配换行、空格、中英文逗号/分号
    tokens = re.split(r'[;；,，\s\n\r]+', str(raw_text).strip())
    clean_list = [t.strip().upper() for t in tokens if t.strip()]
    # 去重
    seen = set()
    final_list = [x for x in clean_list if not (x in seen or seen.add(x))]
    return ";".join(final_list), len(final_list)

def load_inventory(file):
    """导入 All Listing Report 校验价格和在售"""
    try:
        content = file.read()
        for enc in ['utf-16', 'utf-8', 'gbk']:
            try:
                df = pd.read_csv(io.BytesIO(content), sep='\t', encoding=enc)
                if 'asin1' in df.columns:
                    return df.set_index('asin1')
            except: continue
        return None
    except: return None

# --- 4. 侧边栏：多阶段切换与文件上传 ---
st.sidebar.header("🛠️ 控制中心")
mode = st.sidebar.radio("选择操作阶段", ["第一阶段：需求录入", "第二阶段：校验与导出", "第三阶段：纠错重做"])

st.sidebar.divider()
inv_file = st.sidebar.file_uploader("1. 导入 All Listing Report (TXT)", type=['txt'])
if inv_file and st.session_state.inventory_db is None:
    st.session_state.inventory_db = load_inventory(inv_file)
    if st.session_state.inventory_db is not None:
        st.sidebar.success("✅ 库存数据已加载")

template_file = st.sidebar.file_uploader("2. 上传 Coupon 原始模板 (Excel)", type=['xlsx'])

# --- 5. 模板解析 (读取第5行和第7行) ---
if template_file and not st.session_state.field_configs:
    wb = load_workbook(template_file, data_only=True)
    ws = wb.active
    configs = []
    for col in range(1, 26):
        title = ws.cell(row=7, column=col).value
        hint = ws.cell(row=5, column=col).value
        if title:
            # 提取下拉选项
            samples = [str(ws.cell(row=r, column=col).value).strip() for r in [8,9] if ws.cell(row=r, column=col).value]
            is_drop = any(k in str(title) for k in ["折扣类型", "限购", "限制", "买家", "叠加", "类型"])
            configs.append({
                "col": col, "label": str(title).strip(), 
                "hint": str(hint).strip() if hint else "遵循亚马逊规则",
                "is_dropdown": is_drop, "options": samples if samples else ["是", "否"]
            })
    st.session_state.field_configs = configs

# --- 6. 主界面逻辑分发 ---
st.title(f"👗 Cupshe 助手 - {mode}")

if mode == "第一阶段：需求录入":
    if not st.session_state.field_configs:
        st.warning("👋 请先在侧边栏上传『Coupon 原始模板』以生成表单。")
    else:
        with st.form("entry_form", clear_on_submit=True):
            st.subheader("📝 录入新优惠券")
            user_input = {}
            cols = st.columns(2)
            for i, cfg in enumerate(st.session_state.field_configs):
                with cols[i % 2]:
                    if cfg['is_dropdown']:
                        user_input[cfg['col']] = st.selectbox(cfg['label'], options=cfg['options'], help=cfg['hint'])
                    elif "ASIN" in cfg['label'].upper():
                        user_input[cfg['col']] = st.text_area(cfg['label'], help=cfg['hint'], placeholder="粘贴ASIN，自动转为分号分隔")
                    elif "日期" in cfg['label'] or "Date" in cfg['label']:
                        user_input[cfg['col']] = st.date_input(cfg['label'], value=datetime.date.today()+datetime.timedelta(days=1))
                    else:
                        user_input[cfg['col']] = st.text_input(cfg['label'], help=cfg['hint'])
            
            if st.form_submit_button("➕ 确认添加并格式化"):
                row = {}
                for c_idx, val in user_input.items():
                    lbl = next(c['label'] for c in st.session_state.field_configs if c['col'] == c_idx)
                    if "ASIN" in lbl.upper():
                        # 【核心】强制格式化
                        final_asin, count = clean_asin_format(val)
                        row[c_idx] = final_asin
                        st.toast(f"已处理 {count} 个 ASIN")
                    elif isinstance(val, (datetime.date, datetime.datetime)):
                        row[c_idx] = val.strftime("%m/%d/%Y")
                    else:
                        row[c_idx] = str(val)
                st.session_state.coupon_pool.append(row)

elif mode == "第二阶段：校验与导出":
    if not st.session_state.coupon_pool:
        st.info("需求池为空，请先前往第一阶段录入。")
    else:
        df_preview = pd.DataFrame(st.session_state.coupon_pool)
        mapping = {c['col']: c['label'] for c in st.session_state.field_configs}
        st.dataframe(df_preview.rename(columns=mapping))

        if st.button("🚀 生成并下载 Excel"):
            template_file.seek(0)
            wb_out = load_workbook(template_file)
            ws_out = wb_out.active
            # 找空行
            curr_r = 8
            while ws_out.cell(row=curr_r, column=1).value: curr_r += 1
            # 写入
            for data in st.session_state.coupon_pool:
                for c_idx, v in data.items():
                    ws_out.cell(row=curr_r, column=int(c_idx)).value = v
                curr_r += 1
            # 下载
            buf = io.BytesIO()
            wb_out.save(buf)
            st.download_button("💾 点击下载文件", buf.getvalue(), f"Coupon_{datetime.date.today()}.xlsx")

elif mode == "第三阶段：纠错重做":
    st.info("上传亚马逊报错文件（Review Report），即可在此快速定位错误行。")
    err_file = st.file_uploader("上传报错 Excel", type=['xlsx'])
    if err_file:
        st.dataframe(pd.read_excel(err_file))