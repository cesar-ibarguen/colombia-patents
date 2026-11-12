"""
Translate the SQL file produced by patentes_a_sql.py (Spanish names) into English:
database, table and column names, plus the values of the lookup tables
(country, sector, application_type). The data rows are not changed.

Usage:
    python setup/to_english.py patentes.sql patents.sql
    mysql -u <user> -p < patents.sql
"""
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")

# English country names (ISO 3166-1, short common form)
en = {
    'AE': 'United Arab Emirates',
    'AG': 'Antigua and Barbuda',
    'AR': 'Argentina',
    'AT': 'Austria',
    'AU': 'Australia',
    'AZ': 'Azerbaijan',
    'BB': 'Barbados',
    'BE': 'Belgium',
    'BG': 'Bulgaria',
    'BH': 'Bahrain',
    'BM': 'Bermuda',
    'BR': 'Brazil',
    'BS': 'Bahamas',
    'BZ': 'Belize',
    'CA': 'Canada',
    'CH': 'Switzerland',
    'CL': 'Chile',
    'CN': 'China',
    'CO': 'Colombia',
    'CR': 'Costa Rica',
    'CU': 'Cuba',
    'CW': 'Curaçao',
    'CY': 'Cyprus',
    'CZ': 'Czech Republic',
    'DE': 'Germany',
    'DK': 'Denmark',
    'DO': 'Dominican Republic',
    'EC': 'Ecuador',
    'ES': 'Spain',
    'FI': 'Finland',
    'FR': 'France',
    'GB': 'United Kingdom',
    'GG': 'Guernsey',
    'GI': 'Gibraltar',
    'GR': 'Greece',
    'GT': 'Guatemala',
    'HK': 'Hong Kong',
    'HR': 'Croatia',
    'HU': 'Hungary',
    'IE': 'Ireland',
    'IL': 'Israel',
    'IM': 'Isle of Man',
    'IN': 'India',
    'IR': 'Iran',
    'IS': 'Iceland',
    'IT': 'Italy',
    'JE': 'Jersey',
    'JO': 'Jordan',
    'JP': 'Japan',
    'KE': 'Kenya',
    'KN': 'Saint Kitts and Nevis',
    'KP': 'North Korea',
    'KR': 'South Korea',
    'KY': 'Cayman Islands',
    'LB': 'Lebanon',
    'LI': 'Liechtenstein',
    'LK': 'Sri Lanka',
    'LU': 'Luxembourg',
    'LV': 'Latvia',
    'MC': 'Monaco',
    'MD': 'Moldova',
    'MT': 'Malta',
    'MU': 'Mauritius',
    'MX': 'Mexico',
    'MY': 'Malaysia',
    'NG': 'Nigeria',
    'NL': 'Netherlands',
    'NO': 'Norway',
    'NZ': 'New Zealand',
    'OM': 'Oman',
    'PA': 'Panama',
    'PE': 'Peru',
    'PH': 'Philippines',
    'PL': 'Poland',
    'PR': 'Puerto Rico',
    'PT': 'Portugal',
    'QA': 'Qatar',
    'RO': 'Romania',
    'RS': 'Serbia',
    'RU': 'Russia',
    'SA': 'Saudi Arabia',
    'SC': 'Seychelles',
    'SE': 'Sweden',
    'SG': 'Singapore',
    'SI': 'Slovenia',
    'SK': 'Slovakia',
    'SM': 'San Marino',
    'SV': 'El Salvador',
    'TC': 'Turks and Caicos Islands',
    'TD': 'Chad',
    'TH': 'Thailand',
    'TR': 'Turkey',
    'TW': 'Taiwan',
    'UA': 'Ukraine',
    'US': 'United States',
    'UY': 'Uruguay',
    'UZ': 'Uzbekistan',
    'VE': 'Venezuela',
    'VG': 'British Virgin Islands',
    'ZA': 'South Africa',
}

header = """-- Patent applications filed in Colombia 2000-2021 (SIC), relational model
-- Table, column and lookup-value names in English
DROP DATABASE IF EXISTS patents;
CREATE DATABASE patents CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE patents;

CREATE TABLE country (
    country_id  CHAR(2)      PRIMARY KEY,
    name        VARCHAR(80)  NOT NULL
);
CREATE TABLE sector (
    sector_id   INT          PRIMARY KEY,
    name        VARCHAR(40)  NOT NULL UNIQUE
);
CREATE TABLE application_type (
    type_id        INT          PRIMARY KEY,
    name           VARCHAR(60)  NOT NULL UNIQUE,
    procedure_type VARCHAR(40)  NOT NULL,
    route          VARCHAR(10)  NOT NULL      -- 'PCT' or 'National'
);
CREATE TABLE application (
    application_id VARCHAR(12)  PRIMARY KEY,
    filing_date    DATE         NOT NULL,
    type_id        INT          NOT NULL,
    sector_id      INT          NULL,
    country_id     CHAR(2)      NOT NULL,     -- country of the first applicant
    region         VARCHAR(80)  NULL,
    city           VARCHAR(80)  NULL,
    is_resident    BOOLEAN      NOT NULL,     -- 1 = applicant resident in Colombia
    FOREIGN KEY (type_id)    REFERENCES application_type(type_id),
    FOREIGN KEY (sector_id)  REFERENCES sector(sector_id),
    FOREIGN KEY (country_id) REFERENCES country(country_id),
    INDEX idx_filing_date (filing_date)
);
CREATE TABLE applicant (
    applicant_id INT          PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    country_code CHAR(2)      NULL           -- taken from the name; may not be in `country`
);
CREATE TABLE inventor (
    inventor_id INT          PRIMARY KEY,
    name        VARCHAR(150) NOT NULL
);
CREATE TABLE application_applicant (
    application_id VARCHAR(12) NOT NULL,
    applicant_id   INT         NOT NULL,
    list_order     TINYINT     NOT NULL,     -- 1 = main applicant
    PRIMARY KEY (application_id, applicant_id),
    FOREIGN KEY (application_id) REFERENCES application(application_id),
    FOREIGN KEY (applicant_id)   REFERENCES applicant(applicant_id)
);
CREATE TABLE application_inventor (
    application_id VARCHAR(12) NOT NULL,
    inventor_id    INT         NOT NULL,
    list_order     SMALLINT    NOT NULL,
    PRIMARY KEY (application_id, inventor_id),
    FOREIGN KEY (application_id) REFERENCES application(application_id),
    FOREIGN KEY (inventor_id)    REFERENCES inventor(inventor_id)
);

-- country: 100 rows
START TRANSACTION;
INSERT INTO country (country_id, name) VALUES
""" + ",\n".join(f"('{c}', '{n.replace(chr(39), chr(39)*2)}')" for c, n in en.items()) + """;
COMMIT;

-- sector: 5 rows
START TRANSACTION;
INSERT INTO sector (sector_id, name) VALUES
(1, 'Electrical engineering'),
(2, 'Mechanical engineering'),
(3, 'Instruments'),
(4, 'Other fields'),
(5, 'Chemistry');
COMMIT;

-- application_type: 5 rows
START TRANSACTION;
INSERT INTO application_type (type_id, name, procedure_type, route) VALUES
(1, 'Integrated circuit layout design', 'Layout design', 'National'),
(2, 'PCT invention patent', 'Invention patent', 'PCT'),
(3, 'National invention patent', 'Invention patent', 'National'),
(4, 'Utility model', 'Utility model', 'National'),
(5, 'PCT utility model', 'Utility model', 'PCT');
COMMIT;
"""
start = next(i for i, l in enumerate(lines) if l.startswith("-- solicitud: "))
rest = "\n".join(lines[start:])
R = [
 ("INSERT INTO solicitud (solicitud_id, fecha, naturaleza_id, sector_id, pais_id, region, ciudad, residente) VALUES",
  "INSERT INTO application (application_id, filing_date, type_id, sector_id, country_id, region, city, is_resident) VALUES"),
 ("INSERT INTO solicitante (solicitante_id, nombre, pais_codigo) VALUES",
  "INSERT INTO applicant (applicant_id, name, country_code) VALUES"),
 ("INSERT INTO inventor (inventor_id, nombre) VALUES", "INSERT INTO inventor (inventor_id, name) VALUES"),
 ("INSERT INTO solicitud_solicitante (solicitud_id, solicitante_id, orden) VALUES",
  "INSERT INTO application_applicant (application_id, applicant_id, list_order) VALUES"),
 ("INSERT INTO solicitud_inventor (solicitud_id, inventor_id, orden) VALUES",
  "INSERT INTO application_inventor (application_id, inventor_id, list_order) VALUES"),
]
for a, b in R:
    n = rest.count(a); assert n > 0, a; rest = rest.replace(a, b)
rest = re.sub(r"^-- solicitud_inventor: ([\d,]+) filas", r"-- application_inventor: \1 rows", rest, flags=re.M)
rest = re.sub(r"^-- solicitud_solicitante: ([\d,]+) filas", r"-- application_applicant: \1 rows", rest, flags=re.M)
rest = re.sub(r"^-- solicitud: ([\d,]+) filas", r"-- application: \1 rows", rest, flags=re.M)
rest = re.sub(r"^-- solicitante: ([\d,]+) filas", r"-- applicant: \1 rows", rest, flags=re.M)
rest = re.sub(r"^-- inventor: ([\d,]+) filas", r"-- inventor: \1 rows", rest, flags=re.M)
assert not re.search(r"^INSERT INTO (solicit|pais|naturaleza)", rest, re.M)
assert "filas" not in "\n".join(l for l in rest.split("\n") if l.startswith("--"))
open(dst, "w", encoding="utf-8").write(header + "\n" + rest)
