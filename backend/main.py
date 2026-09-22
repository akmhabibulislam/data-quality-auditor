import os
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Response, Query, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.models import AuditReport, AuditConfig
from backend.engine.ingestion import read_dataset_to_polars
from backend.engine.profiler import profile_dataset
from backend.export.reporter import generate_json_report, generate_html_report, generate_pdf_report

app = FastAPI(
    title="Data Quality Auditor Enterprise API",
    description="Vectorized data quality profiling, anomaly detection, statistical inference, and remediation engine.",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_AUDIT_REPORT: Optional[AuditReport] = None

@app.post("/api/audit", response_model=AuditReport)
async def audit_dataset(
    file: UploadFile = File(...),
    iqr_multiplier: float = Form(default=1.5),
    zscore_threshold: float = Form(default=3.0)
):
    """
    Ingest dataset (CSV, TSV, JSON, Parquet up to 500MB) with configurable anomaly thresholds.
    """
    global LAST_AUDIT_REPORT
    try:
        content = await file.read()
        file_size = len(content)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        config = AuditConfig(iqr_multiplier=iqr_multiplier, zscore_threshold=zscore_threshold)
        df, detected_format = read_dataset_to_polars(content, file.filename or "dataset.csv")
        
        if df.height == 0:
            raise HTTPException(status_code=400, detail="The dataset contains zero valid rows.")

        report = profile_dataset(
            df=df,
            filename=file.filename or "dataset.csv",
            file_size_bytes=file_size,
            file_format=detected_format,
            config=config
        )
        LAST_AUDIT_REPORT = report
        return report

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profiling failed: {str(e)}")

@app.post("/api/audit/sample/{sample_name}", response_model=AuditReport)
async def audit_sample_dataset(
    sample_name: str,
    iqr_multiplier: float = Query(default=1.5),
    zscore_threshold: float = Query(default=3.0)
):
    """Run audit against bundled benchmark datasets with customizable thresholds."""
    global LAST_AUDIT_REPORT
    sample_path = os.path.join(os.path.dirname(__file__), "..", "data", "samples", f"{sample_name}.csv")
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail=f"Sample dataset '{sample_name}' not found.")

    with open(sample_path, "rb") as f:
        content = f.read()

    config = AuditConfig(iqr_multiplier=iqr_multiplier, zscore_threshold=zscore_threshold)
    df, detected_format = read_dataset_to_polars(content, f"{sample_name}.csv")
    
    report = profile_dataset(
        df=df,
        filename=f"{sample_name}.csv",
        file_size_bytes=len(content),
        file_format=detected_format,
        config=config
    )
    LAST_AUDIT_REPORT = report
    return report

@app.post("/api/export/json")
async def export_json(report: Optional[AuditReport] = None):
    active_report = report or LAST_AUDIT_REPORT
    if not active_report:
        raise HTTPException(status_code=400, detail="No audit report available to export.")
    
    json_data = generate_json_report(active_report)
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="audit_{active_report.summary.filename}.json"'}
    )

@app.post("/api/export/html")
async def export_html(report: Optional[AuditReport] = None):
    active_report = report or LAST_AUDIT_REPORT
    if not active_report:
        raise HTTPException(status_code=400, detail="No audit report available to export.")
    
    html_data = generate_html_report(active_report)
    return Response(
        content=html_data,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="audit_{active_report.summary.filename}.html"'}
    )

@app.post("/api/export/pdf")
async def export_pdf(report: Optional[AuditReport] = None):
    active_report = report or LAST_AUDIT_REPORT
    if not active_report:
        raise HTTPException(status_code=400, detail="No audit report available to export.")
    
    try:
        pdf_bytes = generate_pdf_report(active_report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="audit_{active_report.summary.filename}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

# Mount static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/", response_class=FileResponse)
async def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Data Quality Auditor API is Active</h1>", status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
