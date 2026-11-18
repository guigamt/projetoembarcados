"""Entrada para o gunicorn (Azure App Service):  gunicorn --workers 1 --threads 8 wsgi:app"""
from app import cria_app

app = cria_app()
app.central.inicia()
