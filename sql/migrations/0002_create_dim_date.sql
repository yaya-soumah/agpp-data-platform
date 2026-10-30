-- Calendar dimension: one row per day (ADR-0009).
-- Names are written out in English so they do not depend on database locale.
CREATE TABLE warehouse.dim_date (
    date_key        integer  PRIMARY KEY,
    full_date       date     NOT NULL UNIQUE,
    year            smallint NOT NULL,
    quarter         smallint NOT NULL,
    month           smallint NOT NULL,
    month_name      text     NOT NULL,
    day_of_month    smallint NOT NULL,
    iso_day_of_week smallint NOT NULL,
    day_name        text     NOT NULL,
    iso_week        smallint NOT NULL,
    iso_year        smallint NOT NULL,
    is_weekend      boolean  NOT NULL
);

COMMENT ON TABLE warehouse.dim_date IS
    'Grain: one row per calendar day from 2000-01-01 to 2049-12-31.';
COMMENT ON COLUMN warehouse.dim_date.date_key IS 'YYYYMMDD as an integer.';
COMMENT ON COLUMN warehouse.dim_date.iso_day_of_week IS '1 = Monday ... 7 = Sunday.';

INSERT INTO warehouse.dim_date (
    date_key, full_date, year, quarter, month, month_name, day_of_month,
    iso_day_of_week, day_name, iso_week, iso_year, is_weekend
)
SELECT
    to_char(d, 'YYYYMMDD')::integer,
    d,
    extract(year FROM d)::smallint,
    extract(quarter FROM d)::smallint,
    extract(month FROM d)::smallint,
    (ARRAY['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December'])[extract(month FROM d)::int],
    extract(day FROM d)::smallint,
    extract(isodow FROM d)::smallint,
    (ARRAY['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
           'Sunday'])[extract(isodow FROM d)::int],
    extract(week FROM d)::smallint,
    extract(isoyear FROM d)::smallint,
    extract(isodow FROM d) >= 6
FROM (
    SELECT date '2000-01-01' + n AS d
    FROM generate_series(0, date '2049-12-31' - date '2000-01-01') AS n
) AS days;
