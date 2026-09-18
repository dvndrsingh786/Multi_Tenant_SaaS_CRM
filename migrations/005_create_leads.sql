CREATE TABLE leads (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    assigned_to BIGINT UNSIGNED NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(30) NULL,
    company_name VARCHAR(255) NULL,
    job_title VARCHAR(255) NULL,
    source ENUM('WEBSITE', 'REFERRAL', 'LINKEDIN', 'EMAIL', 'PHONE', 'ADVERTISEMENT', 'OTHER')
        NOT NULL DEFAULT 'OTHER',
    status ENUM('NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST')
        NOT NULL DEFAULT 'NEW',
    estimated_value DECIMAL(15, 2) NOT NULL DEFAULT 0,
    converted_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,

    -- Other tables point at (company_id, id), so they can only link to leads of the same company.
    CONSTRAINT uq_leads_company_lead UNIQUE (company_id, id),

    -- Every index starts with company_id because every query filters by company first.
    INDEX idx_leads_company_created (company_id, deleted_at, created_at),
    INDEX idx_leads_company_status (company_id, status),
    INDEX idx_leads_company_assigned (company_id, assigned_to),
    INDEX idx_leads_company_email (company_id, email),

    CONSTRAINT fk_leads_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_leads_assigned_user FOREIGN KEY (company_id, assigned_to)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
