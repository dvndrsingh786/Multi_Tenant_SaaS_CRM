-- Written by the background reminder job.
CREATE TABLE notifications (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    activity_id BIGINT UNSIGNED NOT NULL,
    message VARCHAR(512) NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- One reminder per activity. If the job runs twice, the second insert is ignored.
    CONSTRAINT uq_notifications_activity UNIQUE (activity_id),
    INDEX idx_notifications_user (company_id, user_id, created_at),

    CONSTRAINT fk_notifications_user FOREIGN KEY (company_id, user_id)
        REFERENCES users(company_id, id),
    CONSTRAINT fk_notifications_activity FOREIGN KEY (company_id, activity_id)
        REFERENCES activities(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
