# IntelliOps — Team Contribution Guide

## 1. Purpose

This guide defines the common Git workflow, coding practices, testing requirements, and pull request process for all contributors to IntelliOps.

All team members must follow these rules to maintain consistent, reliable, and integratable code.

## 2. Branch Strategy

The repository uses the following branches:

- `main`: Stable, tested project version.
- `develop`: Shared integration branch.
- `feature/<use-case>`: Individual development branch for each assigned use case.

### Feature Branch Names

| Member | Feature Branch |
|---|---|
| 1 | `feature/cost-optimization` |
| 2 | `feature/delivery-delay` |
| 3 | `feature/demand-forecasting` |
| 4 | `feature/inventory-optimization` |
| 5 | `feature/business-risk` |
| 6 | `feature/customer-churn` |
| 7 | `feature/workforce-optimization` |
| 8 | `feature/complaint-sentiment` |
| 9 | `feature/employee-attrition` |
| 10 | `feature/location-recommendation` |
| 11 | `feature/sales-revenue-forecasting` |

The team coordinator creates the feature branches from the latest `develop` branch and ensures they are available on GitHub.

## 3. Standard Git Workflow

Each member must work only on their assigned feature branch.

### Step 1: Clone the Repository

New contributors should clone the repository once:

```bash
git clone https://github.com/lasyapeketi/IntelliOps.git
cd IntelliOps
```

### Step 2: Switch to the Assigned Branch

```bash
git fetch origin
git switch feature/<your-use-case>
```

Replace the placeholder with your assigned branch name.

### Step 3: Make Changes

- Work only on files related to your assigned use case unless a shared change has been coordinated.
- Follow the agreed folder structure and API contracts.
- Test changes before committing.

### Step 4: Commit Changes

```bash
git add .
git commit -m "feat: implement <use-case>"
```

Use meaningful commit messages describing the change.

Examples:

- `feat: implement delivery delay prediction`
- `fix: handle missing inventory inputs`
- `test: add demand forecasting tests`
- `docs: update API documentation`

Review `git status` before staging to avoid committing secrets, virtual environments, or large unnecessary files.

### Step 5: Push Changes

```bash
git push
```

For the first push of a new branch, use:

```bash
git push -u origin feature/<your-use-case>
```

### Step 6: Open a Pull Request

Create a pull request on GitHub with:

- **Base branch:** `develop`
- **Compare branch:** your assigned feature branch

Describe the implemented functionality, tests performed, API changes, and any known limitations.

### Step 7: Review and Merge

The coordinator or an assigned reviewer checks the code, tests, API compatibility, and documentation before merging into `develop`.

Do not merge untested or incompatible code.

## 4. Updating Your Feature Branch

Before starting new work, check whether your local branch is behind its remote counterpart:

```bash
git fetch origin
git status
```

If you need the latest shared integration changes, coordinate with the team and update your feature branch from `develop` using the agreed merge or rebase workflow. Resolve conflicts carefully and test again before pushing.

## 5. Coding Standards

- Use descriptive variable and function names.
- Follow Python conventions for backend code and TypeScript conventions for frontend code.
- Keep functions focused and reusable.
- Separate preprocessing, prediction logic, API routes, and UI components.
- Validate user input and handle errors.
- Avoid duplicating shared functionality.
- Add comments where the implementation is not self-explanatory.
- Do not commit passwords, API keys, tokens, or `.env` files.

## 6. Machine Learning Standards

Each use-case owner is responsible for:

- Identifying and documenting the dataset source.
- Cleaning and preprocessing data.
- Splitting training and testing data appropriately.
- Preventing data leakage.
- Selecting appropriate evaluation metrics.
- Saving and loading model artifacts reliably when applicable.
- Documenting assumptions, limitations, and prediction outputs.
- Testing the model on inputs beyond a single example.

Do not present placeholder or hardcoded outputs as genuine model predictions.

## 7. API Integration Standards

- Follow `docs/api-contracts.md`.
- Use the exact use-case identifiers defined in the API contract.
- Preserve the shared JSON response structure.
- Document use-case-specific input fields and prediction fields.
- Keep backend schemas, frontend TypeScript types, and tests consistent.
- Coordinate changes to shared interfaces before implementation.

## 8. Pull Request Checklist

Before requesting a review, verify that:

- [ ] The code runs successfully.
- [ ] Relevant tests pass.
- [ ] Input validation and error handling are implemented.
- [ ] API contracts are followed.
- [ ] No secrets or unnecessary large files are committed.
- [ ] Documentation is updated where necessary.
- [ ] Changes are limited to the intended scope.
- [ ] The pull request targets `develop`.

## 9. Definition of Done

A use case is complete when its required functionality is implemented, predictions or outputs are validated, tests pass, API integration works, documentation is available, and the changes have been reviewed and merged into `develop`.

## 10. Shared Documentation

All contributors must refer to:

- `README.md` — project overview and setup.
- `docs/architecture.md` — system architecture.
- `docs/api-contracts.md` — common JSON API formats.
- `docs/contribution-guide.md` — collaboration and Git workflow.

These documents are the shared reference for development and integration. Update them through reviewed changes whenever agreed project standards change.
