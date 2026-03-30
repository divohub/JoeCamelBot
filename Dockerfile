# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create a data directory for the database
RUN mkdir -p /app/data

# Environment variables (to be overridden by .env or docker-compose)
ENV PYTHONUNBUFFERED=1

# Command to run the bot
CMD ["python", "main.py"]
