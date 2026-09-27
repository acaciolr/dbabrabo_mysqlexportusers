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
