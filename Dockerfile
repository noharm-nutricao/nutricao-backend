FROM python:3.11-slim

WORKDIR /app

# copiar requirements
COPY requirements.txt .

# instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# copiar código
COPY . .

# criar usuário sem privilégios
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# porta da API
EXPOSE 5000

# rodar flask
CMD ["python", "mobile.py"]

