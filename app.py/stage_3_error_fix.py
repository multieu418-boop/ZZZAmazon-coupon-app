import streamlit as st
import pandas as pd

st.set_page_config(page_title="第三阶段：纠错重做", layout="wide")

st.title("🛠️ 第三阶段：纠错重做流")

err_file = st.file_uploader("上传亚马逊返回的报错 Excel 文件", type=['xlsx'])

if err_file:
    df = pd.read_excel(err_file)
    st.warning("识别到报错行，请查看最后一列的 Error Message 进行修正。")
    st.dataframe(df)