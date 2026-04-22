
from .main import db

from sqlalchemy import func
from sqlalchemy.dialects import postgresql

from app.extensions import db

class NutritionalNrs(db.Model):
    __tablename__ = "nutricional_nrs"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    triagem_imc_baixo = db.Column("triagem_imc_baixo", db.Boolean, nullable=False)
    triagem_perda_peso = db.Column("triagem_perda_peso", db.Boolean, nullable=False)
    triagem_ingestao_reduzida = db.Column("triagem_ingestao_reduzida", db.Boolean, nullable=False)
    triagem_doenca_grave = db.Column("triagem_doenca_grave", db.Boolean, nullable=False)

    score_comprometimento = db.Column("score_comprometimento", db.Integer, nullable=False)
    score_gravidade = db.Column("score_gravidade", db.Integer, nullable=False)
    idade_maior_70 = db.Column("idade_maior_70", db.Boolean, nullable=False)

    updated_at = db.Column("updated_at", db.DateTime, nullable=True, onupdate=func.now())
    created_at = db.Column("created_at", db.DateTime, nullable=True)


class NutritionalScreening(db.Model):
    __tablename__ = "nutricional_triagem"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    protocolo = db.Column("protocolo", db.String, nullable=False)

    nrs_nut = db.Column("nrs_nut", db.Integer, nullable=True)
    nrs_doenca = db.Column("nrs_doenca", db.Integer, nullable=True)
    nrs_idade = db.Column("nrs_idade", db.Integer, nullable=True)
    nrs_total = db.Column("nrs_total", db.Integer, nullable=True)
    nrs_completo = db.Column("nrs_completo", db.Boolean, nullable=False, default=False)
    nrs_ref_at = db.Column("nrs_ref_at", db.DateTime, nullable=True)

    mn_idade = db.Column("mn_idade", db.Integer, nullable=True)
    mn_apache = db.Column("mn_apache", db.Integer, nullable=True)
    mn_sofa = db.Column("mn_sofa", db.Integer, nullable=True)
    mn_comor = db.Column("mn_comor", db.Integer, nullable=True)
    mn_dias = db.Column("mn_dias", db.Integer, nullable=True)
    mn_total = db.Column("mn_total", db.Integer, nullable=True)
    mn_apache_manual = db.Column("mn_apache_manual", db.Boolean, nullable=True)
    mn_sofa_manual = db.Column("mn_sofa_manual", db.Boolean, nullable=True)

    classificacao = db.Column("classificacao", db.String, nullable=True)
    calculado_at = db.Column("calculado_at", db.DateTime, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)
    updated_at = db.Column("updated_at", db.DateTime, nullable=True, onupdate=func.now())


class NutritionalGlim(db.Model):
    __tablename__ = "nutricional_glim"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    diagnostico = db.Column("diagnostico", db.String, nullable=False)
    fenotipos = db.Column("fenotipos", postgresql.ARRAY(postgresql.TEXT), nullable=True)
    etiologias = db.Column("etiologias", postgresql.ARRAY(postgresql.TEXT), nullable=True)
    observacao = db.Column("observacao", postgresql.TEXT, nullable=True)
    idusuario = db.Column("idusuario", db.Integer, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)
    updated_at = db.Column("updated_at", db.DateTime, nullable=True, onupdate=func.now())


class NutritionalAssessment(db.Model):
    __tablename__ = "nutricional_avaliacao"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    idusuario = db.Column("idusuario", db.Integer, nullable=True)
    conduta = db.Column("conduta", postgresql.TEXT, nullable=True)
    frequencia = db.Column("frequencia", db.String, nullable=True)
    ingestao = db.Column("ingestao", db.Integer, nullable=True)
    meta_kcal = db.Column("meta_kcal", db.Integer, nullable=True)
    meta_prot = db.Column("meta_prot", db.Integer, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)


class NutritionalD7(db.Model):
    __tablename__ = "nutricional_d7"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    dt_prevista = db.Column("dt_prevista", db.DateTime, nullable=False)
    concluido = db.Column("concluido", db.Boolean, nullable=True)
    idusuario = db.Column("idusuario", db.Integer, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)
    updated_at = db.Column("updated_at", db.DateTime, nullable=True, onupdate=func.now())

class NutritionalTriagem(db.Model):
    __tablename__ = "nutricional_triagem_pedro"

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

class NutritionalAlert(db.Model):
    __tablename__ = "nutricional_alerta"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    tipo = db.Column("tipo", db.String, nullable=True)
    descricao = db.Column("descricao", postgresql.TEXT, nullable=True)
    severidade = db.Column("severidade", db.String, nullable=True)
    ativo = db.Column("ativo", db.Boolean, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)
    reconhecido = db.Column("reconhecido", db.Boolean, nullable=True)
    reconhecido_por = db.Column("reconhecido_por", db.Integer, nullable=False)
    reconhecido_at = db.Column("reconhecido_at", db.DateTime, nullable=True)
