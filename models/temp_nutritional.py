from .main import db


class NutricionalNrs(db.Model):
	"""Tabela nutricional_nrs (triagem NRS-2002)."""

	__tablename__ = "nutricional_nrs"
	__table_args__ = (
		db.Index(
			"nutricional_nrs_atendimento_idx",
			"nratendimento",
			db.text("updated_at DESC"),
		),
	)

	id = db.Column("id", db.BigInteger, primary_key=True)
	nratendimento = db.Column(
		"nratendimento",
		db.Integer,
		db.ForeignKey("pessoa.nratendimento"),
		nullable=False,
	)

	# Etapa 1: Triagem inicial
	triagem_imc_baixo = db.Column("triagem_imc_baixo", db.Boolean, nullable=False)
	triagem_perda_peso = db.Column("triagem_perda_peso", db.Boolean, nullable=False)
	triagem_ingestao_reduzida = db.Column(
		"triagem_ingestao_reduzida", db.Boolean, nullable=False
	)
	triagem_doenca_grave = db.Column("triagem_doenca_grave", db.Boolean, nullable=False)

	# Etapa 2: Triagem final
	score_comprometimento = db.Column(
		"score_comprometimento", db.SmallInteger, nullable=True
	)
	score_gravidade = db.Column("score_gravidade", db.SmallInteger, nullable=True)
	idade_maior_70 = db.Column("idade_maior_70", db.Boolean, nullable=True)

	# Controle incremental
	updated_at = db.Column(
		"updated_at",
		db.DateTime(timezone=True),
		nullable=False
	)
	created_at = db.Column(
		"created_at",
		db.DateTime(timezone=True),
		nullable=False
	)
