# start-hermes.ps1 - Hermes desktop agent (FastAPI :8478). Must run in session 1 (screenshots).
# Reads C:\hermes-bridge\.env (now pointing at the local B60 gateway).
Set-Location 'C:\hermes-bridge'
& 'C:\hermes-bridge\venv\Scripts\python.exe' main.py *> 'V:\AI\logs\hermes.log'
