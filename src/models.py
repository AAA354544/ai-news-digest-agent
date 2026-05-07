from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    url: str
