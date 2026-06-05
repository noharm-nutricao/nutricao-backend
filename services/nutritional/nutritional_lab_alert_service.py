from repository.nutritional import nutritional_repository

EXAMES = {
    "ALB": {"nome": "Albumina", "dir": "low"},
    "HB": {"nome": "Hemoglobina", "dir": "low"},
    "P": {"nome": "Fosforo", "dir": "low"},
    "MG": {"nome": "Magnesio", "dir": "low"},
    "K": {"nome": "Potassio", "dir": "low"},
    "PCR": {"nome": "PCR", "dir": "high"},
}

FOSFORO_MAGNESIO = {"P", "MG"}


def is_exame_alterado(tpexame, resultado, min_val, max_val) -> bool:
    if resultado is None:
        return False
    if EXAMES.get(tpexame.upper(), {}).get("dir") == "high":
        return max_val is not None and resultado > max_val
    return min_val is not None and resultado < min_val


def resolver_severidade(qtd_alterados, tem_fosforo_ou_magnesio, em_ne_npt_pos_npo):
    if qtd_alterados <= 0:
        return None
    if tem_fosforo_ou_magnesio and em_ne_npt_pos_npo:
        return "cr"
    if qtd_alterados >= 3:
        return "cr"
    if qtd_alterados == 2:
        return "al"
    return "md"


def calculate_lab_severity(nratendimento):
    idsegmento = nutritional_repository.get_patient_segment_id(nratendimento)
    latest = nutritional_repository.get_latest_monitored_exams(nratendimento)

    alterados = []
    for tpexame, resultado in latest.items():
        limite = nutritional_repository.get_exam_limit(idsegmento, tpexame)
        if limite is None:
            continue
        if is_exame_alterado(tpexame, resultado, limite.min, limite.max):
            alterados.append(tpexame)

    tem_fosforo_ou_magnesio = any(tp in FOSFORO_MAGNESIO for tp in alterados)
    em_ne_npt_pos_npo = nutritional_repository.get_ne_npt_pos_npo(nratendimento)
    sev = resolver_severidade(len(alterados), tem_fosforo_ou_magnesio, em_ne_npt_pos_npo)

    nomes_alterados = {EXAMES[tp]["nome"] for tp in alterados}
    ativos = nutritional_repository.get_active_lab_alerts(nratendimento)
    ativos_por_descricao = {a.descricao: a for a in ativos}

    for descricao, alerta in ativos_por_descricao.items():
        if descricao not in nomes_alterados:
            nutritional_repository.deactivate_lab_alert(alerta)

    for tpexame in alterados:
        descricao = EXAMES[tpexame]["nome"]
        existente = ativos_por_descricao.get(descricao)
        if existente is None or not existente.ativo:
            nutritional_repository.create_lab_alert(nratendimento, descricao, sev)
        else:
            nutritional_repository.set_lab_severity(existente, sev)


def process_lab_pending_alerts():
    pendentes = nutritional_repository.get_lab_pending_aux_alerts()
    processados = set()
    for pendente in pendentes:
        if pendente.nratendimento not in processados:
            calculate_lab_severity(pendente.nratendimento)
            processados.add(pendente.nratendimento)
        nutritional_repository.recon_pending_aux_alert(pendente.id)
