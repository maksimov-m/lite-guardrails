from pydantic import BaseModel


# --- PII -------------------------------------------------------------------
class PiiRuleIn(BaseModel):
    type: str
    regex: str
    enabled: bool = True


class PiiRulePatch(BaseModel):
    type: str | None = None
    regex: str | None = None
    enabled: bool | None = None


# --- NSFW ------------------------------------------------------------------
class NsfwDictIn(BaseModel):
    name: str
    text: str = ""


class NsfwDictPatch(BaseModel):
    name: str | None = None
    text: str | None = None
    enabled: bool | None = None


# --- relevant --------------------------------------------------------------
class RelevantIn(BaseModel):
    type: str
    text: str = ""


class RelevantPatch(BaseModel):
    type: str | None = None
    text: str | None = None
    enabled: bool | None = None


# --- API-ключи -------------------------------------------------------------
class ApiKeyIn(BaseModel):
    name: str
    rate_limit_per_min: int | None = None  # None — глобальный дефолт


class ApiKeyPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    rate_limit_per_min: int | None = None
