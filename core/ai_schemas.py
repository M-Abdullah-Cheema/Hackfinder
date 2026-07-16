from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class ExtractedOpportunity(BaseModel):
    """The strict schema the LLM MUST adhere to when extracting data."""
    
    title: str = Field(description="The formal name of the event, hackathon, or job role.")
    category: Literal['Hackathon', 'Internship', 'Workshop', 'Job', 'Scholarship', 'Other'] = Field(
        description="Categorize the opportunity strictly into one of these options."
    )
    organization_name: str = Field(description="The university, company, or society hosting the event.")
    
    # Pydantic will automatically attempt to parse standard date strings into datetime objects
    application_deadline: Optional[datetime] = Field(
        default=None, 
        description="The final deadline to apply or register. Leave null if not mentioned."
    )
    registration_url: Optional[str] = Field(
        default=None, 
        description="The URL where a user can apply or register. E.g., forms.gle or website link."
    )
    is_remote: bool = Field(
        default=False, 
        description="True if the event/job is online or remote. False if physical/on-site."
    )