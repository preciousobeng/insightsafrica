# Environment Setup

## Prerequisites

- Python 3.10+
- pip or conda
- NASA Earthdata account (free) — https://urs.earthdata.nasa.gov/

## Install Python Dependencies

```bash
cd GhanaFloodWatch
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## NASA Earthdata Authentication

IMERG data requires a free NASA Earthdata account.

1. Register at https://urs.earthdata.nasa.gov/
2. Create a `.env` file in the project root:

```
NASA_EARTHDATA_USER=your_username
NASA_EARTHDATA_PASSWORD=your_password
```

CHIRPS data requires no authentication.

## Ghana Bounding Box

Used in all data fetch scripts:

```
West:  -3.2617
East:   1.2166
South:  4.7370
North: 11.1748
```
