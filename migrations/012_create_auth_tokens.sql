-- Login tokens. We only store a SHA-256 hash of each token, never the token itself,
-- so a leaked database backup cannot be used to log in.
CREATE TABLE auth_tokens (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_auth_tokens_hash UNIQUE (token_hash),
    INDEX idx_auth_tokens_user (user_id),

    CONSTRAINT fk_auth_tokens_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
