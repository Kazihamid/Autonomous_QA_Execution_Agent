from typing import Any, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.generator.core import generate_project, GeneratorError

router = APIRouter(prefix="/api/v1")

class GenerateRequest(BaseModel):
    scenarioId: str
    scenarioVersionId: str
    scenarioVersion: int = Field(ge=1)
    target: Literal["PLAYWRIGHT_PYTEST", "SELENIUM_TESTNG"]
    automationIr: dict[str, Any]
    generatorVersion: str = "0.3.2"
    configuration: dict[str, Any] = Field(default_factory=dict)

@router.post("/generate")
def generate(request: GenerateRequest):
    try:
        return generate_project(request.model_dump())
    except GeneratorError as ex:
        raise HTTPException(status_code=422, detail={"code": ex.code, "message": str(ex), "unsupported": ex.unsupported}) from ex
