from datetime import timedelta

from odoo import Command, fields
from odoo.tests.common import tagged

from .common import SprintTeamCase


@tagged('post_install', '-at_install')
class TestNotifications(SprintTeamCase):

    def _partners(self, *users):
        return self.env['res.users'].union(*users).partner_id

    # ---------------------- tarefas ----------------------
    def test_team_follows_team_tasks(self):
        team = self._partners(self.lead_a, self.eng_a1, self.eng_a2)
        self.assertLessEqual(team, self.task_a1.message_partner_ids)
        self.assertLessEqual(team, self.sprint_a.message_partner_ids)
        self.assertFalse(self._partners(self.eng_b1, self.lead_b) & self.task_a1.message_partner_ids)

    def test_any_tracked_change_notifies_the_team(self):
        # o prazo não gera notificação no Odoo "de origem": aqui gera
        before = self.task_a2.message_ids
        self.task_a2.with_user(self.lead_a).write({
            'date_deadline': fields.Datetime.now() + timedelta(days=3)})
        notified = self.team_notifications(self.task_a2, since=before)
        self.assertIn(self.eng_a1.partner_id, notified)
        self.assertIn(self.eng_a2.partner_id, notified)
        # quem fez a alteração não se avisa a si próprio
        self.assertNotIn(self.lead_a.partner_id, notified)
        # a outra equipa não é avisada
        self.assertNotIn(self.eng_b1.partner_id, notified)

    def test_stage_change_notifies_the_team(self):
        stage = self.env['project.task.type'].create({
            'name': 'Em curso', 'project_ids': [Command.link(self.project_a.id)]})
        self.task_a1.with_user(self.eng_a1).write({'stage_id': stage.id})
        self.flush_tracking()
        messages = self.task_a1.message_ids.filtered(
            lambda m: m.subtype_id == self.env.ref('project.mt_task_stage'))
        notified = self.env['mail.notification'].search(
            [('mail_message_id', 'in', messages.ids)]).res_partner_id
        self.assertIn(self.lead_a.partner_id, notified)
        self.assertIn(self.eng_a2.partner_id, notified)
        self.assertNotIn(self.eng_a1.partner_id, notified)

    def test_changes_outside_teams_are_unchanged(self):
        task = self.env['project.task'].create({
            'name': 'Livre', 'project_id': self.project_free.id})
        task.write({'priority': '1'})
        self.flush_tracking()
        subtype = self.env.ref('project_sprint.mt_team_update_project_task')
        self.assertFalse(task.message_ids.filtered(lambda m: m.subtype_id == subtype))

    # ---------------------- sprints ----------------------
    def test_sprint_start_notifies_the_team(self):
        before = self.sprint_a.message_ids
        self.sprint_a.with_user(self.lead_a).action_start()
        notified = self.team_notifications(self.sprint_a, since=before)
        self.assertIn(self.eng_a1.partner_id, notified)
        self.assertIn(self.eng_a2.partner_id, notified)
        self.assertNotIn(self.lead_a.partner_id, notified)
        self.assertNotIn(self.eng_b1.partner_id, notified)

    def test_new_sprint_notifies_the_team(self):
        today = fields.Date.context_today(self.env['project.sprint'])
        sprint = self.env['project.sprint'].with_user(self.lead_a).create({
            'project_id': self.project_a.id,
            'date_start': today, 'date_end': today + timedelta(days=7)})
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(sprint))

    def test_adding_and_removing_tasks_notifies_the_team(self):
        self.sprint_a.with_user(self.lead_a).write({
            'task_ids': [Command.link(self.task_a_free.id)]})
        self.sprint_a.with_user(self.lead_a).write({
            'task_ids': [Command.unlink(self.task_a1.id)]})
        self.flush_tracking()
        bodies = ' '.join(self.sprint_a.message_ids.mapped('body'))
        self.assertIn('Tarefas adicionadas: Tarefa sem responsável', bodies)
        self.assertIn('Tarefas removidas: Tarefa de A1', bodies)
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(self.sprint_a))

    def test_deadline_cron_alerts_the_team(self):
        today = fields.Date.context_today(self.env['project.sprint'])
        self.sprint_a.write({
            'state': 'active', 'date_start': today - timedelta(days=13),
            'date_end': today + timedelta(days=1)})
        self.env['project.sprint']._cron_deadline_alerts()
        self.flush_tracking()
        bodies = ' '.join(self.sprint_a.message_ids.mapped('body'))
        self.assertIn('termina amanhã', bodies)
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(self.sprint_a))
        # sprint de outra equipa não é afetado
        self.assertNotIn('termina amanhã', ' '.join(self.sprint_b.message_ids.mapped('body')))

    # ---------------------- equipa ----------------------
    def test_member_changes_are_announced_to_the_team(self):
        newcomer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Novo', 'login': 'novo', 'email': 'novo@test.local',
            'notification_type': 'inbox',
            'groups_id': [Command.link(self.env.ref('project.group_project_user').id)]})
        role = self.env.ref('project_sprint.role_backend')
        self.team_a.with_user(self.lead_a).write({
            'member_ids': [Command.create({'user_id': newcomer.id, 'role_id': role.id})]})
        self.flush_tracking()
        bodies = ' '.join(self.team_a.message_ids.mapped('body'))
        self.assertIn('Novo entrou na equipa', bodies)
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(self.team_a))
        # o novo membro passa a ver o que é da equipa
        self.assertIn(newcomer.partner_id, self.project_a.message_partner_ids)
        self.assertIn(newcomer.partner_id, self.task_a1.message_partner_ids)
        self.assertIn(newcomer.partner_id, self.sprint_a.message_partner_ids)
        self.assertIn(self.project_a, self.env['project.project'].with_user(newcomer).search([]))

    def test_removed_member_stops_following_and_seeing(self):
        self.team_a.member_ids.filtered(lambda m: m.user_id == self.eng_a2).unlink()
        partner = self.eng_a2.partner_id
        self.assertNotIn(partner, self.project_a.message_partner_ids)
        self.assertNotIn(partner, self.sprint_a.message_partner_ids)
        self.assertNotIn(partner, self.team_a.message_partner_ids)
        # continua a ver a tarefa que lhe está atribuída, mas já não o projeto
        self.assertNotIn(self.project_a, self.env['project.project'].with_user(
            self.eng_a2).search([]))
        self.assertIn(self.task_a2, self.env['project.task'].with_user(
            self.eng_a2).search([('id', '=', self.task_a2.id)]))

    def test_changing_the_lead_changes_who_is_notified(self):
        self.team_a.member_ids.filtered(lambda m: m.user_id == self.eng_a2).unlink()
        self.team_a.lead_id = self.eng_a2
        self.assertIn(self.eng_a2.partner_id, self.project_a.message_partner_ids)
        self.assertNotIn(self.lead_a.partner_id, self.project_a.message_partner_ids)
        self.assertNotIn(self.lead_a.partner_id, self.task_a1.message_partner_ids)

    def test_changing_the_project_team_moves_the_followers(self):
        self.project_a.team_id = self.team_b
        self.assertEqual(self.project_a.privacy_visibility, 'followers')
        self.assertIn(self.eng_b1.partner_id, self.project_a.message_partner_ids)
        self.assertIn(self.eng_b1.partner_id, self.task_a1.message_partner_ids)
        self.assertNotIn(self.eng_a2.partner_id, self.project_a.message_partner_ids)
        self.assertNotIn(self.eng_a2.partner_id, self.sprint_a.message_partner_ids)
        # eng_a1 continua a ver a sua tarefa atribuída, mas já não o projeto
        self.assertNotIn(self.project_a, self.env['project.project'].with_user(
            self.eng_a1).search([]))

    def test_sync_followers_button_restores_subtypes(self):
        self.task_a1.message_unsubscribe(partner_ids=self.eng_a1.partner_id.ids)
        self.team_a.action_sync_followers()
        self.assertIn(self.eng_a1.partner_id, self.task_a1.message_partner_ids)

    def test_no_message_when_tracking_is_disabled(self):
        today = fields.Date.context_today(self.env['project.sprint'])
        sprint = self.env['project.sprint'].with_context(tracking_disable=True).create({
            'project_id': self.project_a.id,
            'date_start': today, 'date_end': today + timedelta(days=7)})
        self.flush_tracking()
        subtype = self.env.ref('project_sprint.mt_team_update_project_sprint')
        self.assertFalse(sprint.message_ids.filtered(lambda m: m.subtype_id == subtype))
