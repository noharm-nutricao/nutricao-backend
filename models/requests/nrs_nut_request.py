from pydantic import BaseModel, Field, model_validator


class NrsNutRequest(BaseModel):
    apache_ii: int = Field(ge=0, le=71)
    sofa: int = Field(ge=0, le=24)

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_fields(cls, values):
        forbidden = {"nrs_nut"}
        present = forbidden & set(values.keys())
        if present:
            raise ValueError(
                f"Campo(s) não permitido(s) neste endpoint: {', '.join(present)}"
            )
        return values

