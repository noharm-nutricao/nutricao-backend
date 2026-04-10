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


class NutricionalTriagem(db.Model):
	"""Tabela nutricional_triagem (NRS-2002 + mNUTRIC)."""

	__tablename__ = "nutricional_triagem"
	__table_args__ = (
		db.CheckConstraint("protocolo IN ('MNUTRIC','NRS2002')", name="ck_triagem_protocolo"),
		db.CheckConstraint("nrs_nut BETWEEN 0 AND 3", name="ck_triagem_nrs_nut"),
		db.CheckConstraint("nrs_doenca BETWEEN 0 AND 3", name="ck_triagem_nrs_doenca"),
		db.CheckConstraint("nrs_idade BETWEEN 0 AND 1", name="ck_triagem_nrs_idade"),
		db.CheckConstraint("nrs_total BETWEEN 0 AND 7", name="ck_triagem_nrs_total"),
		db.CheckConstraint("mn_idade BETWEEN 0 AND 2", name="ck_triagem_mn_idade"),
		db.CheckConstraint("mn_apache BETWEEN 0 AND 3", name="ck_triagem_mn_apache"),
		db.CheckConstraint("mn_sofa BETWEEN 0 AND 3", name="ck_triagem_mn_sofa"),
		db.CheckConstraint("mn_comor BETWEEN 0 AND 1", name="ck_triagem_mn_comor"),
		db.CheckConstraint("mn_dias BETWEEN 0 AND 1", name="ck_triagem_mn_dias"),
		db.CheckConstraint("mn_total BETWEEN 0 AND 10", name="ck_triagem_mn_total"),
		db.CheckConstraint("classificacao IN ('cr','al','md','bx')", name="ck_triagem_classificacao"),
		db.Index("idx_triagem_nratendimento", "nratendimento"),
	)

	id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
	nratendimento = db.Column(
		"nratendimento",
		db.Integer,
		db.ForeignKey("pessoa.nratendimento"),
		nullable=False,
	)

	protocolo = db.Column("protocolo", db.String(10), nullable=False)

	# NRS-2002
	nrs_nut = db.Column("nrs_nut", db.SmallInteger, nullable=True)
	nrs_doenca = db.Column("nrs_doenca", db.SmallInteger, nullable=True)
	nrs_idade = db.Column("nrs_idade", db.SmallInteger, nullable=True)
	nrs_total = db.Column("nrs_total", db.SmallInteger, nullable=True)
	nrs_completo = db.Column(
		"nrs_completo",
		db.Boolean,
		nullable=False,
		server_default=db.text("false"),
	)
	nrs_ref_at = db.Column("nrs_ref_at", db.DateTime(timezone=True), nullable=True)

	# mNUTRIC
	mn_idade = db.Column("mn_idade", db.SmallInteger, nullable=True)
	mn_apache = db.Column("mn_apache", db.SmallInteger, nullable=True)
	mn_sofa = db.Column("mn_sofa", db.SmallInteger, nullable=True)
	mn_comor = db.Column("mn_comor", db.SmallInteger, nullable=True)
	mn_dias = db.Column("mn_dias", db.SmallInteger, nullable=True)
	mn_total = db.Column("mn_total", db.SmallInteger, nullable=True)
	mn_apache_manual = db.Column(
		"mn_apache_manual",
		db.Boolean,
		nullable=True,
		server_default=db.text("false"),
	)
	mn_sofa_manual = db.Column(
		"mn_sofa_manual",
		db.Boolean,
		nullable=True,
		server_default=db.text("false"),
	)

	# Classificação
	classificacao = db.Column("classificacao", db.String(2), nullable=True)
	calculado_at = db.Column(
		"calculado_at",
		db.DateTime(timezone=True),
		nullable=True,
		server_default=db.text("now()"),
	)
	created_at = db.Column(
		"created_at",
		db.DateTime(timezone=True),
		nullable=True,
		server_default=db.text("now()"),
	)
	updated_at = db.Column(
		"updated_at",
		db.DateTime(timezone=True),
		nullable=True,
		server_default=db.text("now()"),
	)
