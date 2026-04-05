import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_ISIN_RE = re.compile(r"^IN[A-Z0-9]{10}$")


class Goal(BaseModel):
    id: str = ""
    name: str
    target_amount: float = Field(ge=0)
    target_year: int = Field(ge=2020, le=2100)


class PolicyUpdate(BaseModel):
    goals: list[Goal] | None = None
    max_drawdown_pct: float | None = Field(default=None, ge=0, le=100)
    monthly_income: float | None = Field(default=None, ge=0)
    fixed_expenses: float | None = Field(default=None, ge=0)
    min_bank_buffer: float | None = Field(default=None, ge=0)
    current_account_balance: float | None = Field(default=None, ge=0)
    risk_profile: str | None = Field(default=None)
    autopilot: bool | None = None


class StockHolding(BaseModel):
    ticker: str
    qty: float = Field(gt=0)
    buy_price: float = Field(ge=0)
    buy_date: str | None = None


class MFHolding(BaseModel):
    """Mutual fund: provide ISIN (preferred for NAV) and/or AMFI scheme code."""

    isin: str | None = None
    amfi_code: str = ""
    units: float = Field(gt=0)
    buy_nav: float = Field(ge=0)
    buy_date: str | None = None

    @model_validator(mode="after")
    def require_isin_or_amfi(self):
        isin = (self.isin or "").strip().upper()
        code = (self.amfi_code or "").strip()
        if not isin and not code:
            raise ValueError("Mutual fund holding needs isin or amfi_code.")
        if isin and not _ISIN_RE.match(isin):
            raise ValueError("Invalid ISIN format (expected 12 chars, e.g. INF247L01445).")
        self.isin = isin or None
        self.amfi_code = code
        return self


class PortfolioUpdate(BaseModel):
    cash: float | None = Field(default=None, ge=0)
    stocks: list[StockHolding] | None = None
    mutual_funds: list[MFHolding] | None = None


class CASPayload(BaseModel):
    """Normalized client-parsed CAS JSON."""

    cash: float = 0
    stocks: list[StockHolding] = Field(default_factory=list)
    mutual_funds: list[MFHolding] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=24)
    is_demo: bool | None = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        digits = "".join(c for c in str(v) if c.isdigit())
        if len(digits) < 10:
            raise ValueError("Phone must have at least 10 digits.")
        if len(digits) == 10:
            return "+91" + digits
        if len(digits) <= 15:
            return "+" + digits
        raise ValueError("Phone number is too long.")


class SimulateTradeRequest(BaseModel):
    proposal_id: str | None = None
    symbol: str
    asset_type: Literal["stock", "mutual_fund"] = "stock"
    side: Literal["buy", "sell"] = "buy"
    qty: float = Field(gt=0)
    price: float = Field(gt=0)


class ProposalDecision(BaseModel):
    proposal_id: str
    approve: bool


class DemoSalaryRequest(BaseModel):
    amount_inr: float = Field(gt=0)


class DemoCrashRequest(BaseModel):
    drop_pct: float = Field(default=20, ge=1, le=90)

