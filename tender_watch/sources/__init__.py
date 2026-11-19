"""The banks this project knows how to collect. Add a new one here."""
from . import afdb, worldbank

SOURCES = {
    worldbank.NAME: worldbank.collect,
    afdb.NAME: afdb.collect,
}
