# Project Sprints — Odoo 18

Módulo `project_sprint` para o desafio *much. Consulting — Software Engineering Challenge*:
sprints para as equipas de engenharia, construído em cima da app **Projeto** do Odoo 18.

## Correr o projeto

Precisas de Docker + Docker Compose.

```bash
cp .env.example .env     # só na primeira vez (valores de desenvolvimento)
docker compose up -d     # cria a base de dados "sprints" e instala o módulo
```

Abre <http://localhost:8069> e entra com o administrador. Menu **Sprints** (canto superior esquerdo).

### Dados de demonstração (3 equipas, 5 projetos, 9 sprints, 8 milestones, 42 tarefas, 11 utilizadores)

```bash
docker compose cp scripts/seed_demo.py odoo:/tmp/seed_demo.py
docker compose exec odoo bash -c "odoo shell -d sprints --db_host=db --db_user=odoo --db_password=odoo --no-http < /tmp/seed_demo.py"
```

(Funciona em bash, cmd e PowerShell: a redireção `<` acontece dentro do contentor.)
O script só cria os dados se ainda não existirem, por isso pode correr-se mais do que uma vez.

### Utilizadores de demonstração

Todos com o domínio `@demo.local` e a palavra-passe **demo** (só para ambiente local; para usar outra,
corre o segundo comando com `docker compose exec -e DEMO_PASSWORD=... odoo bash -c "..."`).
Dica: abre uma janela anónima por utilizador para mostrar as diferenças de permissões lado a lado.

| Utilizador | Papel | Equipa |
|---|---|---|
| `ana.costa` | Líder | Backend |
| `bruno.silva`, `carla.mendes`, `diogo.ramos` | Engenheiros | Backend |
| `eduardo.faria` | Líder | Frontend |
| `filipa.rocha`, `goncalo.pinto`, `helena.duarte` | Engenheiros | Frontend |
| `ines.moreira` | Líder | DevOps e QA |
| `joao.lopes`, `katia.nunes` | Engenheiros | DevOps e QA |

O utilizador administrador do Odoo é **gestor**: vê e edita tudo.

### Testes automáticos

```bash
docker compose exec odoo odoo -d sprints_test -i project_sprint --test-enable --test-tags /project_sprint --stop-after-init --http-port=8070 --db_host=db --db_user=odoo --db_password=odoo
docker compose exec db dropdb -U odoo sprints_test
```

(a segunda linha apaga a base de dados de testes)

São 52 testes (sprints, permissões, notificações e milestones). Usam uma base de dados à parte,
por isso não mexem nos dados da demo.

### Começar do zero

```bash
docker compose down -v   # apaga a base de dados e os ficheiros do Odoo
docker compose up -d
```

> Se já tinhas dados de uma versão anterior, abre cada **Equipa** e carrega em **Sincronizar seguidores**
> (só gestores): aplica as regras de visibilidade e as notificações aos projetos, sprints e tarefas que já existiam.

## O que o módulo faz

| Menu | Descrição |
|---|---|
| **As minhas tarefas** | As tarefas atribuídas a mim em sprints planeados ou ativos, ordenadas por prazo (`Faltam 4 d`, `Em atraso 3 d`). |
| **Sprints** | Lista, kanban (por estado) e gráfico de pontos. O formulário mostra progresso, tarefas, milestone e botões Iniciar/Fechar. |
| **Board** | Kanban das tarefas por etapa, de todos os sprints ativos ou de um só (botão **Board** no sprint). **Só líderes e gestores arrastam.** |
| **Milestones** | Marcos dos projetos da equipa. Um sprint pode apontar para um milestone e avisa se acabar depois do prazo. |
| **Equipas** | Equipas com líder, membros e funções (as funções formam uma hierarquia configurável). |

Regras de negócio dos sprints: um sprint ativo por projeto; as tarefas só podem estar em sprints do
seu projeto; uma tarefa pode passar por vários sprints; ao fechar um sprint com tarefas por concluir,
um assistente pergunta se vão para outro sprint ou voltam ao backlog; o progresso conta pontos de
esforço (ou tarefas, se não houver pontos); tarefas canceladas não contam.

## Permissões

| | Gestor | Líder da equipa | Engenheiro |
|---|---|---|---|
| Ver projetos, tarefas, sprints, milestones e equipa | tudo | só da sua equipa | só da sua equipa |
| Criar, iniciar, fechar e editar sprints | ✔ | da sua equipa | ✘ (só vê) |
| **Reordenar o board** (arrastar) | ✔ | da sua equipa | ✘ (só vê) |
| Criar e editar milestones | ✔ | da sua equipa | ✘ (só vê) |
| Editar tarefas | todas | todas as da equipa | as que lhe estão atribuídas ou que criou |
| Comentar tarefas | ✔ | ✔ | ✔ (inclusive nas dos colegas) |
| Gerir membros e funções da equipa | ✔ | da sua equipa | ✘ |
| Criar equipas | ✔ | ✘ | ✘ |

Projetos sem equipa mantêm o comportamento normal do Odoo.

## Notificações

Sempre que alguém mexe em algo que pertence a uma equipa, o líder e os membros recebem um aviso
na caixa de entrada do Odoo (ícone de mensagens), exceto quem fez a alteração:

- **Tarefas:** mudança de etapa, responsável, prazo, pontos, sprint, projeto, etc.
- **Sprints:** criação, início/fecho, datas, milestone, tarefas adicionadas ou removidas.
- **Milestones:** criação e alterações (nome, prazo, atingido).
- **Equipa:** entrada, saída e mudança de função de membros; mudança de líder.
- **Alertas automáticos** (tarefa agendada diária): sprint que termina amanhã ou que ficou em atraso.

Quem tiver um servidor de email de saída configurado e a preferência "Email" no seu perfil também
recebe por email.

## Decisões técnicas (para a defesa)

- **Equipas = seguidores.** A visibilidade usa o mecanismo nativo do Odoo: os projetos de uma equipa
  ficam com privacidade "Seguidores" e a equipa é subscrita nos projetos, sprints e tarefas. Isto dá,
  com o mesmo mecanismo, o filtro de visibilidade (regras nativas) *e* a lista de quem é notificado.
  Os seguidores sincronizam-se sozinhos quando muda a equipa, o líder, os membros ou o projeto.
- **Regras de acesso (`security/security.xml`).** As regras de grupo somam-se (OU) e as globais
  restringem (E). Por isso a leitura é dada por regras de grupo (cada um vê a sua equipa) e a edição
  de tarefas e milestones por regras globais com exceção do gestor. As permissões de escrita ficam
  também na base de dados, não só na interface.
- **Arrastar no board.** A vista "só leitura" tem `records_draggable="false"`; a ação do menu escolhe a
  vista certa consoante o utilizador. Como esconder na interface não é segurança, o `write` da tarefa
  recusa alterações de `sequence` a quem não é líder da equipa nem gestor (`_check_can_reorder`).
- **Vistas por papel.** Uma vista que herda de outra não pode ter `groups`; por isso há vistas
  primárias (`mode="primary"`) para a versão só leitura e a ação escolhe qual abrir.
- **Notificações com `mail.thread`.** Em vez de criar um modelo de notificações novo, usa-se o chatter e
  subtipos de mensagem. Por omissão o Odoo só avisa de algumas mudanças (as outras ficam em silêncio no
  histórico); o mixin `project.team.notify.mixin` faz com que todas as alterações rastreadas avisem a equipa.
- **Estrutura.** `deadline_mixin` (prazos, partilhado por tarefa e sprint) e `team_notify_mixin`
  (notificações) evitam código repetido; cada modelo só diz de que equipa é (`_get_notify_team`).

## Estrutura

```
addons/project_sprint/
├── models/      sprint, tarefa, projeto, equipa, milestone, mixins (prazos e notificações)
├── security/    grupos, regras de acesso (security.xml) e permissões por modelo (ir.model.access.csv)
├── views/       sprints, board, as minhas tarefas, milestones, equipas, tarefas e projetos
├── data/        funções, tipos de mensagem da equipa, tarefa agendada de alertas
├── wizard/      assistente de fecho de sprint
├── tests/       52 testes automáticos
└── static/      estilos
scripts/seed_demo.py   dados de demonstração
```

## Limitações e próximos passos

- Os textos do módulo estão em português e os do Odoo em inglês (sem ficheiros de tradução `.po`).
- Não há burndown/velocity; o gráfico mostra pontos totais e concluídos por projeto.
- Os alertas de prazo correm uma vez por dia (tarefa agendada do Odoo).
