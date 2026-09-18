CREATE TABLE customers (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    lead_id BIGINT UNSIGNED NULL,
    assigned_to BIGINT UNSIGNED NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(30) NULL,
    company_name VARCHAR(255) NULL,
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,

    CONSTRAINT uq_customers_company_customer UNIQUE (company_id, id),

    -- One lead can become at most one customer. This is our safety net against
    -- double conversion, even if two requests arrive at the same moment.
    CONSTRAINT uq_customers_lead UNIQUE (company_id, lead_id),

    INDEX idx_customers_company_created (company_id, deleted_at, created_at),
    INDEX idx_customers_company_assigned (company_id, assigned_to),

    CONSTRAINT fk_customers_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_customers_lead FOREIGN KEY (company_id, lead_id)
        REFERENCES leads(company_id, id),
    CONSTRAINT fk_customers_assigned_user FOREIGN KEY (company_id, assigned_to)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
