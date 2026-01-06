import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

app = FastAPI(title="PDF Extraction Backend")

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Startup (SAFE place for FS ops)
# -------------------------
@app.on_event("startup")
def startup():
    uploads = Path("/tmp/uploads")
    outputs = Path("/tmp/outputs")
    uploads.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

# -------------------------
# Health / Root
# -------------------------
@app.get("/api")
def root():
    return {"status": "running"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

# -------------------------
# Extract (lazy imports)
# -------------------------
@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    # ⬇️ IMPORT HEAVY CODE ONLY WHEN ENDPOINT IS HIT
    from extractor.app.extractor import extract_document
    from extractor.app.highlight import highlight_pdf
    from extractor.app.db import save_doc_metadata

    uploads = Path("/tmp/uploads")
    outputs = Path("/tmp/outputs")

    doc_id = f"{Path(file.filename).stem}-{uuid.uuid4().hex[:8]}"
    pdf_path = uploads / f"{doc_id}.pdf"

    pdf_path.write_bytes(await file.read())

    result = await run_in_threadpool(
        extract_document,
        str(pdf_path),
        doc_id,
        outputs,
    )

    highlight_path = outputs / f"{doc_id}_highlighted.pdf"
    highlight_pdf(
        str(pdf_path),
        result["chunks"],
        str(highlight_path),
    )

    save_doc_metadata(result)

    return {
        "doc_id": doc_id,
        "chunks_count": len(result["chunks"]),
    }

# -------------------------
# Metadata / Search
# -------------------------
@app.get("/api/metadata/{doc_id}")
def metadata(doc_id: str):
    from extractor.app.db import get_metadata
    return get_metadata(doc_id)

@app.get("/api/search")
def search(q: str):
    from extractor.app.db import simple_search
    return {"results": simple_search(q)}
