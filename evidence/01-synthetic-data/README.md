# Synthetic Data Execution Evidence

**Workspace profile:** `fe-bar`

**Catalog:** `serverless_stable_febar_scottj_catalog`

**Schema/Volume:** `student_retention_bronze.raw_data`

**Seed:** `20260921`

**Run date:** `2026-09-21`

All records shown here are synthetic. No real student or customer data is present.

## Build Claim Proven

This package proves implementation-plan Task 2: the project can generate a
repeatable, realistically imbalanced synthetic university dataset with the six
contracted source entities, an embedded retention incident, intentional defect
rows for later quarantine testing, and no unintended referential-integrity
violations. The raw run record, exact validation SQL, returned query results,
and local verification record are retained beside this summary.

## Generator Runs

Initial bootstrap job run: `309550092725814`

Generator task run: `328056588598522`

Result: `TERMINATED / SUCCESS`

```json
{
  "rows": {
    "attendance_events": 300000,
    "engagement_events": 250000,
    "enrollments": 60000,
    "financial_events": 40000,
    "student_outcomes": 40000,
    "students": 20000
  },
  "run_date": "2026-09-21"
}
```

Deterministic rerun: `845407514884426`

Generator task run: `1060441874029780`

Result: `TERMINATED / SUCCESS`

The rerun used the identical seed and date and overwrote the same immutable partitions.

## Row Counts

SQL statement: `01f1b5e9-93ec-19b1-88b6-0c2dc887c349`

| Dataset | Rows |
|---|---:|
| attendance_events | 300,000 |
| engagement_events | 250,000 |
| enrollments | 60,000 |
| financial_events | 40,000 |
| student_outcomes | 40,000 |
| students | 20,000 |

## Nonuniform Program Distribution

SQL statement: `01f1b5e9-93f2-1a85-addb-5e28a4d16311`

| Program | Students | Average synthetic next-term net tuition |
|---|---:|---:|
| BUS | 6,032 | $9,069.66 |
| ARTS | 4,987 | $8,993.60 |
| STEM | 4,017 | $8,857.35 |
| HEALTH | 2,918 | $8,968.97 |
| EDU | 2,046 | $8,899.53 |

This deliberately skewed distribution prevents the uniform-data anti-pattern and gives cohort analysis meaningful differences in group size.

## Embedded Incident Pattern

SQL statement: `01f1b5e9-93e6-1cad-9283-ff81fca2b62f`

| Story segment | Attendance rate | Events |
|---|---:|---:|
| BASELINE | 88.6% | 299,740 |
| INCIDENT_PATTERN | 56.4% | 250 |

SQL statement: `01f1b5e9-93eb-1398-9e3a-7f862999d680`

| Incident cohort | Outcomes | Stop-out rate across label terms |
|---|---:|---:|
| false | 39,400 | 10.5% |
| true | 600 | 30.7% |

The incident cohort is substantially different but not deterministic: some incident students persist and some baseline students stop out.

## Referential Integrity

SQL statement: `01f1b5e9-b3df-13c9-a0e4-01d4e688a085`

Injected defect rows are excluded from this check because they exist specifically for the Bronze quarantine demonstration.

| Child dataset | Orphan rows |
|---|---:|
| attendance_events | 0 |
| engagement_events | 0 |
| enrollments | 0 |
| financial_events | 0 |
| student_outcomes | 0 |

## Deterministic Checksums

Overflow-safe checksums were calculated as `SUM(CAST(xxhash64(...) AS DECIMAL(38,0)))` before and after the identical rerun.

| Dataset | Before rerun | After rerun |
|---|---:|---:|
| attendance_events | -7302530383460132773522 | -7302530383460132773522 |
| engagement_events | -1870411590126981066431 | -1870411590126981066431 |
| enrollments | -1469215451743508725569 | -1469215451743508725569 |
| financial_events | -428521798841114519334 | -428521798841114519334 |
| student_outcomes | 1159512271447505876593 | 1159512271447505876593 |
| students | -1631310212048987621906 | -1631310212048987621906 |

Every checksum is identical, demonstrating deterministic and idempotent generation for a given seed and run date.

## Representative Synthetic Incident Students

| Student | Program | Level | Attendance rate | Missed assignments | Financial hold | Maximum balance | Historical stop-out label present |
|---|---|---|---:|---:|---|---:|---|
| STU-000042 | HEALTH | SENIOR | 93.3% | 0 | false | $5,231.78 | true |
| STU-000124 | ARTS | SOPHOMORE | 93.3% | 0 | true | $7,011.74 | true |
| STU-000185 | BUS | SOPHOMORE | 93.3% | 0 | false | $6,249.84 | false |
| STU-000246 | ARTS | JUNIOR | 100.0% | 0 | false | $1,323.75 | false |
| STU-000328 | BUS | FIRST_YEAR | 86.7% | 1 | true | $3,036.03 | false |

The row-level sample intentionally remains noisy. The solution will calculate recent-window features rather than treating incident membership or any single event as an outcome.
