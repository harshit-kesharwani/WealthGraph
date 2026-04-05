# Drops Cloud Run CORS_ORIGINS so the API uses in-code defaults (see app/config.py).
# Re-deploy the API image after changing defaults in code.
# If you need extra domains, set CORS_ORIGINS in Console and include every origin (comma-separated).
$ErrorActionPreference = "Stop"
$Project = "genaicohert"
$Region = "us-central1"
$Service = "wealthgraph-api"

gcloud run services update $Service `
  --region $Region `
  --project $Project `
  --remove-env-vars CORS_ORIGINS

Write-Host "Removed CORS_ORIGINS from $Service (defaults from API image apply). Redeploy API if you changed config.py." -ForegroundColor Green
