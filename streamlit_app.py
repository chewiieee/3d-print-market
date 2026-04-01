import traceback
import streamlit as st

try:
	from dashboard import *  # noqa: F401,F403
except Exception as e:
	st.error("应用启动失败，请将以下错误信息发给开发者。")
	st.exception(e)
	st.code(traceback.format_exc())
