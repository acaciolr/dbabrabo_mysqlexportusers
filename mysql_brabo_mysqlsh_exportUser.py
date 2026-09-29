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
#  Repo     : https://github.com/acaciolr/dbabrabo_mysqlexportusers
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

__version__ = "2.3"

SYSTEM_USERS = (
    "mysql.sys",
    "mysql.session",
    "mysql.infoschema",
    "mariadb.sys",
    "mariadb.session",
)


# ---------------------------------------------------------------------
# Helpers de sessao (leem globals.session SEMPRE frescos)
# ---------------------------------------------------------------------
def _get_session():
    """Devolve a sessao ATUAL do MySQL Shell, ou None se nao conectado.

    Importante: le globals.session a cada chamada. O autoload do
    init.d roda ANTES do usuario conectar, entao capturar a sessao
    no import faria ela ficar presa em None.
    """
    try:
        return globals.session
    except Exception:
        return None


def _get_shell():
    try:
        return globals.shell
    except Exception:
        return None


class Brabo(object):
    """DBA BRABO - export e dump de metadados de seguranca."""

    # -----------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------
    @property
    def session(self):
        """Sessao atual (sempre fresca)."""
        return _get_session()

    @property
    def shell(self):
        """Shell atual (sempre fresco)."""
        return _get_shell()

    def _check_session(self):
        if self.session is None:
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

        result = self.session.run_sql(sql, args)
        return [(r[0], r[1]) for r in result.fetch_all()]

    def _user_ddl(self, user, host):
        """Devolve (create_stmt, alter_stmt) para uma conta."""
        acc = self._quote_account(user, host)
        row = self.session.run_sql("SHOW CREATE USER {}".format(acc)).fetch_one()
        create = row[0]
        if create.upper().startswith("CREATE USER"):
            create = "CREATE USER IF NOT EXISTS" + create[len("CREATE USER"):]
        alter = create.replace("CREATE USER IF NOT EXISTS", "ALTER USER", 1)
        return create, alter

    def _user_grants(self, user, host):
        acc = self._quote_account(user, host)
        sql = "SHOW GRANTS FOR {}".format(acc)
        return [r[0] for r in self.session.run_sql(sql).fetch_all()]

    # -----------------------------------------------------------------
    # Conversao MariaDB -> MySQL
    # -----------------------------------------------------------------
    def _convert_mariadb_to_mysql(self, stmt):
        """Converte sintaxe proprietaria do MariaDB para MySQL valido."""
        if not stmt:
            return stmt

        s = stmt

        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+USING\s+PASSWORD\('([^']*)'\)",
            r"IDENTIFIED WITH \1 BY '\2'",
            s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+USING\s+",
            r"IDENTIFIED WITH \1 AS ",
            s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"IDENTIFIED\s+VIA\s+(\S+)\s+AS\s+",
            r"IDENTIFIED WITH \1 AS ",
            s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s+OR\s+(unix_socket|ed25519|auth_pam|mysql_old_password|pam)\b",
            "", s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s+IDENTIFIED\s+BY\s+PASSWORD\s+'[^']*'",
            "", s, flags=re.IGNORECASE,
        )
        s = re.sub(
            r"\s+IDENTIFIED\s+BY\s+'[^']*'",
            "", s, flags=re.IGNORECASE,
        )
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
        """Converte uma linha de SHOW GRANTS em REVOKE."""
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

    def _supports_gtid(self):
        try:
            row = self.session.run_sql("SELECT @@gtid_mode").fetch_one()
            return bool(row) and row[0] in ("ON", "OFF_PERMISSIVE", "ON_PERMISSIVE")
        except Exception:
            return False

    def _build_manifest(self):
        """Cria manifesto novo no formato do util.dumpInstance()."""
        try:
            host = self.session.run_sql("SELECT @@hostname").fetch_one()[0]
            vers = self.session.run_sql("SELECT @@version").fetch_one()[0]
            charset = self.session.run_sql(
                "SELECT @@character_set_server"
            ).fetch_one()[0]
            gtid = ""
            if self._supports_gtid():
                try:
                    gtid = self.session.run_sql(
                        "SELECT @@gtid_executed"
                    ).fetch_one()[0] or ""
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
                row = self.session.run_sql(
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
    # v1.1 - export em arquivo unico
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
        """Exporta CREATE USER / ALTER USER / GRANTs (ou REVOKEs)."""
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

        server = self.session.run_sql("SELECT @@hostname").fetch_one()[0]
        version = self.session.run_sql("SELECT @@version").fetch_one()[0]

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
        """Atalho para export_grants(mode='revoke')."""
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
        util.dumpInstance().
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

Roadmap (v2.4+)
---------------
brabo.grants.diff()
brabo.security.audit()
brabo.replication.status()
brabo.innodb.cluster()
Ordenacao deterministica de GRANTs para Git
Migracao para a API oficial de extensoes do Shell
""".format(__version__))

# ---------------------------------------------------------------------
# Autoload robusto
# ---------------------------------------------------------------------
# Cria a instancia SEMPRE, independente do contexto.
brabo = Brabo()

# Registra em globals.brabo (usado quando o Shell carrega via init.d).
try:
    globals.brabo = brabo
    _registered = True
except Exception:
    _registered = False

# Mensagem de carregamento (sempre visivel, ajuda no diagnostico).
if _registered:
    print("DBA BRABO extension v{} loaded. Type brabo.help() for usage.".format(__version__))
else:
    print("DBA BRABO extension v{} loaded (import direto). Use from brabo import brabo.".format(__version__))
