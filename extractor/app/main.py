import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

# ✅ ABSOLUTE IMPORTS (REQUIRED ON VERCEL)
from extractor.app.extractor import extract_document
from extractor.app.db import save_doc_metadata, get_metadata, simple_search
from extractor.app.highlight import highlight_pdf

# ✅ Serverless-safe temp directories
UPLOADS = Path("/tmp/uploads")
OUTPUTS = Path("/tmp/outputs")
UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PDF Extraction Backend")

# ✅ CORS (safe for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Routes
# -------------------------

@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    doc_id = f"{Path(file.filename).stem}-{uuid.uuid4().hex[:8]}"
    pdf_path = UPLOADS / f"{doc_id}.pdf"

    # Save uploaded PDF
    pdf_path.write_bytes(await file.read())

    # Run extraction in threadpool
    result = await run_in_threadpool(
        extract_document,
        str(pdf_path),
        doc_id,
        OUTPUTS,
    )

    # Highlight PDF
    highlight_path = OUTPUTS / f"{doc_id}_highlighted.pdf"
    highlight_pdf(
        str(pdf_path),
        result["chunks"],
        str(highlight_path),
    )

    # Save metadata (non-background on serverless)
    save_doc_metadata(result)

    return {
        "doc_id": doc_id,
        "chunks_count": len(result["chunks"]),
    }


@app.get("/api/metadata/{doc_id}")
def metadata(doc_id: str):
    return get_metadata(doc_id)


@app.get("/api/search")
def search(q: str):
    return {"results": simple_search(q)}


@app.get("/api")
def root():
    return {"status": "running"}
