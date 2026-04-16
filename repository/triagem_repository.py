"""Repository: patient listing with campo1 (triagem) data."""

from sqlalchemy import asc, select

from models.appendix import Department
from models.main import db
from models.prescription import Patient
from models.triagem import Triagem


def get_patients_with_triagem(id_segment: int = None, id_department: int = None):
    """
    Return active patients joined with their triagem (campo1) data.
    Patients without triagem are included (triagem cols will be None).
    Excludes discharged patients (dtalta IS NULL).
    Ordered by triagem.pri ASC NULLS LAST, then admission number ASC.
    """
    query = (
        select(Patient, Triagem, Department.name.label("ala"))
        .select_from(Patient)
        .outerjoin(Triagem, Triagem.admissionNumber == Patient.admissionNumber)
        .outerjoin(
            Department,
            (Department.id == Patient.fksetor)
            & (Department.idHospital == Patient.idHospital),
        )
        .where(Patient.dischargeDate.is_(None))
        .order_by(
            asc(Triagem.pri).nulls_last(),
            asc(Patient.admissionNumber),
        )
    )

    if id_segment is not None:
        from models.prescription import Prescription

        agg_sub = (
            select(Prescription.admissionNumber)
            .where(Prescription.idSegment == id_segment)
            .where(Prescription.agg.is_(True))
        )
        query = query.where(Patient.admissionNumber.in_(agg_sub))

    if id_department is not None:
        from models.prescription import Prescription

        dept_sub = (
            select(Prescription.admissionNumber)
            .where(Prescription.idDepartment == id_department)
        )
        query = query.where(Patient.admissionNumber.in_(dept_sub))

    return db.session.execute(query).all()
