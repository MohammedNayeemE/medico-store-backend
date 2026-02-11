# EPMS Backend

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/MohammedNayeemE/medico-store-backend)

## Project Overview

The Electronic Pharmacy Management System (EPMS) Backend is a robust REST API designed to manage pharmacy operations including inventory, order processing, payment handling, customer management, reporting, and content management. It emphasizes scalability, integration, and security for both web and third-party applications.

## Technical Overview / Architecture

- **Framework:** FastAPI (asynchronous Python web framework)
- **Databases:**
  - PostgreSQL (primary)
  - Redis (cache/session)
  - MongoDB (content/files)
- **Key Architecture Elements:**
  - Layered design (API, service, models, storage, utilities)
  - Role-Based Access Control (RBAC) & JWT authentication
  - Multi-database support for optimized storage
  - Production-ready logging, error handling, monitoring, and audit logging

>
> **DeepWiki code documentation & Q&A:** [https://deepwiki.com/MohammedNayeemE/medico-store-backend](https://deepwiki.com/MohammedNayeemE/medico-store-backend)

## Setup & Run Instructions

### Prerequisites
- Python 3.13+
- PostgreSQL 12+
- Redis 6+
- MongoDB 5+

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/MohammedNayeemE/medico-store-backend.git
   cd medico-store-backend
   ```
2. **Create a virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Configure environment:**
   ```bash
   touch .env
   # Edit .env with your configuration (see Environment Variables section)
   ```
4. **Install & Start Databases** (follow [Database Setup](#database-setup) for OS-specific steps)
5. **Initialize databases and run migrations** (see [Database Setup](#database-setup))
6. **Run the backend:**
   ```bash
   uvicorn app.main:app --reload
   # Docs available at http://localhost:8000/docs
   ```

## Key Design Decisions
- **Async modular FastAPI architecture** for scalability & maintainability.
- **Strict separation of concerns** (API, service, storage, etc.) to promote clear tests and robust logic.
- **Multi-database strategy** (Postgres/Redis/MongoDB) optimizes for transactional and non-transactional data.
- **Security and audit**: JWT, RBAC, secure password handling, device/session tracking, rate limiting, and comprehensive audit logging.
- **Automatic OpenAPI docs** for easy developer handoff and third-party consumption.
- **Contributor-friendly**: style guides, migration scripts, and project structure guidelines included
- **Flexible environment configuration** and .env usage for smooth operation across dev, staging, and production.

## Documentation
- **API documentation:** Auto-generated at `/docs` after server startup
- **Deep System Architecture:** [docs/System_Architecture.md](docs/System_Architecture.md)
- **DeepWiki code documentation & Q&A:** [https://deepwiki.com/MohammedNayeemE/medico-store-backend](https://deepwiki.com/MohammedNayeemE/medico-store-backend)

## Additional Resources
- [docs/Auth_Role_Documentation.md](docs/Auth_Role_Documentation.md)
- Troubleshooting and support in the `docs/` folder

---

## Contributing
TBD

_Last updated: 2025_

