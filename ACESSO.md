# Acesso

## Domínios (produção)
`https://$DOMAIN` serve a SPA (nginx); `https://$DOMAIN/api/v1/*` vai para a API (prioridade maior no Traefik). O callback `/internal/ia/callback` **não** é roteado publicamente.

## Primeiro acesso do Master
1. Copie `.env.example` para `.env`, ajuste `MASTER_EMAIL` e execute `make keys`. O comando gera `MASTER_PASSWORD` se estiver vazio (ou preserve a senha que você definiu com ≥ 12 caracteres); guarde-a em um cofre.
2. `make migrate && make seed` cria o usuário Master (ativo).
3. Entre em `/entrar`: senha + código de 6 dígitos enviado ao e-mail. Troque a senha em seguida (Perfil).
4. **Clientes → Nova empresa**: valida o CNPJ, cria a chave de dados da empresa e envia o convite ao administrador (link válido por 72 h, defina a senha com ≥ 12 caracteres).

## Perfis
| Perfil | Quem | Faz |
|---|---|---|
| **Master** | operador da plataforma | empresas, planos, cotas, catálogo, operação da IA, auditoria global (com motivo). **Não lê** documentos; só com *acesso de suporte* aprovado pelo admin da empresa, e então só cópias anonimizadas |
| **Administrador da empresa** | cliente | cargos, matriz de obrigatoriedade, usuários RH, retenção, plano, auditoria, logs; vê dados de saúde |
| **RH** | operacional | envia lotes, busca, revisa e completa pré-cadastros gerados pelos documentos. Dados de saúde só com a permissão `saude:ler`; pode ter escopo por unidade |

## Criar usuários
- Admin da empresa → **Configurações → Usuários RH → Convidar**. O e-mail precisa ser de um **domínio permitido** (Configurações → Empresa e unidades). Mudar permissões ou domínios pede novo código por e-mail (*step-up*).
- Master → **Usuários Master → Convidar**.

## Dados de demonstração (`SEED_DEMO=true`, só dev)
Empresa **Agrotech Garanhuns** (CNPJ fictício válido). Senha de todos: `Demo!Citadel#2026`.

| E-mail | Perfil |
|---|---|
| `admin@agrotech.demo` | Administrador |
| `rh@agrotech.demo` | RH com `saude:ler` |
| `rh2@agrotech.demo` | RH sem acesso a saúde |
| `master@citadel.local` (senha `MASTER_PASSWORD`; dev: `Citadel!Master#2026`) | Master |
