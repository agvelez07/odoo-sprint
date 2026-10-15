def seed(env):
    import os
    from datetime import date, timedelta
    from odoo import Command

    # Palavra-passe dos utilizadores de demonstração (só para ambiente local).
    # Para usar outra: docker compose exec -T -e DEMO_PASSWORD=... odoo odoo shell ...
    demo_password = os.environ.get('DEMO_PASSWORD', 'demo')

    # Sem mensagens nem emails durante a criação dos dados: a caixa de entrada
    # fica limpa para mostrar as notificações reais na demo.
    env = env(context=dict(
        env.context, tracking_disable=True, no_reset_password=True,
        mail_auto_subscribe_no_notify=True, mail_create_nosubscribe=False))
    today = date.today()

    def day(n):
        return today + timedelta(days=n)

    Team = env['project.team']
    if Team.search([('name', '=', 'Equipa Backend')]):
        print('Dados de demo já existem. Nada feito.')
        return

    group_user = env.ref('project.group_project_user')
    group_lead = env.ref('project_sprint.group_team_lead')

    def role(xmlid):
        return env.ref('project_sprint.' + xmlid)

    def make_user(name, login, lead=False):
        user = env['res.users'].search([('login', '=', login)], limit=1)
        if user:
            return user
        groups = [Command.link(group_user.id)]
        if lead:
            groups.append(Command.link(group_lead.id))
        return env['res.users'].create({
            'name': name, 'login': login, 'email': login, 'groups_id': groups,
            'password': demo_password,
            # notificações na caixa de entrada do Odoo (sem precisar de servidor de email)
            'notification_type': 'inbox',
        })

    # ---------- Utilizadores ----------
    ana = make_user('Ana Costa', 'ana.costa@demo.local', lead=True)
    bruno = make_user('Bruno Silva', 'bruno.silva@demo.local')
    carla = make_user('Carla Mendes', 'carla.mendes@demo.local')
    diogo = make_user('Diogo Ramos', 'diogo.ramos@demo.local')
    eduardo = make_user('Eduardo Faria', 'eduardo.faria@demo.local', lead=True)
    filipa = make_user('Filipa Rocha', 'filipa.rocha@demo.local')
    goncalo = make_user('Gonçalo Pinto', 'goncalo.pinto@demo.local')
    helena = make_user('Helena Duarte', 'helena.duarte@demo.local')
    ines = make_user('Inês Moreira', 'ines.moreira@demo.local', lead=True)
    joao = make_user('João Lopes', 'joao.lopes@demo.local')
    katia = make_user('Kátia Nunes', 'katia.nunes@demo.local')

    # ---------- Equipas ----------
    def make_team(name, lead, members):
        return Team.create({
            'name': name,
            'lead_id': lead.id,
            'member_ids': [Command.create({'user_id': u.id, 'role_id': role(r).id})
                           for u, r in members],
        })

    backend = make_team('Equipa Backend', ana, [
        (bruno, 'role_backend'), (carla, 'role_backend'), (diogo, 'role_tech_lead')])
    frontend = make_team('Equipa Frontend', eduardo, [
        (filipa, 'role_frontend'), (goncalo, 'role_frontend'), (helena, 'role_engineer')])
    devops = make_team('Equipa DevOps e QA', ines, [
        (joao, 'role_engineer'), (katia, 'role_tech_lead')])

    # ---------- Projetos ----------
    stages = env['project.task.type'].create([
        {'name': name, 'sequence': i}
        for i, name in enumerate(['Por Fazer', 'Em curso', 'Feito'])])

    def make_project(name, team):
        return env['project.project'].create({
            'name': name, 'team_id': team.id, 'allow_milestones': True,
            'type_ids': [Command.set(stages.ids)]})

    pagamentos = make_project('Plataforma de Pagamentos', backend)
    gateway = make_project('API Gateway', backend)
    portal = make_project('Portal do Cliente', frontend)
    mobile = make_project('App Mobile', frontend)
    cloud = make_project('Infraestrutura Cloud', devops)

    # ---------- Sprints e tarefas ----------
    Sprint = env['project.sprint']
    Task = env['project.task']

    Milestone = env['project.milestone']

    def make_milestone(project, name, deadline, reached=False):
        return Milestone.create({
            'name': name, 'project_id': project.id,
            'deadline': day(deadline), 'is_reached': reached})

    def make_sprint(project, name, start, end, state, goal, milestone=None):
        return Sprint.create({
            'name': name, 'project_id': project.id, 'goal': goal,
            'date_start': day(start), 'date_end': day(end), 'state': state,
            'milestone_id': milestone.id if milestone else False})

    status_map = {
        'todo': (0, '01_in_progress'),
        'doing': (1, '01_in_progress'),
        'done': (2, '1_done'),
        'cancel': (0, '1_canceled'),
    }

    def make_tasks(project, specs):
        # (nome, pontos, estado, responsável, [sprints], prazo em dias)
        for name, points, status, user, sprints, deadline in specs:
            stage_idx, state = status_map[status]
            Task.create({
                'name': name,
                'project_id': project.id,
                'stage_id': stages[stage_idx].id,
                'state': state,
                'effort_points': points,
                'user_ids': [Command.set([user.id])] if user else [],
                'sprint_ids': [Command.set([s.id for s in sprints])],
                'date_deadline': day(deadline) if deadline is not None else False,
            })

    # Plataforma de Pagamentos
    ms_fund = make_milestone(pagamentos, 'Fundações concluídas', -14, reached=True)
    ms_mvp = make_milestone(pagamentos, 'MVP de pagamentos', 6)
    ms_golive = make_milestone(pagamentos, 'Go-live MB Way', 25)
    p1 = make_sprint(pagamentos, 'Sprint 1', -28, -15, 'closed', 'Fundações do módulo de pagamentos', ms_fund)
    p2 = make_sprint(pagamentos, 'Sprint 2', -10, 4, 'active', 'Reembolsos e auditoria', ms_mvp)
    p3 = make_sprint(pagamentos, 'Sprint 3', 5, 19, 'planned', 'MB Way e contabilidade', ms_golive)
    make_tasks(pagamentos, [
        ('Modelar entidades de pagamento', 5, 'done', bruno, [p1], -18),
        ('Integrar gateway Multibanco', 8, 'done', carla, [p1], -16),
        ('Webhooks de confirmação', 3, 'done', bruno, [p1], -15),
        ('Testes de carga básicos', 3, 'cancel', diogo, [p1], -15),
        ('Reconciliação diária', 5, 'doing', diogo, [p1, p2], 3),
        ('Reembolsos parciais', 5, 'done', carla, [p2], -2),
        ('Notificações por email', 3, 'doing', bruno, [p2], 2),
        ('Auditoria de transações', 8, 'doing', carla, [p2], 4),
        ('Dashboard de erros', 5, 'todo', diogo, [p2], 4),
        ('Rate limiting', 3, 'todo', bruno, [p2], 4),
        ('Suporte a MB Way', 8, 'todo', None, [p3], 18),
        ('Exportação contabilística', 5, 'todo', None, [p3], 19),
        ('Documentação da API', 2, 'todo', None, [], None),
        ('Revisão de segurança PCI', 8, 'todo', None, [], None),
    ])

    # API Gateway (sprint em atraso)
    # o milestone venceu antes do fim do sprint: aparece "em risco"
    ms_beta = make_milestone(gateway, 'Gateway beta', -5)
    g1 = make_sprint(gateway, 'Sprint 1', -20, -3, 'active', 'Gateway mínimo viável', ms_beta)
    make_tasks(gateway, [
        ('Autenticação OAuth2', 8, 'done', bruno, [g1], -8),
        ('Roteamento dinâmico', 8, 'doing', carla, [g1], -3),
        ('Cache de respostas', 5, 'todo', diogo, [g1], -3),
        ('Métricas Prometheus', 3, 'doing', bruno, [g1], -3),
        ('Logs estruturados', 2, 'done', carla, [g1], -10),
        ('Circuit breaker', 5, 'todo', None, [], None),
    ])

    # Portal do Cliente
    ms_portal = make_milestone(portal, 'Portal v1', 12)
    c1 = make_sprint(portal, 'Sprint 1', -24, -11, 'closed', 'Base do portal', ms_portal)
    c2 = make_sprint(portal, 'Sprint 2', -10, 9, 'active', 'Faturas e perfil', ms_portal)
    make_tasks(portal, [
        ('Layout base responsivo', 5, 'done', filipa, [c1], -14),
        ('Página de login', 3, 'done', goncalo, [c1], -12),
        ('Listagem de faturas', 5, 'done', filipa, [c1], -11),
        ('Pesquisa avançada', 5, 'doing', helena, [c1, c2], 6),
        ('Detalhe de fatura', 3, 'done', goncalo, [c2], -3),
        ('Download de PDF', 3, 'doing', filipa, [c2], 7),
        ('Perfil do utilizador', 5, 'todo', goncalo, [c2], 8),
        ('Modo escuro', 2, 'todo', helena, [c2], 9),
        ('Acessibilidade WCAG', 5, 'todo', helena, [c2], 9),
        ('Internacionalização', 5, 'todo', None, [], None),
    ])

    # App Mobile
    ms_proto = make_milestone(mobile, 'Protótipo aprovado', 20)
    m1 = make_sprint(mobile, 'Sprint 1', 3, 17, 'planned', 'Protótipo navegável', ms_proto)
    make_tasks(mobile, [
        ('Protótipo de navegação', 5, 'todo', None, [m1], 10),
        ('Autenticação biométrica', 8, 'todo', None, [m1], 14),
        ('Notificações push', 5, 'todo', None, [m1], 17),
        ('Publicar nas lojas', 3, 'todo', None, [], None),
    ])

    # Infraestrutura Cloud
    ms_pipe = make_milestone(cloud, 'Pipeline em produção', 1)   # em risco: o sprint acaba depois
    ms_res = make_milestone(cloud, 'Resiliência validada', 20)
    i1 = make_sprint(cloud, 'Sprint 1', -12, 2, 'active', 'Pipeline e monitorização', ms_pipe)
    i2 = make_sprint(cloud, 'Sprint 2', 3, 17, 'planned', 'Resiliência', ms_res)
    make_tasks(cloud, [
        ('Pipeline CI/CD', 8, 'done', joao, [i1], -6),
        ('Terraform da rede', 5, 'done', katia, [i1], -4),
        ('Monitorização', 5, 'doing', joao, [i1], 2),
        ('Backups automáticos', 3, 'done', katia, [i1], -1),
        ('Testes E2E', 5, 'todo', joao, [i1], 2),
        ('Autoscaling', 8, 'todo', None, [i2], 15),
        ('Disaster recovery', 5, 'todo', None, [i2], 17),
        ('Custos cloud', 3, 'todo', None, [], None),
    ])

    print('Demo criada: 3 equipas, 5 projetos, 9 sprints, 8 milestones, 42 tarefas, 11 utilizadores.')
    print('Líderes: ana.costa / eduardo.faria / ines.moreira (@demo.local).')
    print('Engenheiros: bruno.silva, carla.mendes, diogo.ramos, ... (@demo.local).')
    print('Palavra-passe de todos os utilizadores de demo: ver README (secção "Utilizadores de demonstração").')


seed(env)
env.cr.commit()