
# Ticketer

Ticketer is a platform for buying tickets for events.


## Features

- Ticket booking/buying
- Google and facebook authentication integration
- Easy to use
- Cross-platform
- Social networks integration
- ...


## Deployment (docker deployment is not ready yet)

To deploy this project, all you need is docker with docker-compose plugin installed
Firstly, set environment variables and some variables in config.py.

Then, you just run it:
```bash
  docker compose up -d
```

Alternatively, you can run Ticketer without a docker. You need to install [Python](https://www.python.org/downloads/) >= 3.11 and [Poetry](https://python-poetry.org/docs/#installation).

Then, you need to install dependencies:
```bash
  poetry install --no-root
```

And run it:
```bash
  poetry run python -m ticketer
```
## Environment Variables

To run this project, you will need to add the following environment variables to your .env file or set them via `set` or `export` command depending on your system:

 - `OAUTH_GOOGLE_CLIENT_ID`
 - `OAUTH_GOOGLE_CLIENT_SECRET`
 - `JWT_KEY`


## Running Tests

To run tests, run the following command

```bash
  pytest -s --disable-warnings tests/
```


## License

[AGPL-3.0](https://choosealicense.com/licenses/agpl-3.0/)

