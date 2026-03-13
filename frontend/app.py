import streamlit as st
import requests
import json
import base64

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Compliance Verification System",
    layout="wide"
)

def display_pdf(file_bytes):
    base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

st.title("GA4GH Compliance Verifier")
st.markdown("Verify Data Use Letters (DUL) against GA4GH policies and Data Use Ontology (DUO) tags.")

with st.sidebar:
    st.header("Admin Settings")
    st.markdown("Upload base policies to update the knowledge base.")
    policy_file = st.file_uploader("Upload Base Policy (PDF)", type=["pdf"], key="policy_upload")
    if policy_file is not None and st.button("Ingest Policy"):
        with st.spinner("Ingesting policy..."):
            files = {"file": (policy_file.name, policy_file.getvalue(), "application/pdf")}
            try:
                response = requests.post(f"{API_URL}/ingest_policy", files=files)
                if response.status_code == 200:
                    st.success("Policy successfully ingested.")
                else:
                    st.error(f"Error: {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Backend API is not running.")


st.header("1. Upload Data Use Letter (DUL)")
dul_file = st.file_uploader("Upload your DUL for compliance checking (PDF)", type=["pdf"], key="dul_upload")

if dul_file is not None:
    st.subheader("2. Compliance Report & Side-by-Side Verification")
    
    verify_button = st.button("Run Compliance Check", type="primary")
    
    if verify_button:
        with st.spinner("Analyzing document against policies..."):
            files = {"file": (dul_file.name, dul_file.getvalue(), "application/pdf")}
            try:
                response = requests.post(f"{API_URL}/verify", files=files)
                if response.status_code == 200:
                    report = response.json()
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("### User DUL Document")
                        display_pdf(dul_file.getvalue())
                        
                    with col2:
                        st.markdown("### Compliance Dashboard")
                        
                        with st.expander("Agent Reasoning Trace", expanded=False):
                            trace = report.get("reasoning_trace", [])
                            if trace:
                                for step in trace:
                                    st.write(f"- {step}")
                            else:
                                st.write("No reasoning trace available.")
                        
                        status = report.get("status", "Unknown")
                        if status == "Compliant":
                            st.success(f"**Overall Status: {status}**")
                        elif status == "Non-Compliant":
                            st.error(f"**Overall Status: {status}**")
                        else:
                            st.warning(f"**Overall Status: {status}**")
                            
                        st.write(report.get("summary", ""))
                        
                        st.markdown("### Machine-Readable DUO Tags")
                        tags = report.get("primary_duo_tags", [])
                        if not tags:
                            st.info("No primary DUO tags resolved.")
                        for tag in tags:
                            st.code(f"{tag.get('tag')} - {tag.get('description')}", language="yaml")
                            
                        st.markdown("### Findings & Policy Citations")
                        findings = report.get("findings", [])
                        
                        if not findings and status == "Compliant":
                            st.success("No gaps or conflicts found.")
                            
                        for i, finding in enumerate(findings):
                            with st.expander(f"{finding.get('severity', 'Info')} {finding.get('finding_type', 'Finding')}: {finding.get('description')[:50]}..."):
                                st.write(f"**Description:** {finding.get('description')}")
                                
                                related_tags = finding.get("mapped_duo_tags", [])
                                if related_tags:
                                    st.write("**Related Tags:**")
                                    for rt in related_tags:
                                        st.caption(f"- {rt.get('tag')}: {rt.get('description')}")
                                
                                citations = finding.get("citations", [])
                                if citations:
                                    st.markdown("#### Grounding Citations")
                                    for c in citations:
                                        st.info(f"**Page {c.get('page_number', 'N/A')} | {c.get('section_header', 'Section N/A')} | {c.get('clause_id', '')}**\n\n\"{c.get('extracted_text', '')}\"")
                                        
                else:
                    st.error(f"Error checking compliance: {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Backend API is not running.")
