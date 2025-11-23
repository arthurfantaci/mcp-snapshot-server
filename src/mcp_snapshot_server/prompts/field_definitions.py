"""Field definitions for elicitation of missing information.

This module defines the fields that can be elicited from users
when critical information is missing from transcript analysis.
"""

from typing import Any, Optional

# Field definitions with metadata for elicitation
FIELD_DEFINITIONS: dict[str, dict[str, Any]] = {
    "company_name": {
        "description": "Full legal name of the customer company",
        "type": "string",
        "example": "Acme Corporation",
        "validation": r"^[A-Za-z0-9\s\.,&'-]{2,100}$",
    },
    "industry": {
        "description": "Primary industry or sector",
        "type": "string",
        "example": "Financial Services, Healthcare, Manufacturing",
        "validation": r"^[A-Za-z\s,]{2,50}$",
    },
    "location": {
        "description": "Primary location (City, State/Province, Country)",
        "type": "string",
        "example": "San Francisco, California, USA",
        "validation": None,
    },
    "primary_contact": {
        "description": "Name of primary customer contact",
        "type": "string",
        "example": "John Smith",
        "validation": r"^[A-Za-z\s\.-]{2,50}$",
    },
    "contact_position": {
        "description": "Position/title of primary contact",
        "type": "string",
        "example": "Chief Technology Officer",
        "validation": None,
    },
    "contact_email": {
        "description": "Email address of primary contact",
        "type": "string",
        "example": "john.smith@acme.com",
        "validation": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    },
    "start_date": {
        "description": "Project start date (YYYY-MM-DD)",
        "type": "date",
        "example": "2024-07-14",
        "validation": r"^\d{4}-\d{2}-\d{2}$",
    },
    "completion_date": {
        "description": "Project completion date (YYYY-MM-DD)",
        "type": "date",
        "example": "2024-12-15",
        "validation": r"^\d{4}-\d{2}-\d{2}$",
    },
    "product_name": {
        "description": "Name of product or service implemented",
        "type": "string",
        "example": "Enterprise Cloud Platform",
        "validation": None,
    },
    "cost_savings": {
        "description": "Cost savings amount with currency",
        "type": "string",
        "example": "$250,000 annually",
        "validation": None,
    },
    "revenue_increase": {
        "description": "Revenue increase amount or percentage",
        "type": "string",
        "example": "$500,000 or 15% increase",
        "validation": None,
    },
    "roi_percentage": {
        "description": "Return on investment percentage",
        "type": "string",
        "example": "150% over 18 months",
        "validation": None,
    },
    "user_count": {
        "description": "Number of users/seats",
        "type": "number",
        "example": "500 users",
        "validation": r"^\d+$",
    },
    "adoption_rate": {
        "description": "User adoption rate percentage",
        "type": "string",
        "example": "95% within 3 months",
        "validation": None,
    },
    "efficiency_improvement": {
        "description": "Efficiency improvement percentage or description",
        "type": "string",
        "example": "40% reduction in processing time",
        "validation": None,
    },
}

# Define which fields are required for each section
REQUIRED_FIELDS: dict[str, list[str]] = {
    "Customer Information": ["company_name", "industry"],
    "Background": [],  # No absolutely required fields
    "Solution": [],  # Product name helpful but not required
    "Engagement Details": ["start_date"],
    "Results and Achievements": [],  # Metrics helpful but not required
    "Adoption and Usage": [],  # Usage stats helpful but not required
    "Financial Impact": [],  # Financial figures helpful but not required
    "Long-Term Impact": [],  # Strategic info helpful but not required
    "Visuals": [],  # No required fields
    "Additional Commentary": [],  # No required fields
    "Executive Summary": [],  # Generated from other sections
}

# Define optional but valuable fields for each section
VALUABLE_FIELDS: dict[str, list[str]] = {
    "Customer Information": ["location", "primary_contact", "contact_position"],
    "Background": [],
    "Solution": ["product_name"],
    "Engagement Details": ["completion_date"],
    "Results and Achievements": [
        "efficiency_improvement",
    ],
    "Adoption and Usage": ["user_count", "adoption_rate"],
    "Financial Impact": ["cost_savings", "revenue_increase", "roi_percentage"],
    "Long-Term Impact": [],
    "Visuals": [],
    "Additional Commentary": [],
}


def get_field_info(field_name: str) -> Optional[dict[str, Any]]:
    """Get information about a specific field.

    Args:
        field_name: Name of the field

    Returns:
        Field information dictionary or None if not found
    """
    return FIELD_DEFINITIONS.get(field_name)


def get_required_fields(section_name: str) -> list[str]:
    """Get list of required fields for a section.

    Args:
        section_name: Name of the section

    Returns:
        List of required field names
    """
    return REQUIRED_FIELDS.get(section_name, [])


def get_valuable_fields(section_name: str) -> list[str]:
    """Get list of valuable (but optional) fields for a section.

    Args:
        section_name: Name of the section

    Returns:
        List of valuable field names
    """
    return VALUABLE_FIELDS.get(section_name, [])


def is_field_required(section_name: str, field_name: str) -> bool:
    """Check if a field is required for a section.

    Args:
        section_name: Name of the section
        field_name: Name of the field

    Returns:
        True if field is required, False otherwise
    """
    required = REQUIRED_FIELDS.get(section_name, [])
    return field_name in required
