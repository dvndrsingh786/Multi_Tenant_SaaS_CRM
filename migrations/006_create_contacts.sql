CREATE TABLE contacts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    owner_id BIGINT UNSIGNED NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(30) NULL,
    job_title VARCHAR(255) NULL,
    company_name VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,

    CONSTRAINT uq_contacts_company_contact UNIQUE (company_id, id),
    INDEX idx_contacts_company_created (company_id, deleted_at, created_at),
    INDEX idx_contacts_company_owner (company_id, owner_id),

    CONSTRAINT fk_contacts_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_contacts_owner FOREIGN KEY (company_id, owner_id)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
