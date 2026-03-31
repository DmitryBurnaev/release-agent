# {ignore_domain} placeholder is substituted at render time from CH settings
UNIQUE_INSTALLATIONS_QUERY = """\
WITH
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
    ) AS ref_host
SELECT
    toUnixTimestamp(toStartOfDay(first_seen)) AS ts,
    count() AS value
FROM
(
    SELECT
        ref_host,
        min(timestamp) AS first_seen
    FROM releases.release_requests
    WHERE ref_host != ''
      AND position(ref_host, '{ignore_domain}') = 0
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
            lower(
                arrayElement(
                    splitByChar(
                        ':',
                        arrayElement(
                            splitByChar(
                                '/',
                                replaceRegexpOne(
                                    ifNull(client_ref_url, ''),
                                    '^[a-zA-Z]+://',
                                    ''
                                )
                            ),
                            1
                        )
                    ),
                    1
                )
            ) AS ref_host
        SELECT
            ref_host,
            min(timestamp) AS first_seen
        FROM releases.release_requests
        WHERE ref_host != ''
          AND position(ref_host, '{ignore_domain}') = 0
        GROUP BY ref_host
    )
    GROUP BY day
) AS daily_installs
ORDER BY ts
"""
