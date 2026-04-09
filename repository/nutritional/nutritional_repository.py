"""Nutritional repository.

Data access layer for the nutritional module. Queries the NoHarm schema
tables (pessoa, segmentosetor, segmento) to retrieve patient data needed
for nutritional score calculations.
"""

from sqlalchemy import text

from models.main import db
from models.prescription import Patient
from models.segment import Segment
from models.appendix import SegmentDepartment

# tp_segmento integer value that identifies ICU segments in NoHarm.
# Adjust this constant to match the hospital's NoHarm configuration.
ICU_SEGMENT_TYPE = 3


def get_active_admissions():
    """Return all active admissions with ICU protocol flag.

    Active means dtalta IS NULL. Joins segmentosetor and segmento to derive
    whether the patient is in an ICU segment (is_icu).

    Returns:
        List of namedtuple-like rows with fields:
            admissionNumber, fksetor, birthdate, admissionDate,
            weight, height, id_icd, segment_type (int), is_icu (bool)
    """
    query = text(
        """
        SELECT
            p.nratendimento,
            p.fksetor,
            p.dtnascimento,
            p.dtinternacao,
            p.peso,
            p.altura,
            p.idcid,
            seg.tp_segmento,
            (seg.tp_segmento = :icu_type) AS is_icu
        FROM pessoa p
        JOIN segmentosetor ss  ON ss.fksetor     = p.fksetor
        JOIN segmento seg      ON seg.idsegmento  = ss.fksegmento
        WHERE p.dtalta IS NULL
        """
    )
    result = db.session.execute(query, {"icu_type": ICU_SEGMENT_TYPE})
    return result.fetchall()
