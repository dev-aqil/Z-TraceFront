from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_date: date = Field(description="Planned/actual sample collection date")
    product_category: str | None = Field(None, description="Product category as in the training data")
    establishment_id: str | None = Field(None, description="Establishment identifier; enables history features")
    metadata: dict[str, str | float | None] = Field(
        default_factory=dict, description="Extra pre-sampling features declared at training (meta_cat_/meta_num_)")
