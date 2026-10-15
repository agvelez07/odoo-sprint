from odoo import api, fields, models


class ProjectProject(models.Model):
    _name = 'project.project'
    _inherit = ['project.project', 'project.team.notify.mixin']

    team_id = fields.Many2one('project.team', string='Equipa', index=True, tracking=True)
    sprint_ids = fields.One2many('project.sprint', 'project_id', string='Sprints')
    sprint_count = fields.Integer(compute='_compute_sprint_count')

    def _compute_sprint_count(self):
        for project in self:
            project.sprint_count = len(project.sprint_ids)

    def action_view_sprints(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'project_sprint.project_sprint_action')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    # ------------------------------------------------------------------
    # Equipa: visibilidade e notificações (ver project.team.notify.mixin)
    # ------------------------------------------------------------------
    def _get_notify_team(self):
        return self.team_id

    def _track_subtype(self, init_values):
        return self._team_track_subtype(super()._track_subtype(init_values))

    def _apply_team_access(self, force=False):
        """Um projeto com equipa só é visível a quem o segue (líder e membros).
        Os gestores continuam a ver todos os projetos."""
        projects = self.filtered('team_id')
        wrong = projects.filtered(lambda p: p.privacy_visibility != 'followers')
        if wrong:
            wrong.sudo().write({'privacy_visibility': 'followers'})
        projects._subscribe_team(force)

    def _unfollow_team(self, team):
        """Tira a equipa antiga dos seguidores do projeto, sprints e tarefas."""
        for project in self.sudo():
            leaving = team._get_partners() - project.team_id._get_partners()
            if not leaving:
                continue
            tasks = self.env['project.task'].sudo().with_context(active_test=False).search(
                [('project_id', '=', project.id)])
            for records in (project, project.sprint_ids, tasks):
                records.message_unsubscribe(partner_ids=leaving.ids)

    def _on_team_changed(self, old_teams):
        """Depois de trocar a equipa: a antiga deixa de seguir, a nova passa a seguir."""
        for project in self:
            if old_teams[project.id] and old_teams[project.id] != project.team_id:
                project._unfollow_team(old_teams[project.id].sudo())
        self._apply_team_access()
        tasks = self.env['project.task'].sudo().search(
            [('project_id', 'in', self.filtered('team_id').ids)])
        tasks._subscribe_team()
        self.sprint_ids.filtered('team_id')._subscribe_team()

    def write(self, vals):
        old_teams = {p.id: p.team_id for p in self} if 'team_id' in vals else None
        res = super().write(vals)
        if old_teams is not None:
            self._on_team_changed(old_teams)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects.filtered('team_id')._apply_team_access()
        return projects
