import os
import json
from typing import Dict, List, TypedDict, Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from backend.ingestion import IngestionEngine
from backend.models import ComplianceReport, Finding, DUOMapping, ClauseCitation

load_dotenv()

duo_mapping_path = os.path.join(os.path.dirname(__file__), "../data/duo_mapping.json")
try:
    with open(duo_mapping_path, "r") as f:
        DUO_MAPPINGS = json.load(f)
except Exception:
    DUO_MAPPINGS = []

class AgentState(TypedDict):
    user_dul_text: str
    extracted_intent: str
    sample_size: int
    retrieved_policies: List[Dict]
    primary_duo_tags: List[Dict]
    findings: List[Dict] 
    status: str
    summary: str
    reasoning_trace: List[str]

class ExtractionOutput(BaseModel):
    research_intent: str = Field(..., description="A short summary of the research intent (e.g., 'heart study', 'cancer research')")
    sample_size: int = Field(..., description="The number of participants or samples in the study. Default to 0 if not specified.")

def extraction_agent(state: AgentState):
    llm = ChatGroq(temperature=0, model_name="llama3-8b-8192")
    structured_llm = llm.with_structured_output(ExtractionOutput)
    
    prompt = PromptTemplate(
        template="Extract the research intent and sample size from the following Data Use Letter.\n\n{dul_text}",
        input_variables=["dul_text"]
    )
    
    try:
        result = structured_llm.invoke(prompt.format(dul_text=state["user_dul_text"]))
        state["extracted_intent"] = result.research_intent
        state["sample_size"] = result.sample_size
        state["reasoning_trace"].append(f"Extraction Agent: Identified intent '{result.research_intent}' with sample size {result.sample_size}.")
    except Exception as e:
        state["extracted_intent"] = state["user_dul_text"][:50]
        state["sample_size"] = 0
        state["reasoning_trace"].append(f"Extraction Agent: Fallback triggered due to LLM error: {str(e)[:50]}...")
        
    return state

def compliance_analysis_agent(state: AgentState):
    intent = state["extracted_intent"].lower()
    sample_size = state["sample_size"]
    
    matched_tags = []
    for mapping in DUO_MAPPINGS:
        if any(keyword in intent for keyword in mapping.get("keywords", [])):
            matched_tags.append({"tag": mapping["tag"], "description": mapping["description"]})
    
    if len(matched_tags) == 0:
        matched_tags.append({"tag": "DUO:0000042", "description": "General Research Use"})
        state["reasoning_trace"].append("Compliance Analysis Agent: No specific keywords matched. Defaulting to DUO:0000042 (General Research Use).")
    else:
        state["reasoning_trace"].append(f"Compliance Analysis Agent: Mapped intent to DUO tags: {[t['tag'] for t in matched_tags]}.")
        
    state["primary_duo_tags"] = matched_tags
    
    vector_store_path = os.path.join(os.path.dirname(__file__), "../data/faiss_index")
    engine = IngestionEngine(vector_store_path=vector_store_path)
    store = engine.load_vector_store()
    
    retrieved = []
    if store:
        retriever = store.as_retriever(search_kwargs={"k": 5})
        query = f"Data use requirements for {intent}"
        if sample_size > 100:
            query += " genomic data sharing large-scale human data"
            state["reasoning_trace"].append(f"Compliance Analysis Agent: Large-scale threshold met (sample_size={sample_size} > 100). Forcing retrieval of GDS clauses.")
        else:
            state["reasoning_trace"].append(f"Compliance Analysis Agent: Sample size {sample_size} <= 100. Standard retrieval applied.")
            
        docs = retriever.invoke(query)
        for d in docs:
            retrieved.append({
                "page_number": d.metadata.get("Page Number"),
                "section_header": d.metadata.get("Section Header"),
                "clause_id": d.metadata.get("Clause ID"),
                "text": d.page_content,
                "source_document": d.metadata.get("Source Document", "Unknown"),
                "chunk_id": d.metadata.get("Chunk ID")
            })
            
    state["retrieved_policies"] = retrieved
    
    context_str = ""
    for idx, p in enumerate(retrieved):
        context_str += f"\n--- Policy {idx+1} ({p['source_document']}) ---\n[Clause: {p['clause_id']}]\n{p['text']}\n"
    
    prompt = PromptTemplate(
        template="""
        You are an expert compliance officer. Analyze the user intent against the retrieved policies.
        User Intent: {intent}
        Sample Size: {sample_size}
        
        Policies:
        {context}
        
        Determine if this is Compliant. Extract findings (Conflicts or Gaps) and list exact citations from the policies to prove them.
        """,
        input_variables=["intent", "sample_size", "context"]
    )
    
    llm = ChatGroq(temperature=0, model_name="llama3-70b-8192")
    structured_llm = llm.with_structured_output(ComplianceReport)
    
    try:
        report: ComplianceReport = structured_llm.invoke(prompt.format(
            intent=intent, 
            sample_size=sample_size, 
            context=context_str
        ))
        
        state["status"] = report.status
        state["summary"] = report.summary
        state["findings"] = [f.dict() for f in report.findings]
        state["reasoning_trace"].append(f"Compliance Analysis Agent: Evaluated status as '{report.status}'.")
    except Exception as e:
        state["status"] = "Needs Review"
        state["summary"] = f"System Error evaluating compliance."
        state["findings"] = []
        state["reasoning_trace"].append(f"Compliance Analysis Agent: API Error ({str(e)[:50]}), skipping strict generation.")

    return state

def citation_verification_agent(state: AgentState):
    metadata_store_path = os.path.join(os.path.dirname(__file__), "../data/metadata_store.json")
    
    if not os.path.exists(metadata_store_path):
        state["reasoning_trace"].append("Citation Verification Agent: Warning - metadata store not found, skipping literal text verification.")
        return state
        
    with open(metadata_store_path, "r") as f:
        metadata_store = json.load(f)
        
    verified_findings = []
    for finding in state["findings"]:
        verified_citations = []
        for citation in finding.get("citations", []):
            extracted_text = citation.get("extracted_text", "")
            if not extracted_text:
                continue
                
            is_verified = False
            for chunk_id, chunk_data in metadata_store.items():
                snippet = extracted_text[:40].strip()
                if snippet and snippet in chunk_data["text"]:
                    is_verified = True
                    citation["clause_id"] = chunk_data["clause_id"]
                    citation["section_header"] = chunk_data["section_header"]
                    citation["page_number"] = chunk_data.get("page_number")
                    break
                    
            if is_verified:
                verified_citations.append(citation)
            else:
                state["reasoning_trace"].append(f"Citation Verification Agent: Hallucinated citation detected: '{extracted_text[:30]}...'. Removing it.")
                
        finding["citations"] = verified_citations
        verified_findings.append(finding)
        
    state["findings"] = verified_findings
    if any(len(f["citations"]) > 0 for f in verified_findings):
        state["reasoning_trace"].append("Citation Verification Agent: Successfully grounded citations in source text.")
    else:
        state["reasoning_trace"].append("Citation Verification Agent: No valid grounded citations found.")
        
    return state

def build_agent_loop():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("extraction", extraction_agent)
    workflow.add_node("compliance", compliance_analysis_agent)
    workflow.add_node("verification", citation_verification_agent)
    
    workflow.set_entry_point("extraction")
    workflow.add_edge("extraction", "compliance")
    workflow.add_edge("compliance", "verification")
    workflow.add_edge("verification", END)
    
    return workflow.compile()
