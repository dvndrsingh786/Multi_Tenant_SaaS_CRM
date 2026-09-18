CREATE TABLE deals (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NULL,
    lead_id BIGINT UNSIGNED NULL,
    assigned_to BIGINT UNSIGNED NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    value DECIMAL(15, 2) NOT NULL DEFAULT 0,
    stage ENUM('NEW', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST')
        NOT NULL DEFAULT 'NEW',
    expected_close_date DATE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,

    CONSTRAINT uq_deals_company_deal UNIQUE (company_id, id),
    INDEX idx_deals_company_created (company_id, deleted_at, created_at),
    INDEX idx_deals_company_stage (company_id, stage),
    INDEX idx_deals_company_assigned (company_id, assigned_to),

    CONSTRAINT fk_deals_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_deals_customer FOREIGN KEY (company_id, customer_id)
        REFERENCES customers(company_id, id),
    CONSTRAINT fk_deals_lead FOREIGN KEY (company_id, lead_id)
        REFERENCES leads(company_id, id),
    CONSTRAINT fk_deals_assigned_user FOREIGN KEY (company_id, assigned_to)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
