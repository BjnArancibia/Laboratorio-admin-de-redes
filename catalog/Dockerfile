# Dockerfile HEREDADO del servicio catalog (lo dejó el equipo anterior).
# Funciona, pero tiene varios problemas. Tu trabajo es dejarlo listo para producción.
FROM python:3.12


COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
