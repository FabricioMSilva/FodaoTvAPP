# Configuração do Supabase

## 1. Criar a estrutura

No Supabase Dashboard, abra **SQL Editor → New query**, copie o conteúdo de
`migrations/20260624_000001_initial_catalog.sql`, execute e confirme que não há erros.

## 2. Tornar seu usuário administrador

No SQL Editor, execute a instrução abaixo, substituindo pelo e-mail do usuário criado em Authentication:

```sql
update public.profiles
set role = 'admin'
where email = 'seu-email@exemplo.com';
```

## 3. Gerar a configuração local do app

Na raiz do projeto, com `.env` preenchido:

```powershell
npm run supabase:config
```

O comando cria `frontend/supabase-config.js`; ele contém somente a chave publicável e é ignorado pelo Git.

## 4. Sincronizar o Android

```powershell
npm run android:sync
```

## 5. Importar o catálogo atual

Depois de executar a migration e marcar seu perfil como administrador, importe o catálogo local:

```powershell
python tools/import_catalog_to_supabase.py
```

O comando usa a chave administrativa apenas no computador e envia os grupos e links de
`output_extracao/` para o Supabase. Esse diretório continua ignorado pelo Git.

## Segurança

- Nunca exponha a `SUPABASE_SERVICE_ROLE_KEY`.
- As regras RLS deixam usuários autenticados lerem apenas o catálogo ativo e seus próprios favoritos.
- Apenas perfis com `role = 'admin'` podem alterar usuários e links.
