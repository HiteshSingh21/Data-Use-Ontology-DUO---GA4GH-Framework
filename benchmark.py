import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.verification import ComplianceVerifier

def main():
    print("Running Citation Accuracy Benchmark...")
    vector_store_path = os.path.join(os.path.dirname(__file__), "data/faiss_index")
    verifier = ComplianceVerifier(vector_store_path=vector_store_path)
    
    scenarios = [
        "We are conducting a local cancer study with 50 patients.",
        "This is an international cardiovascular heart study involving 150 participants.",
        "We collected data for general research purposes from 200 subjects for an academic institution."
    ]
    
    total_findings_with_citations = 0
    grounded_findings = 0
    hallucinations = 0
    
    for i, dul in enumerate(scenarios):
        print(f"\nEvaluating Scenario {i+1}...")
        report = verifier.verify_document(dul)
        
        trace = "\n".join(report.reasoning_trace)
        if "Hallucinated citation detected" in trace:
            hallucinations += trace.count("Hallucinated citation detected")
            
        for f in report.findings:
            if f.citations:
                total_findings_with_citations += len(f.citations)
                grounded_findings += len(f.citations)
                
    accuracy = 1.0
    if (grounded_findings + hallucinations) > 0:
        accuracy = grounded_findings / (grounded_findings + hallucinations)
        
    print(f"\nBenchmark Results")
    print(f"Total scenarios tested: {len(scenarios)}")
    print(f"Total Grounded Citations Found: {grounded_findings}")
    print(f"Hallucinations Dropped: {hallucinations}")
    print(f"Citation Accuracy Score: {accuracy * 100:.1f}%")

if __name__ == "__main__":
    main()
