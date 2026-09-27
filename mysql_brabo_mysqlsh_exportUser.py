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