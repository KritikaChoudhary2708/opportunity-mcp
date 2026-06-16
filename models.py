""" The Opportunity models: our single, canonical shape for any job or gig, no matter which source it came from.
 Every normalizer in source/ will produce one of these. """

from pydantic import BaseModel, Field

class Opportunity(BaseModel):
          """One job or freelance listing, normalised to common schema"""
          id: str = Field(..., description = "Unique ID within its source")
          source: str = Field(..., description="Which board it came from, eg 'remoteok'")
          kind:  str = Field("job", description="'job' or 'freelance' or 'internship'")
          title: str = Field(..., description="Role or gig title")
          company: str = Field("", description="Employer or client name")
          location: str = Field("", description="Where the job is located, taken from the source")
          url: str = Field("", description="Apply / detail link")
          date: str = Field("", description="ISO date, YYYY-MM-DD")
          skills: list[str] = Field(default_factory=list, description="Tags / extracted skills")
          salary: str = Field("", description="Normalized salary range, may be empty")
          snippet: str = Field("", description="Short description excerpt")

          
