from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import SprintTeamCase


@tagged('post_install', '-at_install')
class TestPermissions(SprintTeamCase):

    # ---------------------- o que cada um vê ----------------------
    def test_team_project_is_followers_only(self):
        self.assertEqual(self.project_a.privacy_visibility, 'followers')
        team_partners = (self.lead_a | self.eng_a1 | self.eng_a2).partner_id
        self.assertLessEqual(team_partners, self.project_a.message_partner_ids)
        self.assertFalse(self.eng_b1.partner_id & self.project_a.message_partner_ids)

    def test_engineer_sees_only_own_team_projects(self):
        projects = self.env['project.project'].with_user(self.eng_a1).search([
            ('id', 'in', [self.project_a.id, self.project_b.id, self.project_free.id])])
        self.assertIn(self.project_a, projects)
        self.assertNotIn(self.project_b, projects)

    def test_engineer_sees_only_own_team_tasks(self):
        tasks = self.env['project.task'].with_user(self.eng_a1).search([
            ('id', 'in', [self.task_a1.id, self.task_a2.id, self.task_b1.id])])
        self.assertEqual(tasks, self.task_a1 | self.task_a2)

    def test_engineer_sees_only_own_team_sprints_and_team(self):
        Sprint = self.env['project.sprint'].with_user(self.eng_a1)
        self.assertEqual(Sprint.search([]), self.sprint_a)
        Team = self.env['project.team'].with_user(self.eng_a1)
        self.assertEqual(Team.search([]), self.team_a)
        Member = self.env['project.team.member'].with_user(self.eng_a1)
        self.assertEqual(Member.search([]).team_id, self.team_a)

    def test_manager_sees_everything(self):
        self.assertEqual(
            self.env['project.sprint'].with_user(self.manager).search_count(
                [('id', 'in', (self.sprint_a | self.sprint_b).ids)]), 2)
        self.assertEqual(
            self.env['project.team'].with_user(self.manager).search_count(
                [('id', 'in', (self.team_a | self.team_b).ids)]), 2)

    # ---------------------- o que cada um edita ----------------------
    def test_engineer_edits_only_assigned_tasks(self):
        self.task_a1.with_user(self.eng_a1).write({'name': 'Mudei o nome'})
        self.assertEqual(self.task_a1.name, 'Mudei o nome')
        with self.assertRaises(AccessError):
            self.task_a2.with_user(self.eng_a1).write({'name': 'Não devia'})
        with self.assertRaises(AccessError):
            self.task_a_free.with_user(self.eng_a1).write({'name': 'Não devia'})

    def test_engineer_can_edit_task_he_created(self):
        task = self.env['project.task'].with_user(self.eng_a1).create({
            'name': 'Criada por mim', 'project_id': self.project_a.id})
        task.write({'name': 'Criada por mim (editada)'})
        self.assertEqual(task.name, 'Criada por mim (editada)')

    def test_engineer_can_comment_on_colleague_task(self):
        self.task_a2.with_user(self.eng_a1).message_post(body='Preciso de ajuda?')
        self.assertTrue(self.task_a2.message_ids.filtered(
            lambda m: m.body and 'Preciso de ajuda?' in m.body))

    def test_lead_edits_all_team_tasks_but_not_other_teams(self):
        for task in (self.task_a1, self.task_a2, self.task_a_free):
            task.with_user(self.lead_a).write({'priority': '1'})
        with self.assertRaises(AccessError):
            self.task_b1.with_user(self.lead_a).write({'priority': '1'})

    def test_manager_edits_every_task(self):
        for task in (self.task_a1, self.task_b1):
            task.with_user(self.manager).write({'priority': '1'})

    def test_private_tasks_are_not_blocked(self):
        task = self.env['project.task'].with_user(self.eng_a1).create({'name': 'Pessoal'})
        task.write({'name': 'Pessoal (editada)'})
        self.assertEqual(task.name, 'Pessoal (editada)')

    def test_tasks_of_projects_without_team_keep_standard_behaviour(self):
        task = self.env['project.task'].create({
            'name': 'Livre', 'project_id': self.project_free.id})
        task.with_user(self.eng_a1).write({'name': 'Livre (editada)'})

    # ---------------------- reordenar ----------------------
    def test_only_lead_or_manager_reorders_tasks(self):
        with self.assertRaises(AccessError):
            self.task_a1.with_user(self.eng_a1).write({'sequence': 1})
        self.task_a1.with_user(self.lead_a).write({'sequence': 1})
        self.task_a2.with_user(self.manager).write({'sequence': 2})
        # outro líder não reordena tarefas de outra equipa
        with self.assertRaises(AccessError):
            self.task_a1.with_user(self.lead_b).write({'sequence': 3})

    def test_reorder_is_free_in_projects_without_team(self):
        task = self.env['project.task'].create({
            'name': 'Livre', 'project_id': self.project_free.id})
        task.with_user(self.eng_a1).write({'sequence': 5})

    # ---------------------- sprints e equipas ----------------------
    def test_engineer_cannot_change_sprints_or_teams(self):
        with self.assertRaises(AccessError):
            self.sprint_a.with_user(self.eng_a1).write({'goal': 'x'})
        with self.assertRaises(AccessError):
            self.team_a.with_user(self.eng_a1).write({'name': 'x'})

    def test_lead_manages_only_own_team_sprints(self):
        today = fields.Date.context_today(self.env['project.sprint'])
        vals = {'date_start': today, 'date_end': today + timedelta(days=7)}
        self.env['project.sprint'].with_user(self.lead_a).create(
            dict(vals, project_id=self.project_a.id))
        with self.assertRaises(AccessError):
            self.env['project.sprint'].with_user(self.lead_a).create(
                dict(vals, project_id=self.project_b.id))
        self.sprint_a.with_user(self.lead_a).write({'goal': 'Objetivo da equipa A'})
        with self.assertRaises(AccessError):
            self.sprint_b.with_user(self.lead_a).write({'goal': 'Não devia'})

    def test_lead_edits_own_team_members_only(self):
        role = self.env.ref('project_sprint.role_frontend')
        member = self.team_a.member_ids[0]
        member.with_user(self.lead_a).write({'role_id': role.id})
        with self.assertRaises(AccessError):
            self.team_b.member_ids[0].with_user(self.lead_a).write({'role_id': role.id})

    # ---------------------- grupo de líder ----------------------
    def test_team_lead_gets_lead_group(self):
        group = self.env.ref('project_sprint.group_team_lead')
        self.assertIn(group, self.lead_a.groups_id)
        self.assertIn(self.env.ref('project.group_project_user'), self.lead_a.groups_id)
        self.assertNotIn(group, self.eng_a1.groups_id)

    def test_changing_lead_moves_the_group(self):
        group = self.env.ref('project_sprint.group_team_lead')
        member = self.team_b.member_ids
        member.unlink()
        self.team_b.lead_id = self.eng_b1
        self.assertIn(group, self.eng_b1.groups_id)
        self.assertNotIn(group, self.lead_b.groups_id)

    def test_lead_keeps_group_while_leading_another_team(self):
        group = self.env.ref('project_sprint.group_team_lead')
        other = self.env['project.team'].create({
            'name': 'Equipa C', 'lead_id': self.lead_b.id})
        self.team_b.member_ids.unlink()
        self.team_b.lead_id = self.eng_b1
        self.assertIn(group, self.lead_b.groups_id)
        self.assertTrue(other)

    # ---------------------- milestones ----------------------
    def test_only_lead_or_manager_edit_milestones(self):
        Milestone = self.env['project.milestone']
        vals = {'name': 'M1', 'project_id': self.project_a.id}
        Milestone.with_user(self.lead_a).create(vals)
        Milestone.with_user(self.manager).create(vals)
        with self.assertRaises(AccessError):
            Milestone.with_user(self.eng_a1).create(vals)
        with self.assertRaises(AccessError):
            Milestone.with_user(self.lead_b).create(vals)
        milestone = Milestone.create(vals)
        with self.assertRaises(AccessError):
            milestone.with_user(self.eng_a1).write({'name': 'x'})
        # todos veem os milestones da equipa
        self.assertIn(milestone, Milestone.with_user(self.eng_a1).search([]))

    # ---------------------- ações com a vista certa ----------------------
    def test_board_is_draggable_only_for_leads_and_managers(self):
        manage = self.env.ref('project_sprint.project_sprint_board_view_kanban_manage')
        readonly = self.env.ref('project_sprint.project_sprint_board_view_kanban')
        for user, view in ((self.lead_a, manage), (self.manager, manage),
                           (self.eng_a1, readonly)):
            action = self.sprint_a.with_user(user).action_open_board()
            self.assertEqual(action['views'][0][0], view.id, user.login)
            self.assertEqual(action['domain'], [('sprint_ids', 'in', self.sprint_a.ids)])
        arch_manage = self.env['project.task'].with_user(self.lead_a).get_view(
            manage.id, 'kanban')['arch']
        arch_readonly = self.env['project.task'].with_user(self.eng_a1).get_view(
            readonly.id, 'kanban')['arch']
        self.assertIn('records_draggable="true"', arch_manage)
        self.assertIn('records_draggable="false"', arch_readonly)

    def test_milestone_views_are_readonly_for_engineers(self):
        eng_action = self.env['project.milestone'].with_user(self.eng_a1).action_open_milestones()
        lead_action = self.env['project.milestone'].with_user(self.lead_a).action_open_milestones()
        eng_list = self.env.ref('project_sprint.project_sprint_milestone_view_list_readonly')
        lead_list = self.env.ref('project_sprint.project_sprint_milestone_view_list')
        self.assertEqual(eng_action['views'][0][0], eng_list.id)
        self.assertEqual(lead_action['views'][0][0], lead_list.id)
