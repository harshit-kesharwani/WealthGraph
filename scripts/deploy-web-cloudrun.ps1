# Deploy static frontend to Cloud Run (from repo root)
# Prerequisite: cd frontend && npm run build
$ErrorActionPreference = "Stop"
$Project = "genaicohert"
$Region = "us-central1"
$Image = "$Region-docker.pkg.dev/$Project/wealthgraph/web:latest"
$Service = "wealthgraph-web"
$Root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $Root "frontend/out/index.html"))) {
  Write-Host "ERROR: Run first: cd frontend && npm run build" -ForegroundColor Red
  exit 1
}

gcloud config set project $Project
Set-Location $Root

gcloud builds submit --config=cloudbuild.web.yaml --project=$Project .

gcloud run deploy $Service `
  --image $Image `
  --region $Region `
  --project $Project `
  --allow-unauthenticated `
  --memory 256Mi `
  --port 8080

Write-Host "`nAdd the new Cloud Run URL to wealthgraph-api CORS if this is first deploy." -ForegroundColor Yellow
