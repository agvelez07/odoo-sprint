from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectTeamRole(models.Model):
    _name = 'project.team.role'
    _description = 'Função na equipa'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(required=True)
    parent_id = fields.Many2one('project.team.role', string='Função pai',
                                index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(compute='_compute_complete_name',
                                recursive=True, store=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for role in self:
            if role.parent_id:
                role.complete_name = f'{role.parent_id.complete_name} / {role.name}'
            else:
                role.complete_name = role.name

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        if self._has_cycle():
            raise ValidationError('Uma função não pode ser pai de si própria.')


class ProjectTeam(models.Model):
    _name = 'project.team'
    _description = 'Equipa de engenharia'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    lead_id = fields.Many2one('res.users', string='Líder de equipa',
                              required=True, index=True, ondelete='restrict')
    member_ids = fields.One2many('project.team.member', 'team_id', string='Membros')
    project_ids = fields.One2many('project.project', 'team_id', string='Projetos')
    sprint_ids = fields.One2many('project.sprint', 'team_id', string='Sprints')
    member_count = fields.Integer(compute='_compute_counts')
    project_count = fields.Integer(compute='_compute_counts')
    sprint_active_count = fields.Integer(compute='_compute_counts')
    sprint_overdue_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Já existe uma equipa com este nome.'),
    ]

    @api.depends('member_ids', 'project_ids', 'sprint_ids.state', 'sprint_ids.date_end')
    def _compute_counts(self):
        for team in self:
            active = team.sprint_ids.filtered(lambda s: s.state == 'active')
            team.member_count = len(team.member_ids)
            team.project_count = len(team.project_ids)
            team.sprint_active_count = len(active)
            team.sprint_overdue_count = len(active.filtered('is_overdue'))

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        self.member_ids = self.member_ids.filtered(
            lambda m: m.user_id != self.lead_id)

    @api.constrains('lead_id', 'member_ids')
    def _check_lead_not_member(self):
        for team in self:
            if team.lead_id in team.member_ids.user_id:
                raise ValidationError(
                    'O líder da equipa não pode ser também membro da mesma equipa.')


class ProjectTeamMember(models.Model):
    _name = 'project.team.member'
    _description = 'Membro de equipa'
    _order = 'role_id, id'

    team_id = fields.Many2one('project.team', required=True,
                              ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Utilizador', required=True,
                              ondelete='cascade', index=True)
    role_id = fields.Many2one('project.team.role', string='Função',
                              required=True, ondelete='restrict')
    task_ids = fields.Many2many('project.task', compute='_compute_task_ids',
                                string='Tarefas em sprints')

    _sql_constraints = [
        ('user_team_uniq', 'unique(team_id, user_id)',
         'Este utilizador já pertence à equipa.'),
    ]

    @api.constrains('user_id', 'team_id')
    def _check_not_lead(self):
        for member in self:
            if member.user_id == member.team_id.lead_id:
                raise ValidationError('O líder da equipa não pode ser também membro.')

    def _compute_task_ids(self):
        Task = self.env['project.task']
        for member in self:
            if not member.team_id.id or not member.user_id.id:
                member.task_ids = False
                continue
            tasks = Task.search([
                ('user_ids', 'in', member.user_id.id),
                ('project_id.team_id', '=', member.team_id.id),
                ('sprint_ids', '!=', False),
            ])

            def end_date(task):
                open_sprints = task.sprint_ids.filtered(lambda s: s.state != 'closed')
                return min(open_sprints.mapped('date_end') or [date.max])

            member.task_ids = tasks.sorted(key=end_date)