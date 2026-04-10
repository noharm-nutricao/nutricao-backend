"""SQLAlchemy models for nutritional module tables."""

from sqlalchemy.dialects import postgresql

from .main import db


class NutritionalAvaliacao(db.Model):
    """Table nutricional_avaliacao - nutritional evaluations."""

    __tablename__ = "nutricional_avaliacao"

    id = db.Column(
        "idnutricional_avaliacao", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    conduta = db.Column("conduta", db.String, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)


class NutritionalD7(db.Model):
    """Table nutricional_d7 - D7 follow-up records."""

    __tablename__ = "nutricional_d7"

    id = db.Column(
        "idnutricional_d7", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    concluido = db.Column("concluido", db.Boolean, nullable=False)
    dt_prevista = db.Column("dt_prevista", db.DateTime, nullable=False)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)


class NutritionalTriagem(db.Model):
    """Table nutricional_triagem - nutritional screening/triage."""

    __tablename__ = "nutricional_triagem"

    id = db.Column(
        "idnutricional_triagem", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    classificacao = db.Column("classificacao", db.String, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)


class NutritionalGlim(db.Model):
    """Table nutricional_glim - GLIM diagnosis data."""

    __tablename__ = "nutricional_glim"

    id = db.Column(
        "idnutricional_glim", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    diagnostico = db.Column("diagnostico", db.String, nullable=True)
    fenotipos = db.Column("fenotipos", postgresql.ARRAY(db.String), nullable=True)
    etiologicos = db.Column("etiologicos", postgresql.ARRAY(db.String), nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)


class NutritionalAlerta(db.Model):
    """Table nutricional_alerta - nutritional alerts (Campo 3)."""

    __tablename__ = "nutricional_alerta"

    id = db.Column(
        "idnutricional_alerta", db.BigInteger, primary_key=True, autoincrement=True
    )
    admissionNumber = db.Column("nratendimento", db.BigInteger, nullable=False)
    alerta = db.Column("alerta", db.String, nullable=False)
    ativo = db.Column("ativo", db.Boolean, nullable=False)
    created_at = db.Column("created_at", db.DateTime, nullable=False)
    created_by = db.Column("created_by", db.BigInteger, nullable=False)

