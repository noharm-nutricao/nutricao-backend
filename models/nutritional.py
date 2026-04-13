
from .main import db


class NutritionalTriagem(db.Model):
    __tablename__ = "nutricional_triagem"

    id = db.Column(
        "idnutricional_triagem", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    classificacao = db.Column("classificacao", db.String, nullable=True)
    mn_apache = db.Column("mn_apache", db.Integer, nullable=True)
    mn_sofa = db.Column("mn_sofa", db.Integer, nullable=True)
    mn_apache_manual = db.Column("mn_apache_manual", db.Boolean, nullable=True)
    mn_sofa_manual = db.Column("mn_sofa_manual", db.Boolean, nullable=True)
    nrs_nut = db.Column("nrs_nut", db.Integer, nullable=True)
    nrs_doenca = db.Column("nrs_doenca", db.Integer, nullable=True)
    nrs_idade = db.Column("nrs_idade", db.Integer, nullable=True)
    nrs_completo = db.Column("nrs_completo", db.Boolean, nullable=True)
    mnutric_total = db.Column("mnutric_total", db.Integer, nullable=True)
    dados_incompletos = db.Column("dados_incompletos", db.Boolean, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)
    updated_at = db.Column("updated_at", db.DateTime, nullable=True)
    updated_by = db.Column("updated_by", db.BigInteger, nullable=True)

