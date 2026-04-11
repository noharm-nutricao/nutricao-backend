from .main import db
 
class NutricionalNrs(db.Model):
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

    updated_at = db.Column("updated_at", db.DateTime, nullable=True)
    created_at = db.Column("created_at", db.DateTime, nullable=True)


class NutricionalScreening(db.Model):
    __tablename__ = "nutricional_triagem"

    id = db.Column("id", db.Integer, primary_key=True)
    nratendimento = db.Column("nratendimento", db.BigInteger, nullable=False)
    protocolo = db.Column("protocolo", db.String, nullable=False)

    nrs_nut = db.Column("nrs_nut", db.Integer, nullable=True)
    nrs_doenca = db.Column("nrs_doenca", db.Integer, nullable=True)
    nrs_idade = db.Column("nrs_idade", db.Integer, nullable=True)
    nrs_total = db.Column("nrs_total", db.Integer, nullable=True)
    nrs_completo = db.Column("nrs_completo", db.Boolean, nullable=False)
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
    updated_at = db.Column("updated_at", db.DateTime, nullable=True)

class NutricionalCidGravidade(db.Model):
	"""Tabela public.nutricional_cid_gravidade (gravidade por capítulo CID)."""

	__tablename__ = "nutricional_cid_gravidade"
	__table_args__ = (
		db.CheckConstraint("score_nrs BETWEEN 0 AND 2", name="ck_nutritional_cid_gravidade_score_nrs"),
		{"schema": "public"},
	)

	prefixo = db.Column("prefixo", db.CHAR(1), primary_key=True)
	score_nrs = db.Column("score_nrs", db.SmallInteger, nullable=False)
	justif = db.Column("justif", db.Text, nullable=True)


class NutricionalCidOverride(db.Model):
	"""Tabela public.nutricional_cid_override (sobrescrita por prefixo CID de 3 chars)."""

	__tablename__ = "nutricional_cid_override"
	__table_args__ = (
		db.CheckConstraint("score_nrs BETWEEN 0 AND 2", name="ck_nutritional_cid_override_score_nrs"),
		{"schema": "public"},
	)

	prefixo3 = db.Column("prefixo3", db.CHAR(3), primary_key=True)
	score_nrs = db.Column("score_nrs", db.SmallInteger, nullable=False)

