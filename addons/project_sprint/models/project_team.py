from datetime import date

from odoo import Command, _, api, fields, models
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
    _inherit = ['mail.thread', 'project.team.notify.mixin']
    _description = 'Equipa de engenharia'
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    lead_id = fields.Many2one('res.users', string='Líder de equipa',
                              required=True, index=True, ondelete='restrict',
                              tracking=True)
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

    # ------------------------------------------------------------------
    # Permissões
    # ------------------------------------------------------------------
    @api.model
    def _user_can_manage(self):
        """Líderes de equipa e gestores podem gerir sprints, milestones e o board."""
        user = self.env.user
        return (user.has_group('project.group_project_manager')
                or user.has_group('project_sprint.group_team_lead'))

    def _sync_lead_group(self, old_leads=None):
        """Quem lidera uma equipa recebe o grupo 'Líder de equipa';
        quem deixa de liderar todas as suas equipas perde-o."""
        group = self.env.ref('project_sprint.group_team_lead').sudo()
        group.users = [Command.link(user.id) for user in self.lead_id]
        for user in (old_leads or self.env['res.users']) - self.lead_id:
            if not self.sudo().search_count([('lead_id', '=', user.id)]):
                group.users = [Command.unlink(user.id)]

    # ------------------------------------------------------------------
    # Seguidores: o líder e os membros seguem a equipa e tudo o que é dela
    # ------------------------------------------------------------------
    def _get_notify_team(self):
        return self

    def _get_partners(self):
        return (self.lead_id | self.member_ids.user_id).partner_id

    def _track_subtype(self, init_values):
        return self._team_track_subtype(super()._track_subtype(init_values))

    def _sync_followers(self, force=False):
        """Põe líder e membros a seguir a equipa, os projetos, sprints e tarefas."""
        Task = self.env['project.task'].sudo()
        for team in self.sudo():
            team._subscribe_team(force)
            team.project_ids._apply_team_access(force)
            team.sprint_ids._subscribe_team(force)
            Task.search([('project_id.team_id', '=', team.id)])._subscribe_team(force)

    def _unfollow(self, partners):
        """Tira estes contactos de tudo o que é da equipa (se já não a integram)."""
        Task = self.env['project.task'].sudo()
        for team in self.sudo():
            leaving = partners - team._get_partners()
            if not leaving:
                continue
            tasks = Task.search([('project_id.team_id', '=', team.id)])
            for records in (team, team.project_ids, team.sprint_ids, tasks):
                records.message_unsubscribe(partner_ids=leaving.ids)

    def action_sync_followers(self):
        self._sync_followers(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Seguidores sincronizados'),
                'message': _('O líder e os membros seguem a equipa, os projetos, os sprints e as tarefas.'),
                'type': 'success',
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        teams._sync_followers()
        teams._sync_lead_group()
        return teams

    def write(self, vals):
        changing_lead = 'lead_id' in vals
        old = {t.id: (t._get_partners(), t.lead_id) for t in self} if changing_lead else {}
        res = super().write(vals)
        if changing_lead:
            for team in self:
                team._unfollow(old[team.id][0])
            self._sync_followers()
            self._sync_lead_group(
                old_leads=self.env['res.users'].union(*[lead for _p, lead in old.values()]))
        return res


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

    @api.model_create_multi
    def create(self, vals_list):
        members = super().create(vals_list)
        for member in members:
            member.team_id._notify_team(_(
                '%(user)s entrou na equipa como %(role)s.',
                user=member.user_id.name, role=member.role_id.complete_name))
        members.team_id._sync_followers()
        return members

    def write(self, vals):
        old_roles = {m.id: m.role_id for m in self} if 'role_id' in vals else {}
        res = super().write(vals)
        for member in self:
            if member.id in old_roles and old_roles[member.id] != member.role_id:
                member.team_id._notify_team(_(
                    'A função de %(user)s mudou de %(old)s para %(new)s.',
                    user=member.user_id.name, old=old_roles[member.id].complete_name,
                    new=member.role_id.complete_name))
        return res

    def unlink(self):
        leaving = [(m.team_id, m.user_id) for m in self]
        for team, user in leaving:
            team._notify_team(_('%s saiu da equipa.', user.name))
        res = super().unlink()
        for team, user in leaving:
            team._unfollow(user.partner_id)
        return res
