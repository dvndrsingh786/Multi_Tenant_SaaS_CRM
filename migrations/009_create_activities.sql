CREATE TABLE activities (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    lead_id BIGINT UNSIGNED NULL,
    customer_id BIGINT UNSIGNED NULL,
    deal_id BIGINT UNSIGNED NULL,
    type ENUM('CALL', 'EMAIL', 'MEETING', 'TASK', 'NOTE') NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    due_at DATETIME NULL,
    completed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT uq_activities_company_activity UNIQUE (company_id, id),
    INDEX idx_activities_company_created (company_id, created_at),
    INDEX idx_activities_company_user (company_id, user_id),

    -- Used by the reminder job: "unfinished activities that are due soon".
    INDEX idx_activities_due (completed_at, due_at),

    CONSTRAINT fk_activities_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_activities_user FOREIGN KEY (company_id, user_id)
        REFERENCES users(company_id, id),
    CONSTRAINT fk_activities_lead FOREIGN KEY (company_id, lead_id)
        REFERENCES leads(company_id, id),
    CONSTRAINT fk_activities_customer FOREIGN KEY (company_id, customer_id)
        REFERENCES customers(company_id, id),
    CONSTRAINT fk_activities_deal FOREIGN KEY (company_id, deal_id)
        REFERENCES deals(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
