ANALYTICS_SELECT_FIELDS = (
    "timestamp",
    "client_version",
    "client_is_corporate",
    "client_ip_address",
    "client_ref_url",
    "response_latest_version",
    "response_time_ms",
    "response_from_cache",
)

REF_HOST_SQL = """\
lower(
    arrayElement(
        splitByChar(':',
            arrayElement(
                splitByChar('/',
                    replaceRegexpOne(ifNull(client_ref_url, ''), '^[a-zA-Z]+://', '')
                ),
                1
            )
        ),
        1
    )
)"""

DEFAULT_ANALYTICS_QUERY = """\
WITH
    {ref_host_sql} AS ref_host
SELECT {fields}
FROM {table}
WHERE client_is_corporate = true
  AND (
      {ignore_domain} = ''
      OR ref_host = ''
      OR position(ref_host, {ignore_domain}) = 0
  )
ORDER BY timestamp DESC
LIMIT 200"""

UNIQUE_INSTALLATIONS_QUERY = """\
WITH
    {ref_host_sql} AS ref_host
SELECT
    toUnixTimestamp(toStartOfDay(first_seen)) AS ts,
    count() AS value
FROM
(
    SELECT
        ref_host,
        min(timestamp) AS first_seen
    FROM {table}
    WHERE ref_host != ''
      AND (
          {ignore_domain} = ''
          OR position(ref_host, {ignore_domain}) = 0
      )
    GROUP BY ref_host
)
GROUP BY toStartOfDay(first_seen)
ORDER BY ts"""

UNIQUE_CLIENTS_QUERY = """\
SELECT
    toUnixTimestamp(day) AS ts,
    sum(installs) OVER (
        ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS value
FROM (
    SELECT
        toStartOfDay(first_seen) AS day,
        count() AS installs
    FROM (
        WITH
            {ref_host_sql} AS ref_host
        SELECT
            ref_host,
            min(timestamp) AS first_seen
        FROM {table}
        WHERE ref_host != ''
          AND (
              {ignore_domain} = ''
              OR position(ref_host, {ignore_domain}) = 0
          )
        GROUP BY ref_host
    )
    GROUP BY day
) AS daily_installs
ORDER BY ts
"""


def clickhouse_identifier(value: str) -> str:
    """Quote a ClickHouse identifier from configuration."""
    return f"`{value.replace('`', '``')}`"


def analytics_table(database: str, table_name: str) -> str:
    return f"{clickhouse_identifier(database)}.{clickhouse_identifier(table_name)}"


def clickhouse_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_default_analytics_query(
    *,
    database: str,
    table_name: str,
    ignore_domain: str,
) -> str:
    return DEFAULT_ANALYTICS_QUERY.format(
        fields=", ".join(ANALYTICS_SELECT_FIELDS),
        ignore_domain=clickhouse_string(ignore_domain.strip().lower()),
        ref_host_sql=REF_HOST_SQL,
        table=analytics_table(database, table_name),
    )


def build_stat_queries(
    *,
    database: str,
    table_name: str,
    ignore_domain: str,
) -> list[dict[str, str]]:
    query_context = {
        "ignore_domain": clickhouse_string(ignore_domain.strip().lower()),
        "ref_host_sql": REF_HOST_SQL,
        "table": analytics_table(database, table_name),
    }
    return [
        {
            "title": "Unique Installations",
            "query": UNIQUE_INSTALLATIONS_QUERY.format(**query_context),
        },
        {
            "title": "Unique Clients",
            "query": UNIQUE_CLIENTS_QUERY.format(**query_context),
        },
    ]
