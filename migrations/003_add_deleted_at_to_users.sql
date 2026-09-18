-- Users are "soft deleted": we fill in deleted_at instead of removing the row.
-- This way old leads, deals and audit logs still point to a real user.
ALTER TABLE users ADD COLUMN deleted_at DATETIME NULL;

-- This extra unique key lets other tables use a foreign key on (company_id, user_id).
-- Then MySQL itself refuses to link a record to a user from a different company.
ALTER TABLE users ADD UNIQUE KEY uq_users_company_user (company_id, id);
