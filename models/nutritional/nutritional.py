from models.main import db


class NutritionalTriage(db.Model):
    __tablename__ = "nutricional_triagem"

    admissionNumber = db.Column("nratendimento", db.BigInteger, primary_key=True)
    apache = db.Column("mn_apache", db.Integer, nullable=True)
    sofa = db.Column("mn_sofa", db.Integer, nullable=True)
    total = db.Column("mn_total", db.Integer, nullable=True)
    apacheManual = db.Column("mn_apache_manual", db.Boolean, nullable=False, default=False)
    sofaManual = db.Column("mn_sofa_manual", db.Boolean, nullable=False, default=False)
