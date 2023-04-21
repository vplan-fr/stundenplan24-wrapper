# stundenplan24-wrapper
A python wrapper for the `stundenplan24.de` API. This wrapper does not implement all features of the APIs because I can only test it on my school. 

## Requirements
- Python 3.9+
- `creds.json`

### `creds.json`
`creds.json` in this repository is the example school.
```json
{
    "school_number": {school_number},
    "user_name": "{username}",
    "password": "{password}"
}
```

## APIs
There are 4 Views for students:

- [X] Indiware Mobil (Schüler)
- [ ] Vertretungsplan (Schüler)
- [ ] Wochenplan
- [ ] Stundenplan

And two for teachers:

- [ ] Indiware Mobil (Lehrer)
- [ ] Vertretungsplan (Lehrer)

They can be accessed at [www.stundenplan24.de](https://www.stundenplan24.de/).

There are at least eight API endpoints. These are stored in [`studenplan24_py.Endpoints`](stundenplan24_py/client.py).

## Translations from German

| German             | English               |
|--------------------|-----------------------|
| Fach               | subject, e.g. `PH`    |
| Kurs               | course, e.g. `7WInf1` |
| Schulklasse        | form, e.g. `6c`       |
| Unterricht         | classes               |
| Schulstunde (Zeit) | period                |
| Unterrichtsstunde  | lesson                |
