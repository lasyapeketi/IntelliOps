# IntelliOps
### Intelligent Business Operations & Resource Optimization Platform

## Overview

IntelliOps is a machine learning platform designed to support business decision-making through predictive analytics, resource optimization, forecasting, and intelligent recommendations.

The platform integrates 11 business use cases into a unified application with a shared frontend and backend architecture.

## Technology Stack

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI
- **Machine Learning:** scikit-learn, pandas, NumPy
- **Database:** PostgreSQL/Supabase, if required
- **API Communication:** REST APIs with JSON
- **Version Control:** Git and GitHub

## Use Cases

1. Cost & Resource Optimization
2. Delivery Delay Prediction
3. Demand Forecasting
4. Inventory Optimization & Replenishment
5. Business Risk & Event Intelligence
6. Customer Behavior & Churn Prediction
7. Resource Allocation & Workforce Optimization
8. Customer Complaint & Sentiment Intelligence
9. Employee Attrition Prediction
10. Business Location Recommendation
11. Sales & Revenue Forecasting

## Architecture

The application follows a modular architecture:

**React Frontend → FastAPI Backend → Use-Case Services → Machine Learning Models → Standardized JSON Responses**

See [`docs/architecture.md`](docs/architecture.md) for the architecture details.

## Repository Structure

```text
IntelliOps/
├── backend/
├── frontend/
├── modules/
├── data/
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   └── contribution-guide.md
├── tests/
├── .gitignore
├── requirements.txt
└── README.md
```

This is the intended structure. Directories will be populated as implementation progresses.

## API Standards

All use cases must follow the common JSON request and response contracts documented in [`docs/api-contracts.md`](docs/api-contracts.md).

Use-case-specific input fields, prediction outputs, and evaluation metrics must be documented by the responsible member.

## Development Workflow

- `main` contains the stable project version.
- `develop` is the shared integration branch.
- Each member works on their assigned `feature/<use-case>` branch.
- Changes are submitted through pull requests targeting `develop`.
- Reviewed and tested changes are merged into `develop`.
- Only validated releases are merged into `main`.

Refer to [`docs/contribution-guide.md`](docs/contribution-guide.md) for the complete workflow.

## Setup

### Prerequisites

- Python 3.10 or a compatible version supported by the project's dependencies.
- Node.js and npm.
- Git.

### Clone the Repository

```bash
git clone https://github.com/lasyapeketi/IntelliOps.git
cd IntelliOps
```

### Backend Setup

Create and activate a Python virtual environment, then install the backend dependencies:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies after the team has added the required packages:

```bash
pip install -r requirements.txt
```

### Frontend Setup

Once the frontend has been initialized:

```bash
cd frontend
npm install
npm run dev
```

## Team Development Rules

- Follow the shared folder structure and API contracts.
- Keep each use case modular.
- Validate inputs and handle errors.
- Test changes before opening pull requests.
- Do not commit credentials, virtual environments, or unnecessary large datasets.
- Update documentation whenever agreed interfaces change.

## Documentation

- [System Architecture](docs/architecture.md)
- [API Contracts and Fixed JSON Format](docs/api-contracts.md)
- [Team Contribution Guide](docs/contribution-guide.md)

## Project Status

Development is in progress. Individual use cases will be integrated into the unified application as their implementations are completed and reviewed.
