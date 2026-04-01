import traceback
import sys
import os
import streamlit as st

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(__file__))

try:
    from dashboard import *  # noqa: F401,F403
except Exception as e:
    st.error("应用启动失败，请将以下错误信息发给开发者。")
    st.exception(e)
    st.code(traceback.format_exc())
