# EPMS Backend

## 1. Project Title and Description

**Electronic Pharmacy Management System (EPMS) - Backend API**

EPMS Backend is a comprehensive, production-ready REST API built with FastAPI for managing pharmacy operations. The system provides a complete solution for inventory management, order processing, payment handling, customer management, reporting, and content management.

The backend follows modern software architecture principles with a layered design, implementing role-based access control (RBAC), JWT authentication, and support for multiple database systems optimized for different use cases. It's designed to be scalable, secure, and maintainable, supporting both web applications and third-party integrations.

**Key Highlights:**
- Asynchronous, high-performance API built with FastAPI
- Multi-database architecture (PostgreSQL, Redis, MongoDB)
- Comprehensive security with JWT authentication and RBAC
- Full-featured pharmacy management capabilities
- RESTful API with OpenAPI documentation
- Production-ready with logging, error handling, and monitoring

---

## 2. Features

### Authentication & Authorization
- **Dual Authentication Methods**: Email/Password for admins, Phone/OTP for customers
- **JWT Token Management**: Access and refresh token mechanism with token revocation
- **Role-Based Access Control (RBAC)**: Granular permissions system
- **Session Management**: Device and IP tracking for security
- **Secure Password Hashing**: Argon2 algorithm for password security

### Inventory Management
- Medicine catalog with categories, tags, and alternate medicines
- Batch tracking with expiry dates and stock management
- GST configuration and pricing management
- Side effects tracking and medicine information
- Advanced search and filtering capabilities

### Order Management
- Shopping cart functionality
- Order processing with multiple status workflows
- Prescription-based orders
- Request orders for out-of-stock items
- Family member order support
- Complete order history and tracking

### Payment & Financial
- Multiple payment status tracking
- Invoice generation and management
- Payment gateway integration support
- Discount and coupon management
- Financial reporting

### Reporting & Analytics
- Sales reports with date range filtering
- Inventory reports
- Export capabilities (Excel, PDF)
- Dashboard analytics
- Custom report generation

### Additional Features
- **File Management**: Upload and storage using MongoDB GridFS
- **Email Notifications**: SMTP integration for email sending
- **SMS Notifications**: Twilio integration for SMS
- **Content Management System (CMS)**: Manage banners, features, policies
- **Issue Tracking**: Customer issue management system
- **Review System**: Product reviews and ratings
- **Audit Logging**: Comprehensive operation logging
- **Backup & Restore**: Automated database backup and restore
- **Rate Limiting**: API rate limiting for abuse prevention

---

## 3. Technology Stack

### Core Framework
- **FastAPI** (0.119.1): Modern, fast web framework for building APIs
- **Python** (3.13): Programming language
- **Uvicorn** (0.37.0): ASGI server for running FastAPI

### Databases
- **PostgreSQL**: Primary relational database (via asyncpg/psycopg)
- **Redis** (7.0.1): Caching and session storage
- **MongoDB**: Document storage and GridFS for files (via motor/pymongo)

### ORM & Database Tools
- **SQLAlchemy** (2.0.44): Async ORM for PostgreSQL
- **Alembic** (1.17.0): Database migration tool
- **Motor** (3.7.1): Async MongoDB driver

### Authentication & Security
- **PyJWT / python-jose** (3.5.0): JWT token handling
- **passlib** (1.7.4): Password hashing
- **argon2-cffi** (25.1.0): Secure password hashing algorithm
- **fastapi-limiter** (0.1.6): Rate limiting middleware

### API & Validation
- **Pydantic** (2.12.3): Data validation and settings management
- **pydantic-settings** (2.11.0): Settings management

### External Integrations
- **fastapi-mail** (1.5.7): Email sending (SMTP)
- **twilio** (9.8.5): SMS notifications
- **aiohttp** (3.13.2): Async HTTP client

### Utilities
- **pandas** (2.3.3): Data processing for reports
- **openpyxl** (3.1.5): Excel file generation
- **reportlab** (4.4.4): PDF generation
- **python-dotenv** (1.2.1): Environment variable management

### Development Tools
- **pytest**: Testing framework
- **flake8** (7.3.0): Code linting
- **isort** (7.0.0): Import sorting

---

## 4. Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software
- **Python 3.13+**: [Download Python](https://www.python.org/downloads/)
- **PostgreSQL 12+**: [Download PostgreSQL](https://www.postgresql.org/download/)
- **Redis 6+**: [Download Redis](https://redis.io/download)
- **MongoDB 5+**: [Download MongoDB](https://www.mongodb.com/try/download/community)
- **Git**: [Download Git](https://git-scm.com/downloads)

### Optional but Recommended
- **Docker & Docker Compose**: For containerized deployment
- **Postman or Insomnia**: For API testing
- **Nvim**: For development

### System Requirements
- **RAM**: Minimum 4GB (8GB recommended)
- **Disk Space**: At least 2GB free space
- **Operating System**: Linux, macOS, or Windows (WSL recommended for Windows)

---

## 5. Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/MohammedNayeemE/medico-store-backend.git 
cd medico-store-backend 
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Create Environment File

Create a `.env` file in the root directory:

```bash
touch .env
```

See the [Environment Variables](#6-environment-variables) section for required configuration.

### Step 5: Install and Start Databases

#### PostgreSQL Setup

```bash
# Install PostgreSQL (if not already installed)
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# Fedora
sudo dnf install postgresql

# macOS (using Homebrew):
brew install postgresql

# Start PostgreSQL service
sudo systemctl start postgresql  # Linux
brew services start postgresql  # macOS
```

#### Redis Setup

```bash
# Install Redis (if not already installed)
# Ubuntu/Debian:
sudo apt-get install redis-server

# macOS (using Homebrew):
brew install redis

# Start Redis service
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

#### MongoDB Setup

```bash
# Install MongoDB (if not already installed)
# Ubuntu/Debian:
sudo apt-get install mongodb

# macOS (using Homebrew):
brew install mongodb-community

# Start MongoDB service
sudo systemctl start mongod  # Linux
brew services start mongodb-community  # macOS
```

### Step 6: Database Setup

See the [Database Setup](#7-database-setup) section for detailed instructions.

---

## 6. Environment Variables

Create a `.env` file in the root directory with the following variables:

### Application Configuration

```env
# Application Info
APP_NAME=EPMS Backend
APP_VERSION=1.0.0

# Environment
DEV=true
DEBUG=true
PRODUCTION_URL=https://your-production-domain.com
```

### Database Configuration

```env
# PostgreSQL Database
DB_URL=postgresql+asyncpg://username:password@localhost:5432/epms_db
POSTGRES_HOST=localhost
POSTGRES_USER=your_postgres_user
POSTGRES_DB=epms_db

# MongoDB
MONGO_DB_URL=mongodb://localhost:27017
MONGO_DB_NAME=epms_content
MONGO_URI=mongodb://localhost:27017/epms_content
```

### Authentication & Security

```env
# JWT Configuration
ACCESS_SECRET_TOKEN=your-super-secret-access-token-key-change-this-in-production
REFRESH_SECRET_TOKEN=your-super-secret-refresh-token-key-change-this-in-production
ALGORITHM=HS256

# Token Expiration (in minutes for access, days for refresh)
ACCESS_TOKEN_EXPIRES=30
REFRESH_TOKEN_EXPIRES=7
```

### Email Configuration (SMTP)

```env
# Email Settings
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
```

### SMS Configuration (Twilio)

```env
# Twilio SMS Settings
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890
```

### reCAPTCHA (Optional)

```env
# reCAPTCHA Configuration
RECAPTCHA_SECRET_KEY=your-recaptcha-secret-key
RECAPTCHA_SITE_KEY=your-recaptcha-site-key
CAPTCHA_BYPASS=false
```

### Backup Configuration

```env
# Backup & Restore Directories
BACKUP_DIR=/path/to/backup/directory
RESTORE_DIR=/path/to/restore/directory
```

### Security Notes

⚠️ **Important**: 
- Never commit the `.env` file to version control
- Use strong, unique secrets for production
- Rotate secrets regularly
- Use environment-specific configurations for different environments

---

## 7. Database Setup

### PostgreSQL Setup

1. **Create Database and User**

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database
CREATE DATABASE epms_db;

# Create user (optional, or use existing user)
CREATE USER epms_user WITH PASSWORD 'your_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE epms_db TO epms_user;

# Exit PostgreSQL
\q
```

2. **Update `.env` file** with your PostgreSQL credentials

3. **Run Database Migrations**

```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

**Note**: The application will automatically create tables on startup if they don't exist, but migrations are recommended for production.

### Redis Setup

1. **Verify Redis is Running**

```bash
redis-cli ping
# Should return: PONG
```

2. **Configure Redis** (if needed)

Edit `/etc/redis/redis.conf` or your Redis configuration file:

```conf
# Allow connections from localhost (default)
bind 127.0.0.1

# Set password (optional but recommended for production)
requirepass your_redis_password
```

3. **Update `.env`** if you set a Redis password (you'll need to update the connection string in `app/core/database.py`)

### MongoDB Setup

1. **Verify MongoDB is Running**

```bash
mongosh
# Should connect successfully
```

2. **Create Database** (optional, MongoDB creates databases automatically)

```javascript
use epms_content
```

3. **GridFS** is automatically configured by the application

### Seed Initial Data

After setting up the databases, seed initial roles and permissions:

```python
# Run the seed script
python -c "
import asyncio
from app.core.database import async_session
from app.utils.seed import seed_roles_and_permissions

async def main():
    async with async_session() as db:
        await seed_roles_and_permissions(db)
        print('✅ Database seeded successfully!')

asyncio.run(main())
"
```

Or create a simple script `seed_db.py`:

```python
import asyncio
from app.core.database import async_session
from app.utils.seed import seed_roles_and_permissions

async def main():
    async with async_session() as db:
        await seed_roles_and_permissions(db)
        print('✅ Database seeded successfully!')

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python seed_db.py
```

---

## 8. Running the Application

### Development Mode

1. **Start the Development Server**

```bash
# Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using FastAPI CLI
fastapi dev app/main.py
```

2. **Access the Application**

- **API Base URL**: `http://localhost:8000/api/v1`
- **API Documentation**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Production Mode

1. **Run with Production Settings**

```bash
# Set DEV=false in .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

2. **Using Gunicorn (Recommended for Production)**

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker Deployment

```bash
# Build the image
docker build -t epms-backend .

# Run the container
docker run -d -p 8000:8000 --env-file .env epms-backend
```

### Verify Installation

1. **Check Health Endpoint**

```bash
curl http://localhost:8000/api/v1/
```

Expected response:
```json
{
  "msg": "the server is running"
}
```

2. **Check Database Connections**

The application will print connection status on startup:
- ✅ PostgreSQL tables created
- ✅ Redis connection established
- ✅ MongoDB connection ready

---

## 9. Development Guidelines

### Code Style

1. **Follow PEP 8** Python style guide
2. **Use type hints** for all function parameters and return types
3. **Write docstrings** for all classes and functions
4. **Keep functions small** and focused on a single responsibility

### Project Structure

```
epms-backend/
├── app/
│   ├── api/              # API routes and dependencies
│   │   ├── routes/       # Route handlers
│   │   └── dependecies/ # FastAPI dependencies
│   ├── core/             # Core configuration
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── middlewares/      # Custom middlewares
│   ├── utils/            # Utility functions
│   └── main.py           # Application entry point
├── alembic/              # Database migrations
├── docs/                 # Documentation
├── tests/                # Test files
├── requirements.txt      # Python dependencies
├── alembic.ini           # Alembic configuration
└── .env                  # Environment variables (not in git)
```

### Naming Conventions

- **Files**: Use snake_case (e.g., `auth_service.py`)
- **Classes**: Use PascalCase (e.g., `AuthService`)
- **Functions/Variables**: Use snake_case (e.g., `get_current_user`)
- **Constants**: Use UPPER_SNAKE_CASE (e.g., `ACCESS_TOKEN_EXPIRES`)

### Adding New Features

1. **Create Models** in `app/models/`
2. **Create Schemas** in `app/schemas/`
3. **Create Services** in `app/services/`
4. **Create Routes** in `app/api/routes/`
5. **Register Routes** in `app/main.py`
6. **Create Migrations** using Alembic

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

### Code Quality

```bash
# Lint code
flake8 app/

# Format imports
isort app/

# Type checking (if using mypy)
mypy app/
```

### Git Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Commit with descriptive messages
4. Push to remote: `git push origin feature/your-feature-name`
5. Create a pull request

### Best Practices

- **Error Handling**: Always use try-except blocks and return appropriate HTTP status codes
- **Logging**: Use the logging module for important operations
- **Security**: Never log sensitive information (passwords, tokens)
- **Validation**: Always validate input using Pydantic schemas
- **Async**: Use async/await for I/O operations
- **Transactions**: Use database transactions for multi-step operations

---

## 10. How to Contribute

We welcome contributions! Please follow these guidelines:

### Getting Started

1. **Fork the repository**
2. **Clone your fork**: `git clone https://github.com/MohammedNayeemE/medico-store-backend.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`
4. **Make your changes**
5. **Test your changes**: Ensure all tests pass
6. **Commit your changes**: Use clear, descriptive commit messages
7. **Push to your fork**: `git push origin feature/your-feature-name`
8. **Create a Pull Request**

### Contribution Guidelines

1. **Code Quality**
   - Follow the project's code style
   - Write tests for new features
   - Ensure all tests pass
   - Update documentation as needed

2. **Commit Messages**
   - Use clear, descriptive messages
   - Follow conventional commit format:
     - `feat:` for new features
     - `fix:` for bug fixes
     - `docs:` for documentation
     - `refactor:` for code refactoring
     - `test:` for tests
     - `chore:` for maintenance
   - using git emojis is recommended

3. **Pull Request Process**
   - Provide a clear description of changes
   - Reference any related issues
   - Ensure CI/CD checks pass
   - Request review from maintainers

4. **Reporting Issues**
   - Use GitHub Issues
   - Provide clear description
   - Include steps to reproduce
   - Include error messages/logs
   - Specify environment details

### Development Setup for Contributors

1. Follow the [Installation and Setup](#5-installation-and-setup) guide
2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov black mypy
   ```
3. Set up pre-commit hooks (if available)
4. Run tests before committing

### Code Review Process

- All contributions require review
- Address feedback promptly
- Maintainers will merge approved PRs

---


### Additional Resources

- **API Documentation**: Available at `/docs` endpoint when server is running
- **Architecture Documentation**: See `docs/System_Architecture.md`
- **Authentication Documentation**: See `docs/Auth_Role_Documentation.md`

---

## Additional Information

### API Endpoints Overview

- **Authentication**: `/api/v1/auth/*`
- **Users & Profiles**: `/api/v1/profile/*`, `/api/v1/roles/*`
- **Inventory**: `/api/v1/inventory/*`
- **Orders**: `/api/v1/orders/*`, `/api/v1/cart/*`
- **Payments**: `/api/v1/payments/*`
- **Reports**: `/api/v1/reports/*`
- **Notifications**: `/api/v1/notifications/*`
- **Content**: `/api/v1/content/*`
- **Files**: `/api/v1/files/*`
- **Dashboard**: `/api/v1/dashboard/*`

### Troubleshooting

**Common Issues:**

1. **Database Connection Errors**
   - Verify PostgreSQL/Redis/MongoDB are running
   - Check connection strings in `.env`
   - Verify database credentials

2. **Import Errors**
   - Ensure virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

3. **Port Already in Use**
   - Change port: `uvicorn app.main:app --port 8001`
   - Or kill the process using the port

4. **Migration Errors**
   - Check database connection
   - Verify Alembic configuration
   - Review migration files for errors

---

**Last Updated**: 2025
