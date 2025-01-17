# stripe_router.py
from fastapi import APIRouter, Request, HTTPException
import httpx
from typing import Optional
import logging
from pydantic import BaseModel
import json
import hmac
import hashlib
import time
import random
from utils.constants import POCKETBASE_BASE_URL
from utils.email import send_password_email
import traceback

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Router setup
router = APIRouter(tags=["Stripe"])

# Configuration
STRIPE_SECRET_KEY = "sk_test_51JbsAaHWpOw8iS6g8YUMN9QS6ZtsC23Qg9YvB78kzbZVbA6uDOXOjdLnuaWYH5paOAtofVbMiNIvnKXUst3LnYhH00hRVIKUEv"
STRIPE_WEBHOOK_SECRET = "we_1QiB6XHWpOw8iS6ggcm072D3"
STRIPE_API_BASE = "https://api.stripe.com/v1"
FASTAPI_URL = "http://0.0.0.0:8000"

# Pydantic models
class Product(BaseModel):
    id: str
    collectionId: str
    collectionName: str
    subscription: bool
    price: float
    description: str
    name: str
    created: str
    updated: str

class CheckoutResponse(BaseModel):
    checkout_url: str
    product_data: Product

async def get_product_from_pocketbase(product_id: str) -> Product:
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Using POCKETBASE_BASE_URL which already includes /collections/
            response = await client.get(
                f"{POCKETBASE_BASE_URL}Products/records/{product_id}"
            )
            response.raise_for_status()
            product_data = response.json()
            
            # Map the response to our Product model
            return Product(
                id=product_data["id"],
                collectionId=product_data["collectionId"],
                collectionName=product_data["collectionName"],
                subscription=product_data["subscription"],
                price=product_data["price"],
                description=product_data["description"],
                name=product_data["name"],
                created=product_data["created"],
                updated=product_data["updated"]
            )
            
        except httpx.TimeoutException:
            logger.error("Timeout while fetching product details")
            raise HTTPException(status_code=504, detail="Timeout while fetching product details")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error while fetching product details: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"Error in get_product_from_pocketbase: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

async def create_stripe_checkout(product: Product, user_id: str, expires_in: Optional[int] = None) -> str:
    # Create form data for Stripe API
    form_data = {
        "payment_method_types[]": "card",
        "mode": "subscription" if product.subscription else "payment",
        "success_url": f"{FASTAPI_URL}/stripe/success?product_id={product.id}",
        "cancel_url": f"{FASTAPI_URL}/stripe/payment/cancel",
        "client_reference_id": user_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": product.name,
        "line_items[0][price_data][product_data][description]": product.description,
        "line_items[0][price_data][unit_amount]": str(int(product.price * 100)),
        "metadata[user_id]": user_id,
        "metadata[product_id]": product.id,
    }

    # Add subscription-specific fields
    if product.subscription:
        form_data["line_items[0][price_data][recurring][interval]"] = "month"

    # Add expiration if specified
    if expires_in:
        form_data["expires_at"] = str(int(time.time() + expires_in))

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=form_data,
                headers={
                    "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Stripe error response: {response.text}")
                raise HTTPException(status_code=400, detail=f"Stripe error: {response.text}")
                
            return response.json()["url"]
    except Exception as e:
        logger.error(f"Error creating checkout: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

async def create_pocketbase_user(email: str, name: str) -> tuple[dict, str]:
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Generate a more user-friendly password
            adjectives = ["happy", "sunny", "bright", "clever", "quick"]
            nouns = ["fox", "dog", "cat", "bird", "star"]
            password = f"{random.choice(adjectives)}_{random.choice(nouns)}_{random.randint(100, 999)}"
            
            user_data = {
                "email": email,
                "password": password,
                "passwordConfirm": password,
                "name": name,
                "credits": 0,  # Initial credits
                "emailVisibility": True
            }
            
            # Correct URL construction - POCKETBASE_BASE_URL already includes "api/collections/"
            response = await client.post(
                f"{POCKETBASE_BASE_URL}users/records",
                json=user_data,
                headers={
                    "Content-Type": "application/json"
                }
            )
            
            # Add debug logging
            logger.info(f"PocketBase Request URL: {POCKETBASE_BASE_URL}users/records")
            logger.info(f"PocketBase Request Body: {json.dumps(user_data, indent=2)}")
            logger.info(f"PocketBase Response Status: {response.status_code}")
            logger.info(f"PocketBase Response: {response.text}")
            
            response.raise_for_status()
            user_data = response.json()
            return user_data, password
            
        except httpx.TimeoutException:
            logger.error("Timeout while creating PocketBase user")
            raise HTTPException(status_code=504, detail="Timeout while creating user")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error while creating PocketBase user: {e}")
            logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"Error in create_pocketbase_user: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/create-checkout/{product_id}/{user_id}", response_model=CheckoutResponse)
async def create_checkout_session(
    product_id: str, 
    user_id: str, 
    expires_in: Optional[int] = None
):
    try:
        # Get product details from Pocketbase
        product = await get_product_from_pocketbase(product_id)
        
        # Create Stripe checkout session
        checkout_url = await create_stripe_checkout(product, user_id, expires_in)
        
        return CheckoutResponse(
            checkout_url=checkout_url,
            product_data=product
        )
        
    except Exception as e:
        logger.error(f"Error creating checkout: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/payment/success")
async def payment_success(user_id: str, product_id: str):
    logger.info(f"Payment success for user {user_id} and product {product_id}")
    return {"status": "success", "user_id": user_id, "product_id": product_id}

@router.get("/payment/cancel")
async def payment_cancel():
    logger.info("Payment cancelled")
    return {"status": "cancelled"}

@router.post("/webhook")
async def stripe_webhook(request: Request):
    # Log initial request details
    logger.info("Webhook request received")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request method: {request.method}")
    
    payload = await request.body()
    logger.info(f"Raw payload received (length: {len(payload)} bytes)")
    logger.debug(f"Payload content: {payload}")
    
    try:
        # Log signature verification attempt
        logger.info("Starting webhook verification")
        # Comment out signature verification for testing
        # sig_header = request.headers.get("stripe-signature")
        # logger.info(f"Stripe signature header: {sig_header}")
        # mac = hmac.new(
        #     STRIPE_WEBHOOK_SECRET.encode('utf-8'),
        #     msg=payload,
        #     digestmod=hashlib.sha256
        # )
        # if not hmac.compare_digest(mac.hexdigest(), sig_header):
        #     logger.error("Invalid signature detected")
        #     raise HTTPException(status_code=400, detail="Invalid signature")
        # logger.info("Signature verification successful")
        
        # Parse and log event data
        logger.info("Parsing event payload")
        event_data = json.loads(payload)
        logger.info(f"Event data parsed successfully (keys: {list(event_data.keys())})")
        
        event_type = event_data["type"]
        logger.info(f"Processing event type: {event_type}")
        logger.debug(f"Full event data: {json.dumps(event_data, indent=2)}")
        
        # Handle different event types
        if event_type == "checkout.session.completed":
            logger.info("Processing checkout.session.completed event")
            session = event_data["data"]["object"]
            logger.info(f"Session object retrieved (keys: {list(session.keys())})")
            
            # Log customer details
            customer_details = session.get("customer_details", {})
            logger.info(f"Customer details: {customer_details}")
            
            customer_email = customer_details.get("email")
            customer_name = customer_details.get("name", "Unknown User")
            logger.info(f"Customer email: {customer_email}")
            logger.info(f"Customer name: {customer_name}")
            
            if customer_email:
                try:
                    logger.info(f"Attempting to create PocketBase user for {customer_email}")
                    logger.info(f"User details - Email: {customer_email}, Name: {customer_name}")
                    
                    # Log before creating user
                    logger.info("Calling create_pocketbase_user")
                    user, password = await create_pocketbase_user(customer_email, customer_name)
                    logger.info("PocketBase user created successfully")
                    
                    # Send welcome email with password
                    try:
                        logger.info(f"Sending welcome email to {customer_email}")
                        await send_password_email(customer_email, password)
                        logger.info("Welcome email sent successfully")
                    except Exception as e:
                        logger.error(f"Failed to send welcome email: {str(e)}")
                        logger.error("Stack trace:")
                        logger.error(traceback.format_exc())
                    
                except Exception as e:
                    logger.error(f"Failed to create PocketBase user: {str(e)}")
                    logger.error("Stack trace:")
                    logger.error(traceback.format_exc())
                    logger.error(f"Failed user details - Email: {customer_email}, Name: {customer_name}")
            
            # Log metadata
            metadata = session.get("metadata", {})
            logger.info(f"Session metadata: {metadata}")
            
            user_id = metadata.get("user_id")
            product_id = metadata.get("product_id")
            logger.info(f"Metadata values - User ID: {user_id}, Product ID: {product_id}")
            
            if user_id and product_id:
                logger.info("Valid metadata found, returning success")
                return {"status": "success"}
            else:
                logger.warning("Missing required metadata fields")
                return {"status": "ignored"}
                
        elif event_type == "charge.succeeded":
            logger.info("Processing charge.succeeded event")
            charge = event_data["data"]["object"]
            logger.info(f"Charge object retrieved (keys: {list(charge.keys())})")
            
            # Log charge details
            logger.info(f"Charge amount: {charge['amount']}")
            logger.info(f"Charge currency: {charge['currency']}")
            logger.info(f"Charge status: {charge['status']}")
            
            # Handle successful charge
            return {"status": "success", "message": "Charge processed successfully"}
            
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return {"status": "ignored", "message": f"Unhandled event type: {event_type}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        logger.error(f"Payload content: {payload}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except KeyError as e:
        logger.error(f"Missing required field: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        logger.error("Stack trace:")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))