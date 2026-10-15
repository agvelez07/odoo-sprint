from odoo import _, api, fields, models


class ProjectMilestone(models.Model):
    _name = 'project.milestone'
    _inherit = ['project.milestone', 'project.team.notify.mixin']

    name = fields.Char(tracking=True)
    is_reached = fields.Boolean(tracking=True)
    sprint_ids = fields.One2many('project.sprint', 'milestone_id', string='Sprints')

    # ------------------------------------------------------------------
    # Notificações (ver project.team.notify.mixin)
    # ------------------------------------------------------------------
    def _get_notify_team(self):
        return self.project_id.team_id

    def _track_subtype(self, init_values):
        return self._team_track_subtype(super()._track_subtype(init_values))

    @api.model_create_multi
    def create(self, vals_list):
        milestones = super().create(vals_list)
        # criar um milestone liga a funcionalidade "Marcos" no projeto
        milestones.project_id.filtered(
            lambda p: not p.allow_milestones).sudo().allow_milestones = True
        milestones._subscribe_team()
        for milestone in milestones:
            milestone._notify_team(_(
                'Novo milestone "%(name)s" em %(project)s (prazo: %(deadline)s).',
                name=milestone.name, project=milestone.project_id.display_name,
                deadline=milestone.deadline or _('sem prazo')))
        return milestones

    # ------------------------------------------------------------------
    # Acesso: só líder da equipa e gestores editam (regra em security.xml);
    # os outros veem as mesmas vistas só para leitura.
    # ------------------------------------------------------------------
    @api.model
    def action_open_milestones(self):
        manage = self.env['project.team']._user_can_manage()
        suffix = '' if manage else '_readonly'
        action = self.env['ir.actions.act_window']._for_xml_id(
            'project_sprint.project_sprint_milestone_action')
        action['views'] = [
            (self.env.ref('project_sprint.project_sprint_milestone_view_list' + suffix).id, 'list'),
            (self.env.ref('project_sprint.project_sprint_milestone_view_form' + suffix).id, 'form'),
        ]
        return action
