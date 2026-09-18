-- Counts requests per key (for example "login + IP address") inside a one-minute window.
CREATE TABLE rate_limits (
    bucket_key CHAR(64) PRIMARY KEY,
    hits INT UNSIGNED NOT NULL DEFAULT 1,
    expires_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
