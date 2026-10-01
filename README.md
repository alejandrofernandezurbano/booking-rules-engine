# Booking rules engine

> **ES:** Motor de reglas para reservar espacios compartidos (auditorios, salas, laboratorios):
> sin choques ni duplicados, horarios y capacidad, límite semanal por rol y aprobación del
> administrador cuando se pasa el límite. Reescritura desde cero, con datos inventados, de la lógica
> que diseñé para el sistema de reservas de espacios de un hospital de alta complejidad (Power Apps).

Shared-space booking breaks in predictable ways: double bookings, the same person booking the
same slot twice, one user hoarding the auditorium, bookings outside opening hours. In
production I built this logic in Power Apps for a large hospital (auditorium, meeting rooms and
buildings, with an occupancy dashboard in Power BI). This repository is an independent
re-implementation in plain Python so the rules can be read, tested and reused.

## Rules

| Rule | Result |
|---|---|
| Same space, overlapping time, another user | rejected |
| Same user, same space, same time (duplicate) | rejected |
| Same user in two spaces at once | rejected |
| Outside opening hours, on weekends, in the past, too far ahead | rejected |
| More attendees than capacity | rejected |
| Duration below minimum or above maximum | rejected |
| Weekly limit by role reached, **no** justification | rejected, with how to ask |
| Weekly limit by role reached, **with** justification | `pending_approval` → admin approves or rejects |
| Admin roles | no weekly limit |

All reasons are returned at once, so the user fixes everything in one go. Cancelled and
rejected bookings free the slot and the weekly quota. `occupancy(day)` feeds a dashboard.

## Run it

```bash
python demo.py
python -m unittest discover -s tests -t .   # 10 tests
```

```
OK  Ana books room 201, Mon 9-10                     status=confirmed
NO  Ana books the same slot again (duplicate)        status=-
      - You already have this space booked at that time (duplicate).
NO  Ana's 4th booking this week, no reason           status=-
      - Your weekly limit is 3 bookings. Add a justification to ask an administrator for approval.
OK  Ana's 4th booking, with a justification          status=pending_approval
    Marta approves booking #4 -> confirmed
```

Python 3.10+, no dependencies. Limits per role live in `Policy`.

## How this maps to Power Platform

The same rules, in the production version, lived in Power Apps formulas and Power Automate
flows over SharePoint / Dataverse: a validation before saving, a role list in SharePoint for
special limits, an approval flow to the administrator, and a Power BI occupancy report. This
Python version is the specification those pieces implement.

## Author

Alejandro Fernández Urbano — Power Platform & AI automation · **Calidá S.A.S.** (Colombia).
[LinkedIn](https://www.linkedin.com/in/alejandro-fernandez-urbano) · alejandrofernandezurbano@gmail.com
