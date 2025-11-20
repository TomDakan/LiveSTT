# Data Dictionary

## Table: Users
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary Key |
| username | VARCHAR(50) | No | Unique username |
| email | VARCHAR(255) | No | User email |

## Table: Events
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary Key |
| timestamp | DATETIME | No | Event time |
