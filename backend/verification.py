import os
from typing import List
from dotenv import load_dotenv

from .models import ComplianceReport, Finding, ClauseCitation, DUOMapping
from .agent_loop import build_agent_loop, AgentState

# Load environment variables (like GROQ_API_KEY)
load_dotenv()

class ComplianceVerifier:
    def __init__(self, vector_store_path: str = "../data/faiss_index"):
        self.workflow = build_agent_loop()
        
    def verify_document(self, user_dul_text: str) -> ComplianceReport:
        print("Starting Multi-Agent Compliance Verification...")
        
        initial_state: AgentState = {
            "user_dul_text": user_dul_text,
            "extracted_intent": "",
            "sample_size": 0,
            "retrieved_policies": [],
            "primary_duo_tags": [],
            "findings": [],
            "status": "Unknown",
            "summary": "",
            "reasoning_trace": []
        }
        
        try:
            final_state = self.workflow.invoke(initial_state)
            
            findings_objs = []
            for f_dict in final_state.get("findings", []):
                citations = [ClauseCitation(**c) for c in f_dict.get("citations", [])]
                finding = Finding(
                    finding_type=f_dict.get("finding_type", "Gap"),
                    description=f_dict.get("description", ""),
                    severity=f_dict.get("severity", "Medium"),
                    mapped_duo_tags=[DUOMapping(**t) for t in f_dict.get("mapped_duo_tags", [])],
                    citations=citations
                )
                findings_objs.append(finding)
                
            report = ComplianceReport(
                status=final_state.get("status", "Needs Review"),
                summary=final_state.get("summary", ""),
                findings=findings_objs,
                primary_duo_tags=[DUOMapping(**t) for t in final_state.get("primary_duo_tags", [])],
                reasoning_trace=final_state.get("reasoning_trace", [])
            )
            return report
            
        except Exception as e:
            print(f"Error during agent loop: {e}")
            return ComplianceReport(
                status="Needs Review",
                findings=[],
                summary=f"Failed to verify due to agent error: {str(e)}",
                primary_duo_tags=[],
                reasoning_trace=[f"Error occurred: {str(e)}"]
            )

