<!--
██████╗ ██████╗  █████╗     ██████╗ ██████╗  █████╗ ██████╗  ██████╗ 
██╔══██╗██╔══██╗██╔══██╗    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗
██║  ██║██████╔╝███████║    ██████╔╝██████╔╝███████║██████╔╝██║   ██║
██║  ██║██╔══██╗██╔══██║    ██╔══██╗██╔══██╗██╔══██║██╔══██╗██║   ██║
██████╔╝██████╔╝██║  ██║    ██████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝
╚═════╝ ╚═════╝ ╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ 
  MySQL Shell Extension · v2.2
-->

# DBA BRABO

> **MySQL Shell Extension** que exporta usuários, roles e privilégios em SQL
> idempotente, gera **REVOKEs** para rollback/auditoria e converte sintaxe
> **MariaDB → MySQL** — sem dependências externas, pronto para Git, seguro
> para replay entre ambientes (dev → staging → prod).

[![Version](https://img.shields.io/badge/version-2.2-blueviolet)](#changelog)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MySQL Shell](https://img.shields.io/badge/MySQL%20Shell-8.0%2B-blue)](#compatibilidade)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%20%7C%208.4%20%7C%209.4-orange)](#compatibilidade)
[![Status](https://img.shields.io/badge/status-beta-orange)](#roadmap)

---

## Por que existe

Migrar usuários, roles e grants entre ambientes sempre foi doloroso. O
`util.dumpInstance()` do MySQL Shell **já exporta** users/roles/grants por
padrão (desde a 8.0.21) e o `util.loadDump(loadUsers=true)` **já importa** de
volta. Mas ele **não cobre** todos os casos:

| Necessidade | `util.dumpInstance()` | **DBA BRABO** |
|---|---|---|
| Exportar tudo para um dump | ✅ sim | ✅ (v2.0) |
| SQL em **arquivo único** | ❌ só diretório | ✅ (v1.1) |
| SQL **idempotente** (`IF NOT EXISTS`) | ❌ não | ✅ |
| Filtrar por **um usuário/host** | ❌ só tudo | ✅ |
| Gerar **REVOKEs** (rollback) | ❌ não | ✅ (v2.1) |
| Converter **MariaDB → MySQL** | ❌ não | ✅ (v2.2) |
| Inventário JSON (plugins, locks, SSL) | ❌ não | ✅ (v2.0) |
| Ordenação determinística para Git | ⚠️ parcial | ✅ |

Ferramentas externas que tentavam resolver isso têm problemas próprios:

- **`mysqldump --all-databases`** — não exporta usuários/grants de forma limpa
- **`mysqlpump`** — deprecado, não cobre roles direito (8.0+)
- **Percona Toolkit** (`pt-show-grants`) — exige instalação externa ao Shell
- **Scripts caseiros** — raramente idempotentes, difíceis de versionar

O **DBA BRABO** preenche essas lacunas dentro do próprio MySQL Shell, em
Python puro, com **zero dependências externas**.

---

## Instalação

```bash
mkdir -p ~/.mysqlsh/init.d
cp brabo.py ~/.mysqlsh/init.d/brabo.py
# reabra o MySQL Shell
```

Ao abrir o Shell, carregue a extensão em modo Python:

```
\py
import sys
sys.path.insert(0, "/root/.mysqlsh/init.d")
from brabo import brabo
```

Você verá:

```
DBA BRABO extension v2.2 loaded. Type brabo.help() for usage.
```

> **Por que `from brabo import brabo` e não `import brabo`?**
> `import brabo` traz o *módulo*. A instância com os métodos está dentro
> dele. Use `from brabo import brabo` para pegar a instância pronta.

---

## Quick Start

### v1.1 — Export em arquivo SQL único

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
brabo.dumpSecurityMetadata(output="/backup/prod")           # dump completo
brabo.dumpSecurityMetadata(output="/backup/prod", include_system=True)
brabo.dumpUsers("/backup/prod")                             # só users
brabo.dumpRoles("/backup/prod")                             # só roles
brabo.dumpGrants("/backup/prod")                            # só grants
brabo.dumpSecurity("/backup/prod")                          # só inventário
```

### v2.1 — Modo REVOKE (rollback / auditoria)

```python
brabo.export_revokes(output="~/revokes_all.sql")            # tudo
brabo.export_revokes(user="acaciolr", output="~/revokes.sql") # um user
brabo.export_grants(mode="revoke")                          # via mode=
```

### v2.2 — Conversão MariaDB → MySQL

```python
brabo.export_grants(convert_mariadb=True, output="~/mysql.sql")
brabo.export_revokes(convert_mariadb=True, output="~/revokes.sql")
brabo.export_grants(user="app", convert_mariadb=True)       # combinado
```

---

## Comandos

### v1.1 — Export em arquivo único

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
| `mode` | `"grant"` | `"grant"` ou `"revoke"` |
| `convert_mariadb` | `False` | Converte sintaxe MariaDB → MySQL |
| `include_create` | `True` | Emite `CREATE USER IF NOT EXISTS` |
| `include_alter` | `False` | Emite `ALTER USER` (modo sync) |
| `include_grants` | `True` | Emite `GRANT`s (ou `REVOKE`s em modo revoke) |
| `include_system` | `False` | Inclui `mysql.sys`, `mysql.session`, ... |

### v2.0 — Security Metadata Dump

| Comando | Descrição |
|---|---|
| `brabo.dumpSecurityMetadata(output, ...)` | Gera dump completo (todos os arquivos + manifesto) |
| `brabo.dumpUsers(output, include_system=False)` | Gera apenas `@.users.sql` |
| `brabo.dumpRoles(output)` | Gera apenas `@.roles.sql` |
| `brabo.dumpGrants(output, include_system=False)` | Gera apenas `@.grants.sql` |
| `brabo.dumpSecurity(output, include_system=False)` | Gera apenas `@.security.json` |

### v2.1 — Modo REVOKE

| Comando | Descrição |
|---|---|
| `brabo.export_revokes()` | Gera `REVOKE` de todos os grants |
| `brabo.export_revokes(user="app")` | Filtra por usuário |
| `brabo.export_revokes(host="%")` | Filtra por host |
| `brabo.export_grants(mode="revoke")` | Equivalente ao atalho acima |

**Parâmetros de `export_revokes()`**

| Parâmetro | Default | Descrição |
|---|---|---|
| `user` | `None` | Filtra por usuário |
| `host` | `None` | Filtra por host |
| `output` | `None` | Caminho do arquivo (aceita `~`) |
| `convert_mariadb` | `False` | Converte sintaxe MariaDB → MySQL |
| `include_system` | `False` | Inclui contas de sistema |

### v2.2 — Conversão MariaDB → MySQL

Ative com `convert_mariadb=True` em `export_grants()` ou `export_revokes()`.

---

## Modo REVOKE

O modo revoke lê o `SHOW GRANTS` de cada conta e gera os `REVOKE`
correspondentes. Regras de conversão:

| GRANT original | REVOKE gerado |
|---|---|
| `GRANT SELECT ON ERP.* TO 'app'@'%'` | `REVOKE SELECT ON ERP.* FROM 'app'@'%';` |
| `GRANT 'role'@'%' TO 'app'@'%'` | `REVOKE 'role'@'%' FROM 'app'@'%';` |
| `GRANT PROXY ON 'x'@'%' TO 'app'@'%'` | `REVOKE PROXY ON 'x'@'%' FROM 'app'@'%';` |
| `GRANT ... WITH GRANT OPTION` | `REVOKE ...` + `REVOKE GRANT OPTION ON ... FROM ...;` |
| `GRANT USAGE ON *.*` | *(ignorado — USAGE é no-op)* |

### Ordem segura de aplicar

1. `REVOKE` das grants de **objetos** (`SELECT`, `INSERT`, `EXECUTE`, ...)
2. `REVOKE` dos **roles** atribuídos
3. `DROP USER` ou `DROP ROLE` (se for o caso)

A extensão emite na ordem em que o `SHOW GRANTS` retorna, que geralmente já
segue essa sequência. **Sempre revise antes de executar em produção.**

---

## Conversão MariaDB → MySQL

Equivalente ao `--convert-MariaDB` do Percona Toolkit `pt-show-grants`.
Ativada via `convert_mariadb=True`.

| MariaDB | MySQL |
|---|---|
| `IDENTIFIED VIA plugin USING 'x'` | `IDENTIFIED WITH plugin AS 'x'` |
| `IDENTIFIED VIA plugin USING PASSWORD('p')` | `IDENTIFIED WITH plugin BY 'p'` |
| `IDENTIFIED VIA plugin AS 'x'` | `IDENTIFIED WITH plugin AS 'x'` |
| `... OR unix_socket` | *(removido)* |
| `... OR ed25519` | *(removido)* |
| `... OR auth_pam` | *(removido)* |
| `GRANT ... IDENTIFIED BY PASSWORD 'x'` | *(removido — MySQL 8 não permite)* |
| `GRANT ... IDENTIFIED BY 'x'` | *(removido — MySQL 8 não permite)* |
| `PASSWORD HISTORY n` | *(removido)* |
| `PASSWORD REUSE INTERVAL n` | *(removido)* |
| `PASSWORD REQUIRE CURRENT` | *(removido)* |

### Avisos importantes

- **`unix_socket`** não tem equivalente no MySQL — o usuário precisará ser
  recriado com senha após a migração
- **`ed25519`** não existe no MySQL — o usuário precisará resetar a senha
- **Hash `mysql_native_password`** é compatível entre MariaDB e MySQL
- **`OR plugin_a OR plugin_b`** — apenas o primeiro plugin é mantido; os
  demais são removidos com aviso
- Senhas do MariaDB portadas como `mysql_native_password` — o MySQL 8
  recomenda migrar para `caching_sha2_password` depois

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

## Integração com `util.dumpInstance()` e `util.loadDump()`

```python
# 1. Faz o dump normal do Shell (dados + security metadata nativos)
util.dumpInstance("/backup/prod")

# 2. Complementa com o dump de segurança da DBA BRABO (opcional)
brabo.dumpSecurityMetadata(output="/backup/prod")

# 3. Valida que o Shell ainda lê o dump sem erros
util.loadDump("/backup/prod", dryRun=True, loadUsers=True)
```

**No destino, para importar tudo (dados + usuários + roles + grants):**

```python
util.loadDump("/backup/prod", loadUsers=True)
```

**Filtros finos (MySQL Shell 8.0.22+):**

```python
util.loadDump("/backup/prod", loadUsers=True,
              includeUsers=["'app'@'%'"])     # só o app

util.loadDump("/backup/prod", loadUsers=True,
              excludeUsers=["'root'@'localhost'"])  # todos menos root
```

> O `loadUsers` é `false` por padrão no Shell. Precisa passar
> explicitamente para importar as contas.

---

## Exemplo de saída

### `@.users.sql`

```sql
-- DBA BRABO - users dump
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
  "generator": "dba-brabo v2.2"
}
```

### REVOKE gerado

```sql
-- USER 'app'@'%'
REVOKE SELECT, INSERT ON ERP.* FROM 'app'@'%';
REVOKE EXECUTE ON PROCEDURE ERP.sp_vendas FROM 'app'@'%';
REVOKE 'app_read'@'%' FROM 'app'@'%';
```

### Conversão MariaDB → MySQL

**Entrada (MariaDB):**
```sql
CREATE USER 'app'@'%' IDENTIFIED VIA mysql_native_password USING PASSWORD('secret');
CREATE USER 'root'@'localhost' IDENTIFIED VIA unix_socket OR mysql_native_password USING PASSWORD('x');
GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%' IDENTIFIED BY PASSWORD '*ABC123';
```

**Saída (MySQL, `convert_mariadb=True`):**
```sql
CREATE USER IF NOT EXISTS 'app'@'%' IDENTIFIED WITH mysql_native_password BY 'secret';
CREATE USER IF NOT EXISTS 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'x';
GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%';
```

---

## Segurança

- ✅ Queries parametrizadas via `session.run_sql(sql, args)`
- ✅ Escaping explícito de `user`/`host` ao montar `'user'@'host'`
- ✅ **Read-only** — a extensão nunca escreve no servidor
- ✅ Modo revoke é read-only também — só **gera** o SQL, não executa
- ✅ Conversão MariaDB reescreve sintaxe, não inventa dados
- ✅ Usuários de sistema excluídos por padrão (`mysql.sys`, `mysql.session`,
  `mysql.infoschema`, `mariadb.sys`, `mariadb.session`)
- ✅ Manifesto `@.json` existente é preservado (chaves do Shell nunca
  são sobrescritas)
- ✅ Nenhuma credencial é logada ou gravada

---

## Compatibilidade

| Versão | Status |
|---|---|
| MySQL 8.0.x | ✅ Testado |
| MySQL 8.4.x | ✅ Testado |
| MySQL 9.4.0 | ✅ Testado |
| MySQL 5.7 | ⏳ Pendente (`SHOW CREATE USER` existe desde 5.7.6) |
| MariaDB | ⚠️ Entrada suportada via `convert_mariadb=True`; saída não suportada |

**Requisitos:** MySQL Shell 8.0+ em modo Python.

---

## Roadmap

| Versão | Escopo |
|---|---|
| **v1.1** | `export_grants()`, `roles()`, `help()`, escaping seguro |
| **v2.0** | `dumpSecurityMetadata()`, manifesto `@.json`, integração com `util.dumpInstance()`, inventário JSON |
| **v2.1** | `export_revokes()`, `mode="revoke"`, `_grant_to_revoke()` |
| **v2.2** *(atual)* | `convert_mariadb=True`, `_convert_mariadb_to_mysql()`, filtro `mariadb.sys`/`mariadb.session` |
| **v2.3** | `brabo.grants.diff()`, `brabo.security.audit()`, ordenação determinística de GRANTs para Git |
| **v3.0** | Migração para a API oficial de extensões do Shell (`shell.register_extension()`) |
| **RFC** | Proposta upstream de `util.dumpInstance(users=True, roles=True, grants=True)` e `util.loadDump(loadUsers=True)` |

---

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md). PRs são bem-vindos, especialmente:

- Testes em **MySQL 5.7**
- Testes em **MariaDB** (para validar a conversão)
- Testes automatizados (pytest + mock da sessão do Shell)
- Validação do formato `@.json` em diferentes versões do MySQL Shell
- Migração para a API oficial de extensões

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

---

## Código-fonte

<details>
<summary><b>Clique para expandir o <code>brabo.py</code> completo (v2.2)</b></summary>

```python
# =====================================================================
#                                                                     
#     ██████╗ ██████╗  █████╗     ██████╗ ██████╗  █████╗ ██████╗  ██████╗ 
#     ██╔══██╗██╔══██╗██╔══██╗    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗
#     ██║  ██║██████╔╝███████║    ██████╔╝██████╔╝███████║██████╔╝██║   ██║
#     ██║  ██║██╔══██╗██╔══██║    ██╔══██╗██╔══██╗██╔══██║██╔══██╗██║   ██║
#     ██████╔╝██████╔╝██║  ██║    ██████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝
#     ╚═════╝ ╚═════╝ ╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ 
#                                                                     
#     MySQL Shell Extension · Export users, roles & grants            
#                                                                     
# =====================================================================
#  File     : brabo.py
#  Version  : 2.2
#  Author   : Acacio LR
#  License  : MIT
#  Repo     : https://github.com/<seu-usuario>/dba-brabo
#  Requires : MySQL Shell 8.0+ (Python mode)
#  Tested   : MySQL 8.0.x · 8.4.x · 9.4.0
# =====================================================================
#
#  DESCRIPTION
#  -----------
#  Extensão nativa para o MySQL Shell que exporta usuários, roles e
#  privilégios em SQL idempotente, pronto para versionamento (Git) e
#  replay seguro entre ambientes (dev → staging → prod).
#
#  A partir da v2.0, a extensão também gera um Security Metadata Dump
#  estruturalmente compatível com util.dumpInstance(), reaproveitando
#  o manifesto @.json existente quando o diretório já contém um dump
#  do Shell.
#
#  A partir da v2.1, suporta modo REVOKE — gera os comandos de revogação
#  a partir dos grants existentes, útil para rollback e auditoria.
#
#  A partir da v2.2, converte sintaxe proprietária do MariaDB para MySQL
#  válido (IDENTIFIED VIA → IDENTIFIED WITH, unix_socket/ed25519 removidos,
#  PASSWORD() convertido), equivalente ao --convert-MariaDB do pt-show-grants.
#
#  INSTALLATION
#  ------------
#    mkdir -p ~/.mysqlsh/init.d
#    cp brabo.py ~/.mysqlsh/init.d/brabo.py
#    # reabra o MySQL Shell
#
#  LOAD IN SHELL
#  ------------
#    \py
#    import sys
#    sys.path.insert(0, "/root/.mysqlsh/init.d")
#    from brabo import brabo
#    brabo.help()
#
#  QUICK START
#  -----------
#    brabo.help()                                        # ajuda inline
#
#    # --- v1.1 (arquivo SQL único) ---
#    brabo.export_grants()                               # tudo -> stdout
#    brabo.export_grants(output="~/backup/grants.sql")   # tudo -> arquivo
#    brabo.export_grants(user="app")                     # filtra usuário
#    brabo.export_grants(host="%")                       # filtra host
#    brabo.export_grants(include_alter=True)             # modo sync
#    brabo.roles()                                       # lista roles
#
#    # --- v2.1 (modo REVOKE) ---
#    brabo.export_revokes()                              # REVOKE de tudo
#    brabo.export_revokes(user="app")                    # REVOKE de um user
#    brabo.export_grants(mode="revoke")                  # idem, via mode=
#
#    # --- v2.2 (conversão MariaDB -> MySQL) ---
#    brabo.export_grants(convert_mariadb=True)           # converte tudo
#    brabo.export_grants(output="~/mysql.sql", convert_mariadb=True)
#    brabo.export_revokes(convert_mariadb=True)
#
#    # --- v2.0 (Security Metadata Dump) ---
#    brabo.dumpSecurityMetadata(output="/backup/prod")   # dump completo
#    brabo.dumpUsers("/backup/prod")                     # só users
#    brabo.dumpRoles("/backup/prod")                     # só roles
#    brabo.dumpGrants("/backup/prod")                    # só grants
#    brabo.dumpSecurity("/backup/prod")                  # só inventário
#
#  ROADMAP
#  -------
#    v1.1  export_grants, roles, help
#    v2.0  dumpSecurityMetadata + integração com util.dumpInstance()
#    v2.1  export_revokes + mode="revoke"
#    v2.2  convert_mariadb + filtro mariadb.sys/mariadb.session  [current]
#    v2.3  grants.diff, security.audit, ordenação determinística
#    v3.0  official Shell extension API (shell.register_extension)
#
# =====================================================================

from mysqlsh import globals
import datetime
import json
import os
import re

__version__ = "2.2"

shell = globals.shell
session = globals.session

SYSTEM_USERS = (
    "mysql.sys",
    "mysql.session",
    "mysql.infoschema",
    "mariadb.sys",
    "mariadb.session",
)


class Brabo(object):
    """DBA BRABO - export e dump de metadados de seguranca."""

    # -----------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------
    def _check_session(self):
        global session
        session = globals.session  # pega a sessao ATUAL, nao a do import
        if session is None:
            print("[ERRO] Sessao nao conectada.")
            print("       Use \\connect usuario@host antes de rodar a extensao.")
            return False
        return True

    @staticmethod
    def _quote_account(user, host):
        """Escapa user/host e devolve a string 'user'@'host' segura."""
        u = str(user).replace("'", "''")
        h = str(host).replace("'", "''")
        return "'{}'@'{}'".format(u, h)

    def _accounts(self, user=None, host=None, include_system=False, is_role=None):
        """Lista contas em mysql.user.

        is_role=None  -> todos (users + roles)
        is_role=False -> apenas usuarios
        is_role=True  -> apenas roles
        """
        role_condition = (
            "account_locked = 'Y' AND password_expired = 'Y' "
            "AND authentication_string = ''"
        )

        sql = "SELECT user, host FROM mysql.user WHERE 1=1"
        args = []

        if user:
            sql += " AND user = ?"
            args.append(user)

        if host:
            sql += " AND host = ?"
            args.append(host)

        if is_role is True:
            sql += " AND ({})".format(role_condition)
        elif is_role is False:
            sql += " AND NOT ({})".format(role_condition)

        if not include_system:
            placeholders = ",".join(["?"] * len(SYSTEM_USERS))
            sql += " AND user NOT IN ({})".format(placeholders)
            args.extend(SYSTEM_USERS)

        sql += " ORDER BY user, host"

        result = session.run_sql(sql, args)
        return [(r[0], r[1]) for r in result.fetch_all()]

    def _user_ddl(self, user, host):
        """Devolve (create_stmt, alter_stmt) para uma conta."""
        acc = self._quote_account(user, host)
        row = session.run_sql("SHOW CREATE USER {}".format(acc)).fetch_one()
        create = row[0]
        if create.upper().startswith("CREATE USER"):
            create = "CREATE USER IF NOT EXISTS" + create[len("CREATE USER"):]
        alter = create.replace("CREATE USER IF NOT EXISTS", "ALTER USER", 1)
        return create, alter

    def _user_grants(self, user, host):
        acc = self._quote_account(user, host)
        sql = "SHOW GRANTS FOR {}".format(acc)
        return [r[0] for r in session.run_sql(sql).fetch_all()]

    # -----------------------------------------------------------------
    # Conversao MariaDB -> MySQL
    # -----------------------------------------------------------------
    def _convert_mariadb_to_mysql(self, stmt):
        """Converte sintaxe proprietaria do MariaDB para MySQL valido.

        Trata:
          IDENTIFIED VIA plugin USING 'x'          -> IDENTIFIED WITH plugin AS 'x'
          IDENTIFIED VIA plugin AS 'x'             -> IDENTIFIED WITH plugin AS 'x'
          IDENTIFIED VIA plugin USING PASSWORD('p')-> IDENTIFIED WITH plugin BY 'p'
          OR unix_socket / OR ed25519 / OR auth_pam-> removido
          GRANT ... IDENTIFIED BY PASSWORD 'x'     -> removido (MySQL 8)
          GRANT ... IDENTIFIED BY 'x'              -> removido (MySQL 8)
          PASSWORD HISTORY/REUSE/REQUIRE           -> removido
        """
        if not stmt:
            return stmt

        s = stmt

        # 1. IDENTIFIED VIA <plugin> USING PASSWORD('...')
        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+USING\s+PASSWORD\('([^']*)'\)",
            r"IDENTIFIED WITH \1 BY '\2'",
            s, flags=re.IGNORECASE,
        )

        # 2. IDENTIFIED VIA <plugin> USING <resto>
        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+USING\s+",
            r"IDENTIFIED WITH \1 AS ",
            s, flags=re.IGNORECASE,
        )

        # 3. IDENTIFIED VIA <plugin> AS <resto>
        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+AS\s+",
            r"IDENTIFIED WITH \1 AS ",
            s, flags=re.IGNORECASE,
        )

        # 4. Remove OR <plugin_inexistente_no_mysql>
        s = re.sub(
            r"\s+OR\s+(unix_socket|ed25519|auth_pam|mysql_old_password|pam)\b",
            "", s, flags=re.IGNORECASE,
        )

        # 5. GRANT ... IDENTIFIED BY PASSWORD '...' (MariaDB permite, MySQL 8 nao)
        s = re.sub(
            r"\s+IDENTIFIED\s+BY\s+PASSWORD\s+'[^']*'",
            "", s, flags=re.IGNORECASE,
        )

        # 6. GRANT ... IDENTIFIED BY '...' (idem)
        s = re.sub(
            r"\s+IDENTIFIED\s+BY\s+'[^']*'",
            "", s, flags=re.IGNORECASE,
        )

        # 7. Remove clausulas MySQL-only (por seguranca, se vierem do dump)
        s = re.sub(
            r"\s+PASSWORD\s+HISTORY\s+\S+",
            "", s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s+PASSWORD\s+REUSE\s+INTERVAL\s+\S+",
            "", s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s+PASSWORD\s+REQUIRE\s+CURRENT(\s+\S+)?",
            "", s, flags=re.IGNORECASE,
        )

        return s

    # -----------------------------------------------------------------
    # Conversao GRANT -> REVOKE
    # -----------------------------------------------------------------
    def _grant_to_revoke(self, grant):
        """Converte uma linha de SHOW GRANTS em REVOKE.

        Regras:
          - GRANT USAGE ON ...      -> ignorado (USAGE eh no-op)
          - WITH GRANT OPTION       -> removido, gera REVOKE separado
          - GRANT X ON obj TO user  -> REVOKE X ON obj FROM user
          - GRANT 'role' TO user    -> REVOKE 'role' FROM user
          - GRANT PROXY ON x TO y   -> REVOKE PROXY ON x FROM y

        Devolve lista de strings (0, 1 ou 2 statements).
        """
        g = grant.strip().rstrip(";").strip()
        if not g:
            return []

        g_up = g.upper()

        if g_up.startswith("GRANT USAGE ON"):
            return []

        had_grant_option = False
        if " WITH GRANT OPTION" in g_up:
            idx = g_up.find(" WITH GRANT OPTION")
            g = g[:idx].rstrip()
            g_up = g.upper()
            had_grant_option = True

        if not g_up.startswith("GRANT "):
            return []

        revoke = "REVOKE " + g[len("GRANT "):]

        idx = revoke.upper().rfind(" TO ")
        if idx == -1:
            return []
        revoke = revoke[:idx] + " FROM " + revoke[idx + 4:] + ";"

        result = [revoke]

        if had_grant_option:
            r_up = revoke.upper()
            on_idx = r_up.find(" ON ")
            from_idx = r_up.rfind(" FROM ")
            if on_idx != -1 and from_idx != -1 and on_idx < from_idx:
                obj = revoke[on_idx + 4:from_idx].strip()
                acc = revoke[from_idx + 6:].rstrip(";").strip()
                result.append(
                    "REVOKE GRANT OPTION ON {} FROM {};".format(obj, acc)
                )

        return result

    # -----------------------------------------------------------------
    # Manifesto @.json - compativel com util.dumpInstance()
    # -----------------------------------------------------------------
    def _read_manifest(self, dump_dir):
        """Le @.json existente. Devolve dict ou None."""
        path = os.path.join(os.path.expanduser(dump_dir), "@.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except Exception as e:
            print("[WARN] Falha ao ler {}: {}".format(path, e))
            return None

    @staticmethod
    def _supports_gtid():
        try:
            row = session.run_sql("SELECT @@gtid_mode").fetch_one()
            return bool(row) and row[0] in ("ON", "OFF_PERMISSIVE", "ON_PERMISSIVE")
        except Exception:
            return False

    def _build_manifest(self):
        """Cria manifesto novo no formato do util.dumpInstance()."""
        try:
            host = session.run_sql("SELECT @@hostname").fetch_one()[0]
            vers = session.run_sql("SELECT @@version").fetch_one()[0]
            charset = session.run_sql("SELECT @@character_set_server").fetch_one()[0]
            gtid = ""
            if self._supports_gtid():
                try:
                    gtid = session.run_sql("SELECT @@gtid_executed").fetch_one()[0] or ""
                except Exception:
                    gtid = ""
        except Exception:
            host, vers, charset, gtid = "unknown", "unknown", "utf8mb4", ""

        return {
            "dumper": "mysqlsh",
            "version": __version__,
            "origin": host,
            "serverVersion": vers,
            "gtidExecuted": gtid,
            "gtidExecutedInconsistent": False,
            "creationTime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "charset": charset,
            "schemas": [],
            "users": [],
            "toolsUsed": ["dba-brabo"],
            "securityMetadata": True,
        }

    def _update_manifest(self, manifest, dump_dir):
        """Grava @.json preservando chaves existentes."""
        path = os.path.join(os.path.expanduser(dump_dir), "@.json")
        with open(path, "w", encoding="utf8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        return path

    # -----------------------------------------------------------------
    # Inventario JSON
    # -----------------------------------------------------------------
    def _build_security_inventory(self, users, roles):
        plugins = {}
        locked = 0
        ssl_required = 0

        for usr, hst in users:
            try:
                row = session.run_sql(
                    "SELECT plugin, account_locked, ssl_type "
                    "FROM mysql.user WHERE user=? AND host=?",
                    [usr, hst],
                ).fetch_one()
                if row:
                    plugin = row[0] or "unknown"
                    plugins[plugin] = plugins.get(plugin, 0) + 1
                    if row[1] == "Y":
                        locked += 1
                    if row[2]:
                        ssl_required += 1
            except Exception:
                pass

        return {
            "users": len(users),
            "roles": len(roles),
            "accounts_locked": locked,
            "ssl_required": ssl_required,
            "plugins": plugins,
            "generated_at": datetime.datetime.now().isoformat(),
            "generator": "dba-brabo v{}".format(__version__),
        }

    # =================================================================
    # v1.1 - comandos legados (agora com mode e convert_mariadb)
    # =================================================================
    def export_grants(
        self,
        user=None,
        host=None,
        output=None,
        mode="grant",
        convert_mariadb=False,
        include_create=True,
        include_alter=False,
        include_grants=True,
        include_system=False,
    ):
        """Exporta CREATE USER / ALTER USER / GRANTs (ou REVOKEs).

        Parametros:
          user             -> filtra por nome de usuario
          host             -> filtra por host
          output           -> caminho de arquivo (aceita ~)
          mode             -> "grant" (default) ou "revoke"
          convert_mariadb  -> converte sintaxe MariaDB -> MySQL
          include_create   -> emite CREATE USER IF NOT EXISTS
          include_alter    -> emite ALTER USER (default False)
          include_grants   -> emite GRANTs/REVOKEs
          include_system   -> inclui mysql.sys, mysql.session, ...
        """
        if not self._check_session():
            return

        mode = (mode or "grant").lower()
        if mode not in ("grant", "revoke"):
            print("[ERRO] mode invalido: '{}'. Use 'grant' ou 'revoke'.".format(mode))
            return

        if mode == "revoke":
            include_create = False
            include_alter = False

        accounts = self._accounts(user, host, include_system=include_system)

        if not accounts:
            print("Nenhum usuario encontrado com os filtros informados.")
            return

        server = session.run_sql("SELECT @@hostname").fetch_one()[0]
        version = session.run_sql("SELECT @@version").fetch_one()[0]

        lines = []
        lines.append("-- =========================================================")
        lines.append("-- DBA BRABO - MySQL Shell Extension")
        lines.append("-- Version : {}".format(__version__))
        lines.append("-- Mode    : {}".format(mode.upper()))
        if convert_mariadb:
            lines.append("-- Convert : MariaDB -> MySQL")
        lines.append("-- Server  : {}".format(server))
        lines.append("-- Version : {}".format(version))
        lines.append("-- Date    : {}".format(datetime.datetime.now()))
        lines.append("-- =========================================================")
        lines.append("")

        for usr, hst in accounts:
            account = self._quote_account(usr, hst)

            lines.append("-- ---------------------------------------------------------")
            lines.append("-- USER {}".format(account))
            lines.append("-- ---------------------------------------------------------")

            if include_create:
                try:
                    create, _ = self._user_ddl(usr, hst)
                    if convert_mariadb:
                        create = self._convert_mariadb_to_mysql(create)
                    lines.append(create + ";")
                except Exception as e:
                    lines.append("-- [WARN] CREATE USER falhou para {}: {}".format(account, e))

            if include_alter:
                try:
                    _, alter = self._user_ddl(usr, hst)
                    if convert_mariadb:
                        alter = self._convert_mariadb_to_mysql(alter)
                    lines.append(alter + ";")
                except Exception as e:
                    lines.append("-- [WARN] ALTER USER falhou para {}: {}".format(account, e))

            if include_grants:
                try:
                    for g in self._user_grants(usr, hst):
                        if convert_mariadb:
                            g = self._convert_mariadb_to_mysql(g)
                        if mode == "revoke":
                            for r in self._grant_to_revoke(g):
                                lines.append(r)
                        else:
                            lines.append(g + ";")
                except Exception as e:
                    lines.append("-- [WARN] SHOW GRANTS falhou para {}: {}".format(account, e))

            lines.append("")

        text = "\n".join(lines)

        if output:
            path = os.path.expanduser(output)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf8") as f:
                f.write(text)
            print("[OK]   {} usuario(s) exportado(s) [modo={}{}]".format(
                len(accounts),
                mode,
                ", convert_mariadb=True" if convert_mariadb else "",
            ))
            print("[FILE] {}".format(path))
        else:
            print(text)

    def export_revokes(
        self,
        user=None,
        host=None,
        output=None,
        convert_mariadb=False,
        include_system=False,
    ):
        """Atalho para export_grants(mode='revoke').

        Gera os REVOKE correspondentes a todos os grants das contas.
        Se user= for informado, gera apenas para aquele usuario.
        """
        return self.export_grants(
            user=user,
            host=host,
            output=output,
            mode="revoke",
            convert_mariadb=convert_mariadb,
            include_create=False,
            include_alter=False,
            include_grants=True,
            include_system=include_system,
        )

    def roles(self, show_grants=True):
        """Lista roles existentes e, opcionalmente, seus privilegios."""
        if not self._check_session():
            return

        rows = self._accounts(is_role=True)

        if not rows:
            print("\nNenhuma role encontrada.\n")
            return

        print("\nRoles\n")
        for usr, hst in rows:
            print("  {}@{}".format(usr, hst))
            if show_grants:
                try:
                    for g in self._user_grants(usr, hst):
                        print("      {}".format(g))
                except Exception as e:
                    print("      [WARN] {}".format(e))
        print()

    # =================================================================
    # v2.0 - Security Metadata Dump
    # =================================================================
    def dumpUsers(self, output, include_system=False):
        """Gera <output>/@.users.sql (CREATE + ALTER USER idempotentes)."""
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        users = self._accounts(include_system=include_system, is_role=False)

        lines = [
            "-- DBA BRABO - users dump",
            "-- Generated: {}".format(datetime.datetime.now()),
            "-- Users    : {}".format(len(users)),
            "",
        ]

        for usr, hst in users:
            acc = self._quote_account(usr, hst)
            lines.append("-- USER {}".format(acc))
            try:
                create, alter = self._user_ddl(usr, hst)
                lines.append(create + ";")
                lines.append(alter + ";")
            except Exception as e:
                lines.append("-- [WARN] {}: {}".format(acc, e))
            lines.append("")

        path = os.path.join(out, "@.users.sql")
        with open(path, "w", encoding="utf8") as f:
            f.write("\n".join(lines))
        return path, len(users)

    def dumpRoles(self, output):
        """Gera <output>/@.roles.sql (CREATE ROLE + grants da role)."""
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        roles = self._accounts(is_role=True)

        lines = [
            "-- DBA BRABO - roles dump",
            "-- Generated: {}".format(datetime.datetime.now()),
            "-- Roles    : {}".format(len(roles)),
            "",
        ]

        for usr, hst in roles:
            acc = self._quote_account(usr, hst)
            lines.append("CREATE ROLE IF NOT EXISTS {};".format(acc))
            try:
                for g in self._user_grants(usr, hst):
                    lines.append(g + ";")
            except Exception as e:
                lines.append("-- [WARN] {}: {}".format(acc, e))
            lines.append("")

        path = os.path.join(out, "@.roles.sql")
        with open(path, "w", encoding="utf8") as f:
            f.write("\n".join(lines))
        return path, len(roles)

    def dumpGrants(self, output, include_system=False):
        """Gera <output>/@.grants.sql (GRANTs por conta)."""
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        users = self._accounts(include_system=include_system, is_role=False)

        lines = [
            "-- DBA BRABO - grants dump",
            "-- Generated: {}".format(datetime.datetime.now()),
            "-- Accounts : {}".format(len(users)),
            "",
        ]

        for usr, hst in users:
            acc = self._quote_account(usr, hst)
            lines.append("-- GRANTS {}".format(acc))
            try:
                for g in self._user_grants(usr, hst):
                    lines.append(g + ";")
            except Exception as e:
                lines.append("-- [WARN] {}: {}".format(acc, e))
            lines.append("")

        path = os.path.join(out, "@.grants.sql")
        with open(path, "w", encoding="utf8") as f:
            f.write("\n".join(lines))
        return path, len(users)

    def dumpSecurity(self, output, include_system=False):
        """Gera <output>/@.security.json (inventario)."""
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        users = self._accounts(include_system=include_system, is_role=False)
        roles = self._accounts(is_role=True)
        inv = self._build_security_inventory(users, roles)

        path = os.path.join(out, "@.security.json")
        with open(path, "w", encoding="utf8") as f:
            json.dump(inv, f, indent=2, ensure_ascii=False)
        return path, inv

    def dumpSecurityMetadata(
        self,
        output,
        include_system=False,
        include_users=True,
        include_roles=True,
        include_grants=True,
        include_inventory=True,
    ):
        """Gera (ou complementa) um Security Metadata Dump compativel com
        util.dumpInstance(). Se <output>/@.json ja existir, reaproveita
        os metadados do dump existente em vez de recria-los.
        """
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)

        manifest = self._read_manifest(out)
        reused = manifest is not None
        if not reused:
            manifest = self._build_manifest()
        else:
            print("[INFO] Manifesto existente encontrado em {}/@.json".format(out))
            print("[INFO] Reaproveitando metadados do dump original.")

        report = {}
        if include_users:
            p, n = self.dumpUsers(out, include_system)
            report["users"] = {"file": p, "count": n}
        if include_roles:
            p, n = self.dumpRoles(out)
            report["roles"] = {"file": p, "count": n}
        if include_grants:
            p, n = self.dumpGrants(out, include_system)
            report["grants"] = {"file": p, "count": n}
        if include_inventory:
            p, inv = self.dumpSecurity(out, include_system)
            report["inventory"] = {"file": p, "data": inv}

        if "toolsUsed" not in manifest or not isinstance(manifest["toolsUsed"], list):
            manifest["toolsUsed"] = []
        if "dba-brabo" not in manifest["toolsUsed"]:
            manifest["toolsUsed"].append("dba-brabo")
        manifest["securityMetadata"] = True
        manifest["securityMetadataVersion"] = __version__
        manifest["securityLastUpdate"] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self._update_manifest(manifest, out)

        print("")
        print("[DBA BRABO] Security Metadata Dump")
        print("  output    : {}".format(out))
        print("  reused    : {}".format(reused))
        for k in ("users", "roles", "grants"):
            if k in report:
                print("  {:<10}: {} -> {}".format(
                    k, report[k]["count"], os.path.basename(report[k]["file"])))
        if "inventory" in report:
            inv = report["inventory"]["data"]
            print("  {:<10}: {} users, {} roles, {} locked, {} ssl".format(
                "inventory", inv["users"], inv["roles"],
                inv["accounts_locked"], inv["ssl_required"]))
        print("")

    # =================================================================
    # Help
    # =================================================================
    def help(self):
        print("""
DBA BRABO Extension v{}

Comandos v1.1 - export em arquivo unico
---------------------------------------
brabo.help()
    Mostra esta ajuda.

brabo.export_grants(...)
    Exporta CREATE USER, ALTER USER e GRANTs em um unico SQL.

    Parametros:
      user             = "app"          filtra por usuario
      host             = "%"            filtra por host
      output           = "~/grants.sql" grava em arquivo
      mode             = "grant"        "grant" (default) ou "revoke"
      convert_mariadb  = False          converte MariaDB -> MySQL
      include_create   = True           emite CREATE USER IF NOT EXISTS
      include_alter    = False          emite ALTER USER (sync)
      include_grants   = True           emite GRANTs/REVOKEs
      include_system   = False          inclui mysql.sys, mysql.session, ...

    Exemplos:
      brabo.export_grants()
      brabo.export_grants(user="app")
      brabo.export_grants(host="%")
      brabo.export_grants(output="~/backup/grants.sql")
      brabo.export_grants(include_alter=True, output="~/sync.sql")
      brabo.export_grants(mode="revoke", output="~/revokes.sql")
      brabo.export_grants(output="~/mysql.sql", convert_mariadb=True)

brabo.export_revokes(user=None, host=None, output=None,
                     convert_mariadb=False, include_system=False)
    Atalho para export_grants(mode="revoke").
    Gera os REVOKE correspondentes a todos os grants das contas.
    Se user= for informado, gera apenas para aquele usuario.

    Exemplos:
      brabo.export_revokes(output="~/revokes_all.sql")
      brabo.export_revokes(user="acaciolr", output="~/revokes_acaciolr.sql")
      brabo.export_revokes(host="%", output="~/revokes_remote.sql")

brabo.roles()
    Lista roles e seus privilegios.

Comandos v2.0 - Security Metadata Dump
--------------------------------------
Estrutura gerada (compativel com util.dumpInstance):

  <output>/
    @.json            manifesto (lido/atualizado)
    @.users.sql       CREATE + ALTER USER
    @.roles.sql       CREATE ROLE + grants de role
    @.grants.sql      GRANTs por conta
    @.security.json   inventario (contadores + plugins)

brabo.dumpSecurityMetadata(output="/backup/prod", ...)
    Comando principal. Gera tudo de uma vez.
    Se o diretorio ja contem @.json, reaproveita os metadados.

    Parametros:
      output            = "/backup/prod"  diretorio destino
      include_system    = False           inclui contas de sistema
      include_users     = True
      include_roles     = True
      include_grants    = True
      include_inventory = True

brabo.dumpUsers(output, include_system=False)
brabo.dumpRoles(output)
brabo.dumpGrants(output, include_system=False)
brabo.dumpSecurity(output, include_system=False)
    Geram apenas uma parte do dump.

Conversao MariaDB -> MySQL
--------------------------
O parametro convert_mariadb=True aplica as seguintes conversoes:

  IDENTIFIED VIA plugin USING 'x'            -> IDENTIFIED WITH plugin AS 'x'
  IDENTIFIED VIA plugin USING PASSWORD('p')  -> IDENTIFIED WITH plugin BY 'p'
  OR unix_socket / OR ed25519 / OR auth_pam  -> removido
  GRANT ... IDENTIFIED BY PASSWORD 'x'       -> removido (MySQL 8 nao suporta)
  PASSWORD HISTORY / REUSE / REQUIRE         -> removido

Plugins sem equivalente no MySQL (unix_socket, ed25519) sao sinalizados
no arquivo gerado. O usuario precisara resetar a senha apos a migracao.

Roadmap (v2.3+)
---------------
brabo.grants.diff()
brabo.security.audit()
brabo.replication.status()
brabo.innodb.cluster()
Ordenacao determinística de GRANTs para Git
Migracao para a API oficial de extensoes do Shell
""".format(__version__))


# ---------------------------------------------------------------------
# Registro global
# ---------------------------------------------------------------------
brabo = Brabo()
globals.brabo = brabo

print("DBA BRABO extension v{} loaded. Type brabo.help() for usage.".format(__version__))
```

</details>
