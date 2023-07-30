# stundenplan24-wrapper
A python wrapper for the `stundenplan24.de` API and XML files of the Indiware Stundenplaner. This wrapper is probably not complete.

## Requirements
- Python 3.9+
- requirements in [`requirements.txt`](requirements.txt)

## APIs
There are four views for students:

- [X] Indiware Mobil (Schüler)
- [X] Vertretungsplan (Schüler)
- [ ] Wochenplan
- [ ] Stundenplan

And two for teachers:

- [X] Indiware Mobil (Lehrer)
- [X] Vertretungsplan (Lehrer)

They can be accessed at [www.stundenplan24.de](https://www.stundenplan24.de/).

There are at least twelve API endpoints. These are stored in [`studenplan24_py.Endpoints`](src/stundenplan24_py/client.py).

stundenplan24.de deletes any plan files older than ten days automatically.

## Translations from German

| German             | English               |
|--------------------|-----------------------|
| Fach               | subject, e.g. `PH`    |
| Kurs               | course, e.g. `7WInf1` |
| Schulklasse        | form, e.g. `6c`       |
| Jahrgang           | year, e.g. 11         |
| Unterricht         | class(es)             |
| Schulstunde (Zeit) | period                |
| Unterrichtsstunde  | lesson                |
| Klausur            | exam                  |
| Kursleiter         | course teacher        |
| (Pausen)Aufsicht   | break supervision     |
