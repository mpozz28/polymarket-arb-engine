# Usa un'immagine ufficiale di Python leggera per ridurre le dimensioni
FROM python:3.12-slim

# Imposta la cartella di lavoro all'interno del container
WORKDIR /app

# Disabilita il buffering dell'output per vedere i log di Python in tempo reale
ENV PYTHONUNBUFFERED=1

# Copia solo il file dei requisiti per sfruttare la cache di Docker
COPY requirements.txt .

# Installa le dipendenze senza salvare la cache per mantenere l'immagine leggera
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto del codice sorgente
COPY . .

# Comando per avviare il motore
CMD ["python", "run_live.py"]