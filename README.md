# Stock Researcher

A comprehensive stock research application that helps users cut through the noise of unreliable sources and access information directly from official company websites and trusted sources.

## Architecture

This project uses a modern, microservices architecture:

- **Frontend**: React application with responsive UI
- **Backend**: Python Flask API with RESTful endpoints
- **Containerization**: Docker for consistent deployment

## Features

- Direct source analysis from official company websites
- Filtering of unreliable sources and paid promotions
- AI-powered summaries of stock performance and outlook
- Responsive design for all devices

## Running with Docker Compose

The easiest way to run the application is using Docker Compose:

```bash
docker-compose up -d
```

This will start both the frontend and backend services. The frontend will be available at http://localhost and the backend API at http://localhost/api.

## Deploying to MCP Servers

To deploy to MCP servers:

1. Make sure Docker is installed on your MCP server
2. Clone this repository to your server
3. Update the `.env` file in the frontend to point to your MCP server URL
4. Run `docker-compose up -d` to start the containers

## Backend API Endpoints

- `GET /api/stocks` - Get a list of all available stocks
- `GET /api/stocks/:symbol` - Get detailed information for a specific stock
- `GET /api/search?symbol=:symbol` - Search for a stock by its ticker symbol

## Development Setup

### Frontend

```bash
cd stock-researcher
npm install
npm start
```

### Backend

```bash
cd stock-researcher-backend
pip install -r requirements.txt
python app.py
``` 