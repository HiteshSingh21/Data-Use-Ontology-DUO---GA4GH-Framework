import os
from ingestion import IngestionEngine

def main():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data")
    vector_store_path = os.path.join(data_dir, "faiss_index")
    ga4gh_path = os.path.join(data_dir, "GA4GH_Framework.pdf")
    nih_path = os.path.join(data_dir, "NIH_GDS_Policy.pdf")
    
    paths_to_ingest = []
    if os.path.exists(ga4gh_path):
        paths_to_ingest.append(ga4gh_path)
        print(f"Found: {ga4gh_path}")
    else:
        print(f"File not found: {ga4gh_path}")
        
    if os.path.exists(nih_path):
        paths_to_ingest.append(nih_path)
        print(f"Found: {nih_path}")
    else:
        print(f"File not found: {nih_path}")
        
    if paths_to_ingest:
        engine = IngestionEngine(data_dir=data_dir, vector_store_path=vector_store_path)
        engine.ingest_documents(paths_to_ingest)
        print("Index build complete!")
    else:
        print("No documents to ingest.")

if __name__ == "__main__":
    main()
