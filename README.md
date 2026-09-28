<!--
██████╗ ██████╗  █████╗     ██████╗ ██████╗  █████╗ ██████╗  ██████╗ 
██╔══██╗██╔══██╗██╔══██╗    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗
██║  ██║██████╔╝███████║    ██████╔╝██████╔╝███████║██████╔╝██║   ██║
██║  ██║██╔══██╗██╔══██║    ██╔══██╗██╔══██╗██╔══██║██╔══██╗██║   ██║
██████╔╝██████╔╝██║  ██║    ██████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝
╚═════╝ ╚═════╝ ╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ 
  MySQL Shell Extension · v2.0
-->

# DBA BRABO

> **MySQL Shell Extension** que exporta usuários, roles e privilégios em SQL
> idempotente — sem dependências externas, pronto para Git, seguro para replay
> entre ambientes (dev → staging → prod).

[![Version](https://img.shields.io/badge/version-2.0-blueviolet)](#changelog)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MySQL Shell](https://img.shields.io/badge/MySQL%20Shell-8.0%2B-blue)](#compatibilidade)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%20%7C%209.4-orange)](#compatibilidade)
[![Status](https://img.shields.io/badge/status-beta-orange)](#roadmap)

---

## Por que existe

Migrar usuários, roles e grants entre ambientes sempre foi doloroso:

- **`mysqldump --all-databases`** — não exporta usuários/grants de forma limpa
- **`mysqlpump`** — deprecado, não cobre roles direito (8.0+)
- **Percona Toolkit** (`pt-show-grants`) — exige instalação externa ao Shell
- **Scripts caseiros** — raramente idempotentes, difíceis de versionar

O **DBA BRABO** resolve isso dentro do próprio MySQL Shell, em Python puro,
com **zero dependências externas**.

A partir da **v2.0**, a extensão também gera um **Security Metadata Dump**
estruturalmente compatível com `util.dumpInstance()`, reaproveitando o
manifesto `@.json` quando o diretório já contém um dump do Shell.

---

## Instalação

```bash
mkdir -p ~/.mysqlsh/init.d
cp brabo.py ~/.mysqlsh/init.d/brabo.py
# reabra o MySQL Shell
```

Ao abrir o Shell você verá:

```
DBA BRABO extension v2.0 loaded. Type brabo.help() for usage.
```

---

## Quick Start

### v1.1 — Export em arquivo SQL único (legado, ainda suportado)

```python
brabo.export_grants()                                       # stdout
brabo.export_grants(output="~/backup/grants.sql")           # arquivo
brabo.export_grants(user="app")                             # filtra user
brabo.export_grants(host="%")                               # filtra host
brabo.export_grants(include_alter=True, output="~/sync.sql")# modo sync
brabo.roles()                                               # lista roles
```

### v2.0 — Security Metadata Dump (compatível com `util.dumpInstance`)

```python
# Gera um dump completo de segurança
brabo.dumpSecurityMetadata(output="/backup/prod")

# Gera só uma parte
brabo.dumpUsers("/backup/prod")
brabo.dumpRoles("/backup/prod")
brabo.dumpGrants("/backup/prod")
brabo.dumpSecurity("/backup/prod")

# Inclui contas de sistema (mysql.sys, mysql.session, mysql.infoschema)
brabo.dumpSecurityMetadata(output="/backup/prod", include_system=True)

# Ajuda inline
brabo.help()
```

---

## Comandos

### v1.1 — Export legado (arquivo único)

| Comando | Descrição |
|---|---|
| `brabo.help()` | Ajuda inline completa |
| `brabo.export_grants()` | Exporta `CREATE USER` + `ALTER USER` + `GRANT`s |
| `brabo.export_grants(user="app")` | Filtra por usuário |
| `brabo.export_grants(host="%")` | Filtra por host |
| `brabo.export_grants(output="~/grants.sql")` | Grava em arquivo |
| `brabo.export_grants(include_alter=True)` | Modo sincronização |
| `brabo.roles()` | Lista roles e seus privilégios |

**Parâmetros de `export_grants()`**

| Parâmetro | Default | Descrição |
|---|---|---|
| `user` | `None` | Filtra por usuário |
| `host` | `None` | Filtra por host |
| `output` | `None` | Caminho do arquivo (aceita `~`) |
| `include_create` | `True` | Emite `CREATE USER IF NOT EXISTS` |
| `include_alter` | `False` | Emite `ALTER USER` (modo sync) |
| `include_grants` | `True` | Emite `GRANT`s |
| `include_system` | `False` | Inclui `mysql.sys`, `mysql.session`, ... |

### v2.0 — Security Metadata Dump

| Comando | Descrição |
|---|---|
| `brabo.dumpSecurityMetadata(output, ...)` | Gera dump completo (todos os arquivos + manifesto) |
| `brabo.dumpUsers(output, include_system=False)` | Gera apenas `@.users.sql` |
| `brabo.dumpRoles(output)` | Gera apenas `@.roles.sql` |
| `brabo.dumpGrants(output, include_system=False)` | Gera apenas `@.grants.sql` |
| `brabo.dumpSecurity(output, include_system=False)` | Gera apenas `@.security.json` |

**Parâmetros de `dumpSecurityMetadata()`**

| Parâmetro | Default | Descrição |
|---|---|---|
| `output` | — | Diretório destino (obrigatório) |
| `include_system` | `False` | Inclui contas internas |
| `include_users` | `True` | Gera `@.users.sql` |
| `include_roles` | `True` | Gera `@.roles.sql` |
| `include_grants` | `True` | Gera `@.grants.sql` |
| `include_inventory` | `True` | Gera `@.security.json` |

---

## Estrutura do Security Metadata Dump

Compatível com o layout gerado por `util.dumpInstance()`:

```
/backup/prod/
├── @.json              ← manifesto (lido/atualizado, nunca sobrescrito)
├── @.users.sql         ← CREATE USER + ALTER USER (idempotente)
├── @.roles.sql         ← CREATE ROLE + grants de role
├── @.grants.sql        ← GRANTs por conta
└── @.security.json     ← inventário (contadores + plugins + flags)
```

### Regras do manifesto `@.json`

Quando o diretório já contém um `@.json` gerado por `util.dumpInstance()`,
a extensão:

1. **Lê** o manifesto existente
2. **Reaproveita** `origin`, `serverVersion`, `gtidExecuted`, `charset`,
   `creationTime`
3. **Apenas adiciona** chaves próprias (`securityMetadata`,
   `securityMetadataVersion`, `securityLastUpdate`)
4. **Nunca toca** em `schemas`, `users`, `snapshot` ou qualquer chave do Shell

---

## Integração com `util.dumpInstance()`

```python
# 1. Faz o dump normal do Shell
util.dumpInstance("/backup/prod")

# 2. Complementa com o dump de segurança
brabo.dumpSecurityMetadata(output="/backup/prod")

# 3. Valida que o Shell ainda lê o dump sem erros
util.loadDump("/backup/prod", dryRun=True)
```

Se o passo 3 rodar sem reclamação do `@.json`, a integração está correta.

---

## Exemplo de saída

### `@.users.sql`

```sql
-- DBA BRABO · users dump
-- Generated: 2026-09-28 10:00:00
-- Users    : 3

-- USER 'app'@'%'
CREATE USER IF NOT EXISTS 'app'@'%'
IDENTIFIED WITH caching_sha2_password
AS '$A$005$HASH';
ALTER USER 'app'@'%'
IDENTIFIED WITH caching_sha2_password
AS '$A$005$HASH';
```

### `@.grants.sql`

```sql
-- GRANTS 'app'@'%'
GRANT SELECT, INSERT ON ERP.* TO 'app'@'%';
GRANT EXECUTE ON PROCEDURE ERP.sp_vendas TO 'app'@'%';
```

### `@.security.json`

```json
{
  "users": 148,
  "roles": 12,
  "accounts_locked": 3,
  "ssl_required": 98,
  "plugins": {
    "caching_sha2_password": 140,
    "mysql_native_password": 8
  },
  "generated_at": "2026-09-28T10:00:00",
  "generator": "dba-brabo v2.0"
}
```

---

## Segurança

- ✅ Queries parametrizadas via `session.run_sql(sql, args)`
- ✅ Escaping explícito de `user`/`host` ao montar `'user'@'host'`
- ✅ **Read-only** — a extensão nunca escreve no servidor
- ✅ Usuários de sistema excluídos por padrão
- ✅ Manifesto `@.json` existente é preservado (chaves do Shell nunca
  são sobrescritas)
- ✅ Nenhuma credencial é logada ou gravada

---

## Compatibilidade

| Versão | Status |
|---|---|
| MySQL 8.0.x | ✅ Testado |
| MySQL 9.4.0 | ✅ Testado |
| MySQL 5.7 | ⏳ Pendente (`SHOW CREATE USER` existe desde 5.7.6) |
| MariaDB | ❌ Não suportado (schema de `mysql.user` diferente) |

**Requisitos:** MySQL Shell 8.0+ em modo Python.

---

## Roadmap

| Versão | Escopo |
|---|---|
| **v1.1** | `export_grants()`, `roles()`, `help()`, escaping seguro |
| **v2.0** *(atual)* | `dumpSecurityMetadata()`, manifesto `@.json`, integração com `util.dumpInstance()`, inventário JSON |
| **v2.1** | `brabo.grants.diff()`, `brabo.security.audit()` |
| **v3.0** | Migração para a API oficial de extensões do Shell (`shell.register_extension()`) |
| **RFC** | Proposta upstream de `util.dumpInstance(users=True, roles=True, grants=True)` e `util.loadDump(loadUsers=True)` |

---

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md). PRs são bem-vindos, especialmente
testes em MySQL 5.7 e MariaDB.

Áreas que precisam de ajuda:

- Testes em **MySQL 5.7**
- Testes em **MariaDB** (para eventual suporte)
- Testes automatizados (pytest + mock da sessão do Shell)
- Migração para a API oficial de extensões
- Validação do formato `@.json` em diferentes versões do MySQL Shell

---

## Licença

[MIT](LICENSE) © Acacio LR

---

## Referências

- [MySQL Shell Utilities](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities.html)
- [`util.dumpInstance()`](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities-dump-instance-schema.html)
- [`util.loadDump()`](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities-load-dump.html)
- [`util.checkForServerUpgrade()`](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities-upgrade.html)
- [MySQL Shell Extension API](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-extensions.html)
- [Percona Toolkit `pt-show-grants`](https://www.percona.com/doc/percona-toolkit/LATEST/pt-show-grants.html)
