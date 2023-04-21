# stundenplan24-wrapper
A python wrapper for the `stundenplan24.de` API. As I don't have access to the teacher's API, this wrapper only supports the student's API. Also, this wrapper does not implement all features of the APIs because I could only test it on my school. 

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
There are 4 Views/APIs for students:

- [X] Indiware Mobil (Schüler)
- [ ] Vertretungsplan (Schüler)
- [ ] Wochenplan
- [ ] Stundenplan

And two for teachers:

- [ ] Indiware Mobil (Lehrer)
- [ ] Vertretungsplan (Lehrer)

They can be accessed at [www.stundenplan24.de](https://www.stundenplan24.de/).

## Translations from German

| German             | English               |
|--------------------|-----------------------|
| Fach               | subject, e.g. `PH`    |
| Kurs               | course, e.g. `7WInf1` |
| Schulklasse        | form, e.g. `6/3`      |
| Unterricht         | classes               |
| Schulstunde (Zeit) | period                |
| Unterrichtsstunde  | lesson                |
