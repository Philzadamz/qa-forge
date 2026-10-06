import uuid
from datetime import datetime

from pydantic import BaseModel


class RecentRunOut(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID | None
    suite_name: str | None
    target: str
    status: str
    total: int
    passed: int
    failed: int
    created_at: datetime


class FeatureUsageOut(BaseModel):
    feature: str
    prompt_tokens: int
    completion_tokens: int


class UsageSummaryOut(BaseModel):
    window_days: int
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float
    by_feature: list[FeatureUsageOut]


class DashboardOut(BaseModel):
    project_count: int
    suite_count: int
    run_count_30_days: int
    pass_rate_30_days: float | None
    recent_runs: list[RecentRunOut]
    usage: UsageSummaryOut
