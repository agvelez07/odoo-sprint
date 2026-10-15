from odoo import _, Command, api, fields, models
from odoo.exceptions import ValidationError, UserError


class ProjectTask(models.Model):
    _inherit = ['project.task', 'project.deadline.mixin']

    sprint_ids = fields.Many2many(
        'project.sprint', 'project_sprint_task_rel', 'task_id', 'sprint_id',
        string='Sprints')
    current_sprint_id = fields.Many2one(
        'project.sprint', compute='_compute_current_sprint',
        store=True, index=True, string='Sprint atual', tracking=True)
    effort_points = fields.Integer(string='Pontos de esforço', tracking=True)
    team_id = fields.Many2one(related='project_id.team_id', string='Equipa', readonly=True)
    team_members_text = fields.Text(compute='_compute_team_members_text',
                                    string='Membros da equipa')

    @api.depends('sprint_ids.state')
    def _compute_current_sprint(self):
        for task in self:
            task.current_sprint_id = task.sprint_ids.filtered(
                lambda s: s.state == 'active')[:1]

    @api.constrains('sprint_ids', 'project_id')
    def _check_sprints_same_project(self):
        for task in self:
            wrong = task.sprint_ids.filtered(
                lambda s: s.project_id != task.project_id)
            if wrong:
                raise ValidationError(_(
                    'A tarefa "%(task)s" só pode estar em sprints do seu projeto (%(project)s).',
                    task=task.name,
                    project=task.project_id.display_name or _('sem projeto')))

    @api.depends('project_id.team_id.lead_id',
                 'project_id.team_id.member_ids.user_id',
                 'project_id.team_id.member_ids.role_id')
    def _compute_team_members_text(self):
        for task in self:
            team = task.project_id.team_id
            if not team:
                task.team_members_text = False
                continue
            lines = [f'{team.lead_id.name} — Líder de equipa']
            lines += [f'{m.user_id.name} — {m.role_id.complete_name}'
                      for m in team.member_ids]
            task.team_members_text = '\n'.join(lines)

    def action_remove_from_sprint(self):
        sprint = self.env['project.sprint'].browse(self.env.context.get('sprint_id'))
        if not sprint.exists():
            raise UserError('Guarde o sprint antes de remover tarefas.')
        if sprint.state == 'closed':
            raise UserError('Não é possível alterar um sprint fechado.')
        sprint.write({'task_ids': [Command.unlink(task.id) for task in self]})

    @api.depends('date_deadline', 'state')
    def _compute_deadline(self):
        super()._compute_deadline()

    def _deadline_info(self):
        self.ensure_one()
        if self.state == '1_done':
            return None, 'Concluída'
        if self.state == '1_canceled':
            return None, 'Cancelada'
        deadline = fields.Date.to_date(self.date_deadline)
        if not deadline:
            return None, 'Sem prazo'
        return deadline, False

    # ------------------------------------------------------------------
    # Notificações: a equipa segue as tarefas dos seus projetos
    # ------------------------------------------------------------------
    def _subscribe_team(self):
        for task in self:
            team = task.project_id.team_id
            if team:
                partners = (team.lead_id | team.member_ids.user_id).partner_id
                task.sudo().message_subscribe(partner_ids=partners.ids)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._subscribe_team()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if 'project_id' in vals:
            self._subscribe_team()
        return res