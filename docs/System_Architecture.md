# System Architecture Document

**Project:** Electronic Pharmacy Management System (EPMS) - Backend

**Version:** 1.0

**Last Updated:** 2025

---

## 1. Executive Summary

The Electronic Pharmacy Management System (EPMS) is a comprehensive backend solution designed to manage pharmacy operations including inventory management, order processing, payment handling, customer management, and reporting. Built on modern Python technologies with FastAPI, the system provides a scalable, secure, and performant API architecture that supports both web applications and third-party integrations.

The system employs a layered architecture pattern with clear separation of concerns, implementing authentication and authorization through JWT tokens and role-based access control (RBAC). It utilizes multiple data storage solutions optimized for different use cases: PostgreSQL for transactional data, Redis for caching and session management, and MongoDB GridFS for document and media storage.

Key architectural strengths include:
- **Asynchronous Processing**: Full async/await support for high concurrency
- **Security-First Design**: JWT authentication, RBAC, rate limiting, and audit logging
- **Scalable Data Architecture**: Multi-database approach optimized for different data types
- **Modular Design**: Service-oriented architecture with clear boundaries
- **API-First Approach**: RESTful API with OpenAPI documentation

---

## 2. System Overview

### 2.1 Purpose

The EPMS backend serves as the core business logic and data management layer for a pharmacy management platform. It provides:

- **Inventory Management**: Track medicines, batches, categories, tags, and stock levels
- **Order Management**: Process customer orders, prescriptions, and request orders
- **Payment Processing**: Handle payment transactions and invoice generation
- **User Management**: Support for customers, administrators, and role-based permissions
- **Reporting & Analytics**: Generate sales reports, inventory reports, and business insights
- **Content Management**: Manage banners, features, policies, and promotional content
- **Notification System**: Send notifications via email and SMS (Twilio integration)
- **Audit & Compliance**: Comprehensive audit logging for all system operations
- **Backup & Recovery**: Automated backup and restore capabilities

### 2.2 Key Features

#### Authentication & Authorization
- Dual authentication methods: Email/Password for admins, Phone/OTP for customers
- JWT-based access and refresh token mechanism
- Role-Based Access Control (RBAC) with granular permissions
- Session management with device tracking
- Token revocation and refresh capabilities

#### Inventory Management
- Medicine catalog with categories, tags, and alternate medicines
- Batch tracking with expiry dates and stock management
- GST configuration and pricing management
- Side effects tracking and medicine information
- Inventory search and filtering capabilities

#### Order Management
- Cart management for customers
- Order processing with multiple status workflows
- Prescription-based orders
- Request orders for out-of-stock items
- Family member order support
- Order history and tracking

#### Payment & Financial
- Multiple payment status tracking
- Invoice generation and management
- Payment gateway integration support
- Discount and coupon management
- Financial reporting

#### Reporting & Analytics
- Sales reports with date range filtering
- Inventory reports
- Export capabilities (Excel, PDF)
- Dashboard analytics
- Custom report generation

#### Additional Features
- File upload and management (MongoDB GridFS)
- Email notifications (SMTP integration)
- SMS notifications (Twilio integration)
- Content management system (CMS)
- Issue tracking and management
- Review and rating system
- Audit log tracking
- Automated backup and restore

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                         │
│  (Web App, Third-party Integrations)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS/REST
                         │
┌────────────────────────────▼────────────────────────────────┐
│                    API Gateway / Load Balancer              │
│                    (nginx/Cloud LB)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            Authentication Middleware                  │  │
│  │         (JWT Token Validation & RBAC)                │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │              API Router Layer                         │  │
│  │  • /auth    • /inventory   • /orders                  │  │
│  │  • /payment • /reports     • /notifications           │  │
│  │  • /cart    • /prescriptions • /dashboard             │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │            Business Logic Layer                       │  │
│  │  • Order Processing  • Inventory Management           │  │
│  │  • Payment Processing • Report Generation             │  │
│  │  • Notification Service • File Management              │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │          Data Access Layer (ORM)                     │  │
│  │              SQLAlchemy Models                        │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼────────┐ ┌─────▼──────┐ ┌───────▼────────┐
│   PostgreSQL   │ │   Redis    │ │    MongoDB     │
│   (Primary DB) │ │  (Cache)   │ │  (GridFS)      │
│                │ │            │ │  (Documents)   │
└────────────────┘ └────────────┘ └────────────────┘
```

### Architecture Layers Description

#### Client Layer
- **Web Applications**: Frontend applications consuming the API
- **Third-party Integrations**: External systems integrating with EPMS
- **Mobile Applications**: Mobile apps connecting via REST API

#### API Gateway / Load Balancer
- **nginx or Cloud Load Balancer**: Routes requests, handles SSL termination, load balancing
- **Rate Limiting**: Prevents API abuse at the gateway level
- **Request Routing**: Directs requests to appropriate backend services

#### FastAPI Application Layer

**Authentication Middleware**
- Validates JWT tokens on each request
- Checks token expiration and revocation status
- Verifies user permissions based on RBAC
- Extracts user context for downstream processing

**API Router Layer**
- RESTful endpoint definitions
- Request validation using Pydantic schemas
- Response formatting and error handling
- Route organization by domain (auth, inventory, orders, etc.)

**Business Logic Layer**
- Core business rules and workflows
- Data transformation and computation
- Integration with external services (email, SMS)
- Complex operations orchestration

**Data Access Layer**
- SQLAlchemy ORM for database operations
- Model definitions and relationships
- Query optimization and transaction management
- Database connection pooling

#### Data Storage Layer

**PostgreSQL (Primary Database)**
- Stores all transactional data
- User accounts, roles, permissions
- Inventory, orders, payments
- Audit logs and system configuration
- ACID compliance for data integrity

**Redis (Cache & Session Store)**
- Caching frequently accessed data (permissions, user sessions)
- Rate limiting counters
- OTP storage for customer authentication
- Session management
- Temporary data storage

**MongoDB (Document & File Storage)**
- GridFS for file storage (images, documents)
- Content management data (banners, features, policies)
- Flexible schema for unstructured content
- Media asset management

---

## 4. Component Architecture

### 4.1 Application Layer Components

#### 4.1.1 Core Components

**Configuration Management (`app/core/config.py`)**
- Centralized settings management using Pydantic Settings
- Environment variable loading
- Configuration validation
- Development and production environment support

**Database Connection (`app/core/database.py`)**
- PostgreSQL async engine setup
- Async session factory for database operations
- Redis connection management
- MongoDB client initialization
- GridFS bucket configuration

**Exception Handling (`app/core/exceptions.py`)**
- Custom exception classes
- Standardized error responses
- Error code definitions

**Logging Configuration (`app/core/logging_config.py`)**
- Structured logging setup
- Log level configuration
- Log formatting and output destinations

#### 4.1.2 API Layer Components

**Route Modules (`app/api/routes/`)**
- **auth_routes.py**: Authentication endpoints (login, register, refresh, logout)
- **profile_routes.py**: User profile management
- **role_routes.py**: Role and permission management
- **inventory/**: Medicine, category, batch, tag, GST, side effects, alternates management
- **cart_routes.py**: Shopping cart operations
- **order_routes.py**: Order creation, status updates, order history
- **payment_routes.py**: Payment processing and status tracking
- **prescriptions.py**: Prescription management
- **request_orders.py**: Request order workflow
- **request_medicines_routes.py**: Medicine request management
- **discount_routes.py**: Discount and coupon management
- **review_routes.py**: Product review and rating
- **notification_routes.py**: Notification management
- **report_routes.py**: Report generation and export
- **dashboard_routes.py**: Dashboard data aggregation
- **content_routes.py**: CMS content management
- **backup_routes.py**: Backup and restore operations
- **file_routes.py**: File upload and download
- **issues_routes.py**: Issue tracking and management
- **audit_logs_routes.py**: Audit log viewing

**Dependencies (`app/api/dependecies/`)**
- **auth.py**: Authentication dependencies (get_current_user, permission checking)
- **get_db_sessions.py**: Database session dependencies (PostgreSQL, Redis)

#### 4.1.3 Middleware Components

**Logging Middleware (`app/middlewares/logging_middleware.py`)**
- Request/response logging
- Performance monitoring
- Error tracking

**CORS Middleware**
- Cross-origin resource sharing configuration
- Allowed origins management

**GZip Middleware**
- Response compression for performance
- Configurable compression level

**Trusted Host Middleware**
- Host validation for security
- Prevents host header attacks

**Rate Limiting**
- FastAPILimiter integration
- Per-endpoint rate limiting
- Redis-backed rate limiting

#### 4.1.4 Service Layer Components

**Authentication Services (`app/services/auth_management/`)**
- **auth_service.py**: JWT token generation, validation, password hashing, token revocation

**Profile Management (`app/services/profile_management/`)**
- **profile_service.py**: User profile CRUD operations, profile updates

**Order Management (`app/services/order_management/`)**
- **order_management_service.py**: Order creation, status management, order processing
- **payment_service.py**: Payment processing, payment status updates
- **invoice_service.py**: Invoice generation, invoice management

**Report Management (`app/services/report_management/`)**
- **report_service.py**: General report generation
- **sales_report_service.py**: Sales-specific reports
- **report_export_service.py**: Export to Excel, PDF formats

**Core Services**
- **inventory_service.py**: Inventory operations, stock management
- **cart_service.py**: Shopping cart operations
- **notification_service.py**: Email and SMS notification sending
- **mail_service.py**: Email service integration
- **file_service.py**: File upload/download operations
- **content_services.py**: CMS content management
- **discount_service.py**: Discount calculation and application
- **review_service.py**: Review and rating management
- **issue_service.py**: Issue tracking and resolution
- **backup_service.py**: Database backup operations
- **restore_service.py**: Database restore operations
- **cache_service.py**: Redis caching operations
- **audit_log_service.py**: Audit log creation and retrieval
- **request_medicine_service.py**: Medicine request processing
- **role_management_service.py**: Role and permission management
- **dashboard_service.py**: Dashboard data aggregation

#### 4.1.5 Data Models (`app/models/`)

**User Management Models (`user_management_models.py`)**
- User, Role, Permission
- ManagementProfile, CustomerProfile
- Session, RevokedToken
- FamilyMember

**Inventory Management Models (`inventory_management_models.py`)**
- Medicine, Category, Tag
- Batch, MedicineCategory, MedicineTag
- GST, SideEffect, AlternateMedicine

**Order Management Models (`order_management_models.py`)**
- Order, OrderItem
- RequestOrder, RequestOrderItem
- Prescription, PrescriptionItem
- Cart, CartItem
- Invoice, Payment
- Discount, Review
- Issue

**Report Management Models (`report_management_models.py`)**
- Report, ReportParameter

**Notification Models (`notification_management_models.py`)**
- Notification

**Content Management Models (`content_management_models.py`)**
- Content stored in MongoDB (flexible schema)

**Backup Models (`backup_models.py`)**
- Backup, BackupFile

**Enums (`enums.py`)**
- OrderStatusEnum, PaymentStatusEnum
- RequestOrderStatusEnum, InvoicePaymentStatusEnum
- RequestStatusEnum, PrescriptionStatusEnum
- ReviewStatusEnum, IssueStatusEnum
- NotificationType, ReportTypeEnum

#### 4.1.6 Schema Components (`app/schemas/`)

Pydantic schemas for request/response validation:
- Request schemas (input validation)
- Response schemas (output formatting)
- Schema organization mirrors model structure
- Type safety and automatic validation

#### 4.1.7 Utility Components (`app/utils/`)

**response_utils.py**
- Standardized response formatting
- Success/error response helpers

**seed.py**
- Database seeding utilities
- Initial data population (roles, permissions)

### 4.2 Data Layer Components

#### 4.2.1 PostgreSQL Database

**Primary Tables:**
- **User Management**: `users`, `roles`, `permissions`, `role_permissions`, `sessions`, `revoked_tokens`, `management_profiles`, `customer_profiles`, `family_members`
- **Inventory**: `medicines`, `categories`, `tags`, `batches`, `medicine_categories`, `medicine_tags`, `gst`, `side_effects`, `alternate_medicines`
- **Orders**: `orders`, `order_items`, `request_orders`, `request_order_items`, `prescriptions`, `prescription_items`, `carts`, `cart_items`
- **Payments**: `invoices`, `payments`, `discounts`
- **Reviews & Issues**: `reviews`, `issues`
- **Reports**: `reports`, `report_parameters`
- **Notifications**: `notifications`
- **Backups**: `backups`, `backup_files`
- **Audit**: `audit_logs`

**Database Features:**
- Foreign key constraints for referential integrity
- Indexes on frequently queried columns
- Soft delete pattern (is_deleted flags)
- Timestamp tracking (created_at, updated_at)
- Async SQLAlchemy for non-blocking operations
- Connection pooling for performance

#### 4.2.2 Redis Cache

**Cache Usage:**
- **Permission Caching**: `permissions:role:{role_id}` - Caches role permissions
- **OTP Storage**: `otp:{phone_number}` - Temporary OTP storage for customer login
- **Session Data**: User session information
- **Rate Limiting**: Request counters for rate limiting
- **General Caching**: Frequently accessed data to reduce database load

**Cache Strategy:**
- TTL-based expiration for temporary data
- Manual invalidation for permission updates
- Cache-aside pattern implementation

#### 4.2.3 MongoDB (GridFS)

**Collections:**
- **GridFS Bucket**: File storage (images, documents, PDFs)
- **Content Collections**: `hero_section`, `banners`, `best_features`, `categories`, `promises`, `policies`
- **Flexible Schema**: Supports dynamic content structure

**Use Cases:**
- Image storage for medicines, banners, user profiles
- Document storage (prescriptions, invoices)
- CMS content with flexible schema
- Media asset management

#### 4.2.4 Database Migration

**Alembic Integration:**
- Version-controlled database migrations
- Migration scripts in `alembic/versions/`
- Automatic table creation on startup
- Schema evolution management

---

## 5. Technology Stack

### Backend Framework
- **FastAPI**: Modern, fast web framework for building APIs
- **Python 3.13**: Programming language
- **Uvicorn**: ASGI server for running FastAPI

### Database & Storage
- **PostgreSQL**: Primary relational database (via asyncpg/psycopg)
- **Redis**: Caching and session storage
- **MongoDB**: Document storage and GridFS for files

### ORM & Database Tools
- **SQLAlchemy 2.0**: Async ORM for PostgreSQL
- **Alembic**: Database migration tool
- **Motor**: Async MongoDB driver

### Authentication & Security
- **PyJWT / python-jose**: JWT token handling
- **passlib**: Password hashing (Argon2)
- **argon2-cffi**: Secure password hashing algorithm

### API & Validation
- **Pydantic**: Data validation and settings management
- **FastAPI-Limiter**: Rate limiting middleware

### External Integrations
- **fastapi-mail**: Email sending (SMTP)
- **Twilio**: SMS notifications
- **aiohttp**: Async HTTP client

### Utilities
- **pandas**: Data processing for reports
- **openpyxl**: Excel file generation
- **reportlab**: PDF generation
- **python-dotenv**: Environment variable management

### Development Tools
- **pytest**: Testing framework
- **flake8**: Code linting
- **isort**: Import sorting

---

## 6. Security Architecture

### 6.1 Authentication
- **JWT Tokens**: Access tokens (short-lived) and refresh tokens (long-lived)
- **Token Revocation**: Database-backed token revocation
- **Session Management**: Device and IP tracking
- **Password Security**: Argon2 hashing algorithm

### 6.2 Authorization
- **Role-Based Access Control (RBAC)**: Role and permission system
- **Permission Scopes**: Granular permission checking per endpoint
- **Security Dependencies**: FastAPI dependency injection for auth

### 6.3 API Security
- **Rate Limiting**: Per-endpoint rate limiting via Redis
- **CORS Configuration**: Controlled cross-origin access
- **HTTPS Enforcement**: Secure cookie settings
- **Input Validation**: Pydantic schema validation
- **SQL Injection Prevention**: SQLAlchemy ORM parameterized queries

### 6.4 Audit & Compliance
- **Audit Logging**: Comprehensive operation logging
- **Soft Deletes**: Data retention with soft delete pattern
- **Timestamp Tracking**: Created/updated timestamps on all entities

---

## 7. Deployment Architecture

### 7.1 Application Deployment
- **Containerization**: Docker support (Dockerfile present)
- **Process Management**: Uvicorn ASGI server
- **Environment Configuration**: Environment variable-based configuration

### 7.2 Database Deployment
- **PostgreSQL**: Standalone or managed database service
- **Redis**: Standalone or managed cache service
- **MongoDB**: Standalone or managed document database

### 7.3 Scalability Considerations
- **Async Architecture**: Non-blocking I/O for high concurrency
- **Connection Pooling**: Database connection pooling
- **Caching Strategy**: Redis caching to reduce database load
- **Horizontal Scaling**: Stateless API design supports multiple instances

---

## 8. API Design

### 8.1 API Structure
- **Base Path**: `/api/v1`
- **RESTful Design**: Standard HTTP methods (GET, POST, PUT, DELETE)
- **OpenAPI Documentation**: Auto-generated Swagger/ReDoc documentation
- **Custom Swagger UI**: Customized documentation interface

### 8.2 Endpoint Organization
- Domain-based route organization
- Consistent naming conventions
- Versioned API structure

### 8.3 Response Format
- JSON responses
- Standardized error responses
- HTTP status code usage
- Pagination support where applicable

---

## 9. Future Enhancements

Based on the README checklist, planned enhancements include:
- Enhanced testing coverage
- Invoice generation improvements
- Notification system enhancements
- Report generation expansion
- Content management features
- Backup system improvements
- Client management features

---

## 10. Conclusion

The EPMS backend architecture provides a robust, scalable, and secure foundation for pharmacy management operations. The layered architecture ensures maintainability, the multi-database approach optimizes performance, and the comprehensive security model protects sensitive data. The system is designed to handle high concurrency, support multiple client types, and scale horizontally as business needs grow.

