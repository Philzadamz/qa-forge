from pydantic import BaseModel


class FeatureOut(BaseModel):
    key: str
    label: str
    description: str
    enabled: bool


class FeaturePatch(BaseModel):
    enabled: bool
