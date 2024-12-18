from pydantic import BaseModel

class ChatMessageInput(BaseModel):
    content: str