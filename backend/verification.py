import os
from typing import List
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import create_extraction_chain_pydantic

from .models import ComplianceReport
from .ingestion import IngestionEngine

# Load environment variables (like GROQ_API_KEY)
load_dotenv()

class ComplianceVerifier:
    def __init__(self, vector_store_path: str = "../data/faiss_index"):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.groq_api_key or self.groq_api_key == "your_groq_api_key_here":
            print("WARNING: GROQ_API_KEY is not set correctly.")
            
        # Initialize Groq Llama 3 Model
        self.llm = ChatGroq(
            temperature=0, 
            groq_api_key=self.groq_api_key, 
            model_name="llama3-70b-8192" # Or 8b depending on speed/rate limits
        )
        
        self.ingestion_engine = IngestionEngine(vector_store_path=vector_store_path)
        self.vector_store = self.ingestion_engine.load_vector_store()
        
    def verify_document(self, user_dul_text: str) -> ComplianceReport:
        """
        Verifies a user's Data Use Letter against the ingrained policy.
        """
        if not self.vector_store:
            raise ValueError("FAISS vector store not found. Please ingest policies first.")
            
        # 1. Retrieve relevant policy chunks based on the user's document text
        # (We take a chunk of the user DUL to find relevant policies, or query general terms)
        # Using the whole DUL text as a query might be large, so we extract key themes.
        # For simplicity, we search for the top 5 most similar chunks to a summary/first chunk of the DUL
        
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        # Take the first ~1000 chars for retrieval context to avoid huge embedding requests
        query_context = user_dul_text[:1000]
        retrieved_docs = retriever.invoke(query_context)
        
        # 2. Format retrieved context with metadata
        context_str = ""
        for i, doc in enumerate(retrieved_docs):
            page_num = doc.metadata.get('Page Number', 'Unknown')
            clause_id = doc.metadata.get('Clause ID', 'Unknown')
            section = doc.metadata.get('Section Header', 'Unknown')
            
            context_str += f"--- Policy Excerpt {i+1} ---\n"
            context_str += f"[Page: {page_num} | Section: {section} | Clause ID: {clause_id}]\n"
            context_str += f"{doc.page_content}\n\n"
            
        # 3. Create prompt instructing the LLM to output structured JSON matching ComplianceReport
        prompt = PromptTemplate(
            template="""
            You are an expert compliance officer analyzing a user's Data Use Letter (DUL) against standard GA4GH policies.
            
            Your goal is to determine if the DUL complies with the policies, identify any conflicts or gaps, 
            and map the text to appropriate machine-readable Data Use Ontology (DUO) tags.
            
            --- STANDARD POLICIES CONTEXT ---
            {context}
            
            --- USER DUL PROPOSAL ---
            {dul_text}
            
            Analyze the DUL. If it violates or omits requirements from the policies, flag it.
            Extract EXACT citations (Page Number, Section, Clause ID, and text snippet) from the policies to prove your points.
            Evaluate the overall status as 'Compliant', 'Non-Compliant', or 'Needs Review'.
            Map the text to DUO tags (e.g. DUO:0000042 General Research Use, DUO:0000006 Health/Medical/Biomedical use).
            
            Provide your response entirely in the requested JSON format.
            """,
            input_variables=["context", "dul_text"]
        )

        
        # Use Langchain's with_structured_output to get Pydantic directly
        structured_llm = self.llm.with_structured_output(ComplianceReport)
        
        chain = prompt | structured_llm
        
        print("Invoking Groq LLM for compliance verification...")
        try:
            report = chain.invoke({"context": context_str, "dul_text": user_dul_text})
            return report
        except Exception as e:
            print(f"Error during LLM invocation: {e}")
            # Fallback for demonstration
            return ComplianceReport(
                status="Needs Review",
                findings=[],
                summary=f"Failed to verify due to LLM error: {str(e)}",
                primary_duo_tags=[]
            )

if __name__ == "__main__":
    print("Verification script working.")
