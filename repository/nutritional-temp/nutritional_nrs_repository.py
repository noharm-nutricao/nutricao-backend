from typing import Optional

from models.main import db
from models.temp_nutritional import NutricionalNrs

def get_nrs_assessment(nratendimento: int) -> Optional[NutricionalNrs]:
    return (
        db.session.query(NutricionalNrs)
        .filter(NutricionalNrs.nratendimento == nratendimento)
        .order_by(NutricionalNrs.updated_at.desc())
        .first()
    )
