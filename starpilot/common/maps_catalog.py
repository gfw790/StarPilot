from __future__ import annotations

from openpilot.starpilot.common.maps_selection import COUNTRY_PREFIX, STATE_PREFIX, normalize_maps_selected


def tr_noop(value: str) -> str:
  """Mark a user-facing catalog label for translation without changing its stored value."""
  return value

MAP_SCHEDULE_LABELS = {
  0: tr_noop("Manually"),
  1: tr_noop("Weekly"),
  2: tr_noop("Monthly"),
}
MAP_SCHEDULE_VALUE_BY_LABEL = {label: value for value, label in MAP_SCHEDULE_LABELS.items()}
MAP_SCHEDULE_OPTIONS = [
  {"value": value, "label": label}
  for value, label in MAP_SCHEDULE_LABELS.items()
]

COUNTRY_REGION_GROUPS = (
  {"key": "africa", "title": "Africa", "regions": {"DZ": "Algeria", "AO": "Angola", "BJ": "Benin", "BW": "Botswana", "BF": "Burkina Faso", "BI": "Burundi", "CM": "Cameroon", "CF": "Central African Republic", "TD": "Chad", "KM": "Comoros", "CG": "Congo (Brazzaville)", "CD": "Congo (Kinshasa)", "DJ": "Djibouti", "EG": "Egypt", "GQ": "Equatorial Guinea", "ER": "Eritrea", "ET": "Ethiopia", "GA": "Gabon", "GM": "Gambia", "GH": "Ghana", "GN": "Guinea", "GW": "Guinea-Bissau", "CI": "Ivory Coast", "KE": "Kenya", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya", "MG": "Madagascar", "MW": "Malawi", "ML": "Mali", "MR": "Mauritania", "MA": "Morocco", "MZ": "Mozambique", "NA": "Namibia", "NE": "Niger", "NG": "Nigeria", "RW": "Rwanda", "SN": "Senegal", "SL": "Sierra Leone", "SO": "Somalia", "ZA": "South Africa", "SS": "South Sudan", "SD": "Sudan", "SZ": "Swaziland", "TZ": "Tanzania", "TG": "Togo", "TN": "Tunisia", "UG": "Uganda", "ZM": "Zambia", "ZW": "Zimbabwe"}},
  {"key": "antarctica", "title": "Antarctica", "regions": {"AQ": "Antarctica"}},
  {"key": "asia", "title": "Asia", "regions": {"AF": "Afghanistan", "AM": "Armenia", "AZ": "Azerbaijan", "BH": "Bahrain", "BD": "Bangladesh", "BT": "Bhutan", "BN": "Brunei", "KH": "Cambodia", "CN": "China", "CY": "Cyprus", "TL": "East Timor", "HK": "Hong Kong", "IN": "India", "ID": "Indonesia", "IR": "Iran", "IQ": "Iraq", "IL": "Israel", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan", "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LB": "Lebanon", "MY": "Malaysia", "MV": "Maldives", "MO": "Macao", "MN": "Mongolia", "MM": "Myanmar", "NP": "Nepal", "KP": "North Korea", "OM": "Oman", "PK": "Pakistan", "PS": "Palestine", "PH": "Philippines", "QA": "Qatar", "RU": "Russia", "SA": "Saudi Arabia", "SG": "Singapore", "KR": "South Korea", "LK": "Sri Lanka", "SY": "Syria", "TW": "Taiwan", "TJ": "Tajikistan", "TH": "Thailand", "TR": "Turkey", "TM": "Turkmenistan", "AE": "United Arab Emirates", "UZ": "Uzbekistan", "VN": "Vietnam", "YE": "Yemen"}},
  {"key": "europe", "title": "Europe", "regions": {"AL": "Albania", "AT": "Austria", "BY": "Belarus", "BE": "Belgium", "BA": "Bosnia and Herzegovina", "BG": "Bulgaria", "HR": "Croatia", "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France", "GE": "Georgia", "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IS": "Iceland", "IE": "Ireland", "IT": "Italy", "KZ": "Kazakhstan", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MK": "Macedonia", "MD": "Moldova", "ME": "Montenegro", "NL": "Netherlands", "NO": "Norway", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "RS": "Serbia", "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden", "CH": "Switzerland", "TR": "Turkey", "UA": "Ukraine", "GB": "United Kingdom"}},
  {"key": "north_america", "title": "North America", "regions": {"BS": "Bahamas", "BZ": "Belize", "CA": "Canada", "CR": "Costa Rica", "CU": "Cuba", "DO": "Dominican Republic", "SV": "El Salvador", "GL": "Greenland", "GD": "Grenada", "GT": "Guatemala", "HT": "Haiti", "HN": "Honduras", "JM": "Jamaica", "MX": "Mexico", "NI": "Nicaragua", "PA": "Panama", "TT": "Trinidad and Tobago", "US": "United States"}},
  {"key": "oceania", "title": "Oceania", "regions": {"AU": "Australia", "FJ": "Fiji", "TF": "French Southern Territories", "NC": "New Caledonia", "NZ": "New Zealand", "PG": "Papua New Guinea", "SB": "Solomon Islands", "VU": "Vanuatu"}},
  {"key": "south_america", "title": "South America", "regions": {"AR": "Argentina", "BO": "Bolivia", "BR": "Brazil", "CL": "Chile", "CO": "Colombia", "EC": "Ecuador", "FK": "Falkland Islands", "GY": "Guyana", "PY": "Paraguay", "PE": "Peru", "SR": "Suriname", "UY": "Uruguay", "VE": "Venezuela"}},
)

STATE_REGION_GROUPS = (
  {"key": "midwest", "title": "Midwest", "regions": {"IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri", "NE": "Nebraska", "ND": "North Dakota", "OH": "Ohio", "SD": "South Dakota", "WI": "Wisconsin"}},
  {"key": "northeast", "title": "Northeast", "regions": {"CT": "Connecticut", "ME": "Maine", "MA": "Massachusetts", "NH": "New Hampshire", "NJ": "New Jersey", "NY": "New York", "PA": "Pennsylvania", "RI": "Rhode Island", "VT": "Vermont"}},
  {"key": "south", "title": "South", "regions": {"AL": "Alabama", "AR": "Arkansas", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "KY": "Kentucky", "LA": "Louisiana", "MD": "Maryland", "MS": "Mississippi", "NC": "North Carolina", "OK": "Oklahoma", "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas", "VA": "Virginia", "WV": "West Virginia"}},
  {"key": "west", "title": "West", "regions": {"AK": "Alaska", "AZ": "Arizona", "CA": "California", "CO": "Colorado", "HI": "Hawaii", "ID": "Idaho", "MT": "Montana", "NV": "Nevada", "NM": "New Mexico", "OR": "Oregon", "UT": "Utah", "WA": "Washington", "WY": "Wyoming"}},
  {"key": "territories", "title": "Territories", "regions": {"AS": "American Samoa", "GU": "Guam", "MP": "Northern Mariana Islands", "PR": "Puerto Rico", "VI": "Virgin Islands"}},
)

MAP_SECTIONS = (
  {"key": "countries", "title": "Countries", "prefix": COUNTRY_PREFIX, "groups": COUNTRY_REGION_GROUPS},
  {"key": "states", "title": "U.S. States", "prefix": STATE_PREFIX, "groups": STATE_REGION_GROUPS},
)


def normalize_schedule_value(value) -> int:
  if isinstance(value, bytes):
    value = value.decode("utf-8", errors="ignore")

  if isinstance(value, str):
    value = value.strip()
    if not value:
      return 2
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
      value = int(value)
    else:
      value = MAP_SCHEDULE_VALUE_BY_LABEL.get(value, 2)

  try:
    normalized = int(value)
  except (TypeError, ValueError):
    return 2

  return normalized if normalized in MAP_SCHEDULE_LABELS else 2


def schedule_label(value) -> str:
  return MAP_SCHEDULE_LABELS[normalize_schedule_value(value)]


def schedule_param_value(value) -> str:
  return str(normalize_schedule_value(value))


def _sorted_regions(regions):
  return sorted(regions.items(), key=lambda item: item[1])


def get_maps_catalog():
  sections = []
  for section in MAP_SECTIONS:
    groups = []
    for group in section["groups"]:
      regions = [
        {
          "code": code,
          "label": label,
          "token": f"{section['prefix']}{code}",
        }
        for code, label in _sorted_regions(group["regions"])
      ]
      groups.append({
        "key": group["key"],
        "title": group["title"],
        "prefix": section["prefix"],
        "regions": regions,
      })
    sections.append({
      "key": section["key"],
      "title": section["title"],
      "prefix": section["prefix"],
      "groups": groups,
    })
  return sections


MAPS_CATALOG = get_maps_catalog()

# Translation extraction markers for catalog labels rendered by the device UI.
# The catalog values, region codes, and selection tokens remain unchanged.
MAP_CATALOG_DISPLAY_LABELS = (
  tr_noop('Countries'),
  tr_noop('Africa'),
  tr_noop('Algeria'),
  tr_noop('Angola'),
  tr_noop('Benin'),
  tr_noop('Botswana'),
  tr_noop('Burkina Faso'),
  tr_noop('Burundi'),
  tr_noop('Cameroon'),
  tr_noop('Central African Republic'),
  tr_noop('Chad'),
  tr_noop('Comoros'),
  tr_noop('Congo (Brazzaville)'),
  tr_noop('Congo (Kinshasa)'),
  tr_noop('Djibouti'),
  tr_noop('Egypt'),
  tr_noop('Equatorial Guinea'),
  tr_noop('Eritrea'),
  tr_noop('Ethiopia'),
  tr_noop('Gabon'),
  tr_noop('Gambia'),
  tr_noop('Ghana'),
  tr_noop('Guinea'),
  tr_noop('Guinea-Bissau'),
  tr_noop('Ivory Coast'),
  tr_noop('Kenya'),
  tr_noop('Lesotho'),
  tr_noop('Liberia'),
  tr_noop('Libya'),
  tr_noop('Madagascar'),
  tr_noop('Malawi'),
  tr_noop('Mali'),
  tr_noop('Mauritania'),
  tr_noop('Morocco'),
  tr_noop('Mozambique'),
  tr_noop('Namibia'),
  tr_noop('Niger'),
  tr_noop('Nigeria'),
  tr_noop('Rwanda'),
  tr_noop('Senegal'),
  tr_noop('Sierra Leone'),
  tr_noop('Somalia'),
  tr_noop('South Africa'),
  tr_noop('South Sudan'),
  tr_noop('Sudan'),
  tr_noop('Swaziland'),
  tr_noop('Tanzania'),
  tr_noop('Togo'),
  tr_noop('Tunisia'),
  tr_noop('Uganda'),
  tr_noop('Zambia'),
  tr_noop('Zimbabwe'),
  tr_noop('Antarctica'),
  tr_noop('Asia'),
  tr_noop('Afghanistan'),
  tr_noop('Armenia'),
  tr_noop('Azerbaijan'),
  tr_noop('Bahrain'),
  tr_noop('Bangladesh'),
  tr_noop('Bhutan'),
  tr_noop('Brunei'),
  tr_noop('Cambodia'),
  tr_noop('China'),
  tr_noop('Cyprus'),
  tr_noop('East Timor'),
  tr_noop('Hong Kong'),
  tr_noop('India'),
  tr_noop('Indonesia'),
  tr_noop('Iran'),
  tr_noop('Iraq'),
  tr_noop('Israel'),
  tr_noop('Japan'),
  tr_noop('Jordan'),
  tr_noop('Kazakhstan'),
  tr_noop('Kuwait'),
  tr_noop('Kyrgyzstan'),
  tr_noop('Laos'),
  tr_noop('Lebanon'),
  tr_noop('Macao'),
  tr_noop('Malaysia'),
  tr_noop('Maldives'),
  tr_noop('Mongolia'),
  tr_noop('Myanmar'),
  tr_noop('Nepal'),
  tr_noop('North Korea'),
  tr_noop('Oman'),
  tr_noop('Pakistan'),
  tr_noop('Palestine'),
  tr_noop('Philippines'),
  tr_noop('Qatar'),
  tr_noop('Russia'),
  tr_noop('Saudi Arabia'),
  tr_noop('Singapore'),
  tr_noop('South Korea'),
  tr_noop('Sri Lanka'),
  tr_noop('Syria'),
  tr_noop('Taiwan'),
  tr_noop('Tajikistan'),
  tr_noop('Thailand'),
  tr_noop('Turkey'),
  tr_noop('Turkmenistan'),
  tr_noop('United Arab Emirates'),
  tr_noop('Uzbekistan'),
  tr_noop('Vietnam'),
  tr_noop('Yemen'),
  tr_noop('Europe'),
  tr_noop('Albania'),
  tr_noop('Austria'),
  tr_noop('Belarus'),
  tr_noop('Belgium'),
  tr_noop('Bosnia and Herzegovina'),
  tr_noop('Bulgaria'),
  tr_noop('Croatia'),
  tr_noop('Czech Republic'),
  tr_noop('Denmark'),
  tr_noop('Estonia'),
  tr_noop('Finland'),
  tr_noop('France'),
  tr_noop('Georgia'),
  tr_noop('Germany'),
  tr_noop('Greece'),
  tr_noop('Hungary'),
  tr_noop('Iceland'),
  tr_noop('Ireland'),
  tr_noop('Italy'),
  tr_noop('Latvia'),
  tr_noop('Lithuania'),
  tr_noop('Luxembourg'),
  tr_noop('Macedonia'),
  tr_noop('Moldova'),
  tr_noop('Montenegro'),
  tr_noop('Netherlands'),
  tr_noop('Norway'),
  tr_noop('Poland'),
  tr_noop('Portugal'),
  tr_noop('Romania'),
  tr_noop('Serbia'),
  tr_noop('Slovakia'),
  tr_noop('Slovenia'),
  tr_noop('Spain'),
  tr_noop('Sweden'),
  tr_noop('Switzerland'),
  tr_noop('Ukraine'),
  tr_noop('United Kingdom'),
  tr_noop('North America'),
  tr_noop('Bahamas'),
  tr_noop('Belize'),
  tr_noop('Canada'),
  tr_noop('Costa Rica'),
  tr_noop('Cuba'),
  tr_noop('Dominican Republic'),
  tr_noop('El Salvador'),
  tr_noop('Greenland'),
  tr_noop('Grenada'),
  tr_noop('Guatemala'),
  tr_noop('Haiti'),
  tr_noop('Honduras'),
  tr_noop('Jamaica'),
  tr_noop('Mexico'),
  tr_noop('Nicaragua'),
  tr_noop('Panama'),
  tr_noop('Trinidad and Tobago'),
  tr_noop('United States'),
  tr_noop('Oceania'),
  tr_noop('Australia'),
  tr_noop('Fiji'),
  tr_noop('French Southern Territories'),
  tr_noop('New Caledonia'),
  tr_noop('New Zealand'),
  tr_noop('Papua New Guinea'),
  tr_noop('Solomon Islands'),
  tr_noop('Vanuatu'),
  tr_noop('South America'),
  tr_noop('Argentina'),
  tr_noop('Bolivia'),
  tr_noop('Brazil'),
  tr_noop('Chile'),
  tr_noop('Colombia'),
  tr_noop('Ecuador'),
  tr_noop('Falkland Islands'),
  tr_noop('Guyana'),
  tr_noop('Paraguay'),
  tr_noop('Peru'),
  tr_noop('Suriname'),
  tr_noop('Uruguay'),
  tr_noop('Venezuela'),
  tr_noop('U.S. States'),
  tr_noop('Midwest'),
  tr_noop('Illinois'),
  tr_noop('Indiana'),
  tr_noop('Iowa'),
  tr_noop('Kansas'),
  tr_noop('Michigan'),
  tr_noop('Minnesota'),
  tr_noop('Missouri'),
  tr_noop('Nebraska'),
  tr_noop('North Dakota'),
  tr_noop('Ohio'),
  tr_noop('South Dakota'),
  tr_noop('Wisconsin'),
  tr_noop('Northeast'),
  tr_noop('Connecticut'),
  tr_noop('Maine'),
  tr_noop('Massachusetts'),
  tr_noop('New Hampshire'),
  tr_noop('New Jersey'),
  tr_noop('New York'),
  tr_noop('Pennsylvania'),
  tr_noop('Rhode Island'),
  tr_noop('Vermont'),
  tr_noop('South'),
  tr_noop('Alabama'),
  tr_noop('Arkansas'),
  tr_noop('Delaware'),
  tr_noop('District of Columbia'),
  tr_noop('Florida'),
  tr_noop('Kentucky'),
  tr_noop('Louisiana'),
  tr_noop('Maryland'),
  tr_noop('Mississippi'),
  tr_noop('North Carolina'),
  tr_noop('Oklahoma'),
  tr_noop('South Carolina'),
  tr_noop('Tennessee'),
  tr_noop('Texas'),
  tr_noop('Virginia'),
  tr_noop('West Virginia'),
  tr_noop('West'),
  tr_noop('Alaska'),
  tr_noop('Arizona'),
  tr_noop('California'),
  tr_noop('Colorado'),
  tr_noop('Hawaii'),
  tr_noop('Idaho'),
  tr_noop('Montana'),
  tr_noop('Nevada'),
  tr_noop('New Mexico'),
  tr_noop('Oregon'),
  tr_noop('Utah'),
  tr_noop('Washington'),
  tr_noop('Wyoming'),
  tr_noop('Territories'),
  tr_noop('American Samoa'),
  tr_noop('Guam'),
  tr_noop('Northern Mariana Islands'),
  tr_noop('Puerto Rico'),
  tr_noop('Virgin Islands'),
)
MAP_TOKEN_LABELS = {
  region["token"]: region["label"]
  for section in MAPS_CATALOG
  for group in section["groups"]
  for region in group["regions"]
}
VALID_MAP_TOKENS = frozenset(MAP_TOKEN_LABELS)


def get_selected_map_tokens(selected_raw) -> list[str]:
  normalized = normalize_maps_selected(selected_raw)
  return [token for token in normalized.split(",") if token and token in VALID_MAP_TOKENS]


def sanitize_selected_locations_csv(values) -> str:
  if isinstance(values, str):
    raw = values
  elif values is None:
    raw = ""
  else:
    raw = ",".join(str(value).strip() for value in values if str(value).strip())

  tokens = get_selected_map_tokens(raw)
  return ",".join(tokens)


def get_selected_map_entries(selected_raw) -> list[dict[str, str]]:
  return [
    {"token": token, "label": MAP_TOKEN_LABELS[token]}
    for token in get_selected_map_tokens(selected_raw)
  ]
