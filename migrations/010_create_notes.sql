CREATE TABLE notes (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    company_id BIGINT UNSIGNED NOT NULL,
    lead_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_notes_company_lead (company_id, lead_id, created_at),

    CONSTRAINT fk_notes_company FOREIGN KEY (company_id) REFERENCES companies(id),
    CONSTRAINT fk_notes_lead FOREIGN KEY (company_id, lead_id)
        REFERENCES leads(company_id, id),
    CONSTRAINT fk_notes_user FOREIGN KEY (company_id, user_id)
        REFERENCES users(company_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
