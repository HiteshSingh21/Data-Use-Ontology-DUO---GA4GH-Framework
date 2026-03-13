import os
import re
import json
import pymupdf4llm
from typing import List
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

class IngestionEngine:
    def __init__(self, data_dir: str = "../data", vector_store_path: str = "../data/faiss_index"):
        self.data_dir = data_dir
        self.vector_store_path = vector_store_path
        self.metadata_store_path = os.path.join(self.data_dir, "metadata_store.json")
        # Using a fast, local embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def extract_metadata(self, text: str, header_metadata: dict) -> dict:
        metadata = {}
        combined_headers = " ".join([v for k, v in header_metadata.items() if k.startswith("Header")])
        clause_match = re.search(r"(Article\s+\d+|[A-Z0-9]+\.\d+|Section\s+\d+)", combined_headers + "\n" + text, re.IGNORECASE)
        if clause_match:
            metadata["Clause ID"] = clause_match.group(1)
        return metadata

    def load_and_chunk_pdf(self, file_path: str, document_type: str = "Policy") -> List[Document]:
        print(f"Parsing {file_path} with pymupdf4llm...")
        markdown_text = pymupdf4llm.to_markdown(file_path)
        
        md_docs = self.markdown_splitter.split_text(markdown_text)
        chunks = self.text_splitter.split_documents(md_docs)
        
        source_doc_name = os.path.basename(file_path)
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            header_str = " > ".join([v for k, v in chunk.metadata.items() if k.startswith("Header")])
            extracted = self.extract_metadata(chunk.page_content, chunk.metadata)
            
            chunk.metadata.update({
                "Document Type": document_type,
                "Source Document": source_doc_name,
                "Section Header": header_str if header_str else "General",
                "Chunk ID": f"{source_doc_name}_chunk_{i}",
                **extracted
            })
            enriched_chunks.append(chunk)
            
        return enriched_chunks

    def ingest_documents(self, file_paths: List[str]):
        all_chunks = []
        for path in file_paths:
            print(f"Loading {path}...")
            doc_type = "Policy" if "policy" in path.lower() or "toolkit" in path.lower() or "framework" in path.lower() else "DUL"
            chunks = self.load_and_chunk_pdf(path, document_type=doc_type)
            all_chunks.extend(chunks)
            
        print(f"Creating FAISS index with {len(all_chunks)} chunks...")
        vector_store = FAISS.from_documents(all_chunks, self.embeddings)
        
        metadata_store = {}
        for chunk in all_chunks:
            chunk_id = chunk.metadata.get("Chunk ID")
            metadata_store[chunk_id] = {
                "clause_id": chunk.metadata.get("Clause ID"),
                "section_header": chunk.metadata.get("Section Header"),
                "source_document": chunk.metadata.get("Source Document"),
                "text": chunk.page_content,
                "page_number": chunk.metadata.get("Page Number", 0) 
            }
            
        os.makedirs(os.path.dirname(self.vector_store_path), exist_ok=True)
        vector_store.save_local(self.vector_store_path)
        
        with open(self.metadata_store_path, "w") as f:
            json.dump(metadata_store, f, indent=2)
            
        print(f"Vector store saved to {self.vector_store_path}")
        print(f"Metadata store saved to {self.metadata_store_path}")
        return vector_store

    def load_vector_store(self):
        if os.path.exists(self.vector_store_path):
            return FAISS.load_local(
                self.vector_store_path, 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
        return None

