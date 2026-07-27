# EyeAI Frontend Batch 02

## Added

- First administrator workspace initialization from the login page.
- My Profile with editable clinician name and email.
- Protected password change workflow.
- Users & Access administration for creating, enabling, disabling, and resetting clinician accounts.
- Patient registry with live search and patient creation.
- Patient profile with demographics, editable notes, and readable identifiers.
- Right-eye and left-eye visit separation.
- Eye-specific longitudinal clinical timeline.
- Visit creation and redirect into the analysis workflow.
- Responsive visits registry.
- Preview datasets for the new screens.
- Extended Arabic and English translations.

## Backend API 3.2.0

- GET `/api/v1/auth/bootstrap-status`
- PATCH `/api/v1/auth/me`
- POST `/api/v1/auth/change-password`
- GET/POST/PATCH `/api/v1/users`
- POST `/api/v1/users/{user_ref}/reset-password`
- GET `/api/v1/visits`
- GET `/api/v1/visits/{visit_ref}`

Public self-registration remains disabled. The first administrator is created only while the users table is empty. Additional users are created by an administrator.
