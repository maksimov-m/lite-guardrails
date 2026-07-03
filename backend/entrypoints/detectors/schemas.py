from pydantic import BaseModel, Field

MAX_BATCH = 1000


class TextIn(BaseModel):
    text: str = Field(..., examples=["привет, как дела?"])
    metadata: dict | None = Field(default=None, examples=[{"user_id": "42", "app": "support-bot"}])


class BatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH)


class AnonymizeIn(BaseModel):
    text: str = Field(..., examples=["почта ivan@example.com"])
    # deanonymize=true — сохранить mapping в Redis, чтобы потом восстановить текст
    # (возвращается id). По умолчанию false: Redis не трогаем, id=null.
    deanonymize: bool = False


class AnonymizeBatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=MAX_BATCH)
    deanonymize: bool = False


class DeanonymizeIn(BaseModel):
    id: str
    text: str


class DeanonymizeBatchIn(BaseModel):
    items: list[DeanonymizeIn] = Field(..., min_length=1, max_length=MAX_BATCH)
