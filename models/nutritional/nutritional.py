from models.main import db


class NutritionalTriage(db.Model):
    __tablename__ = "nutricional_triagem"

    id = db.Column("id", db.BigInteger, primary_key=True)
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    protocol = db.Column("protocolo", db.String(10), nullable=False)
    age = db.Column("mn_idade", db.Integer, nullable=True)
    apache = db.Column("mn_apache", db.Integer, nullable=True)
    sofa = db.Column("mn_sofa", db.Integer, nullable=True)
    comorbidity = db.Column("mn_comor", db.Integer, nullable=True)
    days = db.Column("mn_dias", db.Integer, nullable=True)
    total = db.Column("mn_total", db.Integer, nullable=True)
    apacheManual = db.Column("mn_apache_manual", db.Boolean, nullable=False, default=False)
    sofaManual = db.Column("mn_sofa_manual", db.Boolean, nullable=False, default=False)
    classification = db.Column("classificacao", db.String(2), nullable=True)
