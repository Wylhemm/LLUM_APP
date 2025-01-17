from fastapi import APIRouter, HTTPException, Request, Response, Body
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import logging
import traceback
from utils.constants import POCKETBASE_BASE_URL

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)
logger.info("Logging system initialized")

router = APIRouter()
templates = Jinja2Templates(directory=".")

class LoginRequest(BaseModel):
    email: str
    password: str

@router.get("/login", response_class=HTMLResponse)
async def get_login():
    with open("login.html") as f:
        return HTMLResponse(content=f.read())

@router.post("/api/login", response_model=None)
async def login_endpoint(request: Request, login_request: LoginRequest = Body(...), response: Response = None):
    logger.info("Login request received")
    logger.debug(f"Request headers: {dict(request.headers)}")
    try:
        body = await request.body()
        logger.debug(f"Raw request body: {body.decode()}")
    except Exception as e:
        logger.error(f"Error reading request body: {str(e)}")
    logger.debug(f"Parsed request data: {login_request.dict()}")
    
    pb_url = f"{POCKETBASE_BASE_URL}users/auth-with-password"
    logger.debug(f"PocketBase URL: {pb_url}")
    
    # Validate email format
    if "@" not in login_request.email or "." not in login_request.email.split("@")[1]:
        logger.warning(f"Invalid email format: {login_request.email}")
        response.status_code = 400
        return {"detail": "Invalid email format"}
    
    # Validate password length
    if len(login_request.password) < 8:
        logger.warning("Password too short")
        response.status_code = 400
        return {"detail": "Password must be at least 8 characters"}
    
    try:
        logger.info("Creating HTTP client for PocketBase request")
        async with httpx.AsyncClient() as client:
            logger.info("Sending request to PocketBase")
            pb_response = await client.post(
                pb_url,
                json={"identity": login_request.email, "password": login_request.password}
            )
            logger.debug(f"PocketBase response status: {pb_response.status_code}")
            
            if pb_response.status_code == 200:
                logger.info("PocketBase authentication successful")
                token_data = pb_response.json()
                logger.debug("Setting authentication cookie")
                
                response.set_cookie(
                    key="llum_login",
                    value=token_data["token"],
                    httponly=True,
                    secure=False,  # Set to True in production with HTTPS
                    samesite="lax",
                    max_age=7 * 24 * 60 * 60  # 7 days
                )
                logger.info("Login successful, returning response")
                return {"status": "success"}
            else:
                logger.warning(f"PocketBase authentication failed: {pb_response.status_code}")
                response.status_code = pb_response.status_code
                error_detail = pb_response.text
                logger.error(f"PocketBase error response: {error_detail}")
                return {"detail": "Login failed"}
                
    except httpx.HTTPError as e:
        logger.error("HTTP error occurred during PocketBase request")
        logger.error(f"Error details: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        response.status_code = 500
        return {"detail": "Internal server error"}
    except Exception as e:
        logger.critical("Unexpected error occurred during login process")
        logger.error(f"Error details: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        response.status_code = 500
        return {"detail": "Internal server error"}
