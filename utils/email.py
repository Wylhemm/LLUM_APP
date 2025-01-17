import os
import resend
from .constants import RESEND_API_KEY

resend.api_key = RESEND_API_KEY

def send_password_email(email: str, password: str) -> None:
    """Send an email with the generated password to the user"""
    try:
        params = {
            "from": "Arata App <contact@arata-app.com>",
            "to": [email],
            "subject": "You're In!",
            "html": f"""
                <p>Hi there!</p>
                <p>A warm welcome to Arata! We're beyond excited to have you join our community.</p>
                <p>Your account is all set up and ready to go.</p>
                <p>To get started, we've created a temporary password for you: <strong>{password}</strong></p>
                <p>When you log in, be sure to update your password to something that's all yours.</p>
                <p>If you have any questions or need a helping hand, our team is always here to support you.</p>
                <p>Thanks for choosing Arata, and happy exploring!</p>
            """
        }
        
        email = resend.Emails.send(params)
        return email
    except Exception as e:
        raise Exception(f"Failed to send email: {str(e)}")