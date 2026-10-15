from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Estados de tarefa que o Odoo considera fechados (project.task.CLOSED_STATES)
CLOSED_STATES = ('1_done', '1_canceled')


class ProjectSprint(models.Model):
    _name = 'project.sprint'
    _inherit = ['project.deadline.mixin', 'project.team.notify.mixin', 'mail.thread']
    _description = 'Project Sprint'
    _order = 'project_id, date_end'

    name = fields.Char(
        string='Nome', required=True, default='New', copy=False, tracking=True)
    project_id = fields.Many2one(
        'project.project', string='Projeto', required=True, index=True,
        ondelete='restrict', tracking=True)
    team_id = fields.Many2one(
        related='project_id.team_id', string='Equipa', store=True, index=True)
    date_start = fields.Date(
        string='Início', required=True, default=fields.Date.context_today,
        tracking=True)
    date_end = fields.Date(
        string='Fim', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=14))
    goal = fields.Text(string='Objetivo')
    state = fields.Selection(
        [('planned', 'Planeado'), ('active', 'Ativo'), ('closed', 'Fechado')],
        string='Estado', default='planned', required=True, index=True, copy=False,
        tracking=True)
    active = fields.Boolean(default=True)
    task_ids = fields.Many2many(
        'project.task', 'project_sprint_task_rel', 'sprint_id', 'task_id',
        string='Tarefas')
    milestone_id = fields.Many2one(
        'project.milestone', string='Milestone', index=True, ondelete='set null',
        domain="[('project_id', '=', project_id)]", tracking=True)
    milestone_deadline = fields.Date(
        related='milestone_id.deadline', string='Prazo do milestone')
    milestone_at_risk = fields.Boolean(
        compute='_compute_milestone_at_risk', string='Milestone em risco')

    # Progresso (guardado para poder agrupar/ordenar sem recalcular)
    task_count = fields.Integer(
        string='N.º de tarefas', compute='_compute_progress', store=True)
    total_points = fields.Integer(
        string='Pontos totais', compute='_compute_progress', store=True)
    done_points = fields.Integer(
        string='Pontos concluídos', compute='_compute_progress', store=True)
    progress = fields.Float(
        string='Progresso', compute='_compute_progress', store=True)
    is_overdue = fields.Boolean(string='Em atraso', compute='_compute_is_overdue')

    # days_overdue e deadline_status vêm do project.deadline.mixin

    # ------------------------------------------------------------------
    # Campos calculados
    # ------------------------------------------------------------------
    @api.depends('task_ids.state', 'task_ids.effort_points')
    def _compute_progress(self):
        for sprint in self:
            # tarefas canceladas nao contam para o progresso
            tasks = sprint.task_ids.filtered(lambda t: t.state != '1_canceled')
            done = tasks.filtered(lambda t: t.state == '1_done')
            sprint.task_count = len(tasks)
            sprint.total_points = sum(tasks.mapped('effort_points'))
            sprint.done_points = sum(done.mapped('effort_points'))
            if sprint.total_points:
                sprint.progress = 100.0 * sprint.done_points / sprint.total_points
            elif tasks:
                # sem pontos definidos: usa a contagem de tarefas
                sprint.progress = 100.0 * len(done) / len(tasks)
            else:
                sprint.progress = 0.0

    @api.depends('state', 'date_end')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for sprint in self:
            sprint.is_overdue = bool(
                sprint.state == 'active' and sprint.date_end and sprint.date_end < today)

    @api.depends('state', 'date_end', 'milestone_id.deadline', 'milestone_id.is_reached')
    def _compute_milestone_at_risk(self):
        """O sprint acaba depois do prazo do milestone a que está ligado."""
        for sprint in self:
            milestone = sprint.milestone_id
            sprint.milestone_at_risk = bool(
                milestone and milestone.deadline and not milestone.is_reached
                and sprint.state != 'closed' and sprint.date_end
                and sprint.date_end > milestone.deadline)

    @api.depends('state', 'date_start', 'date_end')
    def _compute_deadline(self):
        super()._compute_deadline()

    def _deadline_info(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.state == 'closed':
            return None, 'Fechado'
        if self.state == 'planned':
            delta = (self.date_start - today).days if self.date_start else 0
            return None, (f'Começa em {delta} d' if delta > 0 else 'Por iniciar')
        if not self.date_end:
            return None, 'Sem prazo'
        return self.date_end, False

    # ------------------------------------------------------------------
    # Notificações (ver project.team.notify.mixin)
    # ------------------------------------------------------------------
    def _get_notify_team(self):
        return self.team_id

    def _track_subtype(self, init_values):
        return self._team_track_subtype(super()._track_subtype(init_values))

    # ------------------------------------------------------------------
    # Validacoes
    # ------------------------------------------------------------------
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for sprint in self:
            if sprint.date_end < sprint.date_start:
                raise ValidationError(_(
                    'A data de fim tem de ser igual ou posterior à data de início.'))

    @api.constrains('state', 'project_id')
    def _check_one_active_per_project(self):
        for sprint in self.filtered(lambda s: s.state == 'active'):
            other = self.search_count([
                ('project_id', '=', sprint.project_id.id),
                ('state', '=', 'active'),
                ('id', '!=', sprint.id),
            ])
            if other:
                raise ValidationError(_(
                    'O projeto "%s" já tem um sprint ativo.',
                    sprint.project_id.display_name))

    @api.constrains('task_ids', 'project_id')
    def _check_tasks_same_project(self):
        for sprint in self:
            wrong = sprint.task_ids.filtered(
                lambda t: t.project_id != sprint.project_id)
            if wrong:
                raise ValidationError(_(
                    'As tarefas %(tasks)s não pertencem ao projeto "%(project)s".',
                    tasks=', '.join(wrong.mapped('name')),
                    project=sprint.project_id.display_name))

    @api.constrains('milestone_id', 'project_id')
    def _check_milestone_same_project(self):
        for sprint in self.filtered('milestone_id'):
            if sprint.milestone_id.project_id != sprint.project_id:
                raise ValidationError(_(
                    'O milestone "%(milestone)s" não pertence ao projeto "%(project)s".',
                    milestone=sprint.milestone_id.name,
                    project=sprint.project_id.display_name))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_with_tasks(self):
        if self.filtered('task_ids'):
            raise UserError(_(
                'Não é possível apagar um sprint com tarefas. Arquive-o.'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' and vals.get('project_id'):
                count = self.with_context(active_test=False).search_count(
                    [('project_id', '=', vals['project_id'])])
                vals['name'] = _('Sprint %s', count + 1)
        sprints = super().create(vals_list)
        sprints._subscribe_team()
        for sprint in sprints:
            sprint._notify_team(_(
                'Novo sprint "%(name)s" em %(project)s (%(start)s a %(end)s).',
                name=sprint.name, project=sprint.project_id.display_name,
                start=sprint.date_start, end=sprint.date_end))
        return sprints

    def write(self, vals):
        tasks_before = {s.id: s.task_ids for s in self} if 'task_ids' in vals else {}
        res = super().write(vals)
        if 'project_id' in vals:
            self._subscribe_team()
        for sprint in self.filtered(lambda s: s.id in tasks_before):
            added = sprint.task_ids - tasks_before[sprint.id]
            removed = tasks_before[sprint.id] - sprint.task_ids
            parts = []
            if added:
                parts.append(_('Tarefas adicionadas: %s.', ', '.join(added.mapped('name'))))
            if removed:
                parts.append(_('Tarefas removidas: %s.', ', '.join(removed.mapped('name'))))
            if parts:
                sprint._notify_team(' '.join(parts))
        return res

    # ------------------------------------------------------------------
    # Acoes
    # ------------------------------------------------------------------
    def action_start(self):
        for sprint in self:
            if sprint.state != 'planned':
                raise UserError(_('Só é possível iniciar sprints planeados.'))
            # a constraint _check_one_active_per_project valida o resto
            sprint.state = 'active'
        return True

    def action_close(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Só é possível fechar sprints ativos.'))
        open_tasks = self.task_ids.filtered(lambda t: t.state not in CLOSED_STATES)
        if not open_tasks:
            self.state = 'closed'
            return True
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fechar sprint'),
            'res_model': 'project.sprint.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sprint_id': self.id},
        }

    def action_open_board(self):
        """Board (kanban) das tarefas: de um sprint (botão) ou de todos os
        sprints ativos (menu). Só líderes e gestores recebem a versão em que
        se pode arrastar; os outros veem o mesmo board só para leitura."""
        manage = self.env['project.team']._user_can_manage()
        view = self.env.ref('project_sprint.project_sprint_board_view_kanban' + (
            '_manage' if manage else ''))
        action = self.env['ir.actions.act_window']._for_xml_id(
            'project_sprint.project_sprint_board_action')
        action['views'] = [(view.id, 'kanban'), (False, 'form')]
        if self:
            self.ensure_one()
            action['name'] = _('Board — %(sprint)s (%(project)s)',
                               sprint=self.name, project=self.project_id.display_name)
            action['domain'] = [('sprint_ids', 'in', self.ids)]
            action['context'] = {'sprint_board': True}
        return action

    # ------------------------------------------------------------------
    # Alertas automáticos (ver data/cron_data.xml)
    # ------------------------------------------------------------------
    @api.model
    def _cron_deadline_alerts(self):
        """Avisa a equipa quando um sprint ativo termina amanhã ou ficou em atraso."""
        today = fields.Date.context_today(self)
        messages = {
            today + timedelta(days=1): _('Este sprint termina amanhã.'),
            today - timedelta(days=1): _('Este sprint passou o prazo e continua ativo.'),
        }
        sprints = self.search([('state', '=', 'active'), ('date_end', 'in', list(messages))])
        for sprint in sprints:
            sprint._notify_team(messages[sprint.date_end])
