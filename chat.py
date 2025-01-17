from fastapi import APIRouter, HTTPException, Cookie
from pydantic import BaseModel
from typing import Optional
import jwt
from openai import OpenAI
from utils.helpers import get_user_credits, update_user_credits, Operation, get_user_name
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

router = APIRouter()

OPENAI_API_KEY = "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"
ASSISTANT_ID = "asst_kLO3obUYX9riPf85igYJ8num"


class ChatMessage(BaseModel):
    message: str

@router.post('/chat')
async def chat_endpoint(
    chat_message: ChatMessage,
    llum_login: Optional[str] = Cookie(None)
):
    if not llum_login:
        raise HTTPException(status_code=401, detail="No authentication token provided")
    
    try:
        # Get user_id from the PocketBase token
        decoded_token = jwt.decode(llum_login, options={"verify_signature": False})
        user_id = decoded_token['id']
        
        # Check user credits
        user_credits = await get_user_credits(user_id)
        if user_credits.credits <= 0:
            raise HTTPException(status_code=403, detail="Insufficient credits")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Create thread
        thread = client.beta.threads.create()
        
        # Add user message
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=chat_message.message
        )
        
        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )
        
        # Wait for completion
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
        
        # Get the response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_response = messages.data[0].content[0].text.value
        
        # Deduct one credit
        updated_credits = await update_user_credits(user_id, Operation.SUBTRACT, 1)
        
        return {
            "response": assistant_response,
            "remaining_credits": updated_credits.credits
        }
        
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/user/credits')
async def check_user_credits(
    llum_login: str = Cookie(None)
):
    logging.info('Received request to check user credits.')
    if not llum_login:
        logging.warning('No authentication token provided.')
        raise HTTPException(status_code=401, detail="No authentication token provided")
    try:
        logging.info('Decoding JWT token.')
        decoded_token = jwt.decode(llum_login, options={"verify_signature": False})
        user_id = decoded_token['id']
        logging.info(f'Extracted user ID: {user_id}')
        user_credits = await get_user_credits(user_id)
        logging.info(f'User credits retrieved: {user_credits.credits}')
        return {
            "credits": user_credits.credits
        }
    except jwt.InvalidTokenError:
        logging.error('Invalid authentication token.', exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logging.error('An error occurred while checking user credits.', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/user/name')
async def get_user_name_endpoint(
    llum_login: str = Cookie(None)
):
    logging.info('Received request to get user name.')
    if not llum_login:
        logging.warning('No authentication token provided.')
        raise HTTPException(status_code=401, detail="No authentication token provided")
    try:
        logging.info('Decoding JWT token.')
        decoded_token = jwt.decode(llum_login, options={"verify_signature": False})
        user_id = decoded_token['id']
        logging.info(f'Extracted user ID: {user_id}')
        username = await get_user_name(user_id)
        logging.info(f'User name retrieved: {username}')
        return {
            "name": username
        }
    except jwt.InvalidTokenError:
        logging.error('Invalid authentication token.', exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logging.error('An error occurred while getting user name.', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
