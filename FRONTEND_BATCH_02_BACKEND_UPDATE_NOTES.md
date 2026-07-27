# Frontend Batch 02 Backend Support

This update adds protected account management and visit-list endpoints required by EyeAI Frontend Batch 02.

## Security model

- Public self-registration is not available.
- `/auth/bootstrap` is usable only while the users table is empty and bootstrap is enabled.
- The first account receives the `admin` role.
- Administrators create clinician accounts from Users & Access.
- Users may update their own name/email and change their own password.
- Only administrators may list, create, disable, or reset other user accounts.
- Administrators cannot disable themselves or remove their own administrator role.

## API version

`3.2.0`
