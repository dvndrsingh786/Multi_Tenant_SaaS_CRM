-- A history of important actions. Rows are only ever inserted, never updated.
CREATE TABLE audit_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    action VARCHAR(20) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    old_values JSON NULL,
    new_values JSON NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_audit_logs_company_created (company_id, created_at),
    INDEX idx_audit_logs_company_entity (company_id, entity_type, entity_id),

    CONSTRAINT fk_audit_logs_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (company_id, user_id)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
