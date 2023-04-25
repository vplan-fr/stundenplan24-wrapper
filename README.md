# stundenplan24-wrapper
A python wrapper for the `stundenplan24.de` API. This wrapper does not implement all features of the APIs because I can only test it on my school. 

## Requirements
- Python 3.9+
- requirements in [`requirements.txt`](requirements.txt)
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
There are four views for students:

- [X] Indiware Mobil (Schüler)
- [X] Vertretungsplan (Schüler)
- [ ] Wochenplan
- [ ] Stundenplan

And two for teachers:

- [ ] Indiware Mobil (Lehrer)
- [ ] Vertretungsplan (Lehrer)

They can be accessed at [www.stundenplan24.de](https://www.stundenplan24.de/).

There are at least twelve API endpoints. These are stored in [`studenplan24_py.Endpoints`](src/stundenplan24_py/client.py).

stundenplan24.de stores the files for about two weeks.

## Translations from German

| German             | English               |
|--------------------|-----------------------|
| Fach               | subject, e.g. `PH`    |
| Kurs               | course, e.g. `7WInf1` |
| Schulklasse        | form, e.g. `6c`       |
| Jahrgang           | year, e.g. 11         |
| Unterricht         | classes               |
| Schulstunde (Zeit) | period                |
| Unterrichtsstunde  | lesson                |
| Klausur            | exam                  |
| Kursleiter         | course teacher        |
