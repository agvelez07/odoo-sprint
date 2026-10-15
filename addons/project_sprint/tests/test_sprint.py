from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProjectSprint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Project = cls.env['project.project']
        Task = cls.env['project.task']
        cls.project = Project.create({'name': 'Projeto A'})
        cls.other_project = Project.create({'name': 'Projeto B'})
        cls.task_a = Task.create({
            'name': 'Tarefa A', 'project_id': cls.project.id, 'effort_points': 3})
        cls.task_b = Task.create({
            'name': 'Tarefa B', 'project_id': cls.project.id, 'effort_points': 2})
        cls.task_other = Task.create({
            'name': 'Tarefa outro projeto', 'project_id': cls.other_project.id})

    def _sprint(self, **kwargs):
        vals = {
            'name': 'Sprint teste',
            'project_id': self.project.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-14',
        }
        vals.update(kwargs)
        return self.env['project.sprint'].create(vals)

    def test_automatic_name(self):
        sprint = self.env['project.sprint'].create({
            'project_id': self.project.id,
            'date_start': '2026-01-01',
            'date_end': '2026-01-14',
        })
        self.assertEqual(sprint.name, 'Sprint 1')

    def test_invalid_dates(self):
        with self.assertRaises(ValidationError):
            self._sprint(date_start='2026-02-01', date_end='2026-01-01')

    def test_one_active_sprint_per_project(self):
        first = self._sprint()
        first.action_start()
        second = self._sprint(date_start='2026-01-15', date_end='2026-01-28')
        with self.assertRaises(ValidationError):
            second.action_start()

    def test_task_from_other_project_is_blocked(self):
        with self.assertRaises(ValidationError):
            self._sprint(task_ids=[Command.set([self.task_other.id])])

    def test_progress(self):
        sprint = self._sprint(
            task_ids=[Command.set([self.task_a.id, self.task_b.id])])
        self.assertEqual(sprint.total_points, 5)
        self.assertEqual(sprint.progress, 0.0)
        self.task_b.state = '1_done'
        self.assertEqual(sprint.done_points, 2)
        self.assertAlmostEqual(sprint.progress, 40.0)

    def test_progress_empty_sprint(self):
        self.assertEqual(self._sprint().progress, 0.0)

    def test_close_sprint_returns_open_tasks_to_backlog(self):
        sprint = self._sprint(
            task_ids=[Command.set([self.task_a.id, self.task_b.id])])
        sprint.action_start()
        self.task_b.state = '1_done'
        wizard = self.env['project.sprint.close.wizard'].with_context(
            default_sprint_id=sprint.id).create({'destination': 'backlog'})
        wizard.action_confirm()
        self.assertEqual(sprint.state, 'closed')
        self.assertNotIn(self.task_a, sprint.task_ids)
        self.assertIn(self.task_b, sprint.task_ids)

    def test_close_sprint_moves_open_tasks_to_next(self):
        sprint = self._sprint(task_ids=[Command.set([self.task_a.id])])
        sprint.action_start()
        following = self._sprint(date_start='2026-01-15', date_end='2026-01-28')
        wizard = self.env['project.sprint.close.wizard'].with_context(
            default_sprint_id=sprint.id).create({
                'destination': 'next', 'next_sprint_id': following.id})
        wizard.action_confirm()
        self.assertEqual(sprint.state, 'closed')
        self.assertIn(self.task_a, following.task_ids)
        # mantem o historico no sprint fechado
        self.assertIn(self.task_a, sprint.task_ids)


@tagged('post_install', '-at_install')
class TestProjectChangeOnchange(TransactionCase):
    """Mudar de projeto limpa as ligações do projeto antigo em vez de dar erro."""

    def test_task_leaves_sprints_when_project_changes(self):
        from odoo.tests import Form
        today = fields.Date.context_today(self.env['project.sprint'])
        p1 = self.env['project.project'].create({'name': 'P1'})
        p2 = self.env['project.project'].create({'name': 'P2'})
        task = self.env['project.task'].create({'name': 'T', 'project_id': p1.id})
        sprint = self.env['project.sprint'].create({
            'project_id': p1.id, 'date_start': today,
            'date_end': today + timedelta(days=7), 'task_ids': [Command.set(task.ids)]})
        with Form(task) as form:
            form.project_id = p2
        self.assertFalse(task.sprint_ids)
        self.assertNotIn(task, sprint.task_ids)

    def test_sprint_drops_tasks_and_milestone_when_project_changes(self):
        from odoo.tests import Form
        today = fields.Date.context_today(self.env['project.sprint'])
        p1 = self.env['project.project'].create({'name': 'P1'})
        p2 = self.env['project.project'].create({'name': 'P2'})
        task = self.env['project.task'].create({'name': 'T', 'project_id': p1.id})
        milestone = self.env['project.milestone'].create({'name': 'M', 'project_id': p1.id})
        sprint = self.env['project.sprint'].create({
            'project_id': p1.id, 'date_start': today, 'milestone_id': milestone.id,
            'date_end': today + timedelta(days=7), 'task_ids': [Command.set(task.ids)]})
        with Form(sprint) as form:
            form.project_id = p2
        self.assertFalse(sprint.task_ids)
        self.assertFalse(sprint.milestone_id)


@tagged('post_install', '-at_install')
class TestProjectChangeWrite(TransactionCase):
    """Mudar o projeto por escrita direta (lista, importação) também limpa as ligações."""

    def test_write_project_on_task_and_sprint(self):
        today = fields.Date.context_today(self.env['project.sprint'])
        p1 = self.env['project.project'].create({'name': 'P1'})
        p2 = self.env['project.project'].create({'name': 'P2'})
        task = self.env['project.task'].create({'name': 'T', 'project_id': p1.id})
        milestone = self.env['project.milestone'].create({'name': 'M', 'project_id': p1.id})
        sprint = self.env['project.sprint'].create({
            'project_id': p1.id, 'date_start': today, 'milestone_id': milestone.id,
            'date_end': today + timedelta(days=7), 'task_ids': [Command.set(task.ids)]})
        task.write({'project_id': p2.id})
        self.assertFalse(task.sprint_ids)
        task.write({'project_id': p1.id})
        sprint.write({'task_ids': [Command.link(task.id)]})
        sprint.write({'project_id': p2.id})
        self.assertFalse(sprint.task_ids)
        self.assertFalse(sprint.milestone_id)