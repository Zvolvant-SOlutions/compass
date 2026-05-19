# Hosting Compass

Compass deploys to **Streamlit Community Cloud** for v1 (single tenant, FERC
demo / pilot). For production we will lift it to **Azure App Service**
fronted by **Azure AD / Entra SSO** with **Azure SQL** as the database — the
data layer is parameterized so the migration is a config change, not a
rewrite.

## v1 — Streamlit Community Cloud

1. Push `main`. The repo at `Zvolvant-SOlutions/compass` is **public** so
   Streamlit Cloud can clone it without deploy keys (same as the NIST tool).
2. Go to https://share.streamlit.io → **Create app** → **Public app from GitHub**.
3. Form:
   - Repository: `Zvolvant-SOlutions/compass`
   - Branch: `main`
   - Main file: `streamlit_app.py`
   - App URL: `zvolvant-compass` (or similar; avoid the substring `sso`)
4. Click **Advanced settings → Secrets** and paste:

   ```
   COMPASS_HASH_SALT = "production-salt-value-here"
   ```

5. Click **Deploy**. First build is ~3 minutes.
6. After the build settles, the app cold-starts with an empty DB. On the first
   request, `db.init_db()` creates the schema. **The seed users are NOT
   created automatically in production** — run `scripts/seed_db.py` once
   manually (e.g., via a Streamlit Cloud one-off) or create users via a
   provisioning script.

## v2 — Azure App Service

When the FERC pilot graduates to production:

1. Provision an Azure App Service for Linux (Python 3.12) in the FERC tenant.
2. Provision Azure SQL Database and set `COMPASS_DB_PATH` to the connection
   string (would need a small change in `db.py` to use SQLAlchemy + pyodbc
   instead of sqlite3 — half a day of work).
3. Register an Azure AD application; set `AZURE_AD_TENANT_ID`,
   `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET` in App Service config.
   The login page automatically surfaces the "Sign in with Microsoft Entra"
   button when those secrets are present.
4. Provision an ADO PAT scoped to the FERC ADO organization; set `ADO_ORG`,
   `ADO_PROJECT`, `ADO_PAT`. Complete `_fetch_sprints_from_ado()` in
   `ado_connector.py`.
5. Set up CI/CD via GitHub Actions or Azure Pipelines — repo already has
   pytest + ruff configured.

## Production hardening checklist

- [ ] Replace SQLite with Azure SQL or Postgres
- [ ] Move audit log to an append-only blob or Event Hub for tamper-evidence
- [ ] Enable Azure AD SSO (`AZURE_AD_*` secrets)
- [ ] Wire live ADO sync (`ADO_*` secrets + complete the connector)
- [ ] Set `COMPASS_HASH_SALT` to a random 256-bit value, distinct from dev
- [ ] Replace the default seed users with provisioned accounts
- [ ] Configure Azure Application Insights for telemetry
- [ ] Encrypt evidence attachments in transit and at rest (SharePoint links
      via Azure AD app-only access)
- [ ] Document the disaster-recovery plan (Azure SQL geo-redundancy + repo
      backup)
