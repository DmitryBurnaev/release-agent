# {ignore_domain} placeholder is substituted at render time from CH settings
UNIQUE_INSTALLATIONS_QUERY = """\
SELECT
    timestamp,
    client_version,
    client_is_corporate,
    client_ip_address,
    client_ref_url,
    response_latest_version,
    response_time_ms,
    response_from_cache
FROM
(
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
        timestamp,
        client_version,
        client_is_corporate,
        client_ip_address,
        client_ref_url,
        response_latest_version,
        response_time_ms,
        response_from_cache,
        ref_host
    FROM releases.release_requests
    WHERE ref_host != ''
      AND position(ref_host, '{ignore_domain}') = 0
    ORDER BY ref_host, timestamp DESC
    LIMIT 1 BY ref_host
)
ORDER BY timestamp DESC
LIMIT 200"""

UNIQUE_INSTALLATIONS_COUNT_QUERY = """\
WITH
    lower(
        arrayElement(
            splitByChar(':',
                arrayElement(
                    splitByChar('/',
                        replaceRegexpOne(\
ifNull(client_ref_url, ''), '^[a-zA-Z]+://', '')
                    ),
                    1
                )
            ),
            1
        )
    ) AS ref_host
SELECT uniqExact(ref_host) AS unique_ref_hosts
FROM releases.release_requests
WHERE ref_host != ''
  AND position(ref_host, '{ignore_domain}') = 0"""
