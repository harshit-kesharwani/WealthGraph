# WealthGraph AI — deploy API to Cloud Run (project: genaicohert)
# Prerequisite: run in an interactive terminal:
#   gcloud auth login er.harshitkesharwani@gmail.com
#   gcloud config set account er.harshitkesharwani@gmail.com
#   gcloud config set project genaicohert

$ErrorActionPreference = "Stop"
$Project = "genaicohert"
$Region = "us-central1"
$Repo = "wealthgraph"
$Image = "$Region-docker.pkg.dev/$Project/$Repo/api:latest"
$Service = "wealthgraph-api"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Project=$Project Region=$Region" -ForegroundColor Cyan

gcloud config set project $Project
gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  firestore.googleapis.com `
  aiplatform.googleapis.com `
  --project $Project

# Describe writes to stderr on NOT_FOUND; avoid terminating the script
cmd /c "gcloud artifacts repositories describe $Repo --location=$Region --project=$Project 1>nul 2>nul"
if ($LASTEXITCODE -ne 0) {
  gcloud artifacts repositories create $Repo `
    --repository-format=docker `
    --location=$Region `
    --project=$Project `
    --description="WealthGraph API images"
}

Set-Location (Join-Path $Root "backend")
gcloud builds submit --tag $Image --project=$Project .

# WARNING: --env-vars-file replaces all container env vars on this revision. Add secrets again in Console if needed.
$frontendUrl = $env:WEALTHGRAPH_CORS_ORIGINS
if ([string]::IsNullOrWhiteSpace($frontendUrl)) {
  $frontendUrl = "https://wealthgraph-web-102631486332.us-central1.run.app"
}

# gcloud --set-env-vars splits on comma; use YAML file so CORS can list multiple origins
$envFile = Join-Path $env:TEMP "wealthgraph-run-env.yaml"
$geminiKey = $env:GEMINI_API_KEY
if ([string]::IsNullOrWhiteSpace($geminiKey)) {
  Write-Host "ERROR: Set GEMINI_API_KEY environment variable before deploying." -ForegroundColor Red
  Write-Host '  $env:GEMINI_API_KEY = "your-key-here"' -ForegroundColor Yellow
  exit 1
}

@"
GCP_PROJECT_ID: "$Project"
GCP_LOCATION: "$Region"
FIREBASE_PROJECT_ID: "genaicohert1firebase"
GEMINI_MODEL: "gemini-2.5-flash"
GEMINI_API_KEY: "$geminiKey"
"@ | Set-Content -Path $envFile -Encoding utf8

gcloud run deploy $Service `
  --image $Image `
  --region $Region `
  --project $Project `
  --allow-unauthenticated `
  --memory 2Gi `
  --timeout 300 `
  --env-vars-file $envFile

Write-Host "`nDone. Frontend uses cloud-config.ts + /api proxy; optional WEALTHGRAPH_CORS_ORIGINS for extra hosts." -ForegroundColor Green
Write-Host "Grant the Cloud Run service account: roles/datastore.user, roles/aiplatform.user (Vertex)." -ForegroundColor Yellow
