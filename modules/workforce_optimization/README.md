# modules/workforce_optimization
# Workforce Optimization

## 1. Overview

The Resource Allocation & Workforce Optimization module recommends suitable employees for tasks based on their skills, availability, current workload, and hourly cost.

It ranks eligible employees using a weighted suitability score to help organizations make resource allocation decisions.

## 2. Objectives

* Match employee skills with task requirements.
* Exclude unavailable employees from recommendations.
* Consider remaining workload capacity.
* Ensure employee hourly costs fit within the task budget.
* Rank eligible employees by suitability score.

## 3. Technology Stack

* Python
* pytest for testing
* Rule-based weighted scoring

## 4. Scoring Methodology

The initial scoring weights are:

| Criterion                   |   Weight |
| --------------------------- | -------: |
| Skills match                |      40% |
| Availability                |      25% |
| Remaining workload capacity |      20% |
| Cost suitability            |      15% |
| **Total**                   | **100%** |

The suitability score is calculated as:

`Score = (Skills × 0.40) + (Availability × 0.25) + (Workload × 0.20) + (Cost × 0.15)`

Each component is scored between 0 and 100.

These weights are initial design choices and have not yet been empirically validated.

## 5. Eligibility Rules

An employee is eligible when:

* They are available.
* They possess all required task skills.
* Their hourly cost does not exceed the task budget.

Eligible employees are ranked in descending order of suitability score.

## 6. Module Structure

```text
workforce_optimization/
├── __init__.py
├── optimizer.py
├── service.py
├── README.md
└── tests/
    └── test_optimizer.py
```

* `optimizer.py`: Calculates suitability scores and ranks eligible employees.
* `service.py`: Provides the service function and structured recommendation response.
* `tests/test_optimizer.py`: Tests eligibility rules, ranking, validation, and service behavior.

## 7. Example Input

```python
task = {
    "required_skills": ["Python", "SQL"],
    "budget_per_hour": 100
}

employees = [
    {
        "employee_id": "E01",
        "skills": ["Python", "SQL"],
        "available": True,
        "current_workload": 20,
        "max_workload": 100,
        "hourly_cost": 80
    },
    {
        "employee_id": "E02",
        "skills": ["Python"],
        "available": True,
        "current_workload": 10,
        "max_workload": 100,
        "hourly_cost": 50
    }
]
```

## 8. Usage

```python
from modules.workforce_optimization.service import optimize_workforce

result = optimize_workforce(task, employees)
print(result)
```

The response includes the recommended employee, ranked eligible employees, the eligible employee count, scoring methodology, and weights.

## 9. Testing

Run the module tests from the repository root:

```bash
py -m pytest modules/workforce_optimization/tests/test_optimizer.py -v
```

The current test suite contains five tests covering employee eligibility, recommendation ranking, unavailable employees, invalid workload values, and empty employee lists.

## 10. Limitations and Future Improvements

* The scoring weights require validation against real allocation outcomes.
* The current engine uses rules rather than a trained machine-learning model.
* Deadline feasibility and task duration are not yet modeled.
* Workload is represented as a normalized remaining-capacity score.
* Future improvements may include workload scheduling, deadline-aware allocation, optimization across multiple tasks, and evaluation using historical assignment data.
* Integration with the shared IntelliOps API remains a separate step.
