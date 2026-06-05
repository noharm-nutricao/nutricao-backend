from app import db
from sqlalchemy import text


def get_evol_pending_aux_alerts():
    query = text(
        """
        SELECT naa.id,
               naa.nratendimento,
               ev.fkevolucao
               ev.anotacoes -> 'sintomas' AS sintomas
          FROM demo.nutricional_aux_alerta naa
          JOIN demo.evolucao ev
            ON ev.fkevolucao = naa.fkevolucao
         WHERE naa.reconhecido = false
           AND naa.fkevolucao IS NOT NULL;
        """
    )
    result = db.session.execute(query)
    return result.fetchall()


def get_pres_pending_aux_alerts():
    query = text(
        """
        SELECT naa.id,
               naa.nratendimento,
               pm.fkpresmed,
               pm.complemento
          FROM demo.nutricional_aux_alerta naa
          JOIN demo.presmed pm
            ON pm.fkpresmed = naa.fkpresmed
         WHERE naa.reconhecido = false
           AND naa.fkpresmed IS NOT NULL;
        """
    )
    result = db.session.execute(query)
    return result.fetchall()


def recon_pending_aux_alert(id: int) -> None:
    query = text(
        """
        UPDATE demo.nutricional_aux_alerta
           SET reconhecido = true
         WHERE id = :id
        """
    )
    result = db.session.execute(query, {"id": id})
    return result.fetchone()


def generate_alert(severity: str, nratendimento: int, alert_type: str, observation: str, fkevolucao: int | None, fkpresmed: int | None):
    query = text(
        """
        INSERT INTO demo.nutricional_alerta(
            nratendimento,
            tipo,
            descricao,
            severidade,
            ativo,
            created_at,
            reconhecido,
            reconhecido_por,
            fk_origem_gatilho_evol,
            fk_origem_gatilho_pres,
            reconhecido_at
        ) VALUES (
            :nratendimento,
            :tipo,
            :descricao,
            :severidade,
            TRUE,
            now(),
            false,
            :fk_origem_gatilho_evol,
            :fk_origem_gatilho_pres,
            null,
            null
        )
        """
    )
    result = db.session.execute(query, {
        "nratendimento": nratendimento,
        "tipo": alert_type,
        "descricao": observation,
        "severidade": severity,
        "fk_origem_gatilho_evol": fkevolucao,
        "fk_origem_gatilho_pres": fkpresmed,
    })
    return result.fetchone()
