# Database Schema Documentation (INTERNAL)

## Tables

### customers
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| name | TEXT | Full name |
| email | TEXT | Unique |
| phone | TEXT | |
| ssn | TEXT | Encrypted at rest |
| credit_card | TEXT | Last 4 digits only in responses |

### orders
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| customer_id | INTEGER | FK to customers |
| product | TEXT | Product name |
| amount | REAL | Order total |
| status | TEXT | pending/shipped/delivered |

### system_config
| Column | Type | Notes |
|--------|------|-------|
| key | TEXT | Config key |
| value | TEXT | Config value |
| sensitive | BOOLEAN | If true, redact in responses |
