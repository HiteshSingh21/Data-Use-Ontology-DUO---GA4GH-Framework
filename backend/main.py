import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile

from .models import ComplianceReport
from .verification import ComplianceVerifier
from .ingestion import IngestionEngine

app = FastAPI(title="Compliance Verifier API", version="1.0.0")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize verifier
vector_store_path = os.path.join(os.path.dirname(__file__), "../data/faiss_index")
try:
    verifier = ComplianceVerifier(vector_store_path=vector_store_path)
except Exception as e:
    print(f"Warning: Could not initialize verifier, maybe missing API keys: {e}")
    verifier = None

@app.post("/verify", response_model=ComplianceReport)
async def verify_dul(file: UploadFile = File(...)):
    """
    Upload a DUL (PDF) to be verified against the ingested policies.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    try:
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            
        # Extract text from PDF for verification using pypdf
        import pypdf
        extracted_text = ""
        with open(tmp_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
        
        # Clean up
        os.unlink(tmp_path)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the PDF")
            
        print(f"Extracted {len(extracted_text)} characters from DUL")
        
        if not verifier:
            raise HTTPException(status_code=500, detail="Verifier not initialized correctly (check API keys)")
            
        # Perform verification
        report = verifier.verify_document(extracted_text)
        return report

    except Exception as e:
        print(f"Error during verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest_policy")
async def ingest_policy(file: UploadFile = File(...)):
    """
    Admin endpoint to upload a new base policy to the FAISS index.
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "../data")
        os.makedirs(data_dir, exist_ok=True)
        
        file_path = os.path.join(data_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Re-ingest
        ingestion_engine = IngestionEngine(vector_store_path=vector_store_path)
        ingestion_engine.ingest_documents([file_path])
        
        # Re-initialize
        global verifier
        verifier = ComplianceVerifier(vector_store_path=vector_store_path)
        
        return {"status": "success", "message": f"Successfully ingested {file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
