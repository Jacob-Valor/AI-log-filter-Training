# =============================================================================

# AI Log Filter - .gitignore

# =============================================================================

# -----------------------------------------------------------------------------

# Python

# -----------------------------------------------------------------------------

**pycache**/
_.py[cod]
_$py.class
_.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
_.egg-info/
.installed.cfg
\*.egg

# Virtual environments

venv/
ENV/
env/
.venv/
.ve/

# mypy

.mypy_cache/
.dmypy.json
dmypy.json

# PyInstaller

_.manifest
_.spec

# Jupyter Notebook

.ipynb_checkpoints/

# IPython

profile_default/
ipython_config.py

# -----------------------------------------------------------------------------

# IDEs and Editors

# -----------------------------------------------------------------------------

.vscode/
.idea/
_.swp
_.swo
\*~
.project
.pydevproject
.cproject
.settings/

# Eclipse

.metadata/
bin/
tmp/
_.tmp
_.bak
_.swp
_~.nib
local.properties
.serverpath/

# NetBeans

/nbproject/private/
/nbbuild/
/dist/
/nbdist/
/nbactions.xml
/.nb-gradle/

# Visual Studio Code

.vscode/

# -----------------------------------------------------------------------------

# Docker

# -----------------------------------------------------------------------------

.docker/

# -----------------------------------------------------------------------------

# Models and Data (keep structure, ignore contents)

# -----------------------------------------------------------------------------

models/**/_
!models/.gitkeep
!models/_/.gitkeep
!models/**/.gitkeep

data/**/_
!data/.gitkeep
!data/_/.gitkeep
!data/**/.gitkeep

processed/\*_/_
!processed/.gitkeep
!processed/\*/.gitkeep

raw/\*_/_
!raw/.gitkeep

# -----------------------------------------------------------------------------

# Logs and Artifacts

# -----------------------------------------------------------------------------

logs/
_.log
_.log._
artifacts/
_.tar
_.tar.gz
_.zip

# -----------------------------------------------------------------------------

# Configuration (keep templates, ignore secrets)

# -----------------------------------------------------------------------------

configs/\*.local.yaml
configs/local.yaml
!configs/template.yaml

# Environment files - keep template, ignore actual

.env
.env.local
.env.\*.local
!.env.example

# -----------------------------------------------------------------------------

# Testing

# -----------------------------------------------------------------------------

.pytest_cache/
.coverage
htmlcov/
.coveragerc
cov.xml

# -----------------------------------------------------------------------------

# OS Files

# -----------------------------------------------------------------------------

.DS*Store
.DS_Store?
.*\*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# -----------------------------------------------------------------------------

# CI/CD

# -----------------------------------------------------------------------------

.github/outputs/
.github/workflows/\*/

# -----------------------------------------------------------------------------

# Misc

# -----------------------------------------------------------------------------

_.bak
_.tmp
_.temp
temp/
tmp/
.tox/
.nox/
.coverage_
.cache/
.pytest*cache/
*/.pytest*cache/
*/.hypothesis/
_.manifest
_.spec

# -----------------------------------------------------------------------------

# Secrets and Credentials (never commit)

# -----------------------------------------------------------------------------

_.pem
_.key
_.crt
credentials.json
service-account_.json
_.p12
_.pfx

# -----------------------------------------------------------------------------

# Documentation Build

# -----------------------------------------------------------------------------

docs/\_build/
docs/.doctrees/
site/

# -----------------------------------------------------------------------------

# macOS

# -----------------------------------------------------------------------------

_.DS_Store
_.apple*double
\*.LSOverride
.*\*

# -----------------------------------------------------------------------------

# Linux

# -----------------------------------------------------------------------------

_~
.fuse_hidden_
.nfs*
.SFS*

# -----------------------------------------------------------------------------

# Windows

# -----------------------------------------------------------------------------

Thumbs.db
ehthumbs.db
Desktop.ini
$RECYCLE.BIN/
\*.lnk

# -----------------------------------------------------------------------------

# Terraform

# -----------------------------------------------------------------------------

_.tfstate
_.tfstate.backup
.terraform/
_.tfvars
!_.tfvars.example

# -----------------------------------------------------------------------------

# Temporary Files

# -----------------------------------------------------------------------------

_.tmp
_.temp
temp/
tmp/
.Temp/
.Temporary/
