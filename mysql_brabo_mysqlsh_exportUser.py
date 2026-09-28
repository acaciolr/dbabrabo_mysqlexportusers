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
#  Version  : 2.0
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
#  A partir da v2.0, a extensão também gera um Security Metadata Dump
#  estruturalmente compatível com util.dumpInstance(), reaproveitando
#  o manifesto @.json existente quando o diretório já contém um dump
#  do Shell.
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
#
#    # --- v1.1 (arquivo SQL único) ---
#    brabo.export_grants()                               # tudo -> stdout
#    brabo.export_grants(output="~/backup/grants.sql")   # tudo -> arquivo
#    brabo.export_grants(user="app")                     # filtra usuário
#    brabo.export_grants(host="%")                       # filtra host
#    brabo.export_grants(include_alter=True)             # modo sync
#    brabo.roles()                                       # lista roles
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
#    v2.0  dumpSecurityMetadata + integração com util.dumpInstance()  [current]
#    v2.1  grants.diff, security.audit
#    v3.0  official Shell extension API (shell.register_extension)
#
# =====================================================================

from mysqlsh import globals
import datetime
import json
import os

__version__ = "2.0"

shell = globals.shell
session = globals.session

# Usuários internos que normalmente NÃO devem ser exportados
SYSTEM_USERS = (
    "mysql.sys",
    "mysql.session",
    "mysql.infoschema",
)


class Brabo(object):
    """DBA BRABO — exportação e dump de metadados de segurança."""

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
        return "'{}'@'{}'".format(u, h)

    def _accounts(self, user=None, host=None, include_system=False, is_role=None):
        """
        Lista contas em mysql.user.

        is_role=None  -> todos (users + roles)  [comportamento v1.1]
        is_role=False -> apenas usuários
        is_role=True  -> apenas roles
        """
        sql = "SELECT user, host FROM mysql.user WHERE 1=1"
        args = []

        if user:
            sql += " AND user = ?"
            args.append(user)

        if host:
            sql += " AND host = ?"
            args.append(host)

        if is_role is not None:
            sql += " AND is_role = ?"
            args.append("Y" if is_role else "N")

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
        return [r[0] for r in session.run_sql("SHOW GRANTS FOR {}".format(acc)).fetch_all()]

    # -----------------------------------------------------------------
    # Manifesto @.json — compatível com util.dumpInstance()
    # -----------------------------------------------------------------
    def _read_manifest(self, dump_dir):
        """Lê @.json existente. Devolve dict ou None."""
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
    # Inventário JSON
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
    # v1.1 — comandos legados (mantidos por retrocompatibilidade)
    # =================================================================
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
        """Exporta CREATE USER / ALTER USER / GRANTs em arquivo único."""
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
        lines.append("-- Version : {}".format(__version__))
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
                    lines.append(create + ";")
                except Exception as e:
                    lines.append("-- [WARN] CREATE USER falhou para {}: {}".format(account, e))

            if include_alter:
                try:
                    _, alter = self._user_ddl(usr, hst)
                    lines.append(alter + ";")
                except Exception as e:
                    lines.append("-- [WARN] ALTER USER falhou para {}: {}".format(account, e))

            if include_grants:
                try:
                    for g in self._user_grants(usr, hst):
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
            print("[OK]   {} usuário(s) exportado(s)".format(len(accounts)))
            print("[FILE] {}".format(path))
        else:
            print(text)

    def roles(self, show_grants=True):
        """Lista roles existentes e, opcionalmente, seus privilégios."""
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
    # v2.0 — Security Metadata Dump (compatível com util.dumpInstance)
    # =================================================================
    def dumpUsers(self, output, include_system=False):
        """Gera <output>/@.users.sql (CREATE + ALTER USER idempotentes)."""
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)
        users = self._accounts(include_system=include_system, is_role=False)

        lines = [
            "-- DBA BRABO · users dump",
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
            "-- DBA BRABO · roles dump",
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
            "-- DBA BRABO · grants dump",
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
        """Gera <output>/@.security.json (inventário)."""
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
        """
        Gera (ou complementa) um Security Metadata Dump compatível com
        util.dumpInstance().

        Se <output>/@.json já existir, reaproveita os metadados do dump
        existente em vez de recriá-los.
        """
        if not self._check_session():
            return

        out = os.path.expanduser(output)
        os.makedirs(out, exist_ok=True)

        # 1. Manifesto — lê ou cria
        manifest = self._read_manifest(out)
        reused = manifest is not None
        if not reused:
            manifest = self._build_manifest()
        else:
            print("[INFO] Manifesto existente encontrado em {}/@.json".format(out))
            print("[INFO] Reaproveitando metadados do dump original.")

        # 2. Gera cada parte
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

        # 3. Atualiza manifesto preservando o original
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

        # 4. Resumo
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

Comandos v1.1 — export em arquivo único
---------------------------------------
brabo.help()
    Mostra esta ajuda.

brabo.export_grants(...)
    Exporta CREATE USER, ALTER USER e GRANTs em um único SQL.

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

Comandos v2.0 — Security Metadata Dump
--------------------------------------
Estrutura gerada (compatível com util.dumpInstance):

  <output>/
    @.json            manifesto (lido/atualizado)
    @.users.sql       CREATE + ALTER USER
    @.roles.sql       CREATE ROLE + grants de role
    @.grants.sql      GRANTs por conta
    @.security.json   inventário (contadores + plugins)

brabo.dumpSecurityMetadata(output="/backup/prod", ...)
    Comando principal. Gera tudo de uma vez.
    Se o diretório já contém @.json, reaproveita os metadados.

    Parâmetros:
      output            = "/backup/prod"  diretório destino
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

    Exemplo:
      brabo.dumpSecurityMetadata(output="/backup/prod")
      brabo.dumpSecurityMetadata(output="/backup/prod", include_system=True)

Roadmap (v2.1+)
---------------
brabo.grants.diff()
brabo.security.audit()
brabo.replication.status()
brabo.innodb.cluster()
Migração para a API oficial de extensões do Shell.
""".format(__version__))


# ---------------------------------------------------------------------
# Registro global
# ---------------------------------------------------------------------
brabo = Brabo()
globals.brabo = brabo

print("DBA BRABO extension v{} loaded. Type brabo.help() for usage.".format(__version__))
