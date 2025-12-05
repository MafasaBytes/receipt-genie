# Database Setup Guide

The backend supports both **SQLite** (for development) and **MySQL** (for production).

## Quick Start: SQLite (No Setup Required)

SQLite is configured by default and requires no setup. The database file will be created automatically at `backend/receipt_scanner.db`.

Just start the server:
```bash
python main.py
```

## MySQL Setup (Production)

### 1. Install MySQL

**Windows:**
- Download MySQL Installer from https://dev.mysql.com/downloads/installer/
- Install MySQL Server
- Note your root password

**macOS:**
```bash
brew install mysql
brew services start mysql
```

### 2. Create Database

Open MySQL command line or MySQL Workbench and run:

```sql
CREATE DATABASE receipt_scanner;
```

### 3. Configure Connection

Create a `.env` file in the `backend/` directory:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/receipt_scanner
```

Or update `config.py` directly:

```python
DATABASE_URL: str = "mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/receipt_scanner"
```

### 4. Test Connection

```bash
python -c "from database import test_connection; print('Connected!' if test_connection() else 'Failed!')"
```

## Switching Between Databases

### Use SQLite (Development)
```python
# In config.py or .env
DATABASE_URL = "sqlite:///./receipt_scanner.db"
```

### Use MySQL (Production)
```python
# In config.py or .env
DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/receipt_scanner"
```

## Troubleshooting

### "Can't connect to MySQL server"
- Make sure MySQL is running: `mysql --version`
- Check if MySQL service is started (Windows: Services, macOS: `brew services list`)
- Verify connection string in `.env` or `config.py`
- Check firewall settings

### "Database connection failed, but continuing"
- This is a warning, not an error
- The app will start but database features won't work
- Set `DATABASE_REQUIRED = True` in `config.py` to make it fail fast

### Reset SQLite Database
Simply delete `receipt_scanner.db` file - it will be recreated on next startup.

