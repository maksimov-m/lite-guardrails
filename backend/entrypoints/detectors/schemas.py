from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.config import settings

MAX_BATCH = 1000

# Ограничение длины пользовательского текста. Значение берётся из settings
# (env MAX_TEXT_LENGTH) на старте процесса. Превышение → 422 (string_too_long)
# ещё до детекции: не пускаем большой ввод в regex/relevant (DoS + смягчение ReDoS).
BoundedText = Annotated[str, StringConstraints(max_length=settings.max_text_length)]


class TextIn(BaseModel):
    text: BoundedText = Field(..., examples=["привет, как дела?"])
    metadata: dict | None = Field(default=None, examples=[{"user_id": "42", "app": "support-bot"}])


class BatchIn(BaseModel):
    texts: list[BoundedText] = Field(..., min_length=1, max_length=MAX_BATCH)


class AnonymizeIn(BaseModel):
    text: BoundedText = Field(..., examples=["почта ivan@example.com"])
    # deanonymize=true — сохранить mapping в Redis, чтобы потом восстановить текст
    # (возвращается id). По умолчанию false: Redis не трогаем, id=null.
    deanonymize: bool = False


class AnonymizeBatchIn(BaseModel):
    texts: list[BoundedText] = Field(..., min_length=1, max_length=MAX_BATCH)
    deanonymize: bool = False


class DeanonymizeIn(BaseModel):
    id: str
    text: BoundedText


class DeanonymizeBatchIn(BaseModel):
    items: list[DeanonymizeIn] = Field(..., min_length=1, max_length=MAX_BATCH)
