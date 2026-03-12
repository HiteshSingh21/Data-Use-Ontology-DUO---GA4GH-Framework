import os
import re
from typing import List
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

class IngestionEngine:
    def __init__(self, data_dir: str = "../data", vector_store_path: str = "../data/faiss_index"):
        self.data_dir = data_dir
        self.vector_store_path = vector_store_path
        # Using a fast, local embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def extract_metadata(self, text: str) -> dict:
        """
        Heuristic to extract 'Section Header' and 'Clause ID' from text block.
        """
        metadata = {}
        # Naive approach: look for short, capitalized lines or lines like "1.1 Something"
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Look for Clause ID like "Article 1" or "1.1"
            clause_match = re.search(r"^(Article\s+\d+|[A-Z0-9]+\.\d+)", line, re.IGNORECASE)
            if clause_match and "Clause ID" not in metadata:
                metadata["Clause ID"] = clause_match.group(1)
            
            # Look for Section Header (short, mostly caps, or title case)
            if len(line) < 60 and line.istitle() and "Section Header" not in metadata:
                metadata["Section Header"] = line
                
        return metadata

    def load_and_chunk_pdf(self, file_path: str, document_type: str = "Policy") -> List[Document]:
        """
        Loads PDF, chunk it, and attaches metadata (Page Number, Section Header, Clause ID).
        """
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        
        chunks = self.text_splitter.split_documents(docs)
        
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            # Page number is often already in chunk.metadata from PyPDFLoader as 'page'
            page_num = chunk.metadata.get("page", 0) + 1 
            
            # Extract additional metadata
            extracted_metadata = self.extract_metadata(chunk.page_content)
            
            # Combine all metadata
            chunk.metadata.update({
                "Document Type": document_type,
                "Page Number": page_num,
                "Chunk ID": i,
                **extracted_metadata
            })
            enriched_chunks.append(chunk)
            
        return enriched_chunks

    def ingest_documents(self, file_paths: List[str]):
        """
        Ingests a list of document paths and saves them to a FAISS vector store.
        """
        all_chunks = []
        for path in file_paths:
            print(f"Loading {path}...")
            # Simple assumption: file name might indicate type
            doc_type = "Policy" if "policy" in path.lower() or "toolkit" in path.lower() else "DUL"
            chunks = self.load_and_chunk_pdf(path, document_type=doc_type)
            all_chunks.extend(chunks)
            
        print(f"Creating FAISS index with {len(all_chunks)} chunks...")
        vector_store = FAISS.from_documents(all_chunks, self.embeddings)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.vector_store_path), exist_ok=True)
        vector_store.save_local(self.vector_store_path)
        print(f"Vector store saved to {self.vector_store_path}")
        return vector_store

    def load_vector_store(self):
        """
        Loads the existing FAISS vector store.
        """
        if os.path.exists(self.vector_store_path):
            return FAISS.load_local(
                self.vector_store_path, 
                self.embeddings,
                allow_dangerous_deserialization=True # Required for loading local FAISS
            )
        return None

if __name__ == "__main__":
    # Simple test
    print("Ingestion engine script working.")
