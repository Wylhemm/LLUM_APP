from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from chat import router as chat_router
from login import router as login_router
from stripe import router as stripe_router
import os
import httpx
from utils.constants import POCKETBASE_BASE_URL

async def check_auth(request: Request):
    if not request.cookies.get("llum_login"):
        return RedirectResponse(url="/login")
    return None

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates and static files
templates = Jinja2Templates(directory=".")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(chat_router, prefix='/api')
app.include_router(login_router, prefix="")
app.include_router(stripe_router)

@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/ebook", response_class=HTMLResponse)
async def get_pdf_viewer(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("book.html", {"request": request})

@app.get("/audiobook", response_class=HTMLResponse)
async def get_audiobook(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("audiobook.html", {"request": request})

@app.get("/self-esteem-test", response_class=HTMLResponse)
async def get_self_esteem_test(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("self-steem-test.html", {"request": request})

@app.get("/codependency-test", response_class=HTMLResponse)
async def get_codependency_test(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("codependency-test.html", {"request": request})

@app.get("/workbook", response_class=HTMLResponse)
async def get_workbook(request: Request, auth_check = Depends(check_auth)):
    if auth_check:
        return auth_check
    return templates.TemplateResponse("workbook.html", {"request": request})

@app.get("/stripe/success")
async def stripe_success(request: Request, product_id: str):
    # Fetch product details from PocketBase
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{POCKETBASE_BASE_URL}Products/records/{product_id}"
            )
            response.raise_for_status()
            product_data = response.json()
            product_name = product_data["name"]
            
            return templates.TemplateResponse(
                "success.html",
                {
                    "request": request,
                    "product_name": product_name
                }
            )
    except Exception as e:
        return HTMLResponse(content=f"Error fetching product details: {str(e)}", status_code=500)

# Catch-all route for any HTML file
@app.get("/{filename}.html", response_class=HTMLResponse)
async def get_html_file(filename: str, request: Request):
    try:
        return templates.TemplateResponse(f"{filename}.html", {"request": request})
    except Exception:
        return HTMLResponse(content="Page not found", status_code=404)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host='0.0.0.0', port=8000, reload=True)
