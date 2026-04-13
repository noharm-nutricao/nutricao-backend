"""Models: triage and nutritional NRS screening tables."""

from sqlalchemy.dialects import postgresql

from .main import db


class Triagem(db.Model):
    """Table triagem - nutritional screening result per admission."""

    __tablename__ = "triagem"

    admissionNumber = db.Column("nratendimento", db.BigInteger, primary_key=True)
    protocolo = db.Column("protocolo", db.String(10), nullable=True)
    mnutric_total = db.Column("mnutric_total", db.SmallInteger, nullable=True)
    mn_dims = db.Column("mn_dims", postgresql.JSON, nullable=True)
    mn_apache_manual = db.Column("mn_apache_manual", db.Boolean, nullable=True)
    mn_sofa_manual = db.Column("mn_sofa_manual", db.Boolean, nullable=True)
    dados_incompletos = db.Column("dados_incompletos", db.Boolean, nullable=True)
    nrs_total = db.Column("nrs_total", db.SmallInteger, nullable=True)
    nrs_dims = db.Column("nrs_dims", postgresql.JSON, nullable=True)
    nrs_nut = db.Column("nrs_nut", db.SmallInteger, nullable=True)
    nrs_completo = db.Column("nrs_completo", db.Boolean, nullable=True)
    classificacao = db.Column("classificacao", db.String(3), nullable=True)
    sev = db.Column("sev", db.String(3), nullable=True)
    pri = db.Column("pri", db.SmallInteger, nullable=True)
    haval = db.Column("haval", db.SmallInteger, nullable=True)
    d7 = db.Column("d7", db.Boolean, nullable=True)
    calculado_at = db.Column("calculado_at", db.DateTime, nullable=True)
    update_at = db.Column("update_at", db.DateTime, nullable=True)


class NutricionalNrs(db.Model):
    """Table nutricional_nrs - NRS nutritional component input per admission cycle."""

    __tablename__ = "nutricional_nrs"

    id = db.Column("id", db.BigInteger, primary_key=True)
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    nrs_nut = db.Column("nrs_nut", db.SmallInteger, nullable=False)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
