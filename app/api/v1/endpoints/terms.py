"""Terms and privacy policy endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_terms():
    """Get terms and conditions."""
    return {
        "title": "Terms of Service",
        "version": "1.0.0",
        "last_updated": "2025-01-01",
        "content": """
# Terms of Service

Welcome to AiGo. By using our service, you agree to these terms.

## 1. Acceptance of Terms
By accessing or using AiGo, you agree to be bound by these Terms of Service.

## 2. Use of Service
You agree to use the service only for lawful purposes and in accordance with these terms.

## 3. User Accounts
You are responsible for maintaining the confidentiality of your account credentials.

## 4. Privacy
Your use of AiGo is also governed by our Privacy Policy.

## 5. Intellectual Property
All content and materials available through AiGo are protected by intellectual property rights.

## 6. Limitation of Liability
AiGo shall not be liable for any indirect, incidental, or consequential damages.

## 7. Modifications
We reserve the right to modify these terms at any time. Continued use constitutes acceptance.

## 8. Contact
For questions about these terms, please contact us.
        """.strip(),
    }


@router.get("/privacy")
async def get_privacy_policy():
    """Get privacy policy."""
    return {
        "title": "Privacy Policy",
        "version": "1.0.0",
        "last_updated": "2025-01-01",
        "content": """
# Privacy Policy

This Privacy Policy describes how AiGo collects, uses, and protects your information.

## 1. Information We Collect
- Account information (email, name)
- Usage data and preferences
- Travel itinerary data you create

## 2. How We Use Your Information
- To provide and improve our services
- To personalize your experience
- To communicate with you about your account

## 3. Data Security
We implement appropriate security measures to protect your personal information.

## 4. Data Sharing
We do not sell your personal information. We may share data with service providers.

## 5. Your Rights
You have the right to access, correct, or delete your personal information.

## 6. Cookies
We use cookies to enhance your experience and analyze usage patterns.

## 7. Changes to This Policy
We may update this policy from time to time. We will notify you of significant changes.

## 8. Contact Us
For privacy-related questions, please contact our support team.
        """.strip(),
    }
