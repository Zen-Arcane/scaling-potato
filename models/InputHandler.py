from pydantic import BaseModel
class UIInput(BaseModel):
    query: str
