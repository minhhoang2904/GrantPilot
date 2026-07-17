"""
frontend / app.py

Streamlit UI cho Policy Advisor:
- Sidebar: nhập hồ sơ doanh nghiệp -> gọi server-c-eligibility để lọc/xếp hạng
  các chính sách đủ điều kiện hưởng.
- Khung chat chính: hỏi đáp tự do -> gọi server-b-retrieval để tra cứu + sinh câu trả lời.

Chạy dev: streamlit run app.py
"""

import os

import requests
import streamlit as st


def get_config(key: str, default: str) -> str:
    if key in st.secrets:
        return st.secrets[key]
    return os.environ.get(key, default)


SERVER_B_URL = get_config("SERVER_B_URL", "http://localhost:8001")
SERVER_C_URL = get_config("SERVER_C_URL", "http://localhost:8002")

st.set_page_config(page_title="Policy Advisor", page_icon="📋", layout="wide")
st.title("📋 Policy Advisor")
st.caption("Tư vấn chính sách hỗ trợ doanh nghiệp")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Hồ sơ doanh nghiệp")
    with st.form("profile_form"):
        business_name = st.text_input("Tên doanh nghiệp")
        industry = st.text_input("Ngành nghề (vd: cong_nghe)")
        business_type = st.selectbox(
            "Loại hình", ["sme", "doanh_nghiep_nho", "startup", "ho_kinh_doanh"]
        )
        num_employees = st.number_input("Số lao động", min_value=0, step=1, value=0)
        province = st.text_input("Tỉnh/thành (vd: ha_noi, nong_thon)")
        annual_revenue = st.number_input(
            "Doanh thu năm (VNĐ)", min_value=0.0, step=1_000_000.0, value=0.0
        )
        founded_year = st.number_input(
            "Năm thành lập", min_value=1900, max_value=2100, value=2024, step=1
        )
        submitted = st.form_submit_button("Kiểm tra điều kiện hưởng")

    if submitted:
        profile_payload = {
            "business_name": business_name or None,
            "industry": industry or None,
            "business_type": business_type or None,
            "num_employees": int(num_employees) or None,
            "province": province or None,
            "annual_revenue": float(annual_revenue) or None,
            "founded_year": int(founded_year) or None,
        }
        try:
            resp = requests.post(
                f"{SERVER_C_URL}/eligibility/check",
                json={"profile": profile_payload, "only_eligible": True},
                timeout=10,
            )
            resp.raise_for_status()
            st.session_state["eligibility_results"] = resp.json()
        except requests.RequestException as exc:
            st.error(f"Không gọi được server-c-eligibility: {exc}")

    results = st.session_state.get("eligibility_results")
    if results:
        st.subheader("Chính sách đủ điều kiện")
        for r in results:
            policy = r["policy"]
            with st.expander(f"{policy['title']} (score: {r['score']:.2f})"):
                st.write(policy.get("summary") or policy.get("content"))
                if policy.get("source_url"):
                    st.markdown(f"[Nguồn]({policy['source_url']})")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Hỏi về chính sách hỗ trợ doanh nghiệp...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            resp = requests.post(
                f"{SERVER_B_URL}/ask", json={"question": question, "top_k": 5}, timeout=15
            )
            resp.raise_for_status()
            answer = resp.json()["answer"]
        except requests.RequestException as exc:
            answer = f"Không gọi được server-b-retrieval: {exc}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
