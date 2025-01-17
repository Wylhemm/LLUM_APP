from typing import Optional
import httpx
from pydantic import BaseModel, Field
from enum import Enum
from .constants import POCKETBASE_BASE_URL

class Operation(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"

class UserCredits(BaseModel):
    credits: int = Field(..., description="Number of credits for the user")

async def get_user_credits(user_id: str) -> UserCredits:
    """
    Get the remaining credits for a user from PocketBase.
    
    Args:
        user_id: The ID of the user to check
        
    Returns:
        UserCredits: Pydantic model containing the number of credits
        
    Raises:
        HTTPException: If the request fails or user is not found
    """
    url = f"{POCKETBASE_BASE_URL}users/records/{user_id}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        
        user_data = response.json()
        return UserCredits(credits=user_data["credits"])

async def update_user_credits(user_id: str, operation: Operation, value: int) -> UserCredits:
    """
    Update a user's credits using the specified operation.
    
    Args:
        user_id: The ID of the user to update
        operation: The operation to perform (add, subtract, multiply, divide)
        value: The value to use in the operation
        
    Returns:
        UserCredits: Pydantic model containing the updated number of credits
        
    Raises:
        HTTPException: If the request fails or user is not found
        ValueError: If trying to divide by zero
    """
    # First get current credits
    current_credits = await get_user_credits(user_id)
    
    # Calculate new credits based on operation
    if operation == Operation.ADD:
        new_credits = current_credits.credits + value
    elif operation == Operation.SUBTRACT:
        new_credits = current_credits.credits - value
    elif operation == Operation.MULTIPLY:
        new_credits = current_credits.credits * value
    elif operation == Operation.DIVIDE:
        if value == 0:
            raise ValueError("Cannot divide by zero")
        new_credits = current_credits.credits // value
    
    # Update credits in PocketBase
    url = f"{POCKETBASE_BASE_URL}users/records/{user_id}"
    
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, json={"credits": new_credits})
        response.raise_for_status()
        
        updated_data = response.json()
        return UserCredits(credits=updated_data["credits"])

async def get_user_name(user_id: str) -> str:
    """
    Get the name of a user from PocketBase.
    
    Args:
        user_id: The ID of the user to check
        
    Returns:
        str: The name of the user
        
    Raises:
        HTTPException: If the request fails or user is not found
    """
    url = f"{POCKETBASE_BASE_URL}users/records/{user_id}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        
        user_data = response.json()
        return user_data["name"]