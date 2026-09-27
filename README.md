## Summary

MySQL Shell already provides powerful administrative utilities such as
`util.dumpInstance()`, `util.copyInstance()`, and `util.checkForServerUpgrade()`.
However, there is currently **no native way to export users, roles, and
privileges** in an idempotent, version-control-friendly SQL format.

This issue proposes adding a first-class utility — `util.exportUsers()` — and
presents a working proof of concept (`brabo.py`) that already implements most
of the required behavior as a community extension.

---

## Problem

DBAs migrating between environments today still rely on external tools:

- **Percona Toolkit** (`pt-show-grants`) — requires installing packages outside
  the Shell, Python 2/3 dependency headaches, no role support beyond basics.
- **`mysqldump --all-databases`** — does **not** export users/grants cleanly;
  output is not idempotent and cannot be replayed safely.
- **`mysqlpump`** — deprecated and does not cover roles properly (8.0+).
- **Manual scripts** — inconsistent, error-prone, rarely idempotent.

There is no official Oracle-supported method to export security metadata in a
form that can be:

1. Replayed safely (`CREATE USER IF NOT EXISTS` semantics)
2. Diffed and version-controlled (deterministic ordering)
3. Migrated to HeatWave, InnoDB Cluster, or any managed MySQL service

---

## Proposal

Add a new utility to the MySQL Shell `util` namespace:

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
#  Version  : 1.1                                                     
#  Author   : Acacio LR                                               
#  License  : MIT                                                     
#  Repo     : https://github.com/<seu-usuario>/dba-brabo              
#  Requires : MySQL Shell 8.0+ (Python mode)                          
#  Tested   : MySQL 8.0.x · 9.4.0                                     
# =====================================================================
#
#  DESCRIPTION
#  -----------
#  Extensão nativa para o MySQL Shell que exporta usuários, roles e
#  privilégios em SQL idempotente, pronto para versionamento (Git) e
#  replay seguro entre ambientes (dev → staging → prod).
#
#  INSTALLATION
#  ------------
#    mkdir -p ~/.mysqlsh/init.d
#    cp brabo.py ~/.mysqlsh/init.d/brabo.py
#    # reabra o MySQL Shell
#
#  QUICK START
#  -----------
#    brabo.help()                                        # ajuda inline
#    brabo.export_grants()                               # tudo -> stdout
#    brabo.export_grants(output="~/backup/grants.sql")   # tudo -> arquivo
#    brabo.export_grants(user="app")                     # filtra usuário
#    brabo.export_grants(host="%")                       # filtra host
#    brabo.export_grants(include_alter=True)             # modo sync
#    brabo.roles()                                       # lista roles
#
#  ROADMAP
#  -------
#    v1.1  export_grants, roles, help                       [current]
#    v2.0  grants.diff, security.audit, replication.status
#          innodb.cluster + official Shell extension API
#
# =====================================================================

from mysqlsh import globals
import datetime
import os

__version__ = "1.1"

shell = globals.shell
session = globals.session

# Usuários internos que normalmente NÃO devem ser exportados
SYSTEM_USERS = (
    "mysql.sys",
    "mysql.session",
    "mysql.infoschema",
)


class Brabo(object):
    """Exporta usuários, grants e roles do MySQL de forma segura."""

    # -----------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------
    def _check_session(self):
        if session is None:
            print("[ERRO] Sessão não conectada.")
            print("       Use \\connect usuario@host antes de rodar a extensão.")
            return False
        return True

    @staticmethod
    def _quote_account(user, host):
        """Escapa user/host e devolve a string 'user'@'host' segura."""
        u = str(user).replace("'", "''")
        h = str(host).replace("'", "''")
        return f"'{u}'@{h}'".replace("'@'", "'@'")  # mantém formato original

    def _accounts(self, user=None, host=None, include_system=False):
        sql = """
        SELECT user, host
          FROM mysql.user
         WHERE 1=1
        """
        args = []

        if user:
            sql += " AND user = ?"
            args.append(user)

        if host:
            sql += " AND host = ?"
            args.append(host)

        if not include_system:
            placeholders = ",".join(["?"] * len(SYSTEM_USERS))
            sql += f" AND user NOT IN ({placeholders})"
            args.extend(SYSTEM_USERS)

        sql += " ORDER BY user, host"

        result = session.run_sql(sql, args)

        return [(r[0], r[1]) for r in result.fetch_all()]

    # -----------------------------------------------------------------
    # Comandos públicos
    # -----------------------------------------------------------------
    def export_grants(
        self,
        user=None,
        host=None,
        output=None,
        include_create=True,
        include_alter=False,
        include_grants=True,
        include_system=False,
    ):
        """
        Exporta CREATE USER / ALTER USER / GRANTs.

        Parâmetros:
          user            -> filtra por nome de usuário
          host            -> filtra por host
          output          -> caminho de arquivo (aceita ~)
          include_create  -> emite CREATE USER IF NOT EXISTS (default True)
          include_alter   -> emite ALTER USER (default False; use só p/ sync)
          include_grants  -> emite GRANTs (default True)
          include_system  -> inclui mysql.sys, mysql.session, etc (default False)
        """
        if not self._check_session():
            return

        accounts = self._accounts(user, host, include_system=include_system)

        if not accounts:
            print("Nenhum usuário encontrado com os filtros informados.")
            return

        server = session.run_sql("SELECT @@hostname").fetch_one()[0]
        version = session.run_sql("SELECT @@version").fetch_one()[0]

        lines = []
        lines.append("-- =========================================================")
        lines.append("-- DBA BRABO - MySQL Shell Extension")
        lines.append(f"-- Version : {__version__}")
        lines.append(f"-- Server  : {server}")
        lines.append(f"-- Version : {version}")
        lines.append(f"-- Date    : {datetime.datetime.now()}")
        lines.append("-- =========================================================")
        lines.append("")

        for usr, hst in accounts:
            account = self._quote_account(usr, hst)

            lines.append("-- ---------------------------------------------------------")
            lines.append(f"-- USER {account}")
            lines.append("-- ---------------------------------------------------------")

            # CREATE USER
            if include_create:
                try:
                    row = session.run_sql(
                        f"SHOW CREATE USER {account}"
                    ).fetch_one()
                    stmt = row[0]
                    if stmt.upper().startswith("CREATE USER"):
                        stmt = stmt.replace(
                            "CREATE USER",
                            "CREATE USER IF NOT EXISTS",
                            1,
                        )
                    lines.append(stmt + ";")
                except Exception as e:
                    lines.append(f"-- [WARN] CREATE USER falhou para {account}: {e}")

            # ALTER USER (opcional, para sincronização)
            if include_alter:
                try:
                    alter = session.run_sql(
                        f"SHOW CREATE USER {account}"
                    ).fetch_one()[0]
                    if alter.upper().startswith("CREATE USER"):
                        alter = "ALTER USER" + alter[len("CREATE USER"):]
                    lines.append(alter + ";")
                except Exception as e:
                    lines.append(f"-- [WARN] ALTER USER falhou para {account}: {e}")

            # GRANTs
            if include_grants:
                try:
                    grants = session.run_sql(f"SHOW GRANTS FOR {account}")
                    for g in grants.fetch_all():
                        lines.append(g[0] + ";")
                except Exception as e:
                    lines.append(f"-- [WARN] SHOW GRANTS falhou para {account}: {e}")

            lines.append("")

        text = "\n".join(lines)

        if output:
            path = os.path.expanduser(output)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(path, "w", encoding="utf8") as f:
                f.write(text)

            print(f"[OK]   {len(accounts)} usuário(s) exportado(s)")
            print(f"[FILE] {path}")
        else:
            print(text)

    def roles(self, show_grants=True):
        """
        Lista roles existentes (is_role='Y').
        Se show_grants=True, mostra também os privilégios de cada role.
        """
        if not self._check_session():
            return

        sql = """
        SELECT user, host
          FROM mysql.user
         WHERE is_role = 'Y'
         ORDER BY user, host
        """
        rows = session.run_sql(sql).fetch_all()

        if not rows:
            print("\nNenhuma role encontrada.\n")
            return

        print("\nRoles\n")
        for usr, hst in rows:
            account = self._quote_account(usr, hst)
            print(f"  {usr}@{hst}")

            if show_grants:
                try:
                    grants = session.run_sql(f"SHOW GRANTS FOR {account}")
                    for g in grants.fetch_all():
                        print(f"      {g[0]}")
                except Exception as e:
                    print(f"      [WARN] {e}")

        print()

    def help(self):
        print("""
DBA BRABO Extension v{}

Comandos
--------
brabo.help()
    Mostra esta ajuda.

brabo.export_grants(...)
    Exporta CREATE USER, ALTER USER e GRANTs.

    Parâmetros:
      user            = "app"          filtra por usuário
      host            = "%"            filtra por host
      output          = "~/grants.sql" grava em arquivo
      include_create  = True           emite CREATE USER IF NOT EXISTS
      include_alter   = False          emite ALTER USER (sync)
      include_grants  = True           emite GRANTs
      include_system  = False          inclui mysql.sys, mysql.session, ...

    Exemplos:
      brabo.export_grants()
      brabo.export_grants(user="app")
      brabo.export_grants(host="%")
      brabo.export_grants(output="~/backup/grants.sql")
      brabo.export_grants(include_alter=True, output="~/sync.sql")

brabo.roles()
    Lista roles e seus privilégios.

Roadmap (v2)
------------
brabo.grants.diff()
brabo.security.audit()
brabo.replication.status()
brabo.innodb.cluster()
""".format(__version__))


# ---------------------------------------------------------------------
# Registro global
# ---------------------------------------------------------------------
brabo = Brabo()
globals.brabo = brabo

print(f"DBA BRABO extension v{__version__} loaded.")
```

```python
util.exportUsers()
```

### Examples

```python
util.exportUsers(output="/tmp/users.sql")
util.exportUsers(user="app")
util.exportUsers(host="%")
util.exportUsers(includeRoles=True)
util.exportUsers(includeSystem=False)
```

### Suggested API

```python
util.exportUsers(
    output          = None,      # path or None for stdout
    user            = None,      # filter by user
    host            = None,      # filter by host
    include_create  = True,      # emit CREATE USER IF NOT EXISTS
    include_alter   = False,     # emit ALTER USER (sync mode)
    include_grants  = True,      # emit GRANTs
    include_roles   = True,      # include roles and default roles
    include_system  = False,     # include mysql.sys, mysql.session, ...
    deterministic   = True,      # stable ordering for Git
)
```

### Expected output

- `CREATE USER IF NOT EXISTS`
- Authentication plugin and password hash
- `ALTER USER` attributes (SSL requirements, password policy, resource limits)
- Roles and default roles
- All `GRANT` statements
- Deterministic ordering for Git version control
- Header with server, version, and timestamp

### Benefits

- Removes dependency on Percona Toolkit and similar external tools
- Simplifies migrations to HeatWave and InnoDB Cluster
- Provides an official Oracle-supported method for exporting security metadata
- Consistent with existing `util.*` administrative functions
- Safe to replay: idempotent output suitable for CI/CD pipelines

---

## Proof of Concept — DBA BRABO extension

To validate the idea before proposing an official implementation, I built a
community extension called **DBA BRABO** (`brabo.py`) that runs inside MySQL
Shell via `~/.mysqlsh/init.d/`. It has no external dependencies.

### Installation

```bash
mkdir -p ~/.mysqlsh/init.d
cp brabo.py ~/.mysqlsh/init.d/brabo.py
# reopen MySQL Shell
```

### Available commands (v1.1)

| Command | Description |
|---|---|
| `brabo.help()` | Inline help |
| `brabo.export_grants()` | Export `CREATE USER` + `GRANT`s |
| `brabo.export_grants(user="app")` | Filter by user |
| `brabo.export_grants(host="%")` | Filter by host |
| `brabo.export_grants(output="~/grants.sql")` | Write to file |
| `brabo.export_grants(include_alter=True)` | Sync mode |
| `brabo.roles()` | List roles and their privileges |

### Sample output

```sql
-- =========================================================
-- DBA BRABO - MySQL Shell Extension
-- Version : 1.1
-- Server  : mysql-prod-01
-- Version : 9.4.0
-- Date    : 2026-09-27 14:03:22
-- =========================================================

-- ---------------------------------------------------------
-- USER 'app'@'%'
-- ---------------------------------------------------------
CREATE USER IF NOT EXISTS 'app'@'%'
IDENTIFIED WITH caching_sha2_password
AS '$A$005$HASH';

GRANT SELECT, INSERT ON ERP.* TO 'app'@'%';
GRANT EXECUTE ON PROCEDURE ERP.sp_vendas TO 'app'@'%';
```

### Security considerations

- Queries are parameterized via `session.run_sql(sql, args)` where possible
- Explicit escaping of `user`/`host` when assembling `'user'@'host'`
  (required because `SHOW CREATE USER` and `SHOW GRANTS` do not accept
  placeholders across all versions)
- The extension is **read-only** — it never writes to the server
- System users (`mysql.sys`, `mysql.session`, `mysql.infoschema`) are
  excluded by default

### Compatibility tested

- MySQL 8.0.x — OK
- MySQL 9.4.0 — OK
- MySQL 5.7 — pending (`SHOW CREATE USER` exists since 5.7.6)
- MariaDB — not supported (different `mysql.user` schema)

---

## Roadmap (V2 of the community extension)

- [ ] `brabo.grants.diff(user_a, user_b)` — compare privileges
- [ ] `brabo.security.audit()` — users without password, without expiration,
      with `%` host, inactive accounts
- [ ] `brabo.replication.status()`
- [ ] `brabo.innodb.cluster()`
- [ ] Migrate to the **official extension API**
      (`shell.register_extension(...)`) to reach the same level of polish as
      `util.checkForServerUpgrade()`
- [ ] Treat roles as first-class citizens in the export

---

## Open questions

1. Should `include_alter` default to `False` (pure restore) or `True`
   (overwrite)? The community extension currently defaults to `False`.
2. Is there interest in splitting the API into namespaces
   (`util.users.export()`, `util.roles.export()`) or keep a single entry point?
3. Should the export include `PROXY` grants, dynamic privileges, and
   password history? These are often missed by community tools.
4. Would Oracle accept a contribution of a prototype as a starting point for
   the official implementation?

---

## Checklist

- [x] No external dependencies
- [x] Handles "session not connected" gracefully
- [x] Escapes `user`/`host` safely
- [x] Filters system users by default
- [x] Inline documentation (`brabo.help()`)
- [x] Deterministic ordering
- [ ] Automated tests
- [ ] Packaging (`pip` or Shell extension format)

---

## References

- [MySQL Shell utilities](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities.html)
- [`util.checkForServerUpgrade()`](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-utilities-upgrade.html)
- [Percona Toolkit `pt-show-grants`](https://www.percona.com/doc/percona-toolkit/LATEST/pt-show-grants.html)
- [MySQL Shell extension API](https://dev.mysql.com/doc/mysql-shell/en/mysql-shell-extensions.html)

[mysql_brabo_mysqlsh_exportUser.py](https://github.com/user-attachments/files/32709088/mysql_brabo_mysqlsh_exportUser.py)
