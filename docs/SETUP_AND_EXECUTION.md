# Setup and Execution Guide — Workforce Intelligence Platform

This guide provides end-to-end instructions for installing, configuring, running, testing, and troubleshooting the **Workforce Intelligence Platform** on Windows (PowerShell) and Unix-like operating systems.

---

## 1. Prerequisites

Before installing, ensure the host system satisfies:

- **Operating System**: Windows 10/11, macOS 12+, or Ubuntu 20.04+ LTS
- **Python**: Version `3.11.x` (Python 3.11.0 to 3.11.9 recommended)
- **Git**: Version `2.30+`
- **Database (Optional)**: MySQL 8.0+ (if connecting to a live database; offline mode runs fully using local CSV seeds)
- **Web Browser**: Chrome, Edge, Firefox, or Safari for viewing the Streamlit dashboard

---

## 2. Repository Cloning & Environment Setup

### Windows PowerShell

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/AkhileshwarMittapelly/workforce-intelligence-platform.git
   Set-Location -Path workforce-intelligence-platform
   ```

2. **Create Python virtual environment**:
   ```powershell
   py -3.11 -m venv .venv
   # Or using standard python:
   python -m venv .venv
   ```

3. **Activate virtual environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   *(If prompted with an execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in PowerShell).*

### Linux / macOS

1. **Clone and enter repository**:
   ```bash
   git clone https://github.com/AkhileshwarMittapelly/workforce-intelligence-platform.git
   cd workforce-intelligence-platform
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

---

## 3. Dependency Installation

Upgrade `pip` and install all required production and testing packages:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify installed packages:
```powershell
python -c "import streamlit, pandas, sqlalchemy, plotly, pytest; print('Dependencies installed successfully!')"
```

---

## 4. Environment Configuration

The application loads configuration via `src/config.py` backed by `python-dotenv` and `pydantic-settings`.

1. **Copy the example environment template**:
   ```powershell
   Copy-Item .env.example .env
   # On Linux/macOS: cp .env.example .env
   ```

2. **Inspect or update configuration variables**:
   ```ini
   # Database Connectivity
   DB_HOST=localhost
   DB_PORT=3306
   DB_NAME=workforce_intelligence
   DB_USER=root
   DB_PASSWORD=your_secure_password
   DB_POOL_SIZE=10
   DB_MAX_OVERFLOW=20
   DB_POOL_RECYCLE=3600

   # Application Settings
   APP_ENV=development
   APP_DEBUG=True
   APP_TITLE=Workforce Intelligence Platform

   # Streamlit Server
   STREAMLIT_SERVER_PORT=8501
   STREAMLIT_SERVER_ADDRESS=0.0.0.0
   ```

> [!NOTE]
> **Zero-Configuration Offline Mode**: If you do not have MySQL installed, you do not need to configure database credentials. The platform automatically detects unreachable database connections and transparently serves all data, forecasts, and gap analyses from verified local seed files in the `data/` directory.

---

## 5. Database Setup (Optional — For Live MySQL)

If you are using a live MySQL 8.0 server:

1. **Access MySQL shell as root or administrator**:
   ```sql
   CREATE DATABASE IF NOT EXISTS workforce_intelligence CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER IF NOT EXISTS 'workforce_user'@'localhost' IDENTIFIED BY 'WorkforceSecurePass2026!';
   GRANT ALL PRIVILEGES ON workforce_intelligence.* TO 'workforce_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. **Apply schema (tables, constraints, and views)**:
   ```powershell
   python database/apply_schema.py
   ```
   *Expected output: Schema created successfully with 12 tables and 5 analytical views.*

3. **Populate database with seed data**:
   ```powershell
   # In MySQL CLI:
   mysql -u workforce_user -p workforce_intelligence < data/seeds.sql
   ```

---

## 6. How to Run the Application

The platform includes a unified quickstart runner script (`run.py`):

### Option A: Standard Quickstart (Recommended)
```powershell
python run.py
```
This command automatically:
- Checks whether baseline seed data exists in `data/`. If missing, deterministically generates it.
- Launches the Streamlit dashboard on port `8501`.
- Automatically opens `http://localhost:8501` in your default browser.

### Option B: Direct Streamlit Launch
```powershell
streamlit run app/main.py --server.port 8501
```

---

## 7. Synthetic Data Generation

You can deterministically regenerate baseline data at either starter or full enterprise scale:

```powershell
# Starter scale: 50 employees, 30 skills, 20 projects, 53 ISO weeks
python run.py --datagen --scale starter

# Enterprise scale: 5,000 employees, 300 skills, 500 projects, 53 ISO weeks
python run.py --datagen --scale full
```

Or invoke the generator directly:
```powershell
python src/generators/synthetic_data_generator.py --scale starter --seed 20261022
```

---

## 8. Running the Automated Test Suite

Execute the full suite of **57 automated tests**:

```powershell
# Quickstart test invocation:
python run.py --test

# Or using Pytest directly:
pytest tests/ -v
```

### Running with Code Coverage
```powershell
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 9. Common Troubleshooting Steps

### 1. Port 8501 Already in Use
**Symptom**: `Port 8501 is already in use by another process.`  
**Solution**: Specify an alternate port when running:
```powershell
streamlit run app/main.py --server.port 8502
```

### 2. PowerShell Script Execution Disabled
**Symptom**: `File ... Activate.ps1 cannot be loaded because running scripts is disabled on this system.`  
**Solution**: Enable script execution for the current process:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 3. Database Connection Times Out
**Symptom**: `MySQL server has gone away` or `Can't connect to MySQL server on 'localhost'`.  
**Resolution**: No action required. The platform's Data Abstraction Layer (`db_service.py`) automatically logs a warning and shifts to offline mode, serving all requests directly from `data/*.csv`.

### 4. Missing Seed Data
**Symptom**: `FileNotFoundError: data/employees.csv not found.`  
**Solution**: Regenerate the baseline seed files with:
```powershell
python run.py --datagen --scale starter
```

### 5. Windows CRLF Line Endings in Git
**Symptom**: Git warning `LF will be replaced by CRLF the next time Git touches it`.  
**Solution**: This is normal behavior on Windows. To standardize, run:
```powershell
git config core.autocrlf true
```
