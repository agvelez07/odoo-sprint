from odoo import models


class TeamNotifyMixin(models.AbstractModel):
    """Avisar a equipa (líder + membros) de tudo o que muda num registo seu.

    Quem herda só diz de que equipa é cada registo (`_get_notify_team`).
    O mixin trata do resto:

    * subscreve o líder e os membros como seguidores;
    * garante que as alterações rastreadas (`tracking=True`) geram sempre
      uma notificação para a equipa, mesmo as que o Odoo, por omissão,
      só regista em silêncio (prazo, responsável, pontos, ...);
    * permite enviar mensagens à equipa (`_notify_team`).
    """
    _name = 'project.team.notify.mixin'
    _description = 'Avisar a equipa'

    def _get_notify_team(self):
        """Equipa a avisar (recordset de project.team; vazio se não houver)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Tipos de mensagem
    # ------------------------------------------------------------------
    def _team_subtype(self):
        """Tipo 'Atualização da equipa' do modelo (data/mail_message_subtype_data.xml)."""
        return self.env.ref(
            'project_sprint.mt_team_update_' + self._name.replace('.', '_'))

    def _team_subtypes(self):
        """Tipos a que a equipa fica subscrita: discussões + os do modelo."""
        return self.env.ref('mail.mt_comment') | self.env['mail.message.subtype'].search(
            [('res_model', '=', self._name)])

    def _team_track_subtype(self, subtype):
        """Usar no fim de `_track_subtype`: se o Odoo não escolheu nenhum
        tipo, a alteração seria só registada. Aqui a equipa é avisada na mesma.
        """
        if not subtype and self._get_notify_team():
            return self._team_subtype()
        return subtype

    # ------------------------------------------------------------------
    # Seguidores e mensagens
    # ------------------------------------------------------------------
    def _subscribe_team(self, force=False):
        """Põe a equipa a seguir os registos, com os tipos de mensagem certos.

        Quem já segue ganha os tipos que lhe faltam, sem perder os que já tinha
        (o Odoo, por exemplo, subscreve a equipa às tarefas só com os tipos do
        projeto). Com `force` repõe exatamente os tipos da equipa.
        """
        records = self.sudo()
        for team in records.mapped(lambda r: r._get_notify_team()):
            partners = team._get_partners().filtered('active')
            team_records = records.filtered(lambda r: r._get_notify_team() == team)
            subtypes = records._team_subtypes().ids
            self.env['mail.followers'].sudo()._insert_followers(
                records._name, team_records.ids, partners.ids,
                subtypes=dict.fromkeys(partners.ids, subtypes),
                existing_policy='replace' if force else 'update')

    def _notify_team(self, body):
        """Mensagem para a equipa (chega à caixa de entrada dos envolvidos)."""
        if self.env.context.get('tracking_disable'):
            return
        for rec in self:
            if rec._get_notify_team():
                # sudo: o autor continua a ser quem fez a alteração
                rec.sudo().message_post(body=body, subtype_id=rec._team_subtype().id)
