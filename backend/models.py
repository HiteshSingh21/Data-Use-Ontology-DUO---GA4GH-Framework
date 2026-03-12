from pydantic import BaseModel, Field
from typing import List, Optional

class DUOMapping(BaseModel):
    tag: str = Field(..., description="The Data Use Ontology tag, e.g., 'DUO:0000042' (General Research Use)")
    description: str = Field(..., description="Description of the tag")

class ClauseCitation(BaseModel):
    clause_id: Optional[str] = Field(None, description="The specific clause identifier, e.g., 'Article 1.1'")
    page_number: Optional[int] = Field(None, description="The page number from the regulatory document")
    section_header: Optional[str] = Field(None, description="The section header from the regulatory document")
    extracted_text: str = Field(..., description="The exact relevant text from the regulatory document")

class Finding(BaseModel):
    finding_type: str = Field(..., description="'Conflict' or 'Gap'")
    description: str = Field(..., description="Explanation of the conflict or missing information")
    severity: str = Field(..., description="'High', 'Medium', or 'Low'")
    mapped_duo_tags: List[DUOMapping] = Field([], description="Potential DUO mappings related to this finding")
    citations: List[ClauseCitation] = Field([], description="Exact citations from the referenced policy")

class ComplianceReport(BaseModel):
    status: str = Field(..., description="Overall status: 'Compliant', 'Non-Compliant', or 'Needs Review'")
    findings: List[Finding] = Field([], description="List of gaps or conflicts found")
    summary: str = Field(..., description="A 1-2 sentence high-level summary of the compliance check")
    primary_duo_tags: List[DUOMapping] = Field([], description="The primary data use tags interpreted from the DUL")
