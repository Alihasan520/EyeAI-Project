# Product Backend Core V1

## Workflow

```text
Admin bootstrap -> Login -> Patient -> Eye visit -> Analyze image
-> Prediction + explanation -> Timeline + alerts -> PDF report
```

## Protected endpoints

```text
POST /api/v1/auth/bootstrap
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/patients
GET  /api/v1/patients
GET  /api/v1/patients/{patient_id}
PATCH /api/v1/patients/{patient_id}
POST /api/v1/patients/{patient_id}/visits
POST /api/v1/visits/{visit_id}/analyze
POST /api/v1/visits/{visit_id}/notes
GET  /api/v1/patients/{patient_id}/timeline
GET  /api/v1/alerts
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/visits/{visit_id}/reports
GET  /api/v1/reports/{report_id}/download
GET  /api/v1/dashboard
```

The bootstrap endpoint works only while the users table is empty.
