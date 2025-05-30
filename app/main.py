import uvicorn
import logging
import sys
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

from app.core.config import settings
from app.api.routes import router as api_router
from app.rag.documents import process_pdf

app = FastAPI(title="EC2 Ubuntu")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

app.include_router(api_router, prefix="/api")

logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request}
    )

@app.post("/upload", response_class=HTMLResponse)
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "error": "Only PDF files are supported."}
        )
    
    try:
        os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)

        content = await file.read()
        if len(content) > settings.MAX_PDF_SIZE_MB * 1024 * 1024:
            return templates.TemplateResponse(
                "index.html", 
                {"request": request, "error": f"File is too large. Maximum size is {settings.MAX_PDF_SIZE_MB}MB."}
            )
            
        if not content:
            return templates.TemplateResponse(
                "index.html", 
                {"request": request, "error": "Uploaded file is empty."}
            )

        file_path = os.path.join(settings.PDF_STORAGE_PATH, file.filename)
        with open(file_path, "wb") as f:
            f.write(content)

        result = process_pdf(file_path)
        
        if result["success"]:
            return templates.TemplateResponse(
                "index.html", 
                {"request": request, "message": "PDF uploaded and processed successfully!"}
            )
        else:
            error = result.get("error", "Unknown error")
            return templates.TemplateResponse(
                "index.html", 
                {"request": request, "error": f"Error processing PDF: {error}"}
            )
            
    except Exception as e:
        logger.exception(f"Error handling PDF upload: {str(e)}")
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "error": f"Error uploading PDF: {str(e)}"}
        )


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions and return a structured response"""
    logger.error(f"HTTP error: {exc.status_code} - {exc.detail}")
    return templates.TemplateResponse(
        "error.html", 
        {
            "request": request, 
            "status_code": exc.status_code, 
            "detail": exc.detail
        },
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions and log them properly"""
    logger.exception(f"Unhandled exception: {str(exc)}")
    return templates.TemplateResponse(
        "error.html", 
        {
            "request": request, 
            "status_code": 500, 
            "detail": "Internal server error. Please try again later."
        },
        status_code=500
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0",
        port=8000,
        log_level="info",
        log_config=None,
        reload=True
    )
